from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
from selenium.common.exceptions import TimeoutException, NoSuchElementException
import os, time, hashlib, redis, csv, threading, random, re, urllib.parse, requests


class yande_re:
    def __init__(self, chrome_driver_path, use_headless=True, redis_host='localhost', redis_port=6379):
        service = Service(executable_path=chrome_driver_path)
        options = Options()
        options.add_experimental_option("excludeSwitches", ["enable-automation"])
        options.add_experimental_option('useAutomationExtension', False)
        options.add_argument(
            'user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        )
        if use_headless:
            options.add_argument('--headless=new')
        options.add_argument("--window-size=1920,1080")

        self.driver = webdriver.Chrome(service=service, options=options)
        self.base_url = 'https://yande.re/'
        self.csv_lock = threading.Lock()
        self.redis_key = 'image_md5_set_yande.re'

        self.main_container_selector = 'div#post-list-posts li[id^="p"], div#content li[id^="p"]'

        try:
            self.redis = redis.Redis(host=redis_host, port=redis_port, db=0, decode_responses=True)
            self.redis.ping()
            print("✅ Redis 连接成功。")
        except Exception:
            print("⚠️ Redis 不可用，将使用内存去重。")
            self.redis = None
            self.visited_md5 = set()

    # 🧠 原图检测逻辑
    def get_hq_image_url(self, lowres_url):
        """
        将 jpeg/jpg 尝试替换为 image/png
        并通过 HEAD 请求检测是否存在更高质量版本
        """
        try:
            if "/jpeg/" in lowres_url or lowres_url.endswith(".jpg"):
                hq_url = lowres_url.replace("/jpeg/", "/image/").rsplit(".", 1)[0] + ".png"

                # 尝试请求原图（仅 HEAD 请求验证存在）
                resp = requests.head(hq_url, timeout=10)    # 增加超时时间，防止网络问题
                if resp.status_code == 200:
                    print(f"🟢 检测到更高清原图: {hq_url}")
                    return hq_url
                else:
                    print(f"⚪ 无高清原图: {hq_url} [{resp.status_code}]")
        except Exception as e:
            print(f"⚠️ 原图检测异常: {e},一般是网络问题 检测URL: {hq_url}")

        return lowres_url

    # ---------------------- 主逻辑 ----------------------
    def get_images(self, tag, csv_path):
        print(f"--- 正在解析【{tag}】的图片列表...")

        wait = WebDriverWait(self.driver, 30)
        try:
            wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, self.main_container_selector)))
            print("[√] 主图片容器加载完成。")
        except TimeoutException:
            print("[✗] 页面加载超时，找不到主图片容器。")
            return

        post_containers = self.driver.find_elements(By.CSS_SELECTOR, self.main_container_selector)
        print(f"🖼️ 共检测到 {len(post_containers)} 个图片容器。")

        successful_writes = 0
        for idx, card_ele in enumerate(post_containers):
            try:
                # 查找原图链接
                try:
                    img_ele = card_ele.find_element(By.CSS_SELECTOR, 'a.directlink.largeimg')
                except NoSuchElementException:
                    try:
                        img_ele = card_ele.find_element(By.CSS_SELECTOR, 'a[href*="files.yande.re"]')
                    except NoSuchElementException:
                        print(f"[跳过] 容器序号 {idx}：未找到原图链接。")
                        continue

                image_url = img_ele.get_attribute('href') or ''
                if not image_url:
                    continue

                # 尝试获取更高清版本
                image_url = self.get_hq_image_url(image_url)

                # 提取标题
                try:
                    title_ele = card_ele.find_element(By.CSS_SELECTOR, 'a.thumb img.preview')
                    title = title_ele.get_attribute('title').strip()
                except NoSuchElementException:
                    title = "N/A"

                # --- 拆分标题 ---
                rating, score, tags_text, user = self.parse_title_info(title)

                # 去重
                md5_hash = hashlib.md5(image_url.encode('utf-8')).hexdigest()
                if self.is_duplicate(md5_hash):
                    print(f"[重复] 容器序号 {idx}：【{title}】 URL 已存在，跳过。")
                    continue

                # 写入 CSV
                image_name = os.path.basename(urllib.parse.urlparse(image_url).path)
                self.write_to_csv(rating, score, tags_text, user, image_name, image_url, csv_path, tag)
                print(f"✔️ 写入成功：{image_url}")
                successful_writes += 1

            except Exception as e:
                print(f"[✗] 提取失败 idx={idx}: {e}")

        print(f"✅ 【{tag}】成功写入 {successful_writes} 条记录。")

    def parse_title_info(self, title_text):
        rating, score, tags, user = "N/A", "N/A", "N/A", "N/A"
        try:
            match = re.search(
                r'Rating:\s*([A-Za-z]+)\s+Score:\s*(\d+)\s+Tags:\s*(.*?)\s+User:\s*(\S+)',
                title_text
            )
            if match:
                rating = match.group(1).strip()
                score = match.group(2).strip()
                tags = match.group(3).strip()
                user = match.group(4).strip()
        except Exception as e:
            print(f"[⚠️] 标题解析失败: {e} | 原始: {title_text}")
        return rating, score, tags, user

    def is_duplicate(self, md5_hash):
        if hasattr(self, 'redis') and self.redis:
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
            if not hasattr(self, 'visited_md5'):
                self.visited_md5 = set()
            if md5_hash in self.visited_md5:
                return True
            self.visited_md5.add(md5_hash)
        return False

    def write_to_csv(self, rating, score, tags, user, name, url, csv_path, tag):
        try:
            with self.csv_lock:
                is_file_empty = not os.path.exists(csv_path) or os.stat(csv_path).st_size == 0
                os.makedirs(os.path.dirname(csv_path), exist_ok=True)
                with open(csv_path, 'a', newline='', encoding='utf-8-sig') as f:
                    writer = csv.writer(f)
                    if is_file_empty:
                        writer.writerow(['Rating', 'Score', 'Tags', 'User', 'ImageName', 'URL', 'Tag'])
                    writer.writerow([rating, score, tags, user, name, url, tag])
        except Exception as e:
            print(f"[✗] 写入 CSV 出错: {e}")

    def main(self, save_dir, tag_file_path, csv_name='all_records_yande_re_v4.csv'):
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
                search_url = f"{self.base_url}{tag}"
                print(f"\n📄 开始处理：【{tag}】\nURL: {search_url}")
                self.driver.get(search_url)
                time.sleep(random.uniform(2.5, 4.0))
                self.get_images(tag, csv_path)
            except Exception as e:
                print(f"[✗] 处理标签 {tag} 出错: {e}")

    def quit(self):
        try:
            if self.driver:
                self.driver.quit()
        except Exception as e:
            print(f"关闭浏览器出错: {e}")


if __name__ == '__main__':
    chrome_driver_path = r'C:\Program Files\Google\chromedriver-win64\chromedriver.exe'
    save_dir = r'R:\py\Auto_Image-Spider\yande.re\output_v3'
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
