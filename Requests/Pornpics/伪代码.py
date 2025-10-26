
# 第一部分：搜索{人名tag}标签，获取相册列表
主页：https://www.pornpics.com/
搜索 GET 请求url："https://www.pornpics.com/search/srch.php?q={人名tag}&lang=zh&limit=20&offset={页码}" ,页码的值为：0、20、40、60......以此类推，每页20个相册。
示例 GET 请求url："https://www.pornpics.com/search/srch.php?q=jillian+janson&lang=zh&limit=20&offset=20"，递进页码如果没有相册加载，这表示没有更多页码。注意：人名{tag}"jillian janson"中的空格需要替换为'+'号。

Network/fetch/XHR 文档response响应示例：
```json
[
    {
        "g_url": "https://www.pornpics.com/zh/galleries/sharon-lee-and-girlfriend-lick-interracial-lesbian-pussies-with-tongues-14334930/",
        "t_url": "https://cdni.pornpics.com/300/1/307/14334930/14334930_005_a553.jpg",
        "h": 450,
        "desc": "Sharon Lee and girlfriend lick interracial lesbian pussies with tongues 14334930",
        "t_url_460": "https://cdni.pornpics.com/460/1/307/14334930/14334930_005_a553.jpg",
        "gid": "14334930",
        "mid": "14334930_42304795",
        "tid": "42304795",
        "nofollow": false,
        "outLink": false
    },

```
逐个获取每个相册标签下的'"g_url"'元素的值，即为图片详情页请求url。
示例："g_url":"https://www.pornpics.com/zh/galleries/sharon-lee-and-girlfriend-lick-interracial-lesbian-pussies-with-tongues-14334930/"，完整请求url为：https://www.pornpics.com/zh/galleries/sharon-lee-and-girlfriend-lick-interracial-lesbian-pussies-with-tongues-14334930/

获取'desc'元素下的文本内容，即为相册的标题，这个值为相册的名称。需要写入到csv文件的'相册'字段。，如：'Sharon Lee and girlfriend lick interracial lesbian pussies with tongues 14334930'



# 第二部分：访问图片详情页，获取图片信息并写入表格
详情页请求url的 doc 响应示例：
```html
                    <ul class="wookmark-initialised" id="tiles">
                        <li class='thumbwook'>
                            <a class='rel-link' href='https://cdni.pornpics.com/1280/7/362/70724309/70724309_001_249a.jpg' data-tid="001" data-pswp-width='853' data-pswp-height='1280' data-size="853x1280">
                                <img src='https://static.pornpics.com/style/img/1px.png' data-src='https://cdni.pornpics.com/460/7/362/70724309/70724309_001_249a.jpg' alt='Naturally curvy teen Jillian Janson squats naked on the table & spreads pussy' width='300' height='450'/>
                            </a>
                        </li>

```
详情页提取图集信息并写入表格
提取url：'a'元素下的'href'属性，即图片原图url，如：'https://cdni.pornpics.com/1280/7/362/70724309/70724309_001_249a.jpg'。
提取标题：'img'元素下的'alt'属性，如：alt='Naturally curvy teen Jillian Janson squats naked on the table & spreads pussy'

图片名称：从图片url中提取最后一个'/'后的文本内容，如：'70724309_001_249a.jpg'，去掉扩展名即为名称'70724309_001_249a'。


写入CSV文件字段：标题、图片名称、图片URL、所属相册、人名Tag标签
注意事项：相册字段需要从第一部分搜索{人名tag}标签，获取相册列表。

# 第三部分：启动下载图片
启动下载图片到本地文件夹
解耦式异步多线程下载图片到本地文件夹,使用相册字段作为子文件夹名，文件命名为名称字段，保留原始图片格式扩展名。
{人名tag}标签文档本地路径：“R:\py\Auto_Image-Spider\Requests\Pornpics\人名tag.txt”
"人名tag.txt"内容示例：
```txt
anna-l-vWIOQsU8
danny-vWIOQsU8
```

csv文件路径存储路径：“R:\py\Auto_Image-Spider\Requests\Pornpics\all_images_data.csv”
下载图片存储路径“R:\py\Auto_Image-Spider\Requests\Pornpics\images\”
示例：R:\py\Auto_Image-Spider\Requests\Pornpics\images\70724309_001_249a.jpg

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
REDIS_KEY = 'pornpics_image_url_set' # 使用 URL 作为唯一标识符

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