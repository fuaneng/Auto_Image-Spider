# SplitshireProject/settings.py

# ... 其他默认配置 ...

# =========================================================
# 自定义 Item Pipeline 配置 (根据 Scrapy 文档要求启用)
# =========================================================

# 启用并设置 Item Pipeline 的优先级（300 是一个惯例值）
ITEM_PIPELINES = {
    'SplitshireProject.pipelines.SplitshireCsvPipeline': 300,
}
# 确保文件路径：SplitshireProject/SplitshireProject/settings.py
BOT_NAME = 'SplitshireProject'

SPIDER_MODULES = ['SplitshireProject.spiders']
NEWSPIDER_MODULE = 'SplitshireProject.spiders'

# 依据 Scrapy 文档，强制使用兼容的 Reactor
TWISTED_REACTOR = 'twisted.internet.selectreactor.SelectReactor'
# 自定义 CSV 写入路径 (供 Pipeline 读取)
# 文件将存储在 D:\work\爬虫\plausible\splitshire_items.csv
CUSTOM_CSV_PATH = r"R:\py\Auto_Image-Spider\Splitshire"


# =========================================================
# 其他爬虫建议设置 (最佳实践)
# =========================================================

# 设置爬虫的延时，避免给目标网站造成过大压力 (politeness) 
# 下载延迟（例如 1 秒）
DOWNLOAD_DELAY = 1 

# 限制并发请求数
CONCURRENT_REQUESTS = 16

# 模拟浏览器行为 (User-Agent)
USER_AGENT = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36 Scrapy-Assistant/1.0'