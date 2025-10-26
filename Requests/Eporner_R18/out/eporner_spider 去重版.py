import requests
from bs4 import BeautifulSoup
import csv
import os
import re
from concurrent.futures import ThreadPoolExecutor, as_completed

# --- 配置常量 ---
BASE_URL = "https://www.eporner.com"
SEARCH_URL_TEMPLATE = BASE_URL + "/search-photos/{person_name}/{page}/"

# 你的本地路径配置
ROOT_PATH = r"R:\py\Auto_Image-Spider\Requests\Eporner_R18"
PERSON_TAGS_FILE = os.path.join(ROOT_PATH, "人名.txt") 
CSV_PATH = os.path.join(ROOT_PATH, "image_data.csv") 
IMAGE_DIR = os.path.join(ROOT_PATH, "images")

# 确保文件夹和下载目录存在
os.makedirs(IMAGE_DIR, exist_ok=True)
os.makedirs(ROOT_PATH, exist_ok=True)

# 模拟浏览器请求头
HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
}

# --- 工具函数 ---

def get_html(url):
    """发送GET请求并返回响应文本，处理常见异常。 (增强版，超时设置为15秒)"""
    try:
        response = requests.get(url, headers=HEADERS, timeout=15) 
        response.raise_for_status() 
        return response
    except requests.exceptions.HTTPError as e:
        if response is not None and response.status_code == 404:
            return None 
        print(f"  [ERROR] HTTP Error ({response.status_code}) for {url}: {e}")
        return None
    except requests.exceptions.Timeout:
        print(f"  [ERROR] Request Timeout for {url}: 请求超时。")
        return None
    except requests.exceptions.RequestException as e:
        print(f"  [ERROR] Connection Error for {url}: 网络连接异常。")
        return None

def read_person_tags(file_path):
    """从指定的 .txt 文件中读取人物标签列表"""
    tags = []
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            for line in f:
                tag = line.strip()
                if tag and not tag.startswith('#'):
                    tags.append(tag)
        print(f"📄 成功从 {file_path} 中读取到 {len(tags)} 个人物标签。")
    except FileNotFoundError:
        print(f"🚨 错误：未找到人名标签文件: {file_path}")
        print("请在指定路径创建此文件，并在其中输入要搜索的人物标签/ID，每行一个。")
    return tags

def extract_album_links(person_name):
    """
    第一部分：搜索图片集合标签，获取标签列表 (内部使用 set 自动去重)
    返回：包含所有相册详情页完整URL的列表。
    """
    album_links = set()
    page = 1
    
    while True:
        search_url = SEARCH_URL_TEMPLATE.format(person_name=person_name, page=page)
        # print(f"  > 正在处理第 {page} 页...")

        response = get_html(search_url)
        if response is None:
            break

        soup = BeautifulSoup(response.text, 'lxml')
        
        album_tags = soup.select('#container.photosgrid a[id^="ah"]') 
        
        if not album_tags:
            break

        for tag in album_tags:
            href = tag.get('href')
            if href and href.startswith('/gallery/'):
                full_url = BASE_URL + href
                album_links.add(full_url)
        
        page += 1
    
    return list(album_links)


def process_album_page(album_url):
    """
    第二部分：访问图片详情页，获取图片信息。
    返回：该相册所有图片的详细信息列表。
    """
    image_data_list = []
    
    response = get_html(album_url)
    if response is None:
        return image_data_list

    soup = BeautifulSoup(response.text, 'lxml')
    
    img_tags = soup.select('div.gallerygrid img[id^="t"]')
    
    for img_tag in img_tags:
        src_url = img_tag.get('src')
        alt_text = img_tag.get('alt', '')
        
        if not src_url:
            continue
            
        # 转换为完整图片URL：去除 URL 中最后一个 '_数字x数字' 形式的缩略图标识符
        full_image_url = re.sub(r'(_\d+x\d+)\.', '.', src_url)
        
        # 提取标题
        title = alt_text.replace('amateur photo', '').replace('porn photo', '').strip()
        
        # 提取名称
        name = re.sub(r'-\d+px$', '', title).strip() 

        image_data_list.append({
            '图片URL': full_image_url,
            '标题': title,
            '名称': name,
        })
        
    return image_data_list

# --- 数据持久化 ---
def save_to_csv(data_list, filename):
    """将数据列表写入CSV文件"""
    if not data_list:
        return
        
    fieldnames = ['图片URL', '标题', '名称']
    file_exists = os.path.exists(filename)
    
    try:
        with open(filename, 'a', newline='', encoding='utf-8-sig') as csvfile:
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
            
            if not file_exists or os.stat(filename).st_size == 0:
                writer.writeheader() 
                
            writer.writerows(data_list)
            
        print(f"💾 成功将 {len(data_list)} 条数据追加写入到 CSV 文件。")
    except IOError as e:
        print(f"  [ERROR] 写入CSV文件失败: {e}")

# --- 多线程下载 ---
def download_image(image_info):
    """
    根据图片信息下载图片并保存。(内部包含文件存在性检查)
    """
    url = image_info['图片URL']
    title = image_info['标题']
    
    ext_match = re.search(r'\.(\w+)$', url)
    extension = f".{ext_match.group(1)}" if ext_match else ".jpg" 

    safe_title = re.sub(r'[\\/:*?"<>|]', '_', title)
    
    filename = safe_title + extension
    filepath = os.path.join(IMAGE_DIR, filename)

    # 检查本地文件是否存在，避免重复下载
    if os.path.exists(filepath):
        return f"Skipped: {filename}"
        
    try:
        response = requests.get(url, headers=HEADERS, stream=True, timeout=30)
        response.raise_for_status()

        with open(filepath, 'wb') as f:
            for chunk in response.iter_content(chunk_size=8192):
                f.write(chunk)
                
        return f"Downloaded: {filename}"
        
    except requests.exceptions.RequestException as e:
        return f"Error downloading {filename} from {url}: {e}"
        
def start_download_executor(all_data):
    """使用ThreadPoolExecutor启动多线程下载"""
    if not all_data:
        print("没有图片数据可供下载。")
        return
        
    MAX_WORKERS = 10 
    
    success_count = 0
    error_count = 0
    
    print(f"\n⚡ 启动 {len(all_data)} 个多线程下载任务...")
    
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        future_to_info = {executor.submit(download_image, item): item for item in all_data}
        
        for future in as_completed(future_to_info):
            try:
                result = future.result()
                if result.startswith("Downloaded"):
                    success_count += 1
                elif result.startswith("Error"):
                    error_count += 1
                # 打印进度
                # print(f"  {result}")
            except Exception as exc:
                print(f"  [EXCEPTION] 任务执行时发生异常: {exc}")
                error_count += 1
                
    print(f"🎉 所有下载任务完成！ 成功: {success_count}， 失败/跳过: {len(all_data) - success_count}， 错误: {error_count}")


# --- 主逻辑 ---
def main():
    # 1. 读取所有目标人物标签
    person_tags = read_person_tags(PERSON_TAGS_FILE)
    if not person_tags:
        return
        
    # **核心去重数据结构**：使用字典来存储所有图片的唯一数据，键为 '图片URL'
    all_unique_data_dict = {}

    # 2. 遍历每个人物标签执行爬取
    for i, tag in enumerate(person_tags):
        person_name = tag.strip()
        print(f"\n=======================================================")
        print(f"🚀 [任务 {i+1}/{len(person_tags)}] 开始处理人物标签: '{person_name}'")
        print(f"=======================================================")

        # A. 提取相册链接
        album_urls = extract_album_links(person_name)
        if not album_urls:
            print(f"⚠️ 未找到人物 '{person_name}' 的任何相册，跳过。")
            continue
        print(f"  找到 {len(album_urls)} 个相册。")

        # B. 遍历相册，提取图片信息
        for j, url in enumerate(album_urls):
            # print(f"    > 正在解析相册 [{j+1}/{len(album_urls)}]")
            data_list = process_album_page(url)
            
            # C. 实时添加到全局去重字典中
            for item in data_list:
                # 以图片URL为键，保证全局唯一性
                all_unique_data_dict[item['图片URL']] = item
            
        print(f"🌟 人物 '{person_name}' 的数据收集完成，当前总计 {len(all_unique_data_dict)} 条独特图片数据。")
        
    # 3. 数据持久化和下载
    overall_unique_data = list(all_unique_data_dict.values()) # 最终列表
        
    if not overall_unique_data:
        print("\n所有人物都没有提取到数据。")
        return
        
    print(f"\n=======================================================")
    print(f"📊 最终总计： {len(overall_unique_data)} 条图片数据准备写入和下载。")
    print(f"=======================================================")

    # D. 写入 CSV
    # 为了避免多次运行重复写入数据，如果文件存在，我们可以先清除它或采取更复杂的更新逻辑。
    # 这里我们继续使用追加模式，但数据已经是去重后的。
    save_to_csv(overall_unique_data, CSV_PATH)
    
    # E. 启动多线程下载
    start_download_executor(overall_unique_data)

if __name__ == '__main__':
    main()