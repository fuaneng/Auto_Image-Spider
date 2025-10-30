
# 📸 V2ph 异步爬虫 (Anti-Bot)

## 简介

本项目是一个针对 `v2ph.com` 网站设计的 Python 异步爬虫。考虑到目标网站使用了 **Cloudflare 等高级反爬机制和会话验证**，本项目采用 `undetected-chromedriver` (uc) 结合手动登录的方式获取有效的会话，然后使用高效的 `requests` 库和多线程并发进行数据抓取。

本项目通过严格控制线程数量（串行访问），确保在依赖 `selenium driver` 辅助请求时避免线程安全问题，同时利用 Redis/内存进行图片 URL 去重，保障数据抓取的高效性和准确性。

## ✨ 主要特性

  * **反爬绕过**: 使用 `undetected-chromedriver` 启动浏览器，绕过 Cloudflare 等真人验证。
  * **手动登录**: 程序暂停，要求用户手动完成网站登录，获取最可靠的会话 Cookies。
  * **会话保持**: 浏览器实例在爬取过程中保持运行，确保会话 Cookies 不失效。
  * **双重请求机制**: 优先使用高效的 `requests` 库进行爬取；若因 Cookies 失效或反爬阻断，则自动回退到运行中的 `driver` 获取页面内容。
  * **多级线程池**: 采用三级线程池（标签、相册、图片），实现高效的异步任务调度。
  * **去重机制**: 支持 **Redis** 和 **内存** 两种图片 URL 去重方式。
  * **数据存储**: 实时将数据写入 CSV 文件，支持并发写入和线程安全。

## ⚙️ 环境要求

  * Python 3.6+
  * Google Chrome 浏览器 (必须安装)
  * 可选：Redis 服务器 (用于持久化去重)

## 📦 安装

### 1\. 安装 Python 依赖

使用 `pip` 安装所有必需的库：

```bash
pip install requests beautifulsoup4 redis urllib3 undetected-chromedriver selenium
```

### 2\. 配置 ChromeDriver (可选)

本项目默认依赖 `undetected-chromedriver` 自动管理驱动器。但如果自动管理失败，您可以手动配置 `CHROME_DRIVER_PATH`。

请确保您下载的 `chromedriver.exe` 版本与您安装的 Chrome 浏览器版本兼容。

## 📋 配置指南

在运行代码之前，请修改代码开头的全局常量部分，以适应您的环境和爬取需求：

```python
# main.py 文件开头部分

# !!! 浏览器驱动路径配置 !!! (若 uc 自动管理失败，请填写绝对路径)
CHROME_DRIVER_PATH = r"C:\Program Files\Google\chromedriver-win64\chromedriver.exe"

# 文件路径配置 (!!! 必须修改为您的绝对路径 !!!)
TAG_FILE_PATH = r"R:\py\Auto_Image-Spider\Requests\v2ph\tag.txt"
CSV_DIR_PATH = r"R:\py\Auto_Image-Spider\Requests\v2ph"
CSV_FILENAME = "v2ph_data.csv"

# Redis 配置 (如果不需要 Redis，无需更改，程序将自动使用内存去重)
REDIS_HOST = 'localhost'
REDIS_PORT = 6379
REDIS_KEY = 'v2ph_image_url_set' 

# 线程池配置 (重要！为避免 Selenium 冲突，标签和相册线程强制为 1)
MAX_TAG_WORKERS = 1         
MAX_ALBUM_WORKERS = 1       
MAX_IMAGE_WORKERS = 10      # 图片解析和 CSV 写入可以高并发
```

### `tag.txt` 格式要求

标签文件 (`TAG_FILE_PATH` 所指文件) 应该每行包含一个您希望爬取的标签名称（例如，演员名称或分类）。

**示例 `tag.txt`:**

```
YUNA
SAINT-Photolife
Misa
```

## 🚀 使用方法

1.  **运行程序**：

    ```bash
    python your_spider_file.py
    ```

2.  **手动登录（关键步骤）**：

      * 程序将启动一个 Chrome 浏览器窗口。
      * **在浏览器中**，请手动完成所有 Cloudflare 验证和网站登录操作。
      * **确保登录成功后，** 切换回控制台窗口。
      * 在控制台看到提示时，按 **回车键 (Enter)** 继续。

3.  **开始爬取**：

      * 程序将获取浏览器会话信息，关闭提示，并在后台启动多线程爬取。
      * 爬取过程中，浏览器窗口会保持打开状态，用于处理任何可能出现的反爬回退请求。

4.  **数据结果**：

      * 所有提取到的图片链接和元数据将实时写入您配置的 CSV 文件 (`v2ph_data.csv`) 中。

5.  **结束清理**：

      * 所有标签和相册任务完成后，程序将自动关闭浏览器实例并退出。

## ⚠️ 注意事项

  * **线程安全**: 由于依赖单个 `undetected-chromedriver` 实例，`MAX_TAG_WORKERS` 和 `MAX_ALBUM_WORKERS` 必须设置为 `1`，以确保串行访问，避免线程竞争导致程序崩溃。
  * **会话有效性**: 如果爬取过程中会话失效，程序会尝试使用 `driver` 重新加载页面，但如果跳转到登录页，爬虫将自动终止。
  * **网络要求**: 爬虫对网络连接要求较高，请确保网络稳定。
  * **路径使用**: 在 Python 字符串中，Windows 路径建议使用原始字符串 (`r"..."`) 来避免转义问题。