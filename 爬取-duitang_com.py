import re
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
import os
import time
import hashlib
import redis
import csv
import threading
import random

class duitang:
    def __init__(self, chrome_driver_path):
        """
        初始化爬虫类，使用标准 Selenium 和 Service 对象。
        
        Args:
            chrome_driver_path: 本地 ChromeDriver 可执行文件的完整路径。
        """
        service = Service(executable_path=chrome_driver_path)
        
        options = Options()
        options.add_experimental_option("excludeSwitches", ["enable-automation"])
        options.add_experimental_option('useAutomationExtension', False)
        user_agent = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        options.add_argument(f'user-agent={user_agent}')
        self.driver = webdriver.Chrome(service=service, options=options)

        self.base_url = 'https://www.duitang.com/search/'
        
        self.redis = redis.Redis(
            host='localhost',
            port=6379,
            db=0,
            decode_responses=True
        )
        self.redis_key = 'duitang_image_md5_hashes'
        self.csv_lock = threading.Lock()

    def get_images(self, tag, csv_path):
        """解析页面上的图片信息并存储 URL 和标题。"""
        print(f"--- 正在解析【{tag}】的图片列表...")
        
        image_card_selector = 'div[class*="woo co"]'
        
        wait = WebDriverWait(self.driver, 20)
        
        try:
            wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, image_card_selector)))
            print("[√] 图片容器已加载。")
            time.sleep(random.uniform(1.5, 3.0))
        except Exception:
            print("[✗] 等待图片容器超时，跳过此标签。")
            return

        last_count = 0
        while True:
            image_elements = self.driver.find_elements(By.CSS_SELECTOR, image_card_selector)
            current_count = len(image_elements)
            
            if current_count == last_count and current_count > 0:
                print("所有图片已加载完毕，准备开始解析。")
                break
            if current_count == 0 and last_count == 0:
                 print("当前页面没有找到图片元素，跳过。")
                 break

            last_element = image_elements[-1]
            self.driver.execute_script("arguments[0].scrollIntoView({behavior: 'smooth', block: 'end'});", last_element)
            
            print(f"滚动到第 {current_count} 个元素，继续加载...")
            last_count = current_count
            time.sleep(random.uniform(2.0, 4.0))

        image_elements = self.driver.find_elements(By.CSS_SELECTOR, image_card_selector)
        print(f"找到 {len(image_elements)} 个图片卡片。")
        
        for card_ele in image_elements:
            try:
                # 在每个卡片内部查找标题和图片元素
                title_element = card_ele.find_element(By.CSS_SELECTOR, '.wooscr .g')
                title = title_element.text.strip()
                
                img_element = card_ele.find_element(By.CSS_SELECTOR, '.mbpho img')
                image_url = img_element.get_attribute('src')
                
                # 步骤1：处理 ".thumb." 参数
                image_url_cleaned = re.sub(r'\.thumb\.[^.]+', '', image_url)

                # 步骤2：处理 "_webp" 后缀
                image_url_cleaned = re.sub(r'_webp$', '', image_url_cleaned)
                
                if image_url_cleaned and title:
                    md5_hash = hashlib.md5(image_url_cleaned.encode('utf-8')).hexdigest()
                    if not self.redis.sismember(self.redis_key, md5_hash):
                        self.redis.sadd(self.redis_key, md5_hash)
                        
                        image_name = image_url_cleaned.split('/')[-1]
                        
                        self.write_to_csv(title, image_name, image_url_cleaned, csv_path, tag)
                    else:
                        image_name = image_url_cleaned.split('/')[-1]
                        print(f"[跳过] 重复图片: {image_name}")
            
            except Exception as e:
                print(f"[✗] 处理图片异常: {e}")
                continue

    def write_to_csv(self, title, name, url, csv_path, tag):
        """将图片信息写入 CSV 文件。"""
        try:
            with self.csv_lock:
                with open(csv_path, 'a', newline='', encoding='utf-8-sig') as f:
                    writer = csv.writer(f)
                    if f.tell() == 0:
                        writer.writerow(['Title', 'ImageName', 'URL', "TAG"])
                    writer.writerow([title, name, url, tag])
                    f.flush()
            print(f'[√] 写入成功：{name}')
        except Exception as e:
            print(f'[✗] 写入 CSV 异常：{name} -> {e}')

    def crawl_page(self, tag, csv_path):
        """爬取单个标签页面。"""
        self.get_images(tag, csv_path)
        return True

    def main(self):
        save_path_all = r'D:\work\爬虫\爬虫数据\duitang'
        tag_file_path = r"D:\work\爬虫\ram_tag_list.txt"
        
        os.makedirs(save_path_all, exist_ok=True)
        
        try:
            with open(tag_file_path, 'r', encoding='utf-8') as f:
                tags = [line.strip() for line in f if line.strip()]
        except FileNotFoundError:
            print(f"[错误] 标签文件未找到: {tag_file_path}")
            return
        
        print(f"--- 找到 {len(tags)} 个标签。")
        
        csv_path = os.path.join(save_path_all, 'all_records.csv')
        
        for tag in tags:
            print(f'\n[INFO] 正在爬取【{tag}】 ...')

            try:
                search_url = f'{self.base_url}?kw={tag}&type=feed'
                self.driver.get(search_url)
                time.sleep(random.uniform(3.0, 5.0))
                
                success = self.crawl_page(tag, csv_path)
                
                if success:
                    print(f'[完成] 【{tag}】全部页面爬取与去重完毕。\n')
                else:
                    print(f'[失败] 【{tag}】爬取失败，请检查网络或网站结构。\n')
            except Exception as e:
                print(f"[✗] 爬取【{tag}】时发生错误: {e}")

        self.driver.quit()

if __name__ == '__main__':
    chrome_driver_path = r'C:\Program Files\Google\chromedriver-win64\chromedriver.exe'
    spider = duitang(chrome_driver_path)
    spider.main()