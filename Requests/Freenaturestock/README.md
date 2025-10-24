
# 📸 Freenaturestock 图片爬虫项目

本项目是一个基于标签、支持分页、解耦式异步多线程的 Python 爬虫，用于从 `freenaturestock.com` 网站抓取指定标签下的高清图片 URL。

## ✨ 项目目标与功能

本项目旨在高效、稳定地爬取目标网站的图片数据，具备以下核心功能：

| 功能 | 描述 | 实现细节 |
| :--- | :--- | :--- |
| **标签爬取** | 支持从本地文件读取多个搜索标签，并为每个标签独立启动爬取任务。 | 从指定路径读取标签列表。 |
| **分页处理** | 自动处理搜索结果的多页分页。 | 连续请求 `.../page/{页码}/?s={tag}` URL。 |
| **智能停止** | 识别分页结束的条件，自动停止该标签的爬取。 | 当返回 **404 状态码** 或 **未提取到新的图片链接** 时停止。 |
| **URL 过滤** | 严格限制抓取的图片来源。 | **只抓取**以 `https://freenaturestock.com/` 开头的图片 URL。 |
| **数据清洗** | 清理 URL 中的冗余信息，标准化数据。 | 使用正则表达式移除图片 URL 中的尺寸分辨率信息（如 `"-768x512"`）。 |
| **高效去重** | 确保抓取到的图片 URL 不重复。 | 优先使用 **Redis 集合**进行持久化去重，若 Redis 连接失败，则回退到 **内存集合**。 |
| **异步并发** | 采用多线程机制加速爬取过程。 | 使用 `ThreadPoolExecutor` 管理 **20 线程** 并发。 |
| **实时存储** | 将清洗后的数据安全地写入 CSV 文件。 | 使用 **追加模式 (`'a'`)** 实时写入，并通过 **线程锁** 确保多线程并发写入时的线程安全。 |

## 🛠️ 技术栈

  * **语言:** Python 3.x
  * **网络请求:** `requests`
  * **HTML 解析:** `BeautifulSoup4`
  * **并发/异步:** `concurrent.futures.ThreadPoolExecutor` (多线程)
  * **去重缓存:** `redis`
  * **文件操作:** `os`, `csv`, `threading`

## 📂 项目结构（伪代码原型）

项目基于面向对象设计（`FreenaturestockScraper` 类），将爬取逻辑、去重逻辑和存储逻辑进行封装。

```
.
├── 爬虫代码.py
├── ram_tag_list_备份.txt (标签输入文件)
└── 爬虫数据/
    └── freenaturestock/
        └── freenaturestock_images.csv (数据输出文件)
```

## ⚙️ 配置与运行

### 1\. 环境准备

请确保安装了所需的 Python 库：

```bash
pip install requests beautifulsoup4 redis
```

### 2\. Redis 配置

本项目支持 Redis 去重。如果需要使用 Redis，请确保本地或远程的 Redis 服务已启动并可通过以下常量访问：

```python
REDIS_HOST = 'localhost'
REDIS_PORT = 6379
REDIS_KEY = 'freenaturestock_image_url_set' # 用于存储已访问 URL 的集合名称
```

如果 Redis 连接失败，系统将自动回退到内存去重。

### 3\. 文件路径配置

请务必根据你的本地环境修改以下路径常量：

| 常量 | 描述 | 示例路径 (基于原型) |
| :--- | :--- | :--- |
| `TAG_FILE_PATH` | 搜索标签的文本文件路径。 | `r'D:\myproject\Code\爬虫\爬虫数据\morguefile\ram_tag_list_备份.txt'` |
| `CSV_DIR_PATH` | CSV 文件存储的目录。 | `r"D:\myproject\Code\爬虫\爬虫数据\freenaturestock"` |
| `CSV_FILENAME` | 输出的 CSV 文件名。 | `"freenaturestock_images.csv"` |

### 4\. 运行爬虫

在配置好路径后，直接运行 Python 脚本即可：

```bash
python 爬虫代码.py
```

## 核心逻辑拆解

### A. 爬取与分页 (`crawl_tag_page`)

使用循环请求分页 URL，直到遇到停止条件：

```python
# Network Doc 结构
# https://freenaturestock.com/page/{页码}/?s={tag}

while True:
    # 1. 构造分页 URL
    url = BASE_URL.format(page=page, tag=tag)
    # 2. 发送请求
    response = requests.get(url, ...)
    
    # 3. 停止条件判断
    if response.status_code == 404:
        break # 404 认为分页结束
    
    # 4. 提取和处理数据
    new_images_count = self._extract_image_urls(response.text, tag)
    if new_images_count == 0 and page > 1:
        break # 未提取到新链接也视为结束
    
    page += 1
```

### B. URL 清洗与提取 (`_clean_and_get_image_info`, `_extract_image_urls`)

1.  **提取：** 从 HTML 中查找所有 `<img>` 标签的 `src` 属性。
2.  **过滤 (新要求):** 只保留以 `https://freenaturestock.com/` 开头的 URL。
3.  **清洗：** 使用正则表达式移除分辨率信息。

<!-- end list -->

```python
def _clean_and_get_image_info(self, url):
    # 移除 "-768x512.jpg" 中的 "-768x512" 部分
    cleaned_url = re.sub(r'-\d+x\d+(\.\w+)$', r'\1', url, flags=re.IGNORECASE)
    # ... 提取图片名称
    return cleaned_url, image_name
```

### C. 数据存储 (`write_to_csv`)

数据以以下格式存储到 CSV 文件中，并严格使用线程锁保证数据完整性。

| Title | ImageName | URL | TAG |
| :--- | :--- | :--- | :--- |
| **(空)** | 从 URL 提取的文件名 | 清洗后的完整 URL | 对应的搜索标签 |

```python
def write_to_csv(self, title, name, url, csv_path, tag):
    with self.csv_lock:
        # ... 写入 [title, name, url, tag]
```