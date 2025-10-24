
# Life of Pix 图片爬虫 (lifeofpix_scraper)

## 描述

本项目是一个使用 Scrapy 框架编写的网络爬虫，旨在从 `lifeofpix.com` 网站抓取图片。它会根据本地提供的标签列表，通过网站的 API 搜索相关图片，下载图片并将其按标签分类存储，同时将图片的元数据（标题、原始 URL、标签、本地存储路径等）保存到一个 CSV 文件中。

## 功能特性

* [cite_start]**基于标签搜索:** 从本地文本文件 (`tag.txt`) 读取标签，为每个标签执行图片搜索 [cite: 1982]。
* [cite_start]**API 抓取:** 直接请求 `lifeofpix.com` 的 JSON API 获取图片数据，效率更高 [cite: 1752, 1748]。
* [cite_start]**自动翻页:** 自动处理 API 的分页，逐页获取图片信息 [cite: 1756]。
* [cite_start]**重复内容检测:** 当连续两页获取到的图片 URL 列表完全相同时，自动停止对该标签的爬取，避免无限循环 [cite: 1006]。
* [cite_start]**图片下载:** 使用 Scrapy 内建的 `ImagesPipeline` 下载图片 [cite: 1373, 1385]。
* [cite_start]**按标签分类存储:** 下载的图片会根据其搜索标签自动存放在对应的子文件夹内 [cite: 1399]。
* **元数据存储:** 将每张成功下载图片的标题 (`adobeRelatedTitle`)、原始下载 URL (`urlDownload`)、所属标签以及本地存储的相对路径记录到 CSV 文件中。
* [cite_start]**去重:** 利用 Scrapy 内建的请求去重机制避免重复爬取 API 页面 [cite: 765, 1019][cite_start]。`ImagesPipeline` 也会基于其缓存机制避免重复下载相同的图片文件 [cite: 1422]。

## 环境要求

* [cite_start]Python 3.9 或更高版本 [cite: 1034]。
* Scrapy 框架。
* (推荐) [cite_start]在 Python 虚拟环境中运行 [cite: 1040, 1042]。

## 安装

1.  **克隆或下载项目:**
    将项目文件放置在您的本地计算机上。

2.  **创建并激活虚拟环境 (推荐):**
    ```bash
    python -m venv venv
    # Windows
    .\venv\Scripts\activate
    # macOS/Linux
    source venv/bin/activate
    ```

3.  **安装 Scrapy:**
    如果您的环境中尚未安装 Scrapy，请运行：
    ```bash
    pip install Scrapy
    ```
   

## 配置

在运行爬虫之前，请确保以下配置正确：

1.  **标签文件:**
    * 确认 `lifeofpix_scraper/spiders/lifeofpix_spider.py` 文件中的 `tag_file_path` 变量指向您存放标签列表的 `.txt` 文件 (默认为 `R:/py/Auto_Image-Spider/Lifeofpix/tag.txt`)。
    * 标签文件中每行应包含一个标签。

2.  **输出路径:**
    * [cite_start]**图片存储:** 在 `lifeofpix_scraper/settings.py` 文件中，检查 `IMAGES_STORE` 设置。这是图片下载后存放的根目录 (默认为 `D:\work\爬虫\lifeofpix\images`)。爬虫会自动在此目录下创建以标签命名的子文件夹。请确保 Scrapy 进程对该目录有写入权限 [cite: 1390]。
    * **CSV 文件:** 在 `lifeofpix_scraper/pipelines.py` 文件中的 `CsvPipeline` 类里，检查 `csv_file_path` 变量。这是存储图片元数据的 CSV 文件路径 (默认为 `D:\work\爬虫\lifeofpix\all_lifeofpix.csv`)。请确保 Scrapy 进程对该目录有写入权限。

3.  **爬虫设置 (可选):**
    * 在 `lifeofpix_scraper/settings.py` 文件中，您可以根据需要调整以下设置：
        * [cite_start]`DOWNLOAD_DELAY`: 请求之间的延迟（秒），用于控制爬取速度，避免给服务器带来过大压力 [cite: 727, 1649]。
        * [cite_start]`CONCURRENT_REQUESTS_PER_DOMAIN`: 对 `lifeofpix.com` 的最大并发请求数 [cite: 682]。
        * [cite_start]`USER_AGENT`: 爬虫使用的 User-Agent 字符串 [cite: 878]。
        * [cite_start]`LOG_LEVEL`: 日志输出级别 (例如 `INFO`, `DEBUG`) [cite: 800]。

## 使用方法

1.  打开终端或命令行工具。
2.  导航到项目的根目录 (包含 `scrapy.cfg` 文件的 `lifeofpix_scraper` 目录)。
3.  如果使用了虚拟环境，请确保已激活。
4.  运行以下命令启动爬虫：
    ```bash
    scrapy crawl lifeofpix
    ```

爬虫将开始执行，您可以观察终端输出的日志信息。爬取完成后，图片将保存在 `IMAGES_STORE` 指定的目录下，元数据将追加到 `csv_file_path` 指定的 CSV 文件中。

## 项目结构

````

lifeofpix\_scraper/
│
[cite\_start]├── scrapy.cfg            \# 项目配置文件 [cite: 1081]
│
└── lifeofpix\_scraper/    \# 项目 Python 模块
│
├── **init**.py
[cite\_start]├── items.py          \# 定义 Item 结构 [cite: 931]
[cite\_start]├── middlewares.py    \# 中间件 (本项目未使用自定义中间件) [cite: 931]
[cite\_start]├── pipelines.py      \# Item Pipelines (图片下载、CSV写入) [cite: 931, 2349]
[cite\_start]├── settings.py       \# 项目设置 [cite: 931, 613]
│
[cite\_start]└── spiders/          \# 存放 Spider 代码的目录 [cite: 932]
├── **init**.py
[cite\_start]└── lifeofpix\_spider.py \# 主要的爬虫逻辑 [cite: 1144]

```

## 注意事项

* 请遵守 `lifeofpix.com` 网站的 `robots.txt` 规则和使用条款。虽然本项目配置为不遵守 `robots.txt` (因为通常 API 不受其限制)，但请自行评估风险。
* [cite_start]过于频繁或大量的请求可能会导致您的 IP 被目标网站暂时或永久封禁 [cite: 1647]。请合理设置 `DOWNLOAD_DELAY` 和并发数。
* 如果目标网站 API 结构发生变化，爬虫代码可能需要相应调整。
* 确保配置文件中指定的所有本地文件路径都存在，并且程序具有读写权限。
```

