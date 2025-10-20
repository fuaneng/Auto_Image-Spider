import scrapy

class LifeofpixItem(scrapy.Item):
    # 定义需要抓取的字段
    title = scrapy.Field()         # 图片标题 (对应 'adobeRelatedTitle') [cite: 356]
    image_urls = scrapy.Field()    # 图片下载 URL 列表 (供 ImagesPipeline 使用) [cite: 2038, 2046, 2078]
    images = scrapy.Field()        # ImagesPipeline 下载后填充的信息 [cite: 2042, 2078]
    tag = scrapy.Field()           # 图片所属的标签 [cite: 356]
    image_name = scrapy.Field()    # 下载后的图片文件名 (用于 CSV) [cite: 356]
    image_path = scrapy.Field()    # 下载后的图片相对路径 (用于 CSV) [cite: 356]