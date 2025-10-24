
# ArtStation 解耦式异步多线程爬虫

本项目基于 Python 和 Selenium，实现了多线程并发爬取 'https://www.artstation.com/' 搜索结果页和详情页图片链接的功能。通过将爬虫实例（Selenium 浏览器）与线程解耦，并利用任务队列进行任务分配，大大提高了数据采集效率。

## 🚀 核心特性

  * **多线程并发 (异步)**：默认开启 3 个独立的 Selenium 实例（可配置），并行处理不同的标签搜索任务。
  * **任务队列解耦**：使用 `queue.Queue` 管理待爬取标签列表，实现线程间的任务安全分配。
  * **线程安全资源管理**：使用 `threading.Lock` 确保 CSV 文件写入的原子性，并利用 Redis 或内存集合进行全局去重。
  * **二级页面深度爬取**：成功访问搜索结果中的每一个作品详情页，提取所有高清图片 URL。

## 💻 项目结构和运行

### 环境依赖

```bash
pip install selenium redis
# 确保你的环境中安装了 Chrome 浏览器，并配置了对应的 ChromeDriver 路径。
```

### 关键配置

在 `if __name__ == '__main__':` 代码块中，你需要配置以下变量：

```python
# --- 配置项 ---
CHROME_DRIVER_PATH = r'C:\Program Files\Google\chromedriver-win32\chromedriver.exe' # 你的 Chrome Driver 路径
SAVE_DIR = r'D:\work\爬虫\爬虫数据\artstation'
TAG_FILE_PATH = r'D:\work\爬虫\ram_tag_list_备份.txt'
MAX_WORKERS = 3  # 默认开启 3 个线程/Selenium 实例（解耦实例数量）
```

## ⚙️ 最重要的实现：二级页面爬取（详情页）

二级页面爬取是本项目获取最终图片 URL 的核心步骤。由于 ArtStation 在搜索结果页（一级页面）只展示缩略图，我们需要进入每个作品的详情页（二级页面）来提取所有清晰的图片链接。

这一逻辑主要集中在 `ArtStationSpider.get_images()` 和 `ArtStationSpider.extract_detail_page()` 方法中。

### 1\. 从一级页面获取详情页链接 (`get_images` 方法)

在滚动加载完搜索结果后，`get_images` 方法负责遍历所有作品卡片，并依次访问其对应的详情页：

```python
# 核心代码片段 (ArtStationSpider.get_images)
for idx, card in enumerate(cards, start=1):
    try:
        href = card.get_attribute("href")
        
        # 1. 在新标签页打开详情页，避免丢失当前搜索页面的状态
        self.driver.execute_script("window.open(arguments[0]);", href)
        self.driver.switch_to.window(self.driver.window_handles[-1])

        time.sleep(random.uniform(1.2, 2.5))
        
        # 2. 调用核心的详情页提取方法
        self.extract_detail_page(tag) 

        # 3. 关闭当前详情页标签，切换回搜索页
        self.driver.close()
        self.driver.switch_to.window(self.driver.window_handles[0])

    except Exception as e:
        # 错误处理逻辑
        pass
```

**关键点说明：**

  * **新标签页打开**：使用 `self.driver.execute_script("window.open(arguments[0]);", href)` 在新的浏览器标签页中打开详情页，保持原搜索页面（一级页面）的状态，避免因页面跳转导致的 DOM 元素丢失。
  * **窗口切换**：通过 `self.driver.switch_to.window(self.driver.window_handles[-1])` 切换到最新打开的标签页进行操作。
  * **返回和清理**：完成详情页提取后，必须调用 `self.driver.close()` 关闭当前标签页，并使用 `self.driver.switch_to.window(self.driver.window_handles[0])` 切换回主窗口，继续遍历剩余的作品卡片。

### 2\. 在二级页面提取图片数据 (`extract_detail_page` 方法)

这是实际提取图片 URL 和去重的地方：

```python
# 核心代码片段 (ArtStationSpider.extract_detail_page)
def extract_detail_page(self, tag: str):
    # ... (等待页面加载逻辑)
    
    # 查找所有图片容器
    picture_eles = self.driver.find_elements(By.CSS_SELECTOR, "main.project-assets picture.d-flex")

    for pic in picture_eles:
        try:
            # 提取 img 标签的 src 属性
            img_ele = pic.find_element(By.CSS_SELECTOR, "img.img.img-fluid.block-center.img-fit")
            image_url = img_ele.get_attribute("src")
            title = img_ele.get_attribute("alt") or self.driver.title.split(' - ')[0]

            image_url_cleaned = re.sub(r'\?.*$', '', image_url)
            md5_hash = hashlib.md5(image_url_cleaned.encode('utf-8')).hexdigest()

            # 检查去重 (使用 Redis 或内存集合)
            if self.is_duplicate(md5_hash):
                continue

            # 写入 CSV (线程安全操作)
            self.write_to_csv(title, image_name, image_url_cleaned, tag)
            
        except NoSuchElementException:
            continue
```

**关键点说明：**

  * **图片元素定位**：使用 CSS 选择器定位到 ArtStation 详情页中的图片容器（`main.project-assets picture.d-flex`），然后从中提取实际的 `img` 标签及其 `src` 属性。
  * **URL 清理与去重**：ArtStation 的图片 URL 常常带有查询参数（如 `?q=...`），需要通过 `re.sub(r'\?.*$', '', image_url)` 清理 URL，然后计算 MD5 进行**准确去重**。
  * **线程安全写入**：调用 `self.write_to_csv` 方法时，内部使用了 `threading.Lock` 锁，确保多个并发线程在写入同一个 CSV 文件时不会互相干扰，避免数据损坏。

## 🧵 异步多线程实现 (`spider_worker` 函数)

异步爬取的实现是通过将 `ArtStationSpider` **类解耦**，并封装在 `spider_worker` 函数中实现的。

1.  **任务队列初始化 (主程序)**：

    ```python
    TAG_QUEUE: Queue[str] = Queue()
    # ... 将所有标签放入 TAG_QUEUE.put(tag)
    ```

2.  **线程启动 (主程序)**：

    ```python
    for i in range(MAX_WORKERS):
        thread_name = f"SpiderWorker-{i+1}"
        thread = threading.Thread(
            target=spider_worker,
            args=(TAG_QUEUE, CHROME_DRIVER_PATH, CSV_PATH, CSV_LOCK, REDIS_CONN),
            name=thread_name
        )
        thread.start()
    ```

3.  **任务循环 (spider\_worker)**：

    ```python
    # 线程工作函数的核心循环
    while not tag_queue.empty():
        tag = tag_queue.get() # 阻塞地获取任务
        # ... 爬取逻辑
        tag_queue.task_done() # 任务完成通知
    ```

**结果：** 每个线程都是一个独立的执行单元，拥有自己的 Chrome 实例，不断从共享队列中拉取任务，从而实现高效的解耦式异步并发爬取。