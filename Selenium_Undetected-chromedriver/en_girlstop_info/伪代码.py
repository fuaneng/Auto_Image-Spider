主页：https://en.girlstop.info/

模特作品页：https://en.girlstop.info/models.php?name={model_name}

model_name.txt
```txt
Gloria-Sol
Mila-Azul

```

network doc 响应
get 请求地址：https://en.girlstop.info/models.php?name={model_name}
```html
<div class="thumb" rel='243345'>
        <a href="/psto.php?id=243345">        
        <div quick='7,10,13,20,21,38,40,42,45,47' rel='243345' code='68da45bbec8f8' class='thumb_wrapper'>
            <picture>
                
                <source srcset='https://girlstop.top/cat/posts/68da45bbec8f8/thumbs/450px_p.webp' type='image/webp'>
                <source srcset='https://girlstop.top/cat/posts/68da45bbec8f8/thumbs/450px_p.jpg' type='image/jpeg'> 
                <img loading='lazy' src='https://girlstop.top/cat/posts/68da45bbec8f8/thumbs/450px_p.jpg' alt='Chair By The Window' style="aspect-ratio:0.666833" >
            </picture>
        </div>
        </a>
        
        <div style='padding-top:5px'><strong class="post_title"><a href="psto.php?id=243345">Chair By The Window</a></strong></div>
        
        <div class="">
            <table><tbody>
            
                </tbody></table>
        </div>
    </div>  

```

提取作品集标题以及作品集详情页链接
标题所在标签：<strong class="post_title"><a href="psto.php?id=243345">Chair By The Window</a></strong>,其中 href 为详情页链接，文本为作品标题如 Chair By The Window
提取所有作品标题以及作品详情页链接
'a[href^="psto.php?id="]'


到作品详情页
```html

    <a id="pic0" class="fullimg" title="Chair By The Window" href="https://girlstop.top/cat/posts/68da45bbec8f8/p.avif">
    <picture>
        
        <source srcset="https://girlstop.top/cat/posts/68da45bbec8f8/thumbs/450px_p.webp" type="image/webp">
        <source srcset="https://girlstop.top/cat/posts/68da45bbec8f8/thumbs/450px_p.jpg" type="image/jpeg"> 
        <img alt="Mila Azul Chair By The Window" style="aspect-ratio:4001/6000"  src="https://girlstop.top/cat/posts/68da45bbec8f8/thumbs/450px_p.jpg" width="300" class="" >
    </picture>
    </a>    
    </li><li>

```

提取图片url:'a'属性中的 href 值为 https://girlstop.top/cat/posts/68da45bbec8f8/p.avif 为图片原始链接

将获取后的所有数据分列实时保存到CSV文件
    def write_to_csv(self, title, name, url, csv_path, model_name):
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
                        writer.writerow(['Title', 'ImageName', 'URL', 'model_name'])
                        
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
            'Referer': 'https://en.girlstop.info/' 
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


标签数据路径：{model_name}标签文件本地文件路径：R:\py\Auto_Image-Spider\Selenium\en_girlstop_info\model_name.txt

CSV文件存储路径:R:\py\Auto_Image-Spider\Selenium\en_girlstop_info

穿行池配置（保持串行）

使用 Selenium UnicodeDecodeError驱动浏览器，处理 Cloudflare 验证
自定义：CUSTOM_DRIVER_PATH = r"C:\Program Files\Google\chromedriver-win64\chromedriver.exe"





// --- 配置部分 ---
常量 BASE_URL = '...'
常量 CSV_目录路径 = '...'
常量 浏览器主版本号 = 142
常量 启用下载 = 真/假
常量 最大下载线程数 = 10

// --- 类：GirlstopSpider ---
类 GirlstopSpider:

    方法 构造函数(配置参数):
        // 初始化驱动和网络工具
        如果 启用下载:
            初始化 下载任务队列 (Queue)
            初始化 线程池 (ThreadPoolExecutor, 线程数=最大下载线程数)
        
        初始化 uc_Chrome驱动 (使用 浏览器主版本号 和 自定义路径)
        
        // 初始化去重机制
        尝试 连接 Redis:
            设置 self.redis = Redis连接
        异常:
            设置 self.redis = 空
            设置 self.visited_urls = 内存集合
        
        设置 self.csv_锁 (Lock)
        
    // --- 实用工具方法 ---
    
    方法 清理文件名(文件名):
        // 移除文件名中不允许的特殊字符
        返回 安全的文件名
        
    方法 是URL已访问(URL):
        如果 self.redis 存在:
            返回 Redis.SADD(URL) == 0 (已存在)
        否则 (使用内存):
            如果 URL 在 self.visited_urls 中:
                返回 真
            将 URL 添加到 self.visited_urls
            返回 假

    方法 安全访问URL(URL):
        驱动.GET(URL)
        等待 5 秒
        
        如果 页面包含 Cloudflare 关键字:
            输出 提示用户手动验证信息
            等待 用户按 Enter
            等待 2 秒
            
        返回 驱动.页面源码

    // --- 异步下载工作方法 ---
    
    方法 下载工作线程(URL, 标题, 模特名):
        安全模特名 = 清理文件名(模特名)
        安全标题 = 清理文件名(标题)
        
        保存目录 = 拼接(CSV_目录路径, 安全模特名, 安全标题)
        文件名 = 从 URL 提取
        保存路径 = 拼接(保存目录, 文件名)
        
        如果 文件已存在于 保存路径:
            返回 真 (成功)
            
        创建 保存目录 (如果不存在)
        
        尝试 使用 requests.GET(URL):
            使用 self.csv_锁:
                写入图片到 保存路径
            输出 "下载成功"
            返回 真
        异常:
            输出 "下载失败"
            返回 假

    // --- 核心爬取流程方法 ---
    
    方法 写入CSV(标题, URL, 模特名):
        // 1. 将下载任务推入队列 (解耦)
        如果 启用下载:
            下载任务队列.put((URL, 标题, 模特名))
            
        // 2. 写入 CSV 记录
        使用 self.csv_锁:
            写入 (标题, URL, 模特名) 到 CSV 文件
        
    方法 提取详情页信息(相对URL, 模特名, 标题):
        完整URL = 拼接(BASE_URL, 相对URL)
        HTML内容 = 安全访问URL(完整URL)
        
        如果 HTML内容 为空:
            返回
            
        解析 HTML内容
        
        找到 所有 <a> 标签且 class="fullimg" 的元素 (即所有图片链接)
        
        对于 每个 图片链接元素:
            图片URL = 链接元素.href
            
            如果 非 是URL已访问(图片URL):
                调用 写入CSV(标题, 图片URL, 模特名)
                
    方法 爬取模特页面(模特名):
        模特URL = 构造模特作品集URL(模特名)
        HTML内容 = 安全访问URL(模特URL)
        
        如果 HTML内容 为空:
            返回
            
        解析 HTML内容
        
        找到 所有 作品集链接 (标题和相对URL)
        
        对于 每个 作品集链接:
            调用 提取详情页信息(相对URL, 模特名, 标题)

    // --- 主执行方法 ---
    
    方法 run(模特名称文件):
        // 1. 爬取阶段 (串行)
        读取 模特名称文件列表
        对于 列表中的 每个 模特名:
            调用 爬取模特页面(模特名)
            
        关闭 驱动.quit()
        输出 "爬取阶段完成"

        // 2. 异步下载阶段 (并行)
        如果 启用下载 并且 下载任务队列 不为空:
            总任务数 = 下载任务队列.大小
            提交 队列中的所有任务 到 线程池，调用 下载工作线程
            
            对于 提交的所有任务:
                等待 任务完成 (future.result())
            
            关闭 线程池.shutdown()
            输出 "异步下载完成"
        
        输出 "程序全部执行完毕"