
# 🕸️ Babesource 异步多功能爬虫 (Babesource-Spider)

本项目是一个功能强大的 Python 爬虫，专为 Babesource 网站设计，用于批量抓取指定人名标签下的所有相册信息和原始图片。该爬虫集成了 **数据收集**、**去重逻辑** 和 **解耦式异步多线程下载**，并提供了灵活的下载开关。

## ✨ 主要功能

* **相册列表抓取**：根据配置文件中的人名标签（Pornstar Tag），自动分页抓取所有相关相册的 URL。
* **图片信息提取**：访问每个相册详情页，提取所有图片的原始 URL、标题和名称。
* **数据持久化**：将提取的图片元数据（URL、标题、名称、相册名、所属集合）写入 CSV 文件。
* **高效去重**：支持 **Redis 集合** 进行持久化去重，确保图片 URL 不会重复爬取和写入；若 Redis 不可用，则自动退回使用内存集合去重。
* **异步下载**：使用 `concurrent.futures.ThreadPoolExecutor` 实现高性能、解耦式的多线程图片下载。
* **灵活控制**：提供 `download_enabled` 参数，允许用户仅收集数据到 CSV 而不启动图片下载。
* **本地目录结构**：下载图片按相册名自动创建子文件夹进行存储。

## ⚙️ 环境要求与安装

### 1. Python 环境

本项目要求使用 **Python 3.6 或更高版本**。

### 2. 依赖库安装

使用 `pip` 安装所有必需的依赖库：

```bash
pip install requests lxml beautifulsoup4 redis
````

### 3\. Redis 服务 (可选)

为了实现持久化去重，建议运行本地 Redis 服务（默认配置在 `localhost:6379`）。如果 Redis 未运行，爬虫将自动切换到内存去重。

## 🚀 配置与使用

### 1\. 文件结构和配置路径

请确保在你的本地文件系统中创建以下目录结构，并根据需要修改 `BASE_DIR` 变量。

| 路径变量 | 默认路径 (基于 `BASE_DIR`) | 说明 |
| :--- | :--- | :--- |
| `BASE_DIR` | `R:\py\Auto_Image-Spider\Requests\Babesource` | 项目根目录。**必须创建**。 |
| `TAG_FILE` | `人名tag.txt` | 存放待爬取的人名标签，每行一个。 |
| `CSV_PATH` | `all_images_data.csv` | 存储所有图片元数据的主 CSV 文件。 |
| `DOWNLOAD_DIR` | `images/` | 图片下载的根目录。 |

### 2\. 配置标签文件 (`人名tag.txt`)

在你指定的 `TAG_FILE` 路径下创建或编辑 `人名tag.txt`，每行写入一个完整的**人名标签**（如在网站 URL 中显示的名称）。

**示例 `人名tag.txt` 内容：**

```
nancy-12284
anna-l-vWIOQsU8
```

### 3\. 运行爬虫

在你的 Python 环境中运行主脚本 (`babesource_spider.py`)。爬虫提供了灵活的运行模式。

#### 模式一：仅爬取数据到 CSV (推荐先运行此模式)

设置 `download_enabled=False`，爬虫将仅收集数据并写入 `all_images_data.csv`，不会启动下载任务。

```python
# 在 if __name__ == '__main__': 块中
spider.start_crawl(download_enabled=False)
```

#### 模式二：爬取数据并同步下载图片

设置 `download_enabled=True` (默认值)，爬虫在数据收集完成后，立即启动多线程下载。

```python
# 在 if __name__ == '__main__': 块中
spider.start_crawl(download_enabled=True)
```

#### 模式三：单独启动下载任务 (基于现有 CSV 数据)

如果你已经完成了数据收集，可以随时单独调用下载方法，它将读取 CSV 文件，并使用多线程下载缺失的图片。

```python
# 在 if __name__ == '__main__': 块中
spider.start_download()
```

## 📂 下载存储结构

图片将根据 CSV 中的 `相册` 字段自动存储在 `images` 目录下的对应子文件夹中：

```
R:\py\Auto_Image-Spider\Requests\Babesource
├── 人名tag.txt
├── all_images_data.csv
└── images/
    ├── nancy-heal-fit-190563/
    │   ├── 19856.jpg
    │   └── ...
    └── another-album-title/
        └── 001.jpg
```

## ⚠️ 注意事项

  * **反爬机制**：请勿设置过高的线程数或过快的请求频率，以免被目标网站封锁 IP。
  * **SSL 警告**：由于目标网站可能存在 SSL/TLS 证书问题，爬虫使用了 `verify=False` 忽略 SSL 证书验证，代码中禁用了相关的警告。
  * **HTML 变更**：如果目标网站更新了页面结构，程序中的 CSS 选择器（如 `.main-content__card.tumba-card`）可能需要进行调整。

<!-- end list -->

