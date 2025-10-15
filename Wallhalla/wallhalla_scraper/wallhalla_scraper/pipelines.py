# wallhalla_scraper/wallhalla_scraper/pipelines.py

import os
import csv
import threading
from scrapy.pipelines.files import FilesPipeline
from scrapy.utils.project import get_project_settings
from scrapy.exporters import CsvItemExporter # 使用 Scrapy 内置的 CSV 导出器更方便

# --- 1. 图片下载和去重 Pipeline ---
class WallhallaFilePipeline(FilesPipeline):
    """
    继承 FilesPipeline，负责图片的下载、去重和重命名。
    """
    
    def file_path(self, request, response=None, info=None, *, item=None):
        """
        自定义文件保存路径和文件名，实现 'tag' 子目录和自定义文件名。
        """
        # Scrapy 会使用 FILES_STORE 作为根目录
        tag_dir = item['tag'] 
        image_name = item['image_name'] 
        
        # 最终路径: {FILES_STORE}/{tag_dir}/{image_name}
        return os.path.join(tag_dir, image_name)

# --- 2. CSV 数据写入 Pipeline ---
class WallhallaCSVPipeline:
    """
    负责将 Item 数据写入一个统一的 CSV 文件。
    """
    
    def __init__(self):
        # 使用 Scrapy 的项目设置来获取路径
        settings = get_project_settings()
        base_save_dir = settings.get('FILES_STORE').rsplit(os.sep, 1)[0] # 返回上级目录
        
        # CSV 文件路径
        self.csv_path = os.path.join(base_save_dir, 'all_records_wallhalla_scrapy.csv')
        self.file = None
        self.exporter = None
        self.csv_lock = threading.Lock() # 虽然 Scrapy 是单线程调度，但使用锁是个好习惯
        self.fields_to_export = ['title', 'image_name', 'detail_url', 'tag']

    @classmethod
    def from_crawler(cls, crawler):
        return cls()

    def open_spider(self, spider):
        # 启动爬虫时打开文件
        try:
            is_file_empty = not os.path.exists(self.csv_path) or os.stat(self.csv_path).st_size == 0
            
            self.file = open(self.csv_path, 'ab') # 使用 'ab' 模式以兼容 CsvItemExporter
            self.exporter = CsvItemExporter(self.file, 
                                            fields_to_export=self.fields_to_export,
                                            encoding='utf-8-sig') # 使用 utf-8-sig 兼容 Excel
            self.exporter.start_exporting()
            
            # 如果文件为空，则写入 header
            if is_file_empty:
                self.file.write(','.join(self.fields_to_export).encode('utf-8-sig') + b'\n')
            
            spider.logger.info(f"✅ CSV 文件已打开/创建: {self.csv_path}")

        except Exception as e:
            spider.logger.error(f"[✗] 打开 CSV 文件出错: {e}")
            
    def close_spider(self, spider):
        # 关闭爬虫时关闭文件
        if self.exporter:
            self.exporter.finish_exporting()
        if self.file:
            self.file.close()

    def process_item(self, item, spider):
        # 处理每个 Item
        if self.exporter:
            # 确保只写入我们需要的字段
            export_item = {k: item.get(k) for k in self.fields_to_export}
            self.exporter.export_item(export_item)
        return item