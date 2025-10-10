from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
from selenium.common.exceptions import TimeoutException
import os, time, hashlib, redis, csv, threading, random, re, urllib.parse


class VintageStockPhotos:
    def __init__(self, chrome_driver_path):
        service = Service(executable_path=chrome_driver_path)
        options = Options()
        options.add_experimental_option("excludeSwitches", ["enable-automation"])
        options.add_experimental_option('useAutomationExtension', False)
        options.add_argument('user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36')
        # options.add_argument('--headless')    # 无头模式
        # options.add_argument('--window-size=1920,1080')  # 设置窗口大小
        options.add_argument('--disable-gpu')   # 禁用GPU加速
        self.driver = webdriver.Chrome(service=service, options=options)

        self.base_url = 'https://vintagestockphotos.com/'
        self.csv_lock = threading.Lock()
        self.redis_key = 'image_md5_set_vintagestockphotos'

        try:
            self.redis = redis.Redis(host='localhost', port=6379, db=0, decode_responses=True)
            self.redis.ping()
            print("✅ Redis 连接成功。")
        except Exception:
            print("⚠️ Redis 不可用，将使用内存去重。")
            self.redis = None
            self.visited_md5 = set()

    # ---------------------- 提取当前页图片 ----------------------
    def get_images(self, tag, csv_path):
        print(f"--- 正在解析【{tag}】的图片列表...")

        wait = WebDriverWait(self.driver, 20)
        try:
            wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, 'div.tabs_content div.flex-images22')))
            print("[√] 主图片容器加载完成。")
        except TimeoutException:
            print("[✗] 页面加载超时。")
            return

        # 滚动加载所有图片
        last_count = 0
        while True:
            image_elements = self.driver.find_elements(By.CSS_SELECTOR, 'div.flex-images22 div.item')
            if len(image_elements) == last_count and last_count > 0:
                break
            self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            last_count = len(image_elements)
            time.sleep(random.uniform(1.5, 2.5))

        print(f"📸 共检测到 {len(image_elements)} 张图片。")
        
        # 遍历图片元素，提取信息
        for card_ele in image_elements:
            try:
                img_ele = card_ele.find_element(By.CSS_SELECTOR, 'a.image img')
                image_url = img_ele.get_attribute('src') or ""
                mouse_attr = img_ele.get_attribute('onmouseover') or ""

                # --- 从 onmouseover 中提取标题 ---
                match = re.search(r"trailOn\('[^']*','([^']*)'", mouse_attr)
                title = match.group(1).strip() if match else "Untitled"

                # --- 构造原图 URL ---
                image_url_cleaned = image_url.replace("thumbnail", "sample")    # 替换为更高分辨率的图片

                # --- 去重 ---
                md5_hash = hashlib.md5(image_url_cleaned.encode('utf-8')).hexdigest()
                if self.is_duplicate(md5_hash):
                    continue

                # --- 写入 CSV ---
                image_name = os.path.basename(image_url_cleaned)
                self.write_to_csv(title, image_name, image_url_cleaned, csv_path, tag)
                print(f"✔️ 提取成功：{title}")

            except Exception as e:
                print(f"[✗] 提取图片信息失败: {e}")

    # ---------------------- 去重逻辑 ----------------------
    def is_duplicate(self, md5_hash):
        if self.redis:
            if self.redis.sismember(self.redis_key, md5_hash):
                return True
            self.redis.sadd(self.redis_key, md5_hash)
        else:
            if md5_hash in self.visited_md5:
                return True
            self.visited_md5.add(md5_hash)
        return False

    # ---------------------- 写入 CSV ----------------------
    def write_to_csv(self, title, name, url, csv_path, tag):
        try:
            with self.csv_lock:
                with open(csv_path, 'a', newline='', encoding='utf-8-sig') as f:
                    writer = csv.writer(f)
                    if f.tell() == 0:
                        writer.writerow(['Title', 'ImageName', 'URL', 'Tag'])
                    writer.writerow([title, name, url, tag])
            print(f"💾 写入成功: {name}")
        except Exception as e:
            print(f"[✗] 写入 CSV 出错: {e}")

    # ---------------------- 翻页逻辑 ----------------------
    def crawl_page(self, tag, csv_path):
        page_num = 1
        wait = WebDriverWait(self.driver, 15)

        while True:
            print(f"\n=== 正在爬取【{tag}】第 {page_num} 页 ===")
            self.get_images(tag, csv_path)

            try:
                next_btn = self.driver.find_element(By.LINK_TEXT, "Next »")
                self.driver.execute_script("arguments[0].click();", next_btn)
                time.sleep(random.uniform(2.5, 4))
                wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, 'div.flex-images22 div.item'))) # 等待新内容加载
                page_num += 1
            except Exception:
                print(f"[完成] 【{tag}】共爬取 {page_num} 页。")
                break

    # ---------------------- 主函数 ----------------------
    def main(self):
        save_dir = r'D:\work\爬虫\爬虫数据\vintagestockphotos'  # 请修改为你的保存目录
        tag_file_path = os.path.join(save_dir, r'D:\work\爬虫\爬虫数据\vintagestockphotos\ram_tag_list_备份.txt')   # 请修改为你的标签文件路径
        os.makedirs(save_dir, exist_ok=True)
        csv_path = os.path.join(save_dir, 'all_records_01.csv')

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
                search_url = f"{self.base_url}search.php?search={encoded_tag}&gid_search=&match=all"
                print(f"\n--- 开始处理：【{tag}】 ---\nURL: {search_url}")
                self.driver.get(search_url)
                time.sleep(random.uniform(3, 5))

                # ✅ 新增：检测是否存在结果
                try:
                    WebDriverWait(self.driver, 10).until(
                        lambda d: d.find_elements(By.CSS_SELECTOR, "div.flex-images22")
                    )
                    image_items = self.driver.find_elements(By.CSS_SELECTOR, "div.flex-images22 div.item")
                    if not image_items:
                        print(f"[跳过] {tag} 无搜索结果（无图片元素）。")
                        continue
                except TimeoutException:
                    print(f"[跳过] {tag} 页面未加载出图片容器。")
                    continue

                self.crawl_page(tag, csv_path)
            except Exception as e:
                print(f"[✗] 处理标签 {tag} 出错: {e}")

        self.driver.quit()


if __name__ == '__main__':
    chrome_driver_path = r'C:\Program Files\Google\chromedriver-win64\chromedriver.exe' # 请修改为你的chromedriver路径
    spider = VintageStockPhotos(chrome_driver_path)
    try:
        spider.main()
    finally:
        spider.driver.quit()
