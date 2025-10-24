import pandas as pd
import os
import re
import threading
from concurrent.futures import ThreadPoolExecutor
from PIL import Image
import io
import time
import requests
import urllib3

# 禁用 SSL 警告
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# --- 全局变量 ---
current = 0
lock = threading.Lock()
total = 0
# 定义重定向目标，用于 requests 检查
REDIRECT_TARGET = 'https://wallpaperswide.com/' 

# --- 工具函数 ---
def sanitize_filename(s):
    """清理文件名中的非法字符"""
    return re.sub(r'[^\w\s\u4e00-\u9fff-.]', '', str(s)).strip().replace(' ', '-')

def is_direct_download(url):
    """判断是否为直接图片链接（这里保留，但代码中不再强制检查）"""
    img_exts = (".jpg", ".jpeg", ".png", ".gif", ".bmp", ".webp")
    return url.lower().endswith(img_exts)

# --- 核心下载函数：纯粹的 requests 下载 (移除重试) ---
def download_image_by_request(args):
    global current
    url, row, base_download_path, tag_folder_name, status_csv_path = args

    img_name = sanitize_filename(str(row.get('ImageName', 'image')))
    name, _ = os.path.splitext(img_name)

    # 自动识别图片扩展名
    ext = os.path.splitext(url.split("?")[0])[1].lower()
    # 简化扩展名处理
    if ext not in [".jpg", ".jpeg", ".png", ".webp", ".bmp"]:
         # 尝试根据 headers 确定，否则默认 .png
        try:
            head_response = requests.head(url, timeout=10, verify=False)
            content_type = head_response.headers.get('content-type', '').lower()
            if 'jpeg' in content_type or 'jpg' in content_type:
                ext = ".jpg"
            elif 'png' in content_type:
                ext = ".png"
            elif 'webp' in content_type:
                ext = ".webp"
            else:
                ext = ".png"
        except Exception:
            ext = ".png"


    file_name = f"{name}{ext}"
    safe_tag_folder = sanitize_filename(tag_folder_name)
    final_dir_path = os.path.join(base_download_path, safe_tag_folder)
    os.makedirs(final_dir_path, exist_ok=True)
    full_path = os.path.join(final_dir_path, file_name)

    def record_status(status, message=""):
        """在下载状态 CSV 中记录结果"""
        global current 
        with lock:
            current += 1
            print(f"[{current}/{total}] {status} {url}")
            df_status = pd.DataFrame([{
                "URL": url,
                "TAG": tag_folder_name,
                "ImageName": img_name,
                "Status": status,
                "Message": message,
                "SavedPath": full_path if status == "✅成功" else ""
            }])
            df_status.to_csv(
                status_csv_path,
                mode='a',
                index=False,
                header=not os.path.exists(status_csv_path),
                encoding='utf-8-sig'
            )

    # 🚀 纯粹的 requests 下载逻辑 (移除重试循环)
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/123.0.0.0 Safari/537.36"
        ),
        "Referer": "https://wallpaperswide.com/"
    }

    try:
        # 直接使用 verify=False 和更长的超时时间（因为没有重试）
        response = requests.get(
            url,
            headers=headers,
            timeout=120, # 增加超时时间以应对网络慢的情况
            proxies={"http": None, "https": None},
            verify=False 
        )
        
        # 检查重定向 
        if response.url.startswith(REDIRECT_TARGET):
            record_status("❌跳过", f"直链重定向到主页: {response.url}")
            return False

        response.raise_for_status() # 检查HTTP状态码

    except Exception as e:
        # 下载失败，直接记录失败并跳过
        record_status("❌失败", f"下载错误: {e.__class__.__name__} - {e}")
        return False

    # 保存文件逻辑
    try:
        # 尝试用 PIL 打开和保存
        image = Image.open(io.BytesIO(response.content))
        # 根据推断出的扩展名选择保存格式
        image_format = "PNG" if ext == ".png" else ("JPEG" if ext in ['.jpg', '.jpeg'] else "WEBP")
        image.save(full_path, image_format)
    except Exception as e:
        # 如果 PIL 失败，直接写入文件内容
        try:
            with open(full_path, "wb") as f:
                f.write(response.content)
        except Exception as file_e:
             record_status("❌失败", f"保存/写入文件失败: {file_e}")
             return False

    record_status("✅成功")
    return True


# --- 主程序入口 (保持不变) ---
if __name__ == "__main__":
    
    default_path = r"\\10.58.134.120\aigc2\01_数据\爬虫数据\wallpaperswide\images"
    download_path = input(f"请输入下载路径（直接回车使用默认路径：{default_path}):").strip() or default_path
    os.makedirs(download_path, exist_ok=True)

    csv_path = r"D:\work\爬虫\爬虫数据\wallpaperswide\all_records3708 - 副本.csv"
    status_csv_path = os.path.join(download_path, "download_status.csv")

    try:
        df = pd.read_csv(csv_path)
    except Exception as e:
        print(f"读取 CSV 文件失败：{e}")
        exit()

    # --- 加载已完成的状态（断点续传） ---
    downloaded_urls = set()
    if os.path.exists(status_csv_path):
        try:
            df_status = pd.read_csv(status_csv_path)
            # 检查 '✅成功' 或 '❌跳过' 的链接
            successful_urls = set(df_status.loc[df_status["Status"].isin(["✅成功", "❌跳过", "❌失败"]), "URL"].astype(str))
            downloaded_urls = successful_urls
            # 💡 注意：这里将"❌失败"也加入已处理集合，确保不再重试已确认失败的链接。
            print(f"✅ 检测到已处理记录 {len(downloaded_urls)} 条（成功/跳过/失败），将跳过这些任务。")
        except Exception:
            pass

    # --- 构建任务列表 ---
    tasks = []
    total_records = len(df)
    for index, row in df.iterrows():
        url = str(row.get("URL"))
        tag = row.get("TAG")

        if pd.notna(url) and pd.notna(tag):
            if url in downloaded_urls:
                continue

            tag_folder_name = str(tag)
            tasks.append((url, row, download_path, tag_folder_name, status_csv_path))

    total = len(tasks)
    skipped_count = total_records - total
    print(f"总记录数：{total_records}")
    print(f"已跳过（已处理或无效）：{skipped_count}")
    print(f"待下载任务数：{total}")

    max_workers = 10
    print(f"使用 {max_workers} 个线程下载...")

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        results = executor.map(download_image_by_request, tasks) 

    success_count = sum(1 for r in results if r)
    print(f"\n下载完成！成功：{success_count}/{total}，失败：{total - success_count}")
    print(f"下载状态已保存到：{status_csv_path}")