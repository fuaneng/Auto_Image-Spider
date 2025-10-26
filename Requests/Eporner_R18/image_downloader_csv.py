import requests
import csv
import os
import re
from concurrent.futures import ThreadPoolExecutor, as_completed

# --- 配置常量 (需与原爬虫脚本保持一致) ---
ROOT_PATH = r"R:\py\Auto_Image-Spider\Requests\Eporner_R18"
CSV_PATH = os.path.join(ROOT_PATH, "123.csv") 
IMAGE_DIR = os.path.join(ROOT_PATH, "images1")

# 确保下载目录存在
os.makedirs(IMAGE_DIR, exist_ok=True)

# 模拟浏览器请求头
HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
}

# --- 核心下载函数 (与主脚本中的一致) ---

def download_image(image_info):
    """
    根据图片信息下载图片并保存到对应的子文件夹中。
    """
    url = image_info['图片URL']
    title = image_info['标题']
    collection_name = image_info['所属集合'] 
    
    ext_match = re.search(r'\.(\w+)$', url)
    extension = f".{ext_match.group(1)}" if ext_match else ".jpg" 

    safe_title = re.sub(r'[\\/:*?"<>|]', '_', title)
    
    # ⚠️ 关键修改：扩展替换规则，将 . 和 - 也替换为 _
    safe_collection_name = re.sub(r'[\\/:*?"<>|.-]', '_', collection_name).strip()
    
    sub_dir = os.path.join(IMAGE_DIR, safe_collection_name)
    os.makedirs(sub_dir, exist_ok=True) 

    filename = safe_title + extension
    filepath = os.path.join(sub_dir, filename) 

    if os.path.exists(filepath) and os.path.getsize(filepath) > 0:
        return f"Skipped (Exists in '{safe_collection_name}'): {filename}"
        
    try:
        response = requests.get(url, headers=HEADERS, stream=True, timeout=30)
        response.raise_for_status()

        with open(filepath, 'wb') as f:
            for chunk in response.iter_content(chunk_size=8192):
                f.write(chunk)
                
        return f"Downloaded to '{safe_collection_name}': {filename}"
        
    except requests.exceptions.RequestException as e:
        return f"Error downloading {filename} to '{safe_collection_name}' from {url}: {e}"
        

def read_data_from_csv(csv_path):
    """
    从 CSV 文件中读取所有图片数据。
    尝试多种编码，以解决手动编辑导致的中文乱码问题。
    """
    data_list = []
    # 定义必须存在的字段
    required_fields = ['图片URL', '标题', '名称', '所属集合']
    
    # 尝试的编码列表，从最可能正确的开始
    encodings_to_try = ['utf-8-sig', 'utf-8', 'gbk'] 
    
    # 尝试读取文件
    for encoding in encodings_to_try:
        try:
            print(f"  [INFO] 尝试使用编码: '{encoding}' 读取 CSV 文件...")
            with open(csv_path, 'r', newline='', encoding=encoding) as csvfile:
                # 必须将文件指针重置到开头，以便 DictReader 重新读取表头
                csvfile.seek(0)
                reader = csv.DictReader(csvfile)
                
                # 检查表头是否成功匹配（即编码是否正确）
                if not reader.fieldnames or not all(field in reader.fieldnames for field in required_fields):
                    # 如果表头不对，说明编码不正确，跳到下一个尝试
                    # print(f"  [DEBUG] 编码 '{encoding}' 失败，表头不匹配。")
                    continue 

                data_list = []
                for row in reader:
                    # 检查关键字段是否存在且非空
                    if all(row.get(f) for f in required_fields):
                        data_list.append(row)
                
                # 如果成功读取到数据（且编码匹配），则返回
                if data_list:
                    print(f"✅ 成功使用编码 '{encoding}' 从 CSV 文件中读取到 {len(data_list)} 条图片记录。")
                    return data_list

        except FileNotFoundError:
            print(f"🚨 错误：未找到 CSV 文件: {csv_path}")
            return []
        except UnicodeDecodeError:
            # 编码错误，尝试下一个
            continue
        except Exception as e:
            print(f"🚨 错误：读取 CSV 文件时发生未知异常: {e}")
            return []

    print(f"🚨 错误：尝试了所有编码 ({', '.join(encodings_to_try)}) 均无法正确读取 CSV 文件。")
    print("请检查文件是否为空，或手动用 VS Code/Notepad++ 等软件将其另存为 'UTF-8' 格式。")
    return []


def start_download_executor(all_data):
    """使用ThreadPoolExecutor启动多线程下载"""
    if not all_data:
        print("没有图片数据可供下载。")
        return
        
    MAX_WORKERS = 10 
    success_count = 0
    error_count = 0
    total_tasks = len(all_data)
    
    print(f"\n⚡ 启动 {total_tasks} 个多线程下载任务...")
    
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        future_to_info = {executor.submit(download_image, item): item for item in all_data}
        
        for i, future in enumerate(as_completed(future_to_info)):
            try:
                result = future.result()
                if result.startswith("Downloaded"):
                    success_count += 1
                elif result.startswith("Error"):
                    error_count += 1
                
                print(f"  [进度 {i+1}/{total_tasks}] {result}")

            except Exception as exc:
                print(f"  [EXCEPTION] 任务执行时发生异常: {exc}")
                error_count += 1
                
    print(f"\n🎉 所有下载任务完成！ 成功: {success_count}， 失败/跳过: {total_tasks - success_count}， 错误: {error_count}")

# --- 主逻辑 ---
def main():
    # 1. 从 CSV 文件读取数据
    all_data = read_data_from_csv(CSV_PATH)
    
    if not all_data:
        print("无法继续下载，请确保 CSV 文件存在且包含数据。")
        return
        
    # 2. 启动下载执行器
    start_download_executor(all_data)

if __name__ == '__main__':
    main()