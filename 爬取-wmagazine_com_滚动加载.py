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
START_URL = 'https://www.wmagazine.com/'
TAG_NAME = 'wmagazine_Homepage_Data'
# 确保你的 ChromeDriver 路径正确
CHROME_DRIVER_PATH = r'C:\Program Files\Google\chromedriver-win64\chromedriver.exe'

# 滚动优化配置
SCROLL_PAUSE_TIME = 3.0      # 每次滚动周期结束后等待新内容加载的时间（秒）
SCROLL_STEPS = 2             # 在两次检查元素之间，执行的小幅度滚动次数
SMALL_SCROLL_AMOUNT = 600    # 每次小滚动移动的像素距离
MAX_SCROLLS = 10000            # 最大滚动检查次数，防止无限循环
# ----------------------------------------------------------------------


class wmagazine:
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
            options.add_argument("--disable-blink-features=AutomationControlled") # 避免被检测
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
        except RedisConnectionError as e:
            print(f"无法连接到 Redis 服务器 'localhost:6379'。请确保 Redis 已启动并监听在正确端口。错误: {e}")
            raise

        self.redis_key = 'image_md5_set_wmagazine'
        self.csv_lock = threading.Lock()
        
    def _clean_url(self, url):
        """
        使用正则表达式移除图片 URL 中问号 (?) 及其后面的所有参数。
        """
        if not url:
            return ""
        # 匹配从问号 (?) 开始到字符串结尾的所有内容，并替换为空
        return re.sub(r'\?.*', '', url)

    def get_images(self, tag, csv_path, image_elements_to_process):
        """
        解析最新加载的图片元素，获取文章标题 (span.Gyx) 和图片URL，并进行去重和存储。
        """
        if not image_elements_to_process:
            return
            
        print(f"--- 正在解析最新加载的 {len(image_elements_to_process)} 个图片容器...")
        
        extracted_count = 0
        
        for card_ele in image_elements_to_process: 
            try:
                # 1. 定位图片元素：使用 img.N4z 确保稳定性
                img_element = card_ele.find_element(By.CSS_SELECTOR, 'img.N4z')
                
                # 2. 定位标题元素 (span.Gyx)
                title_element = card_ele.find_element(By.CSS_SELECTOR, 'span.Gyx')
                
                title = title_element.text.strip()
                
                # 3. 获取图片 URL
                image_url = img_element.get_attribute('src')
                
                # 4. 清理 URL
                image_url_cleaned = self._clean_url(image_url)

                
                if image_url_cleaned and title:
                    md5_hash = hashlib.md5(image_url_cleaned.encode('utf-8')).hexdigest()
                    
                    # Redis 去重检查
                    if not self.redis.sismember(self.redis_key, md5_hash):
                        self.redis.sadd(self.redis_key, md5_hash)
                        
                        image_name = image_url_cleaned.split('/')[-1]
                        
                        self.write_to_csv(title, image_name, image_url_cleaned, csv_path, tag)
                        extracted_count += 1
                        
            except NoSuchElementException as e:
                # 找不到子元素，跳过当前卡片
                continue
            except Exception as e:
                print(f"[✗] 处理图片异常: {e}")
                continue
        
        print(f"--- 本轮解析完成，新增 {extracted_count} 条数据。")


    def write_to_csv(self, title, name, url, csv_path, tag):
        """将图片信息写入 CSV 文件，确保线程安全。"""
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
        核心爬取逻辑：导航、初始解析、基于多次小幅度滚动的增量加载和分段解析。
        """
        # [主要修改点 1] 顶级内容容器，用于限定搜索范围
        main_content_selector = 'body > div.YSb > div.F0j' 
        # [关键修正] 使用属性包含选择器，捕获所有以 I2g 开头的图片卡片容器
        image_card_selector = 'div[class*="I2g"]' 
        
        wait = WebDriverWait(self.driver, 20)
        
        # 导航和初始等待
        try:
            print(f"[INFO] 导航到起始页: {start_url}")
            self.driver.get(start_url)
            # 等待主要的顶级内容容器出现
            wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, main_content_selector)))
            print("[√] 初始页面加载稳定。")
        except Exception as e:
            print(f"[✗] 初始加载失败: {e}")
            return False

        processed_count = 0
        scroll_cycle_count = 0
        
        # 获取顶级内容容器，后续所有搜索都将在这个容器内进行
        try:
            main_content_element = self.driver.find_element(By.CSS_SELECTOR, main_content_selector)
        except NoSuchElementException:
            print(f"[致命错误] 未找到顶级内容容器: {main_content_selector}。程序退出。")
            return False

        while scroll_cycle_count < MAX_SCROLLS:
            print(f"\n==== 开始第 {scroll_cycle_count + 1} 轮滚动周期和解析 ====")
            
            # 1. 检查和增量解析 (分段存储点：在顶级容器内搜索所有卡片)
            # 使用修正后的选择器查找所有包含 I2g 的卡片
            all_elements = main_content_element.find_elements(By.CSS_SELECTOR, image_card_selector)
            current_count = len(all_elements)

            print(f"[INFO] 检查前，当前共有 {current_count} 个图片卡片，已处理 {processed_count} 个。")
            
            if current_count > processed_count:
                # [存储数据]：发现新内容，立即进行解析和存储
                print("[√] 新内容加载完成，正在进行增量解析和存储...")
                new_elements_to_process = all_elements[processed_count:]
                self.get_images(tag, csv_path, new_elements_to_process)
                processed_count = current_count
                
                # 确保最后一个元素进入视图，准备滚动
                last_element = all_elements[-1]
                self.driver.execute_script("arguments[0].scrollIntoView(true);", last_element)
                time.sleep(SCROLL_PAUSE_TIME)
            
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
                # 如果元素数量没有增加
                if scroll_after <= scroll_before:
                    # 且滚动条没有移动（或移动极少），说明已达底部
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
        
        save_path_all = r'D:\work\爬虫\爬虫数据\wmagazine'
        os.makedirs(save_path_all, exist_ok=True)
        
        start_url = START_URL
        title = TAG_NAME
        csv_path = os.path.join(save_path_all, 'all_wmagazine_records.csv')
        
        print(f'\n[INFO] 正在爬取【{title}】 - {start_url}')
        print(f'[INFO] 所有数据将保存到：{csv_path}')
        
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
        wmagazine(CHROME_DRIVER_PATH).main()
    except (WebDriverException, RedisConnectionError):
        # 致命错误信息已在初始化中打印
        print("\n[程序退出] 请先解决上述致命错误后再重试。")