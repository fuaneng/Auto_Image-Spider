import os
import re
import csv
import time
import requests
import urllib3
import redis
from concurrent.futures import ThreadPoolExecutor
from threading import Lock
from bs4 import BeautifulSoup

# --- 配置常量 ---
BASE_SEARCH_URL = "https://www.pornpics.com/search/srch.php"
BASE_GALLERY_URL = "https://www.pornpics.com"
MAX_WORKERS_CRAWL = 5  # 爬取线程数
MAX_WORKERS_DOWNLOAD = 10 # 下载线程数

# 文件路径配置
TAG_FILE_PATH = r"R:\py\Auto_Image-Spider\Requests\Pornpics\人名tag.txt"
CSV_DIR_PATH = r"R:\py\Auto_Image-Spider\Requests\Pornpics"
CSV_FILENAME = "all_images_data.csv"
DOWNLOAD_DIR_PATH = r"R:\py\Auto_Image-Spider\Requests\Pornpics\images"

# Redis 配置
REDIS_HOST = 'localhost'
REDIS_PORT = 6379
REDIS_KEY = 'pornpics_image_url_set' # 使用 图片 URL 作为唯一标识符

class PornpicsSpider:
    """
    Pornpics 爬虫类，集成了搜索、详情页解析、CSV 存储、Redis/内存去重和异步下载功能。
    """
    def __init__(self, csv_dir_path, csv_filename, redis_host=REDIS_HOST, redis_port=REDIS_PORT):
        """
        初始化爬虫实例，集成 Redis/内存去重逻辑。
        """
        self.csv_dir_path = csv_dir_path
        self.csv_path = os.path.join(self.csv_dir_path, csv_filename)
        self.csv_lock = Lock() # 用于 CSV 写入的线程锁
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Referer': 'https://www.pornpics.com/' # 有时 Referer 是必须的
        }
        urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
        self._setup_redis_duplication(redis_host, redis_port)
        self._ensure_csv_headers()

    def _setup_redis_duplication(self, redis_host, redis_port):
        """ 初始化 Redis 连接或回退到内存去重 """
        try:
            # 尝试连接 Redis
            self.redis = redis.StrictRedis(host=redis_host, port=redis_port, decode_responses=True, socket_connect_timeout=5)
            # 尝试执行一次 ping 来验证连接
            self.redis.ping()
            print("✅ Redis 连接成功，使用 Redis 集合进行去重。")
        except redis.exceptions.ConnectionError as e:
            print(f"⚠️ Redis 连接失败 ({e})，将使用内存去重。")
            self.redis = None
            # 内存去重集合，用于在当前程序生命周期内的去重
            self.visited_urls = set()
        except Exception as e:
            print(f"⚠️ Redis 初始化遇到其他错误 ({e})，将使用内存去重。")
            self.redis = None
            self.visited_urls = set()

    def _ensure_csv_headers(self):
        """ 确保 CSV 文件及其表头存在 """
        fieldnames = ['标题', '图片名称', '图片URL', '所属相册', '人名Tag标签']
        if not os.path.exists(self.csv_path):
            os.makedirs(os.path.dirname(self.csv_path), exist_ok=True)
            with open(self.csv_path, 'w', newline='', encoding='utf-8-sig') as f:
                writer = csv.DictWriter(f, fieldnames=fieldnames)
                writer.writeheader()
            print(f"📄 已创建 CSV 文件：{self.csv_path} 并写入表头。")

    def _is_url_visited(self, image_url):
        """ 检查 URL 是否已被访问（去重） """
        if self.redis:
            # 使用 Redis 的 sadd 方法，如果元素已存在，返回 0
            return self.redis.sadd(REDIS_KEY, image_url) == 0
        else:
            # 内存去重
            if image_url in self.visited_urls:
                return True
            self.visited_urls.add(image_url)
            return False

    def _read_tags(self, file_path):
        """ 从文件读取人名 Tag 列表 """
        if not os.path.exists(file_path):
            print(f"❌ 错误：Tag 文件不存在于 {file_path}")
            return []
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                # 过滤空行并去除首尾空格
                return [tag.strip() for tag in f if tag.strip()]
        except Exception as e:
            print(f"❌ 读取 Tag 文件时发生错误: {e}")
            return []

    # --- 第一部分：搜索相册列表 ---
    def _fetch_gallery_list(self, tag):
        """ 搜索特定 Tag 的所有相册，并返回相册URL和标题列表 """
        galleries = []
        offset = 0
        tag_encoded = tag.replace(' ', '+') # 替换空格为 '+'

        while True:
            search_params = {
                'q': tag_encoded,
                'lang': 'zh',
                'limit': 20,
                'offset': offset
            }
            search_url = f"{BASE_SEARCH_URL}?q={tag_encoded}&lang=zh&limit=20&offset={offset}"
            print(f"🔍 正在搜索 Tag: {tag} - 页码 Offset: {offset}")

            try:
                response = requests.get(search_url, headers=self.headers, verify=False, timeout=15)
                response.raise_for_status()
                data = response.json()
            except requests.exceptions.RequestException as e:
                print(f"❌ 搜索请求失败: {search_url} - 错误: {e}")
                break
            except ValueError:
                print(f"❌ 响应不是有效的 JSON: {search_url}")
                break
            
            # 递进页码如果没有相册加载，这表示没有更多页码
            if not data:
                print(f"✅ Tag: {tag} - 相册列表爬取完成。")
                break

            for item in data:
                gallery_url = item.get('g_url')
                gallery_title = item.get('desc')
                if gallery_url and gallery_title:
                    # 确保是完整的 URL
                    if not gallery_url.startswith('http'):
                        gallery_url = BASE_GALLERY_URL + gallery_url
                    galleries.append({
                        'gallery_url': gallery_url,
                        'gallery_title': gallery_title,
                        'tag': tag
                    })
            
            offset += 20
            time.sleep(1) # 礼貌性等待

        return galleries

    # --- 第二部分：访问详情页，获取图片信息并写入表格 ---
    def _parse_gallery_page(self, gallery_info):
        """ 访问单个相册详情页，提取图片信息并写入 CSV """
        gallery_url = gallery_info['gallery_url']
        gallery_title = gallery_info['gallery_title']
        tag = gallery_info['tag']
        
        print(f"🖼️ 正在解析相册: {gallery_title} ({gallery_url})")

        try:
            response = requests.get(gallery_url, headers=self.headers, verify=False, timeout=15)
            response.raise_for_status()
            response.encoding = 'utf-8' # 确保中文标题正确解析
            soup = BeautifulSoup(response.text, 'html.parser')
        except requests.exceptions.RequestException as e:
            print(f"❌ 详情页请求失败: {gallery_url} - 错误: {e}")
            return
        
        # 定位到包含图片列表的 ul 元素
        tiles_ul = soup.find('ul', id='tiles')
        if not tiles_ul:
            print(f"⚠️ 未找到相册图片列表: {gallery_url}")
            return

        image_data_list = []
        # 查找所有 li.thumbwook 下的 a.rel-link 元素
        for a_tag in tiles_ul.select('li.thumbwook a.rel-link'):
            image_url = a_tag.get('href') # 图片原图 URL
            img_tag = a_tag.find('img')
            
            if image_url and img_tag:
                image_title = img_tag.get('alt', '').strip() # 图片标题
                
                # 从图片 URL 中提取图片名称
                match = re.search(r'[^/]+$', image_url)
                if match:
                    full_filename = match.group(0)
                    # 去掉扩展名即为名称
                    image_name, _ = os.path.splitext(full_filename) 
                else:
                    image_name = 'unknown' # 无法提取时使用默认值

                data_row = {
                    '标题': image_title,
                    '图片名称': image_name,
                    '图片URL': image_url,
                    '所属相册': gallery_title,
                    '人名Tag标签': tag
                }

                # 检查 URL 是否已存在（去重）
                if not self._is_url_visited(image_url):
                    image_data_list.append(data_row)
                    print(f"   [+] 收集图片: {image_name}")
                else:
                    print(f"   [-] 跳过重复图片: {image_name}")


        # 批量写入 CSV
        if image_data_list:
            self._write_to_csv(image_data_list)
            print(f"✅ 相册 {gallery_title} 的 {len(image_data_list)} 张图片信息已写入 CSV。")
        else:
            print(f"ℹ️ 相册 {gallery_title} 中没有新的图片数据写入。")

    def _write_to_csv(self, data_list):
        """ 线程安全地将数据写入 CSV 文件 """
        fieldnames = ['标题', '图片名称', '图片URL', '所属相册', '人名Tag标签']
        with self.csv_lock: # 使用线程锁
            with open(self.csv_path, 'a', newline='', encoding='utf-8-sig') as f:
                writer = csv.DictWriter(f, fieldnames=fieldnames)
                writer.writerows(data_list)

    def start_crawl(self, download_enabled=False):
        """ 
        启动爬虫任务，控制数据收集和可选的下载。
        :param download_enabled: bool, 是否在数据收集后立即启动下载。
        """
        print("\n--- 🌐 爬虫数据收集阶段开始 ---")
        tags = self._read_tags(TAG_FILE_PATH)
        if not tags:
            print("❌ 爬虫终止：未找到或无法读取人名 Tag。")
            return

        all_galleries = []
        # 1. 获取所有 Tag 的相册列表 (同步操作，避免并发引起 offset 混乱)
        for tag in tags:
            galleries = self._fetch_gallery_list(tag)
            all_galleries.extend(galleries)
            time.sleep(2) # 搜索 Tag 之间稍作停顿

        if not all_galleries:
            print("❌ 爬虫终止：未找到任何相册。")
            return

        print(f"✅ 总共找到 {len(all_galleries)} 个相册，启动并发解析。")

        # 2. 并发访问相册详情页并写入 CSV
        with ThreadPoolExecutor(max_workers=MAX_WORKERS_CRAWL) as executor:
            executor.map(self._parse_gallery_page, all_galleries)

        print("\n--- ✅ 爬虫数据收集阶段完成 ---")

        if download_enabled:
            print("\n--- ⬇️ 立即启动图片下载任务 ---")
            self.start_download()

    # --- 第三部分：启动下载图片 ---
    def start_download(self):
        """ 从 CSV 文件读取数据，启动解耦式异步多线程下载图片 """
        if not os.path.exists(self.csv_path):
            print(f"❌ 下载终止：CSV 文件不存在于 {self.csv_path}")
            return

        print(f"⬇️ 正在从 {self.csv_path} 读取下载任务...")
        
        download_tasks = []
        try:
            with open(self.csv_path, 'r', newline='', encoding='utf-8-sig') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    # 准备下载所需信息
                    download_tasks.append({
                        'image_url': row['图片URL'],
                        'album_name': row['所属相册'],
                        'filename': row['图片名称'],
                        'tag': row['人名Tag标签']
                    })
        except Exception as e:
            print(f"❌ 读取 CSV 文件时发生错误: {e}")
            return

        if not download_tasks:
            print("ℹ️ CSV 文件中没有找到下载任务。")
            return

        print(f"🚀 启动 {len(download_tasks)} 个图片的下载任务，使用 {MAX_WORKERS_DOWNLOAD} 线程。")

        # 使用多线程执行下载任务
        with ThreadPoolExecutor(max_workers=MAX_WORKERS_DOWNLOAD) as executor:
            executor.map(self._download_image_task, download_tasks)

        print("\n--- ✅ 所有图片下载任务完成 ---")


    def _download_image_task(self, task):
        """ 单个图片的下载逻辑 """
        image_url = task['image_url']
        album_name = task['album_name']
        filename = task['filename']
        
        # 提取文件扩展名，用于保留原始格式
        ext = os.path.splitext(os.path.basename(image_url))[-1]
        
        # 构建子文件夹路径 (使用相册字段作为子文件夹名)
        # 清理相册名中的非法字符，以防创建文件夹失败
        safe_album_name = re.sub(r'[\\/:*?"<>|]', '_', album_name) 
        sub_dir = os.path.join(DOWNLOAD_DIR_PATH, safe_album_name)
        os.makedirs(sub_dir, exist_ok=True)
        
        # 完整的文件路径 (使用名称字段作为文件名，保留扩展名)
        file_path = os.path.join(sub_dir, f"{filename}{ext}")

        # 检查文件是否已存在（二次去重/断点续传简单实现）
        if os.path.exists(file_path):
            # print(f"   [SKIP] 文件已存在: {file_path}")
            return

        try:
            # 流式下载图片
            response = requests.get(image_url, headers=self.headers, verify=False, stream=True, timeout=30)
            response.raise_for_status()

            with open(file_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)
            print(f"   [SUCCESS] 下载完成: {file_path}")

        except requests.exceptions.RequestException as e:
            print(f"   [ERROR] 下载失败: {image_url} - 错误: {e}")
        except Exception as e:
            print(f"   [ERROR] 处理下载文件时发生未知错误: {e}")


if __name__ == '__main__':
    # 确保下载目录存在
    os.makedirs(DOWNLOAD_DIR_PATH, exist_ok=True)
    
    # 实例化爬虫
    spider = PornpicsSpider(
        csv_dir_path=CSV_DIR_PATH, 
        csv_filename=CSV_FILENAME
    )

    # --- 运行模式示例 ---
    
    # 示例 1: 仅爬取数据到 CSV，不下载图片
    print("\n--- 模式一：仅爬取数据到 CSV (download_enabled=False) ---")
    spider.start_crawl(download_enabled=False)
    
    # # 示例 2: 爬取数据并下载图片 (如果需要，请取消下一行的注释)
    # print("\n--- 模式二：爬取数据并下载图片 (download_enabled=True) ---")
    # spider.start_crawl(download_enabled=True) 

    # 示例 3: 也可以在数据收集完成后单独启动下载任务
    # print("\n--- 模式三：单独启动下载任务 ---")
    # spider.start_download()