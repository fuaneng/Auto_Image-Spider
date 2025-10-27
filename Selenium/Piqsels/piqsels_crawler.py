import os
import csv
import time
import redis
import urllib3
import undetected_chromedriver as uc 
from threading import Lock
from bs4 import BeautifulSoup
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from requests.exceptions import RequestException
import random # 引入 random 用于随机等待

# 忽略 Requests 的 SSL 警告 (虽然这个版本没有用到 Requests，但保留这个习惯)
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# --- 配置常量 ---
REDIS_HOST = 'localhost'
REDIS_PORT = 6379
REDIS_KEY = 'piqsels_image_url_set' 
TAG_FILE_PATH = r"R:\py\Auto_Image-Spider\Requests\Piqsels\ram_tag_list.txt"
CSV_DIR_PATH = r"R:\py\Auto_Image-Spider\Requests\Piqsels"
CSV_FILENAME = "piqsels_data.csv"
BASE_URL_TEMPLATE = "https://www.piqsels.com/en/search?q={tag}&page={page}"

# !! 您的自定义驱动路径 !!
CUSTOM_DRIVER_PATH = r"C:\Program Files\Google\chromedriver-win64\chromedriver.exe"

class PiqselsImageCrawler:
    """
    针对 piqsels.com 的单线程串行爬虫，集成 Selenium 处理反爬验证，
    并使用 Redis/内存进行去重。
    """

    def __init__(self, csv_dir_path, csv_filename, driver_path, redis_host=REDIS_HOST, redis_port=REDIS_PORT):
        
        self.csv_dir_path = csv_dir_path
        self.csv_path = os.path.join(self.csv_dir_path, csv_filename) 
        self.csv_lock = Lock() 
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image:apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.9',
            'Accept-Language': 'en-US,en;q=0.9,zh-CN;q=0.8,zh;q=0.7'
        }
        
        # --- Redis/内存 去重初始化逻辑 ---
        self.redis = None
        self.visited_urls = set()
        self._init_deduplication(redis_host, redis_port)

        # --- Selenium 初始化 (使用指定路径) ---
        self.driver = None
        print("⏳ 正在初始化 Selenium 浏览器...")
        try:
            self.driver = uc.Chrome(
                headless=False, 
                use_subprocess=True,
                driver_executable_path=driver_path 
            )
            # 设置隐式等待，作为额外的缓冲机制
            self.driver.implicitly_wait(2) 
            print("✅ Selenium 浏览器初始化成功。")
        except Exception as e:
            print(f"❌ Selenium 浏览器初始化失败: {e}")
            self.driver = None


    def _init_deduplication(self, redis_host, redis_port):
        """初始化 Redis 或内存去重机制。"""
        try:
            self.redis = redis.StrictRedis(host=redis_host, port=redis_port, decode_responses=True)
            self.redis.ping()
            print("✅ Redis 连接成功，使用 Redis 集合进行去重。")
        except redis.exceptions.ConnectionError:
            print("⚠️ Redis 连接失败，将使用内存去重。") 
            self.redis = None
            self.visited_urls = set()
        except Exception as e:
            print(f"⚠️ Redis 初始化遇到其他错误 ({e})，将使用内存去重。")
            self.redis = None
            self.visited_urls = set()


    def _is_url_visited(self, url):
        """检查 URL 是否已被访问（即已保存）。"""
        unique_id = os.path.basename(url) 
        
        if self.redis:
            return not self.redis.sadd(REDIS_KEY, unique_id)
        else:
            if unique_id in self.visited_urls:
                return True
            self.visited_urls.add(unique_id)
            return False


    def write_to_csv(self, title, name, url, tag):
        """
        写入 CSV 方法。
        """
        csv_path = self.csv_path
        try:
            # 单线程不需要 Lock，但保留 structure 以防未来更改
            os.makedirs(os.path.dirname(csv_path), exist_ok=True)
            is_file_empty = not os.path.exists(csv_path) or os.stat(csv_path).st_size == 0
            
            with open(csv_path, 'a', newline='', encoding='utf-8-sig') as f:
                writer = csv.writer(f)
                
                if is_file_empty:
                    writer.writerow(['Title', 'ImageName', 'URL', 'TAG'])
                    
                writer.writerow([title, name, url, tag])
            print(f"[{tag}] [✓] 成功写入 CSV: {name}")
        except Exception as e:
            print(f"[{tag}] [✗] 写入 CSV 出错: {e}")


    def _get_page_source(self, url, tag, page_num):
        """
        使用 Selenium 驱动浏览器，处理 Cloudflare 验证并获取页面源代码。
        返回：HTML内容（成功），None（可重试失败，如网络超时/验证卡住），""（不可重试失败，如 No results）
        """
        if not self.driver:
            return None 

        print(f"[{tag}] 尝试访问 URL: {url}")
        self.driver.get(url)

        try:
            # 1. 等待 ID 为 "main" 的主内容区域加载出来 (最长 60 秒用于手动 Cloudflare)
            WebDriverWait(self.driver, 60).until(
                EC.presence_of_element_located((By.ID, "main"))
            )
            
            # --- 检查 “No results” 元素 (快速跳过逻辑) ---
            try:
                # 尝试找到 <span class="notfound">No results</span> 元素
                no_results_element = self.driver.find_element(By.CLASS_NAME, "notfound")
                if no_results_element and no_results_element.text.strip().lower() == "no results":
                    print(f"[{tag}] [Page {page_num}] ❌ 检测到 'No results'，**快速跳过当前标签，无需重试**。")
                    return "" # 返回 "" 作为特殊标记
            except Exception:
                pass
            
            # 2. 继续等待图片列表 (等待第一个图片元素出现)
            try:
                WebDriverWait(self.driver, 5).until( 
                    EC.presence_of_element_located((By.CSS_SELECTOR, "#flow li.item"))
                )
            except Exception:
                # 检查是否是 Cloudflare 再次触发
                page_text = self.driver.page_source
                if "Just a moment" in page_text or "captcha" in page_text:
                    print(f"[{tag}] ⚠️ 检测到 Cloudflare 再次触发验证，请手动处理浏览器窗口。")
                    return None # 返回 None 允许重试，给用户时间去处理浏览器窗口

                print(f"[{tag}] ⚠️ 页面加载超时，未找到图片元素或 Cloudflare 再次触发。")
                return None
            
            print(f"[{tag}] ✅ 页面加载成功或已通过验证。")
            
            # 3. 检查 404 
            page_text = self.driver.page_source
            if "page not found" in page_text.lower() or self.driver.title.lower().startswith("404"):
                 print(f"[{tag}] ⚠️ 检测到可能是 404 页面，停止分页。")
                 return None 
            
            return self.driver.page_source

        except Exception as e:
            # 页面加载超时或 Cloudflare 验证卡住
            print(f"[{tag}] ⚠️ 页面加载超时或出现异常 (Message: {e.msg if hasattr(e, 'msg') else e})。返回 None 允许重试。")
            return None


    def _parse_page(self, html_content, tag):
        """
        解析 HTML 内容，提取图片信息。
        """
        if not html_content:
            return []

        soup = BeautifulSoup(html_content, 'html.parser')
        ul_flow = soup.find('ul', id='flow')
        
        if not ul_flow:
             # 在 _get_page_source 中已检查过，这里无需重复打印
             return []

        image_items = ul_flow.find_all('li', class_='item')
        
        if not image_items:
            # 在 _get_page_source 中已处理 No results/超时，这里无需重复打印
            return [] 

        data_list = []
        for item in image_items:
            try:
                img_tag = item.find('img', class_='lazy')
                title = img_tag.get('alt', 'N/A').strip() if img_tag else 'N/A'

                license_a_tag = item.find('a', rel="license") 
                if license_a_tag:
                    about_url = license_a_tag.get('about')
                    if about_url and about_url.endswith('-thumbnail.jpg'):
                        full_url = about_url.replace('-thumbnail.jpg', '.jpg')
                        image_name = os.path.basename(full_url)
                    else:
                        continue 
                else:
                    continue 

                if self._is_url_visited(full_url):
                    print(f"[{tag}] [~] URL 已存在，跳过: {image_name}")
                    continue

                data_list.append({
                    'title': title, 'name': image_name, 'url': full_url, 'tag': tag
                })

            except Exception as e:
                print(f"[{tag}] [✗] 解析单个图片信息时出错: {e}")
                continue

        return data_list


    def start_crawl_for_tag(self, tag):
        """
        针对单个标签，执行串行分页爬取。在加载失败或无数据时快速跳过。
        """
        if not self.driver:
            print(f"[{tag}] [✗] 爬虫无法启动，Selenium 驱动缺失。")
            return

        print(f"\n--- ⚡️ 开始爬取标签: {tag} ---")
        page = 1
        max_retries = 3 

        while True:
            url = BASE_URL_TEMPLATE.format(tag=tag, page=page)
            print(f"[{tag}] [Page {page}] 正在处理...")
            
            html_content = None
            retry_count = 0
            
            # --- 页面加载与重试逻辑 ---
            while retry_count < max_retries:
                html_content = self._get_page_source(url, tag, page) 
                
                if html_content == "": 
                    # 发现 No results，无需重试
                    retry_count = max_retries 
                    break 
                
                if html_content is not None:
                    break # 成功获取 HTML
                
                print(f"[{tag}] [Page {page}] 加载失败，重试 ({retry_count + 1}/{max_retries})...")
                retry_count += 1
                time.sleep(5) 

            # --- 快速跳过和最终失败判断 ---
            if html_content is None or html_content == "": 
                print(f"[{tag}] [Page {page}] 停止分页，快速跳过当前标签。")
                break 

            # --- 解析数据 ---
            image_data = self._parse_page(html_content, tag)

            if not image_data:
                # 解析返回空列表（未提取到任何新数据 或 页面中无图片元素）
                print(f"[{tag}] [Page {page}] **解析结果为空，停止分页**。")
                break 
            
            # 写入 CSV
            for data in image_data:
                self.write_to_csv(data['title'], data['name'], data['url'], data['tag'])

            page += 1
            # 随机延迟，模拟人类行为，延迟范围 3 到 8 秒
            time.sleep(3 + random.uniform(2, 5)) 


    def run(self):
        """
        主执行方法：读取标签文件，并对每个标签启动爬取。
        """
        if not self.driver:
             print("❌ 爬虫无法启动，请解决 Selenium 驱动初始化错误。")
             return

        tag_list = []
        try:
            with open(TAG_FILE_PATH, 'r', encoding='utf-8') as f:
                tag_list = [line.strip() for line in f if line.strip()]
            print(f"✅ 成功读取 {len(tag_list)} 个标签。")
        except FileNotFoundError:
            print(f"❌ 标签文件未找到: {TAG_FILE_PATH}")
            return

        for tag in tag_list:
            self.start_crawl_for_tag(tag)
        
        if self.driver:
            self.driver.quit()
            print("\n🎉 所有标签爬取完成，浏览器已关闭。")

if __name__ == '__main__':
    crawler = PiqselsImageCrawler(
        csv_dir_path=CSV_DIR_PATH, 
        csv_filename=CSV_FILENAME,
        driver_path=CUSTOM_DRIVER_PATH # 传递本地驱动路径
    )
    crawler.run()