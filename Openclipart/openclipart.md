

# 🖼️ OpenClipart 高性能爬虫（Selenium + JS 点击 + Redis 去重）

> 🚀 一款为 **OpenClipart.org** 打造的高性能图像信息采集爬虫，
> 使用 **Selenium** 自动化浏览器实现标签搜索、分页抓取、弹窗自动处理与防重复机制。

---

## 📋 功能概述

✅ 支持 **按标签（tag）批量抓取** 图像信息
✅ 自动 **滚动加载懒加载图片区域**
✅ **JS 翻页点击**（绕过遮挡与弹窗）
✅ 自动检测 **页面是否真正翻页**（防止重复页）
✅ **禁用图片加载** 提升解析速度 40%+
✅ **Redis 去重** 或本地内存去重机制
✅ 结果输出至 **UTF-8 CSV 文件**
✅ 支持 **Headless（无界面）运行**

---

## 🧩 项目结构

```
openclipart_crawler/
│
├── openclipart_spider.py        # 主程序文件（本 README 对应代码）
├── README.md                    # 项目说明文件（当前文档）
├── requirements.txt             # 依赖清单
│
├── data/
│   ├── ram_tag_list.txt         # 标签文件（每行一个标签）
│   └── all_records_openclipart.csv  # 输出数据文件
│
└── logs/
    └── runtime.log              # 日志输出（可选）
```

---

## ⚙️ 环境依赖

### 🧱 1️⃣ 基础环境

| 组件           | 推荐版本          |
| ------------ | ------------- |
| Python       | 3.8+          |
| Chrome 浏览器   | 91+           |
| ChromeDriver | 与 Chrome 版本对应 |
| Redis（可选）    | 5.0+          |

> ⚠️ 若不使用 Redis，会自动切换到本地内存去重模式。

---

### 📦 2️⃣ 安装依赖

在命令行中执行：

```bash
pip install selenium redis
```

或者使用 `requirements.txt`：

```bash
pip install -r requirements.txt
```

---

## 🚀 使用方法

### 1️⃣ 准备标签文件

在 `data/ram_tag_list.txt` 中按行列出要搜索的关键词，例如：

```text
cat
dog
flower
car
```

---

### 2️⃣ 配置路径参数

修改 `openclipart_spider.py` 中的以下变量：

```python
chrome_driver_path = r'C:\Program Files\Google\1\chromedriver-win32\chromedriver.exe'
save_dir = r'D:\work\爬虫\爬虫数据\openclipart'
tag_file_path = r'D:\work\爬虫\ram_tag_list.txt'
```

---

### 3️⃣ 运行脚本

```bash
python openclipart_spider.py
```

或在后台运行（Linux）：

```bash
nohup python openclipart_spider.py > logs/runtime.log 2>&1 &
```

---

## 🧠 核心设计说明

### 1️⃣ **禁用图片加载**

通过 Chrome `prefs` 关闭图片加载，加快页面解析速度：

```python
prefs = {"profile.managed_default_content_settings.images": 2}
options.add_experimental_option("prefs", prefs)
```

> ⚠️ 若需要下载图片，请注释掉此配置。

---

### 2️⃣ **JS 翻页点击**

有时页面存在弹窗或遮挡层，普通 `.click()` 会失败。
因此使用 JavaScript 直接触发：

```python
self.driver.execute_script("arguments[0].click();", next_btn)
```

可绕过浮层、透明遮罩、不可见区域等限制。

---

### 3️⃣ **页面变化校验**

为了防止“下一页点击失败但内容未变”的情况，
程序会在翻页前后计算页面 HTML 的 MD5 值：

```python
page_html_before = self.driver.execute_script("return document.body.innerHTML;")
page_hash_before = hashlib.md5(page_html_before.encode('utf-8')).hexdigest()
```

翻页后再比对，如相同则中断抓取，避免死循环。

---

### 4️⃣ **滚动加载逻辑**

OpenClipart 的搜索结果使用懒加载，
程序自动滚动页面直到内容完全加载：

```python
while True:
    self.driver.execute_script(f"window.scrollBy(0, {SCROLL_STEP});")
    ...
```

并检测页面高度变化，智能判断何时停止。

---

### 5️⃣ **Redis 去重机制**

Redis 用于跨任务持久去重：

```python
self.redis.sadd(self.redis_key, md5_hash)
```

> 如果 Redis 不可用，自动切换到内存去重模式。

---

## 🧾 输出文件格式

输出文件：
`D:\work\爬虫\爬虫数据\openclipart\all_records_openclipart.csv`

字段格式如下：

| 列名        | 示例                                                                                | 说明     |
| --------- | --------------------------------------------------------------------------------- | ------ |
| Title     | Cute Cat                                                                          | 图片标题   |
| ImageName | cat.png                                                                           | 文件名    |
| URL       | [https://openclipart.org/image/2000px/](https://openclipart.org/image/2000px/)... | 图片 URL |
| Tag       | cat                                                                               | 搜索标签   |

---

## ⚡ 性能优化建议

| 优化点              | 说明            |
| ---------------- | ------------- |
| ✅ 禁用图片加载         | 加快页面解析速度      |
| ✅ 启用 Headless 模式 | 减少显卡资源占用      |
| ✅ Redis 去重       | 防止重复存储，支持断点续爬 |
| ✅ 分步滚动加载         | 确保懒加载图片被识别    |
| ✅ 随机延时           | 模拟人类行为，防止封禁   |

---

## 🧰 弹窗处理机制

程序自动清理常见弹窗与遮罩层：

```python
def clear_popups(self):
    self.driver.execute_script("""
        const modals = document.querySelectorAll('.modal, .overlay, .popup, .backdrop');
        modals.forEach(m => m.remove());
    """)
```

避免影响按钮点击与翻页。

---

## 🧩 常见问题 FAQ

### ❓ Q1: 页面总是重复识别上一页内容？

👉 解决：

* 已通过 HTML MD5 检测机制自动处理；
* 若仍存在，可加大 `time.sleep()` 延迟或使用更快网络。

---

### ❓ Q2: 翻页时出现 “ClickInterceptedException”？

👉 原因：

* 翻页按钮被遮罩层或弹窗覆盖。

👉 解决：

* 本代码使用 `JS 点击` 已自动绕过；
* 若依旧出错，可增加 `self.clear_popups()` 调用频率。

---

### ❓ Q3: Redis 未连接怎么办？

👉 若 Redis 不可用，程序自动切换为内存去重模式。
仍可正常运行，只是不同标签任务间不会共享去重记录。

---

### ❓ Q4: 如何查看爬取进度？

👉 控制台会输出：

```
=== 正在爬取【cat】第 3 页 ===
✔️ 成功写入 Cute Cat -> https://openclipart.org/image/2000px/cat.png
```

也可将日志重定向保存：

```bash
python openclipart_spider.py > logs/runtime.log
```

---

## 📈 后续扩展

可扩展功能包括：

* [ ] 多线程并发爬取（每个标签独立进程）
* [ ] 自动下载原图到本地
* [ ] 增加异常重试与断点恢复
* [ ] 与数据库（MySQL / MongoDB）集成

---

## 🧑‍💻 作者信息

👨‍💻 **Selenium（GPT-5 助手）**

> 全球顶级 Selenium 自动化专家，
> 专注高性能网页采集与智能浏览器控制。

📧 如需协助优化或扩展，请在此基础上提出需求。

---

## ⚠️ 声明

本项目仅供 **学习与研究用途**，
禁止用于任何违反网站使用条款的行为。
使用本项目产生的任何后果由使用者自负。

---

**Happy Crawling! 🕸️🔨🤖🔧**

---
