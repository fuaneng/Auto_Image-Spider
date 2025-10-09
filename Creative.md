# Creative Market Image Scraper
# Creative Market 高清图片信息爬虫

这是一个基于 Python 和 Selenium 的网络爬虫项目，旨在从 [Creative Market](https://creativemarket.com/) 网站上根据指定的搜索标签，自动抓取商品的高清图片链接和相关信息。

该爬虫能够处理动态加载、无限滚动和分页的复杂网页，并通过监听网络请求来精准地获取目标数据，最终将结果整理并存入 CSV 文件。

## ✨ 主要功能

- **动态抓取**: 使用 Selenium 驱动真实的 Chrome 浏览器，有效处理 JavaScript 渲染的动态内容。
- **网络监听**: 智能地捕获浏览器的网络日志（Performance Log），直接从后端 API 响应中提取数据，精准且高效。
- **智能解析**: 将捕获到的 JSON 数据解析后构建成高效的查找表，确保图片标题和其对应的高清图 `f-nw-r` 链接精确匹配。
- **自动滚动与翻页**: 模拟用户行为，自动向下滚动以加载页面上的所有商品，并自动点击“下一页”按钮，直至爬取完所有页面。
- **数据去重**: 集成 Redis 数据库，对已爬取的图片 URL 进行 MD5 哈希存储和比较，确保数据的唯一性，支持多次运行和断点续爬。
- **数据导出**: 将抓取到的标题、图片名称、高清原图URL和搜索标签等信息，统一保存到 `all_records.csv` 文件中，方便后续使用。

## ⚙️ 环境准备

在运行此爬虫之前，请确保你的系统已安装以下软件和库：

1.  **Python 3.7+**: [官方下载地址](https://www.python.org/downloads/)
2.  **Google Chrome**: 最新版本的 Chrome 浏览器。
3.  **ChromeDriver**: 版本需要与你的 Chrome 浏览器主版本号匹配。[官方下载地址](https://googlechromelabs.github.io/chrome-for-testing/)
4.  **Redis**: 一个正在运行的 Redis 服务实例。[官方安装指南](https://redis.io/docs/getting-started/installation/)

## 🚀 安装与设置

1.  **克隆或下载项目**
    将代码下载到你的本地计算机。

2.  **安装 Python 依赖库**
    打开终端或命令行，运行以下命令来安装必需的 Python 库：
    ```bash
    pip install selenium redis
    ```

3.  **配置脚本**
    打开代码文件（`.py`），根据你的本地环境修改以下几个关键路径变量：

    - **`chrome_driver_path`**: 在 `if __name__ == '__main__':` 代码块中，将其路径修改为你自己下载的 `chromedriver.exe` 文件的绝对路径。
      ```python
      # 示例
      chrome_driver_path = r'C:\path\to\your\chromedriver.exe'
      ```

    - **`save_path_all`**: 在 `main` 函数中，设置你希望保存 CSV 文件的文件夹路径。
      ```python
      # 示例
      save_path_all = r'D:\scraped_data\creativemarket'
      ```

    - **`tag_file_path`**: 在 `main` 函数中，指定包含搜索关键词的文本文件路径。
      ```python
      # 示例
      tag_file_path = r"D:\my_project\tags.txt"
      ```

4.  **准备标签文件**
    创建一个文本文件（例如 `tags.txt`），每行写入一个你想要爬取的搜索标签。例如：
    ```
    vintage font
    abstract background
    logo mockup
    ```

## 🏃‍♂️ 如何运行

完成所有配置后，只需在终端或命令行中运行 Python 脚本即可：

```bash
python your_script_name.py
```

爬虫将自动启动 Chrome 浏览器，并开始按照标签文件中的顺序逐一进行爬取。你可以在终端看到详细的运行日志和进度。

## 📜 工作流程简介

本爬虫的核心工作流程如下：

1.  **初始化**: 启动一个带有“性能日志”功能的 Selenium WebDriver 实例。
2.  **导航**: 对于标签文件中的每一个标签，构建搜索 URL 并访问。
3.  **加载数据**: 模拟用户向下滚动，直到页面上所有商品都加载出来。
4.  **捕获数据**:
    - 从页面 HTML 中提取所有商品的标题和唯一的 **Base64 路径指纹**。
    - 同时，从浏览器的网络日志中捕获包含所有图片链接的巨大 JSON 响应体。
5.  **数据匹配**:
    - 将 JSON 响应体解析为 Python 字典。
    - 遍历字典，构建一个从 **Base64 路径指纹**到**高清图 URL (`f-nw-r`)** 的映射表。
    - 使用 HTML 中提取的指纹，在该映射表中精确查找对应的 URL。
6.  **存储数据**:
    - 将匹配成功的（标题、URL、标签等）信息写入 CSV 文件。
    - 在写入前，通过 Redis 检查该 URL 是否已存在，避免重复记录。
7.  **循环**: 点击“下一页”，重复上述过程，直到爬取完该标签下的所有页面。

## 📊 输出格式

爬取的数据将被保存在你在 `save_path_all` 中指定的 `all_records.csv` 文件里。文件包含以下列：

- **Title**: 商品的原始标题。
- **ImageName**: 根据标题和 URL 的 MD5 哈希生成的唯一图片名称。
- **Original_URL**: 精确匹配到的 `f-nw-r` 高清原图链接。
- **TAG**: 该条记录来源于哪个搜索标签。