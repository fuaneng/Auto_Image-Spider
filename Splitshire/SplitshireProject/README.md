# Splitshire 图片采集爬虫 (SplitshireProject)

## 🎯 项目目的 (Purpose)

本项目基于 **Scrapy 框架**开发，用于从 [Splitshire](https://www.splitshire.com/) 网站批量采集指定标签下的图片信息（包括标题、原图链接和文件名），并将采集结果整理并写入本地 CSV 文件中。

## ✨ 核心功能 (Features)

  * **标签驱动**: 从本地文本文件 (`ram_tag_list.txt`) 读取搜索关键词，自动构建起始请求。
  * **图片解析**: 准确识别并提取延迟加载 (Lazy Loading) 模式下的图片 URL（优先 `data-src` 属性）。
  * **URL 转换**: 将缩略图 URL 中的 `/thumbnail/` 替换为 `/full/`，获取原图链接。
  * **数据持久化**: 使用自定义 Item Pipeline 将采集到的数据（标题、文件名、URL、标签）写入指定的 CSV 文件。

## 🛠️ 环境与安装 (Setup and Installation)

### 1\. 软件要求 (Prerequisites)

  * Python 3.6+
  * Scrapy
  * Twisted (如果遇到兼容性问题，请参考下方配置)

### 2\. 安装依赖 (Dependencies)

在您的 Python 环境中，安装 Scrapy 和其他相关依赖：

```bash
pip install scrapy
```

### 3\. 项目初始化 (Project Structure)

在您的项目根目录 (`SplitshireProject`) 中，确保存在以下关键文件和文件夹：

```
SplitshireProject/
├── scrapy.cfg
└── SplitshireProject/
    ├── __init__.py
    ├── items.py
    ├── pipelines.py
    ├── settings.py
    └── spiders/
        ├── __init__.py
        └── splitshire.py  <-- 核心爬虫代码
```

## ⚙️ 配置说明 (Configuration)

### 1\. 标签文件配置

您需要创建并配置一个文本文件，用于存放搜索标签，每行一个标签：

  * **路径**: `D:\work\爬虫\ram_tag_list.txt`
  * **内容示例**:
    ```text
    cat
    forest
    travel
    minimal
    ```

### 2\. 输出路径配置 (`settings.py`)

在 `SplitshireProject/SplitshireProject/settings.py` 中，配置 CSV 文件的输出目录：

```python
# 自定义 CSV 写入路径
CUSTOM_CSV_PATH = r"D:\work\爬虫\plausible"
```

### 3\. 爬虫核心配置 (`settings.py`)

为解决 Windows 下的 Twisted 兼容性问题，以及启用自定义的 Pipeline，请确保 `settings.py` 中包含以下配置：

```python
# 解决 Windows 下的 Twisted Reactor 错误
TWISTED_REACTOR = 'twisted.internet.selectreactor.SelectReactor' 

# 启用并设置 Item Pipeline 的优先级
ITEM_PIPELINES = {
    'SplitshireProject.pipelines.SplitshireCsvPipeline': 300,
}

# 建议的爬取策略（可根据网络条件调整）
DOWNLOAD_DELAY = 1 
CONCURRENT_REQUESTS = 16
```

## ▶️ 运行项目 (Running the Spider)

请在包含 `scrapy.cfg` 文件的 **项目根目录** (`SplitshireProject/`) 下执行以下命令。

### 1\. 启动爬虫 (Run Command)

使用 `scrapy crawl` 命令启动爬虫：

```bash
scrapy crawl splitshire
```

### 2\. 详细调试 (Debug Mode)

如果需要查看详细的请求、响应和 Item 写入日志，可以使用 `DEBUG` 级别：

```bash
scrapy crawl splitshire -L DEBUG
```

## 📤 结果输出 (Output)

爬虫运行完成后，采集到的数据将写入到您指定的目录下：

  * **文件路径**: `D:\work\爬虫\plausible\splitshire_items.csv`
  * **文件内容字段**: `Title`, `ImageName`, `URL`, `TAG`

## 🤝 调试辅助 (Troubleshooting)

如果您在运行时遇到 `KeyError: 'Spider not found: splitshire'` 或其他项目加载问题，请首先：

1.  **检查目录**: 确保您在包含 `scrapy.cfg` 的目录下运行命令。
2.  **检查名称**: 确保 `splitshire.py` 中的 `name = 'splitshire'` 完全匹配。
3.  **检查配置**: 确保 `settings.py` 中的 `SPIDER_MODULES` 配置正确指向您的 `spiders` 目录。

https://wimg.rule34.xxx/samples/666/sample_589928a77567ded3fe6399b87492b866.jpg?15150444
https://wimg.rule34.xxx/samples/666/sample_589928a77567ded3fe6399b87492b866.jpg?15150444
"https://s3t3d2y9.afcdn.net/library/896850/3afb58b852c417ae6f6bf02b7608b3f00d44fe1e.jpg
"image": "https:\/\/s3t3d2y9.afcdn.net\/library\/896850\/3afb58b852c417ae6f6bf02b7608b3f00d44fe1e.jpg",