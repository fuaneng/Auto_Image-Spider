import scrapy
import json
import os
from pathlib import Path
from lifeofpix_scraper.items import LifeofpixItem # 导入 Item 定义

class LifeofpixSpider(scrapy.Spider):
    name = "lifeofpix" # 爬虫的唯一名称 [cite: 635, 851]
    allowed_domains = ["lifeofpix.com"] # 允许爬取的域名 [cite: 857]
    tag_file_path = r"R:\py\Auto_Image-Spider\Lifeofpix\tag.txt" # 本地标签文件路径 (请确保此路径正确)
    base_api_url = "https://www.lifeofpix.com/api/search/photos/{tag}/40.json?page={page}"

    custom_settings = { # 可以为单个 Spider 定义特定设置 [cite: 860, 1381]
        'LOG_LEVEL': 'INFO', # 设置日志级别，减少不必要的输出 [cite: 1559, 2272]
    }

    def __init__(self, *args, **kwargs):
        super(LifeofpixSpider, self).__init__(*args, **kwargs)
        self.tags = self._read_tags() # 读取标签
        self.last_page_urls = {} # 用于存储每个标签上一页的图片 URL 集合，以检测重复页

    def _read_tags(self):
        """从本地文件读取标签列表"""
        tags = []
        try:
            with open(self.tag_file_path, 'r', encoding='utf-8') as f:
                tags = [line.strip() for line in f if line.strip()]
            self.logger.info(f"成功读取 {len(tags)} 个标签来自: {self.tag_file_path}")
        except FileNotFoundError:
            self.logger.error(f"标签文件未找到: {self.tag_file_path}")
        except Exception as e:
            self.logger.error(f"读取标签文件时出错: {e}")
        return tags

    def start_requests(self): # 使用 start_requests 代替 start_urls 以便动态生成初始请求 [cite: 649, 895]
        """根据标签列表生成初始请求"""
        if not self.tags:
            self.logger.warning("标签列表为空，无法开始爬取。")
            return

        for tag in self.tags:
            self.last_page_urls[tag] = set() # 初始化每个 tag 的上一页 URL 集合
            start_page = 1
            api_url = self.base_api_url.format(tag=tag, page=start_page)
            self.logger.info(f"开始爬取标签 '{tag}' 的第一页: {api_url}")
            # 使用 cb_kwargs 传递 tag 和 page 信息到回调函数 [cite: 1151, 1184]
            yield scrapy.Request(api_url, callback=self.parse_api, cb_kwargs={'tag': tag, 'page': start_page})

    def parse_api(self, response, tag, page):
        """解析 API 返回的 JSON 数据"""
        try:
            data = json.loads(response.text) # 解析 JSON [cite: 165, 212]
            image_list = data.get('data', [])

            if not image_list:
                self.logger.info(f"标签 '{tag}' 第 {page} 页没有图片数据，停止该标签的爬取。")
                return # 如果没有数据，则停止该标签的后续翻页

            current_page_urls = {img.get('urlDownload') for img in image_list if img.get('urlDownload')}

            # 检查当前页的 URL 集合是否与上一页完全相同 (且非空)
            if current_page_urls and current_page_urls == self.last_page_urls.get(tag):
                self.logger.info(f"标签 '{tag}' 第 {page} 页数据与上一页重复，停止该标签的爬取。")
                return # 如果数据重复，停止该标签的后续翻页

            self.last_page_urls[tag] = current_page_urls # 更新上一页的 URL 集合

            self.logger.info(f"标签 '{tag}' 第 {page} 页发现 {len(image_list)} 张图片。")

            for image_data in image_list:
                download_url = image_data.get('urlDownload')
                title = image_data.get('adobeRelatedTitle')

                if not download_url:
                    self.logger.warning(f"在标签 '{tag}' 第 {page} 页发现一条记录缺少 'urlDownload'。")
                    continue

                item = LifeofpixItem()
                item['title'] = title if title else "No Title Provided"
                item['image_urls'] = [download_url] # ImagesPipeline 需要一个列表 [cite: 2038, 2046]
                item['tag'] = tag
                yield item # 将 Item 交给 Pipeline 处理 [cite: 681]

            # 准备下一页的请求 (只要当前页有数据且未重复就继续)
            next_page = page + 1
            next_api_url = self.base_api_url.format(tag=tag, page=next_page)
            self.logger.debug(f"准备爬取标签 '{tag}' 的下一页: {next_api_url}")
            # 使用 response.follow 可以更方便地处理相对 URL 和传递 cb_kwargs [cite: 706, 707]
            # 但这里 API URL 是完整的，所以也可以直接用 scrapy.Request
            yield scrapy.Request(next_api_url, callback=self.parse_api, cb_kwargs={'tag': tag, 'page': next_page})

        except json.JSONDecodeError:
            self.logger.error(f"无法解析标签 '{tag}' 第 {page} 页的 JSON: {response.url}")
        except Exception as e:
            self.logger.error(f"处理标签 '{tag}' 第 {page} 页时发生错误 ({response.url}): {e}")