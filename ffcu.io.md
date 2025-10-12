# FFCU 图片爬虫项目

## 🎯 项目目标

本项目是一个基于 Python 和 Selenium 框架构建的爬虫程序，用于自动化爬取 `ffcu.io` 网站上特定标签（Tag）下的图片信息。

**核心目标：**

* 根据标签列表自动搜索并遍历所有结果页。
* 安全、平滑地滚动页面，确保懒加载（Lazy Loading）图片完全加载。
* 提取每张图片的标题、原始 URL 等信息。
* 使用 Redis 或内存集合进行高效去重，避免重复存储。
* 将最终结果数据保存到 CSV 文件中。

---

## 🛠️ 技术栈与依赖

本项目使用以下主要技术：

| 技术 | 描述 |
| :--- | :--- |
| **Python** | 主要编程语言 |
| **Selenium** | 自动化浏览器操作，处理动态内容和懒加载 |
| **Chrome / ChromeDriver** | 用于 Selenium 控制的浏览器及其驱动 |
| **Redis** | 可选，用于高效、持久化的去重集合 |
| **CSV** | 用于数据存储 |
| **Threading** | 用于 CSV 文件写入的线程安全锁 |

### 依赖安装

请确保你的环境中已安装 Python 3.x，并通过 `pip` 安装所需的库：

```bash
pip install selenium redis
````

### 浏览器驱动配置

1.  下载与你当前 Chrome 浏览器版本匹配的 **ChromeDriver**。
2.  将 `chromedriver.exe` 放置在你本地可访问的路径。
3.  在代码的 `if __name__ == '__main__':` 块中，更新 `chrome_driver_path` 变量为你实际的驱动路径。

<!-- end list -->

```python
if __name__ == '__main__':
    # ⚠️ 请将此路径替换为你本地的 ChromeDriver 路径
    chrome_driver_path = r'C:\Program Files\Google\1\chromedriver-win32\chromedriver.exe'
    # ...
```

-----

## 🚀 使用指南

### 1\. 配置路径

在 `ffcu` 类的 `main` 方法中，根据你的环境修改以下文件路径：

```python
def main(self):
    # 数据保存目录
    save_dir = r'D:\work\爬虫\爬虫数据\ffcu'
    # 标签列表文件路径 (每行一个标签)
    tag_file_path = r'D:\work\爬虫\ram_tag_list.txt'
    # CSV 导出文件路径
    csv_path = os.path.join(save_dir, 'all_records_ffcu_01.csv')
    # ...
```

### 2\. 准备标签文件

创建一个文本文件（例如 `ram_tag_list.txt`），每行填写一个你希望爬取的搜索关键词或标签：

```
tag_a
tag_b
another tag
```

### 3\. 运行程序

直接运行 Python 脚本：

```bash
python your_script_name.py
```

程序将在终端打印详细的运行日志，包括：Redis 连接状态、标签处理进度、滚动加载过程、重复项跳过信息以及最终写入结果。

-----

## 核心技术点解析

### 1\. 平滑滚动加载 (Anti-Bot/Anti-Lost)

为解决懒加载图片因滚动过快而丢失的问题，采用了分步平滑滚动策略。

  * **实现位置：** `ffcu.get_images` 方法
  * **机制：** 不再使用 `window.scrollTo(0, document.body.scrollHeight)` 一次到底，而是每 2.0 秒向下滚动 **1080 像素**（`SCROLL_HEIGHT`），模拟人类操作，确保图片请求和渲染完成。

<!-- end list -->

```python
# 核心滚动逻辑片段
SCROLL_HEIGHT = 1080
SCROLL_PAUSE_TIME = 2.0

# ...
# 执行滚动
self.driver.execute_script(f"window.scrollTo(0, {new_scroll_position});")
# 暂停等待加载
time.sleep(SCROLL_PAUSE_TIME + random.random() * 0.5)
# ...
```

### 2\. 健壮的元素定位与 URL 提取

针对页面中图片元素类名可能因排序或懒加载状态而不同的问题，采用了通用定位方法，并扩展了 URL 属性的获取范围。

  * **通用定位：** 使用 `card_ele.find_element(By.TAG_NAME, 'img')`，忽略所有冗余或变化的 CSS 类名。
  * **多属性 URL 提取：** 确保能捕获到 `src`、`data-src`、`data-original` 等所有可能的链接属性。

<!-- end list -->

```python
# 核心提取逻辑片段
img_ele = card_ele.find_element(By.TAG_NAME, 'img')

image_url = (img_ele.get_attribute('src')
             or img_ele.get_attribute('data-src')       
             or img_ele.get_attribute('data-original')
             or img_ele.get_attribute('data-lazy-src')
             or "")
```

### 3\. 高效去重机制

使用 MD5 哈希值对清理后的图片 URL 进行唯一性检查。

  * **优先使用 Redis：** 如果 Redis 可用，使用 `SET` 结构进行持久化和高效的跨进程去重。
  * **降级到内存：** 如果 Redis 不可用，则降级使用内存 `set()` (`self.visited_md5`) 进行会话级别去重。

### 4\. 线程安全的 CSV 写入

使用 `threading.Lock` 确保在并发环境中，对 CSV 文件的写入操作是原子性的和线程安全的，防止数据损坏。

```python
# 核心写入逻辑片段
with self.csv_lock:
    # ... 写入文件操作 ...
```

-----

## 🔍 调试输出示例

程序在运行时会提供详细的日志，帮助你追踪爬取进度和去重效果：

```
✅ Redis 连接成功。
--- 发现 1 个标签 ---

--- 开始处理：【tag_test】 ---
URL: [https://ffcu.io/?s=tag_test](https://ffcu.io/?s=tag_test)
[√] 主图片容器加载完成。
🚀 开始分步滚动加载 (每步 1080px，暂停 2.0秒)...
✅ 滚动到底部。总共滚动了 4 次。
🖼️ 共检测到 10 个图片容器。

✔️ 写入成功！【图片标题 A】
[重复] 容器序号 1：【图片标题 B】URL ... 已存在，跳过。
✔️ 写入成功！【图片标题 C】
[重复] 容器序号 3：【图片标题 D】URL ... 已存在，跳过。
✔️ 写入成功！【图片标题 E】
✔️ 写入成功！【图片标题 F】
[重复] 容器序号 6：【图片标题 G】URL ... 已存在，跳过。
[重复] 容器序号 7：【图片标题 H】URL ... 已存在，跳过。
[重复] 容器序号 8：【图片标题 I】URL ... 已存在，跳过。
[重复] 容器序号 9：【图片标题 J】URL ... 已存在，跳过。

✅ 【tag_test】本页共检测 10 个容器，成功写入 4 条记录。
[完成] 【tag_test】共爬取 1 页。

正在关闭浏览器...
```

```
```