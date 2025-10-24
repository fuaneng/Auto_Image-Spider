from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
from selenium.common.exceptions import TimeoutException, NoSuchElementException, ElementClickInterceptedException
import os, time, hashlib, redis, csv, threading, random, re, urllib.parse, sys


class metmuseum:
    def __init__(self, chrome_driver_path, use_headless=True, redis_host='localhost', redis_port=6379):
        service = Service(executable_path=chrome_driver_path)
        options = Options()
        options.add_experimental_option("excludeSwitches", ["enable-automation"])
        options.add_experimental_option('useAutomationExtension', False)
        options.add_argument(
            'user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36')
        if use_headless:
            options.add_argument('--headless=new')  # 新 headless 模式，或用 '--headless' 取决于 chromedriver 版本
        options.add_argument("--window-size=1920,1080")
        # 推荐禁用图片加载以加快页面解析（如果你需要下载图片则不要禁用）
        # prefs = {"profile.managed_default_content_settings.images": 2}
        # options.add_experimental_option("prefs", prefs)

        self.driver = webdriver.Chrome(service=service, options=options)
        self.base_url = 'https://www.metmuseum.org/'
        self.csv_lock = threading.Lock()
        self.redis_key = 'image_md5_set_metmuseum'
        # 全局一级容器 CSS（保持你提供的选择器）
        self.main_container_selector = 'section.object-grid_grid__hKKqs figure.collection-object_collectionObject__SuPct'

        # Redis 连接（可选）
        try:
            self.redis = redis.Redis(host=redis_host, port=redis_port, db=0, decode_responses=True)
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
            wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, self.main_container_selector)))
            print("[√] 主图片容器加载完成。")
        except TimeoutException:
            print("[✗] 页面加载超时，找不到主图片容器。")
            return

        # === 分步平滑滚动加载（在你原来思路上增强判断） ===
        SCROLL_STEP = 1080  # 每次滚动像素
        MAX_IDLE_ROUNDS = 2  # 当多次滚动页面高度没有变化则停止
        scroll_round = 0
        idle_rounds = 0
        last_height = self.driver.execute_script("return document.body.scrollHeight")
        window_height = self.driver.execute_script("return window.innerHeight;")

        print(f"🚀 开始分步滚动加载 (step={SCROLL_STEP}px)...")
        while True:
            scroll_round += 1
            # 计算新的位置并滚动
            new_pos = min(last_height, (scroll_round * SCROLL_STEP))
            self.driver.execute_script(f"window.scrollTo(0, window.pageYOffset + {SCROLL_STEP});")
            time.sleep(1.0 + random.random() * 1.0)  # 随机等待，降低被阻断的概率

            current_height = self.driver.execute_script("return document.body.scrollHeight")
            current_offset = self.driver.execute_script("return window.pageYOffset;")

            # 打印进度（简短）
            # print(f"  scroll_round={scroll_round}, offset={current_offset}, pageHeight={current_height}")

            # 如果页面高度增加，重置 idle 计数
            if current_height > last_height:
                idle_rounds = 0
                last_height = current_height
            else:
                idle_rounds += 1

            # 到达底部判断：offset + window_height >= total_height - small_margin
            if (current_offset + window_height) >= (current_height - 20):
                print(f"✅ 检测到滚动到底部 (offset+win >= total). rounds={scroll_round}")
                break

            if idle_rounds >= MAX_IDLE_ROUNDS:
                print(f"✅ 停止滚动：已连续 {idle_rounds} 次没有发现页面高度变化。")
                break

            # 安全上限，避免无限循环
            if scroll_round >= 80:
                print("⚠️ 达到最大滚动次数，停止滚动以避免无限循环。")
                break

        # === 滚动加载结束，开始提取 ===
        post_containers = self.driver.find_elements(By.CSS_SELECTOR, self.main_container_selector)
        last_count = len(post_containers)
        print(f"🖼️ 共检测到 {last_count} 个图片容器。")

        successful_writes = 0
        for idx, card_ele in enumerate(post_containers):
            try:
                # 尝试多种方式获取图片元素 / 链接
                img_ele = None
                try:
                    img_ele = card_ele.find_element(By.TAG_NAME, 'img')
                except NoSuchElementException:
                    # 如果没有 img，可寻找 background-image 或 a>img 之类
                    try:
                        img_ele = card_ele.find_element(By.CSS_SELECTOR, 'div img')
                    except NoSuchElementException:
                        img_ele = None

                if not img_ele:
                    print(f"[跳过] 容器序号 {idx}：未找到 img 元素。")
                    continue

                # 先尝试 src，再尝试 data-src 或 srcset
                image_url = img_ele.get_attribute('src') or img_ele.get_attribute('data-src') or ''
                if not image_url:
                    srcset = img_ele.get_attribute('srcset') or ''
                    if srcset:
                        # 从 srcset 中选最大的 (通常最后一个)
                        parts = [p.strip() for p in srcset.split(',') if p.strip()]
                        if parts:
                            last = parts[-1].split()[0]
                            image_url = last

                if not image_url:
                    print(f"[跳过] 容器序号 {idx}：图片 URL 为空。")
                    continue

                # --- 提取标题（优先从 a.link 或 caption） ---
                try:
                    title_ele = card_ele.find_element(By.CSS_SELECTOR, 'div.collection-object_title__1MnJJ a.collection-object_link__qM3YR')
                    title = title_ele.text.strip()
                except NoSuchElementException:
                    # 备用： figcaption 直接文本
                    try:
                        figcap = card_ele.find_element(By.TAG_NAME, 'figcaption')
                        title = figcap.text.splitlines()[0].strip() if figcap.text else "NAN"
                    except Exception:
                        title = "NAN"

                # --- 清理图片 URL (把常见的移动尺寸替换为 original) ---
                # 例如: .../mobile-large/DP701752.jpg  -> .../original/DP701752.jpg
                image_url_cleaned = re.sub(r'/mobile-[^/]+/', '/original/', image_url, flags=re.IGNORECASE)
                # 另外一些路径可能是 /web-large/ 或 /medium/ ，覆盖常见情况
                image_url_cleaned = re.sub(r'/(web|medium|small|thumb)-?large?/', '/original/', image_url_cleaned, flags=re.IGNORECASE)

                # 规范化链接（若为相对链接）
                if image_url_cleaned.startswith('/'):
                    image_url_cleaned = urllib.parse.urljoin(self.base_url, image_url_cleaned)

                # --- 去重 ---
                md5_hash = hashlib.md5(image_url_cleaned.encode('utf-8')).hexdigest()
                if self.is_duplicate(md5_hash):
                    print(f"[重复] 容器序号 {idx}：【{title}】 URL 已存在，跳过。")
                    continue

                # --- 写入 CSV ---
                image_name = os.path.basename(urllib.parse.urlparse(image_url_cleaned).path)
                self.write_to_csv(title, image_name, image_url_cleaned, csv_path, tag)
                print(f"✔️ 写入成功！【{image_url_cleaned}】")
                successful_writes += 1

            except Exception as e:
                print(f"[✗] 容器序号 {idx} 提取图片信息失败: {e}")

        print(f"✅ 【{tag}】本页共检测 {len(post_containers)} 个容器，成功写入 {successful_writes} 条记录。")

    # ---------------------- 去重逻辑 ----------------------
    def is_duplicate(self, md5_hash):
        if self.redis:
            try:
                if self.redis.sismember(self.redis_key, md5_hash):
                    return True
                self.redis.sadd(self.redis_key, md5_hash)
            except Exception as e:
                # 若 Redis 出错，退回到内存集合（确保脚本不崩溃）
                print(f"⚠️ Redis 操作出错，退回到内存去重: {e}")
                if not hasattr(self, 'visited_md5'):
                    self.visited_md5 = set()
                if md5_hash in self.visited_md5:
                    return True
                self.visited_md5.add(md5_hash)
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
                # 确保目录存在
                os.makedirs(os.path.dirname(csv_path), exist_ok=True)
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
                # 翻页：寻找 aria-label="Next Page" 的按钮并点击（这是按钮不是 a.href）
                # 备用选择器： button[aria-label*="Next"] 或 button.pagination-controls_paginationButton__JT_jI[aria-label="Next Page"]
                try:
                    next_btn = self.driver.find_element(By.CSS_SELECTOR, 'button[aria-label="Next Page"]')
                except NoSuchElementException:
                    # 有些页面 button 位置不同，尝试更宽松的匹配
                    try:
                        next_btn = self.driver.find_element(By.CSS_SELECTOR, 'button[aria-label*="Next"]')
                    except NoSuchElementException:
                        next_btn = None

                if not next_btn:
                    print(f"[完成] 未找到 Next 按钮，认为已到最后一页。共爬取 {page_num} 页。")
                    break

                # 如果按钮是禁用的（类名或 disabled 属性），则结束
                disabled = next_btn.get_attribute('disabled')
                if disabled:
                    print(f"[完成] Next 按钮已禁用，结束翻页。共爬取 {page_num} 页。")
                    break

                # 点击下一页
                try:
                    self.driver.execute_script("arguments[0].scrollIntoView({block:'center'});", next_btn)
                    time.sleep(0.5)
                    next_btn.click()
                except ElementClickInterceptedException:
                    # 如果点击被拦截，尝试 JS 点击
                    self.driver.execute_script("arguments[0].click();", next_btn)

                # 随机等待并确保新页面加载出主容器
                time.sleep(random.uniform(2.5, 4.5))
                wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, self.main_container_selector)))
                page_num += 1

            except TimeoutException:
                print(f"[✗] 翻页后页面加载超时，可能没有新内容。已完成 {page_num} 页。")
                break
            except Exception as e:
                print(f"[✗] 翻页过程中出现错误: {e}")
                break

    # ---------------------- 主函数 ----------------------
    def main(self, save_dir, tag_file_path, csv_name='all_records_metmuseum_01.csv'):
        os.makedirs(save_dir, exist_ok=True)
        csv_path = os.path.join(save_dir, csv_name)

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
                search_url = f"{self.base_url}art/collection/search?q={encoded_tag}"
                print(f"\n--- 开始处理：【{tag}】 ---\nURL: {search_url}")
                self.driver.get(search_url)
                time.sleep(random.uniform(2.5, 4.0))

                try:
                    WebDriverWait(self.driver, 15).until(
                        lambda d: d.find_elements(By.CSS_SELECTOR, self.main_container_selector))
                except TimeoutException:
                    print(f"[跳过] {tag} 页面未加载出图片容器。")
                    continue

                self.crawl_page(tag, csv_path)
            except Exception as e:
                print(f"[✗] 处理标签 {tag} 出错: {e}")

    def quit(self):
        try:
            if self.driver:
                self.driver.quit()
        except Exception as e:
            print(f"关闭浏览器出错: {e}")


if __name__ == '__main__':
    # ⚠️ 请确认你的驱动路径是否正确！
    chrome_driver_path = r'C:\Program Files\Google\1\chromedriver-win32\chromedriver.exe'

    # 保存路径与标签文件（示例）
    save_dir = r'D:\work\爬虫\爬虫数据\metmuseum'
    tag_file_path = r'D:\work\爬虫\ram_tag_list.txt'

    spider = None
    try:
        spider = metmuseum(chrome_driver_path, use_headless=True)
        spider.main(save_dir=save_dir, tag_file_path=tag_file_path)
    except Exception as main_e:
        print(f"主程序运行出错: {main_e}")
    finally:
        if spider:
            print("\n正在关闭浏览器...")
            spider.quit()
