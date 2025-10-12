import os
import re
import csv
import time
import random
import urllib.parse
import hashlib
import threading

import redis
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.keys import Keys # 引入 Keys 模块
from selenium.common.exceptions import (
    NoSuchElementException,
    WebDriverException,
    TimeoutException,
)

# ----------------------------- 配置区（请根据需要修改路径） -----------------------------
START_URL = 'https://www.civitai.com/'
# ！！！请务必检查并修改以下路径！！！
CHROME_DRIVER_PATH = r"C:\Program Files\Google\chromedriver-win64\chromedriver.exe"  # 你的 chromedriver 路径
USER_DATA_DIR = r"R:\py\Auto_Image-Spider\保存和导入 Cookies\civitai_data"         # 你的 Chrome 用户数据目录（用于保持登录）
PROFILE_DIR = "Default"    # profile 目录名（Default 或者 Profile 1 等）
TAG_TXT_DIR = r'R:\py\Auto_Image-Spider\保存和导入 Cookies\civitai'  # 存放 tag.txt 的目录
# 滚动与加载参数
SMALL_SCROLL_AMOUNT = 1080  # 每次微调滚动的像素数
MAX_SCROLLS = 200    # 最大滚动次数（防止死循环）
# 当连续 N 轮没有新图片时就认为已到底部
NO_NEW_ROUNDS_TO_STOP = 3    # 连续 N 轮无新图片时认为已到底部
# ----------------------------- 配置区（请根据需要修改路径） -------------------------------
# Redis 去重键
REDIS_KEY = 'image_md5_set_civitai'
# --------------------------------------------------------------------------------------

class CivitaiSpider:
    def __init__(self, chrome_driver_path: str, user_data_dir: str = None, profile_dir: str = "Default"):
        """初始化 WebDriver、Redis（可选）及线程锁"""
        print("[INFO] 初始化 WebDriver（使用持久化用户数据目录以保持登录）...")
        try:
            service = Service(executable_path=chrome_driver_path)
            options = Options()
            
            options.add_argument('--disable-gpu')
            options.add_argument("--window-size=1920,1080") 
            options.add_argument("--disable-blink-features=AutomationControlled")
            options.add_experimental_option("excludeSwitches", ["enable-automation"])
            options.add_experimental_option('useAutomationExtension', False)

            if user_data_dir:
                options.add_argument(f"--user-data-dir={user_data_dir}")
                options.add_argument(f"--profile-directory={profile_dir}")

            user_agent = (
                'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
                'AppleWebKit/537.36 (KHTML, like Gecko) '
                'Chrome/120.0.0.0 Safari/537.36'
            )
            options.add_argument(f'user-agent={user_agent}')

            self.driver = webdriver.Chrome(service=service, options=options)
        except WebDriverException as e:
            raise SystemExit(f"[致命错误] 无法启动 Chrome WebDriver：{e}")

        # Redis 连接和设置保持不变
        try:
            self.redis = redis.Redis(host='localhost', port=6379, db=0, decode_responses=True)
            self.redis.ping()
            print("[√] Redis 连接成功（用于 URL 去重）。")
        except Exception:
            print("[⚠] 无法连接 Redis，使用本地集合进行去重。")
            self.redis = None
            self.seen_set = set()

        self.redis_key = REDIS_KEY
        self.csv_lock = threading.Lock()
        self.base_url = START_URL

    # ... (辅助函数 _clean_url, _get_image_id_from_url, _md5, write_to_csv, get_images 保持不变)
    def _clean_url(self, url: str) -> str:
        """将缩略图 URL 尽量转换为原图形式。"""
        if not url: return ""
        m = re.search(r'/([0-9a-fA-F-]{8,36})/', url)
        if not m: return url
        image_id = m.group(1)
        prefix = url.split(f'/{image_id}/')[0]
        return f"{prefix}/{image_id}/original=true"

    def _get_image_id_from_url(self, url: str) -> str:
        """从 url 提取 image id（uuid 或数字 id）"""
        if not url: return ""
        m = re.search(r'/([0-9a-fA-F-]{8,36})/', url)   # UUID 格式
        if m: return m.group(1)
        return os.path.splitext(os.path.basename(url))[0]

    def _md5(self, text: str) -> str:
        """计算字符串 md5（用于去重）"""
        return hashlib.md5(text.encode('utf-8')).hexdigest()

    def write_to_csv(self, prompt: str, name: str, url: str, csv_path: str, tag: str):
        """以线程安全方式写入 CSV（带表头检测）"""
        try:
            with self.csv_lock:
                file_exists = os.path.exists(csv_path) and os.path.getsize(csv_path) > 0
                with open(csv_path, 'a', newline='', encoding='utf-8-sig') as f:
                    writer = csv.writer(f)
                    if not file_exists:
                        writer.writerow(['Prompt', 'ImageName', 'URL', 'TAG'])
                    writer.writerow([prompt, name, url, tag])
                    f.flush()
            print(f"[√] 已写入 CSV：{name}")
        except Exception as e:
            print(f"[✗] 写入 CSV 失败：{name} -> {e}")

    def get_images(self, tag: str, csv_path: str, image_card_elements: list):
        """解析给定的一组图片卡片，提取图片 URL 并写入 CSV。"""
        if not image_card_elements: return 0

        newly_extracted = 0
        print(f"--- 正在解析 {len(image_card_elements)} 个新图片卡片 ---")
        for card_ele in image_card_elements:
            try:
                img_element = card_ele.find_element(By.CSS_SELECTOR, 'img.EdgeImage_image__iH4_q.Cards_image__d4f6b')   # 主要图片选择器
                image_url = img_element.get_attribute('src')
                if not image_url: continue

                image_url_cleaned = self._clean_url(image_url)
                image_id = self._get_image_id_from_url(image_url_cleaned)
                image_name = image_id

                try:
                    link_ele = card_ele.find_element(By.CSS_SELECTOR, 'a[href^="/images/"]')    # 链接选择器
                    image_page_href = link_ele.get_attribute('href')   # 详情页链接
                except NoSuchElementException:
                    image_page_href = ""

                prompt_text = f"Prompt 未在卡片中提供（详情页: {image_page_href})"

                md5_key = self._md5(image_url_cleaned)
                already_seen = False
                if self.redis:
                    try:
                        if self.redis.sismember(self.redis_key, md5_key):
                            already_seen = True
                        else:
                            self.redis.sadd(self.redis_key, md5_key)
                    except Exception:
                        if md5_key in getattr(self, 'seen_set', set()):
                            already_seen = True
                        else:
                            self.seen_set.add(md5_key)
                else:
                    if md5_key in self.seen_set:
                        already_seen = True
                    else:
                        self.seen_set.add(md5_key)

                if already_seen: continue

                self.write_to_csv(prompt_text, image_name, image_url_cleaned, csv_path, tag)
                newly_extracted += 1

            except Exception as e:
                continue

        print(f"--- 本轮解析完成，新增 {newly_extracted} 条记录 ---")
        return newly_extracted
    # ---------------------- 页面滚动并抓取直到稳定（强化滚动操作） ----------------------
    def crawl_page(self, search_url: str, tag: str, csv_path: str) -> bool:
        """
        打开 search_url 并滚动加载图片，使用更可靠的键盘操作来确保滚动发生。
        """
        wait = WebDriverWait(self.driver, 10)  # 等待超时设为 10 秒
        image_card_selector = 'div.relative.flex-1'  # 图片卡片选择器

        try:
            print(f"[INFO] 导航到：{search_url}")
            self.driver.get(search_url)
            # 等待至少一张图片卡片出现
            wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, image_card_selector)))
            print("[√] 页面已加载，找到图片卡片容器。")
        except TimeoutException:
            print("[✗] 页面加载超时或未找到任何图片卡片。")
            return False
        except Exception as e:
            print(f"[✗] 页面加载异常：{e}")
            return False

        # ---------------------- 滚动主循环 (强化) ----------------------
        scroll_cycle_count = 0
        processed_count = 0
        no_new_content_rounds = 0

        # 在循环开始前尝试点击 body 元素，确保焦点在页面上
        try:
            self.driver.find_element(By.TAG_NAME, 'body').click()
        except Exception:
            pass # 忽略点击失败

        while scroll_cycle_count < MAX_SCROLLS:
            print(f"\n==== 开始第 {scroll_cycle_count + 1} 轮滚动周期和解析 ====")

            # 1. 解析当前已加载但未处理的图片
            all_elements = self.driver.find_elements(By.CSS_SELECTOR, image_card_selector)
            current_count = len(all_elements)

            if current_count > processed_count:
                print(f"[INFO] 发现新加载的图片 (当前总数: {current_count})，进行解析...")
                new_elements = all_elements[processed_count:]
                self.get_images(tag, csv_path, new_elements)
                processed_count = current_count
            else:
                 print("[INFO] 当前未发现新图片卡片。")

            # 2. **强化滚动操作：使用键盘模拟 Page Down 或 End**
            print("[INFO] 尝试使用 Page Down 模拟滚动...")
            try:
                # 尝试使用 END 键滚动到页面底部，这通常比 JavaScript 滚动更可靠
                self.driver.find_element(By.TAG_NAME, 'body').send_keys(Keys.END)
                time.sleep(random.uniform(1.0, 2.0)) # 给予加载时间
            except Exception as e:
                print(f"[WARN] 键盘操作失败 ({e})，回退到 JavaScript 滚动...")
                try:
                    # 回退到 JavaScript 滚动到底部
                    self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
                    time.sleep(random.uniform(1.0, 2.0))
                except Exception as js_e:
                    print(f"[FATAL] JavaScript 滚动也失败: {js_e}")
                    break # 滚动失败，直接退出循环

            # 3. 等待新内容出现 (逻辑保持不变，依靠元素总数)
            try:
                wait.until(
                    lambda driver: len(driver.find_elements(By.CSS_SELECTOR, image_card_selector)) > processed_count
                )
                print("[√] 成功加载了新的一批图片！")
                no_new_content_rounds = 0 

            except TimeoutException:
                # 10秒内没有新图片出现
                no_new_content_rounds += 1
                print(f"[⚠] 等待超时，未发现新图片。({no_new_content_rounds}/{NO_NEW_ROUNDS_TO_STOP})")

                # 检查是否真的到底部
                scroll_height = self.driver.execute_script("return document.body.scrollHeight")
                current_scroll = self.driver.execute_script("return window.scrollY + window.innerHeight")
                
                if abs(scroll_height - current_scroll) < 50:
                    print("[INFO] 滚动条已到达页面最底部。")
                else:
                    # 如果未到底部，尝试微调向下滚动
                    self.driver.execute_script(f"window.scrollBy(0, {SMALL_SCROLL_AMOUNT});")
                    print(f"[INFO] 未到底部，微调向下滚动 {SMALL_SCROLL_AMOUNT} 像素。")
                    time.sleep(1) 

                # 检查退出条件
                if no_new_content_rounds >= NO_NEW_ROUNDS_TO_STOP:
                    print(f"[完成] 已连续 {NO_NEW_ROUNDS_TO_STOP} 轮未发现新内容，判定'{tag}'已抓取完毕。")
                    # 退出前再检查一次是否有未解析的元素
                    all_elements_final = self.driver.find_elements(By.CSS_SELECTOR, image_card_selector)
                    final_count = len(all_elements_final)
                    if final_count > processed_count:
                         print(f"[INFO] 退出前发现最后一批未解析的图片 ({final_count - processed_count} 张)，正在解析...")
                         new_elements_final = all_elements_final[processed_count:]
                         self.get_images(tag, csv_path, new_elements_final)
                    break


            scroll_cycle_count += 1
            if scroll_cycle_count >= MAX_SCROLLS:
                print(f"[⚠] 达到最大滚动次数 {MAX_SCROLLS}，强制停止。")
                break

            time.sleep(random.uniform(0.5, 1.5)) 

        print(f"[√] 标签 '{tag}' 滚动抓取完成，共找到约 {processed_count} 张图片。")
        return True

    # ---------------------- 主流程 ----------------------
    def main(self):
        # 准备保存目录和 tag 文件路径
        save_path_all = TAG_TXT_DIR
        os.makedirs(save_path_all, exist_ok=True)
        csv_path = os.path.join(save_path_all, 'all_records_civitai.csv')
        tag_file_path = os.path.join(save_path_all, r"R:\py\Auto_Image-Spider\保存和导入 Cookies\civitai\tag1.txt")

        # 读取 tag 列表
        try:
            with open(tag_file_path, 'r', encoding='utf-8') as f:
                tags = [line.strip() for line in f if line.strip()]
        except FileNotFoundError:
            print(f"[错误] 未找到标签文件: {tag_file_path}，请创建并填入每行一个 tag。")
            return

        print(f"--- 发现 {len(tags)} 个标签 ---")

        # 逐个处理 tag
        for tag in tags:
            try:
                encoded_tag = urllib.parse.quote_plus(tag)
                search_url = f'{self.base_url}images?tags={encoded_tag}'
                print(f"\n=== 开始处理标签：{tag} ===\nURL: {search_url}")
                ok = self.crawl_page(search_url, tag, csv_path)
                if not ok:
                    print(f"[✗] 标签 {tag} 抓取失败或页面加载异常，跳过。")
                time.sleep(random.uniform(1.5, 3.0))
            except Exception as e:
                print(f"[✗] 处理标签 {tag} 时发生异常：{e}")
                continue

        print("[√] 所有标签处理完毕，退出浏览器。")

if __name__ == '__main__':
    # 启动爬虫
    spider = CivitaiSpider(CHROME_DRIVER_PATH, USER_DATA_DIR, PROFILE_DIR)
    try:
        spider.main()
    finally:
        try:
            spider.driver.quit()
        except Exception:
            pass