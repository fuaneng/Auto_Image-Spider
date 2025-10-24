import os
import csv
import re
import time
import requests
import urllib3
import redis
from bs4 import BeautifulSoup
from concurrent.futures import ThreadPoolExecutor, as_completed
from threading import Lock

# ----------------- 配置常量 -----------------
# 网站基础信息
BASE_URL = "https://freephotos.cc"
SEARCH_URL_TEMPLATE = f"{BASE_URL}/search/{{tag}}"
DOWNLOAD_URL_PREFIX = f"{BASE_URL}/api/download/"

# 文件路径和名称
TAG_FILE_PATH = r'D:\myproject\Code\爬虫\爬虫数据\libreshot\ram_tag_list_备份.txt'
CSV_DIR = r'D:\myproject\Code\爬虫\爬虫数据\libreshot\csv_output'
CSV_FILENAME = 'image_data.csv'
CHECKPOINT_FILE = 'completed_tags.txt'

# Redis 配置
REDIS_HOST = 'localhost'
REDIS_PORT = 6379
REDIS_KEY = 'freephotos_image_url_set' # 使用 ImageName (URL Path) 作为唯一标识符

# 线程配置
TAG_PROCESS_THREADS = 10 # 标签处理线程数
# DOWNLOAD_THREADS = 20    # 图片下载线程数（我们将使用线程池实现）

class ImageScraper:
    """
    高效、多线程图片信息爬虫类。
    负责标签处理、网页请求、数据解析、去重和 CSV 写入。
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
        # 忽略 SSL 警告
        urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
        
        # 已完成标签集合（用于断点续爬）
        self.completed_tags = self._load_completed_tags()
        self.tag_lock = Lock() # 用于更新 completed_tags 和断点文件的线程锁

        # --- 去重初始化逻辑 ---
        self.redis = None
        self.visited_names = set() # 内存去重集合
        try:
            # 尝试连接 Redis
            self.redis = redis.StrictRedis(host=redis_host, port=redis_port, decode_responses=True)
            self.redis.ping()
            print("✅ Redis 连接成功，使用 Redis 集合进行去重。")
        except redis.exceptions.ConnectionError as e:
            print(f"⚠️ Redis 连接失败 ({e})，将使用内存去重。")
        except Exception as e:
            print(f"⚠️ Redis 初始化遇到其他错误 ({e})，将使用内存去重。")
        
    def _load_completed_tags(self):
        """加载已完成的标签，用于断点续爬。"""
        if os.path.exists(CHECKPOINT_FILE):
            with open(CHECKPOINT_FILE, 'r', encoding='utf-8') as f:
                return set(line.strip() for line in f if line.strip())
        return set()

    def _mark_tag_completed(self, tag):
        """将标签标记为已完成，并保存到断点文件。"""
        with self.tag_lock:
            if tag not in self.completed_tags:
                self.completed_tags.add(tag)
                with open(CHECKPOINT_FILE, 'a', encoding='utf-8') as f:
                    f.write(f"{tag}\n")

    def is_name_visited(self, image_name):
        """
        检查图片名称（ImageName，即下载路径中的唯一标识符）是否已被访问。
        使用 Redis 或内存集合进行去重。
        """
        if self.redis:
            # 使用 Redis 的 sadd 方法，如果元素已存在，返回 0；否则，返回 1
            # 我们将 ImageName 作为唯一标识
            is_new = self.redis.sadd(REDIS_KEY, image_name)
            return is_new == 0
        else:
            # 内存去重
            with self.tag_lock: # 使用锁确保内存集合的多线程安全
                if image_name in self.visited_names:
                    return True
                self.visited_names.add(image_name)
                return False

    def write_to_csv(self, title, name, url, tag):
        """
        写入 CSV 方法，已集成线程锁，确保多线程安全。
        """
        # 使用 self.csv_path 和 self.csv_lock 替换伪代码中的参数
        try:
            with self.csv_lock: # 使用线程锁
                os.makedirs(os.path.dirname(self.csv_path), exist_ok=True)
                # 检查文件是否存在或是否为空
                is_file_empty = not os.path.exists(self.csv_path) or os.stat(self.csv_path).st_size == 0
                
                with open(self.csv_path, 'a', newline='', encoding='utf-8-sig') as f:
                    writer = csv.writer(f)
                    
                    if is_file_empty:
                        writer.writerow(['Title', 'ImageName', 'URL', 'TAG'])
                        
                    writer.writerow([title, name, url, tag])
        except Exception as e:
            print(f"[{tag}] [✗] 写入 CSV 出错: {e}")

    def _parse_and_save(self, html_content, tag):
        """
        解析 HTML 内容，提取所需数据，并进行去重和保存。
        """
        if not html_content:
            return

        soup = BeautifulSoup(html_content, 'html.parser')
        
        # 查找包含图片的父 div
        image_containers = soup.select('div.columns-1 div.h-min.w-full a')

        count = 0
        for a_tag in image_containers:
            try:
                # 1. 提取 'a' 元素的 'href'
                href = a_tag.get('href') # 示例: /photo/a-hot-dog-with-chips-and-condiments-on-a-plate-1a

                if not href or not href.startswith('/photo/'):
                    continue

                # 2. 提取图片名称 (ImageName)
                image_name = href.replace('/photo/', '').strip() # 示例: a-hot-dog-with-chips-and-condiments-on-a-plate-1a
                
                # 3. 进行去重检查
                if self.is_name_visited(image_name):
                    print(f"[{tag}] [SKIP] 已爬取: {image_name}")
                    continue

                # 4. 拼接最终的直链下载地址 (URL)
                download_url = DOWNLOAD_URL_PREFIX + image_name

                # 5. 提取图片标题 (Title)
                img_tag = a_tag.find('img')
                title = img_tag.get('alt') if img_tag and img_tag.get('alt') else "N/A"

                # 6. 写入 CSV
                self.write_to_csv(title, image_name, download_url, tag)
                count += 1
                
            except Exception as e:
                print(f"[{tag}] [✗] 解析或保存单个图片数据出错: {e}")

        print(f"[{tag}] [✓] 完成解析和保存，新增 {count} 条记录。")

    def fetch_tag_page(self, tag):
        """
        多线程工作函数：请求单个标签的页面并处理数据。
        """
        if tag in self.completed_tags:
            print(f"[{tag}] [SKIP] 标签已在断点记录中，跳过。")
            return

        url = SEARCH_URL_TEMPLATE.format(tag=tag)
        print(f"[{tag}] [i] 正在请求 URL: {url}")
        
        try:
            # 网站可能有多页，但伪代码只给出了单页信息，我们暂时只爬取第一页
            response = requests.get(url, headers=self.headers, verify=False, timeout=60)    # 60 秒超时
            response.raise_for_status() # 检查 HTTP 状态码
            
            self._parse_and_save(response.text, tag)
            self._mark_tag_completed(tag) # 标记标签处理完成

        except requests.exceptions.RequestException as e:
            print(f"[{tag}] [✗] 请求失败: {e}")
        except Exception as e:
            print(f"[{tag}] [✗] 发生未知错误: {e}")

    def load_tags(self):
        """从本地文件加载待处理的标签列表。"""
        try:
            with open(TAG_FILE_PATH, 'r', encoding='utf-8') as f:
                # 去除空行和首尾空格
                tags = [line.strip() for line in f if line.strip()]
                print(f"✅ 成功加载 {len(tags)} 个标签。")
                return tags
        except FileNotFoundError:
            print(f"❌ 标签文件未找到: {TAG_FILE_PATH}")
            return []
        except Exception as e:
            print(f"❌ 加载标签文件出错: {e}")
            return []

    def run_scraper(self):
        """
        启动多线程爬虫主流程。
        """
        tags = self.load_tags()
        if not tags:
            return

        # 使用 ThreadPoolExecutor 实现多线程爬取标签
        print(f"\n🚀 启动标签处理，线程数: {TAG_PROCESS_THREADS}")
        start_time = time.time()
        
        # 筛选出未完成的标签
        tags_to_process = [tag for tag in tags if tag not in self.completed_tags]
        print(f"✨ 待处理标签: {len(tags_to_process)} 个 (已跳过 {len(tags) - len(tags_to_process)} 个已完成标签)。")

        with ThreadPoolExecutor(max_workers=TAG_PROCESS_THREADS) as executor:
            # 提交任务
            future_to_tag = {executor.submit(self.fetch_tag_page, tag): tag for tag in tags_to_process}
            
            # 实时获取任务结果
            for future in as_completed(future_to_tag):
                tag = future_to_tag[future]
                try:
                    # 结果已被 fetch_tag_page 函数内部处理
                    future.result() 
                except Exception as exc:
                    print(f'[{tag}] [✗] 生成了一个异常: {exc}')

        end_time = time.time()
        print(f"\n🎉 所有标签处理完毕! 总耗时: {end_time - start_time:.2f} 秒。")
        
        # --- 异步/多线程下载部分（可扩展）---
        # 这里可以加入启动异步下载器的逻辑，例如：
        # self.start_download_manager()

# ----------------- 示例运行 -----------------
if __name__ == '__main__':
    
    # 确保 CSV 目录存在
    os.makedirs(CSV_DIR, exist_ok=True)
    
    # 实例化爬虫并运行
    scraper = ImageScraper(
        csv_dir_path=CSV_DIR, 
        csv_filename=CSV_FILENAME
    )
    
    scraper.run_scraper()