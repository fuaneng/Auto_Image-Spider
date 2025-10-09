import pandas as pd
import os
import re
import threading
from concurrent.futures import ThreadPoolExecutor
from PIL import Image
import io
import time
import requests
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.common.exceptions import NoSuchElementException
from selenium.webdriver.common.by import By
import urllib3

# 禁用 SSL 警告
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# --- 全局变量 ---
current = 0
lock = threading.Lock()
total = 0

# --- 工具函数 ---
def sanitize_filename(s):
    """清理文件名中的非法字符"""
    return re.sub(r'[^\w\s\u4e00-\u9fff-.]', '', str(s)).strip().replace(' ', '-')

def is_direct_download(url):
    """判断是否为直接图片链接"""
    img_exts = (".jpg", ".jpeg", ".png", ".gif", ".bmp", ".webp")
    return url.lower().endswith(img_exts)

# --- 核心下载函数 ---
def download_image_by_screenshot(args):
    global current
    url, row, base_download_path, tag_folder_name, status_csv_path = args

    img_name = sanitize_filename(str(row.get('ImageName', 'image')))
    name, _ = os.path.splitext(img_name)

    # 自动识别图片扩展名
    ext = os.path.splitext(url.split("?")[0])[1].lower()
    if ext not in [".jpg", ".jpeg", ".png", ".webp", ".bmp"]:
        ext = ".png"

    file_name = f"{name}{ext}"
    safe_tag_folder = sanitize_filename(tag_folder_name)
    final_dir_path = os.path.join(base_download_path, safe_tag_folder)
    os.makedirs(final_dir_path, exist_ok=True)
    full_path = os.path.join(final_dir_path, file_name)

    def record_status(status, message=""):
        """在下载状态 CSV 中记录结果"""
        global current   # 用 global，而不是 nonlocal
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

    # ✅ 处理图片直链
    if is_direct_download(url):
        headers = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/123.0.0.0 Safari/537.36"
            ),
            "Referer": "https://wallpaperswide.com/"
        }

        for attempt in range(3):
            try:
                try:
                    response = requests.get(
                        url,
                        headers=headers,
                        timeout=60,
                        proxies={"http": None, "https": None},
                        verify=True
                    )
                    response.raise_for_status()
                except requests.exceptions.SSLError:
                    print(f"⚠️ SSL 验证失败，自动切换到 verify=False: {url}")
                    response = requests.get(
                        url,
                        headers=headers,
                        timeout=60,
                        proxies={"http": None, "https": None},
                        verify=False
                    )
                    response.raise_for_status()
                break
            except Exception as e:
                if attempt < 2:
                    print(f"⚠️ 第 {attempt+1} 次下载失败（{e.__class__.__name__}3 秒后重试...")
                    time.sleep(3)
                else:
                    record_status("❌失败", f"直接下载错误: {e}")
                    return False

        try:
            image = Image.open(io.BytesIO(response.content))
            image_format = "PNG" if ext == ".png" else "JPEG"
            image.save(full_path, image_format)
        except Exception:
            with open(full_path, "wb") as f:
                f.write(response.content)

        record_status("✅成功")
        return True

    # 🚀 否则用 Selenium 截图
    chrome_driver_path = r'C:\Program Files\Google\chromedriver-win64\chromedriver.exe'
    options = Options()
    options.add_argument("--headless=new")
    options.add_argument("--disable-gpu")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-notifications")
    options.add_experimental_option('excludeSwitches', ['enable-logging'])
    options.add_argument(
        "user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36"
    )
    options.add_argument(f"referer=https://wallpaperswide.com/")    # 避免防盗链，但不一定有效

    driver = None
    max_retries = 3
    for attempt in range(max_retries):
        try:
            service = Service(chrome_driver_path)
            driver = webdriver.Chrome(service=service, options=options)
            driver.set_page_load_timeout(30)
            driver.get(url)
            time.sleep(3)

            img_element = driver.find_element(By.TAG_NAME, "img")
            img_width = driver.execute_script("return arguments[0].naturalWidth", img_element)
            img_height = driver.execute_script("return arguments[0].naturalHeight", img_element)
            driver.set_window_size(img_width + 100, img_height + 100)
            time.sleep(1)

            img_data = img_element.screenshot_as_png
            image = Image.open(io.BytesIO(img_data))
            image.save(full_path, "PNG")

            record_status("✅成功")
            return True

        except NoSuchElementException:
            if attempt < max_retries - 1:
                print(f"⚠️ 未找到图片元素，第 {attempt+1} 次重试...")
                time.sleep(5)
                continue
            else:
                record_status("❌失败", "未找到图片元素")
                return False

        except Exception as e:
            if attempt < max_retries - 1:
                print(f"⚠️ 异常 {e.__class__.__name__}，第 {attempt+1} 次重试...")
                time.sleep(5)
                continue
            else:
                record_status("❌失败", f"异常：{e}")
                return False

        finally:
            if driver:
                driver.quit()
    return False


# --- 主程序入口 ---
if __name__ == "__main__":
    default_path = r"\\10.58.134.120\aigc2\01_数据\爬虫数据\wallpaperswide\images"
    download_path = input(f"请输入下载路径（直接回车使用默认路径：{default_path}):").strip() or default_path
    os.makedirs(download_path, exist_ok=True)

    csv_path = r"D:\work\爬虫\爬虫数据\wallpaperswide\all_records3708.csv"
    status_csv_path = os.path.join(download_path, "download_status.csv")    # 下载状态 CSV 路径，与图片同目录，便于管理

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
            downloaded_urls = set(df_status.loc[df_status["Status"] == "✅成功", "URL"].astype(str))
            print(f"✅ 检测到已完成记录 {len(downloaded_urls)} 条，将跳过这些任务。")
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
    print(f"已跳过（已下载或无效）：{skipped_count}")
    print(f"待下载任务数：{total}")

    max_workers = 10  # 根据实际情况调整线程数，过多可能导致系统资源紧张
    print(f"使用 {max_workers} 个线程下载...")

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        results = executor.map(download_image_by_screenshot, tasks)

    success_count = sum(1 for r in results if r)
    print(f"\n下载完成！成功：{success_count}/{total}，失败：{total - success_count}")
    print(f"下载状态已保存到：{status_csv_path}")
