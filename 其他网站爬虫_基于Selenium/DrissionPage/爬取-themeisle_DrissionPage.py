from DrissionPage import Chromium
import os
import time
import hashlib
import redis
import csv
import threading
from typing import List

class themeisle:
    def __init__(self, port=9527, max_workers=12):
        self.browser = Chromium(port)
        self.max_workers = max_workers

        self.redis = redis.Redis(
            host='localhost',
            port=6379,
            db=0,
            decode_responses=True
        )
        self.redis_key = 'image_md5_set_themeisle'
        self.csv_lock = threading.Lock()
        
    def url(self, tag):
        """
        根据标签构建搜索URL
        """
        return f'https://mystock.themeisle.com/?s={tag}&tag='

    def get_images(self, tab, tag, csv_path):
        """
        解析页面上所有图片信息并存储 URL。
        """
        img_wrappers = tab.eles('.gallery__photo-wrapper')
        if not img_wrappers:
            print(f"[-] 在标签 '{tag}' 下未找到任何图片。")
            return
        
        print(f"[+] 找到 {len(img_wrappers)} 个图片容器，开始通过 JavaScript 获取链接...")
        
        found_count = 0
        for i, wrapper in enumerate(img_wrappers):
            try:
                script = """
                var downloadLink = arguments[0].querySelector('.gallery__photo-info__download');
                return downloadLink ? downloadLink.href : null;
                """
                url = tab.run_js(script, wrapper)
                
                if url:
                    md5_value = hashlib.md5(url.encode()).hexdigest()
                    
                    if self.redis.sismember(self.redis_key, md5_value):
                        continue
                    
                    self.redis.sadd(self.redis_key, md5_value)
                    
                    image_name = url.split('/')[-1].split('?')[0]
                    self.write_to_csv(tag, image_name, url, csv_path)
                    found_count += 1

            except Exception as e:
                print(f"[✗] 解析图片异常：{e}")

        print(f"[+] 本次解析找到并处理了 {found_count} 个新链接。")

    def write_to_csv(self, title, name, url, csv_path):
        """将图片信息写入 CSV 文件"""
        try:
            with self.csv_lock:
                with open(csv_path, 'a', newline='', encoding='utf-8-sig') as f:
                    writer = csv.writer(f)
                    if f.tell() == 0:
                        writer.writerow(['Title', 'ImageName', 'URL', "TAG"])
                    writer.writerow(['', name, url, title])
                    f.flush()
            print(f'[√] 写入成功：{name}')
        except Exception as e:
            print(f'[✗] 写入 CSV 异常：{name} -> {e}')

    def crawl_page(self, url, tag, csv_path):
        tab = self.browser.new_tab()
        try:
            tab.get(url)
            print(f"[+] 正在加载页面：{url}")
            
            start_time = time.time()
            timeout = 30
            # 检查是否有图片元素，如果没有则直接返回
            while True:
                first_ele = tab.ele('.gallery__photo-wrapper')
                if first_ele:
                    print(f"[*] 第一个图片元素已找到，开始滚动。")
                    break
                if time.time() - start_time > timeout:
                    print("[✗] 等待元素超时，页面未加载成功，跳过该标签。")
                    return False
                time.sleep(1)
            
            last_image_count = 0
            
            while True:
                current_image_elements = tab.eles('.gallery__photo-wrapper')
                current_image_count = len(current_image_elements)
                
                print(f'[*] 当前图片数量: {current_image_count}')
                
                if current_image_count == last_image_count:
                    print("[*] 图片数量不再增加，认为已加载所有内容。")
                    break
                
                last_image_element = current_image_elements[-1]
                
                script = "arguments[0].scrollIntoView(true);"
                tab.run_js(script, last_image_element)
                
                time.sleep(5)
                
                last_image_count = current_image_count
            
            print("[*] 滚动完成，开始解析页面所有图片。")
            self.get_images(tab, tag, csv_path)
            
            return True
        except Exception as e:
            print(f"[✗] 爬取页面异常：{url} -> {e}")
            return False
        finally:
            tab.close()
    
    def load_tags_from_file(self, file_path: str) -> List[str]:
        tags = []
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                for line in f:
                    tag = line.strip()
                    if tag:
                        tags.append(tag)
        except FileNotFoundError:
            print(f"[✗] 错误：未找到标签文件 {file_path}")
        return tags

    def main(self):
        save_path_all = r'D:\work\爬虫\爬虫数据\themeisle'
        os.makedirs(save_path_all, exist_ok=True)
        
        tags_file_path = r"D:\work\爬虫\ram_tag_list.txt"
        tags = self.load_tags_from_file(tags_file_path)
        
        if not tags:
            print("[✗] 未找到任何标签，爬虫已退出。")
            return
        
        # 定义一个总的CSV文件路径
        csv_path_all = os.path.join(save_path_all, 'all_records.csv')
        
        # 检查并删除旧文件，以确保每次运行都是全新的
        if os.path.exists(csv_path_all):
            os.remove(csv_path_all)
            print(f"[*] 已删除旧的 '{csv_path_all}' 文件。")
            
        print("[*] 正在清空 Redis 缓存...")
        self.redis.delete(self.redis_key)
        
        for tag in tags:
            start_url = self.url(tag)
            
            print(f'\n[INFO] 正在爬取【{tag}】 ...')
            
            # 使用统一的csv_path_all，不再为每个标签创建新文件
            success = self.crawl_page(start_url, tag, csv_path_all)
            
            if success:
                print(f'[完成] 【{tag}】页面爬取与去重完毕。\n')
            else:
                print(f'[跳过] 【{tag}】无图片或加载失败。\n')

if __name__ == '__main__':
    spider = themeisle()
    spider.main()