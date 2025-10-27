
# 📸 Piqsels 单线程爬虫 (Selenium + Undetected-Chromedriver)

本项目是一个针对 `piqsels.com` 网站设计的单线程爬虫。由于目标网站采用了 Cloudflare 等先进的反爬机制，本项目使用 **Selenium** 配合 **`undetected-chromedriver`** 来模拟真实用户行为，实现稳定、低速、串行的内容抓取。

为了提高爬虫的稳定性和抗识别能力，所有请求都在同一个浏览器实例中进行，并集成了随机延迟和重试机制。

## ✨ 特性

* **反爬绕过**：使用 `undetected-chromedriver`，有效绕过常见的 Selenium 检测。
* **串行稳定**：采用单线程串行模式，最大限度地模拟人类浏览行为，降低 Cloudflare 触发真人验证的几率。
* **手动验证支持**：为 Cloudflare 人工验证预留了充足的等待时间（60 秒），一旦验证通过即可继续。
* **效率优化**：集成 `"No results"` 快速跳过和重试逻辑。
* **持久化去重**：支持使用 **Redis** 或本地内存对已抓取的图片 URL 进行去重。
* **数据输出**：将抓取到的图片信息（标题、名称、URL、标签）保存到 CSV 文件。

## ⚙️ 环境设置

### 1. 依赖安装

确保您的 Python 环境中安装了所有必要的库：

```bash
pip install selenium undetected-chromedriver beautifulsoup4 requests redis urllib3
````

### 2\. Chrome 浏览器和驱动

由于使用了 `undetected-chromedriver` (uc)，它通常会自动管理 Chrome 驱动。但为了稳定性和精确控制，您需要：

  * **安装 Google Chrome 浏览器。**
  * **设置 `CUSTOM_DRIVER_PATH`**：如果您需要指定本地的驱动路径，请确保该路径正确。

## 🚀 项目配置

在运行脚本之前，请根据您的环境修改以下配置常量：

### `piqsels_crawler.py` 文件头部

| 常量名称 | 描述 | 示例值 |
| :--- | :--- | :--- |
| `CUSTOM_DRIVER_PATH` | **【必需】** 您本地 `chromedriver.exe` 的完整路径。 | `r"D:\myproject\chromedriver-win64\chromedriver.exe"` |
| `TAG_FILE_PATH` | **【必需】** 包含待爬取关键词（每行一个）的文本文件路径。 | `r"D:\myproject\Code\爬虫数据\piqsels\ram_tag_list_备份.txt"` |
| `CSV_DIR_PATH` | 抓取结果 CSV 文件的输出目录。 | `r"D:\myproject\Code\爬虫数据\piqsels"` |
| `CSV_FILENAME` | 结果 CSV 文件的文件名。 | `"piqsels_data.csv"` |

### Redis 配置 (可选)

如果希望使用 Redis 进行持久化去重，请确保您的 Redis 服务已启动。如果连接失败，程序会自动退回到内存去重。

| 常量名称 | 描述 |
| :--- | :--- |
| `REDIS_HOST` | Redis 服务器地址。 |
| `REDIS_PORT` | Redis 服务器端口。 |
| `REDIS_KEY` | 用于存储已访问 URL 的 Redis 集合键名。 |

## ▶️ 运行指南

1.  **准备标签文件**：确保 `TAG_FILE_PATH` 指向的文件中包含了您想要搜索的所有关键词，每个关键词占一行。

2.  **首次启动**：运行主脚本。

    ```bash
    python piqsels_crawler.py
    ```

3.  **处理 Cloudflare 验证**：

      * 脚本启动时，Chrome 浏览器窗口会弹出。
      * 如果出现 Cloudflare 的 **"Just a moment"** 页面或 **人机验证（CAPTCHA）**，请在 60 秒内手动完成验证操作。
      * 一旦验证通过，浏览器将跳转到搜索结果页，脚本将自动开始抓取。

4.  **抓取过程**：

      * 脚本会逐个标签、逐页串行地进行爬取。
      * 标签或页面之间会有 **3 到 8 秒的随机延迟**，以模拟人类行为，请耐心等待。
      * 如果 Cloudflare 在抓取过程中再次触发验证，程序会超时重试，并提示您手动处理浏览器窗口。

5.  **完成**：所有标签爬取完毕后，浏览器窗口将自动关闭，并在指定路径生成包含所有数据的 CSV 文件。

-----

**注意**：由于目标网站的反爬策略随时可能更新，如果程序在运行时遇到长时间卡顿或多次触发人工验证，可能需要更新 `undetected-chromedriver` 版本或调整代码中的等待时间。

```
```