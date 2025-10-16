# SplitshireProject/spiders/splitshire.py

import scrapy
import os
from ..items import SplitshireItem

# 定义标签文件的绝对路径
TAG_FILE_PATH = r"R:\py\Auto_Image-Spider\Splitshire\ram_tag_list.txt"
BASE_URL = 'https://www.splitshire.com/images?search='

class SplitshireSpider(scrapy.Spider):
    """
    Splitshire 爬虫：从本地文件读取标签并爬取搜索结果页面中的图片信息。
    """
    name = 'splitshire'
    allowed_domains = ['splitshire.com', 'images.splitshire.com']

    def start_requests(self):
        """
        根据本地标签文件生成初始请求。
        """
        self.logger.info(f"正在从文件读取标签: {TAG_FILE_PATH}")
        
        if not os.path.exists(TAG_FILE_PATH):
            self.logger.error(f"本地标签文件不存在，请检查路径: {TAG_FILE_PATH}")
            return

        try:
            # 读取标签文件，并对标签进行去重处理
            with open(TAG_FILE_PATH, 'r', encoding='utf-8') as f:
                tags = {line.strip() for line in f if line.strip()}
        except Exception as e:
            self.logger.error(f"读取标签文件失败: {e}")
            return

        for tag in tags:
            # 拼接完整的搜索 URL
            url = f"{BASE_URL}{tag}"
            self.logger.info(f"生成起始请求: URL={url}, Tag={tag}")
            # 使用 cb_kwargs 传递 tag，以便在 parse 方法中使用
            yield scrapy.Request(url, self.parse, cb_kwargs={'tag': tag})

    def parse(self, response, tag):
        """
        解析搜索结果页面，提取图片链接和标题。
        修正: 优先从 data-src 提取，以应对延迟加载。
        """
        item_containers = response.css('div.grid-blocks-items div.grid-item')

        if not item_containers:
            self.logger.warning(f"页面 {response.url} 未找到任何图片容器 (div.grid-item)")
            return
        
        for item_container in item_containers:
            item = SplitshireItem()
            
            # 1. 提取图片预览链接 (优先从 data-src 提取，然后回退到 src)
            # 根据 Scrapy Selector 规则: 提取 img.lozad 元素的 data-src 属性
            preview_url = item_container.css('img.lozad::attr(data-src)').get()
            
            # 如果 data-src 为空，则回退到 src 属性
            if not preview_url:
                preview_url = item_container.css('img.lozad::attr(src)').get()

            # 2. 提取标题 (保持不变)
            title_parts = item_container.css('div.d-flex h3 *::text').getall()
            title = ''.join(t.strip() for t in title_parts if t.strip())

            # 基础数据有效性检查
            if not preview_url or not title:
                self.logger.debug(f"跳过缺少数据项 (Tag: {tag}). 容器内容片段: {item_container.get()[:200]}")
                continue

            # 确保排除 'default.png' 或其他占位符 URL
            if 'default.png' in preview_url.lower() or '/thumbnail/' not in preview_url:
                self.logger.debug(f"跳过占位图或无效链接: {preview_url}")
                continue

            # 3. 替换 URL 成原图
            # 规则: 使用'/thumbnail/'替换成'/full/'来获取原图 URL
            full_image_url = preview_url.replace('/thumbnail/', '/full/')
            
            # 4. 提取图片名称 (确保保留完整文件名，如 The-Creepy..._N4wjI.png)
            image_name = full_image_url.split('/')[-1]
            
            # 填充 Item
            item['title'] = title
            item['image_url'] = full_image_url
            item['image_name'] = image_name
            item['tag'] = tag

            yield item