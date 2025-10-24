
# 🏛️ MetMuseum 图片爬虫（Selenium 自动化版）

> 使用 Selenium 自动化从 [大都会艺术博物馆 (The Met Museum)](https://www.metmuseum.org/) 抓取艺术藏品图片与相关信息，并保存为 CSV 文件。

---

## 📘 项目简介

本项目基于 **Selenium + Python 3** 实现，自动爬取 Met Museum 艺术藏品检索页的图片信息。  
支持分步滚动加载、分页翻页、Redis 去重与线程安全 CSV 写入。

✅ 特性：
- 自动搜索多个关键词（从 tag 文件读取）  
- 智能滚动加载，触发懒加载图片  
- 自动翻页直到无“下一页”  
- 自动提取标题与原图链接（自动替换 `mobile-large` → `original`）  
- Redis/内存 去重机制  
- CSV 文件安全写入（支持断点续写）  
- 详细日志输出，方便追踪与调试  

---

## 🧩 环境依赖

### 1️⃣ Python 版本
- Python **3.8+**

### 2️⃣ 必需依赖
安装以下包：

```bash
pip install selenium redis
````

> 建议使用虚拟环境（如 `venv` 或 `conda`）。

### 3️⃣ Chrome 浏览器与 ChromeDriver

* Chrome 浏览器（版本需与 `chromedriver` 匹配）
* 下载对应版本的 [ChromeDriver](https://chromedriver.chromium.org/downloads)

示例路径（Windows）：

```
C:\Program Files\Google\1\chromedriver-win32\chromedriver.exe
```

### 4️⃣ 可选依赖：Redis 服务

* 若安装 Redis，则自动启用持久化去重功能；
* 若无 Redis，会自动退回为内存去重（仅限当前运行周期）。

Windows 下可使用 [Memurai](https://www.memurai.com/) 或 [Redis on WSL]。

---

## 📂 项目目录结构

```
metmuseum_spider/
│
├── metmuseum_spider.py      # 主程序（Selenium 爬虫）
├── README.md                # 项目说明文档（本文件）
├── ram_tag_list.txt         # 搜索标签文件（每行一个关键词）
└── output/
    └── all_records_metmuseum_01.csv   # 输出结果文件
```

---

## ⚙️ 使用步骤

### 1️⃣ 准备关键词文件

在项目根目录创建 `ram_tag_list.txt`，每行一个标签关键词，例如：

```
painting
sculpture
Chaim Gross
Egyptian
```

---

### 2️⃣ 编辑驱动与路径配置

在 `metmuseum_spider.py` 文件末尾找到以下代码块：

```python
if __name__ == '__main__':
    chrome_driver_path = r'C:\Program Files\Google\1\chromedriver-win32\chromedriver.exe'
    save_dir = r'D:\work\爬虫\爬虫数据\metmuseum'
    tag_file_path = r'D:\work\爬虫\ram_tag_list.txt'
```

根据你的实际情况修改：

* ✅ `chrome_driver_path` → ChromeDriver 路径
* ✅ `save_dir` → 图片/CSV 保存路径
* ✅ `tag_file_path` → 标签文件路径

---

### 3️⃣ 运行脚本

在命令行中运行：

```bash
python metmuseum_spider.py
```

程序将自动执行以下步骤：

1. 读取关键词列表；
2. 打开 MetMuseum 搜索页；
3. 逐页滚动、加载、提取；
4. 写入 CSV 文件；
5. 自动翻页至结束；
6. 关闭浏览器。

---

## 📸 输出结果示例

输出文件：`all_records_metmuseum_01.csv`

| Title          | ImageName    | URL                                                                                                                                | Tag         |
| -------------- | ------------ | ---------------------------------------------------------------------------------------------------------------------------------- | ----------- |
| Women          | DP701752.jpg | [https://images.metmuseum.org/CRDImages/ma/original/DP701752.jpg](https://images.metmuseum.org/CRDImages/ma/original/DP701752.jpg) | Chaim Gross |
| Vase           | 1985.1.1.jpg | [https://images.metmuseum.org/CRDImages/as/original/1985.1.1.jpg](https://images.metmuseum.org/CRDImages/as/original/1985.1.1.jpg) | Chinese     |
| Statue of Isis | 19.2.3.jpg   | [https://images.metmuseum.org/CRDImages/eg/original/19.2.3.jpg](https://images.metmuseum.org/CRDImages/eg/original/19.2.3.jpg)     | Egyptian    |

---

## 🧠 核心功能详解

### 🔹 1. 滚动加载逻辑

为触发懒加载图片，本项目采用：

* 每次滚动固定像素 (`1080px`)
* 检测页面高度变化
* 连续 2 次无变化则停止
* 最大 80 次滚动上限保护

✅ 兼容 MetMuseum 目前的瀑布流加载机制。

---

### 🔹 2. 翻页逻辑

* 自动识别并点击 “Next Page” 按钮：

  ```html
  <button aria-label="Next Page"> ... </button>
  ```
* 检测按钮禁用或不存在即停止翻页；
* 兼容部分页面结构变化（aria-label 含 "Next" 的情况）。

---

### 🔹 3. 去重机制

两种模式：

| 模式         | 是否启用 Redis | 数据持久化 | 推荐   |
| ---------- | ---------- | ----- | ---- |
| ✅ Redis 模式 | 是          | 是     | 最佳性能 |
| ⚙️ 内存模式    | 否          | 否     | 简易使用 |

使用 Redis：

```bash
redis-server
```

---

### 🔹 4. 图片 URL 清洗逻辑

MetMuseum 图片常见为：

```
https://images.metmuseum.org/CRDImages/as/mobile-large/11_7_3.JPG
```

自动替换为原图：

```
https://images.metmuseum.org/CRDImages/as/original/11_7_3.JPG
```

同时兼容其他路径前缀：
`web-large`, `medium`, `small`, `thumb`。

---

### 🔹 5. CSV 写入机制

* 多线程安全（`threading.Lock`）；
* 自动写入表头；
* 采用 `utf-8-sig` 防止 Excel 乱码；
* 文件断点续写（不会重复写入）。

---

## 🧰 调试与优化建议

| 目标       | 操作建议                    |
| -------- | ----------------------- |
| 查看真实页面行为 | 将 `use_headless=False`  |
| 提高速度     | 可禁用图片加载、增加 `prefs` 参数   |
| 下载原图     | 可扩展使用 `requests` 模块批量下载 |
| 避免封禁     | 每次搜索或翻页后增加随机延时 `2~5 秒`  |
| 断点续爬     | Redis 模式下支持断点续爬，不会重复写入  |

---

## ⚠️ 常见问题（FAQ）

### ❓ 1. 程序卡在页面加载？

* 检查 ChromeDriver 版本与浏览器是否匹配；
* 若 MetMuseum 改版，可重新更新容器选择器：

  ```python
  self.main_container_selector = 'section.object-grid_grid__hKKqs figure.collection-object_collectionObject__SuPct'
  ```

### ❓ 2. Redis 连接失败？

* 启动 Redis 服务后重试；
* 或关闭 Redis 自动退回内存模式。

### ❓ 3. CSV 无内容？

* 确认关键词有搜索结果；
* 或页面加载时间不足，可适当增加等待秒数。

---

## 🧩 扩展功能（可选）

> 以下为未来可拓展模块：

* [ ] 图片下载功能（requests + 多线程）
* [ ] MongoDB 数据存储
* [ ] 自动异常截图保存
* [ ] CLI 命令行参数支持
* [ ] Docker 部署环境

---

## 🧑‍💻 作者信息

👨‍💻 **Selenium Master: Selenium（AI 代码助手）**
📍 专精于 Web 自动化 / 动态页面解析 / 多线程爬虫
📬 欢迎提交 Issue 或 Pull Request 优化脚本！

---

## 🪪 License

本项目仅用于学习与研究，**禁止用于任何商业用途**。
如需批量下载或使用 MetMuseum 图片，请遵守其官方网站的版权声明。

