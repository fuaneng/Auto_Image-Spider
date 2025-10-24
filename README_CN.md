## Auto_Image-Spider

[项目地址](https://github.com/fuaneng/Auto_Image-Spider)
[![GitHub stars](https://img.shields.io/github/stars/fuaneng/Auto_Image-Spider?style=social)](https://github.com/fuaneng/Auto_Image-Spider/stargazers)
[![GitHub forks](https://img.shields.io/github/forks/fuaneng/Auto_Image-Spider?style=social)](https://github.com/fuaneng/Auto_Image-Spider/network/members)
---

## 🏷 标签（Topics）

`图片爬虫` | `Selenium` | `Requests` | `Scrapy` | `DrissionPage` | `Redis` | `Python` | `批量抓图` | `AIGC 训练素材`

![liblib 个人主页](https://liblibai-online.liblib.cloud/img/db14e0c0ab354c569a27c03b25b2aff8/cd6a410fefc4b09e7b56c3bdca810809bcde70e07d3c6aa04b1829af2980ad89.png)

---
## 📢 项目说明

本项目是一个用于 **批量抓取图片资源** 的 Python 爬虫集合，支持多种图片／素材网站、关键词批量抓取、自动保存图片及 CSV 记录。适合用于图像数据收集、AIGC 训练素材准备等场景，请合理使用，避免对目标网站造成过大负担。

---

## 📋 项目简介

- 本项目由本人整理维护，目标是通过不同的爬虫管道脚本从不同图片 / 素材网站抓取图片、标题、原始 URL 等信息用作 AIGC 训练素材。  
- 支持多种目标网站（见下方“支持的网站清单”一节）。  
- 主要功能包括：自动浏览器模拟、滚动加载、点击“加载更多”、分页接口、静态请求、去重处理、保存 CSV ＋ 图片。  
- 脚本可按标签文件（每行一个关键词）批量执行。  
- 输出结果包括：标题、图片文件名、原始图片 URL、搜索关键词等字段。

---

## 🛠 技术栈 & 爬虫框架概览

- 语言：**Python 3.x**  
- 常用库/工具包括：  
  - `selenium`：用于浏览器自动化操作，如滚动页面、点击按钮、获取动态加载内容。  
  - `requests` / `urllib`：用于静态请求、下载图片资源。  
  - `scrapy`：可用于爬虫框架化、分页／发现链接的场景。  
  - `DrissionPage`：一种 Python 浏览器自动化／渲染工具，可作为 Selenium 的替代或配合使用。  
  - `redis`：可选，用于 URL 去重、缓存、状态存储。  
  - 文件系统操作（`os`、`pathlib` 等）：用于图片保存、目录管理。  
- 每个脚本可视目标网站特点选择合适的方式（静态请求、浏览器模拟、分页翻页等）。

---

## ✅ 支持的网站清单 & 框架映射（部分）

以下为仓库中部分已支持或预期支持的网站清单，列出网站名称、主要抓取特点、建议使用的框架／方法（你可根据脚本实际情况补充或修正）。

| 目录／脚本 名称       | 目标网站                          | 抓取特点                             | 使用框架／方法                                         | 备注                       |
|------------------------|----------------------------------|--------------------------------------|-------------------------------------------------------|----------------------------|
| `Lifeofpix/`           | Life of Pix                       | 静态分页、无登录、可直接下载图片     | `requests` ＋ 静态 HTML 解析                          | 简单场景                   |
| `Unsplash/`            | Unsplash                          | 滚动加载／分页接口、动态内容          | `selenium` 或 `requests` 分页                         | 可选浏览器模拟             |
| `FreePhotos_cc/`       | FreePhotos.cc                     | 免费照片素材，分页较多                | `requests` ＋ `BeautifulSoup`／`lxml`                | 静态请求优先               |
| `ArtStation/`          | ArtStation                        | 数字艺术平台，图片高质量、加载复杂    | `selenium` ＋ ChromeDriver                             | 动态加载、点击“加载更多”   |
| `Civitai/`             | Civitai                           | 模型 + 图片资源、需要登录或 Cookies   | `selenium` ＋ 登录处理                                   | 登录 + 滚动/分页            |
| …（其它目录／脚本）     | （补充）                          | （补充）                              | （补充）                                                | （备注）                   |

> ⚠️ 注意：以上表格为示例，具体框架选择需参照每个脚本实际 `import` 情况（如是否含 `import drissionpage`、`import scrapy`、`from selenium import webdriver` 等）进行确认。

---

## 📂 项目结构 & 配置说明

- `tag_file_path`：标签关键词文件路径（如 `tags.txt`），每行一个关键词。  
- `save_path_all`：根保存目录，程序运行时如不存在则自动创建。  
- 各脚本文件命名规范例如 `crawl_lifeofpix.py`、`crawl_unsplash.py` 等。  
- 运行脚本前需在脚本头部或配置文件中指定关键词文件、保存路径、浏览器驱动路径、是否启用 Redis 等。  
- 输出结果说明：  
  - 生成 CSV（如 `all_records.csv`）包含：Title（标题）、ImageName（保存文件名）、URL（原始图片 URL）、TAG（关键词）  
  - 图片保存至对应目录：如 `save_path_all/<site_name>/<tag>/…`  

---

## ▶️ 快速启动指南

1. 安装 Python 3（建议 3.8 及以上）。  
2. 安装必要依赖（示例）：  
   ```bash
   pip install selenium redis beautifulsoup4 lxml requests drissionpage scrapy 
   ```

3. 下载与你本地 Chrome 浏览器版本匹配的 ChromeDriver，并将其路径配置到脚本（变量如 `chrome_driver_path`）
    ```bash
    # 建议使用固定路径，避免环境变量问题
    CHROME_DRIVER_PATH = r'C:\Program Files\Google\chromedriver-win64\chromedriver.exe'
    ```
4. （可选）若使用 Redis 去重功能，启动 Redis 服务（默认 host=localhost, port=6379, db=0）。
5. 准备标签文件（例如 `tags.txt`），每行一个关键词。
6. 执行某个脚本，例如：

   ```bash
   python crawl_lifeofpix.py --tag_file tags.txt --save_dir ./images/lifeofpix
   ```
7. 等待程序运行结束，检查 保存目录与 CSV 记录文件。

---

## ⚠️ 注意事项 & 建议

* 多数目标网站具有 **反爬机制**（如 IP 限制、动态渲染、无限滚动、验证码等），建议：

  * 控制抓取频率，加入随机延迟（`time.sleep()`）
  * 善用代理池或 IP 切换（如有需要）
  * 避免短期大量并发请求导致封锁
* 使用 selenium 框架时，必须确认 ChromeDriver 版本与你本地 Chrome 浏览器兼容，否则浏览器自动化可能失败。
* 若不使用 Redis 去重，可修改／注释脚本中相关逻辑。
* 下载的图片请确保合法使用，遵循目标站点的版权／授权条款，仅用于个人研究或非商业用途。
* 若脚本中断或报错，建议检查：网络状态、浏览器驱动路径、标签文件格式、目标页面结构是否变化。

---

## 🧩 贡献 &许可

本项目采用 MIT 许可证开源，欢迎社区参与贡献。

欢迎你：

* 提交 issue 反馈问题或建议
* Fork 本仓库，新增或改进脚本（支持更多网站、优化性能、增强去重等）
* 如果你有其他想法也欢迎告诉我
* 请尊重目标网站 TOS / 版权协议，仅用于合法用途

---




