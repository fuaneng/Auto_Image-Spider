# 文件名: video_url_extractor.py (DOM 提取修正版)

import pandas as pd
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, WebDriverException, NoSuchElementException, ElementClickInterceptedException
import time
import os
import re
import json
from urllib.parse import urlparse, urlunparse

class VideoSourceExtractor:
    """
    负责读取 CSV 中的链接，直接从加载的页面 DOM 中提取视频源地址。
    不再需要复杂的性能日志监听。
    """
    def __init__(self, chrome_driver_path=None):
        options = Options()
        
        # 移除所有性能日志配置 (options.capabilities["goog:loggingPrefs"] 等)，
        # 因为我们不再使用 driver.get_log('performance')

        # 保持非无头模式（浏览器可见）
        options.add_argument('--window-size=1920,1080')
        options.add_argument('--disable-gpu')
        
        # 禁用自动化控制栏
        options.add_experimental_option("excludeSwitches", ["enable-automation"])
        options.add_experimental_option('useAutomationExtension', False)

        # 启动 WebDriver
        if chrome_driver_path and os.path.exists(chrome_driver_path):
            from selenium.webdriver.chrome.service import Service
            service = Service(executable_path=chrome_driver_path)
            self.driver = webdriver.Chrome(service=service, options=options)
            print("【INFO】使用手动指定的 ChromeDriver 路径。")
        else:
            print("【INFO】使用 Selenium Manager 自动管理 ChromeDriver。")
            self.driver = webdriver.Chrome(options=options)
            
        self.VIDEO_PLAYER_SELECTOR = 'div.fp-player'
        self.VIDEO_ELEMENT_SELECTOR = f'{self.VIDEO_PLAYER_SELECTOR} video'
        
    def listen_for_video_url(self, url):
        """打开页面，移除遮挡，并通过 DOM 元素提取视频源地址。"""
        
        print(f"\n[🔍] 正在访问: {url}")
        
        try:
            # 1. 导航到目标 URL
            self.driver.get(url)
            WebDriverWait(self.driver, 10).until(
                EC.presence_of_element_located((By.TAG_NAME, 'body'))
            )
            time.sleep(2) # 页面初步加载稳定
            
            # 2. 移除广告遮挡元素 (保持此步骤以确保能点击)
            print("[🧹] 尝试使用 JS 移除常见的广告遮挡元素...")
            ad_selectors = [
                'div[id*="ad"]', 'div[class*="ad"]', '.interstitial', '.overlay', 
                'iframe[id*="ad"]', 'div[style*="position: fixed"]', '#top_popup', '.ad-layer'
            ]
            
            js_script_hide_ads = """
            var selectors = arguments[0];
            selectors.forEach(function(selector) {
                document.querySelectorAll(selector).forEach(function(element) {
                    if (element.tagName !== 'BODY' && element.tagName !== 'HTML') {
                        element.style.display = 'none'; 
                    }
                });
            });
            """
            self.driver.execute_script(js_script_hide_ads, ad_selectors)
            time.sleep(1) 

            # 3. 模拟点击播放按钮 (触发视频加载)
            print("[👆] 尝试模拟点击播放区域...")
            
            play_button_selector = 'button[aria-label="Play"], .video-player-container, .player, .play-button, .vjs-big-play-button' 
            
            try:
                video_element_placeholder = WebDriverWait(self.driver, 5).until(
                    EC.element_to_be_clickable((By.CSS_SELECTOR, play_button_selector))
                )
                self.driver.execute_script("arguments[0].click();", video_element_placeholder)
                print("    [√] 成功点击播放元素。")
                
            except (TimeoutException, NoSuchElementException, ElementClickInterceptedException):
                self.driver.execute_script("document.querySelector('body').click();")
                print("    [~] 未找到特定按钮或被拦截，点击 body 元素。")
            
            # 等待视频元素加载
            time.sleep(3) 

            # --- 核心修正: 强制可见并提取 SRC ---
            
            # 4. 强制 video 容器可见
            print(f"[👀] 强制使 {self.VIDEO_PLAYER_SELECTOR} 元素可见...")
            js_script_make_visible = f"""
            var player = document.querySelector('{self.VIDEO_PLAYER_SELECTOR}');
            if (player) {{
                player.style.visibility = 'visible';
                player.style.position = 'static';
                player.style.display = 'block';
            }}
            """
            self.driver.execute_script(js_script_make_visible)
            
            # 5. 找到 <video> 元素并提取 src 属性
            video_element = WebDriverWait(self.driver, 5).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, self.VIDEO_ELEMENT_SELECTOR))
            )
            raw_src = video_element.get_attribute('src')
            
            if raw_src:
                # 6. 清理 URL: 移除末尾的查询参数（如 ?rnd=...）
                parsed_url = urlparse(raw_src)
                # 重新构建 URL，只保留 scheme, netloc, path (移除 query)
                clean_url = urlunparse(parsed_url._replace(query=''))

                print(f"【🎉】成功捕获影片源 URL (原始): {raw_src}")
                print(f"【🎉】成功捕获影片源 URL (清理后): {clean_url}")
                return clean_url
            
        except TimeoutException:
            print(f"【✗】超时: 未在指定时间内找到 {self.VIDEO_ELEMENT_SELECTOR} 元素。")
            
        except WebDriverException as e:
            print(f"【✗】导航或操作失败: {e}")
            
        except Exception as e:
            print(f"【✗】发生未知异常: {e}")
            
        return None

    
    def process_csv(self, csv_path):
        """读取 CSV 文件，处理链接，并更新影片源地址。"""
        if not os.path.exists(csv_path):
            print(f"【✗】错误: 文件未找到，请确认路径是否正确: {csv_path}")
            return

        df = pd.read_csv(csv_path, encoding='utf-8-sig')
        
        if 'url' not in df.columns:
            df['url'] = pd.NA
        
        for index, row in df.iterrows():
            href = row['href']
            if pd.notna(row.get('url')) and row['url'] not in ['', 'NOT_FOUND']:
                print(f"[跳过] 索引 {index}: 链接已存在 ({row['url']})")
                continue
            
            video_url = self.listen_for_video_url(href)
            
            if video_url:
                df.loc[index, 'url'] = video_url
            else:
                df.loc[index, 'url'] = 'NOT_FOUND'
                print(f"【⚠️】警告: 未找到 {row['Title']} 的影片源。")

        print("\n[💾] 正在将更新后的数据保存回 CSV 文件...")
        df.to_csv(csv_path, index=False, encoding='utf-8-sig')
        print("【完成】影片源地址提取完成，请检查 CSV 文件。")


    def run(self, csv_path, chrome_driver_path=None):
        """主执行流程"""
        try:
            self.process_csv(csv_path)
        finally:
            self.driver.quit()
            print("浏览器已关闭。")

# ----------------------------------------------------
# 导入和执行方式
# ----------------------------------------------------

if __name__ == '__main__':
    # --- 配置信息 ---
    
    # 请确保 SAVE_PATH_ALL 和 CSV_FILE_PATH 变量的定义是正确的
    SAVE_PATH_ALL = r'R:\py\Auto_Image-Spider\爬虫数据\wallpaperswide'
    CSV_FILE_PATH = os.path.join(SAVE_PATH_ALL, 'all_records.csv')
    
    # 保持你能够正常运行的路径，或者设置为 None 让 Selenium 自动管理
    CHROME_DRIVER_PATH = r'C:\Program Files\Google\chromedriver-win64\chromedriver.exe'

    # --- 开始执行 ---
    
    if not os.path.exists(CSV_FILE_PATH):
        print(f"【✗】错误: 目标 CSV 文件不存在 ({CSV_FILE_PATH})。请先运行第一个爬虫脚本。")
    else:
        try:
            extractor = VideoSourceExtractor(CHROME_DRIVER_PATH)
            extractor.run(CSV_FILE_PATH, CHROME_DRIVER_PATH)
        except Exception as e:
            # 捕获其他可能的 CSV 读取错误
            print(f"【✗】读取 CSV 发生错误: {e}")