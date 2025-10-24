from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
from selenium.common.exceptions import TimeoutException, NoSuchElementException
import os, time, hashlib, redis, csv, threading, random, urllib.parse


class yande_re:
    def __init__(self, chrome_driver_path, use_headless=True, redis_host='localhost', redis_port=6379):
        service = Service(executable_path=chrome_driver_path)
        options = Options()
        options.add_experimental_option("excludeSwitches", ["enable-automation"])
        options.add_experimental_option('useAutomationExtension', False)
        options.add_argument(
            'user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36')
        # if use_headless:
        #     options.add_argument('--headless=new')
        # options.add_argument("--window-size=1920,1080")
        options.add_argument('--disable-logging')
        options.add_argument('--log-level=3')

        self.driver = webdriver.Chrome(service=service, options=options)
        self.base_url = 'https://yande.re/'
        self.csv_lock = threading.Lock()

        # ✅ 保证属性一定存在
        self.redis = None
        self.visited_md5 = set()
        self.redis_key = 'image_md5_set_yande.re'

        # ✅ 页面主容器选择器，通用匹配全部图片卡片 li 元素，如下：
        # <li id="p1213212" class="creator-id-457203 has-parent">...</li>
        # <li id="p1213620" class="javascript-hide creator-id-117710">...</li>
        # <li id="p1213443" class="javascript-hide creator-id-366544 has-parent">...</li>
        self.main_container_selector = 'div#post-list-posts li[id^="p"], div#content li[id^="p"]'

        # ✅ 初始化 Redis（容错）
        try:
            import redis
            self.redis = redis.Redis(host=redis_host, port=redis_port, db=0, decode_responses=True)
            self.redis.ping()
            print("✅ Redis 连接成功。")
        except Exception as e:
            print(f"⚠️ Redis 不可用，将使用内存去重。原因: {e}")
            self.redis = None

        # ---------------------- get_images 函数中 ----------------------
    def get_images(self, tag, csv_path):
        print(f"--- 正在解析【{tag}】的图片列表...")

        wait = WebDriverWait(self.driver, 30)
        post_containers = []
        try:
            # 先等待主选择器
            wait.until(EC.presence_of_all_elements_located((By.CSS_SELECTOR, self.main_container_selector)))
            post_containers = self.driver.find_elements(By.CSS_SELECTOR, self.main_container_selector)
        except TimeoutException:
            print("[⚠️] 主容器未加载成功，尝试备用选择器...")
            try:
                wait.until(EC.presence_of_all_elements_located((By.CSS_SELECTOR, self.backup_container_selector)))
                post_containers = self.driver.find_elements(By.CSS_SELECTOR, self.backup_container_selector)
            except TimeoutException:
                print("[✗] 页面加载超时，找不到任何图片容器。")
                return 0

        print(f"🖼️ 检测到 {len(post_containers)} 个图片容器。")

        successful_writes = 0
        for idx, card_ele in enumerate(post_containers):
            try:
                img_a = card_ele.find_element(By.CSS_SELECTOR, 'a.directlink.largeimg')
                image_url = img_a.get_attribute('href')
                if not image_url:
                    continue

                title = "NAN"
                try:
                    title_ele = card_ele.find_element(By.CSS_SELECTOR, 'a.thumb > img.preview')
                    title = title_ele.get_attribute('title') or title_ele.get_attribute('alt') or "NAN"
                except NoSuchElementException:
                    pass

                md5_hash = hashlib.md5(image_url.encode('utf-8')).hexdigest()
                if self.is_duplicate(md5_hash):
                    print(f"[重复] {idx}: {title}")
                    continue

                image_name = os.path.basename(urllib.parse.urlparse(image_url).path)
                self.write_to_csv(title, image_name, image_url, csv_path, tag)
                print(f"✔️ {idx}: {image_url}")
                successful_writes += 1

            except Exception as e:
                print(f"[✗] 提取失败 idx={idx}: {e}")

        return successful_writes

    # ---------------------- 去重逻辑 ----------------------
    def is_duplicate(self, md5_hash):
        if self.redis:
            try:
                if self.redis.sismember(self.redis_key, md5_hash):
                    return True
                self.redis.sadd(self.redis_key, md5_hash)
            except Exception:
                if not hasattr(self, 'visited_md5'):
                    self.visited_md5 = set()
                if md5_hash in self.visited_md5:
                    return True
                self.visited_md5.add(md5_hash)
        else:
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

    # ---------------------- 翻页抓取 ----------------------
    def crawl_page(self, tag, csv_path):
        total = 0
        page = 1
        while True:
            print(f"\n📄 正在抓取第 {page} 页...")
            count = self.get_images(tag, csv_path)
            total += count

            try:
                next_btn = self.driver.find_element(By.CSS_SELECTOR, 'a.next_page')
                next_url = next_btn.get_attribute('href')
                if not next_url:
                    break
                self.driver.get(next_url)
                time.sleep(random.uniform(2, 3))
                page += 1
            except NoSuchElementException:
                print("🚫 没有下一页了。")
                break
        print(f"✅ 共抓取 {total} 张图片。")

    # ---------------------- 主函数 ----------------------
    def main(self, save_dir, tag_file_path, csv_name='all_records_yande_re.csv'):
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
            # 关键修复：对 tag 进行编码但保留路径与查询相关字符
            # safe="/:?=&" 会保留斜杠和查询符号，避免把整个 path+query 编码成 %2F %3F ...
            encoded_tag = urllib.parse.quote(tag, safe="/:?=&")
            # 使用 urljoin 做安全拼接
            search_url = urllib.parse.urljoin(self.base_url, encoded_tag)
            print(f"\n=== 开始处理：【{tag}】 ===\nURL: {search_url}")
            self.driver.get(search_url)
            time.sleep(random.uniform(2.5, 4.0))
            self.crawl_page(tag, csv_path)

    def quit(self):
        try:
            if self.driver:
                self.driver.quit()
        except Exception as e:
            print(f"关闭浏览器出错: {e}")


if __name__ == '__main__':
    chrome_driver_path = r'C:\Program Files\Google\chromedriver-win64\chromedriver.exe'
    save_dir = r'R:\py\Auto_Image-Spider\yande.re\output_1012'
    tag_file_path = r'R:\py\Auto_Image-Spider\yande.re\ram_tag_周.txt'

    spider = None
    try:
        spider = yande_re(chrome_driver_path, use_headless=True)
        spider.main(save_dir=save_dir, tag_file_path=tag_file_path)
    except Exception as main_e:
        print(f"主程序运行出错: {main_e}")
    finally:
        if spider:
            print("\n正在关闭浏览器...")
            spider.quit()
