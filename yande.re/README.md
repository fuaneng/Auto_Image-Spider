# ![项目地址](https://github.com/fuaneng/Auto_Image-Spider)

# yande.re 图片爬虫 (yande_re_spider_v4)

本项目是一个基于 Python 和 Selenium 的高级网络爬虫，专为抓取 `yande.re` 网站图片而设计。它利用多线程并行处理多个标签页面的解析和图片下载任务，并集成了 **Redis 或内存去重**、**断点续传**、**原图检测** 等功能，以实现高效、稳定的数据采集。

## 🚀 主要特性

* **标签并行处理:** 使用 `TagWorker` 线程池同时处理多个搜索标签页。
* **内容并行解析:** 在每个标签页内，使用 `Parser` 线程池快速解析图片链接及元数据。
* **异步下载:** 使用 `Downloader` 线程池进行高速图片下载，支持断点续传。
* **去重机制:** 支持 **Redis** 或 **内存 Set** 对已处理的图片 URL MD5 进行去重，避免重复下载。
* **断点续爬:** 通过 `processed_tags.txt` 文件记录已完成处理的标签，下次运行时自动跳过，实现标签级别的断点续爬。
* **原图优先:** 尝试检测并下载更高清的 PNG 格式原图。
* **详细记录:** 将图片元数据（评分、标签、URL 等）统一记录到 CSV 文件。

## 🛠️ 环境准备

### 1. Python 环境

确保您的系统已安装 Python 3.8+。

### 2. 依赖安装

使用 `pip` 安装所需的 Python 库：

```bash
pip install selenium requests pandas redis
````

### 3\. Chrome 浏览器与驱动

本项目依赖 Chrome 浏览器和对应的 `ChromeDriver`。

1.  **安装 Chrome 浏览器**。
2.  **下载 ChromeDriver:** 确保下载的 `ChromeDriver` 版本与您的 Chrome 浏览器版本兼容。
      * 下载地址：[ChromeDriver 官方网站](https://chromedriver.chromium.org/downloads)
3.  **配置路径:** 将 `chromedriver.exe` 的路径配置到主程序 `if __name__ == '__main__':` 块中的 `chrome_driver_path` 变量。

### 4\. Redis (可选，推荐)

如果希望使用更健壮的去重机制，建议安装并运行 Redis 服务器。

  * 默认连接信息：`localhost:6379`。如果 Redis 不可用，程序将自动退化为内存去重。

## ⚙️ 使用说明

### 1\. 配置文件

在运行脚本前，请准备好以下文件：

#### A. 标签文件 (`ram_tag_周.txt`)

创建一个文本文件，每行包含一个要爬取的 `yande.re` 搜索 URL 的路径。

> **注意:** 脚本会自动将此路径前缀加上 `https://yande.re/`。

**示例 `ram_tag_周.txt` 内容:**

```text
post?tags=date%3Aday%3D1+month%3D1+year%3D2024
post?tags=date%3Aday%3D8+month%3D1+year%3D2024
post?tags=some_other_tag
```

#### B. 主程序配置

在脚本的 `if __name__ == '__main__':` 块中修改以下参数：

```python
if __name__ == '__main__':
    # 【必须修改】ChromeDriver 的绝对路径
    chrome_driver_path = r'C:\Program Files\Google\chromedriver-win64\chromedriver.exe' 
    # 【必须修改】所有输出文件（CSV、图片文件夹、进度文件）的保存根目录
    save_dir = r'R:\py\Auto_Image-Spider\yande.re\output_v4' 
    # 【必须修改】标签文件的路径
    tag_file_path = r'R:\py\Auto_Image-Spider\yande.re\ram_tag_周.txt'
    
    # 实例化爬虫并配置线程数
    spider = yande_re(
        chrome_driver_path, 
        use_headless=True,            # 是否启用无头模式 (当前代码已注释掉，可忽略此参数)
        download_workers=10,          # 【推荐配置】下载线程数
        tag_workers=3                 # 【推荐配置】标签并行处理数
    )
    
    # 启动主程序
    spider.main(
        save_dir=save_dir, 
        tag_file_path=tag_file_path, 
        enable_download=True         # 【关键】设为 True 开启下载图片，设为 False 仅解析和记录 CSV
    )
```

### 2\. 运行爬虫

```bash
python your_script_name.py
```

## 📂 输出结构

脚本运行时会在 `save_dir` 目录下创建以下结构：

```
output_v4/
├── all_records_yande_re_v4.csv    # 所有图片的元数据记录
├── processed_tags.txt             # 已成功处理完成的标签列表 (用于断点续爬)
└── images/                        # 图片保存根目录
    ├── 2024年1月1日 - 2024年1月7日（2024年第1周）/
    │   └── image_name_1.png
    │   └── image_name_2.jpg
    └── some_other_tag/
        └── image_name_3.png
```

## 💡 核心代码解析

### 类 `yande_re`

这是整个爬虫的核心类。

| 方法名 | 描述 |
| :--- | :--- |
| `__init__` | 初始化 Selenium 驱动路径、Redis 连接、线程池（下载、标签）以及配置参数。 |
| `main` | 主入口函数。负责设置目录、加载已处理标签、补全未完成下载，并启动 `tag_workers` 线程池。 |
| `process_tag` | **标签处理线程**。为每个标签独立创建一个 `WebDriver` 实例和 `Parser` 线程池，负责进入标签页并提取所有图片卡片。 |
| `process_image_card` | **解析线程**。从单个图片卡片中提取 URL、标题等信息，进行去重检查，写入 CSV，并将下载任务提交给下载线程池。 |
| `download_image` | **下载线程**。执行实际的图片下载操作，支持断点下载（`.downloading` 临时文件机制）。 |
| `is_duplicate` | 利用 Redis 或内存 Set 检查并记录图片 URL 的 MD5 哈希，实现去重。 |
| `get_hq_image_url` | 尝试将低分辨率的 JPG/JPEG URL 转换为更高清的 PNG 格式原图 URL，并通过 `requests.head` 检查原图是否存在。 |
| `parse_tag_to_week_label` | 将包含日期信息的 URL 标签转换为更友好的“年-月-日（周数）”格式作为保存文件夹名。 |
| `mark_tag_as_processed` | 将已成功处理的标签写入进度文件 (`processed_tags.txt`)，用于断点续爬。 |
| `resume_incomplete_downloads` | 读取 CSV 记录，检查图片文件是否存在或是否带有 `.downloading` 临时文件，并重新提交未完成的下载任务。 |

### 并发设计

| 线程池/模式 | 作用 | 线程数 | 目的 |
| :--- | :--- | :--- | :--- |
| `TagWorker` (标签) | 并行处理不同的搜索标签/页面。 | `tag_workers` | 加速多标签的爬取进度。 |
| `Parser` (解析) | 在单个标签页内，并行解析图片卡片，提取信息。 | `parser_workers` | 加速页面元素的提取速度。 |
| `Downloader` (下载) | 异步执行文件下载任务。 | `download_workers` | 将耗时的网络 I/O 操作与爬取解析逻辑分离。 |

```
```