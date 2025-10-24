

[![Python](https://img.shields.io/badge/Python-3.6%2B-blue.svg)](https://www.python.org/)
[![Selenium](https://img.shields.io/badge/Selenium-4.0%2B-green.svg)](https://www.selenium.dev/)
[![Redis](https://img.shields.io/badge/Redis-3.0%2B-red.svg)](https://redis.io/)
[![License](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Unsplash](https://img.shields.io/badge/Unsplash-Image%20Spider-yellow.svg)](https://unsplash.com/)
![Unsplash 多线程图片爬虫](https://github.com/fuaneng/Auto_Image-Spider/Unsplash/unsplash_com.png)

# 📸 Unsplash 多线程图片爬虫 (Unsplash-Concurrent-Spider.py)

本项目是一个基于 Python 和 Selenium 的高性能多线程爬虫，专为从 Unsplash 网站异步抓取大量图片链接和元数据而设计。通过使用多线程和信号量机制，它可以同时处理多个搜索标签，大大提高了数据采集效率。

## ✨ 特性

  * **多线程并发：** 默认支持 **5 个** 独立的浏览器实例（可配置），异步处理不同的搜索任务，互不干扰。
  * **健壮性高：** 内置了针对 Selenium 常见的 `StaleElementReferenceException` (元素失效) 错误的重试机制。
  * **无限滚动处理：** 自动模拟用户滚动，并具备识别内容加载完毕或到达最大滚动次数的智能停止机制。
  * **去重机制：** 默认支持 **Redis** 进行跨任务 URL 去重，若 Redis 连接失败，自动降级为内存去重。
  * **无头模式：** 支持在后台运行浏览器（`headless` 模式），节省系统资源。

## ⚙️ 环境要求

在运行本项目之前，请确保你的系统满足以下要求：

1.  **操作系统：** Windows, macOS, 或 Linux。
2.  **Python 版本：** Python 3.6 及以上。
3.  **浏览器：** 推荐使用 Google Chrome。
4.  **ChromeDriver：** 与你的 Chrome 浏览器版本兼容的 ChromeDriver 可执行文件。
      * **获取方法：** 你可以在 [ChromeDriver 官网](https://sites.google.com/chromium.org/driver/) 下载与你 Chrome 浏览器版本对应的驱动。

### 📦 安装依赖库

本项目需要 `selenium` 和 `redis` 库。请在你的命令行或终端中运行以下命令安装：

```bash
pip install selenium redis
```

-----

## 🚀 快速开始（初学者指南）

### 步骤一：放置文件和设置标签列表

1.  **创建项目文件夹：**
    在你的电脑上创建一个文件夹，例如 `unsplash_spider`。

2.  **创建标签文件：**
    在你的数据保存目录下（例如：`D:\work\爬虫\爬虫数据\unsplash`），创建一个名为 `ram_tag_list_备份.txt` 的文本文件。
    在这个文件中，每行输入一个你想爬取的搜索关键词或标签。

    **`ram_tag_list_备份.txt` 示例：**

    ```
    nature photography
    minimalist wallpaper
    city light
    monastery
    ocean waves
    ...
    ```

3.  **配置 ChromeDriver 路径：**
    确保你已经下载了 `chromedriver.exe` 并知道它的完整路径（例如：`C:\path\to\chromedriver.exe`）。

### 步骤二：修改配置参数

打开你的 Python 爬虫文件，找到 `if __name__ == '__main__':` 下方的 **配置部分**，根据你的实际情况进行修改。

```python
if __name__ == '__main__':
    # ⚠️ 配置部分：请修改为你自己的路径和设置
    chrome_driver_path = r'C:\Program Files\Google\chromedriver-win32\chromedriver.exe'  # <--- 【必改】ChromeDriver 路径
    save_dir = r'D:\work\爬虫\爬虫数据\unsplash'                                         # <--- 【必改】数据保存的根目录
    tag_file_path = r'D:\work\爬虫\爬虫数据\unsplash\ram_tag_list_备份.txt'               # <--- 【必改】标签文件路径
    csv_name = 'all_records_unsplash.csv'                                         # 最终输出的 CSV 文件名
    use_headless = True                                                           # 是否启用无头模式 (True: 后台运行; False: 显示浏览器窗口)
    
    # 🚀 并发控制设置
    MAX_THREADS = DEFAULT_MAX_THREADS  # 默认设置为 5 个并发线程 (即同时打开 5 个浏览器)
    # ... (其他代码)
```

### 步骤三：运行爬虫

在命令行或终端中，导航到你的 Python 文件所在目录，并运行脚本：

```bash
python your_spider_file_name.py
```

程序将开始运行，你会看到最多 5 个浏览器实例（如果 `use_headless` 为 `False`）被启动，并开始并行处理你的标签列表。

-----

## 🛠️ 高级配置 (可选)

### 1\. 调整并发线程数

如果你希望同时运行更多或更少的浏览器实例，可以修改 `MAX_THREADS` 参数。

```python
    # 🚀 并发控制设置
    MAX_THREADS = 10  # 例如，设置为 10 个线程，取决于你的计算机性能
    semaphore = threading.Semaphore(MAX_THREADS)
```

### 2\. 调整滚动策略

这些参数位于文件的最上方，用于控制爬虫在无限滚动页面上的行为：

| 参数 | 默认值 | 建议用途 |
| :--- | :--- | :--- |
| `MAX_SCROLLS` | `100` | 网站图片量极大时，可以调高（例如 `200`），否则保持默认即可。 |
| `NO_NEW_ROUNDS_TO_STOP` | `2` | 保持默认或调高到 `3`。此值越小，爬虫越早判断页面到底，可能牺牲一点完整性但提高效率。 |
| `SMALL_SCROLL_AMOUNT` | `200` | 用于微调滚动，一般不需改动。|

### 3\. Redis 去重

如果你的本地安装了 Redis 服务（默认端口 6379），代码将自动启用 Redis 进行去重。

  * 如果不需要 Redis，可以将 `run_spider_task` 函数中传入的 Redis 参数设置为任意不正确的值，例如：
    ```python
    # args=(tag, ..., 'wrong_host', 9999, semaphore)
    ```
    爬虫将自动识别连接失败，并降级为使用内存（`visited_md5` 集合）进行去重。

## ⚠️ 常见问题与解决方案

| 问题 | 原因 | 解决方案 |
| :--- | :--- | :--- |
| `FileNotFoundError: ChromeDriver not found at path: ...` | `chrome_driver_path` 设置不正确。 | 检查并修正 `chrome_driver_path` 变量中的路径。 |
| `selenium.common.exceptions.SessionNotCreatedException` | ChromeDriver 版本与 Chrome 浏览器版本不兼容。| 下载与你 Chrome 浏览器版本完全匹配的 ChromeDriver。 |
| 爬取中出现 `StaleElementReferenceException` | 页面 DOM 结构快速变化。| **已解决。** 代码中已内置重试机制 (`get_images` 函数中的 `max_retries = 2`) 来处理此问题。 |
| 爬虫运行速度慢，电脑卡顿 | 并发线程数 (`MAX_THREADS`) 过高。| 调低 `MAX_THREADS`，例如设置为 `3` 或 `4`，以减轻 CPU 和内存压力。|
| 爬虫提前结束，图片不完整 | `NO_NEW_ROUNDS_TO_STOP` 设置过低。| 适当调高 `NO_NEW_ROUNDS_TO_STOP` (例如到 `3`) 或 `MAX_SCROLLS`。 |