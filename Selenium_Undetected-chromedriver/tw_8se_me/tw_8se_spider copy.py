import os
import re
import csv
import time
import random
import traceback
import threading
import requests
from concurrent.futures import ThreadPoolExecutor, as_completed

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC


# ---------------- 配置 ----------------
CUSTOM_BROWSER_PATH = r"C:\Program Files\Google\Chrome\Application\chrome.exe"
CHROMEDRIVER_PATH = r"C:\Program Files\Google\chromedriver-win64\chromedriver.exe"

BASE_URL = "https://xchina.fit"
MODEL_ID_FILE = r"R:\py\Auto_Image-Spider\Selenium_Undetected-chromedriver\tw_8se_me\model_id.txt"
CSV_OUTPUT_PATH = r"R:\py\Auto_Image-Spider\Selenium_Undetected-chromedriver\tw_8se_me\results.csv"
# ✅ 新增：CSV 输出目录（每个模特一个 CSV）
CSV_OUTPUT_DIR = r"R:\py\Auto_Image-Spider\Selenium_Undetected-chromedriver\tw_8se_me\csvs"
DOWNLOAD_ROOT = r"R:\py\Auto_Image-Spider\Selenium_Undetected-chromedriver\tw_8se_me\models"

PAGE_LOAD_TIMEOUT = 30
MAX_WORKERS = 10
DOWNLOAD_ENABLED = False  # ← 控制是否下载图片, 建议保持 True, 否则仅采集信息 False ！！！注意该脚本目前无法正常下载图片，仅采集信息，后续会修复该问题。如果下载图片，请将使用独立的下载脚本。
# -------------------------------------


class XChinaSpider:
    def __init__(self):
        self.csv_lock = threading.Lock()
        self.download_tasks = []
        self.executor = ThreadPoolExecutor(max_workers=MAX_WORKERS)
        self.driver = None
        self._init_driver()

    def _init_driver(self):
        """初始化 Selenium 驱动"""
        from selenium.webdriver.chrome.options import Options
        options = Options()
        options.binary_location = CUSTOM_BROWSER_PATH
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        options.add_argument("--disable-blink-features=AutomationControlled")
        service = Service(CHROMEDRIVER_PATH)
        self.driver = webdriver.Chrome(service=service, options=options)
        self.driver.implicitly_wait(5)
        print("[✔] 启动 Chrome 成功")

    # ----------------- 工具函数 -----------------
    def parse_model_file(self):
        """解析 model_id.txt 文件"""
        pairs, lines = [], []
        with open(MODEL_ID_FILE, 'r', encoding='utf-8') as f:
            for raw in f:
                line = raw.strip()
                if not line or line.startswith('#'):
                    continue
                if '#' in line:
                    line = line.split('#', 1)[0].strip()
                if line:
                    lines.append(line)
        for i in range(0, len(lines) - 1, 2):
            pairs.append((lines[i].strip(), lines[i + 1].strip()))
        print(f"[i] 共解析到 {len(pairs)} 位模特")
        return pairs

    def write_to_csv(self, title, image_name, url, model_name):
        """写入 CSV（每个 model 单独表格）"""
        try:
            with self.csv_lock:
                os.makedirs(CSV_OUTPUT_DIR, exist_ok=True)
                csv_path = os.path.join(CSV_OUTPUT_DIR, f"{self._sanitize_filename(model_name)}.csv")

                is_empty = not os.path.exists(csv_path) or os.stat(csv_path).st_size == 0

                with open(csv_path, 'a', newline='', encoding='utf-8-sig') as f:
                    writer = csv.writer(f)
                    if is_empty:
                        writer.writerow(['Title', 'ImageName', 'URL', 'ModelName'])
                    writer.writerow([title, image_name, url, model_name])
        except Exception as e:
            print(f"[✗] 写入 {model_name}.csv 出错: {e}")

    @staticmethod
    def _sanitize_filename(name):
        return re.sub(r'[\\/*?:"<>|]', '_', name)

    # ----------------- 下载部分 -----------------
    def _download_image(self, url: str, save_path: str, retries=3, timeout=15):
        """下载单张图片"""
        os.makedirs(os.path.dirname(save_path), exist_ok=True)
        if os.path.exists(save_path):
            return
        for _ in range(retries):
            try:
                r = requests.get(url, headers={'User-Agent': 'Mozilla/5.0'}, timeout=timeout)
                if r.status_code == 200 and r.content:
                    with open(save_path, 'wb') as f:
                        f.write(r.content)
                    return
            except Exception:
                time.sleep(1.5 + random.random())
        print(f"[✗] 下载失败: {url}")

    def schedule_download(self, model_name, title, image_urls):
        """添加下载任务"""
        base_dir = os.path.join(DOWNLOAD_ROOT, model_name, self._sanitize_filename(title))
        for url in image_urls:
            img_name = os.path.basename(url)
            save_path = os.path.join(base_dir, img_name)
            self.download_tasks.append(self.executor.submit(self._download_image, url, save_path))

    def wait_for_downloads(self):
        """等待下载完成"""
        if not self.download_tasks:
            return
        print(f"[⏳] 等待 {len(self.download_tasks)} 个下载任务完成...")
        for future in as_completed(self.download_tasks):
            future.result()
        print("[✔] 所有图片下载完成")

    # ----------------- 核心逻辑 -----------------
    def _try_load_model_page(self, model_id: str):
        """优先加载完整作品页（带分页）"""
        url_full = f"{BASE_URL}/photos/model-{model_id}.html"
        url_basic = f"{BASE_URL}/model/id-{model_id}.html"

        for url in [url_full, url_basic]:
            print(f"[→] 尝试加载: {url}")
            self.driver.get(url)
            try:
                WebDriverWait(self.driver, PAGE_LOAD_TIMEOUT).until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, 'div.item.photo'))
                )
                print(f"[✔] 成功加载: {url}")
                return url
            except Exception:
                print(f"[!] 页面未加载成功: {url}")
                continue
        return None

    def _parse_gallery_elements(self, model_name: str):
        """解析当前页作品列表"""
        works = self.driver.find_elements(By.CSS_SELECTOR, 'div.item.photo')
        if not works:
            return False

        for w in works:
            try:
                a_tag = w.find_element(By.CSS_SELECTOR, 'a[href^="/photo/id-"]')
                title = a_tag.get_attribute('title') or a_tag.text or 'Untitled'

                img_div = w.find_element(By.CSS_SELECTOR, 'div.img')
                style = img_div.get_attribute('style')
                m = re.search(r"url\(['\"]?(https://[^'\"]+)['\"]?\)", style)
                if not m:
                    continue
                thumb_url = m.group(1)
                base_url = thumb_url.rsplit('/', 1)[0] + "/"

                count_div = w.find_element(By.CSS_SELECTOR, 'div.tags > div')
                m2 = re.search(r"(\d+)", count_div.text)
                total = int(m2.group(1)) if m2 else 0
                if total == 0:
                    continue

                image_urls = [f"{base_url}{i:04d}.jpg" for i in range(1, total + 1)]

                # 写入 CSV
                for url in image_urls:
                    self.write_to_csv(title, os.path.basename(url), url, model_name)

                print(f"[+] {model_name} | {title} | {total} 张 ✅")

                if DOWNLOAD_ENABLED:
                    self.schedule_download(model_name, title, image_urls)
            except Exception as e:
                print(f"[✗] 解析作品失败: {e}")
                traceback.print_exc()
        return True

    def fetch_model_page_galleries_fast(self, model_id: str, model_name: str):
        """爬取所有分页作品"""
        base_url = self._try_load_model_page(model_id)
        if not base_url:
            print(f"[✗] 无法加载模特作品页: {model_id}")
            return

        # 第一页
        page = 1
        while True:
            url = base_url if page == 1 else base_url.replace('.html', f'/{page}.html')
            print(f"[→] 加载分页: {url}")
            self.driver.get(url)
            try:
                WebDriverWait(self.driver, PAGE_LOAD_TIMEOUT).until(
                    EC.presence_of_all_elements_located((By.CSS_SELECTOR, 'div.item.photo'))
                )
            except Exception:
                pass

            has_works = self._parse_gallery_elements(model_name)
            if not has_works:
                print(f"[✔] {model_name} 所有作品已加载完 (共 {page-1} 页)")
                break

            page += 1
            time.sleep(1.5 + random.random())

    # ----------------- 主流程 -----------------
    def run(self):
        models = self.parse_model_file()
        for model_id, model_name in models:
            try:
                self.fetch_model_page_galleries_fast(model_id, model_name)
            except Exception as e:
                print(f"[✗] 模特 {model_name} 出错: {e}")
        self.driver.quit()
        if DOWNLOAD_ENABLED:
            self.wait_for_downloads()
        print("[✔] 全部任务完成")


# ----------------- 启动 -----------------
if __name__ == "__main__":
    print("🔨🤖 xchina.fit 自动翻页版爬虫启动中...")
    spider = XChinaSpider()
    spider.run()
    print("任务完成 ✅")
