from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
from selenium.common.exceptions import TimeoutException, NoSuchElementException # 导入 Selenium 常见异常
import os
import time
import hashlib
import redis
import csv
import threading
import random
import re  # 导入 re 模块用于 URL 清理

class freestocks:
    def __init__(self, chrome_driver_path):
        """
        初始化爬虫类，使用标准 Selenium 和 Service 对象。
        
        Args:
            chrome_driver_path: 本地 ChromeDriver 可执行文件的完整路径。
        """
        service = Service(executable_path=chrome_driver_path)
        
        options = Options()
        # 禁用自动化控制栏
        options.add_experimental_option("excludeSwitches", ["enable-automation"])
        options.add_experimental_option('useAutomationExtension', False)
        # 设置 User-Agent
        user_agent = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        options.add_argument(f'user-agent={user_agent}')
        self.driver = webdriver.Chrome(service=service, options=options)

        self.base_url = 'https://freestocks.org/search/'
        
        # Redis 连接配置
        self.redis = redis.Redis(
            host='localhost',
            port=6379,
            db=0,
            decode_responses=True
        )
        self.redis_key = 'image_md5_set_freestocks'
        # 写入 CSV 的线程锁
        self.csv_lock = threading.Lock()

    def get_images(self, tag, csv_path):
        """解析当前页面上的图片信息，处理滚动加载并存储 URL 和标题"""
        print(f"--- 正在解析【{tag}】的图片列表...")

        # 图片的一级容器 CSS 选择器
        image_card_selector = 'div.img-wrap.jg-entry.jg-entry-visible' 
        
        wait = WebDriverWait(self.driver, 20)
        
        # 步骤 1: 等待初始图片容器加载
        try:
            wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, image_card_selector)))
            print("[√] 图片容器已加载。")
            time.sleep(random.uniform(1.5, 3.0))
        except TimeoutException:
            print("[✗] 等待图片容器超时，可能是没有搜索结果或页面加载慢。")
            return
        except Exception as e:
            print(f"[✗] 等待图片容器时发生未知异常: {e}")
            return

        # 步骤 2: 滚动加载所有图片
        last_count = 0
        while True:
            image_elements = self.driver.find_elements(By.CSS_SELECTOR, image_card_selector)
            current_count = len(image_elements)
            
            # 停止加载条件：如果当前数量和上次数量一致，且数量大于 0
            if current_count == last_count and current_count > 0:
                print(f"所有图片 ({current_count} 个) 已加载完毕，准备开始解析。")
                break
            # 退出条件：如果两轮都找不到图片
            if current_count == 0 and last_count == 0:
                print("当前页面没有找到图片元素，跳过。")
                break

            # 滚动到底部加载更多
            if current_count > 0:
                last_element = image_elements[-1]
                self.driver.execute_script("arguments[0].scrollIntoView({behavior: 'smooth', block: 'end'});", last_element)
                
                print(f"滚动到第 {current_count} 个元素，继续加载...")
            
            last_count = current_count
            time.sleep(random.uniform(2.0, 4.0))

        image_elements = self.driver.find_elements(By.CSS_SELECTOR, image_card_selector)
        print(f"找到 {len(image_elements)} 个图片卡片进行解析。")
        
        # 步骤 3: 解析图片信息
        for card_ele in image_elements: 
            try:
                # 查找包含标题和图片的 <a> 标签
                a_element = card_ele.find_element(By.TAG_NAME, 'a')
                
                # 从 <a> 标签中提取标题 (title 属性)
                title = a_element.get_attribute('title') 
                
                # 在 <a> 标签内部查找 img 元素
                img_element = a_element.find_element(By.TAG_NAME, 'img')
                
                # 从 img 元素的 src 属性中提取 URL
                image_url = img_element.get_attribute('src')
                
                # 清理 URL: 使用正则表达式去除 "-数字x数字." 部分
                # 例如：将 "-1024x683.jpg" 替换为 ".jpg"
                image_url_cleaned = re.sub(r'-\d+x\d+\.', '.', image_url)
                
                if image_url_cleaned and title:
                    md5_hash = hashlib.md5(image_url_cleaned.encode('utf-8')).hexdigest()
                    if not self.redis.sismember(self.redis_key, md5_hash):
                        self.redis.sadd(self.redis_key, md5_hash)
                        
                        image_name = image_url_cleaned.split('/')[-1]
                        
                        self.write_to_csv(title, image_name, image_url_cleaned, csv_path, tag)
                    else:
                        print(f"[跳过] 重复图片: {image_url_cleaned.split('/')[-1]}")
                
            except Exception as e:
                print(f"[✗] 处理图片异常: {e}")
                continue

    def write_to_csv(self, title, name, url, csv_path, tag):
        """将图片信息写入 CSV 文件"""
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
        """按页爬取，处理翻页逻辑和页面稳定性，使用 JavaScript 点击避免遮挡问题。"""
        # 下一页的翻页元素
        next_page_selector = 'a.next.page-numbers'
        # 图片容器选择器，用于等待新页面加载稳定
        image_card_selector = 'div.img-wrap.jg-entry.jg-entry-visible'
        
        current_page_num = 1
        wait = WebDriverWait(self.driver, 20)
        
        while True:
            print(f"\n==== 开始爬取【{tag}】第 {current_page_num} 页 ====")
            
            # 1. 爬取当前页面的图片（包含滚动加载）
            # get_images 内部处理了页面的图片加载和滚动稳定性
            self.get_images(tag, csv_path)
            
            # 2. 翻页逻辑
            try:
                # 查找下一页元素，等待它变得可点击
                next_button = wait.until(
                    EC.element_to_be_clickable((By.CSS_SELECTOR, next_page_selector))
                )
                
                # ***关键使用 JavaScript 点击绕过元素遮挡***
                print(f"[INFO] 找到下一页按钮，准备使用 JS 翻页到第 {current_page_num + 1} 页...")
                self.driver.execute_script("arguments[0].click();", next_button)
                # **********************************************
                
                current_page_num += 1
                
                # 3. 等待下一页图片容器加载稳定
                # 显式等待至少一个图片容器出现在新页面上，确保页面跳转和内容加载完成。
                wait.until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, image_card_selector))
                )
                print("[√] 新页面加载稳定，检测到图片容器。")
                
                # 增加随机延迟，模拟真实用户行为
                time.sleep(random.uniform(2.0, 4.0)) 
                
                # 继续 while 循环，爬取新页面
                
            except (TimeoutException, NoSuchElementException):
                # 找不到下一页元素时，退出循环
                print(f"[完成] 标签【{tag}】已爬取到最后一页 (第 {current_page_num} 页)。")
                return True 
            except Exception as e:
                # 其他翻页错误
                print(f"[✗] 翻页时发生错误: {e}")
                return False

    def main(self):
        # --- 配置路径：请修改为你的实际路径 ---
        save_path_all = r'D:\work\爬虫\爬虫数据\freestocks'
        tag_file_path = r"D:\work\爬虫\ram_tag_list.txt"
        # -------------------------------------
        
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
            try:
                # 构造搜索 URL: https://freestocks.org/search/tag/
                search_url = f'{self.base_url}{tag}/' 
                self.driver.get(search_url)
                time.sleep(random.uniform(3.0, 5.0)) # 初始页面加载等待
                
                success = self.crawl_page(tag, csv_path)
                
                if success:
                    print(f'[完成] 【{tag}】全部页面爬取与去重完毕。\n')
                else:
                    print(f'[失败] 【{tag}】爬取失败，请检查网络或网站结构。\n')
            except Exception as e:
                print(f"[✗] 爬取【{tag}】时发生错误: {e}")

        self.driver.quit()

if __name__ == '__main__':
    # --- 配置 ChromeDriver 路径：请修改为你的实际路径 ---
    chrome_driver_path = r'C:\Program Files\Google\chromedriver-win64\chromedriver.exe'
    # --------------------------------------------------
    
    spider = freestocks(chrome_driver_path)
    spider.main()