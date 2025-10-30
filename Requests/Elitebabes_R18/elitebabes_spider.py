import requests
import urllib3
import os
import csv
import re
import redis
from concurrent.futures import ThreadPoolExecutor, as_completed
from threading import Lock
from bs4 import BeautifulSoup
from lxml import etree
from tqdm import tqdm

# --- 配置常量 ---
BASE_URL = "https://www.elitebabes.com/"
API_URL_TEMPLATE = "https://www.elitebabes.com/gridapi/?content=channel_old&nr=6512&sort=trending&mpage={}"
START_PAGE = 1
# 相册/详情页解析线程数
ALBUM_PARSING_THREADS = 20
# 图片下载线程数
DOWNLOAD_THREADS = 50

# CSV/下载路径配置
CSV_DIR_PATH = r"R:\py\Auto_Image-Spider\Requests\Elitebabes_R18"
CSV_FILENAME = "all_images_data.csv"
DOWNLOAD_PATH = os.path.join(CSV_DIR_PATH, "images")

# Redis 配置
REDIS_HOST = 'localhost'
REDIS_PORT = 6379
REDIS_KEY = 'elitebabes_r18_image_url_set' # 使用 图片URL 作为唯一标识符

class ElitebabesSpider:
    """
    Elitebabes 图片爬虫类：负责相册列表获取、详情页解析、数据存储和异步下载。
    集成了 Redis/内存去重逻辑和线程池管理。
    """
    def __init__(self, csv_dir_path=CSV_DIR_PATH, csv_filename=CSV_FILENAME, 
                 download_path=DOWNLOAD_PATH, redis_host=REDIS_HOST, redis_port=REDIS_PORT):
        """
        初始化爬虫实例，集成 Redis/内存去重逻辑。
        """
        self.csv_dir_path = csv_dir_path
        self.csv_path = os.path.join(self.csv_dir_path, csv_filename) 
        self.download_path = download_path
        self.csv_lock = Lock() # 用于 CSV 写入的线程锁
        self.album_urls = [] # 用于存储所有相册URL和标题的列表
        self.image_data_list = [] # 用于存储所有图片信息的列表

        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Referer': 'https://www.elitebabes.com/watch-4-beauty/',    # 避免 403 错误，如果是模特 /dakota-3/
            'Accept': 'application/json, text/javascript, */*; q=0.01',
            'X-Requested-With': 'XMLHttpRequest'
        }
        urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
        
        # 确保目录存在
        os.makedirs(self.csv_dir_path, exist_ok=True)
        os.makedirs(self.download_path, exist_ok=True)

        # --- 去重初始化逻辑 ---
        try:
            self.redis = redis.StrictRedis(host=redis_host, port=redis_port, decode_responses=True)
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
            
        # 初始化 CSV 文件头
        self._initialize_csv()

    def _initialize_csv(self):
        """初始化 CSV 文件，写入表头（如果文件不存在）。"""
        fieldnames = ['标题', '图片名称', '图片URL', '所属相册', 'watch-4-beauty标签']
        if not os.path.exists(self.csv_path) or os.path.getsize(self.csv_path) == 0:
            with self.csv_lock:
                with open(self.csv_path, 'w', newline='', encoding='utf-8') as f:
                    writer = csv.DictWriter(f, fieldnames=fieldnames)
                    writer.writeheader()
                    print(f"📄 CSV 文件已创建: {self.csv_path}")
        else:
            print(f"📄 CSV 文件已存在: {self.csv_path}")

    def is_url_visited(self, url):
        """检查 URL 是否已被访问或处理（去重）。"""
        if self.redis:
            # Redis 去重：检查集合中是否存在
            return self.redis.sismember(REDIS_KEY, url)
        else:
            # 内存去重：检查 set 中是否存在
            return url in self.visited_urls

    def mark_url_visited(self, url):
        """将 URL 标记为已访问或处理。"""
        if self.redis:
            # Redis 标记：添加到集合
            self.redis.sadd(REDIS_KEY, url)
        else:
            # 内存标记：添加到 set
            self.visited_urls.add(url)

    def crawl_album_list(self):
        """
        第一部分：搜索 watch-4-beauty，获取相册列表的 URL 和标题。
        """
        print("\n--- 1. 🚀 开始获取相册列表 ---")
        page = START_PAGE
        while True:
            url = API_URL_TEMPLATE.format(page)
            print(f"   => 正在爬取第 {page} 页: {url}")
            try:
                response = requests.get(url, headers=self.headers, verify=False, timeout=15)
                # API 返回的不是标准的 JSON，而是包含 HTML 的文本
                if response.status_code == 200 and response.text.strip():
                    # 检查响应内容是否包含相册列表的 HTML
                    if "li style=" not in response.text:
                         print(f"   => 第 {page} 页响应不包含相册列表，或者已到达末页。")
                         break
                         
                    # 使用 lxml/etree 解析包含 HTML 片段的响应
                    # 因为响应内容没有根标签，需要手动添加一个
                    html_content = f"<html><body><ul>{response.text}</ul></body></html>"
                    tree = etree.HTML(html_content)
                    album_elements = tree.xpath('//li/figure/a')
                    
                    if not album_elements:
                        print(f"   => 第 {page} 页未找到相册元素，停止爬取。")
                        break
                        
                    for a_tag in album_elements:
                        album_url = a_tag.get('href')
                        album_title = a_tag.get('title')
                        if album_url and album_title:
                            self.album_urls.append({
                                'album_url': album_url,
                                'album_title': album_title
                            })
                            
                    print(f"   => 第 {page} 页获取 {len(album_elements)} 个相册。")
                    page += 1
                else:
                    print(f"   => 响应状态码非 200 ({response.status_code}) 或内容为空，停止爬取。")
                    break
            except requests.exceptions.RequestException as e:
                print(f"   => 请求第 {page} 页失败: {e}，停止爬取。")
                break
            
        print(f"--- 1. ✅ 相册列表获取完成，共找到 {len(self.album_urls)} 个相册。---")

    def parse_album_page(self, album_info):
        """
        第二部分：访问图片详情页，获取图片信息。
        """
        album_url = album_info['album_url']
        album_title = album_info['album_title']
        
        try:
            response = requests.get(album_url, headers=self.headers, verify=False, timeout=15)
            if response.status_code != 200:
                print(f"   [WARN] 访问相册页失败 {album_url}: 状态码 {response.status_code}")
                return None
            
            # 使用 lxml 解析 HTML 页面
            tree = etree.HTML(response.text)
            
            # 找到所有包含图片信息的 <li> 元素下的 <a> 标签
            image_elements = tree.xpath('//ul[@class="list-gallery static css"]/li/a')
            
            extracted_images = []
            for a_tag in image_elements:
                # 提取最大的分辨率的图片 URL
                data_srcset = a_tag.get('data-srcset')
                image_url = ''
                
                # --- START: 通用原图 URL 提取逻辑 ---
                if data_srcset:
                    # 1. 获取 data-srcset 中第一个 URL（最高分辨率）
                    # 格式如：https://cdn.../0002-01_2400.jpg 2400w, ...
                    first_url_part = data_srcset.split(',')[0].strip()
                    # 提取纯 URL（去除后面的 ' 2400w' 等描述符）
                    max_res_url = first_url_part.split(' ')[0]
                    
                    # 2. 从 max_res_url 中移除随机分辨率后缀
                    
                    # 示例: max_res_url = https://cdn.elitebabes.com/content/250585/0002-01_2400.jpg
                    
                    # 找到最后一个 '/'，分离路径和文件名
                    path_part, filename_part = max_res_url.rsplit('/', 1)
                    
                    # 找到最后一个 '_' 和倒数第一个 '.'
                    last_underscore = filename_part.rfind('_')
                    last_dot = filename_part.rfind('.')
                    
                    if last_underscore != -1 and last_dot != -1 and last_underscore < last_dot:
                        # 假设分辨率后缀在最后一个 '_' 和 '.' 之间
                        # 移除 '_分辨率' 部分
                        # '0002-01_2400.jpg' -> '0002-01' + '.jpg'
                        base_name = filename_part[:last_underscore]
                        extension = filename_part[last_dot:]
                        clean_filename = base_name + extension
                        
                        image_url = path_part + '/' + clean_filename
                    else:
                        # 如果格式不符合预期，则使用最高分辨率的 URL 作为兜底
                        image_url = max_res_url
                # --- END: 通用原图 URL 提取逻辑 ---
                
                # 如果没有 data-srcset，尝试使用 href 属性
                if not image_url:
                    image_url = a_tag.get('href')

                # 提取 img 标签的 alt 属性作为标题
                img_tag = a_tag.find('img')
                if img_tag is not None:
                    image_title = img_tag.get('alt', '').strip()
                else:
                    image_title = album_title # 备用标题
                    
                # 提取图片名称 (使用去除后缀后的 image_url)
                if image_url:
                    # 示例: image_url = https://cdn.../250585/0002-01.jpg
                    name_parts = image_url.split('/')[-2:]
                    # 仅保留文件名部分，去除扩展名
                    base_name = os.path.splitext(name_parts[-1])[0] 
                    # 重新构造图片名称
                    # 示例: 250585_0002-01
                    image_name_for_file = f"{name_parts[-2]}_{base_name}"
                    
                    if not self.is_url_visited(image_url):
                        self.mark_url_visited(image_url) # 标记为已处理
                        
                        extracted_images.append({
                            '标题': image_title,
                            '图片名称': image_name_for_file, # 用于文件名
                            '图片URL': image_url,
                            '所属相册': album_title,
                            'watch-4-beauty标签': 'watch-4-beauty',
                        })

            return extracted_images
            
        except requests.exceptions.RequestException as e:
            print(f"   [ERROR] 解析相册页请求失败 {album_url}: {e}")
            return None
        except Exception as e:
            print(f"   [ERROR] 解析相册页内容失败 {album_url}: {e}")
            return None

    def _process_album_parsing(self, album_info):
        """线程池执行函数：解析单个相册并存储数据。"""
        images_data = self.parse_album_page(album_info)
        if images_data:
            self.image_data_list.extend(images_data) # 收集数据到列表
            self.save_to_csv(images_data) # 实时写入 CSV
            print(f"   [INFO] 已解析 {album_info['album_title']}，获取 {len(images_data)} 张图片。")


    def start_crawl(self, download_enabled=False):
        """
        启动爬虫任务，支持仅爬取数据或爬取+下载两种模式。
        """
        # 1. 爬取相册列表
        self.crawl_album_list()
        
        if not self.album_urls:
            print("🛑 没有找到相册列表，爬虫结束。")
            return

        print(f"\n--- 2. ⚡️ 开始异步解析 {len(self.album_urls)} 个相册 ({ALBUM_PARSING_THREADS} 线程) ---")
        
        # 2. 异步解析相册详情页
        # 使用 ThreadPoolExecutor 进行并发解析
        with ThreadPoolExecutor(max_workers=ALBUM_PARSING_THREADS) as executor:
            # 提交任务
            future_to_album = {executor.submit(self._process_album_parsing, album_info): album_info for album_info in self.album_urls}
            
            # 使用 tqdm 进度条追踪任务完成情况
            for future in tqdm(as_completed(future_to_album), total=len(self.album_urls), desc="相册解析进度"):
                # 简单处理异常，不影响其他线程
                try:
                    future.result()
                except Exception as exc:
                    album_info = future_to_album[future]
                    print(f"   [ERROR] 相册 {album_info['album_url']} 在解析时发生异常: {exc}")

        print("--- 2. ✅ 所有相册解析完成。---")
        
        # 3. 如果启用了下载，则启动下载任务
        if download_enabled:
            # 从 CSV 文件重新加载数据，确保下载的是最新的完整列表
            self.image_data_list = self._load_data_from_csv()
            if self.image_data_list:
                self.start_download()
            else:
                print("🛑 CSV 中没有图片数据，无法启动下载。")


    def save_to_csv(self, data_list):
        """
        将图片信息写入 CSV 文件。
        """
        fieldnames = ['标题', '图片名称', '图片URL', '所属相册', 'watch-4-beauty标签']
        with self.csv_lock: # 使用锁确保多线程写入安全
            with open(self.csv_path, 'a', newline='', encoding='utf-8') as f:
                writer = csv.DictWriter(f, fieldnames=fieldnames)
                for data in data_list:
                    writer.writerow(data)


    def _load_data_from_csv(self):
        """从 CSV 文件加载所有数据，用于单独启动下载或确保完整列表。"""
        data = []
        if os.path.exists(self.csv_path):
            try:
                with open(self.csv_path, 'r', newline='', encoding='utf-8') as f:
                    reader = csv.DictReader(f)
                    for row in reader:
                        data.append(row)
                print(f"💾 已从 CSV 文件加载 {len(data)} 条图片记录。")
            except Exception as e:
                print(f"   [ERROR] 加载 CSV 文件失败: {e}")
        return data


    def download_image(self, image_data):
        """
        第三部分：下载单张图片到本地文件夹。
        """
        image_url = image_data['图片URL']
        album_title = image_data['所属相册']
        image_name = image_data['图片名称'] # 包含唯一 ID 和分辨率前缀

        # 1. 创建子文件夹（以相册标题命名，并进行安全文件名处理）
        # 移除 Windows 文件名非法字符
        safe_album_title = re.sub(r'[\\/:*?"<>|]', '', album_title).strip()
        album_dir = os.path.join(self.download_path, safe_album_title)
        os.makedirs(album_dir, exist_ok=True)
        
        # 2. 构造最终文件路径（保留原始扩展名）
        _, ext = os.path.splitext(image_url.split('?')[0])
        if not ext: ext = '.jpg' # 默认扩展名
        
        final_file_path = os.path.join(album_dir, f"{image_name}{ext}")

        # 3. 检查文件是否已存在（二次去重/断点续传）
        if os.path.exists(final_file_path):
            # print(f"      [SKIP] 文件已存在: {final_file_path}")
            return final_file_path # 返回已存在的文件路径

        # 4. 下载图片
        try:
            # 添加 Referer 头以避免 403 错误
            download_headers = self.headers.copy()
            download_headers['Referer'] = BASE_URL # 随便一个 referrer 
            
            response = requests.get(image_url, headers=download_headers, stream=True, verify=False, timeout=30)
            
            if response.status_code == 200:
                with open(final_file_path, 'wb') as f:
                    # 使用 response.iter_content 节省内存
                    for chunk in response.iter_content(chunk_size=8192):
                        if chunk:
                            f.write(chunk)
                # print(f"      [SUCCESS] 下载完成: {final_file_path}")
                return final_file_path
            else:
                # print(f"      [FAIL] 下载失败 {image_url}: 状态码 {response.status_code}")
                return None
        except requests.exceptions.RequestException as e:
            # print(f"      [ERROR] 下载请求失败 {image_url}: {e}")
            return None


    def start_download(self):
        """
        单独启动下载任务，从已存储的 CSV 数据中读取信息进行下载。
        """
        # 确保数据已从 CSV 文件加载
        if not self.image_data_list:
            self.image_data_list = self._load_data_from_csv()

        if not self.image_data_list:
            print("🛑 无法启动下载：请先运行爬取模式获取数据到 CSV 文件。")
            return

        print(f"\n--- 3. 💾 开始异步下载 {len(self.image_data_list)} 张图片 ({DOWNLOAD_THREADS} 线程) ---")
        
        # 3. 异步下载图片
        with ThreadPoolExecutor(max_workers=DOWNLOAD_THREADS) as executor:
            future_to_image = {executor.submit(self.download_image, img_data): img_data for img_data in self.image_data_list}
            
            # 使用 tqdm 进度条追踪任务完成情况
            download_success_count = 0
            for future in tqdm(as_completed(future_to_image), total=len(self.image_data_list), desc="图片下载进度"):
                try:
                    result = future.result()
                    if result:
                        download_success_count += 1
                except Exception as exc:
                    image_data = future_to_image[future]
                    # print(f"   [ERROR] 图片 {image_data['图片URL']} 在下载时发生异常: {exc}")
        
        print(f"--- 3. ✅ 所有下载任务完成。成功下载/跳过 {download_success_count} 张图片。---")


# --- 启动代码 ---
if __name__ == '__main__':
    # 实例化爬虫
    spider = ElitebabesSpider()
    
    # --- 运行模式示例 ---
    
    # 示例 1: 仅爬取数据到 CSV，不下载图片
    # print("\n--- 模式一：仅爬取数据到 CSV (download_enabled=False) ---")
    # spider.start_crawl(download_enabled=False)
    
    # 示例 2: 爬取数据并下载图片 (如果需要，请取消下一行的注释)
    # print("\n--- 模式二：爬取数据并下载图片 (download_enabled=True) ---")
    # spider.start_crawl(download_enabled=True) 

    # 示例 3: 也可以在数据收集完成后单独启动下载任务
    # 注意：运行此模式前，请确保已运行过模式一或二，且 CSV 文件中包含数据
    print("\n--- 模式三：单独启动下载任务 ---")
    spider.start_download()