
# 📸 Isorepublic 图片爬虫

本项目是一个用于从 Isorepublic 网站抓取高分辨率图片信息（标题、原图 URL）的 Python 爬虫。它设计用于处理大量的搜索标签，并具备健壮的防反爬机制、数据去重和线程安全的文件存储功能。

## ✨ 主要特性

  * **多标签并发处理**: 使用线程池 (`ThreadPoolExecutor`) 并发处理多个搜索标签（如 `girl`, `plane`）。
  * **单标签串行爬取**: 每个标签内部的页面请求严格串行，以应对目标网站可能的反爬限制。
  * **智能翻页与停止**: 自动根据 URL 模板翻页，并以 **404 状态码** 作为标签爬取结束的信号。
  * **真人模拟机制**:
      * 使用全面且逼真的浏览器请求头 (`Headers`)。
      * 在每次请求间设置 **随机礼貌性延迟** (`1.0` 到 `3.0` 秒)。
      * 使用更长的请求超时时间 (`15` 秒)，避免因网络波动导致的超时错误。
  * **数据去重**: 支持 **Redis 集合** 进行持久化去重，若 Redis 不可用则自动回退到 **内存集合**。
  * **线程安全存储**: 使用 `threading.Lock` 确保并发环境下向 CSV 文件写入数据的安全性和完整性。
  * **图片 URL 清洗**: 使用通用正则表达式移除 WordPress 缩略图分辨率后缀（如 `-450x300`），获取原图 URL。

## ⚙️ 环境要求

  * Python 3.6+
  * **Redis** (可选，用于持久化去重)

### 依赖安装

使用 `pip` 安装所需的 Python 库：

```bash
pip install requests beautifulsoup4 redis
```

## 🚀 快速开始

### 1\. 配置项目参数

在脚本的顶部，根据您的实际路径和需求修改以下常量：

```python
# --- Redis 配置 ---
REDIS_HOST = 'localhost'
REDIS_PORT = 6379
REDIS_KEY = 'piqsels_image_url_set' 

# --- 文件路径配置（请根据你的实际路径修改） ---
TAG_FILE_PATH = r"D:\myproject\Code\爬虫\ram_tag_list_备份.txt" # 标签文件路径
CSV_DIR_PATH = r"D:\myproject\Code\爬虫\爬虫数据\Isorepublic"  # CSV 存储目录
CSV_FILENAME = "isorepublic_data.csv"
MAX_TAG_WORKERS = 20 # 标签处理线程数

# --- 爬虫增强配置 ---
MIN_DELAY = 1.0 # 最小等待秒数
MAX_DELAY = 3.0 # 最大等待秒数
REQUEST_TIMEOUT = 15 # 请求超时时间（秒）
```

### 2\. 准备标签文件

确保 `TAG_FILE_PATH` 所指向的文件存在，且每行包含一个您希望爬取的搜索标签。

**`ram_tag_list_备份.txt` 示例:**

```
girl
plane
nature
food
coding
...
```

### 3\. 运行爬虫

执行 Python 脚本：

```bash
python lsorepublic_requsets.py
```

爬虫将启动 20 个线程并发处理标签。每个线程会串行地请求该标签下的所有页面，并将提取到的数据实时写入指定的 CSV 文件中。

## 💾 数据输出格式

数据将实时分列存储到 `isorepublic_data.csv` 文件中，包含以下四列：

| 列名 | 说明 | 示例值 |
| :--- | :--- | :--- |
| **Title** | 图片的标题 (`alt` 属性) | Smiling Girl in Hat |
| **ImageName** | 提取出的图片文件名 (不含扩展名) | iso-republic-girl-hat-smile |
| **URL** | 清洗后的原图 URL | [可疑链接已删除] |
| **TAG** | 触发本次爬取的搜索标签 | girl |

## 核心方法解析

### `crawl_tag_pages(self, tag)`

此方法是爬虫的核心逻辑，负责单标签的串行翻页和数据提取。

  * **URL 模板**: 使用 `https://isorepublic.com/page/{page}/?s={tag}&post_type=photo_post` 构造分页链接。
  * **停止逻辑**: `if response.status_code == 404:` 语句判断爬取是否结束，确保在没有更多页面时优雅退出。
  * **反爬对策**: 包含 `time.sleep(random.uniform(MIN_DELAY, MAX_DELAY))` 实现了随机间隔，以模拟人类浏览。

### `parse_item(self, item, tag)`

负责从单个 HTML 元素中提取所需数据并进行处理。

  * **URL 清洗**: 使用 `re.sub(r'-\d+x\d+$', '', base_url)` 正则表达式通用地移除缩略图后缀，获取原图链接。
  * **去重检查**: 通过调用 `self.is_url_visited(final_url)` 确保数据不重复记录。

-----

👋 **后续步骤**

请将上述内容保存为 `README.md` 文件。如果在使用过程中遇到任何新的编程问题或需要功能扩展，请随时告诉我！