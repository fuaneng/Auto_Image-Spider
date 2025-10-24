
# 🖼️ Imgur 多线程图片爬虫

> 使用 **Selenium + Requests + Redis + 多线程** 构建的高性能图片爬虫，可批量抓取 [Imgur](https://imgur.com/) 各标签下的热门图片数据，并自动保存为 CSV 文件。
> 💾 支持实时写入、Redis 去重、分页抓取、无头浏览器模拟访问等功能。

---

## 🚀 功能概述

* ✅ **Selenium 自动访问主页**（防止被封）
* ✅ **多线程抓取**（默认 20 线程）
* ✅ **调用 Imgur 官方 API 接口**
* ✅ **分页爬取至数据为空或返回 404**
* ✅ **Redis / 内存 去重机制**
* ✅ **实时写入 CSV 文件**
* ✅ **线程安全写入（Lock）**
* ✅ **异常捕获与健壮性设计**

---

## 📁 项目结构

```bash
ImgurCrawler/
├── crawler_imgur.py          # 主程序文件（爬虫核心）
├── README.md                 # 使用说明文档
├── requirements.txt          # 依赖库列表
└── data/
    ├── imgur/                # 存放 CSV 数据
    └── libreshot/
        └── ram_tag_list_备份.txt   # 存放标签(tag)列表
```

---

## ⚙️ 环境依赖

请确保系统已安装以下组件：

| 依赖            | 说明               |
| ------------- | ---------------- |
| Python ≥ 3.8  | 推荐使用 3.8+ 版本     |
| Google Chrome | 浏览器              |
| ChromeDriver  | 与 Chrome 版本对应的驱动 |
| Redis Server  | 可选（用于全局 URL 去重）  |

---

## 📦 安装依赖

```bash
pip install selenium requests redis urllib3
```

---

## 🧠 运行逻辑说明

1. **Selenium 初始化：**

   * 启动 Chrome 浏览器（无头模式）
   * 打开主页：[https://imgur.com/](https://imgur.com/)

2. **读取标签文件：**

   * 从 `ram_tag_list_备份.txt` 中读取每一行标签
     例如：

     ```
     girl
     nature
     cat
     ```

3. **API 请求逻辑：**

   * 每个标签的请求 URL：

     ```
     https://api.imgur.com/post/v1/posts/t/{tag}?client_id=d70305e7c3ac5c6&filter%5Bwindow%5D=week&include=adtiles%2Cadconfig%2Ccover&location=desktoptag&page={页数}&sort=-viral
     ```
   * 返回 JSON 数据，根据 `"mime_type"` 判断是否为图片

4. **数据提取：**

   * 仅保存 `"image/*"` 类型
   * 提取字段：

     * `title` → 图片标题
     * `cover.url` → 图片链接
     * `basename(url)` → 图片文件名

5. **结果存储：**

   * 数据实时写入 CSV 文件
   * 文件路径示例：

     ```
     D:\myproject\Code\爬虫\爬虫数据\imgur\imgur_data.csv
     ```
   * CSV 格式：
     | Title | ImageName | URL | TAG |

6. **去重机制：**

   * 优先使用 Redis Set：`imgur_image_url_set`
   * 若 Redis 不可用，则使用内存集合去重

---

## 🔧 配置项

在脚本中你可自定义以下参数：

| 变量名                  | 默认值                                                              | 说明                 |
| -------------------- | ---------------------------------------------------------------- | ------------------ |
| `CHROME_DRIVER_PATH` | `r'C:\Program Files\Google\chromedriver-win64\chromedriver.exe'` | ChromeDriver 路径    |
| `TAG_FILE_PATH`      | `D:\myproject\Code\爬虫\爬虫数据\libreshot\ram_tag_list_备份.txt`        | 标签文件路径             |
| `CSV_DIR_PATH`       | `D:\myproject\Code\爬虫\爬虫数据\imgur`                                | CSV 输出目录           |
| `CLIENT_ID`          | `d70305e7c3ac5c6`                                                | Imgur 公共 client_id |
| `REDIS_HOST`         | `localhost`                                                      | Redis 主机           |
| `REDIS_PORT`         | `6379`                                                           | Redis 端口           |
| `max_workers`        | `20`                                                             | 线程池并发数             |

---

## ▶️ 运行示例

```bash
python crawler_imgur.py
```

运行日志示例：

```
🌐 Selenium 已成功访问 Imgur 主页
✅ Redis 连接成功，使用 Redis 去重。
🚀 开始抓取标签: girl
[girl] ✅ Robyn the Guard (Miltonius' Akumi fanart) [by me] | https://i.imgur.com/C1WRtaf.jpeg
[girl] ⚙️ 已存在: https://i.imgur.com/C1WRtaf.jpeg
[girl] 🛑 无更多数据，结束。
🎉 所有任务已完成！
```

---

## 🧩 核心方法说明

| 方法                           | 功能描述                    |
| ---------------------------- | ----------------------- |
| `init_selenium()`            | 启动无头浏览器访问主页             |
| `fetch_tag_page(tag, page)`  | 调用 Imgur API 获取 JSON 数据 |
| `parse_and_save(posts, tag)` | 提取图片信息并写入 CSV           |
| `write_to_csv()`             | 线程安全写入 CSV 文件           |
| `is_duplicated(url)`         | Redis/内存去重逻辑            |
| `crawl_tag(tag)`             | 分页抓取单个标签                |
| `run(tags, max_workers)`     | 多线程启动任务                 |

---

## 🧰 Redis 去重逻辑示例

```python
self.redis.sadd('imgur_image_url_set', img_url)
if self.redis.sismember('imgur_image_url_set', img_url):
    # 已存在则跳过
```

如果 Redis 不可连接，程序会自动使用内存去重集合：

```python
self.visited_urls = set()
```

---

## ⚠️ 注意事项

* 建议使用稳定网络环境，Imgur API 对速率有限制；
* 若需要下载图片，可扩展 `parse_and_save()` 中的逻辑；
* 若不想使用 Selenium，可直接注释掉 `init_selenium()`；
* Redis 未启动时不会报错，只会提示“改用内存去重”。

---

