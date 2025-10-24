from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
from selenium.common.exceptions import TimeoutException, NoSuchElementException
import os, time, hashlib, redis, csv, threading, random, re, urllib.parse


class ffcu:
    def __init__(self, chrome_driver_path):
        service = Service(executable_path=chrome_driver_path)
        options = Options()
        options.add_experimental_option("excludeSwitches", ["enable-automation"])
        options.add_experimental_option('useAutomationExtension', False)
        options.add_argument(
            'user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36')
        # options.add_argument('--headless')  # 调试完可以开启
        options.add_argument("--window-size=1920,1080")
        self.driver = webdriver.Chrome(service=service, options=options)

        self.base_url = 'https://ffcu.io/'
        self.csv_lock = threading.Lock()
        self.redis_key = 'image_md5_set_ffcu'
        self.main_container_selector = 'div.blog_post_preview.post-listing.image-post-format.one-image-format'

        try:
            self.redis = redis.Redis(host='localhost', port=6379, db=0, decode_responses=True)
            self.redis.ping()
            print("✅ Redis 连接成功。")
        except Exception:
            print("⚠️ Redis 不可用，将使用内存去重。")
            self.redis = None
            self.visited_md5 = set()

    # ---------------------- 提取当前页图片 (修复分步滚动和打印) ----------------------
    def get_images(self, tag, csv_path):
        print(f"--- 正在解析【{tag}】的图片列表...")

        wait = WebDriverWait(self.driver, 30)
        try:
            # 等待第一个图片容器加载
            wait.until(EC.presence_of_element_located((
                By.CSS_SELECTOR, self.main_container_selector)))
            print("[√] 主图片容器加载完成。")
        except TimeoutException:
            print("[✗] 页面加载超时。")
            return

        # === 核心修复区域：分步平滑滚动加载 ===
        SCROLL_HEIGHT = 1080  # 每次滚动的像素距离
        SCROLL_PAUSE_TIME = 2.0  # 每次滚动后的暂停时间
        
        current_scroll_position = 0
        total_scrolls = 0
        window_height = self.driver.execute_script("return window.innerHeight;") # 获取浏览器视口高度
        
        print(f"🚀 开始分步滚动加载 (每步 {SCROLL_HEIGHT}px，暂停 {SCROLL_PAUSE_TIME}秒)...")

        while True:
            total_scrolls += 1
            
            # 1. 计算新的滚动位置并执行滚动
            new_scroll_position = current_scroll_position + SCROLL_HEIGHT
            self.driver.execute_script(f"window.scrollTo(0, {new_scroll_position});")
            
            # 2. 暂停，等待内容加载
            time.sleep(SCROLL_PAUSE_TIME + random.random() * 0.5)
            
            # 3. 更新当前滚动位置和页面总高度
            current_scroll_position = self.driver.execute_script("return window.pageYOffset;")
            page_total_height = self.driver.execute_script("return document.body.scrollHeight")

            # 4. 检查是否到达底部
            # 如果当前滚动位置加上浏览器视口高度约等于页面总高度，则认为到达底部。
            if (current_scroll_position + window_height) >= page_total_height:
                print(f"✅ 滚动到底部。总共滚动了 {total_scrolls} 次。")
                break
                
            # 如果实际滚动位置没有达到预期的 new_scroll_position，通常意味着到达了页面底部
            if current_scroll_position < new_scroll_position:
                 print(f"✅ 滚动到底部 (滚动位置稳定)。总共滚动了 {total_scrolls} 次。")
                 break

        # === 滚动加载结束，开始提取 ===
        
        # 再次确认所有容器都已加载，并计算最终数量
        post_containers = self.driver.find_elements(By.CSS_SELECTOR, self.main_container_selector)
        last_count = len(post_containers)
        print(f"🖼️ 共检测到 {last_count} 个图片容器。")

        # --- 遍历提取 ---
        successful_writes = 0
        
        for idx, card_ele in enumerate(post_containers):
            try:
                # 使用 By.TAG_NAME 定位 img 元素（不受类名差异影响）
                img_ele = card_ele.find_element(By.TAG_NAME, 'img')
                
                # 扩展图片 URL 属性获取
                image_url = (img_ele.get_attribute('src')
                             or img_ele.get_attribute('data-src')       
                             or img_ele.get_attribute('data-original')
                             or img_ele.get_attribute('data-lazy-src')
                             or "")
                                 
                if not image_url:
                    print(f"[跳过] 容器序号 {idx}：未找到有效图片链接。")
                    continue

                # --- 提取标题 ---
                try:
                    title_ele = card_ele.find_element(By.CSS_SELECTOR, 'div.blog_post_title h2 a')
                    title = title_ele.text.strip()
                except NoSuchElementException:
                    title = "未命名图片"

                # --- 清理图片 URL ---
                image_url_cleaned = re.sub(r'-\d+x\d+(?=\.\w+$)', '', image_url)

                # --- 去重及打印修改 ---
                md5_hash = hashlib.md5(image_url_cleaned.encode('utf-8')).hexdigest()
                if self.is_duplicate(md5_hash):
                    # 📢 发现重复项时，打印跳过信息
                    print(f"[重复] 容器序号 {idx}：【{title}】URL {image_url_cleaned} 已存在，跳过。")
                    continue

                # --- 写入 CSV ---
                image_name = os.path.basename(image_url_cleaned)
                self.write_to_csv(title, image_name, image_url_cleaned, csv_path, tag)
                
                # 📢 成功写入时，打印成功信息
                print(f"✔️ 写入成功！【{title}】")
                successful_writes += 1

            except NoSuchElementException:
                continue 
            except Exception as e:
                print(f"[✗] 容器序号 {idx} 提取图片信息失败: {e}")
                
        print(f"✅ 【{tag}】本页共检测 {len(post_containers)} 个容器，成功写入 {successful_writes} 条记录。")


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
                # 优化写入逻辑，检查文件是否存在和是否为空
                is_file_empty = not os.path.exists(csv_path) or os.stat(csv_path).st_size == 0
                
                with open(csv_path, 'a', newline='', encoding='utf-8-sig') as f:
                    writer = csv.writer(f)
                    if is_file_empty:
                        writer.writerow(['Title', 'ImageName', 'URL', 'Tag'])
                    writer.writerow([title, name, url, tag])
        except Exception as e:
            print(f"[✗] 写入 CSV 出错: {e}")

    # ---------------------- 翻页逻辑 ----------------------
    def crawl_page(self, tag, csv_path):
        page_num = 1
        wait = WebDriverWait(self.driver, 15)

        while True:
            print(f"\n=== 正在爬取【{tag}】第 {page_num} 页 ===")
            self.get_images(tag, csv_path)

            try:
                # 尝试定位“Next”按钮
                next_btn = self.driver.find_element(By.XPATH, "//li[@class='next_page']/a[contains(text(),'Next')]")
                next_url = next_btn.get_attribute("href")
                
                if not next_url:
                    print(f"[完成] 【{tag}】共爬取 {page_num} 页。")
                    break

                self.driver.get(next_url)
                time.sleep(random.uniform(3, 5))
                
                # 等待下一页图片容器加载
                wait.until(EC.presence_of_element_located(
                    (By.CSS_SELECTOR, self.main_container_selector)))
                
                page_num += 1
            except NoSuchElementException:
                # 未找到 Next 按钮，认为到达最后一页
                print(f"[完成] 【{tag}】共爬取 {page_num} 页。")
                break
            except Exception as e:
                print(f"[✗] 翻页过程中出现错误: {e}")
                print(f"[完成] 【{tag}】共爬取 {page_num} 页。")
                break

    # ---------------------- 主函数 ----------------------
    def main(self):
        save_dir = r'D:\work\爬虫\爬虫数据\ffcu'
        tag_file_path = r'D:\work\爬虫\ram_tag_list.txt'
        os.makedirs(save_dir, exist_ok=True)
        csv_path = os.path.join(save_dir, 'all_records_ffcu_01.csv')

        try:
            with open(tag_file_path, 'r', encoding='utf-8') as f:
                tags = [line.strip() for line in f if line.strip()]
        except FileNotFoundError:
            print(f"[错误] 未找到标签文件: {tag_file_path}")
            return

        print(f"--- 发现 {len(tags)} 个标签 ---")

        for tag in tags:
            try:
                encoded_tag = urllib.parse.quote_plus(tag)
                search_url = f"{self.base_url}?s={encoded_tag}"
                print(f"\n--- 开始处理：【{tag}】 ---\nURL: {search_url}")
                self.driver.get(search_url)
                time.sleep(random.uniform(3, 5))

                try:
                    # 确保搜索结果页有图片容器
                    WebDriverWait(self.driver, 15).until(
                        lambda d: d.find_elements(By.CSS_SELECTOR, self.main_container_selector))
                except TimeoutException:
                    print(f"[跳过] {tag} 页面未加载出图片容器。")
                    continue

                self.crawl_page(tag, csv_path)
            except Exception as e:
                print(f"[✗] 处理标签 {tag} 出错: {e}")

        # driver.quit() 会在 finally 块中处理

if __name__ == '__main__':
    # ⚠️ 请确认你的驱动路径是否正确！
    chrome_driver_path = r'C:\Program Files\Google\1\chromedriver-win32\chromedriver.exe'
    
    spider = None # 初始化为 None
    try:
        spider = ffcu(chrome_driver_path)
        spider.main()
    except Exception as main_e:
        print(f"主程序运行出错: {main_e}")
    finally:
        # 确保无论程序是否出错，WebDriver 都会关闭
        if spider and spider.driver:
            print("\n正在关闭浏览器...")
            spider.driver.quit()