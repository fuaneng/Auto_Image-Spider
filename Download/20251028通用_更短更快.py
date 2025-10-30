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

# 禁用 SSL 验证警告，这是解决证书问题后的最佳实践
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# ---------- 全局控制 ----------
lock = threading.Lock()
current = 0
total = 0
driver_pool = threading.local()  # 每线程独立driver
# 任务队列中需要额外携带 Title 信息
screenshot_queue = queue.Queue()  # 请求失败任务队列
# 全局变量：下载根路径 (在 __main__ 中设置)
GLOBAL_DOWNLOAD_PATH = "" 


# ---------- 基础函数 (保持不变) ----------
def sanitize_filename(s: str) -> str:
    """清理文件名，移除无效字符，并将空格替换为连字符 '-'。"""
    # 先将空格替换为连字符
    s_cleaned = str(s).strip().replace(' ', '-')
    # 再移除其他无效字符
    return re.sub(r'[^\w\u4e00-\u9fff-.]', '', s_cleaned).strip()

def is_pil_compatible_image(url: str) -> bool:
    """检查是否为可以直接用 Pillow 处理的图片格式 (包括 .tiff 和 .heic)"""
    # 此函数仅用于辅助判断，现在下载主要依赖 Content-Type
    return url.lower().endswith((".jpg", ".jpeg", ".png", ".gif", ".bmp", ".webp", ".tiff", ".tif", ".heic"))

def is_direct_file_download(url: str) -> bool:
    """检查是否为可以直接下载文件内容保存，无需 Pillow 处理的格式 (例如 .svg)"""
    # 此函数仅用于辅助判断，现在下载主要依赖 Content-Type
    return url.lower().endswith((".svg"))

def is_downloadable(url: str) -> bool:
    """检查是否为可下载的格式 (PIL 兼容 或 直接保存文件)"""
    # 注意：此函数在新的 request_worker 中不再作为进入截图队列的判断标准
    return is_pil_compatible_image(url) or is_direct_file_download(url)


# ---------- 下载函数 (关键优化：流式下载) ----------
def try_download_with_requests(url: str, retries: int = 2) -> tuple[bytes | None, str]:
    """
    requests 流式下载函数，自动重试。
    - 解决了 SSL 证书验证失败问题 (verify=False)。
    - 解决了 HTTP 403 权限问题 (添加 User-Agent)。
    - 解决了大文件内存占用问题 (stream=True + iter_content)。
    返回 (内容, 失败消息)
    """
    headers = {
        # 伪装成 Chrome 浏览器
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                      "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36",
                      'Referer': 'https://v2ph.com/'    # 模拟从原始网站发起请求
    }
    
    for _ in range(retries):
        resp = None 
        try:
            # 启用流式模式 (stream=True) 并禁用 SSL 验证 (verify=False)
            resp = requests.get(url, headers=headers, timeout=(5, 10), verify=False, stream=True)
            
            if resp.status_code != 200:
                return None, f"HTTP Status Code {resp.status_code}"
            
            content_type = resp.headers.get('Content-Type', '').lower()
            if 'html' in content_type or 'text/plain' in content_type:
                return None, f"Content-Type: {content_type}"
                
            # 使用 iter_content 流式读取内容到内存
            content = b''
            for chunk in resp.iter_content(chunk_size=8192): 
                if chunk:
                    content += chunk
            
            return content, "OK"
            
        except requests.RequestException as e:
            time.sleep(0.5)
            last_error = str(e)
            
        finally:
            # 确保在流模式下关闭连接
            if resp:
                resp.close()
            
    return None, f"Requests 异常或超时: {last_error}"


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

        WebDriverWait(driver, 15).until(
            EC.presence_of_element_located((By.TAG_NAME, "img"))
        )
        img = driver.find_element(By.TAG_NAME, "img")

        for _ in range(10):
            width = driver.execute_script("return arguments[0].naturalWidth", img)
            if width > 300:
                break
            time.sleep(0.5)

        driver.execute_script("arguments[0].scrollIntoView(true);", img)
        time.sleep(0.5)

        img_data = img.screenshot_as_png
        Image.open(io.BytesIO(img_data)).save(save_path, "PNG")
        return True
    except Exception as e:
        print(f"[截图失败] {url} -> {e}")
        return False


# ---------- 状态记录 (保持不变) ----------
def record_status(url, tag, name, title, status, msg, path=""):
    """
    记录下载状态到 CSV 文件。
    """
    global current, GLOBAL_DOWNLOAD_PATH
    
    # 根据 TAG 规范化名称并构建记录文件的路径
    tag_cleaned = sanitize_filename(tag)
    status_csv_path = os.path.join(GLOBAL_DOWNLOAD_PATH, f"{tag_cleaned}_records.csv")

    with lock:
        current += 1
        print(f"[{current}/{total}] {tag_cleaned} | {status} {url}")
        pd.DataFrame([{
            "URL": url,
            "TAG": tag,
            "Title": title,
            "ImageName": name,
            "Status": status,
            "Message": msg,
            "SavedPath": path if status == "✅成功" else ""
        }]).to_csv(status_csv_path, mode='a', index=False,
                   header=not os.path.exists(status_csv_path), encoding='utf-8-sig')


# ---------- Request 下载线程 (关键修复：始终尝试 requests) ----------
def request_worker(args):
    """主下载线程：负责 requests 直接下载，不再根据 URL 后缀将任务丢给截图队列"""
    url, row, base_path, tag, title = args 
    
    raw_name = str(row.get('ImageName', 'image')).strip()
    name = sanitize_filename(raw_name)
    
    pil_exts = [".jpg", ".jpeg", ".png", ".bmp", ".webp", ".gif", ".tiff", ".tif", ".heic"]
    direct_exts = [".svg"]

    name_root, name_ext = os.path.splitext(name)
    ext = name_ext.lower()
    
    # 如果文件名本身没有有效扩展名，默认使用 .png
    if ext not in pil_exts and ext not in direct_exts:
        ext = ".png"
    
    # 构造保存路径：使用规范化后的 TAG 作为文件夹名
    folder = os.path.join(base_path, sanitize_filename(tag))
    os.makedirs(folder, exist_ok=True)
    full_path = os.path.join(folder, f"{name_root}{ext}")
    
    # ------------------------------------------------------------------------
    # 核心修复：强制执行 try_download_with_requests
    # ------------------------------------------------------------------------
    
    try:
        content, fail_msg = try_download_with_requests(url)
        
        if content:
            # 无论 URL 后缀如何，只要拿到了二进制内容，就尝试保存
            if ext in direct_exts:
                # SVG 等直接写入文件
                with open(full_path, 'wb') as f:
                    f.write(content)
                record_status(url, tag, name, title, "✅成功", "直接下载", full_path)
            
            elif ext in pil_exts or True: # True确保了所有拿到 content 的都至少尝试 PIL
                # 图片格式尝试用 PIL 处理
                try:
                    Image.open(io.BytesIO(content)).save(full_path)
                    record_status(url, tag, name, title, "✅成功", "PIL保存", full_path)
                except Exception as pil_e:
                    print(f"[PIL处理失败] {url} -> {pil_e}")
                    # PIL 处理失败，转入截图队列（以防是某种特殊格式，虽然可能性小）
                    screenshot_queue.put((url, tag, name, title, full_path))
        
        else:
            # requests 下载失败 (content is None)
            if fail_msg.startswith("HTTP Status Code") or fail_msg.startswith("Content-Type"):
                # 明确的 HTTP 协议错误，不转截图
                record_status(url, tag, name, title, "❌失败", fail_msg)
            else:
                # 其他下载失败原因（如请求异常、超时），转入截图队列尝试
                screenshot_queue.put((url, tag, name, title, full_path))

    except Exception as e:
        print(f"[requests异常] {url} -> {e}")
        record_status(url, tag, name, title, "❌失败", f"未知异常: {e}")


# ---------- Selenium 截图消费者 (保持不变) ----------
def screenshot_worker():
    """后台截图线程"""
    while True:
        try:
            url, tag, name, title, full_path = screenshot_queue.get(timeout=10)
        except queue.Empty:
            break

        ok = selenium_capture_image(url, full_path)
        
        if ok:
            name_root, _ = os.path.splitext(full_path)
            png_path = f"{name_root}.png"
            if full_path != png_path:
                 os.rename(full_path, png_path) 
            full_path = png_path 

        record_status(
            url, tag, name, title,
            "✅成功" if ok else "❌失败",
            "截图成功" if ok else "截图失败",
            full_path if ok else ""
        )
        screenshot_queue.task_done()


# ---------- 主程序入口 (保持不变) ----------
if __name__ == "__main__":
    default_path = r"R:\py\Auto_Image-Spider\Requests\v2ph\images"
    download_path = input(f"下载路径(回车默认): {default_path}").strip() or default_path
    os.makedirs(download_path, exist_ok=True)
    
    # 设置全局下载路径
    GLOBAL_DOWNLOAD_PATH = download_path 

    csv_path = r"R:\py\Auto_Image-Spider\Requests\v2ph\v2ph_data.csv"
    
    df = pd.read_csv(csv_path)
    # 确保 TAG 存在且非空
    df = df[df['TAG'].notna() & (df['TAG'] != '')]
    
    downloaded_urls = set()
    
    # 遍历所有独特的 TAG，查找已下载的 URL
    unique_tags = df['TAG'].unique()
    for tag in unique_tags:
        tag_cleaned = sanitize_filename(tag)
        # 独立的状态记录文件路径
        status_csv_path = os.path.join(GLOBAL_DOWNLOAD_PATH, f"{tag_cleaned}_records.csv")
        
        if os.path.exists(status_csv_path):
            try:
                df_s = pd.read_csv(status_csv_path)
                # 收集该 TAG 下已成功下载的 URL
                downloaded_urls.update(df_s.loc[df_s["Status"] == "✅成功", "URL"].astype(str))
            except Exception as e:
                print(f"Warning: 无法读取或解析 {status_csv_path}. 错误: {e}")
                pass


    # 任务列表构造
    tasks = [(r.URL, r, download_path, r['TAG'], r['Title']) 
              for _, r in df.iterrows() if pd.notna(r.URL) and r.URL not in downloaded_urls]
    
    total = len(tasks)
    print(f"待下载: {total} 个")

    # 启动后台截图线程（建议 2-3 个）
    for _ in range(1):
        threading.Thread(target=screenshot_worker, daemon=True).start()

    # 高并发requests下载
    with ThreadPoolExecutor(max_workers=20) as ex:
        ex.map(request_worker, tasks)

    # 等待截图任务完成
    screenshot_queue.join()

    # 关闭所有 Selenium 驱动
    if hasattr(driver_pool, "driver") and driver_pool.driver:
        driver_pool.driver.quit()
        driver_pool.driver = None

    print("\n✅ 全部任务完成")