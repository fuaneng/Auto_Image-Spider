主页：https://civitai.com/
图片预览地址：https://civitai.com/images?tags=(tag)，(tag)为图片标签,比如"5133"，例如："https://civitai.com/images?tags=5133"
在预览地址下打开 network fetch/xhr 
请求标头url为："https://civitai.com/api/trpc/image.getInfinite?input=%7B%22json%22%3A%7B%22period%22%3A%22Month%22%2C%22periodMode%22%3A%22published%22%2C%22sort%22%3A%22Most%20Reactions%22%2C%22types%22%3A%5B%22image%22%5D%2C%22withMeta%22%3Afalse%2C%22tags%22%3A%5B5133%5D%2C%22useIndex%22%3Atrue%2C%22browsingLevel%22%3A28%2C%22include%22%3A%5B%22cosmetics%22%5D%2C%22excludedTagIds%22%3A%5B415792%2C426772%2C5188%2C5249%2C130818%2C130820%2C133182%2C5351%2C306619%2C154326%2C161829%2C163032%5D%2C%22disablePoi%22%3Atrue%2C%22disableMinor%22%3Atrue%2C%22cursor%22%3Anull%2C%22authed%22%3Atrue%7D%2C%22meta%22%3A%7B%22values%22%3A%7B%22cursor%22%3A%5B%22undefined%22%5D%7D%7D%7D"
滚动加载更多图片时，请求url中的参数会变化，表示下一页数据，如："https://civitai.com/api/trpc/image.getInfinite?input=%7B%22json%22%3A%7B%22period%22%3A%22Month%22%2C%22periodMode%22%3A%22published%22%2C%22sort%22%3A%22Most%20Reactions%22%2C%22types%22%3A%5B%22image%22%5D%2C%22withMeta%22%3Afalse%2C%22tags%22%3A%5B5133%5D%2C%22useIndex%22%3Atrue%2C%22browsingLevel%22%3A28%2C%22include%22%3A%5B%22cosmetics%22%5D%2C%22excludedTagIds%22%3A%5B415792%2C426772%2C5188%2C5249%2C130818%2C130820%2C133182%2C5351%2C306619%2C154326%2C161829%2C163032%5D%2C%22disablePoi%22%3Atrue%2C%22disableMinor%22%3Atrue%2C%22cursor%22%3A%2250%7C1760155262152%22%2C%22authed%22%3Atrue%7D%7D"

network fetch/xhr 请求响应内容（json格式）：
          {
            "id": 105270601,
            "reactionCount": 1478,
            "commentCount": 1,
            "collectedCount": 119,
            "index": 1,
            "postId": 23354518,
            "url": "ac9ab616-486e-4b3a-b16f-09345338bf1d",
            "nsfwLevel": 4,
            "aiNsfwLevel": 0,
            "width": 1248,
            "height": 1824,
            "hash": "UZGRuG~VT0%Lo}o#kWbbxt%2$*j]WVWVkCoL",
            "hideMeta": false,
            "sortAt": "2025-10-11T03:10:00.000Z",
            "type": "image",
            "userId": 316908,
            "needsReview": null,
            "hasMeta": true,
            "onSite": false,
            "postedToId": null,
            "combinedNsfwLevel": 4,
            "baseModel": "Illustrious",
            "modelVersionIds": [1306061, 1348455, 1896532, 1920055, 1967210, 2291129],
            "toolIds": [],
            "techniqueIds": [],
            "existedAtUnix": 1760101623583,
            "sortAtUnix": 1760152200000,
            "tagIds": [4, 251, 531, 697, 1238, 2687, 3726, 5133, 5193, 5262, 5773, 6997, 7157, 111763, 111960, 112269, 113933, 115378, 116858, 116880, 117860, 121765, 122902, 125411, 126119, 131304, 132582, 133718, 135884, 143215, 144825, 156603, 161852, 161932, 162271, 163890, 233029],
            "modelVersionIdsManual": [],
            "minor": false,
            "blockedFor": null,
            "remixOfId": null,
            "hasPositivePrompt": true,
            "availability": "Public",
            "poi": false,
            "acceptableMinor": false,
            "stats": {
              "views": 0,
              "downloads": 0,
              "shares": 0
            }
          },
图片url拼接规则：基础路径/url值/id值
基础路径：	"https://image.civitai.com/xG1nkqKTMzGDvpLrqFT7WA/"	（平台基础路径）这是固定的文件存储CDN 路径。
提取"url"值: "ac9ab616-486e-4b3a-b16f-09345338bf1d"	
提取"id"值: "105270601"
拼接示例：https://image.civitai.com/xG1nkqKTMzGDvpLrqFT7WA/" + "ac9ab616-486e-4b3a-b16f-09345338bf1d" + "105270601"
完整示例："https://image.civitai.com/xG1nkqKTMzGDvpLrqFT7WA/ac9ab616-486e-4b3a-b16f-09345338bf1d/105270601"

将获取后的所有数据分列实时保存到CSV文件
    def write_to_csv(self,  name, url, csv_path, tag):
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
                        writer.writerow(['ImageName', 'URL', 'TAG'])
                        
                    writer.writerow([name, url, tag])
        except Exception as e:
            print(f"[{tag}] [✗] 写入 CSV 出错: {e}")



Redis 去重逻辑示例
REDIS_HOST = 'localhost'
REDIS_PORT = 6379
REDIS_KEY = 'image_md5_set_civitai' # 使用 URL 作为唯一标识符
# ----------------------------- 配置区（请根据需要修改路径） -----------------------------
# ！！！注意，必须配合 selenium 浏览器使用！！！
CHROME_DRIVER_PATH = r"C:\Program Files\Google\chromedriver-win64\chromedriver.exe"  # 你的 chromedriver 路径
已经登录的用户数据目录已经保存至本地路径：USER_DATA_DIR = r"R:\py\Civitai_保存和导入 Cookies\civitai_data"     
TAG_TXT_PATH = r"R:\py\Auto_Image-Spider\保存和导入 Cookies\civitai\tag.txt"  # 存放标签文件路径
```tag.txt
5133
5122
6997

```

表格保存目录
CSV_DIR_PATH = r"R:\py\Auto_Image-Spider\Selenium_Cookies\


Civitai_保存和导入 Cookies\Civitai_图片数据_CSV"
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
            'Referer': 'https://civitai.com/' 
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




