# -*- coding: utf-8 -*-
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException, WebDriverException
from redis.exceptions import ConnectionError as RedisConnectionError

import os
import time
import hashlib
import redis
import csv
import threading
import random
import re

# ----------------------------------------------------------------------
# 配置项
# ----------------------------------------------------------------------
START_URL = 'https://www.lensculture.com/'
TAG_NAME = 'lensculture_Homepage_Data'
CHROME_DRIVER_PATH = r'C:\Program Files\Google\1\chromedriver-win32\chromedriver.exe'

# 滚动优化配置
SCROLL_PAUSE_TIME = 3.0
SCROLL_STEPS = 2
SMALL_SCROLL_AMOUNT = 1080
MAX_SCROLLS = 100
# ----------------------------------------------------------------------


class lensculture:
    def __init__(self, chrome_driver_path):
        print("[INFO] 正在初始化 WebDriver...")
        try:
            service = Service(executable_path=chrome_driver_path)
            options = Options()
            options.add_argument('--headless')
            options.add_argument('--disable-gpu')
            options.add_argument("--window-size=1920,1080")  # 模拟 1k 显示器
            options.add_argument("--disable-blink-features=AutomationControlled")
            options.add_experimental_option("excludeSwitches", ["enable-automation"])
            options.add_experimental_option('useAutomationExtension', False)
            user_agent = ('Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
                          'AppleWebKit/537.36 (KHTML, like Gecko) '
                          'Chrome/91.0.4472.124 Safari/537.36')
            options.add_argument(f'user-agent={user_agent}')

            self.driver = webdriver.Chrome(service=service, options=options)
        except WebDriverException as e:
            print(f"[致命错误] WebDriver 启动失败: {e}")
            raise

        self.base_url = START_URL

        # Redis 初始化
        self.redis = redis.Redis(host='localhost', port=6379, db=0, decode_responses=True)
        try:
            self.redis.ping()
            print("[√] Redis 连接成功。")
        except RedisConnectionError as e:
            print(f"无法连接 Redis: {e}")
            raise

        self.redis_key = 'image_md5_set_lensculture'
        self.csv_lock = threading.Lock()

    # ----------------------------------------------------------------------
    def _clean_url(self, url: str) -> str:
        """
        将缩略图 URL 转换为原图 URL。
        示例：
        https://images.lensculture.com/dynamic/.../fit=cover,width=370,height=240
        → https://images.lensculture.com/dynamic/.../contain=2200
        """
        if not url:
            return ""
        return re.sub(r'fit=cover,width=\d+,height=\d+', 'contain=2200', url)

    # ----------------------------------------------------------------------
    def get_images(self, tag, csv_path, image_elements_to_process):
        """解析新加载的图片卡片"""
        if not image_elements_to_process:
            return

        print(f"--- 正在解析最新加载的 {len(image_elements_to_process)} 个图片容器 ---")
        extracted_count = 0

        for card_ele in image_elements_to_process:
            try:
                # 1. 获取图片元素
                img_element = card_ele.find_element(By.CSS_SELECTOR, 'img')
                image_url = img_element.get_attribute('src')

                # 2. 获取标题
                try:
                    title_element = card_ele.find_element(By.CSS_SELECTOR, 'div.title')
                    title = title_element.text.strip()
                except NoSuchElementException:
                    title = "Untitled"

                # 3. 清理 URL
                image_url_cleaned = self._clean_url(image_url)

                if image_url_cleaned:
                    md5_hash = hashlib.md5(image_url_cleaned.encode('utf-8')).hexdigest()

                    if not self.redis.sismember(self.redis_key, md5_hash):
                        self.redis.sadd(self.redis_key, md5_hash)
                        image_name = image_url_cleaned.split('/')[-1]
                        self.write_to_csv(title, image_name, image_url_cleaned, csv_path, tag)
                        extracted_count += 1

            except Exception as e:
                print(f"[✗] 处理图片异常: {e}")
                continue

        print(f"--- 本轮解析完成，新增 {extracted_count} 条数据。")

    # ----------------------------------------------------------------------
    def write_to_csv(self, title, name, url, csv_path, tag):
        """线程安全地写入 CSV"""
        try:
            with self.csv_lock:
                file_exists = os.path.exists(csv_path) and os.path.getsize(csv_path) > 0
                with open(csv_path, 'a', newline='', encoding='utf-8-sig') as f:
                    writer = csv.writer(f)
                    if not file_exists:
                        writer.writerow(['Title', 'ImageName', 'URL', "TAG"])
                    writer.writerow([title, name, url, tag])
                    f.flush()
            print(f'[√] 写入成功：{name}')
        except Exception as e:
            print(f'[✗] 写入 CSV 异常：{name} -> {e}')

    # ----------------------------------------------------------------------
    def crawl_page(self, start_url, tag, csv_path):
        """核心爬取逻辑"""
        wait = WebDriverWait(self.driver, 20)
        image_card_selector = 'a.featured-articles-item'

        try:
            print(f"[INFO] 导航到起始页: {start_url}")
            self.driver.get(start_url)

            # 等待首页主要容器出现
            wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, 'div.recent-articles-list.js-lazy-list')))
            print("[√] 初始页面加载稳定。")
        except Exception as e:
            print(f"[✗] 初始加载失败: {e}")
            return False

        # 滚动加载逻辑
        main_content_element = self.driver.find_element(By.CSS_SELECTOR, 'div.recent-articles-list.js-lazy-list')
        processed_count = 0

        for scroll_cycle_count in range(MAX_SCROLLS):
            print(f"\n==== 开始第 {scroll_cycle_count + 1} 轮滚动 ====")

            all_elements = main_content_element.find_elements(By.CSS_SELECTOR, image_card_selector)
            current_count = len(all_elements)
            print(f"[INFO] 当前共有 {current_count} 个卡片，已处理 {processed_count} 个。")

            if current_count > processed_count:
                new_elements = all_elements[processed_count:]
                self.get_images(tag, csv_path, new_elements)
                processed_count = current_count

            # 执行多次小滚动
            scroll_before = self.driver.execute_script("return window.scrollY")
            for step in range(SCROLL_STEPS):
                self.driver.execute_script(f"window.scrollBy(0, {SMALL_SCROLL_AMOUNT});")
                time.sleep(0.5 + random.uniform(0.1, 0.5))

            time.sleep(SCROLL_PAUSE_TIME)
            scroll_after = self.driver.execute_script("return window.scrollY")

            final_elements = main_content_element.find_elements(By.CSS_SELECTOR, image_card_selector)
            final_count = len(final_elements)

            if final_count == processed_count and scroll_after <= scroll_before:
                print(f"[完成] 到达底部，共 {final_count} 条。")
                break

        return True

    # ----------------------------------------------------------------------
    def main(self):
        """主入口"""
        save_path_all = r'D:\work\爬虫\爬虫数据\lensculture'
        os.makedirs(save_path_all, exist_ok=True)

        csv_path = os.path.join(save_path_all, 'all_lensculture_records.csv')
        print(f'\n[INFO] 开始爬取【{TAG_NAME}】 → {START_URL}')
        print(f'[INFO] 数据保存路径：{csv_path}')

        success = self.crawl_page(START_URL, TAG_NAME, csv_path)
        if success:
            print(f'[√] 【{TAG_NAME}】爬取完毕。')
        else:
            print(f'[✗] 【{TAG_NAME}】爬取失败。')

        self.driver.quit()


if __name__ == '__main__':
    try:
        lensculture(CHROME_DRIVER_PATH).main()
    except (WebDriverException, RedisConnectionError):
        print("\n[程序退出] 请先解决上述致命错误后再重试。")
