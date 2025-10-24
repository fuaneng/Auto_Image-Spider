
# Libreshot 高效图片爬虫

这是一个用于从 Libreshot 网站高效爬取图片信息（标题、原图 URL）的 Python 爬虫项目。项目采用了多线程并发处理、集成 Redis/内存去重机制，并支持将多词搜索标签进行正确的 URL 编码。

## ✨ 主要功能

* **多线程并发：** 使用 `concurrent.futures.ThreadPoolExecutor` 实现多标签并发爬取，效率高。
* **智能去重：** 集成 Redis 集合作为首选去重方案，若 Redis 连接失败则自动回退到进程内内存去重，确保数据不重复。
* **URL 编码处理：** 自动将多词标签中的空格替换为 `+` 号，以构造正确的搜索 URL。
* **数据清洗：** 自动去除图片缩略图 URL 中的分辨率参数（如 `-508x339`），以获取原图的 URL。
* **线程安全写入：** 使用线程锁 (`threading.Lock`) 保证多线程环境下 CSV 文件的写入是安全且原子性的。
* **实时存储：** 将爬取到的数据（标题、图片名称、原图 URL、标签）实时保存到 CSV 文件中。

## 🛠️ 环境要求

在运行此项目之前，请确保你的环境满足以下要求：

1.  **Python 3.x**
2.  **Redis 服务**（可选，用于跨会话去重）
3.  **Python 依赖库：**
    ```bash
    pip install requests lxml redis urllib3
    ```

## ⚙️ 文件配置

在运行爬虫之前，你需要配置以下两个关键路径：

### 1. 标签列表文件

爬虫会从该文件中读取待搜索的所有标签。

* **路径配置：**
    ```python
    TAG_FILE_PATH = r"D:\myproject\Code\爬虫\爬虫数据\libreshot\ram_tag_list_备份.txt"
    ```
* **格式要求：** 文件中每行一个搜索标签。

### 2. CSV 输出目录

爬取结果 CSV 文件的存放位置。

* **路径配置：**
    ```python
    CSV_DIR_PATH = r"D:\myproject\Code\爬虫\爬虫数据\libreshot\results"
    CSV_FILENAME = "libreshot_images.csv"
    ```

### 3. Redis 配置 (可选)

如果你选择使用 Redis 进行去重，请确保 Redis 服务运行正常，并检查以下配置：

```python
REDIS_HOST = 'localhost'
REDIS_PORT = 6379
REDIS_KEY = 'libreshot_image_url_set' 
````

## ▶️ 如何运行

1.  **保存代码：** 将爬虫代码保存为 Python 文件（例如 `scraper.py`）。

2.  **准备标签：** 确保标签列表文件已准备好并位于指定路径。

3.  **执行文件：** 在终端中运行：

    ```bash
    requests_spide_libreshot.py
    ```

4.  **查看结果：** 程序运行完成后，爬取到的数据将保存在指定的 CSV 文件中。

## 💡 爬虫逻辑详解

### 爬取流程

1.  **加载任务：** 从本地文件加载所有标签。
2.  **创建线程池：** 启动一个包含 **10 个工作线程**的线程池。
3.  **并发请求：** 每个线程接收一个标签任务，执行以下操作：
      * 将标签（如 "building material"）转换为 URL 编码格式（`building+material`）。
      * 构造完整的搜索 URL，并发送 `GET` 请求。
4.  **解析数据：** 使用 `lxml` 库和 XPath 表达式，从 HTML 响应中定位图片数据块。
5.  **数据处理：**
      * 提取图片的 `data-src` 作为原始 URL。
      * 清理 URL，移除分辨率后缀，获取原图 URL 和图片名称。
6.  **去重检查：** 将清理后的原图 URL 提交给 Redis 或内存集合进行检查。
7.  **保存数据：** 如果 URL 是新的（未被爬取过），则通过线程锁安全地将 `[Title, ImageName, URL, TAG]` 写入 CSV 文件。

### 字段提取规则

| 字段 | 来源 | 清洗/处理 |
| :--- | :--- | :--- |
| **标题 (Title)** | 包含图片的 `<a>` 标签的 `title` 属性。 | 直接提取。 |
| **图片 URL (URL)** | `<img>` 标签的 `data-src` 属性。 | **去除** URL 中类似 `-508x339` 的分辨率后缀。 |
| **图片名称 (ImageName)**| 从清理后的图片 URL 中提取不含扩展名的文件名。 | `URL.split('/')[-1].split('.')[0]` |
| **标签 (TAG)** | 当前请求所使用的搜索标签。 | 直接使用。 |

```
```