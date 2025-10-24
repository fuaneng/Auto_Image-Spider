import os
import time
import hashlib
import redis
import csv
import threading
import random
import re
import urllib.parse
from queue import Queue
from typing import List, Optional

# --- Selenium 导入 ---
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
from selenium.common.exceptions import TimeoutException, NoSuchElementException, WebDriverException

# ====================================================================
# 1. 爬虫类 (解耦)
# ====================================================================

class ArtStationSpider:
    """
    一个独立的 ArtStation 爬虫实例，负责管理自己的 Selenium 浏览器
    并处理单个标签的爬取任务。
    """

    def __init__(self, chrome_driver_path: str, csv_path: str, csv_lock: threading.Lock, redis_conn: Optional[redis.Redis]):
        """
        初始化 Spider，创建独立的 Chrome 驱动实例。

        Args:
            chrome_driver_path: Chrome Driver 的可执行文件路径。
            csv_path: 记录爬取结果的 CSV 文件路径。
            csv_lock: 用于并发写入 CSV 的线程锁。
            redis_conn: Redis 连接实例 (可能为 None)。
        """
        print(f"[{threading.current_thread().name}] 正在启动 Chrome 浏览器...")
        service = Service(executable_path=chrome_driver_path)
        options = Options()
        options.add_experimental_option("excludeSwitches", ["enable-automation"])
        options.add_experimental_option('useAutomationExtension', False)
        options.add_argument(
            f'user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/{random.randint(90, 105)}.0.{random.randint(4400, 4800)}.124 Safari/537.36')
        options.add_argument("--window-size=1920,1080")
        # options.add_argument("--headless")  # 可在调试完成后开启

        try:
            self.driver = webdriver.Chrome(service=service, options=options)
            print(f"[{threading.current_thread().name}] Chrome 启动成功。")
        except WebDriverException as e:
            print(f"[{threading.current_thread().name}] ❌ Chrome 启动失败: {e}")
            self.driver = None
            raise

        self.base_url = 'https://www.artstation.com/'
        self.csv_lock = csv_lock
        self.csv_path = csv_path
        self.redis = redis_conn
        self.redis_key = 'image_md5_set_artstation'
        self.visited_md5 = set() if not self.redis else None

        # 顶级图片容器选择器（主页面）
        self.main_container_selector = (
            "div.gallery-grid.ng-trigger.ng-trigger-animateBlocks.size-small"
        )
        self.card_selector = "projects-list-item.gallery-grid-item a.gallery-grid-link"


    # ---------------------- 滚动加载并提取搜索页卡片 ----------------------
    def get_images(self, tag: str):
        """
        处理单个标签的搜索页面，进行滚动加载并提取卡片链接。
        """
        thread_name = threading.current_thread().name
        print(f"[{thread_name}] --- 正在解析【{tag}】的图片列表...")

        wait = WebDriverWait(self.driver, 30)
        try:
            wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, self.main_container_selector)))
            print(f"[{thread_name}] [√] 主图片容器加载完成。")
        except TimeoutException:
            print(f"[{thread_name}] [✗] 页面加载超时。")
            return

        # === 分步滚动加载 ===
        SCROLL_STEP = 1080
        SCROLL_PAUSE = 2.5
        last_height = self.driver.execute_script("return document.body.scrollHeight")

        print(f"[{thread_name}] 🚀 开始滚动加载更多内容...")
        # 滚动 5 次为例，防止无限滚动，可根据需要调整
        for i in range(5):
            self.driver.execute_script("window.scrollBy(0, arguments[0]);", SCROLL_STEP)
            time.sleep(SCROLL_PAUSE + random.random() * 1.5)

            new_height = self.driver.execute_script("return document.body.scrollHeight")
            if new_height == last_height:
                print(f"[{thread_name}] ✅ 滚动到底部（第 {i+1} 次）。")
                break
            last_height = new_height

        cards = self.driver.find_elements(By.CSS_SELECTOR, self.card_selector)
        print(f"[{thread_name}] 🖼️ 检测到 {len(cards)} 个卡片链接。")

        for idx, card in enumerate(cards, start=1):
            try:
                href = card.get_attribute("href")
                # 尝试获取图片元素的 alt 属性作为标题
                title = card.find_element(By.CSS_SELECTOR, "img.d-block.gallery-grid-background-image").get_attribute("alt")

                # print(f"[{thread_name}] [{idx}/{len(cards)}] 🧭 {title} | {href}")

                if not href or not href.startswith("https://www.artstation.com/artwork/"):
                    continue

                # 打开详情页，使用 execute_script 在新标签页打开
                self.driver.execute_script("window.open(arguments[0]);", href)
                self.driver.switch_to.window(self.driver.window_handles[-1])

                time.sleep(random.uniform(1.2, 2.5))
                self.extract_detail_page(tag)

                self.driver.close()
                self.driver.switch_to.window(self.driver.window_handles[0])

            except Exception as e:
                print(f"[{thread_name}] [✗] 打开或解析卡片出错: {e}")
                # 确保关闭可能打开的新窗口
                if len(self.driver.window_handles) > 1:
                    self.driver.close()
                    self.driver.switch_to.window(self.driver.window_handles[0])
                continue

    # ---------------------- 详情页提取 ----------------------
    def extract_detail_page(self, tag: str):
        """
        从当前详情页提取图片 URL 和信息。
        """
        thread_name = threading.current_thread().name
        wait = WebDriverWait(self.driver, 20)
        try:
            wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "main.project-assets")))
        except TimeoutException:
            print(f"[{thread_name}] ❌ 详情页加载失败。")
            return

        try:
            # 查找图片容器
            picture_eles = self.driver.find_elements(By.CSS_SELECTOR, "main.project-assets picture.d-flex")
            print(f"[{thread_name}] 📷 详情页检测到 {len(picture_eles)} 张图片。")

            for pic in picture_eles:
                try:
                    # 查找具体的 img 标签
                    img_ele = pic.find_element(By.CSS_SELECTOR, "img.img.img-fluid.block-center.img-fit")
                    image_url = img_ele.get_attribute("src")
                    # 尝试从 img 的 alt 属性获取标题，或从页面其他位置获取
                    title = img_ele.get_attribute("alt") or self.driver.title.split(' - ')[0] or "未命名"

                    if not image_url:
                        continue

                    # 清理 URL 以计算 MD5
                    image_url_cleaned = re.sub(r'\?.*$', '', image_url)
                    md5_hash = hashlib.md5(image_url_cleaned.encode('utf-8')).hexdigest()

                    if self.is_duplicate(md5_hash):
                        # print(f"[{thread_name}] [重复] 跳过：{title}")
                        continue

                    image_name = os.path.basename(image_url_cleaned)
                    self.write_to_csv(title, image_name, image_url_cleaned, tag)
                    print(f"[{thread_name}] ✔️ 保存成功：{title}")

                except NoSuchElementException:
                    continue
        except Exception as e:
            print(f"[{thread_name}] [✗] 提取详情页图片出错: {e}")

    # ---------------------- 去重逻辑 (线程安全) ----------------------
    def is_duplicate(self, md5_hash: str) -> bool:
        """
        检查 MD5 是否已存在，并进行记录。
        """
        if self.redis:
            # Redis 是线程安全的，直接操作
            if self.redis.sismember(self.redis_key, md5_hash):
                return True
            self.redis.sadd(self.redis_key, md5_hash)
        elif self.visited_md5 is not None:
            # 如果没有 Redis，使用内存集合，但多线程下这个集合会有数据竞争问题
            # ⚠️ 理论上此处的内存去重在多线程下不够安全，但为保持原有逻辑结构，仅作为备用。
            # 实际生产应使用 Redis 或其他线程安全机制。
            if md5_hash in self.visited_md5:
                return True
            self.visited_md5.add(md5_hash)
        return False

    # ---------------------- 写入 CSV (线程安全) ----------------------
    def write_to_csv(self, title: str, name: str, url: str, tag: str):
        """
        使用锁确保线程安全地写入 CSV 文件。
        """
        try:
            with self.csv_lock:
                is_file_empty = not os.path.exists(self.csv_path) or os.stat(self.csv_path).st_size == 0
                with open(self.csv_path, 'a', newline='', encoding='utf-8-sig') as f:
                    writer = csv.writer(f)
                    if is_file_empty:
                        writer.writerow(['Title', 'ImageName', 'URL', 'Tag'])
                    writer.writerow([title, name, url, tag])
        except Exception as e:
            print(f"[{threading.current_thread().name}] [✗] 写入 CSV 出错: {e}")

    # ---------------------- 关闭浏览器 ----------------------
    def close(self):
        """
        关闭 Selenium 实例。
        """
        if self.driver:
            print(f"[{threading.current_thread().name}] 🔚 正在关闭浏览器...")
            self.driver.quit()

# ====================================================================
# 2. 线程工作函数
# ====================================================================

def spider_worker(tag_queue: Queue, chrome_driver_path: str, csv_path: str, csv_lock: threading.Lock, redis_conn: Optional[redis.Redis]):
    """
    线程的工作函数。每个线程将创建一个 ArtStationSpider 实例，并从队列中持续获取标签进行爬取。
    """
    spider: Optional[ArtStationSpider] = None
    try:
        # 1. 初始化独立的 Selenium 实例
        spider = ArtStationSpider(chrome_driver_path, csv_path, csv_lock, redis_conn)

        # 2. 从队列中循环获取标签，直到队列为空
        while not tag_queue.empty():
            tag = tag_queue.get()
            try:
                # 构造搜索 URL
                encoded_tag = urllib.parse.quote_plus(tag)
                search_url = f"{spider.base_url}search?sort_by=relevance&query={encoded_tag}"
                
                print(f"\n[{threading.current_thread().name}] === 开始处理：【{tag}】 ===\nURL: {search_url}")
                
                # 访问搜索页
                spider.driver.get(search_url)
                time.sleep(random.uniform(2, 4))

                # 开始爬取
                spider.get_images(tag)

            except WebDriverException as e:
                print(f"[{threading.current_thread().name}] [致命错误] WebDriver 内部出错，跳过当前标签: {e}")
            except Exception as e:
                print(f"[{threading.current_thread().name}] [✗] 处理标签 {tag} 出错: {e}")
            finally:
                tag_queue.task_done() # 通知队列任务完成
                
    except Exception as e:
        print(f"[{threading.current_thread().name}] [致命错误] 线程初始化或主循环出错: {e}")
    finally:
        # 3. 线程结束时关闭浏览器
        if spider:
            spider.close()

# ====================================================================
# 3. 主程序入口 (管理多线程)
# ====================================================================

if __name__ == '__main__':
    # --- 配置项 ---
    CHROME_DRIVER_PATH = r'C:\Program Files\Google\chromedriver-win32\chromedriver.exe'
    SAVE_DIR = r'D:\work\爬虫\爬虫数据\artstation'
    TAG_FILE_PATH = r'D:\work\爬虫\ram_tag_list_备份.txt'
    MAX_WORKERS = 3  # 默认开启 3 个线程/Selenium 实例

    # --- 初始化资源 ---
    os.makedirs(SAVE_DIR, exist_ok=True)
    CSV_PATH = os.path.join(SAVE_DIR, 'all_records_artstation_async.csv')
    CSV_LOCK = threading.Lock()
    TAG_QUEUE: Queue[str] = Queue()
    
    # 初始化 Redis
    REDIS_CONN: Optional[redis.Redis] = None
    try:
        REDIS_CONN = redis.Redis(host='localhost', port=6379, db=0, decode_responses=True)
        REDIS_CONN.ping()
        print("✅ Redis 连接成功，启用 Redis 去重。")
    except Exception:
        print("⚠️ Redis 不可用，使用内存去重（多线程下不够安全）。")

    # 1. 读取标签文件并放入队列
    try:
        with open(TAG_FILE_PATH, 'r', encoding='utf-8') as f:
            tags = [line.strip() for line in f if line.strip()]
            for tag in tags:
                TAG_QUEUE.put(tag)
    except FileNotFoundError:
        print(f"[错误] 未找到标签文件: {TAG_FILE_PATH}")
        exit()

    print(f"--- 发现 {TAG_QUEUE.qsize()} 个标签，将启动 {MAX_WORKERS} 个爬虫线程 ---")
    
    # 2. 启动爬虫线程
    threads: List[threading.Thread] = []
    try:
        for i in range(MAX_WORKERS):
            thread_name = f"SpiderWorker-{i+1}"
            thread = threading.Thread(
                target=spider_worker,
                args=(TAG_QUEUE, CHROME_DRIVER_PATH, CSV_PATH, CSV_LOCK, REDIS_CONN),
                name=thread_name
            )
            thread.start()
            threads.append(thread)
            print(f"主线程：已启动 {thread_name}")

        # 3. 等待队列所有任务完成
        TAG_QUEUE.join()
        
        print("\n✅ 所有标签任务已完成。等待线程退出...")
        
        # 4. 等待所有线程结束
        for thread in threads:
            thread.join()

    except Exception as main_e:
        print(f"主程序运行出错: {main_e}")
        
    print("\n🎯 异步多实例爬取流程全部结束。")