主页：https://tw.8se.me/photoShow.html?id=TxYGVsIRVwO2tEcYcMaE8XBGYTQrUzAvczRrdnQyVG45ajdMMTBjRW5BWENIZ3RROG5JUE12NlR4RVE9"

模特作品页：https://tw.8se.me/model/id-{model_id}.html

model_id.txt
```txt
67e1c853d3528   # {model_id}
白浅浅          # 模特真姓名{model_name}
6751as151a223   # {model_id}
高七千          # 模特真姓名{model_name}

```

作品页 network doc 响应
https://xchina.fit/
get 请求地址：https://tw.8se.me/model/id-{model_id}.html
```html
                            <div class="item photo">
                                <a href="/photo/id-690e2f7fa5358.html" title="梨霜兒 Vol. 10915">
                                    <div role="img" class="img" style="background-image:url('https://img.xchina.io/photos2/690e2f7fa5358/0001_600x0.webp');"></div>
                                </a>
                                <div class="text">
                                    <div class="subs">
                                        <div>
                                            <a href="/photos/series-5f1476781eab4.html">秀人網</a>
                                        </div>
                                        <div>Vol. 10915 (2025.10.27)</div>
                                    </div>
                                    <div class="title">
                                        <a href="/photo/id-690e2f7fa5358.html">梨霜兒</a>
                                    </div>
                                    <div>
                                        <div class="model-container">
                                            <a href="/videos/model-67e1c853d3528.html" class="model-item">白淺淺</a>
                                        </div>
                                    </div>
                                </div>
                                <div class="tags">
                                    <div>74P</div>
                                    <div class="empty"></div>
                                    <div class="empty"></div>
                                    <div class="empty"></div>
                                </div>
                            </div>
```

提取作品集标题以及作品集详情页链接
标题所在标签：<a href="/photo/id-690e2f7fa5358.html" title="梨霜兒 Vol. 10915">，'title'属性为作品标题
获取第一张图片url：<div role="img" class="img" style="background-image:url('https://img.xchina.io/photos2/690e2f7fa5358/0001_600x0.webp');"></div>，'style'属性为图片url,图片url为'background-image'属性值https://img.xchina.io/photos2/690e2f7fa5358/0001_600x0.webp,
清洗url，获取原图url,将'_600x0.webp'替换为'.jpg'如：https://img.xchina.io/photos2/690e2f7fa5358/0001.jpg

根据 div class="tags" 标签下的 div标签内容确定图片数量：<div>74P</div>，'div'标签内容为图片数量，清洗'74P'，获取'74'作为图片数量，按照第一张图命名规则获取所有图片名称，如：0001.jpg,0002.jpg,...0074.jpg，
按名称可以得到所有图片原图url，如：https://img.xchina.io/photos2/690e2f7fa5358/0001.jpg,https://img.xchina.io/photos2/690e2f7fa5358/0002.jpg,...https://img.xchina.io/photos2/690e2f7fa5358/0074.jpg

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



标签数据路径：{model_id}标签文件本地文件路径：R:\py\Auto_Image-Spider\Selenium\en_girlstop_info\tw_8se_me\model_id.txt

CSV文件存储路径:R:\py\Auto_Image-Spider\Selenium_Undetected-chromedriver\en_girlstop_info\tw_8se_me





