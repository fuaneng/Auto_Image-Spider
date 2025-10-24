import os
import re
import time
import threading
from concurrent.futures import ThreadPoolExecutor
import pandas as pd
import requests 
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

# 禁用 urllib3 的不安全请求警告
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
    opts.add_argument('--ignore-certificate-errors')
    opts.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
    opts.add_argument("--disable-gpu")
    opts.add_argument("--no-sandbox")
    opts.add_argument("--disable-dev-shm-usage")
    opts.add_argument("--window-size=1920,1080")
    opts.add_experimental_option('excludeSwitches', ['enable-logging'])
    opts.add_experimental_option("excludeSwitches", ["enable-automation"])
    opts.add_experimental_option('useAutomationExtension', False)
    
    prefs = {
        "download.prompt_for_download": False,  
        "download.default_directory": target_folder, 
        "savefile.default_directory": target_folder,
        "profile.default_content_settings.popups": 0
    }
    opts.add_experimental_option("prefs", prefs)

    return webdriver.Chrome(service=Service(CHROME_DRIVER_PATH), options=opts)

# ---------- 文件等待与查找（增强版 - 优化打印频率 V2）----------
def wait_for_download_and_find(target_folder: str) -> str | None:
    """
    等待下载完成，找到下载的文件并返回其默认文件名。
    进一步优化了打印频率。
    """
    MAX_WAIT_SECONDS = 300
    STABILITY_THRESHOLD = 2  # 文件大小稳定的检查次数阈值

    start_time = time.time()
    last_known_size = -1
    stabilized_time = 0
    
    # 控制打印频率增加到 20 秒
    last_print_time = 0 
    PRINT_INTERVAL = 20  # 每 20 秒打印一次状态 

    while time.time() - start_time < MAX_WAIT_SECONDS:
        
        temp_files = glob.glob(os.path.join(target_folder, "*.crdownload"))
        
        downloaded_files = [
            f for f in glob.glob(os.path.join(target_folder, "*"))
            if not f.endswith((".crdownload", ".tmp"))
        ]
        
        recent_downloads = [
            f for f in downloaded_files
            if os.path.getmtime(f) > start_time - 5 and os.path.getsize(f) > 1000 
        ]

        # ----------------------------------------------------
        should_print = False
        current_time = time.time()
        
        if current_time - last_print_time >= PRINT_INTERVAL or last_known_size == -1:
            should_print = True
            last_print_time = current_time
        # ----------------------------------------------------

        if not temp_files and recent_downloads:
            # 1. 发现已完成文件 (crdownload 已消失)
            latest_file_path = max(recent_downloads, key=os.path.getmtime)
            current_size = os.path.getsize(latest_file_path)
            
            if current_size == last_known_size:
                # 2. 文件大小稳定，增加计时
                stabilized_time += 1
                if stabilized_time >= STABILITY_THRESHOLD:
                    # 3. 达到稳定性阈值，确认下载完成
                    print(f"[Selenium下载成功] 文件大小稳定 ({current_size} bytes)，确认完成。")
                    return latest_file_path
            else:
                # 4. 文件大小仍在变化，重置计时器
                last_known_size = current_size
                stabilized_time = 0
                should_print = True # 文件大小变化时立即打印
            
            if should_print:
                # 打印稳定检查信息，只打印 KB 级别大小，避免数字太长
                print(f"[Selenium下载管理] 稳定检查中... 大小: {current_size/1024:.0f}KB (已稳定 {stabilized_time}s)")

        elif temp_files:
            # 仍在下载中
            if should_print:
                print(f"[Selenium下载管理] 正在下载中... 已耗时: {int(current_time - start_time)}s")
            
        else:
            # 既没有 crdownload 也没有已完成文件
            if should_print:
                print(f"[Selenium下载管理] 等待下载或完成... 已耗时: {int(current_time - start_time)}s")

        time.sleep(5) # 每 5 秒检查一次

    # 5. 超时处理
    print(f"[Selenium下载失败] 达到最大等待时间 ({MAX_WAIT_SECONDS}s)，下载未完成或失败。")
    tmp_files = glob.glob(os.path.join(target_folder, "*.tmp"))
    if tmp_files:
        print(f"[Selenium下载失败] 发现残留临时文件: {os.path.basename(max(tmp_files, key=os.path.getmtime))}")
    return None

# ---------- requests 下载函数 - 【优化：移除进度打印】----------
def requests_downloader(url: str, target_folder: str, title: str) -> str | None:
    """
    使用 requests 库下载文件，适用于静态资源 URL。
    """
    
    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        }
        response = requests.get(url, stream=True, timeout=30, headers=headers, verify=False)
        response.raise_for_status() 

        content_type = response.headers.get('Content-Type', '')
        url_path = url.split('?')[0] 
        guessed_extension = '.' + url_path.split('.')[-1] if '.' in url_path.split('/')[-1] else ''

        if 'image/jpeg' in content_type:
            extension = '.jpg'
        elif 'image/png' in content_type:
            extension = '.png'
        elif 'image/gif' in content_type:
            extension = '.gif'
        elif 'image/webp' in content_type:
            extension = '.webp'
        elif 'image/heif' in content_type:
             extension = '.heif'
        else:
            extension = guessed_extension if 1 < len(guessed_extension) < 6 else '.jpg' 

        base_name = sanitize_filename(title)
        final_filename = base_name + extension
        file_path = os.path.join(target_folder, final_filename)
        
        if os.path.exists(file_path) and os.path.getsize(file_path) > 0:
            print(f"[{current+1}/{total}] [Requests跳过] 文件已存在: {final_filename}")
            return file_path

        total_size = int(response.headers.get('content-length', 0))
        chunk_size = 8192 
        
        # 【保留】打印一次开始下载信息
        print(f"[{current+1}/{total}] [Requests开始] {url} (大小: {total_size/1024/1024:.2f}MB)")

        with open(file_path, 'wb') as f:
            for chunk in response.iter_content(chunk_size=chunk_size):
                if chunk: 
                    f.write(chunk)
        
        # 【保留】打印成功信息
        print(f"[Requests成功] 文件: {final_filename}")
        return file_path

    except requests.exceptions.RequestException as e:
        # 【保留】打印失败信息
        print(f"[{current+1}/{total}] [Requests失败] {url} -> 请求错误: {e}")
        return None
    except Exception as e:
        # 【保留】打印异常信息
        print(f"[{current+1}/{total}] [Requests异常] {url} -> 意外错误: {e}")
        return None


# ---------- 状态记录 ----------
def record_status(status_csv_path, url, tag, title, status, msg, path=""):
    """使用新的表格列名记录状态"""
    global current
    with lock:
        current += 1
        # 【这是主要的任务进度打印，保持不变】
        print(f"[{current}/{total}] {status} {url}")
        
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


# ---------- 线程工作函数（修改：加入requests逻辑）----------
def selenium_worker(args):
    """根据 URL 类型，选择使用 requests 或 Selenium 进行下载"""
    url, row, base_path, tag, status_csv = args
    
    driver = None
    saved_path = ""
    ok = False
    
    raw_name = str(row.get('ImageName', 'image')).strip()
    title = raw_name 
    
    # 1. 获取目标文件夹
    folder = get_target_folder(tag)

    # 【关键逻辑：判断是否使用 requests 下载】
    if url.startswith("https://images.unsplash.com/"):
        
        # 走 requests 下载路径
        saved_path = requests_downloader(url, folder, title)
        ok = saved_path is not None
        
        status_msg = "Requests下载完成" if ok else "Requests下载失败"
        
        record_status(
            status_csv, url, tag, title,
            "✅成功" if ok else "❌失败",
            status_msg,
            saved_path if ok else ""
        )
        return # requests 路径结束
        
    # 2. 如果不匹配，继续使用 Selenium 逻辑
    try:
        
        driver = get_selenium_driver(folder)

        print(f"[{current+1}/{total}] [开始下载(Selenium)] {url}")
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
        record_status(status_csv, url, tag, title, "❌失败", "页面加载超时")
    except WebDriverException as e:
        record_status(status_csv, url, tag, title, "❌失败", f"WebDriver 错误: {e}")
    except Exception as e:
        record_status(status_csv, url, tag, title, "❌失败", f"意外错误: {e}")
    finally:
        if driver:
            time.sleep(1) 
            driver.quit()


# ---------- 主程序入口 ----------
if __name__ == "__main__":
    
    # --- 请根据你的实际环境修改以下路径 ---
    default_path = r"D:\myproject\Code\爬虫\爬虫数据\unsplash\images1"
    download_path = input(f"下载路径(回车默认): {default_path}").strip() or default_path
    
    GLOBAL_DOWNLOAD_PATH = download_path
    
    os.makedirs(download_path, exist_ok=True)
    
    if not os.path.exists(CHROME_DRIVER_PATH):
        print(f"【错误】ChromeDriver 路径不存在: {CHROME_DRIVER_PATH}")
        print("请修改代码中的 CHROME_DRIVER_PATH 变量！")
        exit()

    csv_path = r"D:\myproject\Code\爬虫\爬虫数据\unsplash\all_records_unsplash_01.csv"
    status_csv_path = os.path.join(download_path, "download_all_records_unsplash_01.csv")
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

    MAX_THREADS = 4 # 设置最大线程数,共用线程设置
    
    with ThreadPoolExecutor(max_workers=MAX_THREADS) as ex:
        ex.map(selenium_worker, tasks)

    print("\n✅ 全部任务完成")