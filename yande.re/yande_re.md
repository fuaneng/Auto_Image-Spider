# Yande.re 高性能图片爬虫

这是一个针对 `yande.re` 网站设计的高性能、支持断点续传的 Python 图片爬虫。它能够根据预设的标签列表，自动化地抓取图片元数据、下载高质量原图，并将它们有序地存储到本地。

## 核心功能 ✨

* **高性能并发下载**：利用 `concurrent.futures.ThreadPoolExecutor` 线程池，实现多线程异步下载图片，极大地提升了下载效率，解决了单线程下载速度慢的问题。
* **断点续爬 (任务级)**：程序会自动记录已成功处理完成的页面标签 (`tag`)。当程序意外中断后重启，它会自动跳过这些已完成的标签，从上次中断的地方继续执行，避免了大量的重复抓取。
* **断点续传 (文件级)**：在下载图片前，程序会检查本地是否已存在同名文件。如果文件已存在，则跳过下载，有效避免了重复下载，并支持在下载中断后继续补充未完成的文件。
* **智能去重机制**：
    * 优先使用 **Redis** 进行高效的分布式去重，确保在多次、多任务运行时不会抓取重复的图片URL。
    * 当 Redis 服务不可用时，自动降级为使用内存中的 `set` 结构进行去重，并配备线程锁确保数据安全，保证了程序的健壮性。
* **高清原图探测**：在抓取到图片链接后，程序会尝试探测是否存在更高质量的 `.png` 格式原图，并优先下载，确保图片质量。
* **详细的元数据提取**：自动解析并抓取每张图片的详细信息，包括：`Rating`(评级), `Score`(分数), `Tags`(标签), `User`(上传者), 并将这些信息与图片URL一同保存到 CSV 文件中。
* **自动分类存储**：下载的图片会根据其所属的“周标签”（例如 `2025年第1周`）自动创建并归入相应的子文件夹中，使文件管理清晰有序。

## 技术栈 🛠️

* **Python 3.10** 及以上版本
* **Selenium**: 用于浏览器自动化，模拟用户操作以加载动态内容。
* **Requests**: 用于执行高效、稳定的文件下载和网络请求。
* **Redis**: (推荐) 用于实现高性能、持久化的URL去重。
* **Concurrent Futures**: 用于实现多线程并发下载。
* **BeautifulSoup**: 用于解析 HTML 内容，提取所需数据。
* **Logging**: 用于记录程序运行状态和调试信息。

## 安装与配置指南 ⚙️

在运行此脚本之前，请确保你的环境已正确配置。

### 1. 安装 Python 库

打开你的终端或命令行，运行以下命令来安装所有必需的 Python 库：

```bash
pip install selenium requests redis
```

### 2. 安装 WebDriver

此脚本使用 Selenium 来驱动 Chrome 浏览器。

* **下载 ChromeDriver**: 你需要下载与你的 **Chrome 浏览器版本完全匹配** 的 `chromedriver.exe`。
    * 官方下载地址: [Chrome for Testing availability](https://googlechromelabs.github.io/chrome-for-testing/)
* **获取路径**: 将下载的 `chromedriver.exe` 放置在一个稳定的目录中，并复制其完整路径。

### 3. 安装 Redis (可选，但强烈推荐)

为了获得最佳的去重性能和持久化记录，建议安装并运行 Redis。

* 访问 [Redis 官网](https://redis.io/docs/getting-started/installation/) 根据你的操作系统进行安装。
* 确保在运行脚本前，Redis 服务已经启动。如果不安装，脚本会自动使用内存进行去重，但在程序关闭后去重记录会丢失。

### 4. 配置脚本

打开脚本文件 (例如 `spider.py`)，找到文件底部的 `if __name__ == '__main__':` 部分，根据你的实际情况修改以下路径和参数：

```python
if __name__ == '__main__':
    # 1. ChromeDriver 的绝对路径
    chrome_driver_path = r'C:\Program Files\Google\chromedriver-win64\chromedriver.exe'
    
    # 2. 数据和图片保存的主目录
    save_dir = r'R:\py\Auto_Image-Spider\yande.re\output_v4'
    
    # 3. 包含待爬取标签的文本文件路径
    tag_file_path = r'R:\py\Auto_Image-Spider\yande.re\ram_tag_周.txt'

    # (可选) 调整下载线程数，默认为 10
    # 数字越大下载越快，但对网络和CPU负担也越大，建议范围 5-20
    spider = yande_re(chrome_driver_path, use_headless=True, max_workers=15) 
    
    # ...
```

## 如何运行 🚀

1.  **准备标签文件**:
    确保在 `tag_file_path` 指定的路径下存在一个 `.txt` 文件 (例如 `ram_tag_周.txt`)。文件内容应为需要爬取的URL标签，每行一个。例如：
    ```
    post?tags=date%3A2024-12-30..2025-01-05
    post?tags=date%3A2024-12-23..2024-12-29
    ...
    ```

2.  **执行脚本**:
    在完成所有配置后，打开终端，进入脚本所在目录，并运行：
    ```bash
    python your_script_name.py
    ```

脚本启动后，你将在控制台看到详细的日志输出，包括 Redis 连接状态、任务加载情况、页面解析进度和文件下载状态。

## 输出文件结构 📁

所有生成的文件都会保存在你配置的 `save_dir` 目录下：

```
R:\py\Auto_Image-Spider\yande.re\output_v4\
│
├── all_records_yande_re_v4.csv     # 存储所有图片元数据的CSV文件
│
├── processed_tags.txt              # 记录已处理完成的标签，用于断点续爬
│
└── images/                         # 存放所有下载图片的主文件夹
    │
    ├── 2025年第1周.../             # 根据周标签自动创建的子文件夹
    │   ├── yande.re_12345.jpg
    │   └── yande.re_67890.png
    │
    └── 2024年第52周.../
        ├── yande.re_54321.jpg
        └── ...
```

---