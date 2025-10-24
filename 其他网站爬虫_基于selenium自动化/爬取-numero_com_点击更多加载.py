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

# ----------------------------------------------------------------------
# 配置项
# ----------------------------------------------------------------------
START_URL = 'https://numero.com.cn/' 
TAG_NAME = 'Numero_Homepage_Data' 
CHROME_DRIVER_PATH = r'C:\Program Files\Google\chromedriver-win64\chromedriver.exe'
# ----------------------------------------------------------------------


class numero:
    def __init__(self, chrome_driver_path):
        """
        初始化爬虫类和所有资源，包括 WebDriver 和 Redis。
        """
        print("[INFO] 正在初始化 WebDriver...")
        try:
            service = Service(executable_path=chrome_driver_path)
            options = Options()
            # 设置浏览器选项
            options.add_experimental_option("excludeSwitches", ["enable-automation"])
            options.add_experimental_option('useAutomationExtension', False)
            user_agent = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
            options.add_argument(f'user-agent={user_agent}')
            self.driver = webdriver.Chrome(service=service, options=options)
        except WebDriverException as e:
            print(f"[致命错误] WebDriver 启动失败，请检查 ChromeDriver 路径/版本与 Chrome 浏览器兼容性：{e}")
            # 如果驱动启动失败，抛出异常以阻止程序继续
            raise

        self.base_url = START_URL
        
        # Redis 连接配置和检查
        self.redis = redis.Redis(
            host='localhost',
            port=8379, # 确保这是你 Redis 实际监听的端口
            db=0,
            decode_responses=True
        )
        try:
            self.redis.ping()
            print("[√] Redis 连接成功。")
        except RedisConnectionError:
            print("[致命错误] 无法连接到 Redis 服务器 'localhost:8379'。请确保 Redis 已启动并监听在正确端口。")
            raise
            
        self.redis_key = 'image_md5_set_numero'
        # 用于 CSV 写入的线程锁
        self.csv_lock = threading.Lock()


    def get_images(self, tag, csv_path, image_elements_to_process):
        """
        解析最新加载的图片元素，获取文章标题和图片URL，并进行去重和存储。
        """
        if not image_elements_to_process:
            return
            
        print(f"--- 正在解析最新加载的 {len(image_elements_to_process)} 个图片容器...")
        
        for card_ele in image_elements_to_process: 
            try:
                # 定位标题和图片元素
                img_element = card_ele.find_element(By.TAG_NAME, 'img')
                title_element = card_ele.find_element(By.CSS_SELECTOR, 'hgroup a h2.numero-h2')
                
                title = title_element.text.strip()
                
                # 优先获取 data-src-large 属性以获取大图URL
                image_url_large = img_element.get_attribute('data-src-large')
                
                if image_url_large:
                    # 移除 _1600x0. 后缀以获得原始文件名 URL
                    image_url_cleaned = image_url_large.replace('_1600x0.', '.')
                else:
                    # 备用方案：使用 src 属性并移除 _640x0. 后缀
                    image_url = img_element.get_attribute('src')
                    image_url_cleaned = image_url.replace('_640x0.', '.')

                
                if image_url_cleaned and title:
                    md5_hash = hashlib.md5(image_url_cleaned.encode('utf-8')).hexdigest()
                    
                    # Redis 去重检查
                    if not self.redis.sismember(self.redis_key, md5_hash):
                        self.redis.sadd(self.redis_key, md5_hash)
                        
                        image_name = image_url_cleaned.split('/')[-1]
                        
                        self.write_to_csv(title, image_name, image_url_cleaned, csv_path, tag)
                
            except NoSuchElementException:
                # 找不到子元素，跳过当前卡片
                continue
            except Exception as e:
                print(f"[✗] 处理图片异常: {e}")
                continue


    def write_to_csv(self, title, name, url, csv_path, tag):
        """将图片信息写入 CSV 文件"""
        try:
            with self.csv_lock:
                # 检查文件是否存在，决定是否写入表头
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

    
    def crawl_page(self, start_url, tag, csv_path):
        """
        核心爬取逻辑：导航、初始解析、循环点击“更多”、等待、精确滚动和分段解析。
        """
        more_button_selector = 'a.numero-button1.js-more-article'
        image_card_selector = 'article.article-thumb.slide'
        
        current_page_num = 1
        wait = WebDriverWait(self.driver, 20)
        
        # 导航和初始等待
        try:
            print(f"[INFO] 导航到起始页: {start_url}")
            self.driver.get(start_url)
            wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, image_card_selector)))
            print("[√] 初始页面加载稳定。")
        except Exception as e:
            print(f"[✗] 初始加载失败: {e}")
            return False

        # --- 初始页处理 ---
        all_elements = self.driver.find_elements(By.CSS_SELECTOR, image_card_selector)
        self.get_images(tag, csv_path, all_elements)
        print(f"[INFO] 第 1 轮初始解析完成，找到 {len(all_elements)} 个元素。")
        current_page_num += 1

        while True:
            print(f"\n==== 开始第 {current_page_num} 轮加载和解析 ====")
            
            # 1. 记录当前元素总数
            initial_count = len(self.driver.find_elements(By.CSS_SELECTOR, image_card_selector))
            print(f"[INFO] 点击“更多”前，当前页面共有 {initial_count} 个图片卡片。")
            
            # 2. 查找并点击“更多”按钮
            try:
                # 等待“更多”按钮变得可点击
                more_button = wait.until(
                    EC.element_to_be_clickable((By.CSS_SELECTOR, more_button_selector))
                )
                
                print(f"[INFO] 找到“更多”按钮，准备点击加载第 {current_page_num} 批新图片...")
                self.driver.execute_script("arguments[0].click();", more_button)
                
                # 等待数据接口返回
                time.sleep(random.uniform(2.0, 3.0))

                # 3. 等待新图片加载完成（通过数量增加来判断）
                wait.until(
                    lambda driver: len(driver.find_elements(By.CSS_SELECTOR, image_card_selector)) > initial_count
                )
                
                # 4. 提取最新加载的部分
                all_new_elements = self.driver.find_elements(By.CSS_SELECTOR, image_card_selector)
                newly_loaded_elements = all_new_elements[initial_count:]
                
                if not newly_loaded_elements:
                    # 理论上不会发生，但作为安全退出条件
                    print("[完成] 检测到元素数量增加，但新元素列表为空，停止爬取。")
                    break

                # 5. **精确滚动到最新加载的第一个元素**
                first_new_element = newly_loaded_elements[0]
                self.driver.execute_script("arguments[0].scrollIntoView({behavior: 'smooth', block: 'center'});", first_new_element)
                
                print(f"[√] 已精确滚动到最新加载的第一个元素，等待图片懒加载。")
                time.sleep(random.uniform(1.0, 2.0))
                
                # 6. 分段解析和存储最新图片
                self.get_images(tag, csv_path, newly_loaded_elements)
                print(f"[√] 第 {current_page_num} 批图片分段解析完成，新增 {len(newly_loaded_elements)} 个元素。")
                
                current_page_num += 1
                
            except TimeoutException:
                # 找不到“更多”按钮 或 新图片数量没有增加，说明已经加载完毕
                final_count = len(self.driver.find_elements(By.CSS_SELECTOR, image_card_selector))
                print(f"[完成] 标签【{tag}】已爬取到最后一页 (共 {final_count} 个卡片)。")
                return True 
            except Exception as e:
                print(f"[✗] 翻页/加载时发生错误: {e}")
                return False

    def main(self):
        """主程序入口，配置路径并启动爬取任务。"""
        
        save_path_all = r'D:\work\爬虫\爬虫数据\numero'
        os.makedirs(save_path_all, exist_ok=True)
        
        start_url = START_URL
        title = TAG_NAME
        # 将所有数据保存到同一个 CSV 文件
        csv_path = os.path.join(save_path_all, 'all_numero_records.csv')
        
        print(f'\n[INFO] 正在爬取【{title}】 - {start_url}')
        print(f'[INFO] 所有数据将保存到：{csv_path}')
        
        # 直接使用当前实例的 crawl_page 方法
        success = self.crawl_page(start_url, title, csv_path)
        
        if success:
            print(f'[完成] 【{title}】全部页面爬取与去重完毕。')
        else:
            print(f'[失败] 【{title}】爬取失败，请检查网络或网站结构。')
        
        # 爬取结束后关闭浏览器
        self.driver.quit()

if __name__ == '__main__':
    # 启动主程序：只实例化一次并传入驱动路径
    try:
        numero(CHROME_DRIVER_PATH).main()
    except (WebDriverException, RedisConnectionError):
        print("\n[程序退出] 请先解决上述致命错误后再重试。")