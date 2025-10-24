# from selenium import webdriver
# from selenium.webdriver.chrome.service import Service
# from selenium.webdriver.common.by import By
# from selenium.webdriver.support.ui import WebDriverWait
# from selenium.webdriver.support import expected_conditions as EC
# from selenium.webdriver.chrome.options import Options
# import os
# import time
# import hashlib
# import redis
# import csv
# import threading
# import json
# import random

# class Theinspirationgrid:
#     def __init__(self, chrome_driver_path):
#         """
#         初始化爬虫类，使用标准 Selenium 和 Service 对象。
        
#         Args:
#             chrome_driver_path: 本地 ChromeDriver 可执行文件的完整路径。
#         """
#         # 步骤 1: 使用 Service 类指定 ChromeDriver 的路径
#         service = Service(executable_path=chrome_driver_path)
        
#         # 步骤 2: 配置浏览器选项以增强拟人化
#         options = Options()
#         # 禁用自动化受控标志
#         options.add_experimental_option("excludeSwitches", ["enable-automation"])
#         options.add_experimental_option('useAutomationExtension', False)
#         # 添加一个用户代理
#         user_agent = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
#         options.add_argument(f'user-agent={user_agent}')

#         # 步骤 3: 将 Service 和 Options 对象传递给 Chrome 浏览器实例
#         self.driver = webdriver.Chrome(service=service, options=options)

#         self.base_url = 'https://theinspirationgrid.com/search/'
        
#         self.redis = redis.Redis(
#             host='localhost',
#             port=6379,
#             db=0,
#             decode_responses=True
#         )
#         self.redis_key = 'image_md5_set_Theinspirationgrid'
#         self.csv_lock = threading.Lock()

#     def get_images(self, tag, csv_path):
#         """解析按标签搜索出现的页面上的图片信息并存储 URL 和标题"""
#         print(f"--- 正在解析【{tag}】的图片列表...")
        
#         teaser_container_selector = 'div.sc-1pxsopf-1.hPWAnJ.teaserContainer'
#         wait = WebDriverWait(self.driver, 20)
        
#         try:
#             wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, teaser_container_selector)))
#             print("[√] 图片容器已加载。")
#             time.sleep(random.uniform(1.5, 3.0))
#         except Exception:
#             print("[✗] 等待图片容器超时，跳过此标签。")
#             return

#         last_count = 0
#         while True:
#             image_elements = self.driver.find_elements(By.CSS_SELECTOR, teaser_container_selector)
#             current_count = len(image_elements)
            
#             if current_count == last_count and current_count > 0:
#                 print("所有图片已加载完毕，准备开始解析。")
#                 break
#             # 增加一个判断条件，如果页面上没有图片元素，则跳出循环，避免无限循环
#             if current_count == 0 and last_count == 0:
#                  print("当前页面没有找到图片元素，跳过。")
#                  break

#             last_element = image_elements[-1]
#             self.driver.execute_script("arguments[0].scrollIntoView({behavior: 'smooth', block: 'end'});", last_element)
            
#             print(f"滚动到第 {current_count} 个元素，继续加载...")
#             last_count = current_count
#             time.sleep(random.uniform(2.0, 4.0))

#         image_elements = self.driver.find_elements(By.CSS_SELECTOR, teaser_container_selector)
#         print(f"找到 {len(image_elements)} 个图片卡片。")
        
#         for img_ele in image_elements:
#             try:
#                 title_ele = img_ele.find_element(By.CSS_SELECTOR, 'h3.title')
#                 title = title_ele.text.strip()
                
#                 img_element = img_ele.find_element(By.CSS_SELECTOR, 'picture img')
#                 image_url = img_element.get_attribute('src')
                
#                 if not image_url:
#                     srcset = img_element.get_attribute('srcset')
#                     if srcset:
#                         best_url = max(srcset.split(','), key=lambda x: int(x.strip().split()[-1].replace('w', ''))).strip().split()[0]
#                         image_url = best_url

#                 if image_url:
#                     md5_hash = hashlib.md5(image_url.encode('utf-8')).hexdigest()
#                     if not self.redis.sismember(self.redis_key, md5_hash):
#                         self.redis.sadd(self.redis_key, md5_hash)
                        
#                         image_name = image_url.split('/')[-1]
                        
#                         self.write_to_csv(title, image_name, image_url, csv_path, tag)
#                     else:
#                         print(f"[跳过] 重复图片: {image_url.split('/')[-1]}")
            
#             except Exception as e:
#                 print(f"[✗] 处理图片异常: {e}")
#                 continue

#     def write_to_csv(self, title, name, url, csv_path, tag):
#         """将图片信息写入 CSV 文件"""
#         try:
#             with self.csv_lock:
#                 with open(csv_path, 'a', newline='', encoding='utf-8-sig') as f:
#                     writer = csv.writer(f)
#                     if f.tell() == 0:
#                         writer.writerow(['Title', 'ImageName', 'URL', "TAG"])
#                     writer.writerow([title, name, url, tag])
#                     f.flush()
#             print(f'[√] 写入成功：{name}')
#         except Exception as e:
#             print(f'[✗] 写入 CSV 异常：{name} -> {e}')

#     def crawl_page(self, tag, csv_path):
#         """按页爬取"""
#         while True:
#             self.get_images(tag, csv_path)
            
#             try:
#                 next_page_btn = self.driver.find_element(By.XPATH, '//button[text()="Next"]')
                
#                 if next_page_btn and next_page_btn.get_attribute('disabled') is None:
#                     print("--- 翻到下一页...")
#                     next_page_btn.click()
#                     time.sleep(random.uniform(2.0, 4.0))
#                 else:
#                     print("最后一页，爬取完成。")
#                     return True
#             except Exception as e:
#                 print(f"[✗] 翻页失败: {e}")
#                 return False

#     def main(self):
#         save_path_all = r'D:\work\爬虫\爬虫数据\Theinspirationgrid'
#         tag_file_path = r"D:\work\爬虫\ram_tag_list.txt"
        
#         os.makedirs(save_path_all, exist_ok=True)
        
#         try:
#             with open(tag_file_path, 'r', encoding='utf-8') as f:
#                 tags = [line.strip() for line in f if line.strip()]
#         except FileNotFoundError:
#             print(f"[错误] 标签文件未找到: {tag_file_path}")
#             return
        
#         print(f"--- 找到 {len(tags)} 个标签。")
        
#         csv_path = os.path.join(save_path_all, 'all_records.csv')
        
#         for tag in tags:
#             print(f'\n[INFO] 正在爬取【{tag}】 ...')

#             try:
#                 search_url = f'{self.base_url}?q={tag}'
#                 self.driver.get(search_url)
#                 time.sleep(random.uniform(3.0, 5.0))
                
#                 success = self.crawl_page(tag, csv_path)
                
#                 if success:
#                     print(f'[完成] 【{tag}】全部页面爬取与去重完毕。\n')
#                 else:
#                     print(f'[失败] 【{tag}】爬取失败，请检查网络或网站结构。\n')
#             except Exception as e:
#                 print(f"[✗] 爬取【{tag}】时发生错误: {e}")

#         self.driver.quit()

# if __name__ == '__main__':
#     chrome_driver_path = r'C:\Program Files\Google\chromedriver-win32\chromedriver.exe'
#     spider = Theinspirationgrid(chrome_driver_path)
#     spider.main()

# 下面是更新后的代码，改进了滚动加载逻辑，确保在没有新图片加载时能够正确退出循环，并且增加了异常处理和日志记录，以便更好地调试和监控爬虫的运行状态。

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
import json
import random

class Theinspirationgrid:
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

        self.base_url = 'https://theinspirationgrid.com/search/'
        
        self.redis = redis.Redis(
            host='localhost',
            port=6379,
            db=0,
            decode_responses=True
        )
        self.redis_key = 'image_md5_set_Theinspirationgrid'
        self.csv_lock = threading.Lock()

    def get_images(self, tag, csv_path):
        """解析按标签搜索出现的页面上的图片信息并存储 URL 和标题"""
        print(f"--- 正在解析【{tag}】的图片列表...")
        
        teaser_container_selector = 'div.sc-1pxsopf-1.hPWAnJ.teaserContainer'
        wait = WebDriverWait(self.driver, 20)
        
        try:
            wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, teaser_container_selector)))
            print("[√] 图片容器已加载。")
            time.sleep(random.uniform(1.5, 3.0))
        except Exception:
            print("[✗] 等待图片容器超时，跳过此标签。")
            return

        # 优化后的滚动加载逻辑
        max_retries = 3  # 最大重试次数
        retries = 0
        last_count = 0
        while True:
            image_elements = self.driver.find_elements(By.CSS_SELECTOR, teaser_container_selector)
            current_count = len(image_elements)
            
            # 如果数量没有增加，增加重试计数
            if current_count == last_count:
                retries += 1
                if retries >= max_retries:
                    print("已尝试多次滚动，没有新图片加载。认为所有图片已加载完毕。")
                    break
                print(f"未发现新图片，第 {retries} 次重试...")
                time.sleep(random.uniform(2.0, 4.0))
            else:
                retries = 0 # 数量增加，重置重试计数
            
            # 如果当前页面没有图片元素，直接跳出循环
            if current_count == 0:
                print("当前页面没有找到图片元素，跳过。")
                break

            # 滚动到最后一个图片元素的位置
            last_element = image_elements[-1]
            self.driver.execute_script("arguments[0].scrollIntoView({behavior: 'smooth', block: 'end'});", last_element)
            
            print(f"滚动到第 {current_count} 个元素，继续加载...")
            last_count = current_count
            time.sleep(random.uniform(2.0, 4.0))

        # 再次获取所有图片卡片元素，确保获取到最终数量
        image_elements = self.driver.find_elements(By.CSS_SELECTOR, teaser_container_selector)
        print(f"找到 {len(image_elements)} 个图片卡片。")
        
        for img_ele in image_elements:
            try:
                title_ele = img_ele.find_element(By.CSS_SELECTOR, 'h3.title')
                title = title_ele.text.strip()
                
                img_element = img_ele.find_element(By.CSS_SELECTOR, 'picture img')
                image_url = img_element.get_attribute('src')
                
                if not image_url:
                    srcset = img_element.get_attribute('srcset')
                    if srcset:
                        best_url = max(srcset.split(','), key=lambda x: int(x.strip().split()[-1].replace('w', ''))).strip().split()[0]
                        image_url = best_url

                if image_url:
                    # 使用 URL 的 MD5 值进行去重
                    md5_hash = hashlib.md5(image_url.encode('utf-8')).hexdigest()
                    if not self.redis.sismember(self.redis_key, md5_hash):
                        self.redis.sadd(self.redis_key, md5_hash)
                        
                        image_name = image_url.split('/')[-1]
                        
                        self.write_to_csv(title, image_name, image_url, csv_path, tag)
                    else:
                        print(f"[跳过] 重复图片: {image_url.split('/')[-1]} (URL: {image_url})") # 打印URL以便验证
            
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
        """按页爬取"""
        while True:
            self.get_images(tag, csv_path)
            
            try:
                next_page_btn = self.driver.find_element(By.XPATH, '//button[text()="Next"]')
                
                if next_page_btn and next_page_btn.get_attribute('disabled') is None:
                    print("--- 翻到下一页...")
                    next_page_btn.click()
                    time.sleep(random.uniform(2.0, 4.0))
                else:
                    print("最后一页，爬取完成。")
                    return True
            except Exception as e:
                print(f"[✗] 翻页失败: {e}")
                return False

    def main(self):
        save_path_all = r'D:\work\爬虫\爬虫数据\Theinspirationgrid'
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
                search_url = f'{self.base_url}?q={tag}'
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
    chrome_driver_path = r'C:\Program Files\Google\chromedriver-win32\chromedriver.exe'
    spider = Theinspirationgrid(chrome_driver_path)
    spider.main()