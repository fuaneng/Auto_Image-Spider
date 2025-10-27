import hashlib
import json
import os
import random
import re
import threading
import time
from typing import Any, Dict, List, Tuple
from queue import Queue

import redis
import csv
from selenium import webdriver
from selenium.common.exceptions import (NoSuchElementException, TimeoutException,
                                        WebDriverException)
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

# --- 全局共享配置和锁（用于解耦） ---
# 请修改为你的实际路径
CHROME_DRIVER_PATH = r'C:\Program Files\Google\chromedriver-win64\chromedriver.exe'
SAVE_PATH_ALL = r'D:\myproject\Code\爬虫\爬虫数据\creativemarket'
TAG_FILE_PATH = r"D:\myproject\Code\爬虫\爬虫数据\creativemarket\ram_tag_list_备份.txt"
CSV_PATH = os.path.join(SAVE_PATH_ALL, 'all_records_multithread.csv')
MAX_THREADS = 20  # 设置最大线程数

# Redis 配置 (所有线程共享)
REDIS_HOST = 'localhost'
REDIS_PORT = 6379
REDIS_DB = 0
REDIS_KEY = 'image_md5_set_creativemarket'
SHARED_REDIS_CLIENT = redis.Redis(host=REDIS_HOST, port=REDIS_PORT, db=REDIS_DB, decode_responses=True)

# 线程安全的 CSV 写入锁 (所有线程共享)
CSV_LOCK = threading.Lock()
# 标签任务队列 (所有线程共享)
TAG_QUEUE = Queue()

class creativemarket:
    """
    负责单个 Selenium 实例的初始化和单个标签（Tag）的爬取。
    每个线程将创建一个此类的独立实例。
    """
    def __init__(self, chrome_driver_path: str):
        """
        初始化爬虫类。每个实例拥有独立的 WebDriver。
        """
        self.driver = None
        self.base_url = 'https://creativemarket.com/search/'
        
        # 共享资源，直接使用全局变量
        self.redis = SHARED_REDIS_CLIENT
        self.redis_key = REDIS_KEY
        self.csv_lock = CSV_LOCK
        
        try:
            service = Service(executable_path=chrome_driver_path)
        except Exception as e:
            print(f"[错误] ChromeDriver 路径错误或服务启动失败: {e}")
            return
            
        options = Options()
        # 1. 启用性能日志，以便获取网络请求信息
        options.set_capability('goog:loggingPrefs', {'performance': 'ALL'})
        
        # 常见反爬配置
        options.add_experimental_option("excludeSwitches", ["enable-automation"])
        options.add_experimental_option('useAutomationExtension', False)
        options.add_argument("--headless") 
            
        # 性能和稳定性配置
        options.add_argument('--disable-gpu')
        options.add_argument("--window-size=1920,1080")
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")

        user_agent = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        options.add_argument(f'user-agent={user_agent}')
        
        try:
            self.driver = webdriver.Chrome(service=service, options=options)
            self.driver.set_page_load_timeout(30)
            print(f"[√] Thread-{threading.get_ident()} WebDriver 初始化成功。")
            
        except WebDriverException as e:
            print(f"[致命错误] Thread-{threading.get_ident()} WebDriver 启动失败: {e}")
            self.driver = None

    # --- 数据提取和网络监听方法 (_get_xhr_json_with_f_nw_r, _extract_base64_paths, _build_url_map_from_json) ---
    # 注：这些方法保持不变，因为它们只依赖于 self.driver，而每个线程都有自己的 driver。
    
    def _get_xhr_json_with_f_nw_r(self) -> str:
        """ 读取 Performance 日志，解析所有请求 ID，并循环获取响应体，直到找到包含 'f-nw-r' 键的 JSON。 """
        # ... (此方法保持不变)
        requests_info = {}

        try:
            time.sleep(1) 
            logs = self.driver.get_log('performance')
        except Exception as e:
            print(f"[✗] Thread-{threading.get_ident()} 无法获取 Performance 日日志: {e}")
            return ""

        for log_entry in logs:
            try:
                message_data = json.loads(log_entry['message'])
                message = message_data['message']
                method = message.get('method')
                params = message.get('params')
                request_id = params.get('requestId')
                
                if not request_id:
                    continue
                
                if method == 'Network.responseReceived':
                    response = params.get('response')
                    if response and response['mimeType'] in ['application/json', 'text/plain', 'text/html']: 
                        requests_info[request_id] = {'loaded': False, 'url': response['url']}
                        
                elif method == 'Network.loadingFinished' and request_id in requests_info:
                    requests_info[request_id]['loaded'] = True

            except Exception:
                continue
        
        if not requests_info:
            return ""

        for request_id, info in requests_info.items():
            if info['loaded']:
                try:
                    response = self.driver.execute_cdp_cmd(
                        'Network.getResponseBody', 
                        {'requestId': request_id}
                    )
                    
                    body = response['body']
                    
                    if '"f-nw-r":' in body and body.strip().startswith('{'):
                        print(f"[√] Thread-{threading.get_ident()} 成功捕获目标 JSON 响应！URL: {info['url'][:80]}...")
                        
                        if response.get('base64Encoded'):
                            import base64
                            return base64.b64decode(body).decode('utf-8', errors='ignore')
                        return body
                        
                except Exception:
                    continue
        
        print(f"[✗] Thread-{threading.get_ident()} 未找到包含 \"f-nw-r\": 键的 JSON 文本。")
        return ""


    def _extract_base64_paths(self) -> List[Tuple[str, str, str]]:
        """ 从产品卡片 div 的 data-title 属性中提取标题和 Base64 路径。 """
        # ... (此方法保持不变)
        paths = []
        product_cards = self.driver.find_elements(By.CSS_SELECTOR, 'div[data-test="sp-product-card"]')
        base64_regex = re.compile(r'/(czM6Ly9maWxlcy\S+)')
        
        for card in product_cards:
            title = card.get_attribute('data-title')
            src = card.get_attribute('data-src-retina')
            
            if src:
                match = base64_regex.search(src)
                if match:
                    base64_path = match.group(1).split('?')[0]
                    final_title = title.strip() if title else "N/A" # 确保标题存在
                    
                    if final_title == "N/A":
                        # print(f"[WARN] 发现 Base64 路径 {base64_path[:10]}... 但标题为空，使用 'N/A'。")
                        pass
                    
                    paths.append((final_title, base64_path, src))
            
        print(f"[√] Thread-{threading.get_ident()} 从 {len(product_cards)} 个产品卡片中提取了 {len(paths)} 个 Base64 路径和标题。")
        return paths

    def _build_url_map_from_json(self, data: Any) -> Dict[str, str]:
        """ 递归遍历解析后的 JSON 数据(字典)，找到所有 'f-nw-r' URL，并映射到其对应的 Base64 路径指纹。 """
        # ... (此方法保持不变)
        url_map = {}
        base64_regex = re.compile(r'(czM6Ly9maWxlcy[^\?]+)')

        def recursive_search(item):
            if isinstance(item, dict):
                if 'f-nw-r' in item and isinstance(item['f-nw-r'], str):
                    f_nw_r_url = item['f-nw-r']
                    
                    match = base64_regex.search(f_nw_r_url)
                    if match:
                        base64_path = match.group(1)
                        cleaned_url = f_nw_r_url.replace('\\/', '/')
                        url_map[base64_path] = cleaned_url
                
                for value in item.values():
                    recursive_search(value)

            elif isinstance(item, list):
                for element in item:
                    recursive_search(element)

        recursive_search(data)
        return url_map
    
    # --- 主要爬取逻辑 (保持不变) ---
    def get_images(self, tag: str, csv_path: str):
        """ 
        执行滚动加载，提取 Base64 路径，然后从网络 JSON 响应中匹配 f-nw-r 链接。
        """
        thread_id = threading.get_ident()
        print(f"--- Thread-{thread_id} 正在解析标签【{tag}】的图片列表...")

        image_card_selector = 'div[data-test="sp-product-card"]' 
        
        # 步骤 1: 滚动加载
        last_count = -1
        scroll_count = 0
        while True:
            image_elements = self.driver.find_elements(By.CSS_SELECTOR, image_card_selector)
            current_count = len(image_elements)
            
            if current_count == last_count and current_count > 0:
                print(f"[√] Thread-{thread_id} 页面所有产品 ({current_count} 个) 已加载完毕。")
                break
            if current_count == 0 and last_count == -1:
                # 页面可能真的没有产品
                break
            
            if current_count > 0:
                self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
                print(f"Thread-{thread_id} 滚动加载，当前找到 {current_count} 个产品...")
                scroll_count += 1
            
            last_count = current_count
            time.sleep(random.uniform(2.0, 4.0))
            
            # 安全限制，防止无限滚动
            if scroll_count > 100:
                 print(f"[WARN] Thread-{thread_id} 滚动次数过多 ({scroll_count} 次)，可能遇到加载问题，停止滚动。")
                 break

        if last_count == 0:
            print(f"Thread-{thread_id} 当前页面没有找到图片元素，跳过。")
            return


        # 步骤 2, 3, 4, 5: 提取、匹配和写入
        base64_paths_and_titles = self._extract_base64_paths()
        if not base64_paths_and_titles:
            print(f"[✗] Thread-{thread_id} 未能从 DOM 中提取任何 Base64 路径。")
            return

        full_json_str = self._get_xhr_json_with_f_nw_r()
        if not full_json_str:
            print(f"[✗] Thread-{thread_id} 无法通过网络日志获取目标 JSON 字符串，跳过本页解析。")
            return
        
        try:
            json_data = json.loads(full_json_str)
        except json.JSONDecodeError:
            print(f"[✗] Thread-{thread_id} 解析捕获的 JSON 字符串失败，跳过本页。")
            return

        url_lookup_map = self._build_url_map_from_json(json_data)
        if not url_lookup_map:
            print(f"[✗] Thread-{thread_id} 未能从 JSON 数据中构建任何 URL 映射，无法继续匹配。")
            return
        print(f"[√] Thread-{thread_id} URL 查找表构建完成，包含 {len(url_lookup_map)} 个条目。")
            
        successful_matches = 0
        for title, base64_path, src_url in base64_paths_and_titles:
            try:
                original_url = url_lookup_map.get(base64_path)
                
                if original_url:
                    # 使用 Title 和 URL MD5 来生成唯一的哈希
                    md5_hash = hashlib.md5(original_url.encode('utf-8')).hexdigest()
                    image_name = f"{title[:30].strip()}-{md5_hash[:6]}" 
                    
                    if not self.redis.sismember(self.redis_key, md5_hash):
                        self.redis.sadd(self.redis_key, md5_hash)
                        self.write_to_csv(title, image_name, original_url, csv_path, tag)
                        successful_matches += 1
                        # print(f"[匹配成功] Thread-{thread_id} 标题: {title[:20]}... | 名称: {image_name} | URL: {original_url}")
                    # else:
                    #     print(f"[跳过] Thread-{thread_id} URL已存在: {title[:20]}...")
                # else:
                #     print(f"[FAIL] Thread-{thread_id} 匹配失败: 标题: {title[:20]}... | 无法在JSON数据中找到指纹: {base64_path}")

            except Exception as e:
                print(f"[ERROR] Thread-{thread_id} 匹配或写入时发生异常: {e}")
                continue 

        print(f"[√] Thread-{thread_id} 标签【{tag}】本页成功写入 {successful_matches} 条新记录到 CSV。")


    # --- 辅助方法：CSV 写入和翻页逻辑 (基本不变) ---
    def write_to_csv(self, title, name, url, csv_path, tag):
        """将图片信息写入 CSV 文件 (包含 Title, ImageName, Original_URL, TAG)，使用全局锁。"""
        try:
            with self.csv_lock: # 使用共享的 CSV 锁
                file_exists = os.path.exists(csv_path)
                
                with open(csv_path, 'a', newline='', encoding='utf-8-sig') as f:
                    writer = csv.writer(f)
                    if not file_exists or f.tell() == 0:
                        writer.writerow(['Title', 'ImageName', 'Original_URL', "TAG"])
                    writer.writerow([title, name, url, tag])
                    f.flush()
        except Exception as e:
            print(f'[✗] Thread-{threading.get_ident()} 写入 CSV 异常：{name} -> {e}')


    def crawl_page(self, tag: str, csv_path: str):
        """
        爬取单个标签的全部页面。
        """
        thread_id = threading.get_ident()
        next_page_selector = 'a.sp-pagination--next'
        image_card_selector = 'div.search__results' 
        current_page_num = 1
        wait = WebDriverWait(self.driver, 20)
        
        # 导航到搜索 URL
        search_url = f'{self.base_url}{tag}?categoryIDs=6'
        print(f"Thread-{thread_id} 正在访问: {search_url}")
        self.driver.get(search_url)
        time.sleep(random.uniform(3.0, 5.0))
        
        while True:
            print(f"\n==== Thread-{thread_id} 开始爬取标签【{tag}】第 {current_page_num} 页 ====")
            self.get_images(tag, csv_path)
            
            try:
                # 检查下一页按钮
                next_button = wait.until(
                    EC.element_to_be_clickable((By.CSS_SELECTOR, next_page_selector))
                )
                if not next_button.get_attribute('href'):
                    raise NoSuchElementException("Next button has no valid link.")
                
                print(f"[INFO] Thread-{thread_id} 找到下一页按钮，准备使用 JS 翻页到第 {current_page_num + 1} 页...")
                self.driver.execute_script("arguments[0].click();", next_button)
                current_page_num += 1
                
                # 等待新页面加载稳定
                wait.until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, image_card_selector))
                )
                print(f"Thread-{thread_id} 新页面加载稳定，检测到图片容器。")
                time.sleep(random.uniform(2.0, 4.0)) 
                
            except (TimeoutException, NoSuchElementException):
                print(f"[完成] Thread-{thread_id} 标签【{tag}】已爬取到最后一页 (第 {current_page_num} 页或找不到下一页按钮)。")
                return True 
            except Exception as e:
                print(f"[✗] Thread-{thread_id} 翻页时发生错误: {e}")
                return False

    def close(self):
        """关闭 WebDriver 实例。"""
        if self.driver:
            try:
                self.driver.quit()
                print(f"[关闭] Thread-{threading.get_ident()} WebDriver 已安全关闭。")
            except Exception:
                pass


def worker_task(tag_queue: Queue, chrome_driver_path: str, csv_path: str):
    """
    单个线程的执行函数。从队列中取出任务（tag）并执行爬取。
    """
    thread_id = threading.get_ident()
    print(f"--- Thread-{thread_id} 启动，准备处理任务。")
    spider = None
    
    # 在线程中创建独立的爬虫实例
    try:
        spider = creativemarket(chrome_driver_path)
        if not spider.driver:
            print(f"[致命错误] Thread-{thread_id} 爬虫实例初始化失败，退出线程。")
            return
            
        while True:
            try:
                # 1. 从队列中获取标签任务 (非阻塞，超时 1 秒)
                tag = tag_queue.get(timeout=1) 
            except Exception:
                # 队列为空，所有任务已分配完毕
                break 

            try:
                print(f"\n[任务分配] Thread-{thread_id} 获得标签任务：【{tag}】")
                spider.crawl_page(tag, csv_path)
                print(f"[任务完成] Thread-{thread_id} 标签【{tag}】处理完毕。")
            except Exception as e:
                print(f"[✗] Thread-{thread_id} 爬取任务中发生未捕获异常：{e}")
            finally:
                # 任务完成，通知队列
                tag_queue.task_done()
                
    finally:
        # 确保 WebDriver 在线程退出前被关闭
        if spider:
            spider.close()
        print(f"--- Thread-{thread_id} 退出。")


class CrawlerManager:
    """
    管理多线程爬取任务的中央调度器。
    """
    def __init__(self, driver_path: str, tags_file: str, csv_output: str, max_threads: int):
        self.driver_path = driver_path
        self.tags_file = tags_file
        self.csv_output = csv_output
        self.max_threads = max_threads
        os.makedirs(os.path.dirname(self.csv_output), exist_ok=True)
        
    def load_tags(self) -> List[str]:
        """从文件加载所有标签，并写入全局队列。"""
        try:
            with open(self.tags_file, 'r', encoding='utf-8') as f:
                tags = [line.strip() for line in f if line.strip()]
                return tags
        except FileNotFoundError:
            print(f"[错误] 标签文件未找到: {self.tags_file}")
            return []

    def start_crawling(self):
        """启动线程池并分配任务。"""
        tags = self.load_tags()
        if not tags:
            print("[致命错误] 没有标签任务，爬虫终止。")
            return
            
        print(f"--- 找到 {len(tags)} 个标签，准备启动 {self.max_threads} 个线程。")

        # 将所有标签放入任务队列
        for tag in tags:
            TAG_QUEUE.put(tag)
        
        threads = []
        for i in range(self.max_threads):
            # 传递 worker_task 所需的共享和独立资源
            t = threading.Thread(
                target=worker_task, 
                args=(TAG_QUEUE, self.driver_path, self.csv_output),
                daemon=True # 设置为守护线程，主程序退出时线程也退出
            )
            threads.append(t)
            t.start()
            print(f"Manager 启动 Thread-{t.ident}...")

        # 阻塞主线程，直到队列中的所有任务完成
        TAG_QUEUE.join() 
        
        print("\n====================================")
        print("所有标签任务已分配并完成处理。")
        print("====================================")
        
        # 此时所有 worker 线程应该因为队列空而退出（通过 `get(timeout=1)` 实现）

if __name__ == '__main__':
    manager = CrawlerManager(
        driver_path=CHROME_DRIVER_PATH,
        tags_file=TAG_FILE_PATH,
        csv_output=CSV_PATH,
        max_threads=MAX_THREADS
    )
    
    # 检查 Redis 连接
    try:
        SHARED_REDIS_CLIENT.ping()
        print("[√] Redis 连接成功。")
    except redis.exceptions.ConnectionError as e:
        print(f"[致命错误] 无法连接到 Redis：{e}。请确保 Redis 服务正在运行。")
    else:
        manager.start_crawling()