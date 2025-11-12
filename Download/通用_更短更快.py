import os
import re
import io
import time
import threading
import queue
from concurrent.futures import ThreadPoolExecutor
import pandas as pd
from PIL import Image
import requests
from pillow_heif import register_heif_opener
register_heif_opener()
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import (
    WebDriverException, TimeoutException, NoSuchElementException
)
import urllib3

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# ---------- 全局控制 ----------
lock = threading.Lock()
current = 0
total = 0
driver_pool = threading.local()  # 每线程独立driver
screenshot_queue = queue.Queue()  # 请求失败任务队列


# ---------- 基础函数 ----------
def sanitize_filename(s: str) -> str:
    """清理文件名，移除无效字符"""
    return re.sub(r'[^\w\s\u4e00-\u9fff-.]', '', str(s)).strip().replace(' ', '-')


def is_pil_compatible_image(url: str) -> bool:
    """检查是否为可以直接用 Pillow 处理的图片格式 (包括 .tiff 和 .heic)"""
    return url.lower().endswith((".jpg", ".jpeg", ".png", ".gif", ".bmp", ".webp", ".tiff", ".tif", ".heic"))

def is_direct_file_download(url: str) -> bool:
    """检查是否为可以直接下载文件内容保存，无需 Pillow 处理的格式 (例如 .svg)"""
    return url.lower().endswith((".svg"))

def is_downloadable(url: str) -> bool:
    """检查是否为可下载的格式 (PIL 兼容 或 直接保存文件)"""
    return is_pil_compatible_image(url) or is_direct_file_download(url)


# ---------- 下载函数 ----------
def try_download_with_requests(url: str, retries: int = 2) -> bytes | None:
    """requests 下载函数，自动重试"""
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                      "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36"
    }
    for _ in range(retries):
        try:
            resp = requests.get(url, headers=headers, timeout=(5, 10), verify=False)
            if resp.status_code == 200:
                # 检查内容类型，避免下载错误的HTML页面
                content_type = resp.headers.get('Content-Type', '').lower()
                if 'html' in content_type or 'text/plain' in content_type:
                    return None
                return resp.content
        except requests.RequestException:
            time.sleep(0.5)
    return None


# ---------- Selenium 驱动 (保持不变) ----------
def get_selenium_driver() -> webdriver.Chrome:
    """线程独立 driver"""
    if hasattr(driver_pool, "driver") and driver_pool.driver:
        return driver_pool.driver

    # 请确保您的 ChromeDriver 路径是正确的
    chrome_driver_path = r"C:\Program Files\Google\chromedriver-win64\chromedriver.exe"
    opts = Options()
    opts.add_argument("--headless=new")
    opts.add_argument("--disable-gpu")
    opts.add_argument("--no-sandbox")
    opts.add_argument("--disable-dev-shm-usage")
    opts.add_argument("--disable-notifications")
    opts.add_argument("--window-size=1920,1080")
    opts.add_experimental_option('excludeSwitches', ['enable-logging'])
    driver_pool.driver = webdriver.Chrome(service=Service(chrome_driver_path), options=opts)
    driver_pool.driver.set_page_load_timeout(30)
    return driver_pool.driver


# ---------- Selenium 截图函数 (保持不变) ----------
def selenium_capture_image(url: str, save_path: str) -> bool:
    """截图方式保存大图，等待加载完成"""
    try:
        driver = get_selenium_driver()
        driver.get(url)

        # 尝试等待页面中出现图片元素
        WebDriverWait(driver, 15).until(
            EC.presence_of_element_located((By.TAG_NAME, "img"))
        )
        img = driver.find_element(By.TAG_NAME, "img")

        # 等待 naturalWidth > 300 才截图（假设大图加载完成）
        for _ in range(10):
            width = driver.execute_script("return arguments[0].naturalWidth", img)
            if width > 300:
                break
            time.sleep(0.5)

        driver.execute_script("arguments[0].scrollIntoView(true);", img)
        time.sleep(0.5)

        # 截图并保存为 PNG 格式
        img_data = img.screenshot_as_png
        Image.open(io.BytesIO(img_data)).save(save_path, "PNG")
        return True
    except Exception as e:
        print(f"[截图失败] {url} -> {e}")
        return False


# ---------- 状态记录 (保持不变) ----------
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


# ---------- Request 下载线程 (已修改) ----------
def request_worker(args):
    """主下载线程：负责 requests 直接下载 SVG 和 PIL 兼容的格式，失败则丢到队列"""
    url, row, base_path, tag, status_csv = args
    raw_name = str(row.get('ImageName', 'image')).strip()
    name = sanitize_filename(raw_name)
    
    # 定义支持的扩展名列表
    pil_exts = [".jpg", ".jpeg", ".png", ".bmp", ".webp", ".gif", ".tiff", ".tif", ".heic"]
    direct_exts = [".svg"]

    # 确定文件扩展名和保存路径
    name_root, name_ext = os.path.splitext(name)
    ext = name_ext.lower()
    
    # 如果原始文件名没有有效扩展名，默认用 .png
    if ext not in pil_exts and ext not in direct_exts:
        ext = ".png"
    
    # 构造保存路径
    folder = os.path.join(base_path, sanitize_filename(tag))
    os.makedirs(folder, exist_ok=True)
    full_path = os.path.join(folder, f"{name_root}{ext}")
    
    # 如果 URL 本身就不是可下载的文件格式，直接进入截图队列
    if not is_downloadable(url):
        screenshot_queue.put((url, tag, name, full_path, status_csv))
        return

    try:
        content = try_download_with_requests(url)
        
        if content:
            if ext in direct_exts:
                # 针对 SVG 等直接保存文件内容
                with open(full_path, 'wb') as f:
                    f.write(content)
                record_status(status_csv, url, tag, name, "✅成功", "直接下载", full_path)
            
            elif ext in pil_exts:
                # 针对 JPG, PNG, TIFF, HEIC 等 PIL 兼容格式
                try:
                    # Pillow 尝试打开并保存（依赖 Pillow-Heif 支持 HEIC）
                    Image.open(io.BytesIO(content)).save(full_path)
                    record_status(status_csv, url, tag, name, "✅成功", "PIL保存", full_path)
                except Exception as pil_e:
                    print(f"[PIL处理失败] {url} -> {pil_e}") # 你的错误信息在这里打印
                    screenshot_queue.put((url, tag, name, full_path, status_csv))
            else:
                 # 理论上不会走到这里，但作为保障，放入截图队列
                screenshot_queue.put((url, tag, name, full_path, status_csv))
        else:
            # requests 下载失败，放入截图队列
            screenshot_queue.put((url, tag, name, full_path, status_csv))

    except Exception as e:
        print(f"[requests异常] {url} -> {e}")
        # 异常情况，放入截图队列
        screenshot_queue.put((url, tag, name, full_path, status_csv))


# ---------- Selenium 截图消费者 (保持不变) ----------
def screenshot_worker():
    """后台截图线程"""
    while True:
        try:
            url, tag, name, full_path, status_csv = screenshot_queue.get(timeout=10)
        except queue.Empty:
            break

        # 注意：Selenium 截图保存的是 PNG 格式
        ok = selenium_capture_image(url, full_path)
        
        # 针对截图任务，如果成功，即使原路径是 .svg 或 .heic，保存的也是 .png
        # 我们用原文件名+新的 .png 扩展名来保存
        if ok:
            name_root, _ = os.path.splitext(full_path)
            png_path = f"{name_root}.png"
            os.rename(full_path, png_path) # 确保状态记录的是正确的路径
            full_path = png_path 

        record_status(
            status_csv, url, tag, name,
            "✅成功" if ok else "❌失败",
            "" if ok else "截图失败",
            full_path if ok else ""
        )
        screenshot_queue.task_done()


# ---------- 主程序入口 (保持不变) ----------
if __name__ == "__main__":
    default_path = r"R:\py\Civitai_保存和导入 Cookies\civitai\pic"
    download_path = input(f"下载路径(回车默认): {default_path}").strip() or default_path
    os.makedirs(download_path, exist_ok=True)

    csv_path = r"R:\py\Civitai_保存和导入 Cookies\civitai\tag_5133.csv"
    status_csv_path = os.path.join(download_path, "download_tag_5133.csv")

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

    # 启动后台截图线程（建议 2-3 个）
    for _ in range(2):
        threading.Thread(target=screenshot_worker, daemon=True).start()

    # 高并发requests下载
    with ThreadPoolExecutor(max_workers=20) as ex:
        ex.map(request_worker, tasks)

    # 等待截图任务完成
    screenshot_queue.join()

    print("\n✅ 全部任务完成")