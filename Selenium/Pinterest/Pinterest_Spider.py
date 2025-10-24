from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.keys import Keys
from selenium.common.exceptions import TimeoutException
import os, time, hashlib, redis, csv, threading, random, urllib.parse

# ---------- 全局滚动策略 ----------
MAX_SCROLLS = 200
NO_NEW_ROUNDS_TO_STOP = 2
SCROLL_WAIT_RANGE = (1.5, 3.5)

class PinterestSpider:
    def __init__(self, chrome_driver_path, use_headless=True, redis_host='localhost', redis_port=6379):
        if not os.path.exists(chrome_driver_path):
            raise FileNotFoundError(f"ChromeDriver not found at path: {chrome_driver_path}")

        service = Service(executable_path=chrome_driver_path)
        options = Options()
        options.add_experimental_option("excludeSwitches", ["enable-automation"])
        options.add_experimental_option('useAutomationExtension', False)
        options.add_argument(
            'user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
            'AppleWebKit/537.36 (KHTML, like Gecko) '
            'Chrome/120.0 Safari/537.36'
        )

        if use_headless:
            options.add_argument("--headless=new")
        options.add_argument("--window-size=1920,1080")

        # 可选：禁用图片加载提高性能（建议关闭以便检测 img 标签）
        # prefs = {"profile.managed_default_content_settings.images": 2}
        # options.add_experimental_option("prefs", prefs)

        self.driver = webdriver.Chrome(service=service, options=options)
        self.base_url = 'https://za.pinterest.com/'
        self.csv_lock = threading.Lock()
        self.redis_key = 'image_md5_set_pinterest'
        self.visited_md5 = set()

        try:
            self.redis = redis.Redis(host=redis_host, port=redis_port, db=0, decode_responses=True)
            self.redis.ping()
            print("✅ Redis 连接成功。")
        except Exception as e:
            print(f"⚠️ Redis 初始化失败 ({e})，使用内存去重。")
            self.redis = None

    # ---------------------- JS 抓取图片 ----------------------
    def get_all_image_data_js(self):
        js = """
        const imgs = Array.from(document.querySelectorAll('img[srcset], img[src]'));
        return imgs.map(img => {
            const srcset = img.getAttribute('srcset') || '';
            const src = img.getAttribute('src') || '';
            const alt = img.getAttribute('alt') || '';
            return { srcset, src, alt };
        });
        """
        return self.driver.execute_script(js)

    # ---------------------- 清除遮挡层 ----------------------
    def remove_overlays(self):
        js = """
        const selectors = [
            'div[data-test-id="fullPageSignupModal"]',
            'div[data-test-id="simple-login-overlay"]',
            'div[data-test-id="login"]',
            'div[data-test-id="overlay"]',
            'div[role="dialog"]'
        ];
        let removed = 0;
        selectors.forEach(sel => {
            document.querySelectorAll(sel).forEach(e => {
                e.remove();
                removed++;
            });
        });
        return removed;
        """
        removed = self.driver.execute_script(js)
        if removed:
            print(f"[清理] 已移除 {removed} 个遮罩层。")

    # ---------------------- 等待图片懒加载稳定 ----------------------
    def wait_for_images_stable(self, timeout=8):
        prev_count = 0
        stable_rounds = 0
        for _ in range(int(timeout * 2)):
            curr_count = len(self.driver.find_elements(By.CSS_SELECTOR, "img[srcset], img[src]"))
            if curr_count == prev_count:
                stable_rounds += 1
                if stable_rounds >= 3:
                    print(f"[√] 图片数稳定: {curr_count}")
                    break
            else:
                stable_rounds = 0
            prev_count = curr_count
            time.sleep(0.5)

    # ---------------------- 高分辨率 URL 选择 ----------------------
    def get_highest_res_url(self, srcset_str, src_url):
        urls = []
        if srcset_str:
            parts = srcset_str.split(',')
            for part in parts:
                url_candidate = part.strip().split()[0]
                urls.append(url_candidate)
            original_url = next((u for u in urls if '/originals/' in u), None)
            if original_url:
                return original_url
            if urls:
                return urls[-1]
        if src_url:
            return src_url.replace('/236x/', '/736x/').replace('/474x/', '/736x/')
        return None

    # ---------------------- 去重逻辑 ----------------------
    def is_duplicate(self, md5_hash):
        if self.redis:
            try:
                if self.redis.sismember(self.redis_key, md5_hash):
                    return True
                self.redis.sadd(self.redis_key, md5_hash)
                return False
            except Exception as e:
                print(f"⚠️ Redis 出错 ({e})，改用内存。")
                self.redis = None
        if md5_hash in self.visited_md5:
            return True
        self.visited_md5.add(md5_hash)
        return False

    # ---------------------- CSV 写入 ----------------------
    def write_to_csv(self, title, name, url, csv_path, tag):
        try:
            with self.csv_lock:
                os.makedirs(os.path.dirname(csv_path), exist_ok=True)
                file_exists = os.path.exists(csv_path)
                with open(csv_path, 'a', newline='', encoding='utf-8-sig') as f:
                    writer = csv.writer(f)
                    if not file_exists:
                        writer.writerow(['Title', 'ImageName', 'URL', 'Tag'])
                    writer.writerow([title, name, url, tag])
        except Exception as e:
            print(f"[✗] 写入 CSV 出错: {e}")

    # ---------------------- 页面爬取逻辑 ----------------------
    def crawl_page(self, search_url, tag, csv_path):
        wait = WebDriverWait(self.driver, 15)
        try:
            print(f"[INFO] 导航到：{search_url}")
            self.driver.get(search_url)
            wait.until(EC.presence_of_element_located((By.TAG_NAME, "body")))
            print("[√] 页面加载完成。")
        except TimeoutException:
            print("[✗] 页面加载超时。")
            return False

        scroll_cycle = 0
        no_new_rounds = 0

        while scroll_cycle < MAX_SCROLLS:
            print(f"\n==== 第 {scroll_cycle + 1} 次滚动 ====")
            self.remove_overlays()

            image_data_list = self.get_all_image_data_js()
            print(f"[INFO] JS 抓取到 {len(image_data_list)} 张图片。")

            written = 0
            for img_data in image_data_list:
                srcset = img_data.get('srcset', '')
                src = img_data.get('src', '')
                alt = img_data.get('alt', '')
                image_url = self.get_highest_res_url(srcset, src)
                if not image_url:
                    continue

                md5_hash = hashlib.md5(image_url.encode('utf-8')).hexdigest()
                if self.is_duplicate(md5_hash):
                    continue

                title = alt or "N/A"
                image_name = os.path.basename(urllib.parse.urlparse(image_url).path)
                if not image_name:
                    image_name = md5_hash + ".jpg"

                self.write_to_csv(title, image_name, image_url, csv_path, tag)
                written += 1
                print(f"✔️ 写入：{image_name}")

            if written == 0:
                no_new_rounds += 1
                print(f"[⚠] 无新增图片 ({no_new_rounds}/{NO_NEW_ROUNDS_TO_STOP})")
            else:
                no_new_rounds = 0

            if no_new_rounds >= NO_NEW_ROUNDS_TO_STOP:
                print("[完成] 已连续无新内容，结束滚动。")
                break

            # 滚动到底部并等待新图片加载
            self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            self.wait_for_images_stable()
            wait_time = random.uniform(*SCROLL_WAIT_RANGE)
            print(f"[等待] 滚动后等待 {wait_time:.2f} 秒...")
            time.sleep(wait_time)
            scroll_cycle += 1

        print(f"[√] '{tag}' 抓取完成。")
        return True

    # ---------------------- 主流程 ----------------------
    def main(self, save_dir, tag_file_path, csv_name='all_records_pinterest.csv'):
        os.makedirs(save_dir, exist_ok=True)
        csv_path = os.path.join(save_dir, csv_name)

        try:
            with open(tag_file_path, 'r', encoding='utf-8') as f:
                tags = [line.strip() for line in f if line.strip()]
        except FileNotFoundError:
            print(f"[错误] 未找到标签文件: {tag_file_path}")
            return

        print(f"--- 共 {len(tags)} 个标签 ---")

        for tag in tags:
            try:
                encoded_tag = urllib.parse.quote(tag.replace(' ', '%20'))
                url = f"{self.base_url}search/pins/?q={encoded_tag}&rs=typed"
                print(f"\n--- 抓取：【{tag}】 ---\nURL: {url}")
                self.crawl_page(url, tag, csv_path)
            except Exception as e:
                print(f"[✗] 处理标签 {tag} 出错: {e}")

    def quit(self):
        try:
            self.driver.quit()
        except Exception as e:
            print(f"关闭浏览器出错: {e}")

# ---------------------- 启动 ----------------------
if __name__ == '__main__':
    chrome_driver_path = r'C:\Program Files\Google\chromedriver-win32\chromedriver.exe'
    save_dir = r'D:\work\爬虫\爬虫数据\pinterest'
    tag_file_path = r'D:\work\爬虫\ram_tag_list_备份.txt'

    spider = None
    try:
        spider = PinterestSpider(chrome_driver_path, use_headless=False)
        spider.main(save_dir, tag_file_path)
    finally:
        if spider:
            spider.quit()
