

目标网页：https://isorepublic.com/
请求地址：https://isorepublic.com/?s={tag}&post_type=photo_post,示例："https://isorepublic.com/?s=girl&post_type=photo_post",
翻页：https://isorepublic.com/page/{页码}/?s={tag}&post_type=photo_post，示例："https://isorepublic.com/page/1/?s=girl&post_type=photo_post",依次翻页爬取，过status响应"404"则代表没有下一页，需要进入下一个{tag}标签

network, doc属性  get请求标头："https://isorepublic.com/page/1/?s=girl&post_type=photo_post"

```html
            <div id="photo-grid">
                <a href="https://isorepublic.com/photo/smiling-girl-in-hat/" title="Smiling Girl in Hat" class="photo-grid-item" itemscope itemtype="http://schema.org/ImageObject">
                    <p class="photo-grid-title" itemprop="name">Smiling Girl in Hat</p>
                    <img src="data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAcIAAAEsAQMAAABqmCH0AAAABlBMVEUAAAD///+l2Z/dAAAAAXRSTlMAQObYZgAAAAlwSFlzAAAOxAAADsQBlSsOGwAAAChJREFUeNrtwTEBAAAAwqD1T20LL6AAAAAAAAAAAAAAAAAAAAAAgLcBQ/gAAWjftlUAAAAASUVORK5CYII=" width="450" height="300" alt="Smiling Girl in Hat" itemprop="image" data-src="https://isorepublic.com/wp-content/uploads/2024/07/iso-republic-girl-hat-smile-450x300.jpg" decoding="async" class="lazyload" data-eio-rwidth="450" data-eio-rheight="300"/>
                    <noscript>
                        <img src="https://isorepublic.com/wp-content/uploads/2024/07/iso-republic-girl-hat-smile-450x300.jpg" width="450" height="300" alt="Smiling Girl in Hat" itemprop="image" data-eio="l"/>
                    </noscript>
                    <span class="hidden" itemprop="license">https://isorepublic.com/license/</span>
                    <span class="hidden" itemprop="acquireLicensePage">https://isorepublic.com/about/</span>
                    <span class="hidden" itemprop="contentUrl">https://isorepublic.com/wp-content/uploads/2024/07/iso-republic-girl-hat-smile-450x300.jpg</span>
                </a>

````

提取图片url，<noscript>元素下的'img'属性中'src'值，去掉后面的缩略分辨率"-450x300"就是原图,（注意这个分辨率不是固定值，需要设置一个通用匹配公式）。处理后的原图url示例："https://isorepublic.com/wp-content/uploads/2024/07/iso-republic-girl-hat-smile.jpg"
提取标题：<noscript>元素下的'img'属性中'alt'值，提取其中的文本信息，如：alt="Smiling Girl in Hat" 
图像名称：直接使用图像url中的最后字段作为图像名称


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
REDIS_KEY = 'isorepublic_image_url_set' # 使用 URL 作为唯一标识符



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


标签数据路径：{tag}标签文件本地文件路径：R:\py\Auto_Image-Spider\Spider_Data\ram_tag_list.txt

CSV文件存储路径:R:\py\Auto_Image-Spider\Requests\Isorepublic

启用完全异步多线程解耦式爬取：8个标签处理线程