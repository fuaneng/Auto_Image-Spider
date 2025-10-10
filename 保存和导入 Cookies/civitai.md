# 🖼️ Civitai 瀑布流图片采集器 (Python + Selenium)

本项目是一个功能强大的 Python 自动化脚本，专为从 **Civitai (civitai.com)** 网站高效、稳定地采集图片 URL 及相关数据而设计。

它解决了 Civitai 网站中常见的**多列瀑布流 (Masonry Layout)** 和**懒加载 (Lazy Loading)** 机制带来的采集难题，能够模拟真实用户操作，确保不错过任何滚动加载的图片。

-----

## ✨ 核心功能与特性

1.  **稳定加载机制：** 采用**键盘模拟滚动 (`Keys.END`)** 优先，结合 **JavaScript 滚动** 为备用的强化滚动策略，确保在复杂的单页应用中能可靠地触发懒加载。
2.  **动态等待：** 不依赖固定的延迟时间，而是通过监控页面上**图片卡片的总数量**是否增加来判断新内容是否加载完成，极大地提高了效率和稳定性。
3.  **多标签批量采集：** 通过配置 `tag.txt` 文件，可一次性采集多个搜索标签下的所有图片。
4.  **去重机制：** 支持使用 **Redis**（推荐）或本地内存中的 `set` 集合进行 URL 去重，避免重复采集数据。
5.  **保持登录状态：** 通过加载 Chrome 用户配置文件，可以保持登录状态，从而访问需要授权才能查看的内容。
6.  **数据输出：** 将采集到的图片 URL（并尝试转换为原图链接）、图片 ID、以及搜索标签等信息结构化保存到 **CSV 文件**中。

-----

## 🛠️ 环境准备

### 1\. 安装依赖

确保你的 Python 环境已安装以下库：

```bash
pip install selenium redis
```

### 2\. 配置 ChromeDriver

  * **下载：** 确保你下载了与本地 **Chrome 浏览器版本匹配**的 [ChromeDriver](https://chromedriver.chromium.org/downloads)。
  * **配置：** 务必在脚本的配置区中，将 `CHROME_DRIVER_PATH` 设置为 `chromedriver.exe` 的完整路径。
  * **注意事项：** 确保 `chromedriver.exe` 与 Chrome 浏览器的版本兼容。如果版本不匹配，可能会导致脚本运行失败。

### 3\. Redis 服务（可选）

如果你的机器上运行了 Redis 服务（默认端口 6379），脚本将自动连接它进行**跨会话去重**。如果 Redis 连接失败，脚本会退回到使用**本地内存 `set`** 进行去重。

-----

## ⚙️ 脚本配置指南

运行前，请打开 `爬取-civitai_tag-滚动加载.py` 文件，并根据你的环境修改顶部的 **配置区** 变量：

| 变量名 | 描述 | **必须修改** |
| :--- | :--- | :--- |
| `CHROME_DRIVER_PATH` | **你的 `chromedriver.exe` 完整路径。** | 是 |
| `USER_DATA_DIR` | Chrome 用户数据目录的父路径（用于保持登录状态）。 | 否 (但推荐) |
| `PROFILE_DIR` | Chrome 配置文件的名称（如 `"Default"`, `"Profile 1"`）。 | 否 (使用默认) |
| `TAG_TXT_DIR` | 存放 `tag.txt` 文件和最终 CSV 文件的目录。 | 是 |
| `MAX_SCROLLS` | 单个标签页面的最大滚动次数，防止无限循环。 | 否 (使用默认 200) |
| `NO_NEW_ROUNDS_TO_STOP` | 连续未发现新图片的轮数，达到此值即停止当前标签采集。 | 否 (使用默认 3) |

### 1\. 创建 `tag.txt`

在 `TAG_TXT_DIR` 指定的目录下，创建一个名为 **`tag.txt`** 的文本文件。每行输入一个你要在 Civitai 搜索的关键词或标签。

**`tag.txt` 示例：**

```
genshin impact
original character
high quality lora
```

-----

## ▶️ 如何运行

1.  **准备环境：** 确保所有依赖已安装，且配置文件已更新。
2.  **执行脚本：** 在终端中运行 Python 脚本。

<!-- end list -->

```bash
python 爬取-civitai_tag-滚动加载.py
```

### 运行提示

  * 脚本运行时会打开一个 Chrome 窗口。为确保滚动和焦点操作的成功，请**避免最大化或最小化该窗口**，并尽量**不要在其上执行鼠标或键盘操作**。
  * 脚本会逐个处理 `tag.txt` 中的标签，并在控制台输出详细的滚动和解析日志。
  * 最终采集结果将保存在 `civitai` 目录下的 **`all_records_civitai.csv`** 文件中。

-----

## 📝 输出 CSV 文件结构

| 列名 | 描述 | 示例数据 |
| :--- | :--- | :--- |
| `Prompt` | 提示词（目前由于卡片信息不完整，显示为详情页链接）。 | `Prompt 未在卡片中提供（详情页: ...）` |
| `ImageName` | 图片的唯一 ID（通常是 UUID）。 | `a1b2c3d4-e5f6-g7h8-i9j0-k1l2m3n4o5p6` |
| `URL` | 转换后的**原始图片链接**（带有 `original=true` 参数）。 | `https://cdn.civitai.com/.../original=true` |
| `TAG` | 抓取该图片时使用的搜索标签。 | `genshin impact` |

```
```