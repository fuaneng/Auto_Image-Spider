# -*- coding: utf-8 -*-
import os
import csv
import time
import requests
import redis
import re
from threading import Lock
from urllib.parse import urljoin
import urllib3
from bs4 import BeautifulSoup, Tag
import undetected_chromedriver as uc
from selenium.common.exceptions import WebDriverException, TimeoutException
from concurrent.futures import ThreadPoolExecutor
from queue import Queue
from typing import Optional, Set, Dict, List, Tuple

# --- 配置常量 ---
BASE_URL = 'https://en.girlstop.info/'
MODEL_NAME_FILE = r'R:\py\Auto_Image-Spider\Selenium_Undetected-chromedriver\en_girlstop_info\model_name.txt'
CSV_DIR_PATH = r'R:\py\Auto_Image-Spider\Selenium_Undetected-chromedriver\en_girlstop_info'
LOGS_SUBDIR = 'csv_logs'

ENABLE_DOWNLOAD = False
MAX_DOWNLOAD_WORKERS = 10

CUSTOM_BROWSER_PATH = r"C:\Program Files\Google\Chrome\Application\chrome.exe"
CHROMEDRIVER_PATH = r"C:\Program Files\Google\chromedriver-win64\chromedriver.exe"

REDIS_HOST = 'localhost'
REDIS_PORT = 6379
REDIS_KEY = 'girlstop_image_url_set'

CHROME_MAIN_VERSION = 142

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


class GirlstopSpider:
    """
    爬取 en.girlstop.info 网站模特作品集和图片 URL 的爬虫。
    """

    def __init__(self, csv_dir_path: str, custom_browser_path: str, redis_host: str = REDIS_HOST, redis_port: int = REDIS_PORT):
        self.csv_dir_path = csv_dir_path
        self.csv_log_path = os.path.join(self.csv_dir_path, LOGS_SUBDIR)

        self.csv_lock = Lock()
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Referer': BASE_URL
        }

        self.download_queue: Optional[Queue] = None
        self.executor: Optional[ThreadPoolExecutor] = None
        if ENABLE_DOWNLOAD:
            self.download_queue = Queue()
            self.executor = ThreadPoolExecutor(max_workers=MAX_DOWNLOAD_WORKERS)
            print(f"✅ 启用异步下载，最大线程数: {MAX_DOWNLOAD_WORKERS}")
        else:
            print("⚠️ 未启用图片下载功能。")

        print(f"🤖 初始化 undetected-chromedriver 驱动 (期望主版本: {CHROME_MAIN_VERSION})...")
        self.driver: Optional[uc.Chrome] = None
        try:
            options = uc.ChromeOptions()
            options.add_argument('--no-sandbox')
            options.add_argument('--disable-dev-shm-usage')

            # 注意：如果 Cloudflare 验证频繁，建议先注释下一行以便手动通过验证
            options.add_argument('--headless=new')

            # 使用临时 profile 目录
            options.add_argument(f'--user-data-dir={os.path.join(os.getcwd(), "temp_chrome_profile")}')

            # 尝试不同的构造签名以兼容不同 uc 版本
            got_driver = False
            # 方式1: 适用于较新版本（version_main + browser_executable_path）
            try:
                self.driver = uc.Chrome(options=options,
                                        version_main=CHROME_MAIN_VERSION,
                                        browser_executable_path=custom_browser_path)
                got_driver = True
            except TypeError:
                # 参数签名可能不被支持，继续尝试其他签名
                self.driver = None
            except Exception as e:
                # 某些版本会抛出其它异常，我们记下来并尝试备选
                print(f"  -> 尝试第一种初始化方式失败: {e}")

            if not got_driver:
                # 方式2: 尝试传入 executable_path / driver_executable_path
                try:
                    # 先试 driver_executable_path
                    self.driver = uc.Chrome(options=options,
                                            version_main=CHROME_MAIN_VERSION,
                                            driver_executable_path=CHROMEDRIVER_PATH,
                                            browser_executable_path=custom_browser_path)
                    got_driver = True
                except Exception as e:
                    print(f"  -> 尝试带 driver_executable_path 初始化失败: {e}")
                    self.driver = None

            if not got_driver:
                try:
                    # 方式3: 某些老版本使用 executable_path 直接位置参数
                    self.driver = uc.Chrome(executable_path=CHROMEDRIVER_PATH, options=options)
                    got_driver = True
                except Exception as e:
                    print(f"  -> 尝试 executable_path 初始化失败: {e}")
                    self.driver = None

            if not got_driver or not self.driver:
                raise RuntimeError("无法通过任何已知方式初始化 undetected-chromedriver，请检查 chromedriver 版本、路径和 uc 版本。")

            self.driver.set_page_load_timeout(60)
            print("✅ undetected-chromedriver 驱动初始化成功 (可能为无头模式)。")
        except Exception as e:
            print(f"❌ uc 驱动初始化失败。请检查驱动路径 ({CHROMEDRIVER_PATH}) 或浏览器路径/版本: {e}")
            print("   建议：临时注释掉 --headless=new 以手工通过 Cloudflare 验证后再恢复无头模式。")
            self.driver = None
            # 注意：不要直接 return，这样调用者可以判断 driver 是否存在
        # 去重
        self.redis: Optional[redis.StrictRedis] = None
        self.visited_urls: Set[str] = set()
        try:
            self.redis = redis.StrictRedis(host=redis_host, port=redis_port, decode_responses=True)
            self.redis.ping()
            print(f"✅ Redis 连接成功，使用 Redis 集合 ({REDIS_KEY}) 进行去重。")
        except redis.exceptions.ConnectionError as e:
            print(f"⚠️ Redis 连接失败 ({e})，将使用内存去重。")
            self.redis = None
        except Exception as e:
            print(f"⚠️ Redis 初始化遇到其他错误 ({e})，将使用内存去重。")
            self.redis = None

        # Ensure CSV log dir exists
        try:
            os.makedirs(self.csv_log_path, exist_ok=True)
            print(f"✅ CSV 日志目录准备就绪: {self.csv_log_path}")
        except Exception as e:
            print(f"⚠️ 无法创建 CSV 日志目录 {self.csv_log_path}: {e}")

    @staticmethod
    def _sanitize_filename(filename: str) -> str:
        safe_filename = re.sub(r'[\\/:*?"<>|]', '_', filename)
        safe_filename = safe_filename.strip()
        return safe_filename[:150]

    def download_worker(self, url: str, title: str, model_name: str) -> bool:
        safe_model_name = self._sanitize_filename(model_name)
        safe_title = self._sanitize_filename(title)
        save_dir = os.path.join(self.csv_dir_path, safe_model_name, safe_title)
        image_name = url.split('/')[-1]
        if '?' in image_name:
            image_name = image_name.split('?')[0]
        if not image_name:
            image_name = "default_image.jpg"
        save_path = os.path.join(save_dir, image_name)

        if os.path.exists(save_path):
            return True

        try:
            os.makedirs(save_dir, exist_ok=True)
        except Exception as e:
            print(f"[{model_name}] [✗] 创建文件夹失败 {save_dir}: {e}")
            return False

        try:
            response = requests.get(url, headers=self.headers, stream=True, verify=False, timeout=20)
            response.raise_for_status()
            with self.csv_lock:
                with open(save_path, 'wb') as f:
                    for chunk in response.iter_content(chunk_size=8192):
                        f.write(chunk)
            print(f"[{model_name}] [✓] 下载成功: {image_name} -> {os.path.join(safe_model_name, safe_title)}")
            return True
        except requests.exceptions.RequestException as e:
            print(f"[{model_name}] [✗] 下载失败: {url}, 错误: {e}")
            return False

    def is_url_visited(self, url: str) -> bool:
        """
        检查 URL 是否已被处理过。返回 True 表示已访问（不应再次写入）。
        """
        if self.redis:
            try:
                if self.redis.sismember(REDIS_KEY, url):
                    return True
                # 不存在则加入集合并返回 False（表示未访问）
                self.redis.sadd(REDIS_KEY, url)
                return False
            except Exception as e:
                print(f"⚠️ Redis 去重异常 ({e})，回退到内存去重。")
                self.redis = None  # 回退
        # 内存去重
        if url in self.visited_urls:
            return True
        self.visited_urls.add(url)
        return False

    def write_to_csv(self, title: str, url: str, model_name: str):
        """将数据写入以 model_name 命名的独立 CSV 文件，并将下载任务加入队列。"""
        if ENABLE_DOWNLOAD and self.download_queue:
            self.download_queue.put((url, title, model_name))

        safe_model_name = self._sanitize_filename(model_name)
        csv_filename = f"{safe_model_name}_results.csv"
        model_csv_path = os.path.join(self.csv_log_path, csv_filename)

        # 保证 url 是绝对 URL（方便后续使用）
        full_url = urljoin(BASE_URL, url)

        name = full_url.split('/')[-1]
        if '?' in name:
            name = name.split('?')[0]

        tag = model_name

        try:
            with self.csv_lock:
                os.makedirs(os.path.dirname(model_csv_path), exist_ok=True)
                is_file_empty = not os.path.exists(model_csv_path) or os.stat(model_csv_path).st_size == 0
                with open(model_csv_path, 'a', newline='', encoding='utf-8-sig') as f:
                    writer = csv.writer(f)
                    if is_file_empty:
                        writer.writerow(['Title', 'ImageName', 'URL', 'model_name'])
                    writer.writerow([title, name, full_url, tag])
            # 总是打印写入确认（方便调试）
            print(f"[{model_name}] [✓] 写入 CSV: {title} -> {model_csv_path}")
        except Exception as e:
            print(f"[{model_name}] [✗] 写入 CSV 出错: {e}")

    def _safe_get_url(self, url: str) -> Optional[str]:
        """
        使用 uc 驱动安全地访问 URL。
        ✅ 智能等待逻辑：首次访问等待 30 秒，之后仅等待 5 秒。
        """
        if not self.driver:
            print("⚠️ driver 未初始化，无法使用 Selenium 获取页面。")
            return None

        # 判断是否第一次访问网站（可根据 self._has_waited 标志）
        if not hasattr(self, "_has_waited"):
            self._has_waited = False

        try:
            self.driver.get(url)

            # 智能等待逻辑
            if not self._has_waited:
                wait_time = 30
                self._has_waited = True
                print(f"   -> 首次访问，等待页面加载和反爬检查 ({wait_time} 秒)...")
            else:
                wait_time = 5
                print(f"   -> 页面加载中 (等待 {wait_time} 秒)...")

            time.sleep(wait_time)

            page_title = self.driver.title or ""
            if 'just a moment' in page_title or 'Cloudflare' in page_title or 'Verify you are human' in page_title:
                print("==========================================================")
                print("⚠️ 检测到 Cloudflare 验证页面！")
                print("【建议】注释掉 `--headless=new` 手动通过一次验证后再重新运行。")
                print("==========================================================")
                time.sleep(5)

            return self.driver.page_source

        except TimeoutException:
            print(f"[{url}] 页面加载超时。")
            return None
        except WebDriverException as e:
            print(f"[{url}] 访问出错: {e}")
            return None


    def extract_details_from_page(self, detail_url: str, model_name: str, title: str):
        full_detail_url = urljoin(BASE_URL, detail_url)
        html_content = self._safe_get_url(full_detail_url)
        if not html_content:
            print(f"[{model_name}] 无法获取详情页内容: {full_detail_url}")
            return
        soup = BeautifulSoup(html_content, 'html.parser')
        image_link_tags = soup.find_all('a', class_='fullimg')
        if not image_link_tags:
            print(f"[{model_name}] [✗] 未能在详情页找到任何图片链接: {full_detail_url}")
            return
        print(f"[{model_name}] 找到 {len(image_link_tags)} 张图片链接。开始记录...")
        for link_tag in image_link_tags:
            if 'href' in link_tag.attrs:
                image_url = link_tag['href']
                # 统一转为绝对 URL
                image_url_abs = urljoin(full_detail_url, image_url)
                if not self.is_url_visited(image_url_abs):
                    self.write_to_csv(title, image_url_abs, model_name)
                else:
                    # 已访问则跳过
                    pass
            else:
                print(f"[{model_name}] [✗] 发现一个缺少 'href' 属性的链接标签。")

    def scrape_model_page(self, model_name: str):
        encoded_model_name = model_name.replace(' ', '+')
        model_url = f"{BASE_URL}models.php?name={encoded_model_name}"
        print(f"\n======== 开始爬取模特: {model_name} ========")
        print(f"访问 URL: {model_url}")

        html_content = self._safe_get_url(model_url)
        if not html_content:
            print(f"[{model_name}] 无法获取页面内容，跳过。")
            return

        soup = BeautifulSoup(html_content, 'html.parser')
        detail_link_tags = soup.select('a[href^="/psto.php?id="], a[href^="psto.php?id="]')

        unique_posts: Dict[str, str] = {}
        for link_tag in detail_link_tags:
            relative_url = link_tag.get('href')
            if not relative_url:
                continue
            current_tag: Optional[Tag] = link_tag
            thumb_div: Optional[Tag] = None
            while current_tag and current_tag.name != 'body':
                current_tag = current_tag.find_parent()
                if current_tag and current_tag.name == 'div' and 'thumb' in current_tag.get('class', []):
                    thumb_div = current_tag
                    break
            title_tag = None
            if thumb_div:
                title_tag = thumb_div.select_one('strong.post_title a')
            title = 'Unknown Title'
            if title_tag:
                title = title_tag.get_text(strip=True)
            elif link_tag.get_text(strip=True):
                title = link_tag.get_text(strip=True)
            # 放宽条件：即便标题为 Unknown 也记录
            if relative_url not in unique_posts:
                unique_posts[relative_url] = title

        if not unique_posts:
            if self.driver and 'just a moment' not in (self.driver.title or "") and 'Cloudflare' not in (self.driver.title or ""):
                print(f"[{model_name}] [✗] 未找到任何作品集链接，可能页面结构已变化或加载失败。")
            return

        print(f"[{model_name}] 找到 {len(unique_posts)} 个作品集。")
        for relative_url, title in unique_posts.items():
            if relative_url:
                self.extract_details_from_page(relative_url, model_name, title)
            else:
                print(f"[{model_name}] [✗] 发现无效作品链接/标题。")

    def run(self, model_names_file: str):
        if not self.driver:
            print("❌ 驱动未成功初始化，程序退出。请参考上方初始化错误信息。")
            return

        model_names: List[str] = []
        try:
            with open(model_names_file, 'r', encoding='utf-8') as f:
                model_names = [line.strip() for line in f if line.strip()]
        except FileNotFoundError:
            print(f"❌ 模特名称文件未找到: {model_names_file}")
            return
        except UnicodeDecodeError:
            print(f"❌ 读取文件时遇到编码错误，请确保 {model_names_file} 是 UTF-8 编码。")
            return

        if not model_names:
            print("❌ 模特名称文件为空。")
            return

        print(f"\n总共需要处理 {len(model_names)} 位模特。")

        for model_name in model_names:
            self.scrape_model_page(model_name)

        try:
            self.driver.quit()
        except Exception:
            pass
        print("\n==================================================")
        print("✅ 网页爬取和数据记录阶段完成。")

        if ENABLE_DOWNLOAD and self.download_queue and self.executor and self.download_queue.qsize() > 0:
            total_tasks = self.download_queue.qsize()
            print(f"🚀 开始异步下载，总任务数: {total_tasks}...")
            futures = []
            while not self.download_queue.empty():
                task = self.download_queue.get()
                future = self.executor.submit(self.download_worker, *task)
                futures.append(future)
            for i, future in enumerate(futures):
                try:
                    future.result()
                except Exception as e:
                    print(f"下载任务异常: {e}")
                if (i + 1) % 50 == 0 or (i + 1) == total_tasks:
                    print(f"   下载进度: {i + 1}/{total_tasks} ({((i + 1) / total_tasks) * 100:.2f}%)")
            self.executor.shutdown(wait=True)
            print("🎉 所有异步下载任务完成。")
        elif ENABLE_DOWNLOAD:
            print("⚠️ 未发现新的下载任务。")

        print("==================================================")
        print("程序全部执行完毕。")


if __name__ == '__main__':
    # 确保图片下载根目录存在
    try:
        os.makedirs(CSV_DIR_PATH, exist_ok=True)
        os.makedirs(os.path.join(CSV_DIR_PATH, LOGS_SUBDIR), exist_ok=True)
    except Exception as e:
        print(f"❌ 无法创建目录 {CSV_DIR_PATH} 或子目录: {e}")

    spider = GirlstopSpider(
        csv_dir_path=CSV_DIR_PATH,
        custom_browser_path=CUSTOM_BROWSER_PATH
    )

    if spider.driver:
        spider.run(MODEL_NAME_FILE)
    else:
        print("程序未启动（driver 未初始化）。请检查上方错误信息并修正。")
