# wallhalla_scraper/wallhalla_scraper/settings.py (部分重要配置)

# ... (其他默认设置)

BOT_NAME = 'wallhalla_scraper'

SPIDER_MODULES = ['wallhalla_scraper.spiders']  # ⬅️ **确保是这个路径**
NEWSPIDER_MODULE = 'wallhalla_scraper.spiders'

# Scrapy 默认是不允许图片加载的，所以不需要额外设置

# ----------------- 数据存储和下载配置 -----------------

# 你的图片下载根目录。Scrapy 会在此目录下创建一个 'full' 子目录存放图片。
# *** 🚨 请修改为你的实际路径！ ***
FILES_STORE = r"\\10.58.134.120\aigc2\01_数据\爬虫数据\wallhalla\images"

# Scrapy Files Pipeline 配置 (用于自动下载图片并去重)
ITEM_PIPELINES = {
    'wallhalla_scraper.pipelines.WallhallaFilePipeline': 1, # 1 是优先级，先下载
    'wallhalla_scraper.pipelines.WallhallaCSVPipeline': 2,
}

# 启用 FilesPipeline
# FILES_URLS_FIELD = 'file_urls' # 默认就是 file_urls
# FILES_RESULT_FIELD = 'files' # 默认就是 files

# ----------------- 爬虫行为配置 -----------------

# 标签文件路径 (用于蜘蛛读取初始标签)
# *** 🚨 请修改为你的实际路径！ ***
TAG_FILE_PATH = r'D:\work\爬虫\爬虫数据\wallhalla\ram_tag_list_备份.txt'

# 并发和延迟设置（重要）
# 推荐的并发数（根据你的网络和服务器承受能力调整）
CONCURRENT_REQUESTS = 16 

# 启用下载延迟，模拟人类行为，防止被封
DOWNLOAD_DELAY = 4
# 在 0.5 到 4.5 秒之间随机延迟，模拟人类行为
RANDOMIZE_DOWNLOAD_DELAY = True

# 每个域名的最大并发连接数（确保同时连接数极低）
CONCURRENT_REQUESTS_PER_DOMAIN = 1 

# 设置 User-Agent 
USER_AGENT = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'

# 禁用 Robots.txt 检查
ROBOTSTXT_OBEY = False

# 禁用 Cookies (如果网站不需要登录，可以提高效率)
COOKIES_ENABLED = False

# 禁用 SSL/TLS 证书验证。仅用于解决特定网站证书问题，不建议用于敏感数据。
DOWNLOAD_HANDLERS = {
    'https': 'scrapy.core.downloader.handlers.http.HTTPDownloadHandler',
}
# 或者
# TELNET_ENABLED = False # 禁用 Telnet 也可以解决一些旧版本 Twisted 证书问题

# 提高日志级别，以便看到 INFO 和 DEBUG 消息
LOG_LEVEL = 'INFO'  # 保持为 INFO