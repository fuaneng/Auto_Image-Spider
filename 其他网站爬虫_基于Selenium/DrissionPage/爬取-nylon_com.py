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
START_URL = 'https://www.nylon.com/' 
TAG_NAME = 'nylon_Homepage_Data' 
# 请确保您的 ChromeDriver 路径是正确的，并且与您的 Chrome 浏览器版本兼容
CHROME_DRIVER_PATH = r'C:\Program Files\Google\chromedriver-win64\chromedriver.exe'
# ----------------------------------------------------------------------


class nylon:
    def __init__(self, chrome_driver_path):
        """
        初始化爬虫类和所有资源，包括 WebDriver 和 Redis。
        """
        print("[INFO] 正在初始化 WebDriver...")
        try:
            service = Service(executable_path=chrome_driver_path)
            options = Options()
            # 设置浏览器选项，规避自动化检测
            options.add_experimental_option("excludeSwitches", ["enable-automation"])
            options.add_experimental_option('useAutomationExtension', False)
            user_agent = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
            options.add_argument(f'user-agent={user_agent}')
            
            # 启用无头模式
            options.add_argument('--headless') 
            
            # ****** 修正点：设置更大的 4K 视窗尺寸 ******
            options.add_argument('--window-size=3840,2160')
            
            self.driver = webdriver.Chrome(service=service, options=options)
        except WebDriverException as e:
            print(f"[致命错误] WebDriver 启动失败，请检查 ChromeDriver 路径/版本与 Chrome 浏览器兼容性：{e}")
            raise

        self.base_url = START_URL
        
        # Redis 连接配置和检查
        self.redis = redis.Redis(
            host='localhost',
            port=6379, 
            db=0,
            decode_responses=True
        )
        try:
            self.redis.ping()
            print("[√] Redis 连接成功。")
        except RedisConnectionError:
            print("[致命错误] Redis 连接失败。请确保 Redis 已启动并监听在正确端口。")
            raise
            
        self.redis_key = 'image_md5_set_nylon'
        # 用于 CSV 写入的线程锁
        self.csv_lock = threading.Lock()
        
        # 用于同一次会话去重
        self.processed_elements_md5 = set() 


    def clean_image_url(self, url):
        """
        清除图片 URL 中的查询参数（? 后面的部分），获取原始图片 URL。
        """
        if not url:
            return ""
        # 使用正则表达式匹配 ? 之前的部分
        match = re.split(r'\?', url)
        return match[0] if match else url


    def get_images(self, tag, csv_path, image_elements_to_process):
        """
        解析最新加载的图片元素，获取文章标题和图片URL，并进行去重和存储。
        """
        if not image_elements_to_process:
            return
            
        print(f"--- 正在解析最新加载的 {len(image_elements_to_process)} 个图片容器...")
        
        new_data_count = 0
        for card_ele in image_elements_to_process: 
            element_id_hash = hash(card_ele) 
            
            if element_id_hash in self.processed_elements_md5:
                continue 

            try:
                # 标题定位: <p class="_CD">
                title_element = card_ele.find_element(By.CSS_SELECTOR, 'div.Jhp > p._CD') 
                # 图片元素定位
                img_element = card_ele.find_element(By.TAG_NAME, 'img')
                
                title = title_element.text.strip()
                
                # 图片 URL 获取
                image_url_raw = img_element.get_attribute('src')
                if not image_url_raw:
                    image_url_raw = img_element.get_attribute('data-src')

                # 清理 URL
                image_url_cleaned = self.clean_image_url(image_url_raw)
                
                
                if image_url_cleaned and title:
                    # Redis 级别的去重
                    md5_hash = hashlib.md5(image_url_cleaned.encode('utf-8')).hexdigest()
                    
                    if not self.redis.sismember(self.redis_key, md5_hash):
                        self.redis.sadd(self.redis_key, md5_hash)
                        
                        image_name = image_url_cleaned.split('/')[-1]
                        
                        self.write_to_csv(title, image_name, image_url_cleaned, csv_path, tag)
                        new_data_count += 1
                
                # 标记该元素已处理
                self.processed_elements_md5.add(element_id_hash)
                
            except NoSuchElementException:
                continue
            except Exception as e:
                print(f"[✗] 处理图片异常: {e}")
                continue
        print(f"--- 本轮解析新增 {new_data_count} 条数据。")


    def write_to_csv(self, title, name, url, csv_path, tag):
        """将图片信息写入 CSV 文件"""
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

    
    def crawl_page(self, start_url, tag, csv_path):
        """
        核心爬取逻辑：分段滚动页面并解析新加载的图片元素。
        使用平滑滚动和显式等待，提高加载稳定性并处理初始弹窗。
        """
        # --- 滚动常量定义 ---
        SCROLL_PAUSE_TIME = 3.0   
        SCROLL_STEPS = 2      
        SMALL_SCROLL_AMOUNT = 600 
        MAX_SCROLLS = 15 # 滚动尝试次数
        
        # 元素选择器
        image_card_selector = 'div.AYM.maG' 
        main_content_selector = 'div.YS_' # 假设这是包含所有内容的最外层容器
        
        # 将等待时间增加到 30 秒，以应对网络波动和复杂加载
        wait = WebDriverWait(self.driver, 30) 
        
        # --- 导航和初始等待 ---
        try:
            print(f"[INFO] 导航到起始页: {start_url}")
            self.driver.get(start_url)
            
            # 等待主要的顶级内容容器出现
            wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, main_content_selector)))
            print("[√] 初始页面加载稳定。")
            
            # 尝试处理 Cookie/通知弹窗 (解决初始加载失败的关键一步)
            cookie_button_selector = '#onetrust-accept-btn-handler, button[aria-label*="accept"], .cc-compliance a'
            
            try:
                # 使用 find_elements 避免在找不到时抛出异常
                cookie_buttons = self.driver.find_elements(By.CSS_SELECTOR, cookie_button_selector)
                for button in cookie_buttons:
                    if button.is_displayed() and button.is_enabled():
                        button.click()
                        print("[INFO] 成功点击并关闭了 Cookie 弹窗。")
                        time.sleep(2) 
                        break # 点击一个按钮后即可退出
            except Exception:
                pass # 忽略所有与弹窗相关的异常

        except Exception as e:
            print(f"[✗] 初始加载失败: {e}")
            if isinstance(e, TimeoutException):
                 print(f"[提示] 超时可能原因：选择器'{main_content_selector}'错误或网络太慢。")
            return False

        # --- 初始化和顶级容器获取 ---
        processed_count = 0
        scroll_cycle_count = 0
        
        try:
            # 获取顶级内容容器，后续所有搜索都将在这个容器内进行
            main_content_element = self.driver.find_element(By.CSS_SELECTOR, main_content_selector)
        except NoSuchElementException:
            print(f"[致命错误] 未找到顶级内容容器: {main_content_selector}。程序退出。")
            return False

        # --- 核心滚动加载循环 ---
        while scroll_cycle_count < MAX_SCROLLS:
            print(f"\n==== 开始第 {scroll_cycle_count + 1} 轮滚动周期和解析 ====")
            
            # 1. 检查和增量解析 
            all_elements = main_content_element.find_elements(By.CSS_SELECTOR, image_card_selector)
            current_count = len(all_elements)

            print(f"[INFO] 检查前，当前共有 {current_count} 个图片卡片，已处理 {processed_count} 个。")
            
            if current_count > processed_count:
                # [存储数据]：发现新内容，进行增量解析和存储
                print("[√] 新内容加载完成，正在进行增量解析和存储...")
                new_elements_to_process = all_elements[processed_count:]
                
                self.get_images(tag, csv_path, new_elements_to_process)
                processed_count = current_count
                
                # 确保最后一个元素进入视图，准备滚动
                last_element = all_elements[-1]
                self.driver.execute_script("arguments[0].scrollIntoView(true);", last_element)
                time.sleep(1.0 + random.uniform(0.5, 1.0)) 
            
            # 2. 执行平滑、多次的小幅度滚动
            scroll_before = self.driver.execute_script("return window.scrollY")
            
            print(f"[INFO] 执行 {SCROLL_STEPS} 次小幅度滚动以触发下一批增量加载...")
            for step in range(SCROLL_STEPS):
                # 每次滚动 SMALL_SCROLL_AMOUNT 像素
                self.driver.execute_script(f"window.scrollBy(0, {SMALL_SCROLL_AMOUNT});")
                # 小等待，模拟用户平滑滚动
                time.sleep(0.5 + random.uniform(0.1, 0.5)) 
            
            scroll_after = self.driver.execute_script("return window.scrollY")
            time.sleep(SCROLL_PAUSE_TIME) # 滚动结束后大等待，让新内容有时间加载

            # 3. 检查是否到达页面底部 
            final_elements = main_content_element.find_elements(By.CSS_SELECTOR, image_card_selector)
            final_count = len(final_elements)
            
            if final_count == processed_count:
                # 元素数量没有增加
                # 检查滚动条是否停止移动或已触及页面底部
                is_at_bottom = self.driver.execute_script("return window.innerHeight + window.scrollY;") >= self.driver.execute_script("return document.body.scrollHeight;")
                
                if scroll_after <= scroll_before or is_at_bottom:
                    print(f"[完成] 滚动条已达底部，且未发现新内容。已爬取到最后一页 (共 {final_count} 个卡片)。")
                    break
                else:
                    # 滚动条移动了，但元素数量没变，继续下一轮尝试
                    print("[INFO] 滚动条移动了，但元素数量未增加。继续下一轮尝试。")
            
            scroll_cycle_count += 1
            
            if scroll_cycle_count >= MAX_SCROLLS:
                print(f"[警告] 已达到最大滚动次数 {MAX_SCROLLS}，停止爬取。")
                break
                
        return True 


    def main(self):
        """主程序入口，配置路径并启动爬取任务。"""
        
        # 数据保存路径
        save_path_all = r'D:\work\爬虫\爬虫数据\nylon'
        os.makedirs(save_path_all, exist_ok=True)
        
        start_url = START_URL
        title = TAG_NAME
        csv_path = os.path.join(save_path_all, 'all_nylon_records.csv')
        
        print(f'\n[INFO] 正在爬取【{title}】 - {start_url}')
        print(f'[INFO] 所有数据将保存到：{csv_path}')
        
        # 启动爬取任务
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
        nylon(CHROME_DRIVER_PATH).main()
    except (WebDriverException, RedisConnectionError):
        print("\n[程序退出] 请先解决上述致命错误（如 ChromeDriver 或 Redis）后再重试。")