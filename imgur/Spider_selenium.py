import os
import csv
import time
import redis
import urllib3
import requests
from threading import Lock
from concurrent.futures import ThreadPoolExecutor, as_completed
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options


# === 常量配置 ===
REDIS_HOST = 'localhost'
REDIS_PORT = 6379
REDIS_KEY = 'imgur_image_url_set'

TAG_FILE_PATH = r"D:\myproject\Code\爬虫\爬虫数据\libreshot\ram_tag_list_备份.txt"
CSV_DIR_PATH = r"D:\myproject\Code\爬虫\爬虫数据\imgur"
CLIENT_ID = "d70305e7c3ac5c6"
CHROME_DRIVER_PATH = r'C:\Program Files\Google\chromedriver-win64\chromedriver.exe'


# === 核心爬虫类 ===
class ImgurCrawler:
    def __init__(self, csv_dir_path, csv_filename, redis_host=REDIS_HOST, redis_port=REDIS_PORT):
        self.csv_dir_path = csv_dir_path
        self.csv_path = os.path.join(self.csv_dir_path, csv_filename)
        self.csv_lock = Lock()

        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Accept': 'application/json'
        }
        urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

        # Redis 初始化
        try:
            self.redis = redis.StrictRedis(host=redis_host, port=redis_port, decode_responses=True)
            self.redis.ping()
            print("✅ Redis 连接成功，使用 Redis 去重。")
        except redis.exceptions.ConnectionError as e:
            print(f"⚠️ Redis 连接失败 ({e})，改用内存去重。")
            self.redis = None
            self.visited_urls = set()

    def is_duplicated(self, url):
        """去重逻辑"""
        if self.redis:
            if self.redis.sismember(REDIS_KEY, url):
                return True
            else:
                self.redis.sadd(REDIS_KEY, url)
                return False
        else:
            if url in self.visited_urls:
                return True
            self.visited_urls.add(url)
            return False

    def write_to_csv(self, title, name, url, tag):
        """写入 CSV"""
        try:
            with self.csv_lock:
                os.makedirs(os.path.dirname(self.csv_path), exist_ok=True)
                is_file_empty = not os.path.exists(self.csv_path) or os.stat(self.csv_path).st_size == 0

                with open(self.csv_path, 'a', newline='', encoding='utf-8-sig') as f:
                    writer = csv.writer(f)
                    if is_file_empty:
                        writer.writerow(['Title', 'ImageName', 'URL', 'TAG'])
                    writer.writerow([title, name, url, tag])
        except Exception as e:
            print(f"[{tag}] [✗] 写入 CSV 出错: {e}")

    def fetch_tag_page(self, tag, page):
        """请求单页"""
        api_url = f"https://api.imgur.com/post/v1/posts/t/{tag}?client_id={CLIENT_ID}&filter%5Bwindow%5D=week&include=adtiles%2Cadconfig%2Ccover&location=desktoptag&page={page}&sort=-viral"
        try:
            response = requests.get(api_url, headers=self.headers, timeout=10, verify=False)
            if response.status_code == 404:
                return None
            data = response.json()
            return data.get("posts", [])
        except Exception as e:
            print(f"[{tag}] [✗] 第 {page} 页请求出错: {e}")
            return None

    def parse_and_save(self, posts, tag):
        """解析 JSON"""
        for post in posts:
            try:
                mime_type = post.get("cover", {}).get("mime_type", "")
                if not mime_type.startswith("image/"):
                    continue  # 非图片跳过

                img_url = post["cover"]["url"]
                title = post.get("title", "").strip()
                image_name = os.path.basename(img_url)

                if not self.is_duplicated(img_url):
                    self.write_to_csv(title, image_name, img_url, tag)
                    print(f"[{tag}] ✅ {title} | {img_url}")
                else:
                    print(f"[{tag}] ⚙️ 已存在: {img_url}")
            except Exception as e:
                print(f"[{tag}] [✗] 解析出错: {e}")

    def crawl_tag(self, tag):
        """分页爬取"""
        print(f"🚀 开始抓取标签: {tag}")
        page = 1
        while True:
            posts = self.fetch_tag_page(tag, page)
            if not posts:
                print(f"[{tag}] 🛑 无更多数据，结束。")
                break
            self.parse_and_save(posts, tag)
            page += 1
            time.sleep(1)

    def run(self, tags, max_workers=20):    # 开启 20 个线程
        """多线程运行"""
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = [executor.submit(self.crawl_tag, tag.strip()) for tag in tags if tag.strip()]
            for f in as_completed(futures):
                f.result()


# === 启动 Selenium 打开主页 ===
def init_selenium():
    options = Options()
    options.add_argument("--headless")  # 无头模式
    options.add_argument("--disable-gpu")
    options.add_argument("--no-sandbox")
    options.add_argument("--log-level=3")

    service = Service(CHROME_DRIVER_PATH)
    driver = webdriver.Chrome(service=service, options=options)

    driver.get("https://imgur.com/")
    print("🌐 Selenium 已成功访问 Imgur 主页")
    time.sleep(2)
    driver.quit()


# === 主函数入口 ===
if __name__ == "__main__":
    # 1️⃣ 启动浏览器
    init_selenium()

    # 2️⃣ 加载标签文件
    with open(TAG_FILE_PATH, 'r', encoding='utf-8') as f:
        tag_list = [line.strip() for line in f.readlines() if line.strip()]

    # 3️⃣ 启动爬虫任务
    crawler = ImgurCrawler(csv_dir_path=CSV_DIR_PATH, csv_filename="imgur_data.csv")
    crawler.run(tag_list, max_workers=20)   # 开启 20 个线程

    print("🎉 所有任务已完成！")
