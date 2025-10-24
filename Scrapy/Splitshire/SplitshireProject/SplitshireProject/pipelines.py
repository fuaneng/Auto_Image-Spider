# SplitshireProject/pipelines.py

import csv
import os
from itemadapter import ItemAdapter
from scrapy.exceptions import DropItem

class SplitshireCsvPipeline:
    """
    将 Item 数据写入到指定的 CSV 文件中
    """
    
    # 默认写入信息文件路径，从 settings 中获取
    DEFAULT_CSV_PATH = r"R:\py\Auto_Image-Spider\Splitshire"
    
    # 在 Scrapy 初始化组件时，通过 from_crawler 传入配置 [cite: 2]
    @classmethod
    def from_crawler(cls, crawler):
        # 从 settings 中获取自定义路径
        csv_dir = crawler.settings.get('CUSTOM_CSV_PATH', cls.DEFAULT_CSV_PATH)
        return cls(csv_dir=csv_dir)

    def __init__(self, csv_dir):
        # 构造函数接收目录路径
        self.csv_dir = csv_dir
        self.files = {}
        self.writers = {}

    def open_spider(self, spider):
        """
        爬虫开启时打开或创建 CSV 文件，并准备写入器
        """
        # CSV 文件名为 'splitshire_items.csv'，存放在指定目录下
        csv_filename = f'{spider.name}_items.csv'
        full_path = os.path.join(self.csv_dir, csv_filename)
        
        # 确保目录存在
        os.makedirs(os.path.dirname(full_path), exist_ok=True)
        
        # 检查文件是否已存在且非空，以决定是否写入表头
        file_exists = os.path.exists(full_path) and os.path.getsize(full_path) > 0
        
        try:
            # 以追加模式打开文件，使用 'utf-8-sig' 确保 Excel 兼容中文
            file = open(full_path, 'a', newline='', encoding='utf-8-sig')
            self.files[spider.name] = file
            self.writers[spider.name] = csv.writer(file)
            
            if not file_exists:
                # 写入表头
                self.writers[spider.name].writerow(['Title', 'ImageName', 'URL', 'TAG'])
        except Exception as e:
            spider.logger.error(f"打开或创建 CSV 文件失败: {e}")
            raise DropItem(f"无法写入 CSV 文件: {e}")


    def close_spider(self, spider):
        """
        爬虫关闭时关闭文件
        """
        if spider.name in self.files:
            self.files[spider.name].close()
            spider.logger.info(f"CSV 文件已关闭: {os.path.join(self.csv_dir, f'{spider.name}_items.csv')}")


    def process_item(self, item, spider):
        """
        处理每个 Item，将其写入 CSV
        """
        adapter = ItemAdapter(item)
        
        try:
            writer = self.writers.get(spider.name)
            if writer:
                row = [
                    adapter.get('title'),
                    adapter.get('image_name'),
                    adapter.get('image_url'),
                    adapter.get('tag')
                ]
                writer.writerow(row)
                spider.logger.info(f"[√] 写入 CSV 成功: {adapter.get('image_name')}")
            else:
                raise DropItem(f"CSV Writer 未初始化: {adapter.get('image_name')}")

        except Exception as e:
            spider.logger.error(f"[✗] 写入 CSV 异常: {e}")
            # 捕获异常后抛出 DropItem，阻止 Item 进入后续 Pipeline
            raise DropItem(f"写入 CSV 异常: {e}")
            
        return item