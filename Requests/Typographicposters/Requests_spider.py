import os
import time
import hashlib
import redis
import csv
import random
import re
import json
import requests
from redis.exceptions import ConnectionError as RedisConnectionError

# 配置常量
# 修正：定义 API 的基础 URL 和图片存储的基础域名
API_BASE_URL = 'https://www.typographicposters.com/api/tg/posters-recent' 
# **关键修正**：IMAGE_DOMAIN 确保以斜杠结尾，方便直接拼接 image.path (image.path以 '/' 开头)
IMAGE_BASE_URL = 'https://videos.typographicposters.com/poster-p3' 

TAG_NAME = 'NAN'
ITEMS_PER_PAGE = 32 # 每页数量
# ** 核心配置 **
# 该网页拥有1w+的图片，每页32张，共3125页
START_PAGE = 1  # 从第 1 页开始爬取
MAX_PAGES = 5 # 爬取到第 5 页 (已改为 5 页，方便测试)
PAGE_SLEEP = 3 # 页面间休眠时间（秒）


class typographicposters:
    def __init__(self):
        print("[INFO] 初始化...")
        # Redis 初始化
        try:
            self.redis = redis.Redis(host='localhost', port=6379, db=0, decode_responses=True)
            self.redis.ping()
            print("[√] Redis 连接成功")
        except RedisConnectionError as e:
            print(f"[✗] Redis 连接失败: {e}")
            self.redis = None
            print("[WARN] Redis 不可用，将跳过去重步骤。")

        self.redis_key = 'image_md5_set_eiginleiki'
        
        # 定义请求头，模拟浏览器访问
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.5735.199 Safari/537.36',
            'Accept': 'application/json, text/plain, */*',
            'Referer': 'https://www.typographicposters.com/',
        }

    # ** 修正后的 URL 组合逻辑 **
    def _get_full_image_url(self, image_path):
        """
        根据 JSON 中的相对路径 image.path 组合出完整的图片 URL。
        image_path 示例: /daan-rietbergen/daan-rietbergen-poster-xxx.jpg
        """
        if not image_path:
            return ""
        
        # 确保基础 URL 不以斜杠结尾，以便直接拼接 image_path（它以斜杠开头）
        base_url = IMAGE_BASE_URL.rstrip('/')
            
        # 确保 image_path 以斜杠开头 (理论上 JSON 返回的数据是这样的)
        if not image_path.startswith('/'):
            image_path = '/' + image_path

        # 直接拼接： base_url + image_path
        # 示例: 'https://videos.typographicposters.com/poster-p3' + '/daan-rietbergen/...'
        return f"{base_url}{image_path}"


    def write_to_csv(self, title, name, url, csv_path, tag):
        """将数据写入 CSV 文件"""
        os.makedirs(os.path.dirname(csv_path), exist_ok=True)
        file_exists = os.path.exists(csv_path) and os.path.getsize(csv_path) > 0
        try:
            with open(csv_path, 'a', newline='', encoding='utf-8-sig') as f:
                writer = csv.writer(f)
                if not file_exists:
                    writer.writerow(['Title', 'ImageName', 'URL', "TAG"])
                writer.writerow([title, name, url, tag])
            print(f"[√] 写入成功: {name}")
        except Exception as e:
            print(f"[✗] 写入 CSV 异常: {e}")

    # ** process_page 逻辑不变，但依赖 _get_full_image_url 的正确性 **
    def process_page(self, api_url, tag, csv_path, page_num):
        """发送 API 请求，解析 JSON 并提取图片链接"""
        print(f"\n==== 正在请求 API: {api_url} (第 {page_num} 页) ====")
        
        try:
            response = requests.get(api_url, headers=self.headers, timeout=15)
            response.raise_for_status() # 检查 HTTP 错误
            data = response.json()
        except requests.exceptions.RequestException as e:
            print(f"[✗] 请求 API 失败: {e}")
            return 0 
        except json.JSONDecodeError:
            print(f"[✗] API 响应不是有效的 JSON。")
            return 0

        # 从 JSON 数据中获取 'hits' 数组
        elements = data.get('hits', [])

        if not elements:
            print(f"[INFO] API 响应中未找到 'hits' 数据或数组为空。")
            return 0 

        print(f"[√] 当前页发现 {len(elements)} 个海报数据。")
        extracted_count = 0

        for idx, item in enumerate(elements, 1):
            try:
                print(f"→ [{idx}/{len(elements)}] 正在处理数据...")
                
                # 提取所需信息
                title = item.get('title', 'N/A')
                image_path = item.get('image', {}).get('path')

                if not image_path:
                    print(f" [⚠] 缺少 image.path 属性，跳过。")
                    continue
                
                # 组合完整的图片 URL
                final_url = self._get_full_image_url(image_path)
                    
                print(f" [√] 完整 URL: {final_url}")

                # 计算 MD5 哈希用于去重
                md5_hash = hashlib.md5(final_url.encode('utf-8')).hexdigest()

                # 检查 Redis，防止重复
                if self.redis:
                    if not self.redis.sismember(self.redis_key, md5_hash):
                        self.redis.sadd(self.redis_key, md5_hash)
                        img_name = os.path.basename(final_url)
                        # 写入 CSV
                        self.write_to_csv(title, img_name, final_url, csv_path, tag)
                        extracted_count += 1
                    else:
                        print(" [INFO] URL 已存在 (MD5 校验)。")
                else:
                    # 如果没有 Redis，则不进行去重，直接写入
                    img_name = os.path.basename(final_url)
                    self.write_to_csv(title, img_name, final_url, csv_path, tag)
                    extracted_count += 1
                    
            except Exception as e:
                print(f"[✗] 处理数据时出错: {e}")
                continue

        print(f"[INFO] 本页完成，新增 {extracted_count} 条记录。")
        return extracted_count

    def run(self, api_base_url, tag, csv_path):
        """主运行函数，处理分页逻辑"""
        total = 0
        print(f"[INFO] 启动 API 爬取（起始页：{START_PAGE}，目标页数：{MAX_PAGES}，每页：{ITEMS_PER_PAGE}）...")

        for page_num in range(START_PAGE, MAX_PAGES + 1):
            # 构建带 page 和 itemsPerPage 参数的 API URL
            api_url = f"{api_base_url}?page={page_num}&itemsPerPage={ITEMS_PER_PAGE}"
            
            # 调用 process_page 处理 API 数据
            count = self.process_page(api_url, tag, csv_path, page_num)
            total += count
            
            print(f"[进度] 已完成 {page_num}/{MAX_PAGES} 页。")
            
            time.sleep(random.uniform(1, PAGE_SLEEP))

        print(f"[完成] 爬取结束，总计 {total} 条。")


if __name__ == '__main__':
    # 配置保存路径
    save_dir = r'R:\py\Auto_Image-Spider\Typographicposters\data'
    csv_path = os.path.join(save_dir, 'all_typographicposters_api.csv')

    try:
        crawler = typographicposters() 
        crawler.run(API_BASE_URL, TAG_NAME, csv_path)
    except Exception as e:
        print(f"[程序退出] 异常: {e}")