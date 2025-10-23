# Freephotos_cc/README.md
# 高效图片信息爬虫

这是一个基于 Python 的多线程爬虫项目，旨在从 `freephotos.cc` 网站高效地爬取图片信息（标题、下载直链、图片名称）并实时保存到 CSV 文件中。项目集成了多线程处理、Redis/内存去重以及断点续爬功能，确保爬取过程的高效与可靠。

## ✨ 特性

* **多线程并行处理：** 使用 `concurrent.futures.ThreadPoolExecutor`，支持配置多达 10 个线程并行处理不同的搜索标签。
* **断点续爬：** 通过记录已完成的标签（`completed_tags.txt` 文件），支持程序中断后从上次停止的地方继续爬取。
* **智能去重：** 优先使用 **Redis 集合**进行高效、持久化的图片 URL 去重；若 Redis 连接失败，自动降级为**内存去重**。
* **线程安全 CSV 写入：** 使用 `threading.Lock` 确保多线程环境下数据安全、实时地写入 CSV 文件。
* **数据提取精确：** 使用 `BeautifulSoup` 和 CSS 选择器精确提取图片标题、图片名称和原图下载直链。

## 🛠️ 技术栈

* **Python 3.x**
* **requests:** 用于 HTTP 请求。
* **beautifulsoup4:** 用于 HTML 解析。
* **concurrent.futures:** 用于多线程/进程管理。
* **redis:** 用于 URL 去重（如果配置）。
* **csv:** 用于数据存储。

## 🚀 快速开始

### 1. 环境准备

确保您的系统中已安装 Python 3.x，并通过 pip 安装所需的库：

```bash
pip install requests beautifulsoup4 redis
````

### 2\. 配置 Redis (可选)

如果希望使用 Redis 进行持久化去重，请确保您的 Redis 服务正在运行。默认配置为：

  * `REDIS_HOST = 'localhost'`
  * `REDIS_PORT = 6379`
  * `REDIS_KEY = 'freephotos_image_url_set'`

如果 Redis 连接失败，程序将自动切换为内存去重。

### 3\. 文件路径配置

在 `ImageScraper.py`（您的代码文件）中，根据您的实际情况修改以下常量：

| 常量名 | 描述 | 示例值 |
| :--- | :--- | :--- |
| `TAG_FILE_PATH` | 包含所有搜索标签的文本文件路径。**（每行一个标签）** | `D:\myproject\Code\爬虫\爬虫数据\libreshot\ram_tag_list_备份.txt` |
| `CSV_DIR` | CSV 数据文件的保存目录。 | `D:\myproject\Code\爬虫\爬虫数据\libreshot\csv_output` |
| `CSV_FILENAME` | CSV 数据文件的名称。 | `image_data.csv` |
| `TAG_PROCESS_THREADS` | 并行处理标签的线程数。 | `10` |

### 4\. 运行爬虫

直接运行主脚本：

```bash
python requests_spide_free.py
```

## 核心功能说明

### 断点续爬机制

程序会检查当前目录下是否存在 `completed_tags.txt` 文件。

  * **加载：** 启动时，加载文件中的所有标签。
  * **跳过：** 在执行 `fetch_tag_page` 时，已记录的标签会被跳过。
  * **更新：** 每次一个标签**完全**处理并保存数据后，该标签会被追加到 `completed_tags.txt` 中。

### 数据提取逻辑

数据提取严格遵循以下规则：

1.  定位到包含图片链接的 `<a>` 元素。
2.  **图片名称 (ImageName)：** 从 `href` 属性中提取路径（如 `/photo/example-1a`），移除 `/photo/` 前缀。
3.  **URL (下载直链)：** 使用前缀 `https://freephotos.cc/api/download/` 拼接 **ImageName**。
4.  **Title (图片标题)：** 提取 `<a>` 标签内 `<img>` 元素的 `alt` 属性值。

### 线程安全

为了保证数据的一致性和避免文件写入冲突，项目采用了以下锁定机制：

  * `self.csv_lock`: 保护 `write_to_csv` 方法，确保 CSV 文件写入是原子操作。
  * `self.tag_lock`: 保护内存中的去重集合 (`self.visited_names`) 和断点记录文件 (`completed_tags.txt`) 的读写。

<!-- end list -->

```
```