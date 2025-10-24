from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
from selenium.common.exceptions import TimeoutException, NoSuchElementException
# <--- 新增：导入并发处理库 --->
from concurrent.futures import ThreadPoolExecutor
import os, time, hashlib, redis, csv, threading, random, re, urllib.parse, requests
from datetime import datetime, timedelta


class yande_re:
    def __init__(self, chrome_driver_path, use_headless=True, redis_host='localhost', redis_port=6379, download_workers=10, parser_workers=3, tag_workers=3):
        self.chrome_driver_path = chrome_driver_path
        self.use_headless = use_headless
        self.base_url = 'https://yande.re/'
        self.csv_lock = threading.Lock()
        self.redis_key = 'image_md5_set_yande.re'
        self.image_save_dir = ''
        self.progress_file_path = ''  # 将在main方法中设置
        self.set_lock = threading.Lock()
        self.parser_workers = parser_workers
        self.download_workers = download_workers
        self.tag_workers = tag_workers
        # 仅初始化下载线程池，解析线程池在每个tag任务中临时创建
        self.download_executor = ThreadPoolExecutor(max_workers=self.download_workers, thread_name_prefix='Downloader')
        print(f"✅ 下载线程池已启动，最大线程数: {self.download_workers}")
        self.main_container_selector = 'div#post-list-posts li[id^="p"], div#content li[id^="p"]'
        try:
            self.redis = redis.Redis(host=redis_host, port=redis_port, db=0, decode_responses=True)
            self.redis.ping()
            print("✅ Redis 连接成功。")
        except Exception:
            print("⚠️ Redis 不可用，将使用内存去重。")
            self.redis = None
            self.visited_md5 = set()

    def resume_incomplete_downloads(self, csv_path):
        import pandas as pd
        if not os.path.exists(csv_path):
            return
        try:
            df = pd.read_csv(csv_path)
        except Exception as e:
            print(f"[断点补全] 读取CSV失败: {e}")
            return
        for _, row in df.iterrows():
            image_name = row.get('ImageName')
            week_label = row.get('WeekLabel')
            image_url = row.get('URL')
            if not image_name or not week_label or not image_url:
                continue
            safe_week_folder_name = re.sub(r'[\\/*?:"<>|]', '_', str(week_label))
            save_path = os.path.join(self.image_save_dir, safe_week_folder_name, image_name)
            temp_path = save_path + ".downloading"
            if not os.path.exists(save_path) or os.path.exists(temp_path):
                print(f"[断点补全] 重新下载未完成图片: {image_name}")
                self.download_executor.submit(self.download_image, image_url, save_path)
    def process_tag(self, tag, csv_path, enable_download=True):
        # 独立创建Selenium实例
        service = Service(executable_path=self.chrome_driver_path)
        options = Options()
        options.add_experimental_option("excludeSwitches", ["enable-automation"])
        options.add_experimental_option('useAutomationExtension', False)
        options.add_argument(
            'user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        )
        # if self.use_headless:
        #     options.add_argument('--headless=new')
        # options.add_argument("--window-size=1920,1080")
        driver = webdriver.Chrome(service=service, options=options)
        parser_executor = ThreadPoolExecutor(max_workers=self.parser_workers, thread_name_prefix='Parser')
        try:
            search_url = f"{self.base_url}{tag}"
            print(f"\n📄 开始处理新标签：【{tag}】\nURL: {search_url}")
            driver.get(search_url)
            wait = WebDriverWait(driver, 30)
            wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, self.main_container_selector)))
            print("[√] 主图片容器加载完成。")
            post_containers = driver.find_elements(By.CSS_SELECTOR, self.main_container_selector)
            total_cards = len(post_containers)
            print(f"🖼️ 共检测到 {total_cards} 个图片容器，开始并行处理...")
            futures = []
            for card_ele in post_containers:
                future = parser_executor.submit(self.process_image_card, card_ele, tag, csv_path, enable_download)
                futures.append(future)
            processed_count = 0
            for future in futures:
                if future.result():
                    processed_count += 1
            print(f"✅ 标签【{tag}】处理完成: 成功处理 {processed_count}/{total_cards} 个图片")
            self.mark_tag_as_processed(tag)
            delay = random.uniform(1, 3)
            print(f"⏳ 随机等待 {delay:.1f} 秒后处理下一个标签...")
            time.sleep(delay)
        except Exception as e:
            print(f"[✗] 处理标签 {tag} 时遇到严重错误: {e}")
        finally:
            parser_executor.shutdown(wait=True)
            driver.quit()

    # 下载功能（已包含断点下载逻辑）
    def download_image(self, image_url, save_path):
        temp_path = save_path + ".downloading"
        try:
            os.makedirs(os.path.dirname(save_path), exist_ok=True)
            if os.path.exists(save_path):
                print(f"🟡 [已完成] 跳过: {os.path.basename(save_path)}")
                return
            if os.path.exists(temp_path):
                print(f"� [断点续传] 检测到未完成下载，重新下载: {os.path.basename(save_path)}")
                os.remove(temp_path)
            print(f"\n📥 开始下载: {os.path.basename(save_path)}")
            response = requests.get(image_url, stream=True, timeout=60)
            response.raise_for_status()
            total_size = int(response.headers.get('content-length', 0))
            block_size = 8192
            downloaded = 0
            with open(temp_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=block_size):
                    f.write(chunk)
                    downloaded += len(chunk)
                    if total_size:
                        percent = int((downloaded / total_size) * 100)
                        print(f"\r💾 下载进度: {percent}% [{downloaded}/{total_size} bytes]", end='', flush=True)
            os.rename(temp_path, save_path)
            print(f"\n✅ 下载完成: {os.path.basename(save_path)}")
        except requests.exceptions.RequestException as e:
            print(f"❌ [下载失败] 网络请求错误: {e} | URL: {image_url}")
            if os.path.exists(temp_path):
                os.remove(temp_path)
        except Exception as e:
            print(f"❌ [下载失败] 未知错误: {e} | 保存路径: {save_path}")
            if os.path.exists(temp_path):
                os.remove(temp_path)

    # 原图检测逻辑
    def get_hq_image_url(self, lowres_url):
        try:
            if "/jpeg/" in lowres_url or lowres_url.endswith(".jpg"):
                hq_url = lowres_url.replace("/jpeg/", "/image/").rsplit(".", 1)[0] + ".png"
                resp = requests.head(hq_url, timeout=10)    # 如果网络慢可以设置更大超时
                if resp.status_code == 200:
                    print(f"🟢 检测到更高清原图: {hq_url[:100]}...") # 打印前100个字符，避免日志过长
                    return hq_url
                else:
                    print(f"⚪ 无高清原图: {hq_url[:100]}... [{resp.status_code}]") # 打印前100个字符，避免日志过长
                    pass
        except Exception as e:
            print(f"⚠️ 原图检测异常: {e}, 通常因为网络问题。")
        return lowres_url

    # tag 转换逻辑
    def parse_tag_to_week_label(self, tag: str) -> str:
        try:
            match = re.search(r'day=(\d+)&month=(\d+)&year=(\d+)', tag)
            if not match:
                return tag 

            day, month, year = map(int, match.groups())
            start_date = datetime(year, month, day)
            end_date = start_date + timedelta(days=6)
            iso_year, iso_week, _ = end_date.isocalendar()
            week_label = (
                f"{start_date.year}年{start_date.month}月{start_date.day}日 - "
                f"{end_date.year}年{end_date.month}月{end_date.day}日（{iso_year}年第{iso_week}周）"
            )
            return week_label
        except Exception as e:
            print(f"⚠️ tag 转换失败: {e} | 原始: {tag}")
            return tag

    # ---------------------- 主逻辑 ----------------------
    def get_images(self, tag, csv_path):
        print(f"--- 正在解析【{tag}】的图片列表...")

        wait = WebDriverWait(self.driver, 30)
        try:
            wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, self.main_container_selector)))
            print("[√] 主图片容器加载完成。")
        except TimeoutException:
            print("[✗] 页面加载超时，找不到主图片容器。")
            return

        post_containers = self.driver.find_elements(By.CSS_SELECTOR, self.main_container_selector)
        print(f"🖼️ 共检测到 {len(post_containers)} 个图片容器。")

        for idx, card_ele in enumerate(post_containers):
            try:
                try:
                    img_ele = card_ele.find_element(By.CSS_SELECTOR, 'a.directlink.largeimg')
                except NoSuchElementException:
                    try:
                        img_ele = card_ele.find_element(By.CSS_SELECTOR, 'a[href*="files.yande.re"]')
                    except NoSuchElementException:
                        continue

                image_url = img_ele.get_attribute('href') or ''
                if not image_url:
                    continue

                image_url = self.get_hq_image_url(image_url)

                try:
                    title_ele = card_ele.find_element(By.CSS_SELECTOR, 'a.thumb img.preview')
                    title = title_ele.get_attribute('title').strip()
                except NoSuchElementException:
                    title = "N/A"

                rating, score, tags_text, user = self.parse_title_info(title)

                md5_hash = hashlib.md5(image_url.encode('utf-8')).hexdigest()
                if self.is_duplicate(md5_hash):
                    continue

                week_label = self.parse_tag_to_week_label(tag)
                image_name = os.path.basename(urllib.parse.urlparse(image_url).path)
                
                # 写入CSV是快速操作，保持在主线程
                self.write_to_csv(rating, score, tags_text, user, image_name, image_url, csv_path, week_label)

                # <--- 修改：将下载任务提交到线程池，实现异步下载 --->
                safe_week_folder_name = re.sub(r'[\\/*?:"<>|]', '_', week_label)
                full_save_path = os.path.join(self.image_save_dir, safe_week_folder_name, image_name)
                self.download_executor.submit(self.download_image, image_url, full_save_path)

            except Exception as e:
                print(f"[✗] 提取失败 idx={idx}: {e}")

    # 标题解析
    def parse_title_info(self, title_text):
        rating, score, tags, user = "N/A", "N/A", "N/A", "N/A"
        try:
            match = re.search(r'Rating:\s*([A-Za-z]+)\s+Score:\s*(\d+)\s+Tags:\s*(.*?)\s+User:\s*(\S+)', title_text)
            if match:
                rating, score, tags, user = match.groups()
        except Exception as e:
            print(f"[⚠️] 标题解析失败: {e} | 原始: {title_text}")
        return rating.strip(), score.strip(), tags.strip(), user.strip()

    # <--- 修改：为内存Set操作增加线程锁 --->
    def is_duplicate(self, md5_hash):
        if hasattr(self, 'redis') and self.redis:
            try:
                if not self.redis.sadd(self.redis_key, md5_hash): # sadd返回0表示已存在
                    return True
            except Exception as e:
                print(f"⚠️ Redis 操作失败: {e}，临时使用内存去重。")
                # Fallback to memory set with lock
                with self.set_lock:
                    if md5_hash in self.visited_md5:
                        return True
                    self.visited_md5.add(md5_hash)
        else:
            with self.set_lock:
                if md5_hash in self.visited_md5:
                    return True
                self.visited_md5.add(md5_hash)
        return False

    # CSV写入
    def write_to_csv(self, rating, score, tags, user, name, url, csv_path, tag_label):
        try:
            with self.csv_lock:
                is_file_empty = not os.path.exists(csv_path) or os.stat(csv_path).st_size == 0
                os.makedirs(os.path.dirname(csv_path), exist_ok=True)
                with open(csv_path, 'a', newline='', encoding='utf-8-sig') as f:
                    writer = csv.writer(f)
                    if is_file_empty:
                        writer.writerow(['Rating', 'Score', 'Tags', 'User', 'ImageName', 'URL', 'WeekLabel'])
                    writer.writerow([rating, score, tags, user, name, url, tag_label])
                    print(f"[✓] 已写入CSV 评分: {score} | URL: {url[:50]}... ")
        except Exception as e:
            print(f"[✗] 写入 CSV 出错: {e}")

    # <--- 新增：断点爬取相关方法 --->
    def load_processed_tags(self):
        """加载已处理的标签列表"""
        if not os.path.exists(self.progress_file_path):
            return set()
        try:
            with open(self.progress_file_path, 'r', encoding='utf-8') as f:
                return {line.strip() for line in f}
        except Exception as e:
            print(f"⚠️ 加载进度文件失败: {e}")
            return set()

    def mark_tag_as_processed(self, tag):
        """将处理完成的标签写入进度文件"""
        try:
            with open(self.progress_file_path, 'a', encoding='utf-8') as f:
                f.write(tag + '\n')
                f.flush()  # 立即写入文件
            print(f"\n{'='*20} 进度保存 {'='*20}")
            print(f"✅ 已将标签【{tag}】标记为已处理")
            print(f"📝 保存至: {self.progress_file_path}")
            print('='*50 + '\n')
        except Exception as e:
            print(f"⚠️ 写入进度文件失败: {e}")

    def process_image_card(self, card_ele, tag, csv_path, enable_download=True):
        """异步处理单个图片卡片"""
        try:
            try:
                img_ele = card_ele.find_element(By.CSS_SELECTOR, 'a.directlink.largeimg')
            except NoSuchElementException:
                try:
                    img_ele = card_ele.find_element(By.CSS_SELECTOR, 'a[href*="files.yande.re"]')
                except NoSuchElementException:
                    return None

            image_url = img_ele.get_attribute('href') or ''
            if not image_url:
                return None

            image_url = self.get_hq_image_url(image_url)

            try:
                title_ele = card_ele.find_element(By.CSS_SELECTOR, 'a.thumb img.preview')
                title = title_ele.get_attribute('title').strip()
            except NoSuchElementException:
                title = "N/A"

            rating, score, tags_text, user = self.parse_title_info(title)

            md5_hash = hashlib.md5(image_url.encode('utf-8')).hexdigest()
            if self.is_duplicate(md5_hash):
                return None

            week_label = self.parse_tag_to_week_label(tag)
            image_name = os.path.basename(urllib.parse.urlparse(image_url).path)
            # 写入CSV是快速操作，保持在主线程
            self.write_to_csv(rating, score, tags_text, user, image_name, image_url, csv_path, week_label)
            # 可选下载
            if enable_download:
                safe_week_folder_name = re.sub(r'[\\/*?:"<>|]', '_', week_label)
                full_save_path = os.path.join(self.image_save_dir, safe_week_folder_name, image_name)
                self.download_executor.submit(self.download_image, image_url, full_save_path)
            return True
        except Exception as e:
            print(f"[✗] 处理图片卡片失败: {e}")
            return None

    def main(self, save_dir, tag_file_path, csv_name='all_records_yande_re_v4.csv', enable_download=False):  # 开启下载设为True，不开启设置为False
        print("\n" + "="*50)
        print("🚀 爬虫启动配置:")
        print(f"📂 保存目录: {save_dir}")
        print(f"🔧 开启下载: {enable_download}")  # 打印下载配置
        print(f"📄 标签文件: {tag_file_path}")
        print(f"📊 记录文件: {csv_name}")
        print("="*50 + "\n")

        os.makedirs(save_dir, exist_ok=True)
        csv_path = os.path.join(save_dir, csv_name)
        self.image_save_dir = os.path.join(save_dir, 'images')
        os.makedirs(self.image_save_dir, exist_ok=True)
        print(f"ℹ️ 图片将保存到: {self.image_save_dir}")
        self.progress_file_path = os.path.join(save_dir, 'processed_tags.txt')
        if not os.path.exists(self.progress_file_path):
            open(self.progress_file_path, 'a').close()
            print(f"✅ 已创建断点续传记录文件: {self.progress_file_path}")
        processed_tags = self.load_processed_tags()
        if processed_tags:
            print(f"✅ 已加载 {len(processed_tags)} 个已处理的标签记录。")
        # 启动时补全未完成图片下载
        print("[断点补全] 检查并补全未完成图片下载...")
        if enable_download:
            self.resume_incomplete_downloads(csv_path)
        try:
            with open(tag_file_path, 'r', encoding='utf-8') as f:
                all_tags = [line.strip() for line in f if line.strip()]
        except FileNotFoundError:
            print(f"[错误] 未找到标签文件: {tag_file_path}")
            return
        print(f"--- 总共发现 {len(all_tags)} 个标签，现在开始并行处理 ---")
        tag_executor = ThreadPoolExecutor(max_workers=self.tag_workers, thread_name_prefix='TagWorker')
        futures = []
        for tag in all_tags:
            if tag in processed_tags:
                print(f"⏭️ [跳过] 标签 '{tag}' 已在之前的运行中处理完毕。")
                continue
            future = tag_executor.submit(self.process_tag, tag, csv_path, enable_download)
            futures.append(future)
        for future in futures:
            future.result()
        tag_executor.shutdown(wait=True)

    # <--- 优雅地关闭浏览器和线程池 --->
    def quit(self):
        print("\n正在等待所有下载任务完成...")
        self.download_executor.shutdown(wait=True)  # 等待所有下载任务完成
        print("✅ 所有下载任务已完成")


if __name__ == '__main__':
    chrome_driver_path = r'C:\Program Files\Google\chromedriver-win64\chromedriver.exe'
    save_dir = r'R:\py\Auto_Image-Spider\yande.re\output_v4'
    tag_file_path = r'R:\py\Auto_Image-Spider\yande.re\ram_tag_周.txt'
    
    # 可以通过在这里实例化时传入 download_workers=10, tag_workers=3 来调整线程数
    spider = None
    try:
        spider = yande_re(chrome_driver_path, use_headless=True, download_workers=10, tag_workers=3)
        spider.main(save_dir=save_dir, tag_file_path=tag_file_path)
    except Exception as main_e:
        print(f"主程序运行出错: {main_e}")
    finally:
        if spider:
            spider.quit()