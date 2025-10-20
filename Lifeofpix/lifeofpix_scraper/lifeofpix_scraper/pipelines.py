import csv
import os
from itemadapter import ItemAdapter
from scrapy.pipelines.images import ImagesPipeline
from scrapy.exceptions import DropItem
from urllib.parse import urlparse
from pathlib import Path

class CustomImagesPipeline(ImagesPipeline): # 继承自 ImagesPipeline 
    """
    自定义图片下载 Pipeline，实现按 TAG 存入不同子文件夹的功能。
    """
    def file_path(self, request, response=None, info=None, *, item=None): # 重写 file_path 方法 
        """
        根据 item 中的 tag 字段返回图片存储的相对路径。
        路径格式： TAG/图片SHA1哈希值.jpg
        """
        adapter = ItemAdapter(item)
        tag = adapter.get('tag', 'untagged') # 获取 tag，如果没有则使用 'untagged'
        # 使用 Scrapy 默认的基于 URL 的哈希作为文件名，防止冲突 [cite: 2053, 2129]
        image_guid = Path(super().file_path(request, response=response, info=info, item=item)).name
        # 确保 tag 名字适合作为文件夹名 (可以添加更多清理逻辑)
        safe_tag = "".join(c for c in tag if c.isalnum() or c in (' ', '_')).rstrip()
        filename = f'{safe_tag}/{image_guid}'
        return filename

class CsvPipeline:
    """
    将爬取到的 Item 信息写入 CSV 文件。
    """
    csv_file_path = r"R:\py\Auto_Image-Spider\Lifeofpix\all_lifeofpix.csv" # CSV 文件存储路径 (请确保此路径正确)

    def open_spider(self, spider): # 在爬虫启动时调用 [cite: 519, 523]
        """打开 CSV 文件并准备写入器"""
        self.output_dir = os.path.dirname(self.csv_file_path)
        os.makedirs(self.output_dir, exist_ok=True) # 确保目录存在
        self.file = open(self.csv_file_path, 'a', newline='', encoding='utf-8-sig') # 使用 utf-8-sig 兼容 Excel
        self.writer = csv.writer(self.file)
        # 检查文件是否为空，如果为空则写入表头
        if self.file.tell() == 0:
            self.writer.writerow(['Title', 'ImageName', 'OriginalURL', "TAG", 'ImagePath']) # 添加 ImagePath 列
        spider.logger.info(f"CSV Pipeline 打开，将写入到: {self.csv_file_path}")

    def close_spider(self, spider): # 在爬虫关闭时调用 [cite: 520, 523]
        """关闭 CSV 文件"""
        self.file.close()
        spider.logger.info(f"CSV Pipeline 关闭。")

    def process_item(self, item, spider): # 处理每一个 Item [cite: 515, 523]
        """将 Item 数据写入 CSV 文件"""
        adapter = ItemAdapter(item)
        images_info = adapter.get('images') # 获取 ImagesPipeline 处理后的信息 

        # 确保图片已成功下载
        if images_info and len(images_info) > 0 and images_info[0].get('path'):
            image_path = images_info[0]['path']
            image_name = os.path.basename(image_path) # 从路径中提取文件名
            original_url = adapter['image_urls'][0] # 获取原始 URL
            title = adapter['title']
            tag = adapter['tag']

            try:
                self.writer.writerow([title, image_name, original_url, tag, image_path])
                spider.logger.debug(f"成功写入 CSV: {image_name}")
            except Exception as e:
                spider.logger.error(f"写入 CSV 时发生异常 for item {item}: {e}")
                raise DropItem(f"写入 CSV 失败: {image_name}") # 如果写入失败，可以选择丢弃 Item [cite: 517, 522]
        else:
            # 如果图片下载失败或信息不完整
            spider.logger.warning(f"Item 缺少图片信息或下载失败，无法写入 CSV: {adapter.get('title', 'N/A')}")
            # 可以选择在这里丢弃 Item，或者让它继续传递（取决于需求）
            # raise DropItem(f"缺少图片信息: {adapter.get('title', 'N/A')}")

        return item # 必须返回 Item，以便后续 Pipeline 处理 [cite: 517]