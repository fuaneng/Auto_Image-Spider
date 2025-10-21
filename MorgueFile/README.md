
# MorgueFile API 爬虫项目

本项目是一个基于 Python 的高性能异步多线程爬虫，用于通过 MorgueFile 的 API 接口抓取图片资源信息。项目集成了线程安全的 CSV 写入以及基于 Redis（或内存）的去重机制，确保数据抓取的效率和准确性。

## ⚙️ 技术栈

* **核心语言:** Python
* **网络请求:** `requests` (用于 API 调用)
* **并发模型:** `concurrent.futures.ThreadPoolExecutor` (20 线程并发)
* **数据存储:** CSV (线程安全写入)
* **去重机制:** `redis` (优先) 或 Python `set` (内存降级)
* **安全处理:** `threading.Lock` (用于 CSV 写入和内存去重)
* **HTTPS 处理:** 禁用 SSL 验证 (`verify=False`) 以解决特定环境下的证书错误。

## 🎯 爬取目标和方式

### 1. 爬取目标

* **数据源:** MorgueFile 搜索 API (`https://api.morguefile.com/api/v1/search`)
* **输入标签文件:** `D:\myproject\Code\爬虫\爬虫数据\morguefile\ram_tag_list_备份.txt`
* **爬取字段:**
    * `title` (图片标题)
    * `url_large` (图片大图 URL)
    * `tag` (搜索关键字)
* **输出文件:** `D:\myproject\Code\爬虫\爬虫数据\morguefile\morguefile_all_data.csv` (所有标签数据写入同一文件)

### 2. 核心爬取步骤与方式

1.  **标签加载:** 从本地指定文本文件加载所有搜索关键字（`tag`）。
2.  **并发任务分配:** 使用 `ThreadPoolExecutor` 启动 **20 个工作线程**。每个线程负责处理一个或多个标签的完整分页爬取任务。
3.  **API 请求与翻页:**
    * 针对每个 `tag`，从 `page=1` 开始递增请求 API URL：`https://api.morguefile.com/api/v1/search?page={页码}&relevant=true&source=search&term={tag}`。
    * **停止条件:** 如果 API 返回数据中的 `data` 列表为空，则认为没有下一页，停止当前标签的爬取。
4.  **去重处理:**
    * 在处理每条数据前，以 `url_large` 作为唯一标识进行去重检查。
    * **优先使用 Redis** 集合进行跨进程/长久去重。
    * 如果 Redis 连接失败，自动降级为使用**进程内内存集合**进行去重。
5.  **数据提取与存储:**
    * 提取 `title` 和 `url_large` 字段。
    * **线程安全写入:** 使用 `threading.Lock` 锁定 CSV 写入操作，确保在多线程并发写入到 `morguefile_all_data.csv` 时，文件结构和数据完整性不受破坏。

## 💻 代码框架 (`MorgueFileSpider` 类)

本项目围绕 `MorgueFileSpider` 类组织，主要方法职责如下：

| 方法名称 | 核心职责 | 关键实现 |
| :--- | :--- | :--- |
| `__init__` | 初始化配置和资源 | 定义文件路径，初始化 `threading.Lock`，尝试连接 **Redis** 或初始化内存去重集合 `visited_urls`。禁用 SSL 警告。 |
| `read_tags` | 加载搜索标签 | 从配置文件路径读取并清洗标签列表。 |
| `get_api_data` | 发送 API 请求 | 构造 URL，使用 `requests.get()` 发送请求，设置 `timeout`，并添加 **`verify=False`** 解决证书验证问题。 |
| `is_duplicate` | 去重检查 | 使用 **Redis SADD** 命令或内存 `set` 检查 `url_large` 是否已存在。 |
| `parse_and_write` | 解析、去重与调度写入 | 遍历 API 返回的 `data` 列表，调用 `is_duplicate` 过滤重复项，调用 `write_to_csv` 写入有效数据。包含翻页停止的判断逻辑。 |
| `write_to_csv` | 线程安全 CSV 写入 | 使用 `with self.csv_lock:` 确保排他性写入，负责检查文件头并追加数据。 |
| `crawl_tag` | 单标签爬取流程 | 控制单个 `tag` 的 `while True` 循环，实现页码递增和停止机制。 |
| `run` | 主执行入口 | 加载所有标签，创建 `ThreadPoolExecutor`，将 `crawl_tag` 任务分配给 **20 个线程**并发执行。 |

## 🚀 运行环境与启动

1.  **依赖安装:**
    ```bash
    pip install requests urllib3 redis
    ```
2.  **配置路径:** 确保 `TAG_FILE_PATH` 和 `CSV_DIR_PATH` 指向的路径正确存在。
3.  **运行 Redis (可选):** 如果要使用持久化去重，请确保本地或远程 Redis 服务器正在运行。
4.  **运行爬虫:**
    ```bash
    python your_spider_file.py
    ```
````