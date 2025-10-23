import os
import re
import csv
import time
import requests
import urllib3
import redis
from lxml import etree
from threading import Lock
from concurrent.futures import ThreadPoolExecutor

# --- 配置常量 ---
BASE_URL = "https://libreshot.com/?s={tag}"
TAG_FILE_PATH = r"D:\myproject\Code\爬虫\爬虫数据\libreshot\ram_tag_list_备份.txt"
CSV_DIR_PATH = r"D:\myproject\Code\爬虫\爬虫数据\libreshot\results"  # 更改为你想要的CSV输出目录
CSV_FILENAME = "libreshot_images.csv"
MAX_WORKERS = 10  # 线程池大小
REDIS_HOST = 'localhost'
REDIS_PORT = 6379
REDIS_KEY = 'libreshot_image_url_set' # 使用去重

class LibreshotScraper:
    """
    高效的 Libreshot 爬虫，支持多线程和 Redis/内存去重。
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
        # 禁用 SSL 警告
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

    def load_tags(self, file_path):
        """
        从本地文件加载标签列表。
        """
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                # 去除空白行和首尾空格
                tags = [line.strip() for line in f if line.strip()]
            print(f"✅ 成功加载 {len(tags)} 个标签。")
            return tags
        except FileNotFoundError:
            print(f"❌ 错误: 标签文件未找到 -> {file_path}")
            return []
        except Exception as e:
            print(f"❌ 错误: 读取标签文件出错 -> {e}")
            return []

    def is_url_visited(self, url):
        """
        使用 Redis 或内存集合检查 URL 是否已被访问。
        成功添加（未访问过）返回 True，否则（已访问过）返回 False。
        """
        if self.redis:
            # Redis: SADD 返回 1 表示添加成功（未重复），返回 0 表示已存在（重复）
            return self.redis.sadd(REDIS_KEY, url) == 1
        else:
            # 内存去重
            if url not in self.visited_urls:
                self.visited_urls.add(url)
                return True
            return False
            
    def write_to_csv(self, title, name, url, csv_path, tag):
        """
        写入 CSV 方法，已集成线程锁，确保多线程安全。
        """
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

    def clean_image_url(self, image_url):
        """
        去除图片 URL 中的分辨率参数（如 -508x339.jpg）以获取原图 URL。
        并提取图片名称。
        """
        # 尝试匹配并去除形如 '-宽度x高度' 的部分
        pattern = r'(-\d+x\d+)(\.[a-zA-Z0-9]+)$'

        match = re.search(pattern, image_url)
        if match:
            # 原图 URL: 替换分辨率部分
            original_url = image_url.replace(match.group(1), '')
        else:
            original_url = image_url

        # 图片名称提取
        name_with_ext = original_url.split('/')[-1]
        name_without_params = name_with_ext.split('?')[0]
        image_name = os.path.splitext(name_without_params)[0]
        
        return original_url, image_name

    def parse_page(self, html_content, tag):
        """
        解析 HTML 内容，提取图片信息并保存。
        """
        if not html_content:
            return
            
        tree = etree.HTML(html_content)
        
        # 使用 XPath 查找所有 img.lazy 元素
        image_elements = tree.xpath('//div[@class="posts"]//img[@class="attachment-post-thumb size-post-thumb wp-post-image lazy"]')

        count = 0
        for img_el in image_elements:
            try:
                # 提取图片 URL
                image_url_with_res = img_el.get('data-src')
                if not image_url_with_res:
                    continue

                # 提取标题
                a_el = img_el.xpath('./ancestor::a[@class="featured-media"]')[0]
                title = a_el.get('title')
                
                # --- 数据清洗与提取 ---
                original_url, image_name = self.clean_image_url(image_url_with_res)

                # --- 去重检查 ---
                if self.is_url_visited(original_url):
                    continue
                
                # --- 保存数据 ---
                self.write_to_csv(title, image_name, original_url, self.csv_path, tag)
                count += 1

            except IndexError:
                print(f"[{tag}] [!] 警告: 无法获取图片的父级 a 元素或标题，跳过此图片。")
                continue
            except Exception as e:
                print(f"[{tag}] [✗] 解析数据时发生错误: {e}")
        
        print(f"[{tag}] [✔] 完成解析，新数据写入 {count} 条。")


    def scrape_tag(self, tag):
        """
        处理单个标签的爬取任务。
        
        将标签中的空格替换为 '+' 进行 URL 编码。
        """
        # --- [修改开始] ---
        # 使用 str.replace() 将标签中的空格替换为 '+'
        encoded_tag = tag.replace(' ', '+')
        url = BASE_URL.format(tag=encoded_tag)
        # --- [修改结束] ---
        
        print(f"[{tag}] 开始爬取 URL: {url}")
        
        try:
            # 建议的请求头和 SSL 忽略设置
            response = requests.get(url, headers=self.headers, verify=False, timeout=15)
            response.raise_for_status()  # 检查 HTTP 错误
            
            self.parse_page(response.content, tag)

        except requests.exceptions.RequestException as e:
            print(f"[{tag}] [✗] 请求出错: {e}")
        except Exception as e:
            print(f"[{tag}] [✗] 发生未知错误: {e}")

    def run_scraper(self):
        """
        主运行方法：加载标签并使用线程池进行并发爬取。
        """
        tags = self.load_tags(TAG_FILE_PATH)
        if not tags:
            print("没有可供爬取的标签，程序终止。")
            return

        print(f"🚀 开始使用 {MAX_WORKERS} 个线程并发爬取 {len(tags)} 个标签...")
        
        start_time = time.time()
        
        # 使用 ThreadPoolExecutor 实现多线程
        with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
            # 提交所有标签的爬取任务
            executor.map(self.scrape_tag, tags)
            
        end_time = time.time()
        
        print("\n==============================================")
        print(f"🎉 所有标签爬取完成。")
        print(f"总耗时: {end_time - start_time:.2f} 秒")
        print(f"数据已保存至: {self.csv_path}")
        print("==============================================")


if __name__ == '__main__':
    scraper = LibreshotScraper(CSV_DIR_PATH, CSV_FILENAME)
    scraper.run_scraper()