import requests
import os
import re
import pandas as pd # 导入 pandas 库
from concurrent.futures import ThreadPoolExecutor, as_completed

# --- 配置常量 (需与原爬虫脚本保持一致) ---
ROOT_PATH = r"R:\py\Auto_Image-Spider\Requests\Eporner_R18"
# ⚠️ 注意：文件路径更改为 XLSX
XLSX_PATH = os.path.join(ROOT_PATH, "image_data.xlsx") 
IMAGE_DIR = os.path.join(ROOT_PATH, "images")

# 确保下载目录存在
os.makedirs(IMAGE_DIR, exist_ok=True)

# 模拟浏览器请求头
HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
}

# --- 核心下载函数 (保持不变) ---

def download_image(image_info):
    """
    根据图片信息下载图片并保存。
    image_info 格式: {'图片URL': url, '标题': title, '名称': name}
    """
    url = image_info['图片URL']
    title = image_info['标题']
    
    # 1. 确定文件扩展名
    ext_match = re.search(r'\.(\w+)$', url)
    extension = f".{ext_match.group(1)}" if ext_match else ".jpg" 

    # 2. 清理标题以作为安全文件名
    safe_title = re.sub(r'[\\/:*?"<>|]', '_', title)
    
    # 3. 构造完整文件路径
    filename = safe_title + extension
    filepath = os.path.join(IMAGE_DIR, filename)

    # 4. 断点续传/跳过逻辑
    if os.path.exists(filepath) and os.path.getsize(filepath) > 0:
        return f"Skipped (Already Exists): {filename}"
        
    try:
        # 5. 发送请求并下载
        response = requests.get(url, headers=HEADERS, stream=True, timeout=30)
        response.raise_for_status()

        with open(filepath, 'wb') as f:
            for chunk in response.iter_content(chunk_size=8192):
                f.write(chunk)
                
        return f"Downloaded: {filename}"
        
    except requests.exceptions.RequestException as e:
        return f"Error downloading {filename} from {url}: {e}"
        

def read_data_from_xlsx(xlsx_path):
    """从 XLSX 文件中读取所有图片数据（使用 Pandas）"""
    data_list = []
    try:
        # 1. 读取 XLSX 文件，header=0 表示第一行是表头
        df = pd.read_excel(xlsx_path, header=0)
        
        # 2. 确保所需的列名存在
        required_cols = ['图片URL', '标题', '名称']
        if not all(col in df.columns for col in required_cols):
             print(f"🚨 错误：XLSX 文件中缺少必需的列。检测到的列名: {list(df.columns)}")
             return []

        # 3. 将 DataFrame 转换为字典列表
        # .to_dict('records') 可以将每一行转换成一个字典
        data_list = df[required_cols].dropna().to_dict('records')

        print(f"✅ 成功从 XLSX 文件中读取到 {len(data_list)} 条图片记录。")
    except FileNotFoundError:
        print(f"🚨 错误：未找到 XLSX 文件: {xlsx_path}")
        return []
    except Exception as e:
        print(f"🚨 错误：读取 XLSX 文件时发生异常: {e}")
        return []
        
    return data_list


def start_download_executor(all_data):
    """使用ThreadPoolExecutor启动多线程下载 (逻辑保持不变)"""
    if not all_data:
        print("没有图片数据可供下载。")
        return
        
    MAX_WORKERS = 10 
    
    success_count = 0
    error_count = 0
    skipped_count = 0
    total_tasks = len(all_data)
    
    print(f"\n⚡ 启动 {total_tasks} 个多线程下载任务...")
    
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        future_to_info = {executor.submit(download_image, item): item for item in all_data}
        
        for i, future in enumerate(as_completed(future_to_info)):
            try:
                result = future.result()
                
                if result.startswith("Downloaded"):
                    success_count += 1
                elif result.startswith("Skipped"):
                    skipped_count += 1
                elif result.startswith("Error"):
                    error_count += 1
                
                print(f"  [进度 {i+1}/{total_tasks}] {result}")
                
            except Exception as exc:
                print(f"  [EXCEPTION] 任务执行时发生异常: {exc}")
                error_count += 1
                
    print(f"\n🎉 所有下载任务完成！ 总任务数: {total_tasks}")
    print(f"   成功下载: {success_count}， 跳过 (已存在): {skipped_count}， 失败/错误: {error_count}")

# --- 主逻辑 ---
def main():
    # 1. 从 XLSX 文件读取数据
    all_data = read_data_from_xlsx(XLSX_PATH)
    
    if not all_data:
        print("无法继续下载，请确保 XLSX 文件存在且包含数据。")
        return
        
    # 2. 启动下载执行器
    start_download_executor(all_data)

if __name__ == '__main__':
    # 再次提醒安装依赖
    try:
        import pandas
    except ImportError:
        print("\n🚨 缺少必要的库！请运行以下命令进行安装:")
        print("pip install pandas openpyxl")
        exit()
        
    main()