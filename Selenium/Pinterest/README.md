
# 🧭 Pinterest 图片爬虫（Selenium + JS Path）

> 一键自动抓取 Pinterest 搜索结果中的高清图片链接
> 支持懒加载检测、遮罩层清除、Redis 去重与 CSV 数据保存

---

<p align="center">
  <img src="https://upload.wikimedia.org/wikipedia/commons/3/35/Pinterest_Logo.svg" alt="Pinterest" width="160"/>
</p>

---

## 🧩 功能概览

✔️ 自动搜索并滚动 Pinterest 页面
✔️ 使用 **JavaScript Path** 抓取所有图片 URL
✔️ 自动清除登录遮罩层（防止遮挡）
✔️ 识别懒加载，等待图片加载稳定
✔️ 支持 **Redis + 本地 MD5 去重**
✔️ 自动写入 CSV 文件
✔️ 可选“可见/不可见”运行模式

---

## 📦 一、环境准备

### 🧰 1. 安装 Python

请确保你安装了 **Python 3.8+**（推荐 3.10 以上版本）

可在命令行中检查：

```bash
python --version
```

### ⚙️ 2. 安装依赖包

创建一个虚拟环境（推荐）：

```bash
python -m venv venv
```

激活它（Windows）：

```bash
venv\Scripts\activate
```

安装必要依赖：

```bash
pip install selenium redis
```

---

## 🪟 二、安装 ChromeDriver

PinterestSpider 依赖 **Chrome + ChromeDriver**。

1️⃣ 打开 Chrome，输入地址：

```
chrome://settings/help
```

查看浏览器版本号，例如：`141.0.7045.160`

2️⃣ 前往官方页面下载对应版本的 [ChromeDriver](https://googlechromelabs.github.io/chrome-for-testing/)

3️⃣ 下载后解压，放置到固定路径，如：

```
C:\Program Files\Google\chromedriver-win32\chromedriver.exe
```

---

## 🔧 三、项目目录结构

```
Pinterest/
│
├── pinterest_spider.py       # 主程序文件
├── ram_tag_list_备份.txt      # 关键词列表文件
├── all_records_pinterest.csv # 自动生成的图片信息表
└── README.md                 # 使用说明
```

---

## 🧠 四、配置与运行

### ✏️ 1. 编辑标签文件

在 `ram_tag_list_备份.txt` 中写入每行一个搜索关键词，例如：

```
cats
nature
sunset
interior design
```

### ⚙️ 2. 编辑主程序配置

打开 `pinterest_spider.py`，修改以下路径：

```python
chrome_driver_path = r'C:\Program Files\Google\chromedriver-win32\chromedriver.exe'
save_dir = r'D:\work\爬虫\爬虫数据\pinterest'
tag_file_path = r'D:\work\爬虫\ram_tag_list_备份.txt'
```

> 🔸 `chrome_driver_path`：ChromeDriver 的路径
> 🔸 `save_dir`：图片记录保存目录
> 🔸 `tag_file_path`：关键词文件路径

---

### 🚀 3. 运行脚本

```bash
python pinterest_spider.py
```

---

## 👁️‍🗨️ 五、运行模式说明

| 模式        | 参数                   | 效果               |
| --------- | -------------------- | ---------------- |
| 可见模式（调试用） | `use_headless=False` | 浏览器窗口可见，方便观察爬取过程 |
| 无头模式（生产用） | `use_headless=True`  | 浏览器后台运行，不弹窗      |

在主函数中修改即可：

```python
spider = PinterestSpider(chrome_driver_path, use_headless=True)
```

---

## 📊 六、输出结果

爬虫会将结果写入一个 CSV 文件（默认：`all_records_pinterest.csv`）：

| Title       | ImageName                            | URL                                               | Tag    |
| ----------- | ------------------------------------ | ------------------------------------------------- | ------ |
| Cute cat    | 22223f30497702f9fb2cca7d7c317401.jpg | [https://i.pinimg.com/](https://i.pinimg.com/)... | cats   |
| Nature View | 7c23f1c48c9d8a2a3b2127d8aa11a8b7.jpg | [https://i.pinimg.com/](https://i.pinimg.com/)... | nature |

> 📁 该文件可直接在 Excel 或 Pandas 中打开进行分析或批量下载。

---

## 🔍 七、主要技术原理讲解

| 模块                     | 功能说明                                              |
| ---------------------- | ------------------------------------------------- |
| **Selenium WebDriver** | 控制浏览器执行滚动、加载、执行 JS                                |
| **JS Path 抓取**         | 在浏览器内部执行 JavaScript 获取 `<img>` 节点数据，绕过 React 动态渲染 |
| **懒加载检测**              | 循环检测图片数量是否稳定，保证图片已加载完成                            |
| **遮罩层清理**              | 通过 JS 删除 Pinterest 登录弹窗、模态对话框等遮挡元素                |
| **Redis + MD5 去重**     | 防止重复记录相同图片 URL                                    |
| **CSV 多线程锁写入**         | 保证多线程情况下写入安全                                      |

---

## ⚡ 八、常见问题（FAQ）

**Q1：运行时报错 `stale element reference`？**

> 已修复。新版本使用 JS Path 获取 DOM，不会再出现。

**Q2：为什么第一次滚动后图片才出现？**

> Pinterest 懒加载机制，脚本中已自动等待加载稳定。

**Q3：出现登录遮罩层？**

> 程序会自动移除，如仍有弹出，可提前登录 Pinterest。

**Q4：Redis 连接失败？**

> 没问题，会自动切换为本地内存去重模式。

**Q5：如何只获取图片 URL 不保存 CSV？**

> 你可以注释掉 `self.write_to_csv()` 行，仅打印结果。

---

## 🧰 九、进阶使用

### 1️⃣ 手动指定爬取 URL

你可以直接调用：

```python
spider.crawl_page("https://za.pinterest.com/search/pins/?q=sunset&rs=typed", "sunset", "result.csv")
```

### 2️⃣ 自定义滚动参数

修改顶部变量控制滚动次数和等待时长：

```python
MAX_SCROLLS = 150
SCROLL_WAIT_RANGE = (1.5, 4.0)
```

### 3️⃣ 禁用图片加载（加速）

若仅抓取图片 URL 而不下载图片，可在初始化时启用：

```python
prefs = {"profile.managed_default_content_settings.images": 2}
options.add_experimental_option("prefs", prefs)
```

---

## 🧑‍💻 十、开发者信息

**作者昵称：** Selenium 🤖
**技术栈：** Python + Selenium + Redis + JavaScript DOM
**版本：** v2.1 (JS Path Enhanced Edition)
**版权声明：** 本项目仅用于学习和技术研究，请勿用于商业用途。

---

## 🌟 示例运行截图

> PinterestSpider 自动滚动、抓取并输出的实时日志：

```
[INFO] 导航到：https://za.pinterest.com/search/pins/?q=cats&rs=typed
[√] 页面加载完成。
==== 第 1 次滚动 ====
[清理] 已移除 2 个遮罩层。
[INFO] JS 抓取到 34 张图片。
✔️ 写入：22223f30497702f9fb2cca7d7c317401.jpg
✔️ 写入：ab12c3d4ef56789a001bc.jpg
...
[√] 图片数稳定: 80
[等待] 滚动后等待 2.31 秒...
==== 第 2 次滚动 ====
[完成] 已连续 2 轮无新内容。
[√] 'cats' 抓取完成。
```

---

## ❤️ 支持与交流

如果这份爬虫项目对你有帮助，欢迎点个 ⭐ **Star**
有问题可以提交 Issue 或留言讨论！

> **一起让 Pinterest 的图片爬取更优雅、更稳定！** 🚀

---


