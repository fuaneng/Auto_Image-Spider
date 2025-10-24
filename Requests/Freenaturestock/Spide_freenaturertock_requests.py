import requests
from bs4 import BeautifulSoup
import re
import os
import csv
from threading import Lock
import urllib3
import redis
from concurrent.futures import ThreadPoolExecutor
from urllib.parse import urlparse

# --- Redis 配置常量 ---
REDIS_HOST = 'localhost'
REDIS_PORT = 6379
REDIS_KEY = 'freenaturestock_image_url_set' # 使用 URL 作为唯一标识符

# --- 文件路径常量 ---
# {tag}文本路径
TAG_FILE_PATH = r'D:\myproject\Code\爬虫\爬虫数据\morguefile\ram_tag_list_备份.txt'
# 表格存储路径
CSV_DIR_PATH = r"D:\myproject\Code\爬虫\爬虫数据\freenaturestock"
CSV_FILENAME = "freenaturestock_images.csv"

# --- 爬虫核心类 ---
class FreenaturestockScraper:
    def __init__(self, csv_dir_path, csv_filename, redis_host=REDIS_HOST, redis_port=REDIS_PORT):
        """
        初始化爬虫实例，集成 Redis/内存去重逻辑。
        """
        self.csv_dir_path = csv_dir_path
        self.csv_path = os.path.join(self.csv_dir_path, csv_filename) 
        self.csv_lock = Lock() # 用于 CSV 写入的线程锁
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        # 禁用 InsecureRequestWarning
        urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

        # --- 去重初始化逻辑 ---
        try:
            # 尝试连接 Redis
            self.redis = redis.StrictRedis(host=redis_host, port=redis_port, decode_responses=True)
            # 尝试执行一次 ping 来验证连接
            self.redis.ping()
            print("✅ Redis 连接成功，使用 Redis 集合进行去重。")
        except redis.exceptions.ConnectionError as e:
            print(f"⚠️ Redis 连接失败 ({e})，将使用内存去重。")
            self.redis = None
            # 内存去重集合
            self.visited_urls = set()
        except Exception as e:
            print(f"⚠️ Redis 初始化遇到其他错误 ({e})，将使用内存去重。")
            self.redis = None
            self.visited_urls = set()
        # ----------------------

    def _is_url_processed(self, url):
        """
        检查 URL 是否已经被处理过 (去重逻辑)。
        """
        if self.redis:
            # 使用 Redis 的 sadd 方法，如果成功添加到集合 (返回 1)，则表示是新的 URL。
            return not self.redis.sadd(REDIS_KEY, url)
        else:
            # 使用内存去重集合
            with self.csv_lock: # 使用 lock 来保护共享的 set
                if url in self.visited_urls:
                    return True
                self.visited_urls.add(url)
                return False

    def write_to_csv(self, title, name, url, csv_path, tag):
        """
        将数据写入 CSV 文件。
        """
        try:
            # 确保目录存在
            os.makedirs(os.path.dirname(csv_path), exist_ok=True)
            
            with self.csv_lock: # 使用线程锁保护文件写入操作
                # 检查文件是否为空，以决定是否写入表头
                is_file_empty = not os.path.exists(csv_path) or os.stat(csv_path).st_size == 0
                
                with open(csv_path, 'a', newline='', encoding='utf-8-sig') as f:
                    writer = csv.writer(f)
                    if is_file_empty:
                        writer.writerow(['Title', 'ImageName', 'URL', 'TAG'])
                    writer.writerow([title, name, url, tag])
            print(f"[{tag}] [✔] 写入 CSV 成功: {url}") # 写入成功信息可选，避免过多输出
        except Exception as e:
            print(f"[{tag}] [✗] 写入 CSV 出错: {e}")

    def _clean_and_get_image_info(self, url):
        """
        清洗 URL，删除尺寸分辨率，并提取图片名称。
        
        清洗规则：匹配并删除形如 "-768x512" 的部分。
        """
        # 匹配 "-数字x数字" + "." + "图片扩展名"
        # 例如："-768x512.jpg", "-200x300.jpeg"
        # 替换为 "." + "图片扩展名"
        cleaned_url = re.sub(r'-\d+x\d+(\.\w+)$', r'\1', url, flags=re.IGNORECASE)

        # 尝试从 URL 提取图片文件名作为 Name
        parsed_url = urlparse(cleaned_url)
        path = parsed_url.path
        image_name = os.path.basename(path)
        
        # 进一步处理名称，去除扩展名（可选）
        name_without_ext = os.path.splitext(image_name)[0]
        
        return cleaned_url, name_without_ext


    def _extract_image_urls(self, html_content, tag):
        """
        从 HTML 内容中提取图片 URL，清洗并去重后写入 CSV。
        """
        soup = BeautifulSoup(html_content, 'html.parser')
        
        # 1. 提取所有 <img> 标签的 src 属性
        image_urls = {img.get('src') for img in soup.find_all('img') if img.get('src')}
        
        # 2. 提取所有可能的链接 (<a> 标签的 href 属性)，并筛选以图片扩展名结尾的 URL
        # 虽然 freenaturestock 的图片链接通常直接在 <img> src 中，但为了健壮性，可以检查所有链接
        # for a in soup.find_all('a'):
        #     href = a.get('href')
        #     if href and re.search(r'\.(jpg|jpeg|png|gif|webp)(\?.*)?$', href, re.IGNORECASE):
        #         image_urls.add(href)

        count_new = 0
        for raw_url in image_urls:
            # 过滤掉一些明显不是主图的链接（如 logo, css/js 图片等）
            if not raw_url.startswith(('http', 'https')):
                 continue # 过滤相对路径，只处理绝对路径
            if 'logo' in raw_url.lower() or 'css' in raw_url.lower() or 'js' in raw_url.lower():
                continue

            cleaned_url, image_name = self._clean_and_get_image_info(raw_url)
            
            if not self._is_url_processed(cleaned_url):
                # 写入 CSV
                # Title 留空，使用清洗后的 URL 作为唯一的标识符
                self.write_to_csv("", image_name, cleaned_url, self.csv_path, tag)
                count_new += 1
        
        return count_new

    def crawl_tag_page(self, tag):
        """
        针对单个标签，从第一页开始爬取所有分页。
        """
        page = 1
        print(f"\n--- 开始爬取标签: [{tag}] ---")
        base_url = "https://freenaturestock.com/page/{page}/?s={tag}"
        
        while True:
            url = base_url.format(page=page, tag=tag)
            
            try:
                # 使用 verify=False 忽略 SSL 警告，如果你在本地遇到相关问题
                response = requests.get(url, headers=self.headers, timeout=15, verify=False)
                
                # 检查状态码
                if response.status_code == 404:
                    print(f"[{tag}] [✔] 页面 {page} 返回 404，认为分页结束。")
                    break
                
                response.raise_for_status() # 对 4xx/5xx 状态码抛出异常

                # 检查内容
                new_images_count = self._extract_image_urls(response.text, tag)
                
                if new_images_count == 0 and page > 1:
                    # 如果当前页没有提取到任何新的图片链接，可以认为到达尾页 (即使状态码不是 404)
                    print(f"[{tag}] [✔] 页面 {page} 未提取到新的图片链接，认为分页结束。")
                    break
                
                print(f"[{tag}] [第 {page} 页] 提取并处理了 {new_images_count} 个新的图片 URL。")
                page += 1
                
            except requests.exceptions.HTTPError as e:
                # 处理 4xx 或 5xx 错误
                if response.status_code == 404:
                     print(f"[{tag}] [✔] 页面 {page} 返回 404，认为分页结束。")
                     break
                print(f"[{tag}] [✗] 请求 {url} 遇到 HTTP 错误: {e}")
                break
            except requests.exceptions.RequestException as e:
                # 处理连接错误、超时等
                print(f"[{tag}] [✗] 请求 {url} 遇到连接错误: {e}")
                break
            except Exception as e:
                print(f"[{tag}] [✗] 处理 {url} 遇到未知错误: {e}")
                break

    def load_tags(self):
        """
        从文件中加载搜索标签列表。
        """
        try:
            with open(TAG_FILE_PATH, 'r', encoding='utf-8') as f:
                # 过滤空行并去除两端空格
                tags = [line.strip() for line in f if line.strip()]
            print(f"总共加载了 {len(tags)} 个标签。")
            return tags
        except FileNotFoundError:
            print(f"错误: 标签文件未找到，请检查路径: {TAG_FILE_PATH}")
            return []
        except Exception as e:
            print(f"错误: 加载标签文件时发生错误: {e}")
            return []

    def start_crawl(self, max_workers=20):
        """
        启动多线程爬取。
        """
        tags = self.load_tags()
        if not tags:
            print("没有可用的标签，爬虫结束。")
            return

        print(f"启动 {max_workers} 线程池进行爬取...")
        
        # 使用 ThreadPoolExecutor 管理并发线程
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            # 提交任务给线程池
            # executor.map 会等待所有任务完成
            # 注意：如果某个 tag 的任务抛出异常，map 会重新抛出该异常。
            executor.map(self.crawl_tag_page, tags)

        print("\n所有标签爬取任务完成！")


# --- 执行代码 ---
if __name__ == '__main__':
    # 实例化爬虫
    scraper = FreenaturestockScraper(CSV_DIR_PATH, CSV_FILENAME)
    
    # 启动爬虫，使用 20 线程
    scraper.start_crawl(max_workers=20)