import requests
import urllib3
import json
import os
import csv
import time
import redis # 引入 redis 库
from concurrent.futures import ThreadPoolExecutor
from threading import Lock

# --- 配置常量 ---
TAG_FILE_PATH = r'D:\myproject\Code\爬虫\爬虫数据\morguefile\ram_tag_list_备份.txt'
CSV_DIR_PATH = r"D:\myproject\Code\爬虫\爬虫数据\morguefile"
API_URL_TEMPLATE = "https://api.morguefile.com/api/v1/search?page={page}&relevant=true&source=search&term={tag}"
MAX_WORKERS = 20
ALL_TAGS_CSV_FILENAME = "morguefile_all_data.csv" 

# --- Redis 配置常量 ---
REDIS_HOST = 'localhost'
REDIS_PORT = 6379
REDIS_KEY = 'morguefile_image_url_set' # 使用 URL 作为唯一标识符

class MorgueFileSpider:
    """
    MorgueFile 图片信息爬虫类
    """

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
            # 内存去重集合，注意：内存集合在多线程间共享，但只在当前程序生命周期内有效。
            # 由于线程池是在当前进程内运行，因此这个 set 是共享的。
            self.visited_urls = set()
        except Exception as e:
            print(f"⚠️ Redis 初始化遇到其他错误 ({e})，将使用内存去重。")
            self.redis = None
            self.visited_urls = set()
        # ----------------------


    def read_tags(self, file_path):
        """
        从文件中读取标签列表
        """
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                tags = [line.strip() for line in f if line.strip()]
            print(f"[!] 成功读取 {len(tags)} 个标签。")
            return tags
        except FileNotFoundError:
            print(f"[✗] 错误: 标签文件未找到: {file_path}")
            return []
        except Exception as e:
            print(f"[✗] 读取标签文件时发生错误: {e}")
            return []

    def get_api_data(self, tag, page):
        """
        发送 API 请求并获取 JSON 数据
        """
        url = API_URL_TEMPLATE.format(page=page, tag=tag)
        try:
            response = requests.get(url, headers=self.headers, timeout=10, verify=False) 
            response.raise_for_status()
            data = response.json()
            return data
        except requests.exceptions.RequestException as e:
            print(f"[{tag}] [Page {page}] [✗] 请求 API 失败: {e}")
            return None
        except json.JSONDecodeError:
            print(f"[{tag}] [Page {page}] [✗] API 返回数据无法解析为 JSON")
            return None
            
    # --- 新增去重检查方法 ---
    def is_duplicate(self, url):
        """
        检查 URL 是否已被访问过。如果是新的，则记录并返回 False；否则返回 True。
        :param url: 图片 URL (作为唯一键)
        :return: True 如果重复，False 如果不重复
        """
        # 使用 URL 的一部分作为唯一键，忽略可能的查询参数
        unique_key = url.split('?')[0] 
        
        if self.redis:
            # 使用 Redis 的 sadd 方法：如果元素已存在，返回 0；如果添加成功（新元素），返回 1
            # 这里的 check 包含添加操作，所以是原子性的。
            return self.redis.sadd(REDIS_KEY, unique_key) == 0
        else:
            # 使用内存集合进行去重，需要线程锁来保证操作的原子性
            with self.csv_lock: # 使用写入锁也可以（或者创建一个单独的去重锁）
                if unique_key in self.visited_urls:
                    return True
                self.visited_urls.add(unique_key)
                return False
        
    def parse_and_write(self, data, tag):
        """
        解析 JSON 数据，检查去重，并写入 CSV
        """
        items = data.get('data', [])
        if not items:
            return 0 

        csv_path = self.csv_path 
        written_count = 0
        duplicate_count = 0
        
        for item in items:
            title = item.get('title', 'N/A')
            url_large = item.get('url_large', 'N/A')
            
            # --- 核心去重逻辑 ---
            if self.is_duplicate(url_large):
                duplicate_count += 1
                continue # 跳过重复项
            # --------------------
            
            name = os.path.basename(url_large.split('?')[0]) if url_large != 'N/A' else 'N/A'
            
            self.write_to_csv(title, name, url_large, csv_path, tag)
            written_count += 1
        
        print(f"[{tag}] [Page {data.get('current_page', '?')}] [✓] 提取 {len(items)} 条，重复 {duplicate_count} 条，写入 {written_count} 条。")
        return len(items)

    def write_to_csv(self, title, name, url, csv_path, tag):
        """
        写入 CSV 方法，已集成线程锁，确保多线程安全。
        """
        try:
            with self.csv_lock: # 使用线程锁
                os.makedirs(os.path.dirname(csv_path), exist_ok=True)
                is_file_empty = not os.path.exists(csv_path) or os.stat(csv_path).st_size == 0
                
                with open(csv_path, 'a', newline='', encoding='utf-8-sig') as f:
                    writer = csv.writer(f)
                    
                    if is_file_empty:
                        writer.writerow(['Title', 'ImageName', 'URL', 'TAG'])
                        
                    writer.writerow([title, name, url, tag])
        except Exception as e:
            print(f"[{tag}] [✗] 写入 CSV 出错: {e}")

    def crawl_tag(self, tag):
        """
        针对单个标签进行爬取，遍历所有页码
        """
        print(f"[{tag}] 开始爬取...")
        page = 1
        
        while True:
            data = self.get_api_data(tag, page)
            if not data:
                print(f"[{tag}] [Page {page}] 停止爬取（API 请求失败或解析错误）。")
                break
            
            num_items = self.parse_and_write(data, tag)
            
            if num_items == 0 and page > 1:
                # 确保第一页为空时也能退出，但主要判断逻辑在 parse_and_write
                print(f"[{tag}] [Page {page}] 没有更多数据，爬取结束。")
                break
            
            # 如果爬取到数据，则继续下一页
            if len(data.get('data', [])) == 0 and page > 1:
                print(f"[{tag}] [Page {page}] 收到空列表，爬取结束。")
                break

            page += 1
        
        print(f"[{tag}] 爬取完成。")


    def run(self):
        """
        主执行方法，使用多线程并发爬取所有标签
        """
        tags = self.read_tags(TAG_FILE_PATH)
        if not tags:
            print("[!] 没有标签需要处理，程序退出。")
            return

        print(f"[!] 启动 {MAX_WORKERS} 个线程...")
        start_time = time.time()

        with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
            executor.map(self.crawl_tag, tags)

        end_time = time.time()
        print(f"\n[!!!] 所有标签爬取完成。数据写入至: {self.csv_path}")
        print(f"[!!!] 总耗时: {end_time - start_time:.2f} 秒")


if __name__ == '__main__':
    # 实例化时使用默认的 Redis 配置
    spider = MorgueFileSpider(
        csv_dir_path=CSV_DIR_PATH, 
        csv_filename=ALL_TAGS_CSV_FILENAME,
        redis_host=REDIS_HOST, # 可以修改为你的 Redis 地址
        redis_port=REDIS_PORT  # 可以修改为你的 Redis 端口
    )
    spider.run()