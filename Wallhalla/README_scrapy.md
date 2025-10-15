
# 🤖 Wallhalla Scraper (壁紙爬蟲專案)

## 📖 專案概述

`Wallhalla Scraper` 是一個基於強大的 **Scrapy** 框架（Python）開發的高性能爬蟲。本專案的目標是根據預設的關鍵字列表，從 **wallhalla.com** 網站上自動搜索、提取高清壁紙的詳細資訊，並將圖片下載至本地，同時將元數據（如標題、標籤、URL）結構化地保存為 CSV 文件。

本專案特別優化了解決網站的 **多重重定向** 和 **初始請求去重** 問題，確保在高并发下能穩定工作。

## 🛠️ 安裝與環境準備

### 1\. 環境要求

確保你的系統已安裝 Python 3.8+。

  * **Python 版本:** 3.8+
  * **Scrapy 版本:** 2.12.0+ (或其他相容版本)

### 2\. 安裝依賴

在專案的根目錄下（例如 `wallhalla_scraper/`），運行以下命令安裝所需的 Python 套件：

```bash
# 請安裝相關的依賴
pip install scrapy

# 执行创建爬虫工作目录
scrapy scrapy startproject wallhalla_scraper

# 进入项目目录
cd wallhalla_scraper

# 执行爬虫
scrapy crawl wallhalla


```

## ⚙️ 專案配置

主要配置文件位於 `wallhalla_scraper/settings.py`。

### 1\. 配置標籤列表 (`TAG_FILE_PATH`)

你需要創建一個純文本文件（例如 `tags.txt`），每行包含一個你想要搜索的關鍵字。

在 `settings.py` 中配置該文件的路徑：

```python
# settings.py
# 🚨 确保此路径指向你的标签文件，每行一个关键词
TAG_FILE_PATH = 'D:/work/爬虫/爬虫数据/wallhalla/tags.txt' 

# ... 
```

### 2\. 配置數據存儲路徑

配置圖片文件和 CSV 文件的存儲位置。

```python
# settings.py

# 圖片文件存儲目錄 (FilesPipeline 使用)
# 🚨 请将其指向你的共享或本地存储目录
FILES_STORE = r'\\10.58.134.120\aigc2\01_数据\爬虫数据\wallhalla\images' 

# CSV 文件输出路径 (WallhallaCSVPipeline 使用)
# 🚨 请将其指向你的 CSV 存储路径
CSV_FILE_PATH = r'\\10.58.134.120\aigc2\01_数据\爬虫数据\wallhalla\all_records_wallhalla_scrapy.csv'

# ...
```

### 3\. 并发与速度优化 (针对大量标签)

由於本專案可能處理數千個標籤，建議配置以下參數以提高穩定性和效率：

```python
# settings.py

# 降低并发请求数，以避免触发服务器 500 错误
CONCURRENT_REQUESTS = 4 

# 增加下载延迟，模拟人类行为，减轻服务器压力
DOWNLOAD_DELAY = 5      
RANDOMIZE_DOWNLOAD_DELAY = True

# 每个域名的最大并发连接数
CONCURRENT_REQUESTS_PER_DOMAIN = 1 

# 启用 FilesPipeline 和 WallhallaCSVPipeline
ITEM_PIPELINES = {
    'wallhalla_scraper.pipelines.WallhallaFilePipeline': 100,
    'wallhalla_scraper.pipelines.WallhallaCSVPipeline': 300, 
}
```

## 🚀 運行爬蟲

在專案的根目錄（包含 `scrapy.cfg` 的目錄）下，運行以下命令啟動爬蟲：

```bash
scrapy crawl wallhalla
```

## ⚙️ 核心爬取邏輯 (`wallhalla_spider.py`)

本爬蟲採用了精確的三步走策略，以應對網站的反爬和複雜重定向：

### 1\. `start_requests` (起始請求)

  * **功能：** 讀取 `tags.txt` 文件中的所有標籤。
  * **關鍵優化：** 為每個標籤生成一個對 `base_url` (首页) 的請求，並設置 `dont_filter=True`。這確保了即使多個標籤的初始 URL 相同，**Scrapy 也不會將其去重**，從而保證所有標籤都能開始爬取流程。

### 2\. `parse_home_page` (模擬搜索)

  * **功能：** 成功訪問首頁後，模擬瀏覽器通過首頁搜索框提交搜索的行為。
  * **關鍵優化：** 發送 `/search?q={tag}` 請求時，**顯式地添加 `Referer` HTTP 頭**，將其設置為剛訪問的**首頁 URL**。這解決了網站因缺少 `Referer` 而將搜索重定向回無參數首頁的問題。

### 3\. `parse_search_page` (處理重定向與解析)

  * **功能：** 處理搜索結果頁面。
  * **關鍵優化：** 檢查響應狀態碼，如果捕獲到 `301/302` 重定向，則手動檢查目標 URL，確保是正確的搜索結果頁面，然後再發送新的請求。這使得爬蟲能夠穩定地從重定向鏈中恢復。
  * **數據提取：** 提取所有詳情頁的鏈接，並生成對 `parse_detail_page` 的請求。

### 4\. `parse_detail_page` (數據與文件 Item)

  * **功能：** 提取壁紙的標題和原始下載鏈接。
  * **數據輸出：** 生成 `WallhallaItem`，其中包含：
      * `title` (標題)
      * `tag` (標籤)
      * `detail_url` (詳情頁 URL)
      * `image_name` (自定義的文件名，基於壁紙 ID)
      * `file_urls` (用於 FilesPipeline 下載的 URL 列表)

## 💾 數據存儲（Item Pipeline）

專案的數據存儲是**過程式**的（Item-by-Item 實時寫入），確保數據安全和低內存佔用。

1.  **`WallhallaFilePipeline` (下載)**：負責根據 `file_urls` 下載圖片，並將下載結果的本地路徑和元數據添加到 Item 中。
2.  **`WallhallaCSVPipeline` (記錄)**：負責接收處理完成的 Item，並將 Item 中的所有字段追加寫入到配置的 `CSV_FILE_PATH` 文件中。

-----