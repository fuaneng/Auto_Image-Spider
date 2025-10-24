
# typographicposters API 爬虫

## 简介

本项目是一个使用 Python 的 `requests` 库和 `redis` 库来爬取 Typographic Posters 网站海报数据的工具。它通过直接请求网站的 API 接口，高效地获取海报的标题和原图链接，并将数据存储到本地 CSV 文件中，同时利用 Redis 实现 URL 去重。

**主要功能：**

  * 通过 API 实现分页爬取，速度快。
  * 基于 URL 路径组合出完整的原图链接。
  * 使用 Redis 数据库进行高效的链接去重。
  * 将爬取结果存储为 UTF-8 编码的 CSV 文件。

## 环境要求

### 依赖库

您需要安装以下 Python 库：

```bash
pip install requests redis
```

### 数据库

项目使用 **Redis** 进行去重。请确保您的本地或远程 Redis 服务器正在运行，并且可以通过 `localhost:6379` 访问。

## 配置文件和常量说明

主要的配置都在代码文件的顶部定义。请根据您的需求修改以下常量：

| 常量名 | 默认值 | 说明 |
| :--- | :--- | :--- |
| `API_BASE_URL` | `'https://www.typographicposters.com/api/tg/posters-recent'` | 目标 API 的基础 URL。 |
| `IMAGE_BASE_URL` | `'https://videos.typographicposters.com/poster-p3'` | 用于拼接完整原图 URL 的域名和前缀。 |
| `TAG_NAME` | `'NAN'` | 存储到 CSV 文件中的标签字段值。 |
| `ITEMS_PER_PAGE` | `32` | 每次 API 请求返回的海报数量。 |
| `START_PAGE` | `1` | 爬取开始的页码。 |
| `MAX_PAGES` | `5` | 爬取结束的页码（含）。 |
| `PAGE_SLEEP` | `3` | 两次 API 请求之间的休眠时间（秒）。 |

**Redis 配置：**

在 `typographicposters.__init__` 方法中配置 Redis 连接：

```python
self.redis = redis.Redis(host='localhost', port=6379, db=0, decode_responses=True)
# ...
self.redis_key = 'image_md5_set_eiginleiki' # 用于去重的 Set 键名
```

## 运行指南

### 1\. 准备工作

1.  确保您已安装所有[依赖库](https://www.google.com/search?q=%23%E4%BE%9D%E8%B5%96%E5%BA%93)。

2.  确保您的 Redis 服务器正在运行。

3.  根据您的需求修改代码顶部的[配置常量](https://www.google.com/search?q=%23%E9%85%8D%E7%BD%AE%E6%96%87%E4%BB%B6%E5%92%8C%E5%B8%B8%E9%87%8F%E8%AF%B4%E6%98%8E)。

4.  修改 `if __name__ == '__main__':` 块中的 CSV 文件保存路径：

    ```python
    save_dir = r'R:\py\Auto_Image-Spider\Typographicposters\data'
    csv_path = os.path.join(save_dir, 'all_typographicposters_api.csv') 
    ```

### 2\. 执行爬虫

1.  打开命令行或终端。

2.  导航到包含 Python 文件的目录。

3.  运行以下命令：

    ```bash
    python your_script_name.py
    ```

    替换 `your_script_name.py` 为您的 Python 文件名称。

### 3\. 查看结果

1.  检查 `save_dir` 目录下是否生成了 `all_typographicposters_api.csv` 文件。

2.  打开该文件，使用文本编辑器（如 Notepad++、Excel 等）查看提取到的海报数据。

    数据格式：

    ```csv
    title,name,url,tag
    海报标题1,文件名1.jpg,https://videos.typographicposters.com/poster-p3/文件名1.jpg,NAN
    海报标题2,文件名2.jpg,https://videos.typographicposters.com/poster-p3/文件名2.jpg,NAN
    ```

## 代码结构说明

项目主要由一个核心类 `typographicposters` 组成，负责整个爬取流程。

### `class typographicposters`

#### `__init__(self)`

初始化类实例。设置 HTTP 请求头、初始化 Redis 连接。如果 Redis 连接失败，程序会发出警告并关闭去重功能，不影响数据写入。

#### `_get_full_image_url(self, image_path)`

**核心逻辑：** 负责将 API 返回的相对路径（如 `/dir/image.jpg`）与 `IMAGE_BASE_URL` 拼接，生成完整的可访问图片 URL。

#### `write_to_csv(self, title, name, url, csv_path, tag)`

将提取到的数据（标题、文件名、URL 和标签）追加写入到指定的 CSV 文件中。包含文件头（Header）的自动创建逻辑。

#### `process_page(self, api_url, tag, csv_path, page_num)`

处理单个 API 页面的核心方法：

1.  使用 `requests.get` 发送 API 请求，并禁用系统代理 (`proxies=None`)，设置超时。
2.  解析返回的 JSON 数据，提取 `hits` 数组。
3.  遍历 `hits` 中的每一项，提取 `title` 和 `image.path`。
4.  使用 `_get_full_image_url` 组合出最终 URL。
5.  对最终 URL 进行 MD5 哈希计算，通过 Redis 进行去重检查。
6.  将去重后的数据写入 CSV 文件。

#### `run(self, api_base_url, tag, csv_path)`

主运行函数：

1.  根据 `START_PAGE` 和 `MAX_PAGES` 循环遍历目标页码。
2.  构建带 `page` 和 `itemsPerPage` 参数的完整 API URL。
3.  调用 `process_page` 处理当前页数据。
4.  在每次请求间休眠，防止请求过于频繁。

## 故障排除

| 错误信息 | 原因分析 | 解决方案 |
| :--- | :--- | :--- |
| `...ProxyError: 'Unable to connect to proxy', Read timed out...` | 系统环境变量中配置了错误的代理。 | 在 `process_page` 的 `requests.get` 中显式设置 `proxies=None`（代码已修正）。 |
| `redis.exceptions.ConnectionError...` | Redis 服务器未启动或连接配置错误。 | 确保 Redis 服务已运行，并检查 `__init__` 中的 `host` 和 `port` 配置。 |
| `requests.exceptions.HTTPError: 404 Client Error` | `API_BASE_URL` 或分页参数错误。 | 检查 `API_BASE_URL` 是否正确，或尝试在浏览器中手动访问生成的 `api_url` 确认是否能返回数据。 |
| `json.JSONDecodeError` | API 响应不是有效的 JSON 格式。 | 检查 API 响应，可能目标网站启用了反爬虫机制，返回了 HTML 或其他格式的内容。 |