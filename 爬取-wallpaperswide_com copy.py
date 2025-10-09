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
import pandas as pd
import threading
import random
import re 
import urllib.parse 
from urllib.parse import urlparse

class wallpaperswide:
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
        # 无头模式（可选）
        # options.add_argument('--headless')
        # 固定分辨率窗口，比如 1920x1080
        options.add_argument('--window-size=1920,1080')
        self.driver = webdriver.Chrome(service=service, options=options)

        self.base_url = 'https://www.lobstertube.com/zh/pornstar/anna-ralphs'
        
        # Redis 连接配置
        self.redis = redis.Redis(
            host='localhost',
            port=6379,
            db=0,
            decode_responses=True
        )
        self.redis_key = 'image_md5_set_anna-ralphs'
        # 写入 CSV 的线程锁
        self.csv_lock = threading.Lock()
        
    
    def scroll_and_load_images(self):
        """滚动页面，加载所有视频封面元素，返回图片卡片元素列表"""
        # 修正: 移除末尾多余的点
        image_card_selector = 'div.card.sub.group' 
        wait = WebDriverWait(self.driver, 20)
        try:
            wait.until(EC.visibility_of_element_located((By.CSS_SELECTOR, image_card_selector)))
            print("[√] 图片容器已加载。")
            time.sleep(random.uniform(1.5, 3.0))
        except TimeoutException:
            print("[✗] 等待图片容器超时，可能是没有搜索结果或页面加载慢。")
            return []
        except Exception as e:
            print(f"[✗] 等待图片容器时发生未知异常: {e}")
            return []

        last_count = 0
        while True:
            image_elements = self.driver.find_elements(By.CSS_SELECTOR, image_card_selector)
            current_count = len(image_elements)
            if current_count == last_count and current_count > 0:
                print(f"所有图片 ({current_count} 个) 已加载完毕，准备开始解析。")
                break
            if current_count == 0 and last_count == 0:
                print("当前页面没有找到图片元素，跳过。")
                break
            if current_count > 0:
                last_element = image_elements[-1]
                self.driver.execute_script("arguments[0].scrollIntoView({behavior: 'smooth', block: 'end'});", last_element)
                print(f"滚动到第 {current_count} 个元素，继续加载...")
            last_count = current_count
            time.sleep(random.uniform(2.0, 4.0))
        image_elements = self.driver.find_elements(By.CSS_SELECTOR, image_card_selector)
        print(f"找到 {len(image_elements)} 个图片卡片进行解析。")
        return image_elements

    def parse_and_save_images(self, image_elements, tag, csv_path):
        """解析图片卡片元素，提取信息并保存到 CSV 文件"""
        for card_ele in image_elements:
            try:
                # 提取 a 标签内的 href 和 title
                a_element = card_ele.find_element(By.CSS_SELECTOR, 'a.item-link.rate-link.relative')
                href = a_element.get_attribute('href')
                title = a_element.get_attribute('title') 
                
                # 补全逻辑：调用写入 CSV 的函数
                if href and title:
                    self.write_to_csv(title, title, href, csv_path, tag)
                
            except NoSuchElementException:
                print("[!] 警告: 未找到图片卡片内的链接或标题元素，跳过此卡片。")
                continue
            except Exception as e:
                print(f"[✗] 解析图片卡片时发生异常: {e}")
                continue

    def get_images(self, tag, csv_path):
        """解析当前页面上的图片信息，处理滚动加载并存储 href 值和标题 title 的值"""
        print(f"--- 正在解析的图片列表...")
        image_elements = self.scroll_and_load_images()
        if image_elements:
            self.parse_and_save_images(image_elements, tag, csv_path)

    def write_to_csv(self, title, name, url, csv_path, tag):
        """使用 pandas 写入 CSV，支持断点续写和更强的数据处理能力"""
        try:
            with self.csv_lock:
                # 读取已有数据
                if os.path.exists(csv_path):
                    try:
                        df = pd.read_csv(csv_path, encoding='utf-8-sig')
                    except pd.errors.EmptyDataError:
                        df = pd.DataFrame(columns=['Title', 'href'])
                else:
                    df = pd.DataFrame(columns=['Title', 'href'])
                    
                # 新数据
                new_row = {'Title': title, 'href': url} # 使用传入的 title 和 url 变量
                
                # 追加
                df = pd.concat([df, pd.DataFrame([new_row])], ignore_index=True)
                
                # 去重
                df.drop_duplicates(subset=['Title', 'href'], inplace=True)
                
                # 保存
                df.to_csv(csv_path, index=False, encoding='utf-8-sig')
            print(f'[√] 写入成功：{name} - {url}')
        except Exception as e:
            print(f'[✗] 写入 CSV 异常：{name} -> {e}')


    def crawl_page(self, tag, csv_path):
        """按页爬取，处理翻页逻辑和页面稳定性，使用 JavaScript 点击避免遮挡问题。"""
        # 下一页按钮使用 XPath 匹配文本 "Next page"
        next_page_xpath = '//a[contains(@class, "button-primary") and contains(@aria-label, "Next page")]'
        # 用于等待页面加载稳定的容器是 div.card.sub.group.
        # 修正: 移除末尾多余的点
        image_card_selector_wait = 'div.card.sub.group' 
        
        current_page_num = 1
        wait = WebDriverWait(self.driver, 20)
        
        while True:
            print(f"\n==== 开始爬取【{tag}】第 {current_page_num} 页 ====")
            
            # 1. 爬取当前页面的图片（包含滚动加载）
            self.get_images(tag, csv_path)
            
            # 2. 翻页逻辑
            try:
                # 查找下一页元素，等待它变得可点击 (使用 XPath)
                next_button = wait.until(
                    EC.element_to_be_clickable((By.XPATH, next_page_xpath))
                )
                
                print(f"[INFO] 找到下一页按钮，准备使用 JS 翻页到第 {current_page_num + 1} 页...")
                # 使用 JavaScript 点击绕过元素遮挡
                self.driver.execute_script("arguments[0].click();", next_button)
                
                # 等待 URL 变化，确保页面已翻页
                wait.until(EC.url_changes(self.driver.current_url)) 
                print(f"[√] 成功翻页到第 {current_page_num + 1} 页，URL: {self.driver.current_url}")
                
                current_page_num += 1
                
                # 3. 等待下一页图片容器加载稳定
                # 修正: 使用修正后的选择器
                wait.until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, image_card_selector_wait))
                )
                print("[√] 新页面加载稳定，检测到图片容器。")
                
                # 增加随机延迟，模拟真实用户行为
                time.sleep(random.uniform(2.0, 4.0)) 
                
            except (TimeoutException, NoSuchElementException):
                # 找不到下一页元素时，退出循环
                print(f"[完成] 标签【{tag}】已爬取到最后一页 (第 {current_page_num} 页)。")
                return True 
            except Exception as e:
                print(f"[✗] 翻页时发生错误: {e}")
                return False

    def crawl_tag(self, tag, csv_path):
        """串行任务：爬取单个标签"""
        try:
            search_url = self.base_url
            print(f"\n--- 开始处理标签/页面：【{tag}】 ---")
            print(f"尝试访问 URL: {search_url}")
            self.driver.get(search_url)
            time.sleep(random.uniform(3.0, 5.0))
            
            self.crawl_page(tag, csv_path)
            
        except Exception as e:
            print(f"[✗] 爬取标签/页面【{tag}】时发生致命错误: {e}")

    def main(self):
        # --- 配置路径：请修改为你的实际路径 ---
        save_path_all = r'R:\py\Auto_Image-Spider\爬虫数据\wallpaperswide'
        # -------------------------------------
        os.makedirs(save_path_all, exist_ok=True)
        
        tags = ['anna-ralphs'] 
        
        print(f"--- 找到 {len(tags)} 个标签。") 
        csv_path = os.path.join(save_path_all, 'all_records.csv')
        
        for tag in tags:
            self.crawl_tag(tag, csv_path)
            time.sleep(random.uniform(0.5, 1.5)) # 控制访问速度，防止被封
            
        self.driver.quit()

if __name__ == '__main__':
    # --- 配置 ChromeDriver 路径：请修改为你的实际路径 ---
    chrome_driver_path = r'C:\Program Files\Google\chromedriver-win64\chromedriver.exe'
    # --------------------------------------------------
    
    # 检查 ChromeDriver 路径是否存在，增加代码稳定性
    if not os.path.exists(chrome_driver_path):
        print(f"[✗] 错误: ChromeDriver 路径不存在或不正确: {chrome_driver_path}")
    else:
        spider = wallpaperswide(chrome_driver_path)
        spider.main()