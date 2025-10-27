import requests
from bs4 import BeautifulSoup
import os
import csv
import re
from threading import Lock
from concurrent.futures import ThreadPoolExecutor
import urllib3
import time # 引入时间库
import random # 引入随机库

# --- Redis 配置 ---
REDIS_HOST = 'localhost'
REDIS_PORT = 6379
REDIS_KEY = 'isorepublic_image_url_set' 

# --- 文件路径配置（请根据你的实际路径修改） ---
TAG_FILE_PATH = r"R:\py\Auto_Image-Spider\Spider_Data\ram_tag_list.txt"
CSV_DIR_PATH = r"R:\py\Auto_Image-Spider\Requests\Isorepublic"
CSV_FILENAME = "isorepublic_data.csv"
MAX_TAG_WORKERS = 8 # 多线程标签处理数量，线程过高容易返回403 

# --- 爬虫增强配置 ---
MIN_DELAY = 1.0 # 最小等待秒数
MAX_DELAY = 3.0 # 最大等待秒数
REQUEST_TIMEOUT = 15 # 将超时时间增加到 15 秒

try:
    import redis
except ImportError:
    print("请安装 redis 库: pip install redis")
    redis = None

class IsorepublicCrawler:
    """
    Isorepublic 图片爬虫类，支持真人模拟、Redis/内存去重和多线程标签处理。
    """

    def __init__(self, csv_dir_path, csv_filename, redis_host=REDIS_HOST, redis_port=REDIS_PORT):
        """
        初始化爬虫实例，集成 Redis/内存去重逻辑，并设置更逼真的请求头。
        """
        self.csv_dir_path = csv_dir_path
        self.csv_path = os.path.join(self.csv_dir_path, csv_filename) 
        self.csv_lock = Lock() 
        # 【更新】增加更全面的请求头
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36', # 升级 User-Agent
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7',
            'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8', # 模拟接受语言
            'Cache-Control': 'max-age=0',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
            # 注意: Referer 最好在每次请求时根据上一个 URL 动态设置，但为简洁和通用性，这里先不设置或设置为根域名
            'Referer': 'https://isorepublic.com/' 
        }
        
        urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

        # --- 去重初始化逻辑（保持不变） ---
        if redis:
            try:
                self.redis = redis.StrictRedis(host=redis_host, port=redis_port, decode_responses=True)
                self.redis.ping()
                print("✅ Redis 连接成功，使用 Redis 集合进行去重。")
            except (redis.exceptions.ConnectionError, Exception) as e:
                print(f"⚠️ Redis 连接或初始化失败 ({e})，将使用内存去重。")
                self.redis = None
                self.visited_urls = set()
        else:
            self.redis = None
            self.visited_urls = set()
            print("⚠️ Redis 库未安装，将使用内存去重。")

    def is_url_visited(self, url):
        # 保持不变
        if self.redis:
            return self.redis.sadd(REDIS_KEY, url) == 0
        else:
            if url in self.visited_urls:
                return True
            self.visited_urls.add(url)
            return False

    def write_to_csv(self, title, name, url, csv_path, tag):
        # 保持不变
        try:
            with self.csv_lock:
                os.makedirs(os.path.dirname(csv_path), exist_ok=True)
                is_file_empty = not os.path.exists(csv_path) or os.stat(csv_path).st_size == 0
                
                with open(csv_path, 'a', newline='', encoding='utf-8-sig') as f:
                    writer = csv.writer(f)
                    
                    if is_file_empty:
                        writer.writerow(['Title', 'ImageName', 'URL', 'TAG'])
                        
                    writer.writerow([title, name, url, tag])
        except Exception as e:
            print(f"[{tag}] [✗] 写入 CSV 出错: {e}")

    def parse_item(self, item, tag):
        # 保持不变
        try:
            noscript_img = item.select_one('noscript img')
            if not noscript_img:
                return
            
            original_url_with_res = noscript_img.get('src')
            title = noscript_img.get('alt', '').strip()
            
            if not original_url_with_res or not title:
                return

            base_url, ext = os.path.splitext(original_url_with_res)
            clean_base_url = re.sub(r'-\d+x\d+$', '', base_url)
            final_url = clean_base_url + ext
            
            image_name_full = os.path.basename(final_url)
            image_name = os.path.splitext(image_name_full)[0]

            if self.is_url_visited(final_url):
                return

            self.write_to_csv(title, image_name, final_url, self.csv_path, tag)
            print(f"[{tag}] [✔] 成功提取并保存: {title}")

        except Exception as e:
            print(f"[{tag}] [✗] 解析单个 item 时出错: {e}")

    def crawl_tag_pages(self, tag):
        """
        【更新】增加随机延迟和增加请求超时时间的单线程串行爬取。
        """
        base_url = "https://isorepublic.com/"
        page_template = f"{base_url}page/{{}}/?s={tag}&post_type=photo_post"
        page = 1 

        print(f"[{tag}] 开始爬取标签...")

        while True:
            # 【更新】在每次请求前，应用随机延迟
            if page > 1:
                delay = random.uniform(MIN_DELAY, MAX_DELAY)
                print(f"[{tag}] 礼貌性等待 {delay:.2f} 秒...")
                time.sleep(delay)
                
            current_url = page_template.format(page)
            print(f"[{tag}] 正在请求页面: {page} ({current_url})")

            try:
                # 【更新】使用更长的超时时间
                response = requests.get(
                    current_url, 
                    headers=self.headers, 
                    verify=False, 
                    timeout=REQUEST_TIMEOUT # 使用新的超时时间
                )
                
                if response.status_code == 404:
                    print(f"[{tag}] [ℹ] 收到 404 响应，认为已到最后一页。爬取结束。")
                    break 
                
                response.raise_for_status() 

                soup = BeautifulSoup(response.text, 'html.parser')
                
                photo_grid = soup.find(id='photo-grid')
                if not photo_grid:
                    print(f"[{tag}] [ℹ] 页面结构异常或没有图片内容，爬取结束。")
                    break

                items = photo_grid.select('a.photo-grid-item')
                
                if not items:
                    print(f"[{tag}] [ℹ] 第 {page} 页没有找到图片项，爬取结束。")
                    break 

                for item in items:
                    self.parse_item(item, tag)

                page += 1
                
            except requests.exceptions.HTTPError as e:
                if e.response.status_code != 404:
                    print(f"[{tag}] [✗] 请求页面 {page} 时发生 HTTP 错误: {e}")
                    break
            except requests.exceptions.Timeout as e:
                # 捕获超时错误
                print(f"[{tag}] [✗] 请求页面 {page} 时发生超时错误 (Timeout): {e}，尝试跳过或重试。")
                # 遇到超时错误时，可以选择 break 停止当前 tag，也可以选择 continue 尝试下一页。
                # 鉴于你希望串行爬取，遇到连续超时可能意味着该 tag 无法继续，因此选择 break。
                break
            except requests.exceptions.RequestException as e:
                print(f"[{tag}] [✗] 请求页面 {page} 时发生网络错误: {e}")
                break
            except Exception as e:
                print(f"[{tag}] [✗] 爬取页面 {page} 时发生未知错误: {e}")
                break
        
        print(f"[{tag}] 标签爬取任务完成。")


    # read_tags_from_file 和 start_crawl 保持不变
    def read_tags_from_file(self, file_path):
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                tags = [line.strip() for line in f if line.strip()]
            return tags
        except FileNotFoundError:
            print(f"❌ 错误: 标签文件未找到: {file_path}")
            return []
        except Exception as e:
            print(f"❌ 错误: 读取标签文件时发生错误: {e}")
            return []

    def start_crawl(self, tag_file_path):
        tags = self.read_tags_from_file(tag_file_path)
        if not tags:
            print("没有标签需要爬取，程序退出。")
            return

        print(f"总共找到 {len(tags)} 个标签，使用 {MAX_TAG_WORKERS} 个线程处理。")

        with ThreadPoolExecutor(max_workers=MAX_TAG_WORKERS) as executor:
            executor.map(self.crawl_tag_pages, tags)
            
        print("所有标签爬取任务完成。")

if __name__ == '__main__':
    # 实例化爬虫
    crawler = IsorepublicCrawler(
        csv_dir_path=CSV_DIR_PATH, 
        csv_filename=CSV_FILENAME
    )
    
    # 启动爬虫
    crawler.start_crawl(TAG_FILE_PATH)