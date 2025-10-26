# 📸 Pornpics 异步爬虫工具

这是一个基于 Python 的多功能爬虫，用于搜索特定人名标签（Tag）下的相册，解析详情页获取图片原图链接、标题等信息，并将数据存储到 CSV 文件。此外，它还提供了**解耦式异步多线程下载**功能，支持断点续传和 Redis/内存去重。

## ✨ 主要特性

* **多模式运行**: 支持“仅爬取数据”、“爬取并下载”、“单独下载”三种模式。
* **异步下载**: 使用 `concurrent.futures.ThreadPoolExecutor` 实现高效率图片下载。
* **智能去重**: 集成 **Redis 或内存去重逻辑**，避免重复爬取和下载相同的图片 URL。
* **结构化存储**: 将爬取的数据（标题、图片URL、所属相册等）存储到结构化的 CSV 文件。
* **路径管理**: 下载图片以相册名为子文件夹名，并以图片名称命名文件，保持清晰的文件结构。

## ⚙️ 环境要求

本项目基于 Python 3.x 开发。

### 依赖库

请使用以下命令安装所有必需的 Python 库：

```bash
pip install requests beautifulsoup4 redis urllib3
````

## 📂 项目结构与配置

请确保你的项目目录和配置路径与代码中设置的常量一致。

### 1\. 路径配置

请根据你的实际情况，修改 `pornpics_spider.py` 文件开头的配置常量：

| 常量名 | 路径示例 | 说明 |
| :--- | :--- | :--- |
| `TAG_FILE_PATH` | `R:\py\...\Pornpics\人名tag.txt` | 存放待爬取人名标签的文本文件路径。 |
| `CSV_DIR_PATH` | `R:\py\...\Pornpics` | CSV 文件存放的目录。 |
| `CSV_FILENAME` | `all_images_data.csv` | 最终存储爬取数据的 CSV 文件名。 |
| `DOWNLOAD_DIR_PATH` | `R:\py\...\Pornpics\images` | 图片下载的根目录。 |

### 2\. 人名 Tag 文件 (`人名tag.txt`)

该文件用于指定需要爬取的人名标签，每行一个 Tag。

**文件路径**: 必须是 `TAG_FILE_PATH` 所指定的路径。

**内容示例**:

```txt
jillian janson
anna-l-vWIOQsU8
danny-vWIOQsU8
```

> **注意**: 标签中的空格在代码中会自动替换为 `+` 进行 URL 编码。

### 3\. Redis 配置

如果需要使用 Redis 进行跨会话去重，请确保你的本地 Redis 服务器正在运行，并使用以下默认配置。如果连接失败，程序将自动回退到内存去重。

```python
REDIS_HOST = 'localhost'
REDIS_PORT = 6379
REDIS_KEY = 'pornpics_image_url_set' 
```

## ▶️ 如何运行

文件：`pornpics_spider.py`

在 `if __name__ == '__main__':` 块中，可以启用不同的运行模式。

### 模式一：仅爬取数据到 CSV（推荐）

爬取所有相册和图片信息，并将数据去重后写入 `all_images_data.csv`，不执行下载。

```python
# 示例 1: 仅爬取数据到 CSV，不下载图片
print("\n--- 模式一：仅爬取数据到 CSV (download_enabled=False) ---")
spider.start_crawl(download_enabled=False)
```

### 模式二：爬取数据并立即下载图片

爬取数据完成后，立即启动下载任务。

```python
# 示例 2: 爬取数据并下载图片 (取消下一行的注释)
print("\n--- 模式二：爬取数据并下载图片 (download_enabled=True) ---")
spider.start_crawl(download_enabled=True) 
```

### 模式三：单独启动下载任务（解耦式）

当 CSV 数据文件已经存在时，你可以单独运行下载任务，实现**下载与爬取的分离**。

```python
# 示例 3: 也可以在数据收集完成后单独启动下载任务
print("\n--- 模式三：单独启动下载任务 ---")
spider.start_download()
```

## 💾 CSV 文件字段说明

最终生成的 CSV 文件将包含以下字段：

| 字段 | 来源 | 示例 |
| :--- | :--- | :--- |
| `标题` | 图片详情页的 `img` 标签的 `alt` 属性。 | Naturally curvy teen Jillian... |
| `图片名称` | 从图片 URL 中提取的文件名（不含扩展名）。 | `70724309_001_249a` |
| `图片URL` | 图片详情页 `a` 标签的 `href` 属性（原图 URL）。 | `https://cdni.pornpics.com/.../70724309_001_249a.jpg` |
| `所属相册` | 相册列表 JSON 响应中的 `desc` 字段。 | Sharon Lee and girlfriend lick... |
| `人名Tag标签` | 从 `人名tag.txt` 文件中读取的人名 Tag。 | `jillian janson` |

## ⬇️ 下载目录结构

图片将下载到 `DOWNLOAD_DIR_PATH` 指定的根目录下，并以 `所属相册` 作为子文件夹名。

**示例结构**:

```
R:\py\Auto_Image-Spider\Requests\Pornpics\images\
├── Sharon Lee and girlfriend lick interracial lesbian pussies with tongues 14334930
│   ├── 14334930_001_a553.jpg
│   └── 14334930_002_a554.jpg
└── Naturally curvy teen Jillian Janson squats naked on the table & spreads pussy
    ├── 70724309_001_249a.jpg
    └── 70724309_002_249b.jpg
```

```
```