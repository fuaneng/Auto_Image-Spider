from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
from selenium.common.exceptions import TimeoutException, NoSuchElementException
import os, time, hashlib, redis, csv, threading, random, re, urllib.parse


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

        # ✅ 通用容器选择器：覆盖所有 li 图片结构
        self.main_container_selector = 'div#post-list-posts li[id^="p"], div#content li[id^="p"]'

        # ✅ Redis 初始化（带降级）
        try:
            self.redis = redis.Redis(host=redis_host, port=redis_port, db=0, decode_responses=True)
            self.redis.ping()
            print("✅ Redis 连接成功。")
        except Exception:
            print("⚠️ Redis 不可用，将使用内存去重。")
            self.redis = None
            self.visited_md5 = set()

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

        # 提取所有 li 元素
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

    # ---------------------- 标题解析 ----------------------
    def parse_title_info(self, title_text):
        """
        从标题中提取 Rating、Score、Tags、User 字段
        示例：
        'Rating: Questionable Score: 147 Tags: ass kantoku miko pantsu skirt_lift User: jokerinyandere'
        """
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
            else:
                # 兼容分段匹配
                parts = re.split(r'\s+(?=[A-Z][a-z]+:)', title_text)
                for p in parts:
                    if p.startswith('Rating:'):
                        rating = p.replace('Rating:', '').strip()
                    elif p.startswith('Score:'):
                        score = p.replace('Score:', '').strip()
                    elif p.startswith('Tags:'):
                        tags = p.replace('Tags:', '').strip()
                    elif p.startswith('User:'):
                        user = p.replace('User:', '').strip()
        except Exception as e:
            print(f"[⚠️] 标题解析失败: {e} | 原始: {title_text}")
        return rating, score, tags, user

    # ---------------------- 去重逻辑 ----------------------
    def is_duplicate(self, md5_hash):
        if hasattr(self, 'redis') and self.redis:
            try:
                if self.redis.sismember(self.redis_key, md5_hash):
                    return True
                self.redis.sadd(self.redis_key, md5_hash)
            except Exception as e:
                print(f"⚠️ Redis 出错，回退内存去重: {e}")
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

    # ---------------------- 写入 CSV ----------------------
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

    # ---------------------- 主入口 ----------------------
    def main(self, save_dir, tag_file_path, csv_name='all_records_yande_re_v3.csv'):
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
                # ✅ 不再使用 quote_plus，直接拼接原始 URL
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


# ---------------------- 启动入口 ----------------------
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
