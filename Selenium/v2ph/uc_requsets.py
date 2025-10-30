import os
import csv
import time
import requests
import redis
import urllib3
from threading import Lock
from urllib.parse import urljoin
from concurrent.futures import ThreadPoolExecutor, as_completed
from bs4 import BeautifulSoup
import undetected_chromedriver as uc
from selenium.common.exceptions import WebDriverException

# --- 全局配置常量 ---
BASE_URL = "https://www.v2ph.com"

# !!! 浏览器驱动路径配置 !!!
# 请根据您的实际路径修改！如果 uc 自动管理成功，此路径可忽略
CHROME_DRIVER_PATH = r"C:\Program Files\Google\chromedriver-win64\chromedriver.exe"

# 文件路径配置
# !!! 请根据您的实际路径修改 !!!
TAG_FILE_PATH = r"R:\py\Auto_Image-Spider\Selenium\v2ph\tag.txt"
CSV_DIR_PATH = r"R:\py\Auto_Image-Spider\Selenium\v2ph"
CSV_FILENAME = "v2ph_data_251029.csv"

# Redis 配置
REDIS_HOST = 'localhost'
REDIS_PORT = 6379
REDIS_KEY = 'v2ph_image_url_set' 

# 线程池配置 (强制串行以避免 Selenium driver 冲突)
MAX_TAG_WORKERS = 1         # 标签处理线程池 (必须为 1)
MAX_ALBUM_WORKERS = 1       # 相册处理线程池 (必须为 1)
MAX_IMAGE_WORKERS = 10      # 图片下载/保存线程池 (高并发，不涉及 driver)

# --- 新增相册限制配置 ---
MAX_ALBUMS_PER_RUN = 15     # <-- 限制每次运行爬取的相册数量

class V2phSpider:
    def __init__(self, driver, cookies_dict, headers, csv_dir_path, csv_filename, redis_host=REDIS_HOST, redis_port=REDIS_PORT):
        """
        初始化爬虫实例，集成 Redis/内存去重逻辑、线程锁和相册计数器。
        """
        self.driver = driver
        self.cookies = cookies_dict
        self.headers = headers
        
        # 路径和锁初始化
        self.csv_dir_path = csv_dir_path
        self.csv_path = os.path.join(self.csv_dir_path, csv_filename)
        self.csv_lock = Lock()
        
        # --- 相册计数器和限制 ---
        self.album_count = 0  
        self.album_limit = MAX_ALBUMS_PER_RUN 
        self.count_lock = Lock() # 用于保护计数器的线程锁
        
        urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
        
        # --- 去重初始化逻辑 ---
        self.redis = None
        self.visited_urls = set()
        try:
            self.redis = redis.StrictRedis(host=redis_host, port=redis_port, decode_responses=True)
            self.redis.ping()
            print("✅ Redis 连接成功，使用 Redis 集合进行去重。")
        except (redis.exceptions.ConnectionError, Exception) as e:
            print(f"⚠️ Redis 连接失败 ({e})，将使用内存去重。")
            self.redis = None

    def is_visited(self, url):
        """检查 URL 是否已被访问。"""
        if self.redis:
            return self.redis.sismember(REDIS_KEY, url)
        else:
            return url in self.visited_urls

    def add_visited(self, url):
        """将 URL 添加到已访问集合。"""
        if self.redis:
            self.redis.sadd(REDIS_KEY, url)
        else:
            self.visited_urls.add(url)

    def write_to_csv(self, title, name, url, tag):
        """
        写入 CSV 方法，已集成线程锁，确保线程安全。
        数据列：['Title', 'ImageName', 'URL', 'TAG']
        """
        try:
            # 1. 写入 CSV
            with self.csv_lock:
                os.makedirs(os.path.dirname(self.csv_path), exist_ok=True)
                is_file_empty = not os.path.exists(self.csv_path) or os.stat(self.csv_path).st_size == 0
                
                with open(self.csv_path, 'a', newline='', encoding='utf-8-sig') as f:
                    writer = csv.writer(f)
                    
                    if is_file_empty:
                        writer.writerow(['Title', 'ImageName', 'URL', 'TAG'])
                        
                    writer.writerow([title, name, url, tag])
                    
            # 2. 写入去重集合
            self.add_visited(url) 

        except Exception as e:
            print(f"[{tag}] [✗] 写入 CSV 或更新去重集合出错: {e}")


    def _fetch_page(self, url, tag, album_title=None):
        """
        封装的页面请求方法：优先 requests，失败则回退到 driver (串行安全)。
        """
        context_name = album_title if album_title else tag
        
        # 1. 尝试使用 requests
        try:
            response = requests.get(url, headers=self.headers, cookies=self.cookies, verify=False, timeout=15)
            
            if response.status_code == 404:
                return None
            
            response.raise_for_status() 
            return response.text
        
        except (requests.exceptions.RequestException, requests.exceptions.HTTPError) as e:
            # 2. 如果 requests 失败 (如 403)，回退到 driver 模式
            print(f"[{context_name}] [!] Requests 失败 ({type(e).__name__})，回退到 Driver 获取页面内容...")
            
            try:
                self.driver.get(url)
                time.sleep(3) 
                
                if "/login" in self.driver.current_url.lower():
                    print(f"[{context_name}] [✗] Cookies 已失效，Driver 跳转至登录页。爬虫终止。")
                    return None
                
                return self.driver.page_source
            
            except Exception as driver_e:
                print(f"[{context_name}] [✗] Driver 请求出错: {driver_e}")
                return None


    def parse_and_save_images(self, album_url, tag, album_title, album_page):
        """进入相册详情页，解析图片 URL，去重并保存到 CSV。"""
        url = f"{album_url}?page={album_page}" if album_page > 1 else album_url
        html_content = self._fetch_page(url, tag, album_title)

        if not html_content:
            return False 
            
        soup = BeautifulSoup(html_content, 'html.parser')
        image_containers = soup.select('div.photos-list .album-photo.my-2 img')
        
        if not image_containers:
            if album_page > 1:
                print(f"[{tag}/{album_title}] [✓] 第 {album_page} 页未找到图片，相册解析完成。")
            return False
            
        print(f"[{tag}/{album_title}] [✓] 正在解析第 {album_page} 页，找到 {len(image_containers)} 张图片...")

        for img in image_containers:
            data_src = img.get('data-src')
            image_name = img.get('alt') or (os.path.basename(data_src) if data_src else "Unknown")
            
            if data_src:
                image_url = urljoin(BASE_URL, data_src) 
                
                if not self.is_visited(image_url):
                    self.write_to_csv(album_title, image_name, image_url, tag)

        return True


    def crawl_album(self, album_path, tag, album_title, image_executor):
        """处理单个相册的翻页和图片解析。"""
        album_url = urljoin(BASE_URL, album_path)
        page = 1
        
        while True:
            future = image_executor.submit(
                self.parse_and_save_images, 
                album_url, 
                tag, 
                album_title, 
                page
            )

            try:
                if not future.result():
                    break 
            except Exception as e:
                 print(f"[{tag}/{album_title}] [✗] 图片解析线程出错: {e}")
                 break
            
            page += 1
            time.sleep(0.5) 
            
        print(f"[{tag}] [✓] 相册 {album_title} 处理完成。")


    def crawl_tag(self, tag, album_executor, image_executor):
        """
        处理单个标签页的翻页和相册链接提取，并检查全局相册限制。
        """
        print(f"\n--- [标签: {tag}] 开始爬取 ---")
        tag_page = 1
        
        while True:
            # 1. 检查全局相册限制 (外层循环)
            with self.count_lock:
                if self.album_count >= self.album_limit:
                    print(f"[{tag}] [!] 已达到全局相册限制 ({self.album_limit} 个)，停止提交新任务。")
                    break
                    
            url = f"{BASE_URL}/actor/{tag}?page={tag_page}"
            html_content = self._fetch_page(url, tag)
            
            if not html_content:
                break
                
            soup = BeautifulSoup(html_content, 'html.parser')
            album_cards = soup.select('div.col-12.col-sm-6.col-md-4.col-lg-3.my-1')
            
            if not album_cards:
                print(f"[{tag}] [✓] 第 {tag_page} 页未找到相册卡片，停止翻页。")
                break

            print(f"[{tag}] [✓] 正在解析第 {tag_page} 页，找到 {len(album_cards)} 个相册...")
            
            # 2. 遍历相册卡片并提交任务
            for card in album_cards:
                with self.count_lock:
                    if self.album_count >= self.album_limit:
                        print(f"[{tag}] [!] 达到全局相册限制 ({self.album_limit} 个)，停止提交。")
                        break # 跳出内层 for 循环
                    
                    link_tag = card.select_one('.card-body h6 a') 
                    if link_tag:
                        album_path = link_tag.get('href') 
                        album_title = link_tag.get_text().strip() 
                        
                        if album_path:
                            # 提交任务
                            album_executor.submit(
                                self.crawl_album, 
                                album_path, 
                                tag, 
                                album_title, 
                                image_executor
                            )
                            # 递增计数器
                            self.album_count += 1
                            print(f"[{tag}] 提交相册: {album_title[:20]}... ({self.album_count}/{self.album_limit})")

                # 如果内层循环中断，外层循环也需要中断
                with self.count_lock:
                    if self.album_count >= self.album_limit:
                        break # 跳出外层 while 循环
            
            tag_page += 1
            time.sleep(1) 

        print(f"--- [标签: {tag}] 所有相册链接已提交或达到限制，等待相册处理完成 ---")


# --- undetected-chromedriver 手动登录辅助函数 ---
def get_cookies_and_headers_manually(target_url=BASE_URL, driver_path=None):
    """
    启动 uc 实例，等待用户手动完成验证和登录，返回活着的 driver 实例。
    """
    print("\n--- 启动 undetected-chromedriver 实例，请手动登录 ---")
    driver = None
    try:
        if driver_path and os.path.exists(driver_path):
             print(f"尝试使用指定的 ChromeDriver 路径: {driver_path}")
             driver = uc.Chrome(
                 headless=False, 
                 use_subprocess=True,
                 driver_executable_path=driver_path 
             )
        else:
             print("使用 undetected-chromedriver 自动管理驱动器。")
             driver = uc.Chrome(
                 headless=False, 
                 use_subprocess=True
             )
             
        driver.get(target_url)
        
        print("\n=====================================================================")
        print("请在打开的 Chrome 浏览器中：手动完成 Cloudflare 验证和网站登录。")
        print("登录成功后，请在 **当前控制台窗口** 按 **回车键 (Enter)** 继续...")
        print("=====================================================================")
        
        input() 
        
        cookies_list = driver.get_cookies()
        cookies_dict = {cookie['name']: cookie['value'] for cookie in cookies_list}
        user_agent = driver.execute_script("return navigator.userAgent")
        headers = {'User-Agent': user_agent, 'Referer': BASE_URL + '/'}

        print("✅ 成功获取会话信息！浏览器实例将保持运行，请勿手动关闭。")
        return driver, cookies_dict, headers

    except WebDriverException as e:
        print(f"!!! 错误：WebDriver 启动或运行出错。请检查你的 Chrome/UC 环境: {e}")
        return None, None, None
    except Exception as e:
        print(f"!!! 错误：获取会话信息时遇到其他错误: {e}")
        return None, None, None
    
# --- 主执行函数 ---
def main():
    
    # 1. 手动登录并获取 driver, Cookies 和 Headers
    driver, cookies_dict, headers = get_cookies_and_headers_manually(BASE_URL, CHROME_DRIVER_PATH)
    
    if not driver:
        print("!!! 严重错误：无法获取有效的浏览器实例，爬虫停止。")
        return
        
    # 2. 读取 TAG 列表
    try:
        with open(TAG_FILE_PATH, 'r', encoding='utf-8') as f:
            tags = [line.strip() for line in f if line.strip()]
        if not tags:
            print("!!! 警告：tag.txt 文件中未找到任何标签。")
            driver.quit()
            return
    except FileNotFoundError:
        print(f"!!! 错误：标签文件未找到: {TAG_FILE_PATH}")
        driver.quit()
        return

    # 3. 初始化爬虫实例
    spider = V2phSpider(driver, cookies_dict, headers, CSV_DIR_PATH, CSV_FILENAME)

    # 4. 启动三级线程池
    print(f"\n--- 启动异步多线程爬虫 ---")
    print(f"目标相册限制: {MAX_ALBUMS_PER_RUN} 个。")
    print(f"配置: 标签线程 {MAX_TAG_WORKERS} (串行), 相册线程 {MAX_ALBUM_WORKERS} (串行), 图片线程 {MAX_IMAGE_WORKERS} (并发)")

    try:
        with ThreadPoolExecutor(max_workers=MAX_IMAGE_WORKERS) as image_executor:
            with ThreadPoolExecutor(max_workers=MAX_ALBUM_WORKERS) as album_executor:
                with ThreadPoolExecutor(max_workers=MAX_TAG_WORKERS) as tag_executor:
                    
                    # 只有在未达到限制时才提交标签任务
                    if spider.album_count < spider.album_limit:
                        tag_futures = {tag_executor.submit(spider.crawl_tag, tag, album_executor, image_executor): tag for tag in tags}
                    else:
                         tag_futures = {}
                         
                    for future in as_completed(tag_futures):
                        tag_name = tag_futures[future]
                        try:
                            future.result()
                        except Exception as exc:
                            print(f"--- [标签: {tag_name}] 运行时出错: {exc} ---")
                
                print("所有标签处理线程已关闭。等待相册处理线程完成...")

            print("所有相册处理线程已关闭。等待图片解析/保存线程完成...")
    
    finally:
        # 5. 最终清理
        print(f"\n✅ 所有爬取任务已完成！总共提交 {spider.album_count} 个相册任务 (目标限制 {MAX_ALBUMS_PER_RUN})。")
        print("数据已保存到:", spider.csv_path)
        print("正在关闭浏览器实例...")
        if driver:
            driver.quit()


if __name__ == "__main__":
    main()