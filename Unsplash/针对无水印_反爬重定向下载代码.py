import os
import re
import time
import threading
from concurrent.futures import ThreadPoolExecutor
import pandas as pd
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.common.exceptions import (
    WebDriverException, TimeoutException
)
import urllib3
import glob

# 导入 HEIC 支持
from pillow_heif import register_heif_opener
try:
    register_heif_opener()
except ImportError:
    pass 

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# ---------- 全局控制 ----------
lock = threading.Lock()
current = 0
total = 0
# 假设你在 __main__ 中设置的下载路径
GLOBAL_DOWNLOAD_PATH = "" 
# 【重要】请将此处替换为你的 ChromeDriver 实际路径！
CHROME_DRIVER_PATH = r"C:\Program Files\Google\chromedriver-win64\chromedriver.exe" 

# ---------- 基础函数 ----------
def sanitize_filename(s: str) -> str:
    """清理文件名，移除无效字符"""
    return re.sub(r'[^\w\s\u4e00-\u9fff-.]', '', str(s)).strip().replace(' ', '-')


def get_target_folder(tag: str) -> str:
    """根据 TAG 获取目标下载文件夹"""
    folder = os.path.join(GLOBAL_DOWNLOAD_PATH, sanitize_filename(tag))
    os.makedirs(folder, exist_ok=True)
    return folder

# ---------- Selenium 驱动 (带下载配置) ----------
def get_selenium_driver(target_folder: str) -> webdriver.Chrome:
    """创建新的 WebDriver 实例，并配置下载到 target_folder"""
    opts = Options()
    opts.add_argument("--headless=new") 
    opts.add_argument("--disable-gpu")
    opts.add_argument("--no-sandbox")
    opts.add_argument("--disable-dev-shm-usage")
    opts.add_argument("--window-size=1920,1080")
    opts.add_experimental_option('excludeSwitches', ['enable-logging'])
    
    prefs = {
        "download.prompt_for_download": False,  
        "download.default_directory": target_folder, 
        "savefile.default_directory": target_folder,
        "profile.default_content_settings.popups": 0
    }
    opts.add_experimental_option("prefs", prefs)

    return webdriver.Chrome(service=Service(CHROME_DRIVER_PATH), options=opts)

# ---------- 文件等待与查找（增强版）----------
def wait_for_download_and_find(target_folder: str) -> str | None:
    """
    等待下载完成，找到下载的文件并返回其默认文件名。

    加入了文件大小稳定性判断，以确保浏览器实例在文件完成写入后再关闭。

    Returns:
        str | None: 成功则返回文件的完整路径，失败则返回 None。
    """
    
    # 【取消固定超时，但设置一个非常长的最大等待时间】
    MAX_WAIT_SECONDS = 300  # 5分钟，如果文件巨大，可以适当增加
    
    start_time = time.time()
    last_known_size = -1
    stabilized_time = 0
    STABILITY_THRESHOLD = 3 # 文件大小连续 3 秒不变，则认为下载完成
    
    print(f"[下载管理] 监控目录: {target_folder}")

    while time.time() - start_time < MAX_WAIT_SECONDS:
        
        # 查找正在下载的临时文件 (*.crdownload)
        temp_files = glob.glob(os.path.join(target_folder, "*.crdownload"))
        
        # 查找已完成的文件：非临时文件（排除 .crdownload 和 .tmp）
        downloaded_files = [
            f for f in glob.glob(os.path.join(target_folder, "*"))
            if not f.endswith((".crdownload", ".tmp"))
        ]
        
        # 找到下载开始后最新创建的文件
        recent_downloads = [
            f for f in downloaded_files
            if os.path.getmtime(f) > start_time - 5 and os.path.getsize(f) > 1000 # 确保文件大小大于 1KB
        ]

        if not temp_files and recent_downloads:
            # 1. 发现已完成文件 (crdownload 已消失)
            latest_file_path = max(recent_downloads, key=os.path.getmtime)
            current_size = os.path.getsize(latest_file_path)
            
            if current_size == last_known_size:
                # 2. 文件大小稳定，增加计时
                stabilized_time += 1
                if stabilized_time >= STABILITY_THRESHOLD:
                    # 3. 达到稳定性阈值，确认下载完成
                    print(f"[下载成功] 文件大小稳定 ({current_size} bytes)，确认完成。")
                    return latest_file_path
            else:
                # 4. 文件大小仍在变化，重置计时器
                last_known_size = current_size
                stabilized_time = 0

            print(f"[下载管理] 稳定检查中... 大小: {current_size} (已稳定 {stabilized_time}s)")

        elif temp_files:
            # 仍在下载中
            print(f"[下载管理] 正在下载中... 已耗时: {int(time.time() - start_time)}s")
        
        else:
            # 既没有 crdownload 也没有已完成文件，可能下载失败或文件太小
            print(f"[下载管理] 等待下载或完成... 已耗时: {int(time.time() - start_time)}s")
            
        time.sleep(1) # 每秒检查一次

    # 5. 超时处理
    print(f"[下载失败] 达到最大等待时间 ({MAX_WAIT_SECONDS}s)，下载未完成或失败。")
    # 检查是否有残留的 .tmp 文件，作为失败日志的参考
    tmp_files = glob.glob(os.path.join(target_folder, "*.tmp"))
    if tmp_files:
         print(f"[下载失败] 发现残留临时文件: {os.path.basename(max(tmp_files, key=os.path.getmtime))}")
    return None

# ---------- 状态记录 ----------
def record_status(status_csv_path, url, tag, title, status, msg, path=""):
    """使用新的表格列名记录状态"""
    global current
    with lock:
        current += 1
        print(f"[{current}/{total}] {status} {url}")
        
        # 保存默认的文件名
        saved_filename = os.path.basename(path) if path else ""
        
        pd.DataFrame([{
            "URL": url,
            "Status": status,
            "Message": msg,
            "下载后的文件名": saved_filename, 
            "原对应TAG": tag,           
            "原标题": title,              
            "SavedPath": path if status == "✅成功" else ""
        }]).to_csv(status_csv_path, mode='a', index=False,
                   header=not os.path.exists(status_csv_path), encoding='utf-8-sig')


# ---------- 线程工作函数 ----------
def selenium_worker(args):
    """Selenium 实例逐个打开图像 URL，实现自动保存下载"""
    url, row, base_path, tag, status_csv = args
    
    driver = None
    saved_path = ""
    ok = False
    
    raw_name = str(row.get('ImageName', 'image')).strip()
    title = raw_name 

    try:
        folder = get_target_folder(tag)
        driver = get_selenium_driver(folder)

        print(f"[{current+1}/{total}] [开始下载] {url}")
        driver.get(url)
        
        # 4. 等待下载完成并找到文件名 (现在使用了文件稳定性判断)
        saved_path = wait_for_download_and_find(folder)
        ok = saved_path is not None

        # 5. 记录状态
        record_status(
            status_csv, url, tag, title,
            "✅成功" if ok else "❌失败",
            "自动下载完成" if ok else "下载失败或超时",
            saved_path if ok else ""
        )
        
    except TimeoutException:
        print(f"[下载失败] {url} -> 页面加载超时")
        record_status(status_csv, url, tag, title, "❌失败", "页面加载超时")
    except WebDriverException as e:
        # 常见的错误如：连接丢失、崩溃等
        print(f"[下载异常] {url} -> WebDriver 错误: {e}")
        record_status(status_csv, url, tag, title, "❌失败", f"WebDriver 错误: {e}")
    except Exception as e:
        print(f"[下载异常] {url} -> 意外错误: {e}")
        record_status(status_csv, url, tag, title, "❌失败", f"意外错误: {e}")
    finally:
        if driver:
            # 【关键】文件稳定后，理论上可以立即关闭。这里留一个短暂延迟作为安全缓冲区。
            time.sleep(1) 
            driver.quit()


# ---------- 主程序入口 ----------
if __name__ == "__main__":
    
    # --- 请根据你的实际环境修改以下路径 ---
    default_path = r"\\10.58.134.120\爬虫数据\unsplash\images1"
    download_path = input(f"下载路径(回车默认): {default_path}").strip() or default_path
    
    GLOBAL_DOWNLOAD_PATH = download_path
    
    os.makedirs(download_path, exist_ok=True)
    
    if not os.path.exists(CHROME_DRIVER_PATH):
         print(f"【错误】ChromeDriver 路径不存在: {CHROME_DRIVER_PATH}")
         print("请修改代码中的 CHROME_DRIVER_PATH 变量！")
         exit()

    csv_path = r"D:\myproject\Code\爬虫\爬虫数据\unsplash\建筑_records.csv"
    status_csv_path = os.path.join(download_path, "建筑_records.csv")
    # ------------------------------------

    df = pd.read_csv(csv_path)
    downloaded_ids = set()
    
    if os.path.exists(status_csv_path):
        try:
            df_s = pd.read_csv(status_csv_path)
            if '原标题' in df_s.columns and '原对应TAG' in df_s.columns:
                 df_s['ID'] = df_s['原标题'].astype(str) + "|" + df_s['原对应TAG'].astype(str)
                 downloaded_ids = set(df_s.loc[df_s["Status"] == "✅成功", "ID"])
            
        except Exception:
            pass

    tasks = []
    for _, r in df.iterrows():
        current_title = str(r.get('ImageName', ''))
        current_tag = str(r.get('TAG', ''))
        current_id = current_title + "|" + current_tag
        
        if pd.notna(r.URL) and current_id not in downloaded_ids:
            tasks.append((r.URL, r, download_path, r.TAG, status_csv_path))

    total = len(tasks)
    print(f"待下载: {total} 个")

    MAX_THREADS = 5 
    
    with ThreadPoolExecutor(max_workers=MAX_THREADS) as ex:
        ex.map(selenium_worker, tasks)

    print("\n✅ 全部任务完成")