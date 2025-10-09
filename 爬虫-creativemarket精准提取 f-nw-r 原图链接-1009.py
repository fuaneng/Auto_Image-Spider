import hashlib
import json
import os
import random
import re
import threading
import time
from typing import Any, Dict, List, Tuple

import redis
import csv
from selenium import webdriver
from selenium.common.exceptions import (NoSuchElementException, TimeoutException,
                                        WebDriverException)
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait


class creativemarket:
    def __init__(self, chrome_driver_path):
        """
        初始化爬虫类。
        """
        self.driver = None
        
        try:
            service = Service(executable_path=chrome_driver_path)
        except Exception as e:
            print(f"[错误] ChromeDriver 路径错误或服务启动失败: {e}")
            return
            
        options = Options()
        # 1. 启用性能日志，以便获取网络请求信息 (Performance Log 模式的核心)
        options.set_capability('goog:loggingPrefs', {'performance': 'ALL'})
        
        options.add_experimental_option("excludeSwitches", ["enable-automation"])
        options.add_experimental_option('useAutomationExtension', False)
        # options.add_argument("--headless") 
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")

        user_agent = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        options.add_argument(f'user-agent={user_agent}')
        
        try:
            self.driver = webdriver.Chrome(service=service, options=options)
            self.driver.set_page_load_timeout(30)
            
        except WebDriverException as e:
            print(f"[致命错误] WebDriver 启动失败: {e}")
            self.driver = None

        self.base_url = 'https://creativemarket.com/search/'
        
        # Redis 连接配置
        self.redis = redis.Redis(host='localhost', port=6379, db=0, decode_responses=True)
        self.redis_key = 'image_md5_set_creativemarket'
        # 写入 CSV 的线程锁
        self.csv_lock = threading.Lock()

    # --- 数据提取和网络监听方法 ---
    def _get_xhr_json_with_f_nw_r(self) -> str:
        """
        读取 Performance 日志，解析所有请求 ID，并循环获取响应体，直到找到包含 'f-nw-r' 键的 JSON。
        """
        requests_info = {}

        try:
            time.sleep(1) 
            logs = self.driver.get_log('performance')
        except Exception as e:
            print(f"[✗] 无法获取 Performance 日日志，可能是驱动不支持: {e}")
            return ""

        for log_entry in logs:
            try:
                message_data = json.loads(log_entry['message'])
                message = message_data['message']
                method = message.get('method')
                params = message.get('params')
                request_id = params.get('requestId')
                
                if not request_id:
                    continue
                
                if method == 'Network.responseReceived':
                    response = params.get('response')
                    if response and response['mimeType'] in ['application/json', 'text/plain', 'text/html']: 
                        requests_info[request_id] = {'loaded': False, 'url': response['url']}
                        
                elif method == 'Network.loadingFinished' and request_id in requests_info:
                    requests_info[request_id]['loaded'] = True

            except Exception:
                continue
        
        if not requests_info:
            return ""

        for request_id, info in requests_info.items():
            if info['loaded']:
                try:
                    response = self.driver.execute_cdp_cmd(
                        'Network.getResponseBody', 
                        {'requestId': request_id}
                    )
                    
                    body = response['body']
                    
                    if '"f-nw-r":' in body and body.strip().startswith('{'):
                        print(f"[√] 成功通过 Performance Log 捕获目标 JSON 响应！URL: {info['url'][:80]}...")
                        
                        if response.get('base64Encoded'):
                            import base64
                            return base64.b64decode(body).decode('utf-8', errors='ignore')
                        return body
                        
                except Exception:
                    continue
        
        print("[✗] 检查了所有已完成的 API 响应，未找到包含 \"f-nw-r\": 键的 JSON 文本。")
        return ""


    def _extract_base64_paths(self) -> List[Tuple[str, str, str]]:
        """
        从产品卡片 div 的 data-title 属性中提取标题和 Base64 路径。
        返回：[(title, base64_path, src_url), ...]
        """
        paths = []
        product_cards = self.driver.find_elements(By.CSS_SELECTOR, 'div[data-test="sp-product-card"]')
        base64_regex = re.compile(r'/(czM6Ly9maWxlcy\S+)')
        
        for card in product_cards:
            title = card.get_attribute('data-title')
            src = card.get_attribute('data-src-retina')
            
            if src:
                match = base64_regex.search(src)
                if match:
                    base64_path = match.group(1).split('?')[0]
                    final_title = title.strip() if title else "N/A" # 确保标题存在
                    
                    if final_title == "N/A":
                        print(f"[WARN] 发现 Base64 路径 {base64_path[:10]}... 但标题为空，使用 'N/A'。")
                    
                    paths.append((final_title, base64_path, src))
            
        print(f"[√] 从 {len(product_cards)} 个产品卡片中成功提取了 {len(paths)} 个 Base64 路径和标题。")
        return paths

    # --- 新增的辅助函数 ---
    def _build_url_map_from_json(self, data: Any) -> Dict[str, str]:
        """
        递归遍历解析后的 JSON 数据(字典)，找到所有 'f-nw-r' URL，
        并将它们映射到其对应的 Base64 路径指纹。

        返回一个字典，格式为: { 'base64_path': 'corresponding_f-nw-r_url', ... }
        """
        url_map = {}
        # 这个正则表达式用于从一个完整的URL中提取出作为唯一标识的Base64路径部分
        base64_regex = re.compile(r'(czM6Ly9maWxlcy[^\?]+)')

        def recursive_search(item):
            """ 递归搜索的内部函数 """
            # 如果当前项是字典
            if isinstance(item, dict):
                # 检查这个字典是否是我们寻找的目标：即包含 'f-nw-r' 键
                if 'f-nw-r' in item and isinstance(item['f-nw-r'], str):
                    f_nw_r_url = item['f-nw-r']
                    
                    # 从 'f-nw-r' URL 中提取 Base64 路径指纹
                    match = base64_regex.search(f_nw_r_url)
                    if match:
                        # 提取到的指纹作为字典的键
                        base64_path = match.group(1)
                        # 清理URL中的转义字符，作为字典的值
                        cleaned_url = f_nw_r_url.replace('\\/', '/')
                        url_map[base64_path] = cleaned_url
                
                # 无论当前字典是否匹配，都继续向更深层级搜索
                for value in item.values():
                    recursive_search(value)

            # 如果当前项是列表，则遍历列表中的每个元素
            elif isinstance(item, list):
                for element in item:
                    recursive_search(element)

        # 启动递归搜索
        recursive_search(data)
        return url_map


    # --- 主要爬取逻辑 (已更新) ---
    def get_images(self, tag, csv_path):
        """
        执行滚动加载，提取 Base64 路径，然后从网络 JSON 响应中匹配 f-nw-r 链接。
        """
        print(f"--- 正在解析【{tag}】的图片列表...")

        image_card_selector = 'div[data-test="sp-product-card"]' 
        
        # 步骤 1: 滚动加载
        last_count = 0
        while True:
            image_elements = self.driver.find_elements(By.CSS_SELECTOR, image_card_selector)
            current_count = len(image_elements)
            
            if current_count == last_count and current_count > 0:
                print(f"[√] 页面所有产品 ({current_count} 个) 已加载完毕。")
                break
            if current_count == 0 and last_count == 0:
                print("当前页面没有找到图片元素，跳过。")
                break

            if current_count > 0:
                self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
                print(f"滚动加载，当前找到 {current_count} 个产品...")
            
            last_count = current_count
            time.sleep(random.uniform(2.0, 4.0))


        # 步骤 2: 提取缩略图中的 Base64 路径和标题 (不变)
        base64_paths_and_titles = self._extract_base64_paths()
        if not base64_paths_and_titles:
            print("[✗] 未能从 DOM 中提取任何 Base64 路径。")
            return

        # 步骤 3: 提取完整的 JSON 字符串并解析
        full_json_str = self._get_xhr_json_with_f_nw_r()
        if not full_json_str:
            print("[✗] 无法通过网络日志获取目标 JSON 字符串，跳过本页解析。")
            return
        
        try:
            # 将JSON字符串解析为Python字典
            json_data = json.loads(full_json_str)
        except json.JSONDecodeError:
            print("[✗] 解析捕获的 JSON 字符串失败，跳过本页。")
            return

        # 步骤 4: 【核心改动】构建 Base64 指纹到 URL 的查找映射表
        print("[INFO] 正在从 JSON 数据中构建 URL 查找表...")
        url_lookup_map = self._build_url_map_from_json(json_data)
        if not url_lookup_map:
            print("[✗] 未能从 JSON 数据中构建任何 URL 映射，无法继续匹配。")
            return
        print(f"[√] URL 查找表构建完成，包含 {len(url_lookup_map)} 个条目。")
            
        # 步骤 5: 【核心改动】遍历 Base64 路径，从映射表中查找 URL 并写入 CSV
        successful_matches = 0
        for title, base64_path, src_url in base64_paths_and_titles:
            try:
                # 直接从映射表中获取 URL，无需正则搜索
                original_url = url_lookup_map.get(base64_path)
                
                if original_url:
                    md5_hash = hashlib.md5(original_url.encode('utf-8')).hexdigest()
                    image_name = f"{title[:30].strip()}-{md5_hash[:6]}" 
                    
                    if not self.redis.sismember(self.redis_key, md5_hash):
                        self.redis.sadd(self.redis_key, md5_hash)
                        self.write_to_csv(title, image_name, original_url, csv_path, tag)
                        successful_matches += 1
                        print(f"[匹配成功] 标题: {title[:20]}... | 名称: {image_name} | URL: {original_url}")
                    else:
                        print(f"[跳过] URL已存在: {title[:20]}...")
                else:
                    # 如果在映射表中找不到，说明匹配失败
                    print(f"[FAIL] 匹配失败: 标题: {title[:20]}... | 无法在JSON数据中找到指纹: {base64_path}")

            except Exception as e:
                print(f"[ERROR] 匹配或写入时发生异常: {e}")
                continue 

        print(f"[√] 成功写入 {successful_matches} 条新记录到 CSV。")


    # --- 辅助方法：CSV 写入和翻页逻辑 (不变) ---
    def write_to_csv(self, title, name, url, csv_path, tag):
        """将图片信息写入 CSV 文件 (包含 Title, ImageName, Original_URL, TAG)"""
        try:
            with self.csv_lock:
                file_exists = os.path.exists(csv_path)
                
                with open(csv_path, 'a', newline='', encoding='utf-8-sig') as f:
                    writer = csv.writer(f)
                    if not file_exists or f.tell() == 0:
                        writer.writerow(['Title', 'ImageName', 'Original_URL', "TAG"])
                    writer.writerow([title, name, url, tag])
                    f.flush()
        except Exception as e:
            print(f'[✗] 写入 CSV 异常：{name} -> {e}')


    def crawl_page(self, tag, csv_path):
        next_page_selector = 'a.sp-pagination--next'
        image_card_selector = 'div.search__results' 
        current_page_num = 1
        wait = WebDriverWait(self.driver, 20)
        
        while True:
            print(f"\n==== 开始爬取【{tag}】第 {current_page_num} 页 ====")
            self.get_images(tag, csv_path)
            
            try:
                next_button = wait.until(
                    EC.element_to_be_clickable((By.CSS_SELECTOR, next_page_selector))
                )
                if not next_button.get_attribute('href'):
                        raise NoSuchElementException("Next button has no valid link.")
                
                print(f"[INFO] 找到下一页按钮，准备使用 JS 翻页到第 {current_page_num + 1} 页...")
                self.driver.execute_script("arguments[0].click();", next_button)
                current_page_num += 1
                
                wait.until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, image_card_selector))
                )
                print("[√] 新页面加载稳定，检测到图片容器。")
                time.sleep(random.uniform(2.0, 4.0)) 
                
            except (TimeoutException, NoSuchElementException):
                print(f"[完成] 标签【{tag}】已爬取到最后一页 (第 {current_page_num} 页或找不到下一页按钮)。")
                return True 
            except Exception as e:
                print(f"[✗] 翻页时发生错误: {e}")
                return False

    def main(self):
        if not self.driver:
            print("[致命错误] WebDriver 未成功初始化，无法继续爬取。")
            return
            
        # --- 配置路径：请修改为你的实际路径 ---
        save_path_all = r'D:\work\爬虫\爬虫数据\creativemarket'
        tag_file_path = r"D:\work\爬虫\ram_tag_list_备份.txt"
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
                search_url = f'{self.base_url}{tag}?categoryIDs=6' 
                self.driver.get(search_url)
                time.sleep(random.uniform(3.0, 5.0))
                
                success = self.crawl_page(tag, csv_path)
                
                if success:
                    print(f'[完成] 【{tag}】全部页面爬取与去重完毕。\n')
                else:
                    print(f'[失败] 【{tag}】爬取失败，请检查网络或网站结构。\n')
            except Exception as e:
                print(f"[✗] 爬取【{tag}】时发生错误: {e}")

        try:
            self.driver.quit()
        except Exception:
            pass

if __name__ == '__main__':
    # --- 配置 ChromeDriver 路径：请修改为你的实际路径 ---
    chrome_driver_path = r'C:\Program Files\Google\1\chromedriver-win32\chromedriver.exe'
    # --------------------------------------------------
    
    spider = creativemarket(chrome_driver_path)
    if spider.driver:
        spider.main()