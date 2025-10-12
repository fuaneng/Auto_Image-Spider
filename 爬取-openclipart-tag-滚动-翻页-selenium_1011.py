from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
from selenium.common.exceptions import TimeoutException, NoSuchElementException, ElementClickInterceptedException
import os, time, hashlib, redis, csv, threading, random, re, urllib.parse, sys


class openclipart:
    def __init__(self, chrome_driver_path, use_headless=True, redis_host='localhost', redis_port=6379):
        service = Service(executable_path=chrome_driver_path)
        options = Options()
        options.add_experimental_option("excludeSwitches", ["enable-automation"])
        options.add_experimental_option('useAutomationExtension', False)
        options.add_argument(
            'user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        )
        # ✅ 启用 headless 模式
        if use_headless:
            options.add_argument('--headless=new')
        options.add_argument("--window-size=1920,1080")

        # ✅ 禁用图片加载以加快页面解析
        prefs = {"profile.managed_default_content_settings.images": 2}
        options.add_experimental_option("prefs", prefs)

        self.driver = webdriver.Chrome(service=service, options=options)
        self.base_url = 'https://openclipart.org/'
        self.csv_lock = threading.Lock()
        self.redis_key = 'image_md5_set_openclipart'
        self.main_container_selector = 'div.gallery div.artwork'

        # Redis 连接
        try:
            self.redis = redis.Redis(host=redis_host, port=redis_port, db=0, decode_responses=True)
            self.redis.ping()
            print("✅ Redis 连接成功。")
        except Exception:
            print("⚠️ Redis 不可用，将使用内存去重。")
            self.redis = None
            self.visited_md5 = set()

    # ---------------------- 清除弹窗 ----------------------
    def clear_popups(self):
        """移除可能遮挡翻页按钮的弹窗或遮罩层"""
        try:
            self.driver.execute_script("""
                const modals = document.querySelectorAll('.modal, .overlay, .popup, .backdrop');
                modals.forEach(m => m.remove());
            """)
        except Exception:
            pass

    # ---------------------- 提取当前页图片 ----------------------
    def get_images(self, tag, csv_path):
        print(f"--- 正在解析【{tag}】的图片列表...")

        wait = WebDriverWait(self.driver, 30)
        try:
            wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, self.main_container_selector)))
            print("[√] 主图片容器加载完成。")
        except TimeoutException:
            print("[✗] 页面加载超时，找不到主图片容器。")
            return

        # 分步滚动加载
        SCROLL_STEP = 1080
        MAX_IDLE_ROUNDS = 2
        scroll_round, idle_rounds = 0, 0
        last_height = self.driver.execute_script("return document.body.scrollHeight")
        window_height = self.driver.execute_script("return window.innerHeight;")

        print(f"🚀 开始分步滚动加载 (step={SCROLL_STEP}px)...")
        while True:
            scroll_round += 1
            self.driver.execute_script(f"window.scrollBy(0, {SCROLL_STEP});")
            time.sleep(1.0 + random.random())

            current_height = self.driver.execute_script("return document.body.scrollHeight")
            current_offset = self.driver.execute_script("return window.pageYOffset;")

            if current_height > last_height:
                idle_rounds = 0
                last_height = current_height
            else:
                idle_rounds += 1

            if (current_offset + window_height) >= (current_height - 20):
                print("✅ 已滚动到底部。")
                break

            if idle_rounds >= MAX_IDLE_ROUNDS or scroll_round >= 80:
                print("✅ 停止滚动：页面高度无变化或达到上限。")
                break

        post_containers = self.driver.find_elements(By.CSS_SELECTOR, self.main_container_selector)
        print(f"🖼️ 共检测到 {len(post_containers)} 个图片容器。")

        successful_writes = 0
        for idx, card_ele in enumerate(post_containers):
            try:
                img_ele = card_ele.find_element(By.TAG_NAME, 'img')
                image_url = img_ele.get_attribute('src') or ''
                title = img_ele.get_attribute('alt') or 'NAN'

                if not image_url:
                    continue

                # 替换成原图 URL
                image_url_cleaned = re.sub(r'/image/\d+px/', '/image/2000px/', image_url)
                if image_url_cleaned.startswith('/'):
                    image_url_cleaned = urllib.parse.urljoin(self.base_url, image_url_cleaned)

                md5_hash = hashlib.md5(image_url_cleaned.encode('utf-8')).hexdigest()
                if self.is_duplicate(md5_hash):
                    continue

                image_name = os.path.basename(urllib.parse.urlparse(image_url_cleaned).path)
                self.write_to_csv(title, image_name, image_url_cleaned, csv_path, tag)
                successful_writes += 1
                print(f"✔️ 成功写入 {title} -> {image_url_cleaned}")

            except Exception as e:
                print(f"[✗] 容器 {idx} 解析失败: {e}")

        print(f"✅ 【{tag}】共提取 {successful_writes}/{len(post_containers)} 条记录。")

    # ---------------------- 去重 ----------------------
    def is_duplicate(self, md5_hash):
        if self.redis:
            try:
                if self.redis.sismember(self.redis_key, md5_hash):
                    return True
                self.redis.sadd(self.redis_key, md5_hash)
                return False
            except Exception:
                pass
        if not hasattr(self, 'visited_md5'):
            self.visited_md5 = set()
        if md5_hash in self.visited_md5:
            return True
        self.visited_md5.add(md5_hash)
        return False

    # ---------------------- 写入 CSV ----------------------
    def write_to_csv(self, title, name, url, csv_path, tag):
        try:
            with self.csv_lock:
                is_file_empty = not os.path.exists(csv_path) or os.stat(csv_path).st_size == 0
                os.makedirs(os.path.dirname(csv_path), exist_ok=True)
                with open(csv_path, 'a', newline='', encoding='utf-8-sig') as f:
                    writer = csv.writer(f)
                    if is_file_empty:
                        writer.writerow(['Title', 'ImageName', 'URL', 'Tag'])
                    writer.writerow([title, name, url, tag])
        except Exception as e:
            print(f"[✗] 写入 CSV 出错: {e}")

    # ---------------------- 翻页（JS点击 + 校验变化） ----------------------
    def crawl_page(self, tag, csv_path):
        page_num = 1
        wait = WebDriverWait(self.driver, 20)

        while True:
            print(f"\n=== 正在爬取【{tag}】第 {page_num} 页 ===")
            self.get_images(tag, csv_path)

            try:
                page_html_before = self.driver.execute_script("return document.body.innerHTML;")
                page_hash_before = hashlib.md5(page_html_before.encode('utf-8')).hexdigest()
            except Exception:
                page_hash_before = str(time.time())

            try:
                self.clear_popups()
                next_btn = self.driver.find_element(By.CSS_SELECTOR, 'li.page-item a[aria-label="Next"]')

                if not next_btn or 'disabled' in next_btn.get_attribute('class').lower():
                    print(f"[完成] Next 按钮已禁用，结束翻页，共爬取 {page_num} 页。")
                    break

                print("➡️ 使用 JS 点击下一页（绕过遮挡）...")
                self.driver.execute_script("arguments[0].scrollIntoView({block:'center'});", next_btn)
                time.sleep(random.uniform(0.3, 0.6))
                self.driver.execute_script("arguments[0].click();", next_btn)

                time.sleep(random.uniform(3.0, 5.0))
                wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, self.main_container_selector)))

                page_html_after = self.driver.execute_script("return document.body.innerHTML;")
                page_hash_after = hashlib.md5(page_html_after.encode('utf-8')).hexdigest()

                if page_hash_after == page_hash_before:
                    print("⚠️ 页面内容未变化，可能仍停留在上一页，终止翻页。")
                    break

                page_num += 1
                print(f"✅ 成功跳转到第 {page_num} 页。")

            except NoSuchElementException:
                print(f"[完成] 未检测到分页按钮，结束翻页，共 {page_num} 页。")
                break
            except TimeoutException:
                print(f"[✗] 第 {page_num} 页加载超时。")
                break
            except Exception as e:
                print(f"[✗] 翻页错误: {e}")
                break

    # ---------------------- 主函数 ----------------------
    def main(self, save_dir, tag_file_path, csv_name='all_records_openclipart.csv'):
        os.makedirs(save_dir, exist_ok=True)
        csv_path = os.path.join(save_dir, csv_name)

        try:
            with open(tag_file_path, 'r', encoding='utf-8') as f:
                tags = [line.strip() for line in f if line.strip()]
        except FileNotFoundError:
            print(f"[错误] 未找到标签文件: {tag_file_path}")
            return

        print(f"--- 发现 {len(tags)} 个标签 ---")
        for tag in tags:
            try:
                encoded_tag = urllib.parse.quote_plus(tag)
                search_url = f"{self.base_url}search/?query={encoded_tag}"
                print(f"\n--- 开始处理：【{tag}】 ---\nURL: {search_url}")
                self.driver.get(search_url)
                time.sleep(random.uniform(2.5, 4.0))

                WebDriverWait(self.driver, 15).until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, self.main_container_selector))
                )

                self.crawl_page(tag, csv_path)
            except Exception as e:
                print(f"[✗] 处理标签 {tag} 出错: {e}")

    def quit(self):
        try:
            if self.driver:
                self.driver.quit()
        except Exception as e:
            print(f"关闭浏览器出错: {e}")


if __name__ == '__main__':
    chrome_driver_path = r'C:\Program Files\Google\1\chromedriver-win32\chromedriver.exe'
    save_dir = r'D:\work\爬虫\爬虫数据\openclipart'
    tag_file_path = r'D:\work\爬虫\ram_tag_list.txt'

    spider = None
    try:
        spider = openclipart(chrome_driver_path, use_headless=True)
        spider.main(save_dir=save_dir, tag_file_path=tag_file_path)
    except Exception as main_e:
        print(f"主程序运行出错: {main_e}")
    finally:
        if spider:
            print("\n正在关闭浏览器...")
            spider.quit()
