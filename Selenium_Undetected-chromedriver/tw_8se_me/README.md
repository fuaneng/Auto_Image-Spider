
# 📸 XChina / 8se.me 全自动异步爬虫（Selenium + 多线程下载）

基于 **Selenium + Python + 多线程异步下载** 构建的高效爬虫系统，  
可自动爬取 `xchina.fit` 与 `tw.8se.me` 模特作品页，自动识别分页、提取所有图片原图链接，并支持异步下载与数据表格化存储。

---

## 🚀 功能概览

| 功能 | 描述 |
|------|------|
| 🧠 智能识别 | 自动检测作品页入口（`/photos/model-xxxx.html` 或 `/model/id-xxxx.html`） |
| 🔁 自动翻页 | 自动遍历 `/2.html`, `/3.html`, ... 直到无作品为止 |
| ⚡ 异步下载 | 使用 `ThreadPoolExecutor` 并发下载图片 |
| 📂 结构化存储 | 图片自动分类保存：`models/{model_name}/{title}/0001.jpg` |
| 📊 独立表格存储 | 每个模特一个 CSV 文件（如 `csvs/白浅浅.csv`） |
| 💾 可控下载开关 | 仅采集数据或下载原图自由切换 |
| 🔒 线程安全 | CSV 写入与下载均使用锁机制，防止竞争冲突 |

---

## 🧩 项目结构

```

R:\py\Auto_Image-Spider
└── Selenium_Undetected-chromedriver
└── en_girlstop_info
└── tw_8se_me
├── xchina_spider_async_paged.py   # 主爬虫脚本
├── model_id.txt                   # 模特信息文件
├── csvs\                          # 每个模特独立 CSV
│   ├── 白浅浅.csv
│   └── 高七千.csv
└── models\                        # 图片保存目录
├── 白浅浅
│   ├── 梨霜兒 Vol. 10915
│   │   ├── 0001.jpg
│   │   ├── 0002.jpg
│   │   └── ...
│   └── ...
└── 高七千
└── ...

````

---

## ⚙️ 环境依赖

### 🐍 Python 版本
> 推荐 Python **3.9 ~ 3.11**

### 📦 安装依赖包
```bash
pip install selenium requests
````

> 如果使用 `undetected_chromedriver`（推荐防止 Cloudflare 检测）：

```bash
pip install undetected-chromedriver
```

---

## 🧭 使用说明

### 1️⃣ 配置浏览器路径

在脚本顶部设置你的 Chrome 路径：

```python
CUSTOM_BROWSER_PATH = r"C:\Program Files\Google\Chrome\Application\chrome.exe"
CHROMEDRIVER_PATH = r"C:\Program Files\Google\chromedriver-win64\chromedriver.exe"
```

> ⚠️ 版本必须与 Chrome 主版本号一致，否则无法启动。

---

### 2️⃣ 准备模特文件 `model_id.txt`

```
67e1c853d3528   # {model_id}
白浅浅          # {model_name}
6751as151a223   # {model_id}
高七千          # {model_name}
```

> 模特 ID 可从网站 URL 中提取：
> `https://xchina.fit/model/id-67e1c853d3528.html`

---

### 3️⃣ 运行爬虫

```bash
python xchina_spider_async_paged.py
```

程序会自动执行以下流程：

1. 启动 Selenium 浏览器
2. 自动加载模特作品页（带分页）
3. 自动解析每个作品的标题、封面图、总数量
4. 自动推算所有图片原图 URL
5. 写入对应 CSV 文件
6. 若开启下载功能则异步保存所有原图

---

### 4️⃣ 控制是否下载图片

在脚本顶部修改：

```python
DOWNLOAD_ENABLED = True   # 下载图片（默认）
```

若只需采集数据不下载：

```python
DOWNLOAD_ENABLED = False
```

---

## 🧠 数据结构说明

CSV 文件字段：

| 字段          | 含义                 |
| ----------- | ------------------ |
| `Title`     | 作品标题（含期号与日期）       |
| `ImageName` | 图片文件名，如 `0001.jpg` |
| `URL`       | 图片原图地址             |
| `ModelName` | 模特中文名              |

---

## 💡 工作原理简述

1. **分析页面结构**

   * 抓取作品列表页 `<div class="item photo">`
   * 提取：

     * `title` 属性 → 作品标题
     * `style` 属性内 `background-image:url(...)` → 图片路径模板
     * `<div class="tags"><div>74P</div></div>` → 图片总数

2. **生成所有原图 URL**

   * 自动替换 `_600x0.webp` 为 `.jpg`
   * 推算完整序列：`0001.jpg` ~ `0074.jpg`

3. **分页处理**

   * 自动访问 `/2.html`, `/3.html`...
   * 若无 `<div.item.photo>` 元素则停止

4. **异步下载**

   * 使用 `ThreadPoolExecutor` 并发执行下载任务
   * 同步 CSV 写入，保证数据完整性

---

## ⚠️ 注意事项

* 若页面被 Cloudflare 拦截，可：

  * 使用 `undetected_chromedriver`
  * 或提前手动验证一次 Cloudflare
* 若目标网站更新结构，请同步调整 CSS 选择器：

  ```python
  'div.item.photo', 'a[href^="/photo/id-"]', 'div.img', 'div.tags > div'
  ```
* 如需中途暂停任务，可安全关闭程序；下次运行会继续抓取尚未存在的文件。

---

## 🧱 可选增强功能

| 功能                 | 描述                              |
| ------------------ | ------------------------------- |
| ✅ 断点续传             | 检测 CSV / 本地文件跳过已完成作品            |
| ✅ Excel 输出         | 每个模特一个 `.xlsx` 文件，每个作品一个 Sheet  |
| ✅ 自动 Cloudflare 绕过 | 结合 `undetected_chromedriver` 实现 |
| ✅ 爬取视频页            | 支持 `/videos/model-xxxx.html` 区域 |

---

## 📜 License

本项目仅供学习与研究使用，请勿将爬取数据用于商业用途或违反目标网站的服务条款。
作者不对任何非法使用行为承担责任。

---

**作者：fuaneng**

> 世界顶级 Selenium 自动化工程师
> “让浏览器为你工作，而不是相反！”

```

---

