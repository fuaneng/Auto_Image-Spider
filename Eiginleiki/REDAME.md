
# Eiginleiki 网站图片爬虫 (EiginleikiCrawler)

本项目是一个基于 Python 和 Selenium WebDriver 的网页爬虫，用于从特定网站的分页结构中提取图片原始 URL，并利用 Redis 进行去重，最终将数据保存到 CSV 文件中。该爬虫已针对网站的结构变化（从第 9 页开始）进行了兼容性处理。

## 目录

  * [项目介绍](https://www.google.com/search?q=%23%E9%A1%B9%E7%9B%AE%E4%BB%8B%E7%BB%8D)
  * [主要功能](https://www.google.com/search?q=%23%E4%B8%BB%E8%A6%81%E5%8A%9F%E8%83%BD)
  * [环境要求](https://www.google.com/search?q=%23%E7%8E%AF%E5%A2%83%E8%A6%81%E6%B1%82)
  * [项目配置](https://www.google.com/search?q=%23%E9%A1%B9%E7%9B%AE%E9%85%8D%E7%BD%AE)
  * [使用指南](https://www.google.com/search?q=%23%E4%BD%BF%E7%94%A8%E6%8C%87%E5%8D%97)
  * [运行结果](https://www.google.com/search?q=%23%E8%BF%90%E8%A1%8C%E7%BB%93%E6%9E%9C)

## 项目介绍

`EiginleikiCrawler` 是一个专为爬取 `eiginleiki.net` 网站图片设计的自动化脚本。它通过控制 Chrome 浏览器模拟用户行为，高效地遍历指定页码范围，提取图片链接。

**核心特性：**

  * **Selenium 驱动：** 使用 Chrome 浏览器进行页面加载和元素交互。
  * **兼容性处理：** 自动识别页码（第 1-8 页 vs. 第 9 页及以后）以应用不同的元素选择器，确保提取的准确性。
  * **效率优化：** 配置禁用图片加载，大幅减少页面加载时间和带宽消耗。
  * **数据去重：** 使用 Redis 数据库存储已提取图片的 MD5 哈希值，确保不重复抓取相同的 URL。
  * **持久化存储：** 将爬取结果（标题、文件名、URL、标签）写入 CSV 文件。

## 主要功能

| 功能模块 | 实现细节 |
| :--- | :--- |
| **分页爬取** | 从 `START_PAGE`（默认为第 9 页）开始，一直爬取到 `MAX_PAGES`（默认为第 330 页）。 |
| **元素提取** | 根据页码动态切换 CSS 选择器：<br> - 第 1-8 页：获取 `a.post_media_photo_anchor` 的 `data-big-photo` 属性。<br> - 第 9 页及以后：获取 `div#post img` 的 `src` 属性。 |
| **URL 清洗** | 移除 URL 末尾可能携带的查询参数。 |
| **去重机制** | 对提取的最终 URL 计算 MD5 哈希值，并使用 Redis Set 进行快速查重和记录。 |
| **浏览器控制** | 配置 `ChromeOptions` 禁用图片加载和设置用户代理（User-Agent）。 |

## 环境要求

在运行此脚本之前，请确保您的系统满足以下要求：

1.  **Python 环境:** Python 3.x
2.  **Chrome 浏览器:** 必须安装最新版本的 Google Chrome。
3.  **ChromeDriver:** 确保安装了与您 Chrome 浏览器版本兼容的 ChromeDriver。
4.  **Redis 服务:** 需要本地运行一个 Redis 实例（默认端口 6379）。

### 依赖安装

使用 `pip` 安装所需的 Python 库：

```bash
pip install selenium redis
```

## 项目配置

您需要在代码文件的顶部配置以下常量：

### 1\. 路径和 URL 配置

| 常量名 | 描述 | 默认值 | **您需要修改** |
| :--- | :--- | :--- | :--- |
| `CHROME_DRIVER_PATH` | ChromeDriver 的完整路径。 | `r'C:\Program Files\Google\chromedriver-win64\chromedriver.exe'` | **✓** (必填) |
| `START_URL` | 用于提取基础域名，保持默认即可。 | `'https://eiginleiki.net/page/1'` | 否 |

### 2\. 爬取控制配置

| 常量名 | 描述 | 默认值 | **您需要修改** |
| :--- | :--- | :--- | :--- |
| `START_PAGE` | 爬虫开始的页码。 | `1` | 是 |
| `MAX_PAGES` | 爬虫停止的页码。 | `330` | 是 |
| `PAGE_SPLIT_POINT` | 结构变化的起始页码（小于此页使用旧结构，大于等于使用新结构）。 | `9` | 否 (除非网站结构再次变化) |
| `PAGE_SLEEP` | 页面间随机休眠的最大秒数（有助于反反爬）。 | `2` | 否 |

### 3\. 数据保存配置

在 `if __name__ == '__main__':` 块中配置数据保存路径：

```python
if __name__ == '__main__':
    # 配置保存目录
    save_dir = r'R:\py\Auto_Image-Spider\Eiginleiki\data'
    # 完整的 CSV 文件路径
    csv_path = os.path.join(save_dir, 'all_eiginleiki_records.csv')
    
    # ...
```

请根据您的实际需求修改 `save_dir`。

## 使用指南

1.  **准备环境：** 确保已安装所有依赖和运行了 Redis 服务。

2.  **配置代码：** 根据 [项目配置](https://www.google.com/search?q=%23%E9%A1%B9%E7%9B%AE%E9%85%8D%E7%BD%AE) 部分修改 `CHROME_DRIVER_PATH` 及爬取范围（`START_PAGE` 和 `MAX_PAGES`）。

3.  **运行脚本：**

    ```bash
    python 你的爬虫文件名.py
    ```

脚本将开始按页码顺序加载页面，提取 URL，进行去重，并将新的记录追加到指定的 CSV 文件中。

## 运行结果

脚本运行期间，您将在控制台看到详细的日志输出，包括：

  * WebDriver 和 Redis 的连接状态。
  * 当前正在加载的页码和 URL。
  * 当前页使用的结构选择器（旧结构/新结构）。
  * 提取到的原图 URL 和 MD5 校验信息。
  * CSV 写入成功的提示或跳过重复 URL 的提示。
  * 最终完成的总记录数。

运行结束后，您将在配置的保存目录中找到名为 `all_eiginleiki_records.csv` 的文件，其中包含所有爬取到的不重复图片链接及其相关信息。