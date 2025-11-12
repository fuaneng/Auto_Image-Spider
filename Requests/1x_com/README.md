
## 🖼️ 1x.com 获奖艺术图片爬虫

### 介绍

这是一个高效的 Python 爬虫项目，用于从艺术摄影社区 1x.com 的特定分类页面（Fine Art Nude / Awarded）爬取高质量图片及其元数据。项目设计了反反爬机制，并采用串行请求获取数据和多线程下载图片，以确保数据完整性和下载效率。

### ✨ 主要功能

  * **动态内容抓取：** 模拟浏览器滚动，处理网站的 AJAX/XHR 请求动态加载下一页数据。
  * **累积式翻页：** 精准模拟网站的 `alreadyloaded` 累积式翻页逻辑，确保不遗漏任何图片。
  * **按需停止：** 自动判断页面末尾，在无新图片数据返回时停止爬取。
  * **数据结构化存储：** 将图片 URL、作者名和年份等信息结构化存储到 CSV 文件。
  * **多线程高速下载：** 使用 `ThreadPoolExecutor` 并发下载图片，大大缩短下载时间。
  * **反爬优化：** 在爬取和下载过程中，使用了 `User-Agent`、`Referer` 和会话管理等技术，提高请求隐秘性。

### ⚙️ 环境与依赖

本项目基于 Python 3.x 开发，需要安装以下库：

| 库名 | 作用 |
| :--- | :--- |
| `requests` | 用于发送 HTTP 请求 |
| `beautifulsoup4` | 用于解析 HTML 和提取数据 |
| `pandas` | 用于数据处理和 CSV 文件的读写 |
| `concurrent.futures` | 用于多线程并发下载 |

#### 安装

```bash
pip install requests beautifulsoup4 pandas
```

### 🚀 如何使用

#### 1\. 配置路径

在你的爬虫代码和下载脚本中，请确保以下路径配置正确：

| 变量名 | 值 | 描述 |
| :--- | :--- | :--- |
| `CSV_PATH` | `R:\py\Auto_Image-Spider\Requests\1x_com\1x_com_awarded.csv` | 数据存储路径 |
| `DOWNLOAD_DIR` | `R:\py\Auto_Image-Spider\Requests\1x_com\images` | 图片下载路径 |

#### 2\. 运行数据爬取脚本 (获取 CSV 文件)

运行你的主爬虫脚本。它将自动：

1.  发送请求获取图片数据。
2.  循环翻页，直到没有新数据。
3.  将 **图片地址、作者名、年份** 写入到 `1x_com_awarded.csv` 文件中。

由于网站的翻页逻辑（`alreadyloaded` 参数的累积性），此步骤必须**串行**执行，以保证数据的完整性。

#### 3\. 运行多线程下载脚本 (下载图片)

运行你的多线程下载脚本。它将自动：

1.  读取上一步生成的 CSV 文件。
2.  使用最多 **6 个线程** 并发下载图片。
3.  自动跳过已经存在的图片。
4.  将图片保存到 `R:\py\Auto_Image-Spider\Requests\1x_com\images` 目录。

### 核心代码逻辑简析

#### 数据爬取 (`main_scraper`)

请求地址：`https://1x.com/backend/lm2.php?style=normal&mode=latest:12:awarded&from={N}&...`

  * **翻页机制：** 循环内，`from` 参数每次递增 **20**。
  * **反爬处理：** 成功的请求会返回一个包含新 HTML 片段的响应。我们解析这个片段，并提取所有图片的 ID (`id="imgcontainer-ID"`)。
  * **`alreadyloaded` 构造：** 提取出的所有历史图片 ID 会被累积起来，并在下一个请求中拼接到 `alreadyloaded` 参数，格式为 `":id1:id2:..."`，这是模仿浏览器行为的关键。
  * **停止条件：** 如果成功获取响应，但解析出的 `photos_data` 列表为空，则程序自动退出循环。

#### 图片下载 (`main_downloader_threaded`)

  * **多线程：** 使用 `concurrent.futures.ThreadPoolExecutor` 管理 **6** 个工作线程，实现 I/O 密集型任务（下载）的并发执行。
  * **隐秘性：** 每个下载请求都包含关键的 `Referer` 头（设置为 `https://1x.com/`），这对于绕过图片服务器的防盗链机制至关重要。
  * **会话管理：** 在每个线程内部使用 `requests.Session()`，保持连接活性，提高效率。

-----

### 鸣谢

感谢 1x.com 提供了如此精美的艺术作品。本项目仅用于学习和技术交流，请勿用于商业用途。