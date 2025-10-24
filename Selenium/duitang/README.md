# 堆糖图片爬虫 (Duitang Image Spider)

[![Python](https://img.shields.io/badge/Python-3.6%2B-blue.svg)](https://www.python.org/)
[![Selenium](https://img.shields.io/badge/Selenium-4.0%2B-green.svg)](https://www.selenium.dev/)
[![Redis](https://img.shields.io/badge/Redis-3.0%2B-red.svg)](https://redis.io/)
[![License](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

## 💻 图片爬虫 (Duitang Image Spider)

本项目是一个基于 **Selenium** 的 Python 爬虫，用于根据标签（Tag）搜索并抓取堆糖（Duitang）网站上的图片信息（标题和原始图片 URL）。

爬虫具备**自动滚动加载**、**数据去重**和**CSV 存储**等功能。

### 🛠️ 技术栈

  * **语言**: Python 3.x
  * **核心库**: `selenium`, `redis`, `re`, `csv`
  * **浏览器驱动**: Chrome / ChromeDriver

### 🚀 功能特点

1.  **标签驱动**: 从指定的本地文件读取搜索标签列表。
2.  **动态加载**: 自动滚动页面以加载所有图片，应对无限滚动机制。
3.  **URL 清理**: 智能解析并还原图片的原始 URL，自动去除缩略图参数（如 `.thumb.xxx`）和格式后缀（如 `_webp`）。
4.  **数据去重**: 使用 **Redis 数据库** 存储已爬取图片的 MD5 哈希值，确保数据唯一性。
5.  **并发安全**: 使用 `threading.Lock` 确保多线程或并发写入 CSV 文件时的安全。
6.  **结果存储**: 将结果写入统一的 `all_records.csv` 文件。

-----

### ⚙️ 环境设置与依赖安装

#### 1\. Python 环境

请确保您已安装 Python 3.6 或更高版本。

#### 2\. 安装 Python 依赖库

使用 pip 安装项目所需的所有依赖：

```bash
pip install selenium redis
```

#### 3\. 设置 Chrome 驱动

本项目依赖于 Chrome 浏览器和对应的 **ChromeDriver**。

1.  请根据您本地 Chrome 浏览器的版本，下载对应的 **ChromeDriver**。
2.  将 ChromeDriver 可执行文件（如 `chromedriver.exe`）放置到您指定的路径。
3.  请在代码的 `if __name__ == '__main__':` 部分更新 `chrome_driver_path` 变量。

#### 4\. Redis 配置

爬虫使用 Redis 进行去重。请确保您的本地或远程服务器上运行着 Redis 实例。

  * 默认配置为连接本地：`host='localhost', port=6379, db=0`。

-----

### 📝 项目配置

在运行爬虫之前，您需要准备两个文件并检查配置路径：

#### 1\. 标签列表文件

  * **路径变量**: `tag_file_path`
  * **要求**: 创建一个文本文件（例如 `ram_tag_list.txt`），每行包含一个您想要搜索的关键词（标签）。
  * **示例 `ram_tag_list.txt`**:
    ```
    天空
    海边
    二次元
    ```

#### 2\. 数据保存路径

  * **路径变量**: `save_path_all`
  * **要求**: 这是爬虫结果 CSV 文件保存的根目录。如果目录不存在，程序会自动创建。

-----

### ▶️ 如何运行

1.  **配置**：确保您已完成上述所有的环境设置和项目配置。
2.  **运行**: 在命令行中执行 Python 主文件：

<!-- end list -->

```bash
python your_spider_file_name.py
```

### 📄 输出结果

爬虫会将结果写入到 `all_records.csv` 文件中，包含以下字段：

| 字段名称 | 说明 |
| :--- | :--- |
| **Title** | 图片的文字标题/描述。 |
| **ImageName** | 图片的文件名（例如：`20220721002824_28bc3.jpeg`）。 |
| **URL** | 清理后、可直接访问的原始图片链接。 |
| **TAG** | 搜索该图片时使用的关键词标签。 |

-----

### 🛑 注意事项

  * **反爬策略**: 由于本爬虫使用 Selenium 模拟浏览器操作，请控制抓取频率，防止被目标网站封锁 IP。代码中已使用 `time.sleep(random.uniform(x, y))` 增加随机延迟。
  * **驱动路径**: 务必检查 `chrome_driver_path` 是否与您本地的 ChromeDriver 路径一致。
  * **Redis 依赖**: 如果您不希望使用 Redis 去重，需要修改 `get_images` 方法中关于 `self.redis.sismember` 和 `self.redis.sadd` 的逻辑。
