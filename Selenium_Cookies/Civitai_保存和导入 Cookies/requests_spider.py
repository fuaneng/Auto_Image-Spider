import requests
import re
import csv
import os
import time
from lxml import etree
from queue import Queue, Empty
from threading import Thread, Lock

# --- 配置和常量 ---
BASE_URL = "https://yande.re/post"
HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
    'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
}

# 文件和目录路径配置
TAGS_FILE_PATH = r'D:\爬虫4\Yande.re\ram_tag_24小时.txt'
CSV_FILE_PATH = r'D:\爬虫4\Yande.re\all_records_yande_re_251101.csv'
DOWNLOAD_DIR = r'D:\爬虫4\Yande.re\251101'

# 线程配置
TAG_PROCESS_THREADS = 1  # 标签处理线程数
ENABLE_DOWNLOAD = True  # 是否启用图片下载功能，True为启用，False为禁用
DOWNLOAD_THREADS = 20    # 图片下载线程数（当启用下载功能时使用）
RETRY_COUNT = 3          # 请求失败重试次数

# --- 全局变量和锁 ---
csv_lock = Lock()  # 用于同步CSV文件写入
download_queue = Queue()  # 图片下载队列
data_queue = Queue()      # 待保存数据队列 (用于解耦，可选，这里直接在解析线程中写入CSV)
tag_queue = Queue()       # 待处理标签队列

# --- 辅助函数 ---

def safe_request(url, method='GET', retries=RETRY_COUNT, **kwargs):
    """带重试机制的安全请求函数"""
    for attempt in range(retries):
        try:
            response = requests.request(method, url, headers=HEADERS, timeout=15, **kwargs)
            response.raise_for_status()  # 检查HTTP状态码
            return response
        except requests.exceptions.RequestException as e:
            print(f"请求失败: {url}, 尝试 {attempt + 1}/{retries} 次. 错误: {e}")
            time.sleep(2 ** attempt)  # 指数退避
    return None

def verify_and_get_hd_url(original_url):
    """
    尝试构造并验证高清原图URL
    将 /jpeg/ 替换为 /image/，.jpg 替换为 .png
    """
    # if 'jpeg' not in original_url:
    #     return original_url  # 如果已经是image或其它格式，直接返回

    # 构造高清URL
    hd_url = original_url.replace('/jpeg/', '/image/').replace('.jpg', '.png')
    
    # 验证高清URL是否存在
    try:
        # 使用HEAD请求，只获取头部，更快
        response = safe_request(hd_url, method='HEAD')
        if response and response.status_code == 200:
            return hd_url
        else:
            return original_url
    except Exception as e:
        print(f"高清URL验证失败: {hd_url}, 错误: {e}")
        return original_url

def parse_metadata_from_title(title_str):
    """从img标签的title属性中解析出评分、分数、标签、用户"""
    metadata = {
        'Rating': 'N/A',
        'Score': 'N/A',
        'Tags': 'N/A',
        'User': 'N/A'
    }
    
    # 正则表达式提取，更鲁棒
    rating_match = re.search(r'Rating:\s*([^ ]+)', title_str)
    score_match = re.search(r'Score:\s*(\d+)', title_str)
    user_match = re.search(r'User:\s*([^ ]+)', title_str)
    tags_match = re.search(r'Tags:\s*(.+?)(?:\s*User:|$)', title_str) # 提取Tags，直到遇到User: 或字符串末尾

    if rating_match:
        metadata['Rating'] = rating_match.group(1).strip()
    if score_match:
        metadata['Score'] = score_match.group(1).strip()
    if user_match:
        metadata['User'] = user_match.group(1).strip()
    if tags_match:
        tags_str = tags_match.group(1).strip()
        # 清理多余空格和格式
        metadata['Tags'] = ' '.join(tags_str.split()) 

    return metadata

def write_to_csv(data):
    """安全地将数据写入CSV文件"""
    fieldnames = ['Rating', 'Score', 'Tags', 'User', 'ImageName', 'URL']
    
    # 确保目录存在
    os.makedirs(os.path.dirname(CSV_FILE_PATH), exist_ok=True)
    
    with csv_lock:  # 使用锁确保多线程写入安全
        # 以追加模式打开，如果文件不存在则创建并写入表头
        file_exists = os.path.exists(CSV_FILE_PATH) and os.path.getsize(CSV_FILE_PATH) > 0
        
        with open(CSV_FILE_PATH, mode='a', newline='', encoding='utf-8-sig') as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            
            if not file_exists:
                writer.writeheader()
            
            writer.writerow(data)

# --- 核心爬虫逻辑 ---

def process_tag_page(tag, page):
    """处理单个标签的某一页"""
    url = f"{BASE_URL}/{tag}"
    params = {'page': page}
    print(f"--- 正在爬取 Tag: {tag}, Page: {page} ---")

    response = safe_request(url, params=params)
    if not response:
        print(f"获取页面失败: Tag={tag}, Page={page}")
        return False, 0 # 返回是否还有下一页，以及本页解析到的图片数

    try:
        html = etree.HTML(response.text)
        
        # 匹配所有包含图片信息的li元素
        # 使用XPath: //ul[@id='post-list']/li[starts-with(@id, 'p')]
        # 或者更简短的：//li[starts-with(@id, 'p')]
        post_elements = html.xpath('//li[starts-with(@id, "p")]')
        
        if not post_elements:
            print(f"Tag: {tag}, Page: {page} 未找到图片，可能已是最后一页或页面结构变化。")
            # 检查是否有 'Next' 链接，如果没有则认为是最后一页
            next_page_link = html.xpath('//a[@class="next_page"]')
            has_next = bool(next_page_link)
            return has_next, 0 

        for post_li in post_elements:
            # 1. 提取元数据（Rating, Score, Tags, User）
            # 数据都在<img>标签的title属性中
            img_title = post_li.xpath('.//img[@class="preview"]/@title')
            if not img_title:
                continue
            
            metadata = parse_metadata_from_title(img_title[0])
            
            # 2. 提取图片URL和PostID
            # 图片URL在 <a class="directlink largeimg" href="..."> 属性中
            directlink_url = post_li.xpath('.//a[@class="directlink largeimg"]/@href')
            if not directlink_url:
                continue
            original_url = directlink_url[0]
            
            # 提取PostID，例如从 <li id="p1246002"> 中提取 '1246002'
            li_id = post_li.attrib.get('id', '')
            post_id = li_id[1:] if li_id.startswith('p') else 'Unknown'

            # 3. 构造图片名称
            safe_tags = metadata['Tags'].replace(' ', '_').replace('/', '_').replace(':', '_')
            image_name = f"yande.re {post_id} {safe_tags}.jpg"
            
            # 4. 验证并获取高清URL (同步操作，因为验证较快且必须先知道URL)
            final_url = verify_and_get_hd_url(original_url)

            # 5. 组装数据
            record = {
                'Rating': metadata['Rating'],
                'Score': metadata['Score'],
                'Tags': metadata['Tags'],
                'User': metadata['User'],
                'ImageName': image_name,
                'URL': final_url
            }
            
            # 6. 实时保存数据到CSV (同步操作，但有锁保护)
            write_to_csv(record)
            
            # 7. 如果启用下载功能，将下载任务放入队列
            if ENABLE_DOWNLOAD:
                download_queue.put({'url': final_url, 'name': image_name})
            
        # 检查是否有 'Next' 链接
        next_page_link = html.xpath('//a[@class="next_page"]')
        has_next = bool(next_page_link)

        print(f"Tag: {tag}, Page: {page} 解析完成，找到 {len(post_elements)} 张图片。")
        return has_next, len(post_elements)

    except Exception as e:
        print(f"解析页面时发生错误: Tag={tag}, Page={page}, 错误: {e}")
        return False, 0


# --- 线程类 ---
class TagProcessor(Thread):
    """标签处理线程：负责从tag_queue中取出标签，并爬取其所有页面"""
    def __init__(self, tag_queue):
        super().__init__()
        self.tag_queue = tag_queue
        self.daemon = True # 保持 daemon=True，以便主程序退出时它能随之结束

    def run(self):
        while True:
            try:
                # 获取标签 (使用 timeout=1 让线程在队列清空后能自然退出，这在 TagProcessor 中是可接受的)
                tag = self.tag_queue.get(timeout=1)
                print(f"[标签处理线程] 开始处理标签: {tag}")
                
                page = 1
                while True:
                    has_next, count = process_tag_page(tag, page)
                    if not has_next or count == 0:
                        break  # 没有下一页或本页没有图片则停止
                    page += 1
                    time.sleep(0.5) # 适当休息，防止请求过快

                print(f"[标签处理线程] 标签 {tag} 处理完成。")
                self.tag_queue.task_done() # 标记此任务完成
            except Empty:
                # 这是正常退出机制，不再是错误
                break 
            except Exception as e:
                print(f"[标签处理线程] 发生未知错误: {e}")
                if 'tag' in locals():
                    self.tag_queue.task_done() # 确保任务完成


class ImageDownloader(Thread):
    """图片下载线程：负责从download_queue中取出任务，并下载图片"""
    def __init__(self, download_queue):
        super().__init__()
        self.download_queue = download_queue
        # 移除了 daemon=True，如果希望在主程序结束后等待它完成，最好移除。
        # 如果保留 daemon=True，你需要确保所有任务被取出并 task_done() 后，主线程才能退出。
        self.daemon = True 
        os.makedirs(DOWNLOAD_DIR, exist_ok=True)

    def run(self):
        while True:
            try:
                # 使用阻塞式 get()，等待直到有任务或收到哨兵 None
                task = self.download_queue.get() 
                
                # 检查哨兵值 (None)
                if task is None:
                    self.download_queue.task_done() # 标记哨兵任务完成
                    print(f"[{self.name}] 收到退出信号，安全退出。")
                    break # 安全退出线程
                    
                url = task['url']
                name = task['name']
                save_path = os.path.join(DOWNLOAD_DIR, name)
                
                # ... (下载逻辑不变)
                if os.path.exists(save_path):
                    print(f"[{self.name}] 文件已存在，跳过: {name}")
                    self.download_queue.task_done()
                    continue

                print(f"[{self.name}] 正在下载: {name} from {url}")

                response = safe_request(url, stream=True)
                if response:
                    with open(save_path, 'wb') as f:
                        for chunk in response.iter_content(chunk_size=8192):
                            f.write(chunk)
                    print(f"[{self.name}] 下载成功: {name}")
                else:
                    print(f"[{self.name}] 下载失败，跳过: {name}")
                    
                self.download_queue.task_done() # 标记此任务完成
            except Exception as e:
                print(f"[{self.name}] 发生未知错误: {e}")
                self.download_queue.task_done() # 确保任务被标记完成


# --- 主程序 (main 函数) ---
def main():
    print("--- yande.re 爬虫启动 ---")
    
    # 1. 读取标签文件 (不变)
    tags = []
    try:
        with open(TAGS_FILE_PATH, 'r', encoding='utf-8') as f:
            tags = [line.strip() for line in f if line.strip()]
        print(f"成功读取 {len(tags)} 个标签。")
    except FileNotFoundError:
        print(f"错误: 标签文件未找到，请检查路径: {TAGS_FILE_PATH}")
        return

    # 2. 将标签放入标签队列 (不变)
    for tag in tags:
        tag_queue.put(tag)

    # 3. 启动标签处理线程 (不变)
    tag_processors = []
    for i in range(TAG_PROCESS_THREADS):
        t = TagProcessor(tag_queue)
        tag_processors.append(t)
        t.start()
        print(f"启动标签处理线程-{i+1}")

    # 4. 如果启用下载功能，启动图片下载线程 (不变)
    downloaders = []
    if ENABLE_DOWNLOAD and DOWNLOAD_THREADS > 0:
        for i in range(DOWNLOAD_THREADS):
            d = ImageDownloader(download_queue)
            downloaders.append(d)
            d.start()
            print(f"启动图片下载线程-{i+1}")
    else:
        print("图片下载功能未启用，将只进行数据抓取")

    # 5. 等待所有标签处理任务完成
    print("\n等待标签处理线程完成所有页面抓取和解析...")
    tag_queue.join()
    print("所有标签页面已处理完毕。")

    # ******* 6. 注入哨兵，等待下载线程完成 *******
    if ENABLE_DOWNLOAD and DOWNLOAD_THREADS > 0:
        print(f"发送 {DOWNLOAD_THREADS} 个退出信号给下载线程...")
        # 向队列中放入与下载线程数相等的 None 哨兵
        for _ in range(DOWNLOAD_THREADS):
            download_queue.put(None)
        
        # 等待所有图片下载任务完成（包括哨兵任务）
        print("等待图片下载线程完成所有下载任务...")
        download_queue.join()
        print("所有图片下载任务已完成。")

    print("\n--- yande.re 爬虫运行结束 ---")

if __name__ == '__main__':
    main()