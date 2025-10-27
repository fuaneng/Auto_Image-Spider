
# 第一部分：搜索 watch-4-beauty ，获取相册列表
主页：https://www.elitebabes.com/
搜索相册列表的：https://www.elitebabes.com/watch-4-beauty/
使用浏览器开发者工具 Network/fetch/XHR 选项卡，观察搜索相册列表的请求url及响应数据格式。
发现搜索相册列表的请求为XHR 文档类型，响应数据格式为json。
搜索 GET 请求url："https://www.elitebabes.com/gridapi/?content=channel_old&nr=6512&sort=trending&mpage={页码}" ,页码的值为：1、2、3、4、5、6......以此类推，每页20个相册。
示例 GET 请求url："https://www.elitebabes.com/gridapi/?content=channel_old&nr=6512&sort=trending&mpage=1"，递进页码如果没有相册加载，这表示没有更多页码。注意：人名{tag}"jillian janson"中的空格需要替换为'+'号。

Network/fetch/XHR 文档response响应示例：
```json
<li style="--ratio: 0.6667">
    <figure>
        <a href="https://www.elitebabes.com/watch-4-beauty-taya-sour-in-new-talent-taya-sour-107400/" title="Taya Sour exposes her nudes and gives an explicit view of her pussy as she seductively straddles the couch.">
            <img alt="Taya Sour exposes her nudes and gives an explicit view of her pussy as she seductively straddles the couch." srcset="
        https://cdn.elitebabes.com/content/250585/1090265_masonry_1200.jpg 1200w, https://cdn.elitebabes.com/content/250585/1090265_masonry_800.jpg 800w, https://cdn.elitebabes.com/content/250585/1090265_masonry_600.jpg 600w, https://cdn.elitebabes.com/content/250585/1090265_masonry_400.jpg 400w, https://cdn.elitebabes.com/content/250585/1090265_masonry_200.jpg 200w" src="https://cdn.elitebabes.com/content/250585/1090265_masonry_400.jpg" sizes="(max-width: 610px) 50vw, (max-width: 930px) 33vw, (max-width: 1549px) 25vw, (min-width: 1550px) 20vw">
        </a>
        <div class="img-overlay">
            <p>
                <a href="https://www.elitebabes.com/watch-4-beauty-taya-sour-in-new-talent-taya-sour-107400/">Taya Sour exposes her nudes and gives an explicit view of her pussy as she seductively straddles the couch.</a>
            </p>
            <ul class="list-icon">
                <li>
                    <a class="simplefavorite-button" data-postid="1090265" data-siteid="1" data-groupid="1" data-favoritecount="3" style="">
                        <i aria-hidden="true" class="icon-schedule"></i>
                        <span>Watch later</span>
                    </a>
                </li>
                <li class="a" id="myrating-1090265">
                    <span id="post-ratings-1090265" class="post-ratings" data-nonce="a1ecb4cc78"></span>
                    <a href="javascript:void(0);" onmouseover="current_rating(1090265, 1, '1 Star');" onmouseout="ratings_off(1, 0, 0);" onclick="rate_post(1);" onkeypress="rate_post(1);" style="cursor: pointer; border: 0px;">
                        <i aria-hidden="true" class="icon-favorite"></i>
                        <span id="thelike">62</span>
                        <span>I Like This</span>
                    </a>
                </li>
                <li>
                    <a href="https://www.elitebabes.com/model/victoria-b-2/">
                        <i aria-hidden="true" class="icon-woman"></i>
                        <span>Victoria B</span>
                    </a>
                </li>
            </ul>
        </div>
    </figure>
</li>

```
逐个获取每个相册标签下的'a'元素下的'href'属性的值，即为图片详情页请求url。
示例："https://www.elitebabes.com/watch-4-beauty-taya-sour-in-new-talent-taya-sour-107400/"，

获取'a'元素下的'title'属性文本信息，即为相册的标题，这个值为相册的名称。需要写入到csv文件的'相册'字段。，如：'Taya Sour exposes her nudes and gives an explicit view of her pussy as she seductively straddles the couch.'



# 第二部分：访问图片详情页，获取图片信息并写入表格
详情页请求url的 doc 响应示例：
```html
<main id="content">
      <p>Taya Sour exposes her nudes and gives an explicit view of her pussy as she seductively straddles the couch.</p>      <p class="link-btn scroll">
        <a class="overlay-b" href="https://www.elitebabes.com/watch-4-beauty/">Watch 4 Beauty</a>						<a class="overlay-b" href="https://www.elitebabes.com/model/victoria-b-2/">Taya Sour</a><a href="https://www.elitebabes.com/tag/asshole/" class="visible-tag" title="">Asshole</a> <a href="https://www.elitebabes.com/tag/babe/" class="visible-tag" title="">Babe</a> <a href="https://www.elitebabes.com/tag/brunette/" class="visible-tag" title="">Brunette</a> <a href="https://www.elitebabes.com/tag/feet/" class="visible-tag" title="">Feet</a> <a href="https://www.elitebabes.com/tag/legs/" class="visible-tag" title="">Legs</a> <a href="https://www.elitebabes.com/tag/pale/" class="visible-tag" title="">Pale</a> <a href="https://www.elitebabes.com/tag/small-tits/" class="visible-tag" title="">Small Tits</a> <a href="https://www.elitebabes.com/tag/close-up-pussy/" class="visible-tag" title="">Close Up Pussy</a> <a href="https://www.elitebabes.com/tag/brunette-small-tits/" class="visible-tag" title="">Brunette Small Tits</a> <a href="https://www.elitebabes.com/tag/brunette-babe/" class="visible-tag" title="">Brunette Babe</a> <a href="https://www.elitebabes.com/tag/pale-brunette/" class="visible-tag" title="">Pale Brunette</a> <a href="https://www.elitebabes.com/tag/brunette-feet/" class="visible-tag" title="">Brunette Feet</a> <a href="https://www.elitebabes.com/tag/spreading/" class="hidden-tag" title="">Spreading</a> <a href="#" class="toggle-more-tags" onclick="event.preventDefault(); this.style.display='none'; var parent = this.closest('p'); parent.querySelectorAll('.hidden-tag').forEach(function(el){el.style.display='inline';}); parent.querySelector('.toggle-less-tags').style.display='inline';">+ All Tags</a><a href="#" class="toggle-less-tags" style="display:none;" onclick="event.preventDefault(); this.style.display='none'; var parent = this.closest('p'); parent.querySelectorAll('.hidden-tag').forEach(function(el){el.style.display='none';}); parent.querySelector('.toggle-more-tags').style.display='inline';">- Less Tags</a></p>        <ul class="list-gallery static css" data-title="Watch 4 Beauty" data-url="https://www.elitebabes.com/watch-4-beauty/">
                                        <li style="--w: 400; --h: 267;"><a data-fancybox="images" data-srcset="https://cdn.elitebabes.com/content/250585/0002-01_2400.jpg 2400w, https://cdn.elitebabes.com/content/250585/0002-01_1800.jpg 1800w, https://cdn.elitebabes.com/content/250585/0002-01_1200.jpg 1200w"  href="https://cdn.elitebabes.com/content/250585/0002-01_1800.jpg" data-width="2400" data-height="1600"><img src="https://cdn.elitebabes.com/content/250585/0002-01_w400.jpg" srcset="https://cdn.elitebabes.com/content/250585/0002-01_w800.jpg 800w, https://cdn.elitebabes.com/content/250585/0002-01_w600.jpg 600w, https://cdn.elitebabes.com/content/250585/0002-01_w400.jpg 400w, https://cdn.elitebabes.com/content/250585/0002-01_w200.jpg 200w" sizes="(max-width: 420px) 100vw,(max-width: 899px) and (min-width: 421px) 66.6vw,(max-width: 1300px) and (min-width: 900px) 33.3vw,(min-width: 1301px) 520px" alt="Taya Sour in New Talent Taya Sour from Watch 4 Beauty" width="400" height="267" loading="lazy" /></a></li>

```
详情页提取图集信息并写入表格
提取url：'a'元素下的'data-srcset'值后去除后缀"_2400"，即图片原图url，如：获取到的'data-srcset'=https://cdn.elitebabes.com/content/250585/0002-01_2400.jpg,则图片url为：https://cdn.elitebabes.com/content/250585/0002-01.jpg
提取标题：'img'元素下的'alt'属性，如：alt='Taya Sour in New Talent Taya Sour from Watch 4 Beauty'

图片名称：从图片url中提取最后一个'/'后的文本内容，如：'250585/0002-01_2400.jpg'，去掉扩展名即为名称'250585_0002-01_2400'。


写入CSV文件字段：标题、图片名称、图片URL、所属相册、watch-4-beauty标签
注意事项：相册字段需要从第一部分搜索 watch-4-beauty ，获取相册列表。

# 第三部分：启动下载图片
启动下载图片到本地文件夹
解耦式异步多线程下载图片到本地文件夹,使用相册字段作为子文件夹名，文件命名为名称字段，保留原始图片格式扩展名。
*解析相册和详情页使用20个线程，下载使用50个线程。

csv文件路径存储路径：“R:\py\Auto_Image-Spider\Requests\Elitebabes_R18\all_images_data.csv”
下载图片存储路径“R:\py\Auto_Image-Spider\Requests\Elitebabes_R18\images\”
示例：R:\py\Auto_Image-Spider\Requests\Elitebabes_R18\images\250585_0002-01_2400.jpg

解耦式异步下载，三种模式：
    # --- 运行模式示例 ---
    
    # 示例 1: 仅爬取数据到 CSV，不下载图片
    print("\n--- 模式一：仅爬取数据到 CSV (download_enabled=False) ---")
    spider.start_crawl(download_enabled=False)
    
    # 示例 2: 爬取数据并下载图片 (如果需要，请取消下一行的注释)
    # print("\n--- 模式二：爬取数据并下载图片 (download_enabled=True) ---")
    # spider.start_crawl(download_enabled=True) 

    # 示例 3: 也可以在数据收集完成后单独启动下载任务
    # print("\n--- 模式三：单独启动下载任务 ---")
    # spider.start_download()



Redis 去重逻辑示例
REDIS_HOST = 'localhost'
REDIS_PORT = 6379
REDIS_KEY = 'elitebabes_r18_image_url_set' # 使用 URL 作为唯一标识符

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