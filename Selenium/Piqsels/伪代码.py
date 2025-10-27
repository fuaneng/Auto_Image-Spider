帮我设计高效的爬虫代码，下面的伪代码中已经给出相关信息和必要的条件：


目标网页：https://www.piqsels.com/
请求地址：https://www.piqsels.com/en/search?q={tag}&page={页数
翻页："https://www.piqsels.com/en/search?q={tag}&page={页数}" 如果返回404，说明没有下页了，只要页面出现“No results”则代表无图片抓取，执行跳过当前{tag},无需重试。下面是页面元素结构：
```html
<main class="resp" id="main">
    <h1 class="view_h1"> royalty free abacus photos free download | <a style="text-decoration: underline" target="_blank" href="https://www.pikrepo.com/en/search?q=abacus">more results</a></h1>
        <section>
                <span class="notfound">No results</span>
                    </section>

    </main>

```

示例网址："https://www.piqsels.com/en/search?q=girl&page=2"，返回状态码200，响应体中包含图片信息。


！！注意！！该目标网页有反爬虫人机验证机制，会不定时会弹出"cloudflare"验证界面，需要真人点击，执行手动验证通过之后才能正常获取到信息（这里推荐使用 selenium "undetected-chromedriver (uc) 库"实例进行串行爬取？绕过Cloudflare验证码，可以采用模拟真实用户的浏览行为来规避检测。通过设置更真实的浏览器环境，减少被识别为自动化工具?或者你有更好的方案）。
# !! 您的自定义驱动路径 !!
CUSTOM_DRIVER_PATH = r"C:\Program Files\Google\chromedriver-win64\chromedriver.exe"

Doc文档response响应示例：

```html
            <section>
                <ul itemscope itemtype="http://schema.org/ImageGallery" class="flex-images" id="flow">
                    <li itemprop="associatedMedia" itemscope itemtype="http://schema.org/ImageObject" class="item shadow" data-w="480" data-h="320">
                        <span class="res">4800x3200px</span>
                        <meta itemprop="fileFormat" content="image/jpeg">
                        <meta itemprop="isFamilyFriendly" content="true">
                        <meta itemprop="keywords" content="close, young, girl, pouring, fresh, pure, water, pitcher, glass, food and drink, women, refreshment, indoors, young adult, adult, drink, one person, clothing, beauty, household equipment, drinking glass, young women, white color, studio shot, beautiful woman, front view, drinking, 4K, CC0, public domain, royalty free">
                        <figure>
                            <a itemprop="url" href="https://www.piqsels.com/en/public-domain-photo-zkcyt" target="_blank">
                                <meta itemprop="license" content="https://creativecommons.org/licenses/publicdomain/">
                                <img class="lazy" itemprop="contentUrl" alt="close, young, girl, pouring, fresh, pure, water, pitcher, glass, food and drink, women, refreshment, indoors, young adult, adult, drink, one person, clothing, beauty, household equipment, drinking glass, young women, white color, studio shot, beautiful woman, front view, drinking, 4K, CC0, public domain, royalty free" title="View a larger version of this photo" src="data:image/gif;base64,R0lGODlhAQABAIAAAAAAAP///yH5BAEAAAAALAAAAAABAAEAAAIBRAA7" data-src="https://p0.piqsels.com/preview/336/319/700/5be978b943a75-thumbnail.jpg" data-srcset="https://p0.piqsels.com/preview/336/319/700/5be978b943a75.jpg 2x,https://p0.piqsels.com/preview/336/319/700/5be978b943a75.jpg 3x,https://p0.piqsels.com/preview/336/319/700/5be978b943a75.jpg 4x">
                            </a>
                            <figcaption itemprop="caption" class="overflow">close, young, girl, pouring, fresh, pure, water, pitcher</figcaption>
                        </figure>
                        <a class="license_a" rel="license" about="https://p0.piqsels.com/preview/336/319/700/5be978b943a75-thumbnail.jpg" href="https://creativecommons.org/licenses/publicdomain/">Public Domain</a>
                    </li>

```


提取字段：
- 提取预览图后去除'-thumbnail'可以得到最大分辨率的预览图url：提取'a'元素下的'about'值，即about="https://p0.piqsels.com/preview/336/319/700/5be978b943a75-thumbnail.jpg" ，去除"-thumbnail",即为1k图url，示例："https://p0.piqsels.com/preview/336/319/700/5be978b943a75.jpg"就是1k图。


- 'img'的'alt'值,如：'img'属性下的'alt'值`alt=" "`就是图片标题

- 图片名称 (ImageName) —— 提取url字段


{tag}文本本地文件路径：D:\myproject\Code\爬虫\爬虫数据\libreshot\ram_tag_list_备份.txt
CSV文件存储路径:r"D:\myproject\Code\爬虫\爬虫数据\piqsels"

将获取后的所有数据分列实时保存到CSV文件
    def write_to_csv(self, title, name, url, csv_path, tag):
        """
        写入 CSV 方法，已集成线程锁，确保线程安全。
        """
        try:
            with self.csv_lock: # 使用线程锁
                os.makedirs(os.path.dirname(csv_path), exist_ok=True)
                is_file_empty = not os.path.exists(csv_path) or os.stat(csv_path).st_size == 0
                
                with open(csv_path, 'a', newline='', encoding='utf-8-sig') as f:
                    writer = csv.writer(f)
                    
                    if is_file_empty:
                        writer.writerow(['Title', 'ImageName', 'URL', 'TAG'])
                        
                    writer.writerow([title, name, url, tag])
        except Exception as e:
            print(f"[{tag}] [✗] 写入 CSV 出错: {e}")


麻烦的验证机制只能使用单线程串型爬取{tag}

Redis 去重逻辑示例
REDIS_HOST = 'localhost'
REDIS_PORT = 6379
REDIS_KEY = 'piqsels_image_url_set' # 使用 URL 作为唯一标识符



    def __init__(self, csv_dir_path, csv_filename, redis_host=REDIS_HOST, redis_port=REDIS_PORT):
        """
        初始化爬虫实例，集成 Redis/内存去重逻辑。
        """
        self.csv_dir_path = csv_dir_path
        self.csv_path = os.path.join(self.csv_dir_path, csv_filename) 
        self.csv_lock = Lock() # 用于 CSV 写入的线程锁
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

        # --- 去重初始化逻辑 ---
        try:
            # 尝试连接 Redis
            self.redis = redis.StrictRedis(host=redis_host, port=redis_port, decode_responses=True)
            # 尝试执行一次 ping 来验证连接
            self.redis.ping()
            print("✅ Redis 连接成功，使用 Redis 集合进行去重。")
        except redis.exceptions.ConnectionError as e:
            print(f"⚠️ Redis 连接失败 ({e})，将使用内存去重。")
            self.redis = None
            # 内存去重集合，注意：内存集合在多线程间共享，但只在当前程序生命周期内有效。
            # 由于线程池是在当前进程内运行，因此这个 set 是共享的。
            self.visited_urls = set()
        except Exception as e:
            print(f"⚠️ Redis 初始化遇到其他错误 ({e})，将使用内存去重。")
            self.redis = None
            self.visited_urls = set()