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
    return re.sub(r'[^\w\s\u4e00-\u9fff-.]', '', str(s)).strip().replace(' ', '-')

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

def get_selenium_driver() -> webdriver.Chrome:
    """线程复用driver实例"""
    if hasattr(driver_pool, "driver") and driver_pool.driver:
        return driver_pool.driver
    chrome_driver_path = r"C:\Program Files\Google\chromedriver-win32\chromedriver.exe"
    opts = Options()
    opts.add_argument("--headless=new")
    opts.add_argument("--disable-gpu")
    opts.add_argument("--no-sandbox")
    opts.add_argument("--disable-dev-shm-usage")
    opts.add_argument("--disable-notifications")
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
    name = sanitize_filename(str(row.get('ImageName', 'image')))
    ext = os.path.splitext(url.split("?")[0])[1].lower() or ".png"
    if ext not in [".jpg", ".jpeg", ".png", ".bmp", ".webp"]:
        ext = ".png"
    folder = os.path.join(base_path, sanitize_filename(tag))
    os.makedirs(folder, exist_ok=True)
    full_path = os.path.join(folder, f"{name}{ext}")

    content = try_download_with_requests(url) if is_direct_download(url) else None
    if content:
        try:
            Image.open(io.BytesIO(content)).save(full_path)
            record_status(status_csv, url, tag, name, "✅成功", "")
            return True
        except Exception as e:
            record_status(status_csv, url, tag, name, "❌失败", f"保存错误: {e}")
            return False
    else:
        ok = selenium_capture_image(url, full_path)
        record_status(status_csv, url, tag, name,
                      "✅成功" if ok else "❌失败",
                      "" if ok else "截图失败", full_path if ok else "")
        return ok

if __name__ == "__main__":
    default_path = r"\\10.58.134.120\aigc2\01_数据\爬虫数据\photos\images"
    download_path = input(f"下载路径(回车默认): ").strip() or default_path
    os.makedirs(download_path, exist_ok=True)

    csv_path = r"D:\work\爬虫\爬虫数据\photos\建筑_records.csv"
    status_csv_path = os.path.join(download_path, "download_建筑.csv")

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

    with ThreadPoolExecutor(max_workers=5) as ex:   # 5线程
        results = ex.map(download_image, tasks)
    success = sum(1 for r in results if r)
    print(f"\n完成 ✅: {success}/{total}")
