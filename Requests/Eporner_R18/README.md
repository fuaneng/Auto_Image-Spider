# 📸 Eporner R18 图片爬虫与多线程下载工具

## 🚀 项目介绍

本项目是一个基于 Python 的网络爬虫，专用于根据人物标签/ID 批量抓取 Eporner 网站上的高清图片资源。项目采用解耦设计，分为数据采集和多线程下载两个主要部分，支持多人物列表处理、数据去重以及中断后的断点续传。

## ✨ 主要功能

* **批量数据采集**：从固定的 `人名.txt` 文件中读取人物标签/ID，并依次爬取其所有相册中的图片信息。
* **智能翻页**：自动处理搜索结果页的分页逻辑，直到遇到 404 状态码为止。
* **高清 URL 转换**：自动将网站返回的图片缩略图 URL 转换为完整的原始图片 URL。
* **全局去重**：在数据收集阶段，通过图片 URL 确保数据的全局唯一性。
* **数据持久化**：将所有图片元数据（图片 URL、标题、名称）统一保存到 CSV 或 XLSX 文件中。
* **多线程下载**：使用 `concurrent.futures.ThreadPoolExecutor` 实现高效率的异步下载。
* **断点续传/跳过**：下载脚本会自动检查本地文件夹，跳过已成功下载的文件，方便中断后恢复下载。

## ⚙️ 环境配置

### 1. 依赖库安装

本项目需要以下 Python 库。请使用 `pip` 进行安装：

```bash
pip install requests beautifulsoup4 lxml pandas openpyxl
````

### 2\. 项目目录结构

请在你的根路径下（例如 `R:\py\Auto_Image-Spider\Requests\Eporner_R18`）创建如下结构：

```
R:\py\Auto_Image-Spider\Requests\Eporner_R18\
├── images/                   # 图片下载存储目录
├── image_data.xlsx           # 【可选】数据保存文件（如果用 Excel 存储）
├── image_data.csv            # 【可选】数据保存文件（如果用 CSV 存储）
├── 人名.txt                  # 【必需】人物标签/ID 列表文件
├── eporner_spider.py         # 爬虫主脚本
└── image_downloader_xlsx.py  # 独立下载脚本 (读取 XLSX)
```

### 3\. 配置目标人物标签

编辑 `人名.txt` 文件，将你要爬取的每个人物标签/ID **每行输入一个**。

**示例 `人名.txt` 内容:**

```
anna-l-vWIOQsU8
anna-ralphs-5bakUFrO
#可以使用 # 符号注释不需要爬取的标签
anna-l-hegre
```

## 🏃 使用指南

### 步骤一：数据采集（运行爬虫主脚本）

运行 `eporner_spider.py` 脚本以开始抓取数据：

```bash
python eporner_spider.py
```

  * **功能：** 脚本会读取 `人名.txt`，遍历所有人物并抓取数据。
  * **输出：** 提取到的数据将写入 `image_data.csv` 文件。
  * **注意：** 爬虫脚本在抓取完数据后会立即启动多线程下载。如果下载未完成即中断，请执行 **步骤二** 恢复下载。

-----

### 步骤二：恢复下载（运行独立下载脚本）

如果你关闭了爬虫脚本，或下载被中断，你可以运行独立的下载脚本来继续任务。

> **注意：** 确保你的元数据已正确保存在 `image_data.xlsx` 文件中（如果 `image_data.csv` 乱码，你需要手动将数据复制到 `.xlsx`）。

运行 `image_downloader_xlsx.py` 脚本：

```bash
python image_downloader_xlsx.py
```

  * **功能：** 脚本将读取 `image_data.xlsx` 文件，并对其中所有未下载或下载不完整的文件进行下载。
  * **跳过机制：** 脚本会自动跳过 `images/` 文件夹中已存在的同名文件。

## 💻 脚本说明

### `eporner_spider.py` (爬虫脚本)

  * **核心逻辑**：封装了 `extract_album_links`（相册链接提取）、`process_album_page`（图片信息提取）和 `save_to_csv`（数据保存）等步骤。
  * **去重机制**：使用全局字典 `all_unique_data_dict`，以图片 URL 为键，确保数据唯一性。

### `image_downloader_xlsx.py` (下载脚本)

  * **数据源**：使用 `pandas.read_excel()` 函数从 `.xlsx` 文件中读取数据，解决了中文编码和 CSV 乱码问题。
  * **下载逻辑**：`start_download_executor` 函数使用线程池并发执行 `download_image` 任务，确保下载效率。

-----

```
```