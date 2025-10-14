from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
from selenium.common.exceptions import TimeoutException, NoSuchElementException
from selenium.webdriver.common.keys import Keys
import os
import time
import hashlib
import redis
import csv
import threading
import random

class WallhallaSpider:
    def __init__(self, chrome_driver_path, base_save_dir, tag_file_path):
        """
        初始化爬虫的基本配置
        :param chrome_driver_path: ChromeDriver 的路径
        :param base_save_dir: 图片和CSV文件的根保存目录
        :param tag_file_path: 标签列表文件的路径
        """
        self.chrome_driver_path = chrome_driver_path
        self.base_save_dir = base_save_dir
        self.images_base_dir = os.path.join(self.base_save_dir, 'images') # 图片的根目录
        self.tag_file_path = tag_file_path
        
        self.driver = None  # Driver 将在处理每个标签时被创建
        self.base_url = 'https://www.wallhalla.com/'
        self.csv_lock = threading.Lock()
        self.redis_key = 'image_md5_set_wallhalla'
        
        # 主容器选择器
        self.main_container_selector = "div.flex.justify-center > div.wallpapers-wrap"
        
        try:
            self.redis = redis.Redis(host='localhost', port=6379, db=0, decode_responses=True)
            self.redis.ping()
            print("✅ Redis 连接成功。")
        except Exception:
            print("⚠️ Redis 不可用，将使用内存去重。")
            self.redis = None
            self.visited_md5 = set()

    def setup_driver(self, download_path):
        """
        为每个标签创建一个新的 WebDriver 实例，并设置独立的下载路径。
        同时禁用图片加载以提升效率。
        :param download_path: 当前标签的图片下载路径
        """
        if self.driver:
            self.driver.quit()

        service = Service(executable_path=self.chrome_driver_path)
        options = Options()
        options.add_experimental_option("excludeSwitches", ["enable-automation"])
        options.add_experimental_option('useAutomationExtension', False)
        
        # --- ✨ 关键修改在这里 ---
        # 合并下载路径设置和禁用图片加载的设置
        prefs = {
            "download.default_directory": download_path,
            "download.prompt_for_download": False,
            "download.directory_upgrade": True,
            "safebrowsing.enabled": True,
            "profile.managed_default_content_settings.images": 2  # 2 表示禁用图片
        }
        options.add_experimental_option("prefs", prefs)

        options.add_argument('user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36')
        options.add_argument("--window-size=1920,1080")
        # options.add_argument("--headless") # 下载文件时，建议不要使用 headless 模式

        self.driver = webdriver.Chrome(service=service, options=options)
        print(f"🔧 WebDriver 已配置，下载路径设置为: {download_path}")
        print("🚀 图片加载已禁用，火力全开模式启动！")


    # ---------------------- 去重逻辑 ----------------------
    def is_duplicate(self, md5_hash):
        if self.redis:
            if self.redis.sismember(self.redis_key, md5_hash):
                return True
            self.redis.sadd(self.redis_key, md5_hash)
        else:
            if md5_hash in self.visited_md5:
                return True
            self.visited_md5.add(md5_hash)
        return False

    # ---------------------- 写入 CSV ----------------------
    def write_to_csv(self, title, name, url, csv_path, tag):
        try:
            with self.csv_lock:
                is_file_empty = not os.path.exists(csv_path) or os.stat(csv_path).st_size == 0
                with open(csv_path, 'a', newline='', encoding='utf-8-sig') as f:
                    writer = csv.writer(f)
                    if is_file_empty:
                        writer.writerow(['Title', 'ImageName', 'URL', 'Tag'])
                    writer.writerow([title, name, url, tag])
        except Exception as e:
            print(f"[✗] 写入 CSV 出错: {e}")

    # ---------------------- 搜索输入逻辑 ----------------------
    def perform_search(self, tag):
        """
        打开首页并通过搜索框输入关键词。
        :return: True 如果搜索结果页加载成功, False 如果超时或没有结果。
        """
        self.driver.get(self.base_url)
        wait = WebDriverWait(self.driver, 20)

        try:
            search_input = wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "input[name='q']")))
            search_input.clear()
            search_input.send_keys(tag)
            time.sleep(random.uniform(0.5, 1.5))

            search_button = self.driver.find_element(By.CSS_SELECTOR, "form[action='/search'] button[type='submit']")
            self.driver.execute_script("arguments[0].click();", search_button)

            # 等待搜索结果加载（主容器出现）
            wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, self.main_container_selector)))
            print(f"🔍 搜索 '{tag}' 成功，页面加载完成。")
            return True

        except TimeoutException:
            # 如果主容器没有在指定时间内出现，说明该标签可能没有搜索结果
            print(f"[✗] 搜索 '{tag}' 失败，页面加载超时或无结果。将跳过此标签。")
            return False

    # ---------------------- 获取并下载图片（重构后）----------------------
    def get_images_and_download(self, tag, csv_path):
        print(f"--- 正在解析【{tag}】的图片列表...")
        wait = WebDriverWait(self.driver, 20)
        
        # 滚动加载逻辑
        print("🚀 开始滚动加载更多内容...")
        last_height = self.driver.execute_script("return document.body.scrollHeight")
        while True:
            self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            time.sleep(2.5 + random.random())
            new_height = self.driver.execute_script("return document.body.scrollHeight")
            if new_height == last_height:
                print("✅ 滚动到底部。")
                break
            last_height = new_height
            
        # 精确定位所有图片卡片的链接
        card_selector = "div.flex.justify-center div.wallpapers-wrap a.wp-item"
        try:
            wallpaper_cards = wait.until(EC.presence_of_all_elements_located((By.CSS_SELECTOR, card_selector)))
            # 提取 href 属性，因为元素在页面跳转后会失效 (StaleElementReferenceException)
            detail_page_links = [card.get_attribute('href') for card in wallpaper_cards]
            print(f"🖼️ 检测到 {len(detail_page_links)} 个图片待处理。")
        except TimeoutException:
            print("[✗] 未找到任何图片卡片。")
            return

        original_window = self.driver.current_window_handle

        for link in detail_page_links:
            try:
                # --- 1. 在新标签页中打开详情页 ---
                self.driver.switch_to.new_window('tab')
                self.driver.get(link)

                # --- 2. 在详情页中定位下载按钮并点击 ---
                download_button_selector = 'a[href*="/variant/original?dl=true"]'
                download_button = wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, download_button_selector)))
                
                # 提取信息用于写入 CSV
                download_url = download_button.get_attribute('href')
                wallpaper_id = download_url.split('/wallpaper/')[1].split('/')[0]
                image_name = f"{wallpaper_id}.jpg" # 假设都是 jpg
                
                # 从页面中获取标题
                try:
                    title = self.driver.find_element(By.CSS_SELECTOR, 'h1.text-2xl').text
                except NoSuchElementException:
                    title = "N/A"

                md5_hash = hashlib.md5(download_url.encode('utf-8')).hexdigest()
                if self.is_duplicate(md5_hash):
                    print(f"🔄 跳过重复图片: {title}")
                    self.driver.close()
                    self.driver.switch_to.window(original_window)
                    continue

                # 点击下载
                download_button.click()
                print(f"✔️ 开始下载: {title} ({image_name})")
                
                # 写入CSV
                self.write_to_csv(title, image_name, download_url, csv_path, tag)

                # 等待下载开始（这个时间需要根据你的网络情况调整）
                time.sleep(5) 

                # --- 3. 关闭详情页，切换回主页面 ---
                self.driver.close()
                self.driver.switch_to.window(original_window)
                time.sleep(random.uniform(1.0, 2.0))

            except Exception as e:
                print(f"[⚠️] 处理链接 {link} 时出错: {e}")
                # 如果出错，确保关闭可能打开的新标签并切回主窗口
                if len(self.driver.window_handles) > 1:
                    self.driver.close()
                    self.driver.switch_to.window(original_window)

    # ---------------------- 主函数 ----------------------
    def main(self):
        os.makedirs(self.images_base_dir, exist_ok=True)
        csv_path = os.path.join(self.base_save_dir, 'all_records_wallhalla_251014.csv')

        try:
            with open(self.tag_file_path, 'r', encoding='utf-8') as f:
                tags = [line.strip() for line in f if line.strip()]
        except FileNotFoundError:
            print(f"[错误] 未找到标签文件: {self.tag_file_path}")
            return

        print(f"--- 发现 {len(tags)} 个标签 ---")

        for tag in tags:
            try:
                print(f"\n=== 开始处理：【{tag}】 ===")
                # 为当前标签创建图片保存目录
                tag_image_path = os.path.join(self.images_base_dir, tag)
                os.makedirs(tag_image_path, exist_ok=True)
                
                # 初始化/重置 WebDriver 并设置新的下载路径
                self.setup_driver(tag_image_path)
                
                # 执行搜索，如果失败则跳过
                if not self.perform_search(tag):
                    continue
                
                time.sleep(random.uniform(1.5, 2.5))
                self.get_images_and_download(tag, csv_path)

            except Exception as e:
                print(f"[✗] 处理标签 {tag} 时发生严重错误: {e}")
            finally:
                # 确保浏览器实例在每个标签处理后都关闭
                self.close()

        print("🎯 所有标签处理完成。")

    def close(self):
        if self.driver:
            print("🔚 正在关闭当前浏览器实例...")
            self.driver.quit()
            self.driver = None


if __name__ == '__main__':
    # --- 请在这里配置你的路径 ---
    CHROME_DRIVER_PATH = r'C:\Program Files\Google\chromedriver-win32\chromedriver.exe'
    # 注意：这里是你想要保存所有数据的根目录
    SAVE_DIRECTORY = r"\\10.58.134.120\aigc2\01_数据\爬虫数据\wallhalla" 
    TAG_FILE_PATH = r'D:\work\爬虫\ram_tag_list.txt'
    
    spider = None
    try:
        spider = WallhallaSpider(
            chrome_driver_path=CHROME_DRIVER_PATH,
            base_save_dir=SAVE_DIRECTORY,
            tag_file_path=TAG_FILE_PATH
        )
        spider.main()
    except Exception as main_e:
        print(f"主程序运行出错: {main_e}")
    finally:
        if spider:
            spider.close()