import scrapy
import os
from urllib.parse import urljoin
# 假设你的 items.py 路径是正确的
from ..items import WallhallaItem 

class WallhallaSpider(scrapy.Spider):
    """
    WallhallaSpider: 用于爬取 wallhalla.com 网站的壁纸信息。
    通过模拟访问首页并带 Referer 发起搜索请求，解决网站重定向和初始请求去重问题。
    """
    name = 'wallhalla'
    # 允许的域名必须包含带 www. 和不带 www. 的版本
    allowed_domains = ['www.wallhalla.com', 'wallhalla.com'] 
    # base_url 设为网站最终重定向的目标域名
    base_url = 'https://wallhalla.com'  
    
    # ---------------------- 步骤 1: 请求首页 ----------------------
    def start_requests(self):
        """
        读取标签文件，并为每个标签生成一个对网站首页的请求。
        """
        tag_file_path = self.settings.get('TAG_FILE_PATH')
        
        tags = [] 
        
        if not tag_file_path or not os.path.exists(tag_file_path):
            self.logger.error(f"❌ 找不到标签文件: {tag_file_path}")
            return
        
        try:
            with open(tag_file_path, 'r', encoding='utf-8') as f:
                tags = [line.strip() for line in f if line.strip()]
        except Exception as e:
            self.logger.error(f"❌ 读取标签文件出错: {e}")
            return

        if not tags:
            self.logger.warning("⚠️ 标签列表为空，爬虫已退出。请检查标签文件内容。")
            return

        self.logger.info(f"--- 发现 {len(tags)} 个标签，开始生成初始请求 ---")

        for tag in tags:
            # 先请求首页，并将 tag 传递给 parse_home_page
            yield scrapy.Request(
                url=self.base_url, 
                callback=self.parse_home_page,
                meta={'tag': tag},
                # ✨ 关键修复：禁用去重，确保每个标签的初始请求都能被发送
                dont_filter=True 
            )

    # ---------------------- 步骤 2: 模拟搜索提交 ----------------------
    def parse_home_page(self, response):
        """
        处理首页响应，模拟表单提交，发送带有 Referer 的 GET 搜索请求。
        """
        tag = response.meta['tag']
        
        self.logger.info(f"🏡 成功访问首页，开始模拟搜索 '{tag}'...")

        # 构造搜索 URL (GET 请求参数: /search?q={tag})
        search_url = urljoin(response.url, f'/search?q={tag}')
        
        # 模拟浏览器提交表单，并设置正确的 Referer 和禁用自动重定向
        yield scrapy.Request(
            url=search_url,
            callback=self.parse_search_page,
            meta={
                'tag': tag,
                'dont_redirect': True,              # 阻止 Scrapy 自动跟随重定向
                'handle_httpstatus_list': [301, 302] # 让 Scrapy 处理 301/302 响应
            },
            headers={
                'Referer': response.url # 设置 Referer 头，模拟请求来自首页
            },
        )

    # ---------------------- 步骤 3: 解析搜索结果页 ----------------------
    def parse_search_page(self, response):
        """
        解析搜索结果页面，提取详情页链接。
        """
        tag = response.meta['tag']

        # 检查是否是重定向（3xx 状态码）
        if response.status in [301, 302]:
            location = response.headers.get('Location').decode('utf-8')
            self.logger.info(f"🔄 捕获到重定向 ({response.status})，目标地址是: {location}")
            
            # 只有当重定向目标包含搜索路径时，我们才跟随
            if '/search?q=' in location:
                # 重新发送请求，让 Scrapy 自动处理这次重定向
                yield scrapy.Request(
                    url=location,
                    callback=self.parse_search_page,
                    meta={'tag': tag}
                )
            else:
                self.logger.error(f"❌ 搜索 '{tag}' 失败，网站重定向到首页，搜索参数丢失。URL: {location}")
            return

        # 只有状态码为 200 时才进行解析
        if response.status != 200:
             self.logger.error(f"❌ 搜索 '{tag}' 失败，状态码: {response.status}. 页面URL: {response.url}")
             return
            
        # 确保我们位于搜索页
        if '/search' not in response.url:
            self.logger.warning(f"⚠️ 搜索 '{tag}' 疑似失败，当前页面不是搜索页: {response.url}")
            return

        self.logger.info(f"🔍 正在解析标签 '{tag}' 的搜索结果页: {response.url}")

        # 使用 CSS 选择器定位所有图片卡片链接
        card_links = response.css('div.wallpapers-wrap a.wp-item::attr(href)').getall()
        
        if not card_links:
            # 强化诊断：检查页面上是否有 '没有结果' 的提示
            no_results_text = response.css('.text-wh-550::text').getall()
            
            is_no_results = False
            for text in no_results_text:
                if 'no results' in text.lower() or 'not found' in text.lower():
                    is_no_results = True
                    break
            
            if is_no_results:
                self.logger.warning(f"⚠️ 标签 '{tag}' (URL: {response.url}) **确认没有搜索结果**。")
            else:
                self.logger.error(f"❌ 标签 '{tag}' (URL: {response.url}) 未找到图片卡片。**请检查选择器是否失效**。")
                
            return # 没有图片，跳过该标签。

        self.logger.info(f"🖼️ 标签 '{tag}' 找到 {len(card_links)} 个详情页链接。")

        for link in card_links:
            detail_url = urljoin(self.base_url, link)
            
            # 发送对详情页的请求
            yield scrapy.Request(
                url=detail_url,
                callback=self.parse_detail_page,
                meta={'tag': tag}
            )
            
        # TODO: 翻页/无限滚动加载逻辑可以在此添加

    # ---------------------- 步骤 4: 解析详情页 ----------------------
    def parse_detail_page(self, response):
        """
        解析详情页，提取图片标题和下载链接，并生成 Item。
        """
        tag = response.meta['tag']
        
        # 1. 提取标题
        title = response.css('h1.text-2xl::text').get(default='N/A').strip()

        # 2. 提取下载链接
        download_relative_url = response.css('a[href*="/variant/original?dl=true"]::attr(href)').get()
        
        if not download_relative_url:
            self.logger.warning(f"❌ 详情页 {response.url} 未找到下载链接。")
            return
        
        download_url = urljoin(self.base_url, download_relative_url)
        
        # 3. 构造文件名和 ID
        try:
             # 从 URL 中提取 ID: /wallpaper/41 -> 41
             wallpaper_id = response.url.split('/wallpaper/')[1].split('/')[0]
             image_name = f"{wallpaper_id}.jpg"
        except IndexError:
             self.logger.warning(f"❌ 无法从 URL 提取 ID: {response.url}")
             image_name = f"unknown_{tag}.jpg"

        
        # 4. 创建 Item
        item = WallhallaItem()
        item['title'] = title
        item['tag'] = tag
        item['detail_url'] = response.url
        item['image_name'] = image_name
        item['file_urls'] = [download_url] # FilesPipeline 使用

        self.logger.info(f"✔️ 提取 Item: {title}, URL: {download_url}")
        
        yield item