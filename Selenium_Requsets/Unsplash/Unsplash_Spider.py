import os, time, hashlib, csv, threading, random, urllib.parse
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.keys import Keys
from selenium.common.exceptions import TimeoutException, NoSuchElementException, StaleElementReferenceException
import redis
import redis.exceptions # 用于更具体的 Redis 异常处理

# ---------- 全局滚动策略常量（可根据需要调整） ----------
MAX_SCROLLS = 100  # 最大的滚动次数限制，防止无限循环
NO_NEW_ROUNDS_TO_STOP = 2    # 连续多少轮次未发现新图片时，判定页面内容已加载完毕并停止抓取
SMALL_SCROLL_AMOUNT = 200   # 滚动量（像素）。用于在接近底部时进行微调，触发懒加载。
# 🚀 新增：默认并发线程数
DEFAULT_MAX_THREADS = 5 


class UnsplashSpider:
    """
    Unsplash 爬虫类，负责单个标签的爬取任务，并管理浏览器实例。
    """
    def __init__(self, chrome_driver_path, use_headless=True, redis_host='localhost', redis_port=6379):
        # ⚠️ 检查 driver 路径是否存在
        if not os.path.exists(chrome_driver_path):
            raise FileNotFoundError(f"ChromeDriver not found at path: {chrome_driver_path}")

        service = Service(executable_path=chrome_driver_path)
        options = Options()
        # 隐藏自动化控制信息
        options.add_experimental_option("excludeSwitches", ["enable-automation"])
        options.add_experimental_option('useAutomationExtension', False)
        # 设置 User-Agent
        options.add_argument(
            'user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        )
        # 设置无头模式
        if use_headless:
            options.add_argument('--headless=new')
        options.add_argument("--window-size=1920,1080")
        
        # 禁用图片加载，提高速度（可选，但会增加获取 URL 的复杂性，此处保留）
        # prefs = {"profile.managed_default_content_settings.images": 2}
        # options.add_experimental_option("prefs", prefs)

        self.driver = webdriver.Chrome(service=service, options=options)
        self.base_url = 'https://unsplash.com/'
        
        # 多线程共享 CSV 写入锁
        self.csv_lock = threading.Lock() 
        self.redis_key = 'image_md5_set_unsplash'
        
        # 【关键抓取元素 1：图片卡片容器】
        self.image_card_selector = 'figure[data-testid="asset-grid-masonry-figure"]'

        # Redis 连接（可选，用于跨任务去重）
        try:
            self.redis = redis.Redis(host=redis_host, port=redis_port, db=0, decode_responses=True)
            self.redis.ping()
        except redis.exceptions.ConnectionError:
            print(f"⚠️ Redis 连接失败，将使用内存去重。")
            self.redis = None
            self.visited_md5 = set()
        except Exception:
            self.redis = None
            self.visited_md5 = set()


    # ---------------------- 增量解析新加载的图片元素 ----------------------
    def get_images(self, tag, csv_path, elements):
        """
        解析图片卡片元素，提取图片URL、标题，进行去重并写入CSV。
        集成了 Stale Element 引用失效的重试处理。
        """
        successful_writes = 0
        for card_ele in elements:
            
            # 🚀 Stale Element 重试逻辑
            max_retries = 2
            attempt = 0
            processed_successfully = False
            
            while attempt < max_retries and not processed_successfully:
                try:
                    # --- 原始的处理逻辑块 START ---
                    
                    # 【关键抓取元素 2：最高质量下载链接】
                    image_url = None
                    try:
                        download_btn = card_ele.find_element(
                            By.CSS_SELECTOR,
                            "a[data-testid='non-sponsored-photo-download-button']"
                        )
                        image_url = download_btn.get_attribute('href') or ''
                    except NoSuchElementException:
                        pass
                    
                    # 【关键抓取元素 3：IMG 标签及 URL 备选方案】
                    if not image_url:
                        try:
                            img_ele = card_ele.find_element(By.CSS_SELECTOR, 'img')
                            # 优先 srcset
                            srcset = img_ele.get_attribute('srcset') or ''
                            if srcset:
                                parts = [p.strip() for p in srcset.split(',') if p.strip()]
                                if parts:
                                    image_url = parts[-1].split()[0]
                            if not image_url:
                                image_url = img_ele.get_attribute('src') or ''
                        except Exception:
                            image_url = None

                    if not image_url:
                        processed_successfully = True # 标记为成功处理(跳过)，退出while
                        continue

                    # 规范化链接
                    image_url_cleaned = urllib.parse.urljoin(self.base_url, image_url)

                    # 【关键抓取元素 4：图片标题提取】
                    title = "N/A"
                    try:
                        img_for_title = card_ele.find_element(By.CSS_SELECTOR, 'img')
                        alt = img_for_title.get_attribute('alt') # 1. 优先 alt 属性
                        if alt and alt.strip():
                            title = alt.strip()
                        else:
                            a_link = card_ele.find_element(By.CSS_SELECTOR, 'a.photoInfoLink-mG0SPO') # 2. 备选：信息链接
                            a_title = a_link.get_attribute('title')
                            if a_title and a_title.strip():
                                title = a_title.strip()
                            elif title == "N/A": 
                                try:
                                    # 3. 最终备选：图注/说明文字
                                    caption = card_ele.find_element(By.CSS_SELECTOR, 'figcaption, .photo-info, .photoMeta')
                                    txt = caption.text.strip()
                                    if txt:
                                        title = txt
                                except Exception:
                                    pass
                    except Exception:
                        pass

                    # 去重：使用 URL 的 md5
                    md5_hash = hashlib.md5(image_url_cleaned.encode('utf-8')).hexdigest()
                    if self.is_duplicate(md5_hash):
                        processed_successfully = True # 标记为成功处理(重复)，退出while
                        continue

                    # image name
                    image_name = os.path.basename(urllib.parse.urlparse(image_url_cleaned).path)
                    if not image_name or len(image_name) < 5:
                        image_name = md5_hash + ".jpg"

                    # 写入 CSV
                    self.write_to_csv(title, image_name, image_url_cleaned, csv_path, tag)
                    successful_writes += 1
                    print(f"[{tag}] ✔️ 写入：{image_name}")
                    
                    processed_successfully = True # 标记为成功处理，退出while
                    
                    # --- 原始的处理逻辑块 END ---

                except NoSuchElementException:
                    print(f"[{tag}] [WARN] 元素结构异常，跳过当前卡片。")
                    processed_successfully = True # 退出while
                
                except StaleElementReferenceException:
                    attempt += 1
                    print(f"[{tag}] [STALE] 元素引用失效，重试第 {attempt} 次...")
                    time.sleep(0.5) # 短暂等待 DOM 稳定
                    if attempt >= max_retries:
                        print(f"[{tag}] [FAIL] 元素引用重试 {max_retries} 次后仍失效，跳过该元素。")
                        processed_successfully = True # 退出while
                
                except Exception as e:
                    print(f"[{tag}] [✗] 处理元素出错: {e}")
                    processed_successfully = True # 退出while

        return successful_writes


    # ---------------------- 页面滚动并抓取直到稳定（强化滚动操作） ----------------------
    def crawl_page(self, search_url: str, tag: str, csv_path: str) -> bool:
        """
        滚动加载图片并调用 get_images 进行解析。
        """
        wait = WebDriverWait(self.driver, 10)
        image_card_selector = self.image_card_selector

        try:
            print(f"[{tag}] [INFO] 导航到：{search_url}")
            self.driver.get(search_url)
            # 等待图片卡片元素出现
            wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, image_card_selector)))
            print(f"[{tag}] [√] 页面已加载，找到图片卡片容器。")
        except TimeoutException:
            print(f"[{tag}] [✗] 页面加载超时或未找到任何图片卡片。")
            return False
        except Exception as e:
            print(f"[{tag}] [✗] 页面加载异常：{e}")
            return False

        # ---------- 滚动主循环 ----------
        scroll_cycle_count = 0
        processed_count = 0
        no_new_content_rounds = 0

        # 尝试点击 body 确保焦点在页面上
        try:
            self.driver.find_element(By.TAG_NAME, 'body').click()
        except Exception:
            pass

        while scroll_cycle_count < MAX_SCROLLS:
            
            # 1. 解析当前已加载但未处理的图片
            all_elements = self.driver.find_elements(By.CSS_SELECTOR, image_card_selector)
            current_count = len(all_elements)

            if current_count > processed_count:
                new_elements = all_elements[processed_count:]
                written = self.get_images(tag, csv_path, new_elements)
                processed_count = current_count
            
            # 2. 滚动操作 (优先使用 END 键)
            try:
                body = self.driver.find_element(By.TAG_NAME, 'body')
                body.send_keys(Keys.END)
                time.sleep(random.uniform(1.0, 2.0))
            except Exception:
                try:
                    self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
                    time.sleep(random.uniform(1.0, 2.0))
                except Exception as js_e:
                    print(f"[{tag}] [FATAL] JavaScript 滚动失败: {js_e}")
                    break

            # 3. 等待新内容出现
            try:
                wait.until(
                    lambda driver: len(driver.find_elements(By.CSS_SELECTOR, image_card_selector)) > processed_count
                )
                no_new_content_rounds = 0
            except TimeoutException:
                no_new_content_rounds += 1
                print(f"[{tag}] [⚠] 等待超时，未发现新图片。({no_new_content_rounds}/{NO_NEW_ROUNDS_TO_STOP})")

                # 【关键抓取元素 6：Load more 按钮】 尝试点击 'Load more'
                try:
                    load_more_button = self.driver.find_element(
                        By.CSS_SELECTOR,
                        "button.loadMoreButton-pYP1fq" 
                    )
                    if load_more_button.is_displayed() and load_more_button.is_enabled():
                        print(f"[{tag}] [INFO] 发现 'Load more' 按钮，尝试点击。")
                        load_more_button.click()
                        no_new_content_rounds = 0 
                        time.sleep(random.uniform(2.0, 3.0)) 
                        print(f"[{tag}] [√] 'Load more' 按钮已点击，重新等待新内容加载。")
                        scroll_cycle_count += 1
                        continue # 跳到下一轮循环
                except NoSuchElementException:
                    pass
                except Exception as click_e:
                    print(f"[{tag}] [WARN] 点击 'Load more' 按钮出错: {click_e}")
                    
                # 检查是否真的到底部
                try:
                    scroll_height = self.driver.execute_script("return document.body.scrollHeight")
                    current_scroll = self.driver.execute_script("return window.scrollY + window.innerHeight")
                except Exception:
                    scroll_height = current_scroll = 0

                if abs(scroll_height - current_scroll) < 50:
                    print(f"[{tag}] [INFO] 滚动条已到达页面最底部。")
                else:
                    # 微调滚动
                    try:
                        self.driver.execute_script(f"window.scrollBy(0, {SMALL_SCROLL_AMOUNT});")
                        time.sleep(1)
                    except Exception:
                        pass

                # 4. 如果超过阈值则结束
                if no_new_content_rounds >= NO_NEW_ROUNDS_TO_STOP:
                    print(f"[{tag}] [完成] 已连续 {NO_NEW_ROUNDS_TO_STOP} 轮未发现新内容，判定'{tag}'已抓取完毕。")
                    
                    # 退出前最后一次解析
                    all_elements_final = self.driver.find_elements(By.CSS_SELECTOR, image_card_selector)
                    final_count = len(all_elements_final)
                    if final_count > processed_count:
                        new_elements_final = all_elements_final[processed_count:]
                        self.get_images(tag, csv_path, new_elements_final)
                    break

            scroll_cycle_count += 1
            if scroll_cycle_count >= MAX_SCROLLS:
                print(f"[{tag}] [⚠] 达到最大滚动次数 {MAX_SCROLLS}，强制停止。")
                break

            time.sleep(random.uniform(0.5, 1.5)) # 小随机等待

        print(f"[{tag}] [√] 标签 '{tag}' 滚动抓取完成，共找到约 {processed_count} 张图片。")
        return True


    # ---------------------- 去重逻辑 ----------------------
    def is_duplicate(self, md5_hash):
        """检查并记录 MD5 哈希以进行去重。"""
        if self.redis:
            try:
                if self.redis.sismember(self.redis_key, md5_hash):
                    return True
                self.redis.sadd(self.redis_key, md5_hash)
            except Exception:
                # Redis 异常时降级到内存去重
                self.redis = None 
                if not hasattr(self, 'visited_md5'):
                    self.visited_md5 = set()
                if md5_hash in self.visited_md5:
                    return True
                self.visited_md5.add(md5_hash)
        
        if not self.redis:
            if md5_hash in self.visited_md5:
                return True
            self.visited_md5.add(md5_hash)
        return False

    # ---------------------- 写入 CSV ----------------------
    def write_to_csv(self, title, name, url, csv_path, tag):
        """写入 CSV 文件，使用线程锁保证多线程安全。"""
        try:
            with self.csv_lock:
                os.makedirs(os.path.dirname(csv_path), exist_ok=True)
                is_file_empty = not os.path.exists(csv_path) or os.stat(csv_path).st_size == 0
                with open(csv_path, 'a', newline='', encoding='utf-8-sig') as f:
                    writer = csv.writer(f)
                    if is_file_empty:
                        writer.writerow(['Title', 'ImageName', 'URL', 'Tag'])
                    writer.writerow([title, name, url, tag])
        except Exception as e:
            print(f"[{tag}] [✗] 写入 CSV 出错: {e}")

    # ---------------------- 退出浏览器 ----------------------
    def quit(self):
        """关闭浏览器实例。"""
        try:
            if self.driver:
                self.driver.quit()
        except Exception:
            pass


# ---------------------- 🚀 多线程 Worker 函数 ----------------------
def run_spider_task(tag: str, chrome_driver_path: str, save_dir: str, csv_name: str, use_headless: bool, redis_host: str, redis_port: int, semaphore: threading.Semaphore):
    """
    单个标签的爬取任务执行体，在独立线程中运行。
    每个任务都会实例化一个独立的 UnsplashSpider（含浏览器）。
    """
    spider = None
    csv_path = os.path.join(save_dir, csv_name)

    try:
        # --- 1. 获取信号量（限制并发数） ---
        semaphore.acquire() 
        print(f"\n[CONTROL] 正在为标签 '{tag}' 启动新的浏览器实例...")

        # --- 2. 实例化 Spider (含独立浏览器) ---
        spider = UnsplashSpider(
            chrome_driver_path=chrome_driver_path, 
            use_headless=use_headless,
            redis_host=redis_host,
            redis_port=redis_port
        )
        
        # --- 3. 准备 URL 并执行爬取任务 ---
        # 修复 Unsplash 特有 URL 编码逻辑：将空格替换为破折号
        tag_with_dashes = tag.replace(' ', '-')
        encoded_tag = urllib.parse.quote(tag_with_dashes).replace('+', '-')
        search_url = f"{spider.base_url}s/photos/{encoded_tag}"
        
        print(f"[{tag}] --- 开始处理：URL: {search_url}")
        spider.crawl_page(search_url, tag, csv_path)
        print(f"[{tag}] [CONTROL] 标签抓取任务完成。")

    except FileNotFoundError as e:
        print(f"[{tag}] [ERROR] 启动失败，驱动未找到: {e}")
    except Exception as e:
        print(f"[{tag}] [ERROR] 处理标签时发生未预期错误: {e}")
    finally:
        # --- 4. 确保关闭浏览器实例和释放信号量 ---
        if spider:
            spider.quit()
        semaphore.release()
        print(f"[{tag}] [CONTROL] 线程已结束并释放信号量。")


# ---------------------- 启动脚本示例 (主控制逻辑) ----------------------
if __name__ == '__main__':
    # ⚠️ 配置部分：请修改为你自己的路径和设置
    chrome_driver_path = r'C:\Program Files\Google\chromedriver-win32\chromedriver.exe'
    save_dir = r'D:\work\爬虫\爬虫数据\unsplash'
    tag_file_path = r'D:\work\爬虫\爬虫数据\unsplash\ram_tag_list_备份.txt'
    csv_name = 'all_records_unsplash.csv'
    use_headless = True
    
    # 🚀 并发控制设置
    MAX_THREADS = DEFAULT_MAX_THREADS  # 设置最大并发线程数（浏览器实例数）
    semaphore = threading.Semaphore(MAX_THREADS)

    os.makedirs(save_dir, exist_ok=True)
    
    # 1. 读取标签
    try:
        with open(tag_file_path, 'r', encoding='utf-8') as f:
            tags = [line.strip() for line in f if line.strip()]
    except FileNotFoundError:
        print(f"[错误] 未找到标签文件: {tag_file_path}")
        exit()

    print(f"\n--- 发现 {len(tags)} 个标签，将使用 {MAX_THREADS} 个并发线程处理 ---")

    threads = []
    
    # 2. 创建并启动线程
    for tag in tags:
        # 为每个标签创建一个独立的线程
        t = threading.Thread(
            target=run_spider_task,
            args=(tag, chrome_driver_path, save_dir, csv_name, use_headless, 'localhost', 6379, semaphore),
            name=f"Thread-{tag}"
        )
        threads.append(t)
        t.start()
        
    # 3. 等待所有线程完成
    for t in threads:
        t.join()

    print("\n[CONTROL] 所有标签爬取任务已完成！")