## 📸 Elitebabes 图片爬虫 (`ElitebabesSpider`)

一个基于 Python 的异步多线程爬虫，用于从 Elitebabes 网站的特定频道 (`watch-4-beauty`) 爬取相册信息、图片 URL，并将数据存储到 CSV 文件，同时支持将图片下载到本地。

该爬虫集成了 **Redis/内存去重** 机制，确保数据抓取的效率和准确性。

### 🚀 主要功能

  * **相册列表爬取：** 循环请求 API 接口，获取 `watch-4-beauty` 频道下的所有相册 URL 和标题。
  * **图片信息解析：** 访问每个相册详情页，提取最高分辨率（原图）的图片 URL、标题和文件名。
  * **智能去重：** 优先使用 Redis 进行持久化去重，如果 Redis 连接失败，则自动回退到内存去重。
  * **解耦式运行：** 支持“仅爬取数据到 CSV”和“爬取并下载图片”以及“单独启动下载”三种模式。
  * **异步高效：** 使用 Python 线程池 (`concurrent.futures`) 实现高并发解析和下载。
  * **结构化存储：** 将爬取到的图片元数据保存到结构化的 CSV 文件中。

### ⚙️ 环境配置与安装

本项目需要 Python 3.6+ 环境。

#### 1\. 安装依赖库

使用 `pip` 安装所有必需的 Python 库：

```bash
pip install requests beautifulsoup4 lxml redis urllib3 tqdm
```

#### 2\. Redis 服务（可选但推荐）

为了实现持久化的高效去重，建议启动本地 Redis 服务。如果未安装或未启动 Redis，爬虫将自动回退到内存去重。

### 📁 项目结构和文件路径

在运行之前，请根据你的系统路径，修改代码文件顶部的配置常量。

| 常量名称 | 默认值 | 描述 |
| :--- | :--- | :--- |
| `CSV_DIR_PATH` | `R:\py\Auto_Image-Spider\Requests\Elitebabes_R18` | 爬虫数据和下载图片的根目录。 |
| `CSV_FILENAME` | `all_images_data.csv` | 存储图片元数据的 CSV 文件名。 |
| `DOWNLOAD_PATH` | `.../Elitebabes_R18/images` | 最终图片下载存储的路径。 |
| `ALBUM_PARSING_THREADS` | `20` | 解析相册详情页的并发线程数。 |
| `DOWNLOAD_THREADS` | `50` | 下载图片的并发线程数。 |
| `REDIS_KEY` | `elitebabes_r18_image_url_set` | Redis 中用于存储已访问 URL 的集合名称。 |

### 💡 如何运行

该爬虫提供了灵活的运行模式，你可以在代码末尾的 `if __name__ == '__main__':` 块中，通过注释/取消注释的方式选择运行模式。

#### 1\. 仅爬取数据到 CSV

此模式将遍历所有相册页，将图片元数据写入 `all_images_data.csv`，但不执行下载任务。

```python
# --- 模式一：仅爬取数据到 CSV (download_enabled=False) ---
spider.start_crawl(download_enabled=False)
```

#### 2\. 爬取数据并立即下载

此模式将在完成数据爬取和 CSV 写入后，立即启动图片下载任务。

```python
# --- 模式二：爬取数据并下载图片 (download_enabled=True) ---
# spider.start_crawl(download_enabled=True) 
```

#### 3\. 单独启动下载任务

此模式适用于你已经有 CSV 数据，想重新或继续下载图片的情况。它会从 CSV 文件加载所有记录，并启动下载。

```python
# --- 模式三：单独启动下载任务 ---
# spider.start_download()
```

### 📋 CSV 文件字段说明

生成的 `all_images_data.csv` 文件包含以下字段：

| 字段名 | 来源 | 示例值 |
| :--- | :--- | :--- |
| **标题** | 详情页 `img` 元素的 `alt` 属性 | `Taya Sour in New Talent Taya Sour from Watch 4 Beauty` |
| **图片名称** | 从图片 URL 中提取的 ID 和名称部分（不含分辨率后缀） | `250585_0002-01` |
| **图片URL** | 经过处理，移除分辨率后缀的原图 URL | `https://cdn.../250585/0002-01.jpg` |
| **所属相册** | 相册列表页的 `title` 属性 | `Taya Sour exposes her nudes...` |
| **watch-4-beauty标签** | 固定标签 | `watch-4-beauty` |

### ⬇️ 下载目录结构

下载器会根据“所属相册”字段自动创建子文件夹，并使用“图片名称”命名文件。

```
R:\py\Auto_Image-Spider\Requests\Elitebabes_R18\
├── all_images_data.csv
└── images\
    ├── Taya Sour exposes her nudes ...\ 
    │   ├── 250585_0002-01.jpg
    │   ├── 250585_0003-01.jpg
    │   └── ...
    └── Another Album Title...\
        └── ...
```

-----

**Would you like me to generate a simple `.gitignore` file to accompany your project?**