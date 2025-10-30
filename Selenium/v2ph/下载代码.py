import requests
import os
import pandas as pd
import time
from concurrent.futures import ThreadPoolExecutor, as_completed # 引入多线程关键库

# === 1. 配置信息和路径设置 ===
# **请根据你的实际情况修改以下变量**
csv_path = r"R:\py\Auto_Image-Spider\Selenium\v2ph\v2ph_data_251029_copy.csv"
download_root_dir = r"R:\py\Auto_Image-Spider\Selenium\v2ph\images"

# CSV 文件中包含图片 URL 和标题的列名
# CSV 文件中包含图片 URL 和标题的列名
# -----------------------------------------------
IMAGE_URL_COL = 'URL'      # <-- 🌟 修正：使用实际的列名 'URL'
# -----------------------------------------------
TITLE_COL = 'Title'        # 使用 'Title' 列作为子文件夹名
# 下载请求头 (通常用于绕过防盗链检查)
HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
    # !!! 关键 !!! 模拟从原始网站发起请求
    'Referer': 'https://v2ph.com/' 
}

# 多线程配置
MAX_WORKERS = 10 # 最大线程数，即同时下载任务的数量

# 下载间隔（秒），在多线程环境下可以适当调小或移除，但为了安全和礼貌，我们保留它作为**线程启动前的延迟**
# 在线程池中，线程会并发执行，这个延迟可以控制任务提交的速度。
DOWNLOAD_DELAY = 0.05 

# === 2. 辅助函数：清理文件名和文件夹名 ===
def sanitize_name(name):
    """
    清理字符串，移除在文件/文件夹名中不允许的特殊字符。
    """
    invalid_chars = '<>:"/\\|?*\n\r\t'
    for char in invalid_chars:
        name = name.replace(char, '_')
    return name.strip()

# === 3. 核心下载逻辑 (保持不变，但现在由线程调用) ===
def download_image(url, save_path, title_name):
    """
    下载单个图片，并保存到指定的路径。
    返回一个描述结果的字符串。
    """
    log_prefix = f"[Title: {title_name[:15]}]"

    if os.path.exists(save_path):
        return f"{log_prefix} [跳过] 文件已存在: {os.path.basename(save_path)}"

    try:
        # 发起 HTTP GET 请求
        response = requests.get(url, headers=HEADERS, stream=True, timeout=15)

        # 检查响应状态码
        if response.status_code == 200:
            # 将图片内容写入文件
            with open(save_path, 'wb') as f:
                # 逐块写入，适用于大文件
                for chunk in response.iter_content(chunk_size=8192):
                    f.write(chunk)
            
            file_size = os.path.getsize(save_path) / 1024  # 转换为 KB
            return f"{log_prefix} ✅ 下载成功！大小: {file_size:.2f} KB"

        elif response.status_code == 403:
            return f"{log_prefix} ❌ 下载失败！状态码: {response.status_code} (Forbidden)。提示: 可能是防盗链，请检查 Referer。"
        else:
            return f"{log_prefix} ❌ 下载失败！状态码: {response.status_code}"
            
    except requests.exceptions.RequestException as e:
        return f"{log_prefix} ❌ 请求发生错误: {e}"
    except Exception as e:
        return f"{log_prefix} ❌ 发生未知错误: {e}"

# === 4. 任务准备和提交函数 ===
def prepare_and_submit_task(executor, index, row, download_root_dir):
    """
    准备下载参数，创建文件夹，并将下载任务提交给线程池。
    """
    image_url = row.get(IMAGE_URL_COL)
    title = str(row.get(TITLE_COL)) 
    
    # 打印正在准备处理的行信息
    # print(f"--- 准备提交第 {index + 1} 行任务 ---")

    if not image_url:
        print(f"  [警告] 第 {index + 1} 行图片 URL 为空，跳过。")
        return None

    # 1. 清理标题并构建子文件夹路径
    sanitized_title = sanitize_name(title)
    sub_dir = os.path.join(download_root_dir, sanitized_title)

    # 2. 确保子文件夹存在 (需要在主线程中执行，避免多个线程同时创建文件夹)
    if not os.path.exists(sub_dir):
        try:
            os.makedirs(sub_dir)
            print(f"  [创建] 子文件夹: {sanitized_title}")
        except Exception as e:
            # 即使在主线程创建，也可能因为网络路径权限等问题失败
            print(f"  [错误] 无法创建文件夹 {sub_dir}: {e}")
            return None
    
    # 3. 获取文件名
    try:
        file_name = os.path.basename(image_url).split('?')[0]
        if not file_name:
            file_name = f"image_{index + 1}.jpg"
    except:
        file_name = f"image_{index + 1}.jpg"

    # 4. 完整的保存路径
    save_path = os.path.join(sub_dir, file_name)

    # 5. 提交下载任务到线程池
    future = executor.submit(download_image, image_url, save_path, title)
    return future


# === 5. 程序主入口 ===
def main():
    print(f"🚀 开始批量多线程下载图片 (最大线程数: {MAX_WORKERS})...")
    print(f"CSV 路径: {csv_path}")
    print(f"下载根目录: {download_root_dir}\n")

    # 确保下载根目录存在
    if not os.path.exists(download_root_dir):
        os.makedirs(download_root_dir)
        print(f"创建下载根目录: {download_root_dir}")

    try:
        # 读取 CSV 文件
        df = pd.read_csv(csv_path)
        total_rows = len(df)
        print(f"成功读取 {total_rows} 行数据。")
        
        # 检查关键列是否存在
        if IMAGE_URL_COL not in df.columns or TITLE_COL not in df.columns:
            print(f"\n🚨 错误: CSV 文件中缺少必要的列。")
            print(f"  必需的列有: '{IMAGE_URL_COL}' 和 '{TITLE_COL}'")
            print(f"  实际拥有的列: {list(df.columns)}")
            return

        # 使用 ThreadPoolExecutor (上下文管理器，确保线程池在结束时自动关闭)
        with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
            futures = []
            
            # 1. 提交所有任务
            for index, row in df.iterrows():
                future = prepare_and_submit_task(executor, index, row, download_root_dir)
                if future:
                    futures.append(future)
                
                # 在提交任务之间设置一个微小的延迟，以控制任务提交速率
                time.sleep(DOWNLOAD_DELAY)
            
            print(f"\n✅ 已提交 {len(futures)} 个下载任务到线程池，开始等待下载完成...")
            start_time = time.time()

            # 2. 等待并处理结果
            # as_completed 会在任务完成后立即返回 Future 对象，可以实时打印结果
            for i, future in enumerate(as_completed(futures)):
                try:
                    result = future.result() # 获取线程的返回结果 (即 download_image 的返回值)
                    print(f"[{i + 1}/{len(futures)}] {result}")
                except Exception as e:
                    print(f"  [线程错误] 任务执行发生异常: {e}")

        end_time = time.time()
        print(f"\n🎉 所有图片下载任务完成！总耗时: {end_time - start_time:.2f} 秒")

    except FileNotFoundError:
        print(f"\n🚨 错误: 找不到指定的 CSV 文件: {csv_path}")
    except pd.errors.EmptyDataError:
        print("\n🚨 错误: CSV 文件为空。")
    except Exception as e:
        print(f"\n🚨 发生致命错误: {e}")

if __name__ == "__main__":
    main()