# SplitshireProject/items.py

import scrapy

class SplitshireItem(scrapy.Item):
    """
    定义要抓取的数据字段：标题、原图URL、图片文件名称和搜索标签
    """
    # 标题
    title = scrapy.Field()
    # 原图 URL
    image_url = scrapy.Field()
    # 图片文件名称（用于下载或存储）
    image_name = scrapy.Field()
    # 搜索使用的标签
    tag = scrapy.Field()