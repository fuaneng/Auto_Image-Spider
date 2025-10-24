from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
from selenium.common.exceptions import TimeoutException, NoSuchElementException
import os
import time
import hashlib
import redis
import csv
import threading
import random
import re
import urllib.parse
from urllib.parse import urlparse


class girlydrop:
    def __init__(self, chrome_driver_path):
        """初始化爬虫类"""
        service = Service(executable_path=chrome_driver_path)
        options = Options()
        options.add_experimental_option("excludeSwitches", ["enable-automation"])
        options.add_experimental_option('useAutomationExtension', False)
        options.add_argument('user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36')
        options.add_argument('--headless')  # 无头模式
        options.add_argument('--window-size=1920,1080')  # 设置窗口大小
        self.driver = webdriver.Chrome(service=service, options=options)

        self.base_url = 'https://girlydrop.com/'
        self.csv_lock = threading.Lock()

        # Redis 初始化
        try:
            self.redis = redis.Redis(host='localhost', port=6379, db=0, decode_responses=True)
            self.redis.ping()
            print("✅ Redis 连接成功。")
        except Exception:
            print("⚠️ Redis 不可用，将使用内存去重。")
            self.redis = None
            self.visited_md5 = set()

        self.redis_key = 'image_md5_set_girlydrop' # Redis 键名

    def get_images(self, tag, csv_path):
        """解析当前页面上的图片信息，支持提取标题、原图链接、标签等"""
        print(f"--- 正在解析【{tag}】的图片列表...")

        # 页面中图片列表所在的容器
        container_selector = 'ul.photoList.orderCyun'
        image_item_selector = 'li.photoList__item'
        wait = WebDriverWait(self.driver, 20)

        # ✅ 等待主容器加载
        try:
            wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, container_selector)))
            print("[√] 主图片容器加载完成。")
            time.sleep(random.uniform(1.0, 2.0))
        except TimeoutException:
            print("[✗] 等待主图片容器超时，页面可能为空。")
            return

        # ✅ 滚动加载逻辑（某些页面需要）
        last_count = 0
        while True:
            image_elements = self.driver.find_elements(By.CSS_SELECTOR, image_item_selector)
            current_count = len(image_elements)
            if current_count == last_count and current_count > 0:
                print(f"所有图片 ({current_count} 张) 已加载完毕。")
                break
            self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            last_count = current_count
            time.sleep(random.uniform(1.5, 2.5))

        # ✅ 遍历每个 <li.photoList__item>
        for card_ele in self.driver.find_elements(By.CSS_SELECTOR, image_item_selector):
            try:
                # 获取主要信息
                a_ele = card_ele.find_element(By.CSS_SELECTOR, 'a.photoList__link')
                img_ele = a_ele.find_element(By.TAG_NAME, 'img')
                title_ele = a_ele.find_element(By.CSS_SELECTOR, 'h3.photoList__title')

                title = title_ele.text.strip()
                image_url = img_ele.get_attribute('src')
                alt_text = img_ele.get_attribute('alt') or ""

                # 提取图像 ID
                match = re.search(r'ID:(\d+)', alt_text)
                if match:
                    img_id = match.group(1)
                    image_url_cleaned = f"https://girlydrop.com/wp-content/uploads/post/p{img_id}.jpg"
                else:
                    image_url_cleaned = image_url

                # 提取标签列表
                tag_list_ele = card_ele.find_elements(By.CSS_SELECTOR, 'ul.tagList li a')
                tag_texts = [t.text.strip() for t in tag_list_ele]
                tags_joined = "、".join(tag_texts) if tag_texts else ""

                # 生成唯一哈希用于去重
                md5_hash = hashlib.md5(image_url_cleaned.encode('utf-8')).hexdigest()
                duplicate = False
                if self.redis:
                    if self.redis.sismember(self.redis_key, md5_hash):
                        duplicate = True
                    else:
                        self.redis.sadd(self.redis_key, md5_hash)
                else:
                    if md5_hash in getattr(self, "visited_md5", set()):
                        duplicate = True
                    else:
                        self.visited_md5.add(md5_hash)

                if duplicate:
                    continue

                # 写入 CSV
                image_name = os.path.basename(image_url_cleaned)
                self.write_to_csv(title, image_name, image_url_cleaned, csv_path, f"{tag} | {tags_joined}")
                print(f"✔️ 提取成功：{title}")

            except Exception as e:
                print(f"[✗] 提取单个图片信息出错: {e}")
                continue



    def write_to_csv(self, title, name, url, csv_path, tag):
        """写入 CSV"""
        try:
            with self.csv_lock:
                with open(csv_path, 'a', newline='', encoding='utf-8-sig') as f:
                    writer = csv.writer(f)
                    if f.tell() == 0:
                        writer.writerow(['Title', 'ImageName', 'URL', 'Tag'])
                    writer.writerow([title, name, url, tag])
            print(f"✔️ 写入成功: {name}")
        except Exception as e:
            print(f"[✗] 写入 CSV 出错: {e}")


    def crawl_page(self, tag, csv_path):
        """翻页逻辑"""
        next_page_xpath = '//a[@class="nextpostslink" and contains(text(),"NEXT")]' # 下一页按钮 XPath
        wait = WebDriverWait(self.driver, 15)
        page_num = 1

        while True:
            print(f"\n=== 开始爬取【{tag}】第 {page_num} 页 ===")
            self.get_images(tag, csv_path)

            try:
                next_button = wait.until(EC.element_to_be_clickable((By.XPATH, next_page_xpath))) # 确保下一页按钮可点击
                self.driver.execute_script("arguments[0].click();", next_button)
                time.sleep(random.uniform(2, 4))
                wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, 'li.photoList__item'))) # 确保新页面加载
                page_num += 1
            except TimeoutException:
                print(f"[完成] 【{tag}】共爬取 {page_num} 页。")
                break
            except Exception as e:
                print(f"[✗] 翻页出错: {e}")
                break


    def main(self):
        save_path_all = r'D:\work\爬虫\爬虫数据\girlydrop'
        tag_file_path = os.path.join(save_path_all, r"D:\work\爬虫\爬虫数据\girlydrop\ram_tag_list.txt") # 标签文件路径
        os.makedirs(save_path_all, exist_ok=True)
        csv_path = os.path.join(save_path_all, 'all_records_01.csv')

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
                search_url = f'{self.base_url}?s={encoded_tag}' # 搜索 URL
                print(f"\n--- 开始处理：【{tag}】 ---\nURL: {search_url}")
                self.driver.get(search_url)
                time.sleep(random.uniform(3, 5))

                current_url = self.driver.current_url
                if "girlydrop.com/?s=" not in current_url:
                    print(f"[跳过] {tag} 没有搜索结果。")
                    continue

                self.crawl_page(tag, csv_path)
            except Exception as e:
                print(f"[✗] 处理标签 {tag} 出错: {e}")

        self.driver.quit()


if __name__ == '__main__':
    chrome_driver_path = r'C:\Program Files\Google\chromedriver-win32\chromedriver.exe' # 修改为你的 chromedriver 路径
    spider = girlydrop(chrome_driver_path)
    try:
        spider.main()
    finally:
        spider.driver.quit()
