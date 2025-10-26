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
CSV_PATH = os.path.join(ROOT_PATH, "all_images_data.csv") 
IMAGE_DIR = os.path.join(ROOT_PATH, "images")

# ⚠️ 新增下载功能开关
# 设置为 True: 爬取数据后立即启动多线程下载
# 设置为 False: 仅爬取数据并写入 CSV，不启动下载
ENABLE_DOWNLOAD = False 

# 确保文件夹结构存在
os.makedirs(IMAGE_DIR, exist_ok=True)
os.makedirs(ROOT_PATH, exist_ok=True)

# 模拟浏览器请求头
HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
}

# --- 工具函数 (网络请求/文件读取) ---

def get_html(url):
    """发送GET请求并返回响应文本，处理常见异常。"""
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
        return []
    return tags

# --- 第一部分：搜索与相册链接提取 ---

def extract_album_links(person_name):
    """
    搜索图片集合标签，获取链接和所属集合名称。
    返回：包含 [(相册详情页完整URL, 所属集合名称), ...] 元组的列表。
    """
    album_data = {} 
    page = 1
    
    while True:
        search_url = SEARCH_URL_TEMPLATE.format(person_name=person_name, page=page)
        response = get_html(search_url)
        if response is None:
            break

        soup = BeautifulSoup(response.text, 'lxml')
        
        # 定位所有相册的容器 div.mbphoto2
        album_containers = soup.select('#container.photosgrid div.mbphoto2')
        
        if not album_containers:
            break

        for container in album_containers:
            # 1. 提取链接 (a 标签)
            a_tag = container.find('a', id=re.compile(r'^ah\d+'))
            # 2. 提取所属集合标题 (div.mbtitphoto2 标签)
            title_tag = container.find('div', class_='mbtitphoto2')
            
            if a_tag and title_tag:
                href = a_tag.get('href')
                album_title = title_tag.get_text().strip()
                
                if href and href.startswith('/gallery/'):
                    full_url = BASE_URL + href
                    if full_url not in album_data:
                        album_data[full_url] = album_title
        
        page += 1
    
    return [(url, title) for url, title in album_data.items()]


# --- 第二部分：访问详情页，获取图片信息 ---

def process_album_page(album_url, album_collection_name):
    """
    访问图片详情页，获取图片信息，并添加所属集合字段。
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
            
        # 1. 转换为完整图片URL (去除 _数字x数字)
        full_image_url = re.sub(r'(_\d+x\d+)\.', '.', src_url)
        
        # 2. 提取标题
        title = alt_text.replace('amateur photo', '').replace('porn photo', '').strip()
        
        # 3. 提取名称 (去除末尾的 -数字px)
        name = re.sub(r'-\d+px$', '', title).strip() 

        image_data_list.append({
            '图片URL': full_image_url,
            '标题': title,
            '名称': name,
            '所属集合': album_collection_name, 
        })
        
    return image_data_list

# --- 数据持久化 ---
def save_to_csv(data_list, filename):
    """将数据列表写入CSV文件"""
    if not data_list:
        return
        
    fieldnames = ['图片URL', '标题', '名称', '所属集合']
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

# --- 第三部分：多线程下载 (分文件夹存储/断点续传) ---

def download_image(image_info):
    """
    根据图片信息下载图片并保存到对应的子文件夹中。
    """
    url = image_info['图片URL']
    title = image_info['标题']
    collection_name = image_info['所属集合']
    
    ext_match = re.search(r'\.(\w+)$', url)
    extension = f".{ext_match.group(1)}" if ext_match else ".jpg" 

    safe_title = re.sub(r'[\\/:*?"<>|]', '_', title)
    
    # ⚠️ 关键修改：扩展替换规则，将 . 和 - 也替换为 _
    # 原始禁止字符：[\\/:*?"<>|]
    # 新增替换字符：. 和 -
    safe_collection_name = re.sub(r'[\\/:*?"<>|.-]', '_', collection_name).strip() 
    
    sub_dir = os.path.join(IMAGE_DIR, safe_collection_name)
    os.makedirs(sub_dir, exist_ok=True) 

    filename = safe_title + extension
    filepath = os.path.join(sub_dir, filename) 

    if os.path.exists(filepath) and os.path.getsize(filepath) > 0:
        return f"Skipped (Exists in '{safe_collection_name}'): {filename}"
        
    try:
        response = requests.get(url, headers=HEADERS, stream=True, timeout=30)
        response.raise_for_status()

        with open(filepath, 'wb') as f:
            for chunk in response.iter_content(chunk_size=8192):
                f.write(chunk)
                
        return f"Downloaded to '{safe_collection_name}': {filename}"
        
    except requests.exceptions.RequestException as e:
        return f"Error downloading {filename} to '{safe_collection_name}' from {url}: {e}"
        
def start_download_executor(all_data):
    """使用ThreadPoolExecutor启动多线程下载"""
    if not all_data:
        print("没有图片数据可供下载。")
        return
        
    MAX_WORKERS = 10 
    success_count = 0
    error_count = 0
    total_tasks = len(all_data)
    
    print(f"\n⚡ 启动 {total_tasks} 个多线程下载任务...")
    
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        future_to_info = {executor.submit(download_image, item): item for item in all_data}
        
        for future in as_completed(future_to_info):
            try:
                result = future.result()
                if result.startswith("Downloaded"):
                    success_count += 1
                elif result.startswith("Error"):
                    error_count += 1
            except Exception as exc:
                print(f"  [EXCEPTION] 任务执行时发生异常: {exc}")
                error_count += 1
                
    print(f"🎉 所有下载任务完成！ 成功: {success_count}， 失败/跳过: {len(all_data) - success_count}， 错误: {error_count}")


# --- 主逻辑 (新增下载开关判断) ---
def main():
    person_tags = read_person_tags(PERSON_TAGS_FILE)
    if not person_tags:
        return
        
    all_unique_data_dict = {}

    for i, tag in enumerate(person_tags):
        person_name = tag.strip()
        print(f"\n=======================================================")
        print(f"🚀 [任务 {i+1}/{len(person_tags)}] 开始处理人物标签: '{person_name}'")
        print(f"=======================================================")

        album_links_and_titles = extract_album_links(person_name)
        if not album_links_and_titles:
            print(f"⚠️ 未找到人物 '{person_name}' 的任何相册，跳过。")
            continue
        print(f"  找到 {len(album_links_and_titles)} 个相册。")

        for j, (url, title) in enumerate(album_links_and_titles):
            data_list = process_album_page(url, title) 
            
            for item in data_list:
                all_unique_data_dict[item['图片URL']] = item
            
        print(f"🌟 人物 '{person_name}' 的数据收集完成，当前总计 {len(all_unique_data_dict)} 条独特图片数据。")
        
    overall_unique_data = list(all_unique_data_dict.values())
        
    if not overall_unique_data:
        print("\n所有人物都没有提取到数据。")
        return
        
    print(f"\n=======================================================")
    print(f"📊 最终总计： {len(overall_unique_data)} 条图片数据准备写入。")
    print(f"=======================================================")

    # D. 写入 CSV
    save_to_csv(overall_unique_data, CSV_PATH)
    
    # E. 启动多线程下载 (新增开关判断)
    if ENABLE_DOWNLOAD:
        print("\n📥 配置：下载功能已启用。")
        start_download_executor(overall_unique_data)
    else:
        print("\n⏸️ 配置：下载功能已禁用。图片信息已保存到 CSV，请稍后运行独立下载脚本。")

if __name__ == '__main__':
    main()