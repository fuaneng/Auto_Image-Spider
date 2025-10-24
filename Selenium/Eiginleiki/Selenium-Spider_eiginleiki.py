from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException
from redis.exceptions import ConnectionError as RedisConnectionError

import os
import time
import hashlib
import redis
import csv
import random
import re


# 配置常量
START_URL = 'https://eiginleiki.net/page/1' 
TAG_NAME = 'NAN'
# 请确保您的 ChromeDriver 路径是正确的
CHROME_DRIVER_PATH = r'C:\Program Files\Google\chromedriver-win64\chromedriver.exe' 

# ** 核心配置 **
# 该网页拥有数千张图片，每页约15张
START_PAGE = 1       # 从第 1 页开始爬取
MAX_PAGES = 330      # 爬取到第 330 页
PAGE_SPLIT_POINT = 9 # 页码分割点：小于 9 使用旧结构，大于等于 9 使用新结构

PAGE_SLEEP = 2 # 页面间休眠时间（秒）


class EiginleikiCrawler:
    def __init__(self, chrome_driver_path):
        print("[INFO] 初始化 WebDriver...")
        service = Service(executable_path=chrome_driver_path)
        options = Options()
        
        # 优化点：配置偏好设置以禁用图片加载
        prefs = {
            "profile.managed_default_content_settings.images": 2, # 2表示禁用图片加载
        }
        options.add_experimental_option("prefs", prefs)
        
        # options.add_argument('--headless')
        options.add_argument('--disable-gpu')
        options.add_experimental_option("excludeSwitches", ["enable-automation"])
        options.add_experimental_option('useAutomationExtension', False)
        # 设置 User-Agent
        ua = ('Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
              'AppleWebKit/537.36 (KHTML, like Gecko) '
              'Chrome/114.0.5735.199 Safari/537.36')
        options.add_argument(f'user-agent={ua}')
        options.add_argument("--disable-blink-features=AutomationControlled")
        
        self.driver = webdriver.Chrome(service=service, options=options)
        self.wait = WebDriverWait(self.driver, 15)

        # Redis 初始化
        try:
            self.redis = redis.Redis(host='localhost', port=6379, db=0, decode_responses=True)
            self.redis.ping()
            print("[√] Redis 连接成功")
        except RedisConnectionError as e:
            print(f"[✗] Redis 连接失败: {e}")
            raise 

        self.redis_key = 'image_md5_set_eiginleiki'

    def _clean_url(self, url):
        """删除 URL 中的查询参数 (?...)"""
        return re.sub(r'\?.*', '', url) if url else ""

    def write_to_csv(self, title, name, url, csv_path, tag):
        """将数据写入 CSV 文件"""
        os.makedirs(os.path.dirname(csv_path), exist_ok=True)
        file_exists = os.path.exists(csv_path) and os.path.getsize(csv_path) > 0
        try:
            with open(csv_path, 'a', newline='', encoding='utf-8-sig') as f:
                writer = csv.writer(f)
                if not file_exists:
                    writer.writerow(['Title', 'ImageName', 'URL', "TAG"])
                writer.writerow([title, name, url, tag])
            print(f"[√] 写入成功: {name}")
        except Exception as e:
            print(f"[✗] 写入 CSV 异常: {e}")

    # ** 关键修改：process_page 现在接受 page_num 作为参数 **
    def process_page(self, page_url, tag, csv_path, page_num):
        """加载页面并根据页码选择不同的图片提取逻辑"""
        print(f"\n==== 正在加载页面: {page_url} (第 {page_num} 页) ====")
        self.driver.get(page_url)
        time.sleep(2) 
        
        # --- 结构判断和选择器定义 ---
        if page_num < PAGE_SPLIT_POINT:
            # 1-8 页：旧结构 (data-big-photo)
            SELECTOR = 'figure.tmblr-full a.post_media_photo_anchor'
            ATTRIBUTE = 'data-big-photo'
            print("  [INFO] 使用旧结构选择器。")
        else:
            # 9 页及以后：新结构 (img src)
            # 定位到包含图片的 <a> 标签 (在 <div id="post"> 内)
            # 我们直接定位到 img 元素，获取其 src
            SELECTOR = 'div#post img' 
            ATTRIBUTE = 'src'
            print("  [INFO] 使用新结构选择器。")
        # --- 结构判断和选择器定义 End ---
        
        # 等待图片元素加载
        try:
            self.wait.until(
                EC.presence_of_element_located((By.CSS_SELECTOR, SELECTOR))
            )
        except TimeoutException:
            print(f"[INFO] 页面 {page_url} 等待元素超时，可能无图片。")
            pass 

        # 查找所有图片元素
        elements = self.driver.find_elements(By.CSS_SELECTOR, SELECTOR)

        if not elements:
            print(f"[INFO] 页面 {page_url} 未找到图片链接 (elements为空)。")
            return 0 

        print(f"[√] 当前页发现 {len(elements)} 个链接。")
        extracted_count = 0

        for idx, ele in enumerate(elements, 1):
            try:
                print(f"→ [{idx}/{len(elements)}] 正在处理图片...")
                
                # ** 核心：根据页码获取不同的属性 **
                final_url = ele.get_attribute(ATTRIBUTE)

                if not final_url:
                    print(f"[⚠] 缺少 {ATTRIBUTE} 属性，跳过。")
                    continue
                
                print(f"[√] 原图 URL: {final_url}")

                final_url = self._clean_url(final_url)
                # 计算 MD5 哈希用于去重
                md5_hash = hashlib.md5(final_url.encode('utf-8')).hexdigest()

                # 检查 Redis，防止重复
                if not self.redis.sismember(self.redis_key, md5_hash):
                    self.redis.sadd(self.redis_key, md5_hash)
                    img_name = os.path.basename(final_url)
                    # 写入 CSV
                    self.write_to_csv("N/A", img_name, final_url, csv_path, tag)
                    extracted_count += 1
                else:
                    print("  [INFO] URL 已存在 (MD5 校验)。")
            except Exception as e:
                print(f"[✗] 处理图片时出错: {e}")
                continue

        print(f"[INFO] 本页完成，新增 {extracted_count} 条记录。")
        return extracted_count

    def run(self, start_url, tag, csv_path):
        """主运行函数，处理分页逻辑"""
        # 提取基础 URL
        base_url = re.sub(r'/page/\d+', '', start_url).rstrip('/')
        total = 0
        print(f"[INFO] 启动分页爬取（起始页：{START_PAGE}，目标页数：{MAX_PAGES}）...")

        for page_num in range(START_PAGE, MAX_PAGES + 1):
            url = f"{base_url}/page/{page_num}"
            
            # ** 核心修改：将 page_num 传入 process_page **
            count = self.process_page(url, tag, csv_path, page_num)
            total += count
            
            print(f"[进度] 已完成 {page_num}/{MAX_PAGES} 页。")
            
            time.sleep(random.uniform(1, PAGE_SLEEP))

        print(f"[完成] 爬取结束，总计 {total} 条。")
        self.driver.quit()


if __name__ == '__main__':
    # 配置保存路径
    save_dir = r'R:\py\Auto_Image-Spider\Eiginleiki\data'
    csv_path = os.path.join(save_dir, 'all_eiginleiki_records.csv')

    try:
        crawler = EiginleikiCrawler(CHROME_DRIVER_PATH)
        crawler.run(START_URL, TAG_NAME, csv_path)
    except Exception as e:
        print(f"[程序退出] 异常: {e}")