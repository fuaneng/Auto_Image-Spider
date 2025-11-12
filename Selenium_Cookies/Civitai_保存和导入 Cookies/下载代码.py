import os
import csv
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from concurrent.futures import ThreadPoolExecutor, as_completed
import time
import random

# ---------------- 配置区 ----------------
# 这是爬虫生成的 CSV 文件的目录
CSV_DIR_PATH = r"R:\py\Auto_Image-Spider\Selenium_Cookies\Civitai_保存和导入 Cookies\Civitai_图片数据_CSV"
# 图片下载保存的目录
DOWNLOAD_DIR_PATH = r"R:\py\Civitai_保存和导入 Cookies\civitai\pic\Civitai_下载图片"

# 下载参数
MAX_WORKERS = 8             # 最大并发下载线程数
CHUNK_SIZE = 1024 * 10      # 每次写入文件块的大小 (10KB)
TIMEOUT = 15                # 请求超时时间 (秒)

# 反爬设置
HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Accept': 'image/avif,image/webp,image/apng,image/svg+xml,image/*,*/*;q=0.8',
    'Accept-Encoding': 'gzip, deflate, br',
    'Connection': 'keep-alive',
    'Referer': 'https://civitai.com/' # 伪装来源，增强反爬能力
}

# ---------------- 核心下载类 ----------------

class Downloader:
    def __init__(self):
        os.makedirs(DOWNLOAD_DIR_PATH, exist_ok=True)
        self.downloaded_count = 0
        self.failed_count = 0
        self.total_tasks = 0

    def get_session(self):
        """配置带有重试机制的 requests.Session"""
        session = requests.Session()
        # 设置重试策略
        retry_strategy = Retry(
            total=3,                # 总重试次数
            backoff_factor=1,       # 重试之间的等待时间倍数 (1s, 2s, 4s...)
            status_forcelist=[429, 500, 502, 503, 504],  # 触发重试的 HTTP 状态码
            allowed_methods=["HEAD", "GET", "OPTIONS"]
        )
        adapter = HTTPAdapter(max_retries=retry_strategy)
        session.mount("https://", adapter)
        session.mount("http://", adapter)
        return session

    def download_image(self, session, image_name, url, tag):
        """下载单个图片并保存到文件"""
        file_path = os.path.join(DOWNLOAD_DIR_PATH, tag, image_name)

        if os.path.exists(file_path):
            # print(f"[{tag}] ⏩ 已存在: {image_name}")
            return 1 # 标记为成功，避免重复下载

        try:
            # 添加随机延迟，避免请求频率过高
            time.sleep(random.uniform(0.1, 0.5)) 
            
            # 使用流式下载 (stream=True) 配合分块写入
            response = session.get(url, headers=HEADERS, timeout=TIMEOUT, stream=True)
            response.raise_for_status()  # 如果状态码不是 200，则抛出异常

            # 确保子目录存在
            os.makedirs(os.path.dirname(file_path), exist_ok=True)

            with open(file_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=CHUNK_SIZE):
                    if chunk:
                        f.write(chunk)
            
            # print(f"[{tag}] ✅ 成功下载: {image_name}")
            return 1

        except requests.exceptions.RequestException as e:
            print(f"[{tag}] ❌ 下载失败: {image_name} - {e}")
            self.failed_count += 1
            return 0
        except Exception as e:
            print(f"[{tag}] ❌ 发生未知错误: {image_name} - {e}")
            self.failed_count += 1
            return 0

    def process_csv_file(self, csv_file_path, tag):
        """读取 CSV 文件并提交下载任务"""
        print(f"\n📂 正在读取文件: {tag}.csv")
        tasks = []
        with open(csv_file_path, 'r', newline='', encoding='utf-8-sig') as f:
            reader = csv.reader(f)
            next(reader)  # 跳过表头
            
            for row in reader:
                if len(row) >= 2:
                    image_name = row[0]
                    url = row[1]
                    tasks.append((image_name, url, tag))

        self.total_tasks += len(tasks)
        print(f"    - 发现 {len(tasks)} 条下载任务。")

        session = self.get_session()
        
        # 使用线程池并发下载
        with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
            future_to_download = {
                executor.submit(self.download_image, session, name, url, tag): name 
                for name, url, tag in tasks
            }
            
            for future in as_completed(future_to_download):
                result = future.result()
                if result == 1:
                    self.downloaded_count += 1
                
                # 实时显示进度
                if (self.downloaded_count + self.failed_count) % 10 == 0 or (self.downloaded_count + self.failed_count) == self.total_tasks:
                     print(f"    -> 进度: {self.downloaded_count}/{self.total_tasks} 成功 | {self.failed_count} 失败", end='\r')


    def run(self):
        """主入口：遍历所有 CSV 文件"""
        csv_files = [f for f in os.listdir(CSV_DIR_PATH) if f.endswith('.csv')]
        
        if not csv_files:
            print(f"❌ 未在 {CSV_DIR_PATH} 中找到任何 CSV 文件。请先运行爬虫。")
            return

        for filename in csv_files:
            tag = filename.replace('tag_', '').replace('.csv', '')
            csv_path = os.path.join(CSV_DIR_PATH, filename)
            self.process_csv_file(csv_path, tag)

        print(f"\n\n============================================")
        print(f"✅ 下载任务完成！")
        print(f"总任务数: {self.total_tasks}")
        print(f"成功下载: {self.downloaded_count}")
        print(f"失败次数: {self.failed_count}")
        print(f"文件保存路径: {DOWNLOAD_DIR_PATH}")
        print(f"============================================")


if __name__ == "__main__":
    downloader = Downloader()
    downloader.run()