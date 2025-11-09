import os
import re
import csv
import time
import random
import requests
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import List, Dict, Any, Set
from threading import Lock

# 导入 undetected_chromedriver
import undetected_chromedriver as uc
from selenium.webdriver.support.ui import WebDriverWait
# 忽略不安全请求警告
import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# ✅ 新增：导入 fake-useragent 库
try:
    from fake_useragent import UserAgent
    # 初始化 UserAgent 实例，它会缓存 User-Agent 列表
    UA = UserAgent()
except ImportError:
    # 如果库未安装，提供一个兜底方案
    print("[⚠️ 警告] 缺少 fake-useragent 库。请运行 pip install fake-useragent")
    class UserAgentFallback:
        def random(self):
            return 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/100.0.4896.127 Safari/537.36'
    UA = UserAgentFallback()


# ---------------- 配置 ----------------
CUSTOM_BROWSER_PATH = r"C:\Program Files\Google\Chrome\Application\chrome.exe"
CSV_OUTPUT_DIR = r"R:\py\Auto_Image-Spider\Selenium_Undetected-chromedriver\tw_8se_me\csvs"
DOWNLOAD_ROOT = r"R:\py\Auto_Image-Spider\Selenium_Undetected-chromedriver\tw_8se_me\models"

BASE_URL = "https://xchina.fit" 

# 指定要下载的 CSV 文件列表
TARGET_CSV_FILENAMES: List[str] = ['年年.csv'] 

# 每个 CSV 文件限制处理的相册数量（Title）无限制设置为 -1
ALBUM_LIMIT_PER_CSV = -1 

# 调整后的限速配置
MAX_DOWNLOAD_WORKERS = 5 
DOWNLOAD_RETRIES = 5
MIN_DELAY_BETWEEN_REQUESTS = 1.0
MAX_DELAY_BETWEEN_REQUESTS = 3.0
# -------------------------------------

# 全局线程锁，用于文件系统操作和全局计数器
file_lock = Lock()


class XChinaDownloader:
    def __init__(self):
        self.executor = ThreadPoolExecutor(max_workers=MAX_DOWNLOAD_WORKERS)
        self.download_tasks: List[Dict[str, str]] = []
        self.driver = None
        self.session_cookies: Dict[str, str] = {} 
        self.download_count = 0
        self.failed_downloads = 0
        self._init_driver_and_session()

    def _init_driver_and_session(self):
        """
        初始化 Undetected-Chromedriver 并获取会话 Cookie
        """
        print("[i] 正在初始化 Undetected-Chromedriver...")
        
        options = uc.ChromeOptions()
        if CUSTOM_BROWSER_PATH:
            options.binary_location = CUSTOM_BROWSER_PATH
            
        options.add_argument('--headless') 
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        options.add_argument("--window-size=1920,1080")

        try:
            self.driver = uc.Chrome(options=options)
            print("[✔] 启动 Undetected Chrome 成功")

            print(f"[→] 访问主页获取 Session Cookie: {BASE_URL}")
            self.driver.get(BASE_URL)
            
            WebDriverWait(self.driver, 15).until(
                lambda driver: driver.execute_script("return document.readyState") == "complete"
            )
            
            cookies = self.driver.get_cookies()
            self.session_cookies = {c['name']: c['value'] for c in cookies}
            print(f"[✔] 成功获取 {len(self.session_cookies)} 个会话 Cookie")

        except Exception as e:
            print(f"[✗] 启动或获取 Cookie 失败: {e}")
            if self.driver: self.driver.quit()
            raise

    # ----------------- 工具函数 (保持不变) -----------------
    @staticmethod
    def _sanitize_filename(name):
        """清理文件名中的非法字符"""
        return re.sub(r'[\\/*?:"<>|]', '_', name)

    def _get_all_urls_from_csv(self) -> List[Dict[str, str]]:
        # ... (CSV 读取和限制逻辑保持不变) ...
        print(f"[i] 正在从目录 {CSV_OUTPUT_DIR} 读取 URL...")
        all_tasks: List[Dict[str, str]] = []
        
        if not os.path.exists(CSV_OUTPUT_DIR):
            print(f"[✗] 错误: CSV 目录不存在: {CSV_OUTPUT_DIR}")
            return []

        file_list = os.listdir(CSV_OUTPUT_DIR)
        
        if TARGET_CSV_FILENAMES:
            file_list = [f for f in file_list if f in TARGET_CSV_FILENAMES]
            print(f"[i] 已过滤，将处理 {len(file_list)} 个目标 CSV 文件。")
        else:
            file_list = [f for f in file_list if f.endswith('.csv')]
            print(f"[i] 未指定目标，将处理目录下所有 {len(file_list)} 个 CSV 文件。")


        for filename in file_list:
            if not filename.endswith('.csv'):
                continue
            
            model_name = self._sanitize_filename(os.path.splitext(filename)[0])
            csv_path = os.path.join(CSV_OUTPUT_DIR, filename)
            
            albums_processed: Set[str] = set()
            
            print(f"[→] 处理文件: {filename} (限制相册数: {ALBUM_LIMIT_PER_CSV if ALBUM_LIMIT_PER_CSV > 0 else '无限制'})")
            
            with open(csv_path, 'r', encoding='utf-8-sig') as f:
                reader = csv.reader(f)
                try:
                    header = next(reader) # 读取标题行
                    url_idx = header.index('URL')
                    title_idx = header.index('Title')
                except (StopIteration, ValueError):
                    print(f"[✗] 错误: CSV 文件 {filename} 格式不正确或为空。")
                    continue
                    
                for row in reader:
                    if len(row) > max(url_idx, title_idx):
                        title = row[title_idx]
                        
                        if ALBUM_LIMIT_PER_CSV > 0:
                            if len(albums_processed) >= ALBUM_LIMIT_PER_CSV and title not in albums_processed:
                                continue 
                        
                        albums_processed.add(title)
                        
                        all_tasks.append({
                            'url': row[url_idx],
                            'title': title,
                            'model_name': model_name
                        })
                        
            print(f"[i] 文件 {filename} 采集了 {len(albums_processed)} 个相册的任务。")

        print(f"[i] 共加载 {len(all_tasks)} 个下载任务")
        return all_tasks

    # ----------------- 下载部分 -----------------
    def _download_image(self, task: Dict[str, str]):
        """
        使用 requests 携带浏览器获取的 Cookie 下载图片，并引入延迟。
        """
        # 引入随机延迟
        delay = random.uniform(MIN_DELAY_BETWEEN_REQUESTS, MAX_DELAY_BETWEEN_REQUESTS)
        time.sleep(delay)
        
        url = task['url']
        model_name = task['model_name']
        title = task['title']
        
        img_name = os.path.basename(url)
        base_dir = os.path.join(DOWNLOAD_ROOT, self._sanitize_filename(model_name), self._sanitize_filename(title))
        save_path = os.path.join(base_dir, img_name)
        
        with file_lock:
            os.makedirs(base_dir, exist_ok=True)
            if os.path.exists(save_path):
                return 

        # 🚀 关键修改：使用 fake-useragent 动态生成 User-Agent
        headers = {
            'User-Agent': UA.random, # <-- 从库中获取随机 UA
            'Referer': BASE_URL, 
        }

        for attempt in range(DOWNLOAD_RETRIES):
            try:
                r = requests.get(
                    url, 
                    headers=headers, 
                    cookies=self.session_cookies, 
                    timeout=20, 
                    stream=True, 
                    verify=False 
                )
                
                if r.status_code == 200:
                    with open(save_path, 'wb') as f:
                        for chunk in r.iter_content(chunk_size=8192):
                            if chunk:
                                f.write(chunk)
                    with file_lock:
                        self.download_count += 1
                    return

                elif r.status_code == 403:
                    time.sleep(3 + random.random() * 2)
                    
                elif r.status_code == 429: 
                    print(f"[⚠️ 限速] 收到 429，休眠 30-60 秒后重试: {url}")
                    time.sleep(random.uniform(30, 60))
                    # 切换新的 User-Agent 以进行下一次重试
                    headers['User-Agent'] = UA.random
                    continue
                    
                else:
                    time.sleep(2 + random.random())
                    
            except requests.exceptions.RequestException as e:
                time.sleep(2 + random.random())
                
        # 所有重试失败
        print(f"[✗ 下载失败] 最终失败: {model_name} | {img_name} | URL: {url}")
        with file_lock:
            self.failed_downloads += 1


    # ----------------- 主执行流程 (保持不变) -----------------
    def run(self):
        """主执行流程"""
        all_tasks = self._get_all_urls_from_csv()
        
        if not all_tasks:
            print("[i] 没有下载任务，程序结束。")
            return

        print(f"\n[⏳] 开始多线程下载 {len(all_tasks)} 张图片，使用 {MAX_DOWNLOAD_WORKERS} 个线程...")
        
        futures = [self.executor.submit(self._download_image, task) for task in all_tasks]
        
        total = len(futures)
        for i, future in enumerate(as_completed(futures)):
            if (i + 1) % 100 == 0 or (i + 1) == total:
                with file_lock:
                    print(f"[进度] 已完成 {i + 1}/{total} 个任务. 成功: {self.download_count}, 失败: {self.failed_downloads}")
            try:
                future.result()
            except Exception as e:
                pass

        self.executor.shutdown(wait=True)
        
        if self.driver:
            self.driver.quit()
            
        print("\n[✔] 所有下载任务完成")
        print(f"统计：总任务数: {total}, 成功: {self.download_count}, 失败: {self.failed_downloads}")


# ----------------- 启动 -----------------
if __name__ == "__main__":
    print("🔨🤖 xchina.fit 独立下载器启动中 (基于 Undetected-Chromedriver Cookie + 随机 UA)...")
    try:
        downloader = XChinaDownloader()
        downloader.run()
    except Exception as e:
        print(f"[致命错误] 下载器启动失败或运行中断: {e}")
    print("任务完成 ✅")
