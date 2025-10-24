# wallhalla_scraper/wallhalla_scraper/items.py

import scrapy

class WallhallaItem(scrapy.Item):
    # 图片下载所需的字段 (Scrapy FilesPipeline 会使用这些)
    file_urls = scrapy.Field() # 包含最终下载链接的列表
    files = scrapy.Field()     # FilesPipeline 自动填充

    # 爬虫自定义的元数据字段
    title = scrapy.Field()     # 壁纸的标题
    tag = scrapy.Field()       # 搜索使用的标签
    detail_url = scrapy.Field() # 详情页链接（用于记录）
    image_name = scrapy.Field() # 最终保存的文件名