import requests
import pandas as pd
import os
import time
# 修复：导入 threading 库，用于在日志中显示线程名称
import threading 
import concurrent.futures
from typing import List, Tuple, Dict, Any, Optional

# --- 配置 ---
CSV_PATH = r'R:\py\Auto_Image-Spider\Requests\1x_com\1x_com_awarded.csv'
DOWNLOAD_DIR = r'R:\py\Auto_Image-Spider\Requests\1x_com\images'
# 用于 Referer 头的基准 URL 
BASE_REFERER_URL = 'https://1x.com/'
MAX_WORKERS = 6 # 线程池中最大线程数

# --- 隐秘性配置 ---
HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
    'Connection': 'keep-alive',
    'Accept': 'image/webp,image/apng,image/*,*/*;q=0.8',
}
THREAD_START_DELAY = 0.1 


def download_image(image_url: str, save_path: str, referer_url: str) -> bool:
    """
    下载单张图片到指定路径，并添加反爬必要的请求头。
    此函数将在单独的线程中运行。
    """
    # 在线程启动时加入微小延迟，增强隐秘性
    time.sleep(THREAD_START_DELAY)

    custom_headers = HEADERS.copy()
    custom_headers['Referer'] = referer_url
    
    filename = os.path.basename(save_path)
    thread_name = threading.current_thread().name # 使用已导入的 threading 模块获取线程名
    
    # 跳过已下载的文件，避免重复劳动
    if os.path.exists(save_path):
        print(f"[{thread_name}] 跳过: {filename} 已存在。")
        return True

    try:
        # 使用 with requests.Session() 来管理单个线程内的连接
        with requests.Session() as session:
            # 2. 发送 GET 请求
            response = session.get(image_url, headers=custom_headers, stream=True, timeout=20)
            response.raise_for_status() # 检查 HTTP 错误
            
            # 3. 写入文件
            with open(save_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    f.write(chunk)
                    
            print(f"[{thread_name}] ✅ 成功下载: {filename}")
            return True
            
    except requests.exceptions.RequestException as e:
        print(f"[{thread_name}] ❌ 下载失败 ({filename}): {e}")
        return False
    except Exception as e:
        print(f"[{thread_name}] ❌ 写入文件失败 ({filename}): {e}")
        return False


def main_downloader_threaded():
    """
    主下载逻辑：读取 CSV，使用 ThreadPoolExecutor 进行并发下载。
    """
    
    # 1. 检查并创建下载目录
    if not os.path.exists(DOWNLOAD_DIR):
        os.makedirs(DOWNLOAD_DIR)
        print(f"已创建下载目录: {DOWNLOAD_DIR}")
        
    # 2. 读取 CSV 文件
    try:
        df = pd.read_csv(CSV_PATH)
        image_urls: List[str] = df['图片地址'].tolist() 
        
    except FileNotFoundError:
        print(f"错误：未找到 CSV 文件: {CSV_PATH}")
        return
    except KeyError:
        print("错误：CSV 文件中未找到名为 '图片地址' 的列。请检查 CSV 格式。")
        return
    except Exception as e:
        print(f"读取 CSV 文件失败: {e}")
        return

    total_images = len(image_urls)
    tasks: List[Tuple[str, str, str]] = [] # 存储 (url, save_path, referer)
    
    # 3. 准备任务列表
    for url in image_urls:
        filename = url.split('/')[-1]
        save_path = os.path.join(DOWNLOAD_DIR, filename)
        referer = BASE_REFERER_URL 
        tasks.append((url, save_path, referer))

    print(f"\n--- 开始多线程下载 (最大线程数: {MAX_WORKERS})，总共 {total_images} 张图片 ---")
    
    downloaded_count = 0
    
    # 4. 使用 ThreadPoolExecutor 并发执行任务
    with concurrent.futures.ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        # 使用 submit 将任务提交给线程池
        future_to_url = {
            executor.submit(download_image, url, save_path, referer): url 
            for url, save_path, referer in tasks
        }
        
        # 使用 as_completed 遍历已完成的任务结果
        for future in concurrent.futures.as_completed(future_to_url):
            url = future_to_url[future]
            try:
                # 获取任务结果 (True/False)
                if future.result():
                    downloaded_count += 1
            except Exception as e:
                # 处理线程执行过程中的异常
                print(f"线程执行图片下载时发生异常 ({url}): {e}")

    print("\n--- 多线程下载完成 ---")
    print(f"总结: 共 {total_images} 个目标，成功下载/跳过 {downloaded_count} 个。")


if __name__ == '__main__':
    main_downloader_threaded()