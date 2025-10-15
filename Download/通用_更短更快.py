# file: downloader_optimized.py
import os
import re
import io
import time
import threading
from concurrent.futures import ThreadPoolExecutor
import pandas as pd
from PIL import Image
import requests
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.common.exceptions import WebDriverException, NoSuchElementException
import urllib3

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

lock = threading.Lock()
current = 0
total = 0
driver_pool = threading.local()  # 每线程独立 driver

def sanitize_filename(s: str) -> str:
    """
    清洗文件名：
    - 保留中英文、数字、下划线、连字符、点号
    - 替换连续空格为单个'-'
    - 去除首尾空格与点号
    - 适配中文及含扩展名的文件
    """
    if not s:
        return "untitled"

    s = str(s).strip()

    # 替换空白为短横线
    s = re.sub(r'\s+', '-', s)

    # 保留中文、英文、数字、下划线、连字符、点号
    s = re.sub(r'[^\w\u4e00-\u9fff\-.]', '', s)

    # 移除首尾的点或连字符（防止 Windows 文件名异常）
    s = s.strip("-. ")

    # 防止空文件名
    if not s:
        s = "untitled"

    return s

def is_direct_download(url: str) -> bool:
    return url.lower().endswith((".jpg", ".jpeg", ".png", ".gif", ".bmp", ".webp"))

def try_download_with_requests(url: str) -> bytes | None:
    """禁用所有认证机制，仅尝试2秒连接"""
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                      "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36"
    }
    try:
        resp = requests.get(url, headers=headers, timeout=2, verify=False)
        if resp.status_code == 200:
            return resp.content
        return None
    except requests.RequestException:
        return None

# def get_selenium_driver() -> webdriver.Chrome:
#     """线程复用driver实例"""
#     if hasattr(driver_pool, "driver") and driver_pool.driver:
#         return driver_pool.driver
#     chrome_driver_path = r"C:\Program Files\Google\chromedriver-win32\chromedriver.exe"
#     opts = Options()
#     opts.add_argument("--headless=new")
#     opts.add_argument("--disable-gpu")
#     opts.add_argument("--no-sandbox")
#     opts.add_argument("--disable-dev-shm-usage")
#     opts.add_argument("--disable-notifications")
#     opts.add_experimental_option('excludeSwitches', ['enable-logging'])
#     driver_pool.driver = webdriver.Chrome(service=Service(chrome_driver_path), options=opts)
#     driver_pool.driver.set_page_load_timeout(30)
#     return driver_pool.driver

def get_selenium_driver() -> webdriver.Chrome:
    """线程复用 driver 实例（优化资源占用）"""
    if hasattr(driver_pool, "driver") and driver_pool.driver:
        return driver_pool.driver

    chrome_driver_path = r"C:\Program Files\Google\chromedriver-win32\chromedriver.exe"
    opts = Options()
    opts.add_argument("--headless=new")
    opts.add_argument("--disable-gpu")
    opts.add_argument("--no-sandbox")
    opts.add_argument("--disable-dev-shm-usage")
    opts.add_argument("--disable-notifications")
    opts.add_argument("--disable-extensions")
    opts.add_argument("--disable-popup-blocking")
    opts.add_argument("--blink-settings=imagesEnabled=true")  # ✅ 保留图片加载
    opts.add_experimental_option("prefs", {
        "profile.managed_default_content_settings.stylesheets": 2,  # 禁用 CSS
        "profile.managed_default_content_settings.cookies": 2,       # 禁用 cookies
        "profile.managed_default_content_settings.plugins": 2,       # 禁用插件
        "profile.managed_default_content_settings.popups": 2,        # 禁用弹窗
        "profile.managed_default_content_settings.geolocation": 2,   # 禁用定位
        "profile.managed_default_content_settings.notifications": 2, # 禁用通知
    })
    opts.add_experimental_option('excludeSwitches', ['enable-logging'])

    driver_pool.driver = webdriver.Chrome(service=Service(chrome_driver_path), options=opts)
    driver_pool.driver.set_page_load_timeout(30)
    return driver_pool.driver

def selenium_capture_image(url: str, save_path: str) -> bool:
    """直接用Selenium截图保存PNG"""
    try:
        driver = get_selenium_driver()
        driver.get(url)
        time.sleep(2)
        img = driver.find_element(By.TAG_NAME, "img")
        width = driver.execute_script("return arguments[0].naturalWidth", img)
        height = driver.execute_script("return arguments[0].naturalHeight", img)
        driver.set_window_size(width + 50, height + 50)
        time.sleep(1)
        img_data = img.screenshot_as_png
        Image.open(io.BytesIO(img_data)).save(save_path, "PNG")
        return True
    except (NoSuchElementException, WebDriverException):
        return False

def record_status(status_csv_path, url, tag, name, status, msg, path=""):
    global current
    with lock:
        current += 1
        print(f"[{current}/{total}] {status} {url}")
        pd.DataFrame([{
            "URL": url,
            "TAG": tag,
            "ImageName": name,
            "Status": status,
            "Message": msg,
            "SavedPath": path if status == "✅成功" else ""
        }]).to_csv(status_csv_path, mode='a', index=False,
                   header=not os.path.exists(status_csv_path), encoding='utf-8-sig')

def download_image(args):
    url, row, base_path, tag, status_csv = args

    # 获取原始文件名并清洗非法字符（保留点号）
    raw_name = str(row.get('ImageName', 'image')).strip()
    name = sanitize_filename(raw_name)

    # 合法扩展名列表
    valid_exts = [".jpg", ".jpeg", ".png", ".bmp", ".webp"]

    # 拆分 name 和扩展名
    name_root, name_ext = os.path.splitext(name)

    # 1️⃣ 优先：如果 name 自带合法后缀，则使用它（不再额外拼接）
    if name_ext.lower() in valid_exts:
        ext = name_ext.lower()
        clean_name = name_root  # 去除扩展部分备用
        final_name = f"{clean_name}{ext}"  # 保持原样
    else:
        # 2️⃣ 否则尝试从 URL 提取后缀
        url_ext = os.path.splitext(url.split("?")[0])[1].lower()
        ext = url_ext if url_ext in valid_exts else ".png"
        final_name = f"{name_root}{ext}"

    # 避免双重后缀（例如 "xx.jpg.jpg"）
    # 这里用正则保证末尾只保留一个合法扩展
    for vext in valid_exts:
        if re.search(f"{re.escape(vext)}{re.escape(vext)}$", final_name, re.IGNORECASE):
            final_name = re.sub(f"{re.escape(vext)}{re.escape(vext)}$", vext, final_name, flags=re.IGNORECASE)

    # 保存路径
    folder = os.path.join(base_path, sanitize_filename(tag))
    os.makedirs(folder, exist_ok=True)
    full_path = os.path.join(folder, final_name)

    # 下载逻辑
    content = try_download_with_requests(url) if is_direct_download(url) else None
    if content:
        try:
            Image.open(io.BytesIO(content)).save(full_path)
            record_status(status_csv, url, tag, final_name, "✅成功", "", full_path)
            return True
        except Exception as e:
            record_status(status_csv, url, tag, final_name, "❌失败", f"保存错误: {e}")
            return False
    else:
        ok = selenium_capture_image(url, full_path)
        record_status(status_csv, url, tag, final_name,
                      "✅成功" if ok else "❌失败",
                      "" if ok else "截图失败",
                      full_path if ok else "")
        return ok


if __name__ == "__main__":
   
    default_path = r"\\10.58.134.120\aigc2\01_数据\爬虫数据\photos\images"  # 默认路径
    download_path = input(f"下载路径(请按Enter确认{default_path}): ").strip() or default_path
    os.makedirs(download_path, exist_ok=True)

    csv_path = r"D:\work\爬虫\爬虫数据\photos\建筑_records.csv"  # 待下载列表
    status_csv_path = os.path.join(download_path, "download_建筑.csv")  # 记录下载状态

    df = pd.read_csv(csv_path)
    downloaded = set()
    if os.path.exists(status_csv_path):
        try:
            df_s = pd.read_csv(status_csv_path)
            downloaded = set(df_s.loc[df_s["Status"] == "✅成功", "URL"].astype(str))
        except Exception:
            pass

    tasks = [(r.URL, r, download_path, r.TAG, status_csv_path)
             for _, r in df.iterrows() if pd.notna(r.URL) and r.URL not in downloaded]
    total = len(tasks)
    print(f"待下载: {total} 个")

    with ThreadPoolExecutor(max_workers=5) as ex:   # 5 线程同时下载
        results = ex.map(download_image, tasks)
    success = sum(1 for r in results if r)
    print(f"\n完成 ✅: {success}/{total}")
