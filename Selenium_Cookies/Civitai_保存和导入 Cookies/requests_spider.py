import os
import csv
import json
import time
import redis
import urllib3
import requests
import random 
from urllib.parse import unquote
from threading import Lock
from seleniumwire import webdriver  
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, StaleElementReferenceException
from selenium.webdriver.common.keys import Keys 


# ---------------- 配置区 ----------------
REDIS_HOST = 'localhost'
REDIS_PORT = 6379
REDIS_KEY = 'image_md5_set_civitai'

CHROME_DRIVER_PATH = r"C:\Program Files\Google\chromedriver-win64\chromedriver.exe" 
USER_DATA_DIR = r"R:\py\Civitai_保存和导入 Cookies\civitai_data"
TAG_TXT_PATH = r"R:\py\Auto_Image-Spider\Selenium_Cookies\Civitai_保存和导入 Cookies\tag.txt"
CSV_DIR_PATH = r"R:\py\Auto_Image-Spider\Selenium_Cookies\Civitai_保存和导入 Cookies\Civitai_图片数据_CSV"

BASE_IMG_URL = "https://image.civitai.com/xG1nkqKTMzGDvpLrqFT7WA/"
API_KEYWORD = "api/trpc/image.getInfinite"

# 滚动与加载参数 
SCROLL_WAIT_TIME = 2.0      # 滚动后强制等待时间 (秒)
MAX_SCROLLS = 200           # 最大翻页次数（防止死循环）
NO_NEW_ROUNDS_TO_STOP = 3   # 连续 N 轮无新图片时认为已到底部


class CivitaiSpider:
    # ... (辅助函数保持 V11/V10 不变)
    def __init__(self):
        self.csv_lock = Lock()
        urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

        try:
            self.redis = redis.StrictRedis(host=REDIS_HOST, port=REDIS_PORT, decode_responses=True)
            self.redis.ping()
            print("✅ Redis 连接成功。")
        except Exception as e:
            print(f"⚠️ Redis 连接失败 ({e})，使用内存模式。")
            self.redis = None
            self.visited_urls = set()

    def write_to_csv(self, name, url, csv_path, tag):
        try:
            with self.csv_lock:
                os.makedirs(os.path.dirname(csv_path), exist_ok=True)
                is_new = not os.path.exists(csv_path)
                with open(csv_path, 'a', newline='', encoding='utf-8-sig') as f:
                    writer = csv.writer(f)
                    if is_new:
                        writer.writerow(['ImageName', 'URL', 'TAG'])
                    writer.writerow([name, url, tag])
        except Exception as e:
            print(f"[{tag}] 写入 CSV 出错: {e}")

    def is_duplicate(self, url):
        if self.redis:
            return self.redis.sismember(REDIS_KEY, url) 
        return url in self.visited_urls

    def mark_visited(self, url):
        if self.redis:
            self.redis.sadd(REDIS_KEY, url)
        else:
            self.visited_urls.add(url)

    def setup_browser(self):
        options = Options()
        options.add_argument(f"user-data-dir={USER_DATA_DIR}")
        options.add_argument("--start-maximized")
        options.add_argument("--disable-blink-features=AutomationControlled")
        options.add_argument("--ignore-certificate-errors")

        service = Service(CHROME_DRIVER_PATH)

        seleniumwire_options = {
            'proxy': {
                'http': 'http://127.0.0.1:7897',
                'https': 'http://127.0.0.1:7897',
                'no_proxy': 'localhost,127.0.0.1'
            }
        }

        driver = webdriver.Chrome(service=service, options=options, seleniumwire_options=seleniumwire_options)
        return driver

    def extract_api_urls(self, driver, tag):
        urls = []
        for request in driver.requests:
            if API_KEYWORD in request.url and request.response:
                urls.append(request.url)
        
        unique_urls = list(dict.fromkeys(urls))
        
        if unique_urls:
            print(f"[{tag}] 🔍 捕获到 {len(unique_urls)} 条唯一 API 请求")
            return unique_urls
        return []

    def fetch_images(self, api_url, tag, csv_path):
        print(f"[{tag}] 🌐 正在请求 API: {api_url[:100]}...")
        try:
            r = requests.get(api_url, timeout=30) 
            r.raise_for_status()
            data = r.json()
        except Exception as e:
            print(f"[{tag}] ❌ 请求失败: {e}")
            return None

        try:
            items = data['result']['data']['json']['items']
        except Exception:
            print(f"[{tag}] ⚠️ JSON 结构不符合预期或 'items' 字段缺失")
            return None

        count = 0
        for item in items:
            img_id = item.get("id")
            img_url = item.get("url")
            
            if not img_id or not img_url:
                continue
            
            full_url = f"{BASE_IMG_URL}{img_url}/{img_id}" 
            
            if not self.is_duplicate(full_url):
                self.mark_visited(full_url)
                img_name = f"{img_id}.jpg"
                self.write_to_csv(img_name, full_url, csv_path, tag)
                count += 1
        
        print(f"[{tag}] ✅ 成功提取 {count} 张新图片。")

        try:
            next_cursor = data['result']['data']['json'].get('nextCursor')
            if next_cursor:
                print(f"[{tag}] ➡️ 发现下一页 cursor: {next_cursor[:10]}...")
            return next_cursor
        except Exception:
            return None


    # ---------------- 主爬取函数 (V12: 恢复 V9 滚动核心) ----------------
    def crawl_tag(self, tag):
        """
        爬取单个标签下的图片，恢复 V9 的组合滚动，并使用 V11 的 API 处理逻辑。
        """
        driver = self.setup_browser()
        url = f"https://civitai.com/images?tags={tag}"
        csv_path = os.path.join(CSV_DIR_PATH, f"tag_{tag}.csv")
        image_card_selector = 'div.relative.flex-1' 
        wait = WebDriverWait(driver, 20) # 保持 20 秒等待新卡片
        
        last_cursor = None
        no_new_content_count = 0 
        current_element_count = 0

        print(f"\n🚀 开始爬取标签 [{tag}] ...")
        
        try:
            driver.get(url)
            wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, image_card_selector)))
            
            # 1. 初始化，处理第一页数据 (V11 逻辑)
            current_element_count = len(driver.find_elements(By.CSS_SELECTOR, image_card_selector))
            print(f"[{tag}] [√] 页面已加载，找到 {current_element_count} 张初始图片。")
            
            initial_urls = self.extract_api_urls(driver, tag)
            initial_cursor_url = next((u for u in initial_urls if '%22cursor%22%3Anull' in u), None)
            
            if initial_cursor_url:
                print(f"[{tag}] ⚙️ 正在处理初始页 API...")
                last_cursor = self.fetch_images(unquote(initial_cursor_url), tag, csv_path)
            else:
                print(f"[{tag}] ⚠️ 未捕获到初始页 API 请求 (cursor:null)。")

            del driver.requests  # 清空请求历史

            # 获取焦点
            driver.find_element(By.TAG_NAME, 'body').click()
            time.sleep(1)

        except TimeoutException:
            print(f"[{tag}] [✗] 页面加载超时或未找到初始图片卡片。")
            driver.quit()
            return
        except Exception as e:
            print(f"[{tag}] [✗] 页面加载异常: {e}")
            driver.quit()
            return


        # --------------------- 主滚动/加载循环 ---------------------
        for page_attempt in range(MAX_SCROLLS):
            print(f"\n[{tag}] ==== 开始第 {page_attempt+1} / {MAX_SCROLLS} 轮翻页尝试 ====")
            
            # 2. **核心滚动操作 (V9 组合拳)**
            print(f"[{tag}] 🌀 滚动尝试: Keys.END + scrollTo(bottom)")
            try:
                # 尝试键盘滚动
                body = driver.find_element(By.TAG_NAME, 'body')
                body.send_keys(Keys.END)
                time.sleep(0.5)
            except Exception:
                pass 

            # 尝试 JavaScript 滚动
            driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            
            # **强制等待，确保脚本被触发**
            print(f"[{tag}] ⏳ 滚动后强制等待 {SCROLL_WAIT_TIME} 秒...")
            time.sleep(SCROLL_WAIT_TIME)
            
            
            # 3. 等待新卡片加载（确认翻页生效）
            try:
                print(f"[{tag}] ⏳ 等待新卡片加载 (当前: {current_element_count} 张)...")
                wait.until(
                    lambda d: len(d.find_elements(By.CSS_SELECTOR, image_card_selector)) > current_element_count
                )
                
                new_count = len(driver.find_elements(By.CSS_SELECTOR, image_card_selector))
                print(f"[{tag}] ✅ 滚动成功，加载了 {new_count - current_element_count} 张新卡片。")
                current_element_count = new_count
                no_new_content_count = 0 

            except TimeoutException:
                # 4. 超时处理
                no_new_content_count += 1
                print(f"[⚠] 等待超时，未发现新图片。({no_new_content_count}/{NO_NEW_ROUNDS_TO_STOP})")

                # **V12 修正：不再进行 `scrollHeight` 检查，只依赖连续超时计数**
                if no_new_content_count >= NO_NEW_ROUNDS_TO_STOP: 
                    print(f"[{tag}] 💤 连续 {NO_NEW_ROUNDS_TO_STOP} 次未加载新内容，判定为已到底部，停止。")
                    break
                
                del driver.requests
                continue 

            # 5. 获取并处理新的 API 请求 (V11 逻辑)
            urls = self.extract_api_urls(driver, tag)
            filtered_urls = [u for u in urls if '%22cursor%22%3Anull' not in u]

            if not filtered_urls:
                print(f"[{tag}] ⚠️ 页面加载了新卡片，但未捕获到新的分页 API 请求。")
                del driver.requests
                continue
            
            latest_valid_url = unquote(filtered_urls[-1]) 
            
            # 6. 检查 cursor 是否重复
            if last_cursor and f"cursor%22%3A%22{last_cursor}" in latest_valid_url:
                print(f"[{tag}] ❌ Cursor 未更新 (捕获到重复请求)，清除请求并继续下一轮滚动。")
                del driver.requests
                continue

            # 7. 获取和处理图片数据
            next_cursor = self.fetch_images(latest_valid_url, tag, csv_path)
            
            # 8. 更新 cursor 并清除请求历史
            if not next_cursor:
                print(f"[{tag}] ✅ 已到最后一页 (nextCursor 为空)。")
                break
            
            last_cursor = next_cursor
            del driver.requests 

        if page_attempt == MAX_SCROLLS - 1:
            print(f"[⚠] 达到最大翻页次数 {MAX_SCROLLS}，强制停止。")

        driver.quit()
        print(f"[{tag}] 🎯 完成爬取。")

    # ---------------- 主程序入口 ----------------
    def run(self):
        if not os.path.exists(TAG_TXT_PATH):
            print(f"❌ 未找到标签文件: {TAG_TXT_PATH}")
            return

        with open(TAG_TXT_PATH, 'r', encoding='utf-8') as f:
            tags = [t.strip() for t in f if t.strip()]

        for tag in tags:
            self.crawl_tag(tag)


if __name__ == "__main__":
    spider = CivitaiSpider()
    spider.run()