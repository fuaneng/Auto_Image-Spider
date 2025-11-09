import os
import csv
import re
import requests
import urllib3
from threading import Lock
from concurrent.futures import ThreadPoolExecutor 
from typing import List, Optional, Set, Tuple

# --- 配置常量 ---
# 【必须修改】CSV 文件所在的目录
CSV_LOGS_DIR = r'R:\py\Auto_Image-Spider\Selenium_Undetected-chromedriver\en_girlstop_info\csv_logs'

# 【必须修改】图片下载的根目录 (这将是 [DOWNLOAD_ROOT]/[Model_Name]/[Title]/ 的根目录)
DOWNLOAD_ROOT = r'R:\py\Auto_Image-Spider\Selenium_Undetected-chromedriver\en_girlstop_info\models' 

# 【可选配置】如果只想下载特定 CSV 文件中的图片，请在这里填写文件名列表（包含 .csv 后缀）
# 格式：['Mila-A_results.csv', 'ModelB_results.csv']。如果留空（[]），则下载所有文件。
TARGET_CSV_FILENAMES: List[str] = ['Susann-A_results.csv','Serena-J_results.csv'] 

# 【可选配置】每个 CSV 文件限制处理的相册数量（Title）。
# 5 表示限制前 5 个相册。
# 0 或负数表示不限制，下载所有相册。
ALBUM_LIMIT_PER_CSV = 10 

# 【配置】下载线程数
MAX_DOWNLOAD_WORKERS = 10 

# 忽略不安全请求警告
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# 全局线程锁，用于文件系统操作
file_lock = Lock()

def _sanitize_filename(filename: str) -> str:
    """
    清理文件名或文件夹名，移除不安全的字符，并限制长度。
    """
    # 移除 Windows/Linux 文件名中不允许的字符
    safe_filename = re.sub(r'[\\/:*?"<>|]', '_', filename)
    safe_filename = safe_filename.strip()
    return safe_filename[:150] 

def download_worker(url: str, title: str, model_name: str) -> bool:
    """
    执行单个文件的下载任务，并根据 model_name 和 title 进行分类存储。
    """
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
        'Referer': url # 使用图片 URL 作为 Referer
    }
    
    # 1. 构建存储路径
    safe_model_name = _sanitize_filename(model_name)
    safe_title = _sanitize_filename(title)
    
    # 存储路径：[DOWNLOAD_ROOT]/[model_name]/[title]/
    save_dir = os.path.join(DOWNLOAD_ROOT, safe_model_name, safe_title)
    
    # 从 URL 中提取文件名
    image_name = url.split('/')[-1]
    if '?' in image_name:
         image_name = image_name.split('?')[0] 
    if not image_name:
        image_name = "default_image.jpg"
        
    save_path = os.path.join(save_dir, image_name)

    if os.path.exists(save_path):
        print(f"[{model_name}] [✓] 文件已存在，跳过: {image_name}")
        return True 
    
    # 2. 确保目标文件夹存在
    try:
        os.makedirs(save_dir, exist_ok=True)
    except Exception as e:
        print(f"[{model_name}] [✗] 创建文件夹失败 {save_dir}: {e}")
        return False

    # 3. 下载文件
    try:
        response = requests.get(url, headers=headers, stream=True, verify=False, timeout=20)
        response.raise_for_status() 
        
        # 写入文件
        with file_lock: # 使用锁，确保文件系统操作互斥
            with open(save_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    f.write(chunk)
                    
        print(f"[{model_name}] [✓] 下载成功: {image_name} -> {os.path.join(safe_model_name, safe_title)}")
        return True

    except requests.exceptions.RequestException as e:
        print(f"[{model_name}] [✗] 下载失败: {url}, 错误: {e}")
        return False

def run_downloader():
    """主程序逻辑：读取选定/所有 CSV 文件中的相册任务，并启动异步下载。"""
    
    print(f"🚀 开始异步下载，最大线程数: {MAX_DOWNLOAD_WORKERS}...")
    
    # 检查相册限制，如果 <= 0 则设置为不限制 (None)
    album_limit = ALBUM_LIMIT_PER_CSV if ALBUM_LIMIT_PER_CSV > 0 else None
    
    all_tasks: List[Tuple[str, str, str]] = []
    
    # 获取目标文件名集合，如果为空则处理所有文件
    target_filenames: Optional[Set[str]] = set(TARGET_CSV_FILENAMES) if TARGET_CSV_FILENAMES else None
    
    if target_filenames:
        print(f"   -> 已指定目标 CSV 文件数量: {len(target_filenames)}")
    else:
        print("   -> 模式: 下载所有模特的任务。")

    if album_limit:
        print(f"   -> 限制模式: 每个文件只下载前 {album_limit} 个相册。")
    else:
        print("   -> 限制模式: 不限制相册数量。")


    # 1. 遍历 CSV 目录，读取所有任务
    for filename in os.listdir(CSV_LOGS_DIR):
        if filename.endswith('_results.csv'):
            
            # 过滤逻辑
            if target_filenames and filename not in target_filenames:
                continue
            
            csv_path = os.path.join(CSV_LOGS_DIR, filename)
            print(f"   -> 读取任务文件: {filename}")
            
            processed_albums: Set[str] = set()
            
            try:
                with open(csv_path, 'r', newline='', encoding='utf-8-sig') as f:
                    reader = csv.reader(f)
                    try:
                        next(reader) # 跳过表头
                    except StopIteration:
                        continue
                        
                    for row in reader:
                        # CSV 列结构: ['Title', 'ImageName', 'URL', 'model_name']
                        if len(row) >= 4:
                            title, _, url, model_name = row
                            
                            # 【核心修改点】
                            # 1. 判断当前相册标题是否已在集合中
                            is_new_album = title not in processed_albums
                            
                            # 2. 如果是新的相册，并且达到限制，则不再添加任务，直接退出读取当前文件
                            if is_new_album and album_limit is not None and len(processed_albums) >= album_limit:
                                break 
                            
                            # 3. 将当前相册标题加入集合
                            processed_albums.add(title)
                            
                            # 4. 添加下载任务 (所有属于前 N 个相册的图片都会被添加)
                            all_tasks.append((url, title, model_name))
            except Exception as e:
                print(f"⚠️ 读取 CSV 文件 {filename} 失败: {e}")
                
            print(f"   -> 已从 {filename} 收集 {len(processed_albums)} 个相册的任务。")


    if not all_tasks:
        print("❌ 未在指定 CSV 文件中找到任何下载任务或目标文件。请检查配置。")
        return

    total_tasks = len(all_tasks)
    print(f"\n🎉 总共收集到 {total_tasks} 个下载任务。")

    # 2. 启动异步下载
    with ThreadPoolExecutor(max_workers=MAX_DOWNLOAD_WORKERS) as executor:
        # 提交所有任务到线程池
        futures = [executor.submit(download_worker, *task) for task in all_tasks]

        # 等待所有下载任务完成 (并提供简单进度)
        for i, future in enumerate(futures):
            future.result() 
            if (i + 1) % 50 == 0 or (i + 1) == total_tasks:
                print(f"   下载进度: {i + 1}/{total_tasks} ({((i + 1) / total_tasks) * 100:.2f}%)")

    print("\n✅ 所有异步下载任务完成。")

# --- 程序入口 ---
if __name__ == '__main__':
    # 确保日志和下载根目录存在 (这里只检查，不处理 FileExistsError，假设常量设置正确)
    os.makedirs(DOWNLOAD_ROOT, exist_ok=True)
    os.makedirs(CSV_LOGS_DIR, exist_ok=True) 
    
    run_downloader()