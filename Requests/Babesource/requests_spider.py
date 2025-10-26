import requests
import os
import csv
import time
import urllib3
import redis
from bs4 import BeautifulSoup
from concurrent.futures import ThreadPoolExecutor, as_completed
from threading import Lock

# --- 配置常量 ---
REDIS_HOST = 'localhost'
REDIS_PORT = 6379
REDIS_KEY = 'babesource_image_url_set' # 使用 图片 URL 作为唯一标识符进行去重

# 文件路径配置
BASE_DIR = r"R:\py\Auto_Image-Spider\Requests\Babesource"
TAG_FILE = os.path.join(BASE_DIR, "人名tag.txt")
CSV_PATH = os.path.join(BASE_DIR, "all_images_data.csv")
DOWNLOAD_DIR = os.path.join(BASE_DIR, "images")

# 确保文件夹存在
os.makedirs(os.path.dirname(CSV_PATH), exist_ok=True)
os.makedirs(DOWNLOAD_DIR, exist_ok=True)


class BabesourceSpider:
    """
    Babesource 爬虫类：负责搜索、解析、数据存储和图片下载。
    支持 Redis/内存去重和下载功能开关。
    """
    def __init__(self, tag_file_path=TAG_FILE, csv_path=CSV_PATH, download_dir=DOWNLOAD_DIR):
        
        self.tag_file_path = tag_file_path
        self.csv_path = csv_path
        self.download_dir = download_dir
        self.csv_lock = Lock()  # 用于 CSV 写入的线程锁
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        # 禁用 SSL 警告，因为使用了 verify=False
        urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
        
        # CSV 字段名：请注意，此处保留了 '相册' 和 '所属集合' 两个字段以保持数据的分类信息
        self.csv_fieldnames = ['图片URL', '标题', '名称', '相册', '所属集合'] 

        # --- 去重初始化逻辑 ---
        try:
            self.redis = redis.StrictRedis(host=REDIS_HOST, port=REDIS_PORT, decode_responses=True)
            self.redis.ping()
            print("✅ Redis 连接成功，使用 Redis 集合进行去重。")
        except redis.exceptions.ConnectionError as e:
            print(f"⚠️ Redis 连接失败 ({e})，将使用内存去重。")
            self.redis = None
            self.visited_urls = set()
        except Exception as e:
            print(f"⚠️ Redis 初始化遇到其他错误 ({e})，将使用内存去重。")
            self.redis = None
            self.visited_urls = set()
            
        # 确保 CSV 文件头部存在
        if not os.path.exists(self.csv_path) or os.path.getsize(self.csv_path) == 0:
            with open(self.csv_path, 'w', newline='', encoding='utf-8') as f:
                writer = csv.DictWriter(f, fieldnames=self.csv_fieldnames)
                writer.writeheader()


    def is_url_visited(self, url):
        """检查 URL 是否已访问 (去重)"""
        if self.redis:
            # Redis: SADD 返回 1 表示添加成功（未重复），返回 0 表示已存在（重复）
            return not self.redis.sadd(REDIS_KEY, url)
        else:
            # 内存去重
            if url in self.visited_urls:
                return True
            self.visited_urls.add(url)
            return False

    def write_to_csv(self, data):
        """将数据写入 CSV 文件 (线程安全)"""
        # 在写入前先进行去重检查
        if self.is_url_visited(data['图片URL']):
            return False
            
        with self.csv_lock:
            try:
                with open(self.csv_path, 'a', newline='', encoding='utf-8') as f:
                    writer = csv.DictWriter(f, fieldnames=self.csv_fieldnames)
                    writer.writerow(data)
                return True
            except Exception as e:
                print(f"❌ 写入 CSV 失败: {e}")
                # 写入失败则从去重集合中移除
                if self.redis:
                    self.redis.srem(REDIS_KEY, data['图片URL'])
                else:
                    self.visited_urls.remove(data['图片URL'])
                return False

    def get_html(self, url):
        """发送 HTTP 请求并返回 BeautifulSoup 对象"""
        try:
            # verify=False 忽略 SSL 证书验证，因为网站可能使用自签名或旧协议
            response = requests.get(url, headers=self.headers, verify=False, timeout=10)
            response.raise_for_status() # 检查 HTTP 错误
            # 使用 lxml 解析器提高解析速度
            return BeautifulSoup(response.text, 'lxml') 
        except requests.exceptions.RequestException as e:
            # print(f"❌ 请求失败: {url} -> {e}")
            return None

    # --- 第一部分：搜索相册列表 ---
    def scrape_album_list(self, tag_name):
        """
        搜索人名标签，获取所有相册详情页 URL
        """
        album_urls = []
        page = 1
        print(f"\n--- 🔎 开始爬取标签: {tag_name} ---")
        
        while True:
            search_url = f"https://babesource.com/pornstars/{tag_name}/page{page}.html"
            soup = self.get_html(search_url)
            time.sleep(1) # 礼貌性延迟

            if soup is None:
                break

            # 查找相册卡片元素
            album_cards = soup.select('.main-content__card.tumba-card')

            # 退出条件：如果没有找到任何相册卡片，则认为没有更多页面
            if not album_cards:
                print(f"   -> 第 {page} 页没有找到相册卡片，结束 {tag_name} 的爬取。")
                break
                
            print(f"   -> 发现第 {page} 页有 {len(album_cards)} 个相册。")
                
            for card in album_cards:
                # 获取相册链接
                link_tag = card.select_one('.main-content__card-link')
                if link_tag and 'href' in link_tag.attrs:
                    album_url = link_tag['href']
                    album_urls.append(album_url)
            
            page += 1

        return list(set(album_urls))


    # --- 第二部分：访问图片详情页，获取图片信息 ---
    def scrape_image_details(self, album_url, tag_name):
        """
        访问相册详情页，提取图片信息并写入 CSV
        """
        # 相册名称：从URL中提取最后一个 '/' 后的文本，去掉 .html
        album_name = album_url.split('/')[-1].replace('.html', '') 

        soup = self.get_html(album_url)
        time.sleep(0.5) # 礼貌性延迟
        
        if soup is None:
            return

        # 查找所有图片容器中的原始图片链接
        image_links = soup.select('.box-massage__tumba .box-massage__card-link')

        if not image_links:
            # print(f"   -> 相册中没有找到图片链接，跳过: {album_name}")
            return

        for link_tag in image_links:
            image_url = link_tag['href'] if 'href' in link_tag.attrs else None
            
            img_tag = link_tag.select_one('picture img')
            # 提取 alt 属性作为标题，如果 alt 缺失则为空字符串
            title = img_tag.get('alt', '').strip() if img_tag else '' 

            if image_url:
                # 提取 图片名称 (不带扩展名)
                file_with_ext = image_url.split('/')[-1]
                image_name = os.path.splitext(file_with_ext)[0]
                
                data = {
                    '图片URL': image_url,
                    '标题': title,
                    '名称': image_name,
                    '相册': album_name,       # 例如: nancy-heal-fit-190563
                    '所属集合': tag_name     # 例如: nancy-12284
                }
                
                # 写入 CSV (已包含去重逻辑)
                if self.write_to_csv(data):
                    print(f"   -> 写入数据: {album_name}/{image_name} (URL: {image_url[:50]}...)")
            
            
    # --- 第三部分：启动下载图片 ---
    def download_image(self, image_info):
        """
        下载单个图片文件
        """
        url = image_info['图片URL']
        album_name = image_info['相册']
        image_name = image_info['名称']
        
        # 提取文件扩展名
        file_ext = os.path.splitext(url.split('/')[-1])[1]
        
        # 构造本地保存路径: 相册名作为子文件夹名
        album_dir = os.path.join(self.download_dir, album_name)
        os.makedirs(album_dir, exist_ok=True) 
        
        # 完整文件路径: .../images/相册/名称.扩展名
        file_path = os.path.join(album_dir, f"{image_name}{file_ext}")
        
        if os.path.exists(file_path):
            return True # 文件已存在，跳过下载
        
        try:
            response = requests.get(url, headers=self.headers, stream=True, verify=False, timeout=20)
            response.raise_for_status()

            with open(file_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    f.write(chunk)
            print(f"✅ 下载成功: {album_name}/{image_name}{file_ext}")
            return True
        except requests.exceptions.RequestException as e:
            print(f"❌ 下载失败 ({album_name}/{image_name}): {e}")
            return False
        except Exception as e:
            print(f"❌ 发生其他错误 ({album_name}/{image_name}): {e}")
            return False


    def start_crawl(self, download_enabled=True):
        """
        爬虫主入口：读取标签文件，执行爬取和可选的下载。
        """
        print("--- 启动 Babesource 爬虫 ---")
        tag_names = []
        
        # 读取标签文件
        try:
            with open(self.tag_file_path, 'r', encoding='utf-8') as f:
                tag_names = [line.strip() for line in f if line.strip()]
        except FileNotFoundError:
            print(f"❌ 标签文件未找到: {self.tag_file_path}")
            return

        if not tag_names:
            print("⚠️ 标签文件为空，无任务可执行。")
            return

        # 1. 爬取所有标签下的相册列表
        all_album_urls = []
        for tag in tag_names:
            urls = self.scrape_album_list(tag)
            # 存储 (相册URL, 人名标签) 对
            all_album_urls.extend([(url, tag) for url in urls]) 
        
        print(f"\n--- ✅ 完成相册列表爬取，共发现 {len(all_album_urls)} 个相册 ---")
        
        # 2. 多线程处理相册详情页，提取图片信息并写入 CSV
        MAX_WORKERS = 5 
        print(f"--- 🚀 启动 {MAX_WORKERS} 线程处理相册详情页 ---")
        
        with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
            futures = [executor.submit(self.scrape_image_details, url, tag) 
                       for url, tag in all_album_urls]
            
            # 等待所有相册处理完成
            for i, future in enumerate(as_completed(futures)):
                pass 

        print("\n--- ✅ 所有相册详情页信息提取完毕并写入 CSV ---")

        # 3. 可选：启动下载任务
        if download_enabled:
            self.start_download() 
        else:
            print("--- 🚧 跳过图片下载任务 (download_enabled=False) ---")

    def start_download(self):
        """
        读取 CSV 文件，启动图片异步多线程下载
        """
        print("\n--- 📥 启动图片下载任务 ---")
        
        image_list_to_download = []
        try:
            with open(self.csv_path, 'r', newline='', encoding='utf-8') as f:
                reader = csv.DictReader(f) # 自动使用第一行作为字段名
                for row in reader:
                    # 仅下载那些 URL 没有被去重过的（虽然理论上写入时已经去重，这里是双重保险）
                    if not self.is_url_visited(row['图片URL']):
                        image_list_to_download.append(row)
        except FileNotFoundError:
            print(f"❌ CSV 文件未找到: {self.csv_path}。请先运行爬取部分。")
            return

        if not image_list_to_download:
            print("⚠️ CSV 文件中没有新的图片信息需要下载。")
            return
            
        print(f"--- 准备下载 {len(image_list_to_download)} 张图片 ---")

        # 使用多线程进行下载
        MAX_DOWNLOAD_WORKERS = 10 
        successful_downloads = 0
        total_downloads = len(image_list_to_download)
        
        with ThreadPoolExecutor(max_workers=MAX_DOWNLOAD_WORKERS) as executor:
            futures = [executor.submit(self.download_image, img_info) 
                       for img_info in image_list_to_download]
                       
            for i, future in enumerate(as_completed(futures)):
                if future.result():
                    successful_downloads += 1
                
        print(f"\n--- ✅ 图片下载任务完成！成功下载 {successful_downloads}/{total_downloads} 张图片 ---")


if __name__ == '__main__':
    # --- 准备工作：创建示例标签文件 ---
    if not os.path.exists(TAG_FILE):
        print(f"💡 正在创建示例标签文件: {TAG_FILE}")
        os.makedirs(os.path.dirname(TAG_FILE), exist_ok=True)
        with open(TAG_FILE, 'w', encoding='utf-8') as f:
            f.write("nancy-12284\n")
            # f.write("另一个标签-id\n") # 可以在此添加更多人名标签
            
    spider = BabesourceSpider()
    
    # --- 运行模式示例 ---
    
    # 示例 1: 仅爬取数据到 CSV，不下载图片
    # print("\n--- 模式一：仅爬取数据到 CSV (download_enabled=False) ---")
    # spider.start_crawl(download_enabled=False)
    
    # 示例 2: 爬取数据并下载图片 (如果需要，请取消下一行的注释)
    # print("\n--- 模式二：爬取数据并下载图片 (download_enabled=True) ---")
    # spider.start_crawl(download_enabled=True) 

    # 示例 3: 也可以在数据收集完成后单独启动下载任务
    print("\n--- 模式三：单独启动下载任务 ---")
    spider.start_download()