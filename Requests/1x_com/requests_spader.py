import requests
import re
import pandas as pd
from bs4 import BeautifulSoup
from typing import List, Dict, Any, Optional

# --- 全局配置 ---
BASE_URL = 'https://1x.com/backend/lm2.php'
TARGET_URL = 'https://1x.com/gallery/fine-art-nude/awarded' # 用于 Referer 头部
CSV_PATH = r'R:\py\Auto_Image-Spider\Requests\1x_com\1x_com_awarded.csv'
ITEMS_PER_PAGE = 20 # 观察到的 from 参数增量

# 初始请求参数 (第一页)
INITIAL_PARAMS = {
    'style': 'normal',
    'mode': 'latest:12:awarded',
    'from': 0,
    'autoload': '',
    'search': '',
    'alreadyloaded': ''
}

# --- 数据结构定义 ---
class PhotoData:
    """用于存储单张照片数据的简单类。"""
    def __init__(self, image_url: str, author_name: str, year: str):
        self.image_url = image_url
        self.author_name = author_name
        self.year = year

    def to_list(self) -> List[str]:
        """返回用于 CSV 写入的列表。"""
        return [self.image_url, self.author_name, self.year]

# --- 辅助函数 ---

def extract_data_from_html(html_content: str) -> List[PhotoData]:
    """
    解析 HTML 片段，提取图片地址、作者名和年份。
    
    Args:
        html_content: 包含图片元素的 HTML 字符串。
        
    Returns:
        包含 PhotoData 对象的列表。
    """
    soup = BeautifulSoup(html_content, 'html.parser')
    photos_data: List[PhotoData] = []
    
    # 查找所有图片容器
    containers = soup.find_all('div', class_='photos-feed-item')
    
    for container in containers:
        image_url = ''
        author_name = ''
        year = ''
        
        # 1. 提取图片地址 (src属性包含 "hd4.jpg" 或 "hd.jpg" 的项)
        img_tag = container.find('img', class_=re.compile(r'photos-feed-image'))
        if img_tag and 'src' in img_tag.attrs:
            src = img_tag['src']
            # 根据你的分析，hd4.jpg 是我们要的图片地址
            if 'hd4.jpg' in src or 'hd.jpg' in src:
                image_url = src
                
        # 2. 提取作者名和年份
        # 寻找包含作者名和链接的 <a> 标签
        author_link = container.find('a', href=re.compile(r'/[a-zA-Z0-9]+'))
        if author_link:
            author_name = author_link.text.strip()
            
            # 从 href 属性中提取年份 (最后的四位数字)
            href = author_link['href']
            match = re.search(r'(\d{4})$', href)
            if match:
                year = match.group(1)
            
        # 确保图片地址不为空才添加
        if image_url:
            photos_data.append(PhotoData(image_url, author_name, year))
            
    return photos_data

def get_image_ids(html_content: str) -> List[str]:
    """
    从 HTML 片段中提取所有已加载图片的 ID，用于构造下一页的 'alreadyloaded' 参数。
    """
    # 匹配 id="imgcontainer-xxxxxx" 中的数字部分
    return re.findall(r'id="imgcontainer-(\d+)"', html_content)

def fetch_page_data(params: Dict[str, Any]) -> Optional[str]:
    """
    发送 GET 请求获取某一页的数据，并提取 CDATA 部分的 HTML 内容。
    """
    print(f"正在请求 page: from={params['from']}, 已加载ID数量={len(params['alreadyloaded'].split(':')) - 1}")
    try:
        # 模拟浏览器行为，添加 headers
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Referer': TARGET_URL,
            'X-Requested-With': 'XMLHttpRequest', # 模拟 XHR 请求
        }
        
        # 发送请求
        response = requests.get(BASE_URL, params=params, headers=headers, timeout=30)
        response.raise_for_status() # 检查HTTP错误
        
        # 提取 <data><![CDATA[...]]></data> 中的内容
        match = re.search(r'<data><!\[CDATA\[(.*?)\]\]></data>', response.text, re.DOTALL)
        if match:
            return match.group(1)
        else:
            print(f"Page from={params['from']}: 响应中未找到 CDATA 数据。")
            return None
        
    except requests.exceptions.RequestException as e:
        print(f"请求失败 (from={params['from']}): {e}")
        return None

# --- 主逻辑函数 ---

def main_scraper():
    """
    主爬虫逻辑，按需串行请求，直到页面没有数据为止。
    """
    
    print("--- 开始串行请求，动态构建 'alreadyloaded' 参数序列 ---")
    
    # 确保 CSV 文件的表头存在
    headers = ['图片地址', '作者名', '年份']
    try:
        # 写入表头，mode='w' 会清空文件并重新写入
        df_init = pd.DataFrame(columns=headers)
        df_init.to_csv(CSV_PATH, index=False, encoding='utf-8-sig', mode='w')
        print(f"已创建或清空 CSV 文件并写入表头: {CSV_PATH}")
    except Exception as e:
        print(f"写入 CSV 文件失败，请检查路径权限: {e}")
        return
        
    already_loaded_ids: List[str] = []
    page_num = 0
    total_extracted_count = 0

    while True:
        
        # 构造当前请求的 alreadyloaded 字符串 (例如: ":id1:id2:id3...")
        already_loaded_str = ":" + ":".join(already_loaded_ids)
        
        # 构造请求参数
        current_params = INITIAL_PARAMS.copy()
        current_params['from'] = page_num * ITEMS_PER_PAGE
        current_params['alreadyloaded'] = already_loaded_str
        
        # 1. 发送请求并获取 HTML 片段
        html_content = fetch_page_data(current_params)
        
        if html_content:
            # 2. 提取数据
            photos_data = extract_data_from_html(html_content)
            
            # --- 关键停止逻辑 ---
            if not photos_data:
                print(f"Page {page_num + 1} (from={current_params['from']}) 未提取到任何图片数据，认为已到达末尾，停止爬取。")
                break # 退出 while 循环
            # --------------------
            
            # 3. 更新已加载 ID 列表
            current_page_ids = get_image_ids(html_content)
            already_loaded_ids.extend(current_page_ids)
            
            # 4. 数据写入 CSV
            # 转换为 DataFrame
            df = pd.DataFrame([p.to_list() for p in photos_data], columns=headers)
            
            # 写入 CSV，mode='a' 表示追加，header=False 表示不写入表头
            df.to_csv(CSV_PATH, index=False, encoding='utf-8-sig', mode='a', header=False)
            
            print(f"Page {page_num + 1} (from={current_params['from']}) 成功抓取 {len(photos_data)} 条数据并写入 CSV.")
            
            total_extracted_count += len(photos_data)
            page_num += 1 # 准备爬取下一页
            
        else:
            # 如果请求失败或响应数据无效，也停止爬取
            print(f"Page {page_num + 1} (from={current_params['from']}) 请求失败或响应数据无效，停止爬取。")
            break 

    print("\n--- 爬取完成 ---")
    print(f"总共提取到 {total_extracted_count} 条数据。")


if __name__ == '__main__':
    main_scraper()