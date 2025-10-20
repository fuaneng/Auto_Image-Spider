# settings.py

BOT_NAME = "lifeofpix_scraper"

SPIDER_MODULES = ["lifeofpix_scraper.spiders"]
NEWSPIDER_MODULE = "lifeofpix_scraper.spiders"

# Obey robots.txt rules
ROBOTSTXT_OBEY = False # 通常API接口不需要遵守robots.txt, 但请自行判断风险 [cite: 1883, 1890]

# Configure item pipelines
# See https://docs.scrapy.org/en/latest/topics/item-pipeline.html
ITEM_PIPELINES = {
   'lifeofpix_scraper.pipelines.CustomImagesPipeline': 1, # 首先运行图片下载 Pipeline [cite: 2049]
   'lifeofpix_scraper.pipelines.CsvPipeline': 300,        # 然后运行 CSV 写入 Pipeline (确保顺序在 ImagesPipeline 之后) [cite: 541, 542]
}

# Configure Images Pipeline settings
# 图片存储路径 (请确保此路径存在或有权限创建) 
IMAGES_STORE = r'R:\py\Auto_Image-Spider\Lifeofpix\images'
# IMAGES_STORE = 'images' # 也可以使用相对路径，相对于项目根目录

# 设置图片下载延迟和并发 (根据需要调整，避免对目标网站造成过大压力)
DOWNLOAD_DELAY = 1 # 下载间隔秒数 [cite: 1486]
CONCURRENT_REQUESTS_PER_DOMAIN = 8 # 对同一域名的并发请求数 [cite: 1441]
# CONCURRENT_REQUESTS = 16 # 全局并发请求数 [cite: 1440]

# 设置 User-Agent (模仿浏览器，降低被封锁风险)
USER_AGENT = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36' # 

# 图片管道默认会过滤掉最近90天内下载过的图片 [cite: 2083, 2084]
# 如果希望每次都重新下载或检查（例如URL不变但图片可能更新），可以设置
# IMAGES_EXPIRES = 0 # 0 表示永不过期，但仍然会基于URL哈希检查是否已下载

# 可选：配置缩略图 [cite: 2088]
# IMAGES_THUMBS = {
#     'small': (50, 50),
# }

# 可选：过滤过小的图片 [cite: 2090]
# IMAGES_MIN_HEIGHT = 100
# IMAGES_MIN_WIDTH = 100

# 启用 Scrapy 内置的去重过滤器 (基于请求指纹) [cite: 1524]
# DUPEFILTER_CLASS = 'scrapy.dupefilters.RFPDupeFilter' # 这是默认值，无需显式设置
# DUPEFILTER_DEBUG = True # 设为 True 可以看到所有被过滤掉的重复请求日志 [cite: 1530]

# 其他推荐设置
REQUEST_FINGERPRINTER_IMPLEMENTATION = "2.7" # 使用新的指纹实现
TWISTED_REACTOR = "twisted.internet.asyncioreactor.AsyncioSelectorReactor" # 推荐的 Reactor [cite: 1620, 1631]
FEED_EXPORT_ENCODING = "utf-8" # 导出文件编码 [cite: 1075]