先启动 selenium 实例，手动登录后继续进行爬取，并支持指定 ChromeDriver 路径。
chrome_driver_path = r"C:\Program Files\Google\chromedriver-win64\chromedriver.exe"

目标网页：https://www.v2ph.com/
请求地址：https://www.v2ph.com/actor/{tag}?page={页码},示例："https://www.v2ph.com/actor/YUNA?page=1",
翻页示例："https://www.v2ph.com/actor/YUNA?page=2",依次翻页爬取，status响应"404"则代表没有下一页，需要进入下一个{tag}标签

network, doc属性  get请求标头："https://www.v2ph.com/actor/YUNA?page=1"

```html
      <div class="col-12 col-sm-6 col-md-4 col-lg-3 my-1">
  <div class="card">
    <div class="card-cover">
      <a class="media-cover" href="/album/a8e83n5z.html">
        <img class="card-img-top" src="data:image/gif;base64,R0lGODdhAQABAPAAAMPDwwAAACwAAAAAAQABAAACAkQBADs=" data-src="https://cdn.v2ph.com/album/yYWGn6AxI8oa6px9.jpg" alt="[SAINT Photolife] Yuna (유나) - Golden" loading="lazy" decoding="async">
      </a>
    </div>
        <div class="album-photos">
      <span class="badge rounded-pill bg-secondary">63P</span>
    </div>
    <div class="card-body media-meta p-2">
      <h6 class="mb-2">
        <a href="/album/a8e83n5z.html">[SAINT Photolife] Yuna (유나) - Golden</a>
      </h6>
      <dl class="row g-1 mb-0 text-muted">
                  <dt class="col-4 text-end">机构</dt>
          <dd class="col-8 mb-0">
            <a href="/company/SAINT-Photolife">SAINT Photolife</a>
          </dd>
                                  <dt class="col-4 text-end">标签</dt>
          <dd class="col-8 mb-0">
            <a href="/category/erotic-underwear">情趣内衣</a>          </dd>
              </dl>
    </div>

````
解析搜索页面，提取相册详情页链接和相册名称：

获取'a'标签下的'href'属性值，进入相册详情页,如：href='album/a8e83n5z.html
相册详情页示例链接：https://www.v2ph.com/album/a8e83n5z.html
相册详情页翻页示例：https://www.v2ph.com/album/a8e83n5z.html?page=2，依次翻页爬取，如果没有'div.album-photo.my-2'，则代表该相册已爬取完成，即可进入下一个相册。
提取相册/Title名称：'a'标签下的'href'属性值中提取文本信息，如：album/a8e83n5z.html 提取出 Yuna (유나) - Golden


进入相册详情页，解析页面获取图片URL列表：
```html
`
              <div class="photos-list text-center">
                                                      <div class="album-photo my-2" style="padding-bottom: 149.944%;">
                      <img src="data:image/gif;base64,R0lGODdhAQABAPAAAMPDwwAAACwAAAAAAQABAAACAkQBADs=" data-src="https://cdn.v2ph.com/photos/dFAuoQAJDZWDYkjN.jpg" class="img-fluid album-photo d-block mx-auto" alt="[SAINT Photolife] Yuna (유나) - Golden 0" loading="lazy" decoding="async">
          </div>

```
提取图片 URL：获取'div'标签下的'img'标签的'data-src属性值，即为图片的真实 URL，如：https://cdn.v2ph.com/photos/dFAuoQAJDZWDYkjN.jpg`


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



Redis 去重逻辑示例
REDIS_HOST = 'localhost'
REDIS_PORT = 6379
REDIS_KEY = 'v2ph_image_url_set' # 使用 URL 作为唯一标识符



    def __init__(self, csv_dir_path, csv_filename, redis_host=REDIS_HOST, redis_port=REDIS_PORT):
        """
        初始化爬虫实例，集成 Redis/内存去重逻辑。
        """
        self.csv_dir_path = csv_dir_path
        self.csv_path = os.path.join(self.csv_dir_path, csv_filename) 
        self.csv_lock = Lock() # 用于 CSV 写入的线程锁
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            # !!! 关键 !!! 模拟从原始网站发起请求
            'Referer': 'https://v2ph.com/' 
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


标签数据路径：{tag}标签文件本地文件路径：R:\py\Auto_Image-Spider\Requests\v2ph\tag.txt

CSV文件存储路径:R:\py\Auto_Image-Spider\Requests\v2ph

穿行池配置（保持串行）