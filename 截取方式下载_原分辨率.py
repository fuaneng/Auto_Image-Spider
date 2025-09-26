import pandas as pd
import os
import re
import threading
from concurrent.futures import ThreadPoolExecutor
from PIL import Image
import io
import time
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.common.exceptions import NoSuchElementException

# 全局计数器和锁
current = 0
lock = threading.Lock()
total = 0  # 总任务数

# 清理文件名中的非法字符
def sanitize_filename(s):
    return re.sub(r'[^\w\s\u4e00-\u9fff-.]', '', str(s)).strip().replace(' ', '-')

# 下载并处理图片
def download_image_by_screenshot(args):
    global current
    url, row, download_path = args

    # 新的文件名生成逻辑
    img_name = sanitize_filename(str(row.get('ImageName', 'image')))
    
    # 检查文件名是否包含后缀，如果是，则不添加 .png
    name, ext = os.path.splitext(img_name)
    if not ext:
        file_name = f"{img_name}.png"
    else:
        file_name = img_name
        
    full_path = os.path.join(download_path, file_name)

    chrome_driver_path = r'C:\Program Files\Google\chromedriver-win32\chromedriver.exe'
    options = Options()
    options.add_argument("--headless")
    options.add_argument("--disable-gpu")
    options.add_argument("--disable-notifications")
    options.add_argument("--disable-background-networking")
    options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36")
    options.add_argument(f"referer=https://inspgr.id/") 

    driver = None
    max_retries = 3

    for attempt in range(max_retries):
        try:
            service = Service(chrome_driver_path)
            driver = webdriver.Chrome(service=service, options=options)
            
            # 访问图片链接
            driver.get(url)
            time.sleep(5)

            # 通过 JavaScript 获取图片元素的原始尺寸
            img_element = driver.find_element("tag name", "img")
            img_width = driver.execute_script("return arguments[0].naturalWidth", img_element)
            img_height = driver.execute_script("return arguments[0].naturalHeight", img_element)
            
            # 动态调整浏览器窗口大小，以适应图片原始尺寸
            # 加上一些边距，避免滚动条
            driver.set_window_size(img_width + 100, img_height + 100) 
            time.sleep(1)
            
            # 重新定位图片元素
            img_element = driver.find_element("tag name", "img")
            
            # 截取图片并保存
            img_data = img_element.screenshot_as_png
            image = Image.open(io.BytesIO(img_data))
            image.save(full_path, "PNG")

            with lock:
                current += 1
                print(f"[{current}/{total}] 成功保存到：{full_path}")
            return True

        except NoSuchElementException:
            if attempt < max_retries - 1:
                print(f"[{current+1}/{total}] ⚠️ 未找到图片元素，第 {attempt + 1} 次重试...")
                time.sleep(5)
                continue
            else:
                with lock:
                    current += 1
                    print(f"[{current}/{total}] ❌ 下载失败：{url}, 错误：未找到图片元素")
                return False

        except Exception as e:
            if attempt < max_retries - 1:
                print(f"[{current+1}/{total}] ⚠️ 下载被中止，第 {attempt + 1} 次重试...")
                time.sleep(5)
                continue
            else:
                with lock:
                    current += 1
                    print(f"[{current}/{total}] ❌ 下载失败：{url}, 错误：{e}")
                return False

        finally:
            if driver:
                driver.quit()
    return False



### 主程序入口

if __name__ == "__main__":
    default_path = r"D:\work\爬虫\爬虫数据\Theinspirationgrid\images"
    download_path = input(f"请输入下载路径（直接回车使用默认路径：{default_path}）：").strip() or default_path
    os.makedirs(download_path, exist_ok=True)

    csv_path = r"D:\work\爬虫\爬虫数据\Theinspirationgrid\all_records - 副本.csv"
    try:
        df = pd.read_csv(csv_path)
    except Exception as e:
        print(f"读取 CSV 文件失败：{e}")
        exit()

    tasks = []
    for _, row in df.iterrows():
        url = row.get("URL")
        if pd.notna(url):
            tasks.append((url, row, download_path))

    total = len(tasks)
    print(f"共 {total} 张图片待下载...")

    max_workers = 5
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        results = executor.map(download_image_by_screenshot, tasks)

    success_count = sum(1 for r in results if r)
    print(f"\n下载完成！成功：{success_count}/{total}，失败：{total - success_count}")