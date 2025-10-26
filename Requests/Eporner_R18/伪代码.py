# 第一部分：搜索图片集合标签，获取标签列表
网址主页：https://www.eporner.com/
搜索请求url："https://www.eporner.com/search-photos/{人名}/{页码}/"
示例请求url："https://www.eporner.com/search-photos/anna-l-vWIOQsU8/2/"，如果状态码404则表示没有更多页码。

Network/Doc文档response响应示例：
```html

                    <div id="vidresults" class="showall">
                        <div id="container" class="photosgrid">
                            <div class="mbphoto2" style="grid-row-end: span 28;" id="pf1692119">
                                <div class="mbphoto2_galleryico">35</div>
                                <a href="/gallery/KoA859GuX6R/Hegre-Anna-L-Sensual-Sunset/" id="ah30976518">
                                    <img id="t30976518" src="https://static-eu-cdn.eporner.com/gallery/6R/uX/KoA859GuX6R/30976518-anna-l-sensual-sunset-13-14000px_296x1000.jpg" alt="amateur photo [Hegre] Anna L (Sensual Sunset" title="amateur photo [Hegre] Anna L (Sensual Sunset" width="296" height="393">
                                    <div class="mbtitphoto2">[Hegre] Anna L (Sensual Sunset </div>
                                </a>
                            </div>

```
逐个获取每个图片集合标签下的'a'元素下的'href'属性的值，即为图片详情页请求url。
示例：href='/gallery/KoA859GuX6R/Hegre-Anna-L-Sensual-Sunset/'，完整请求url为：https://www.eporner.com/gallery/KoA859GuX6R/Hegre-Anna-L-Sensual-Sunset/

提取'div'元素下'class'属性值为'mbtitphoto2'的文本内容，即为图片集合的标题，这个值为图片集合的名称。需要写入到csv文件的'所属集合'字段。



# 第二部分：访问图片详情页，获取图片信息并写入表格
详情页请求url的响应示例：
```html
<div id="container" class="photosgrid gallerygrid">
<div class="mbphoto2" id="pf22644354" style="grid-row-end: span 16;" onclick="return EP.gallery.showSlide('hbIdVGHQI6s', 0);" >
<a href="/photo/Yt2lY7NnvPI/anna-l-finger-fucking-01-14000px/" id="ah22644354" >
<img id="t22644354" src="https://static-eu-cdn.eporner.com/gallery/6s/QI/hbIdVGHQI6s/22644354-anna-l-finger-fucking-01-14000px_296x1000.jpg" alt="amateur photo anna-l-finger-fucking-01-14000px" title="amateur photo anna-l-finger-fucking-01-14000px" width="296" height="221"> </a>
<div class="sg_gallery_meta">
<span class="mbvie">610</span>
<span class="mbrate">50%</span>
</div>
</div>

```
提取信息并写入表格
提取url：'img'元素下的'src'属性，即图片缩略图url，去除'_296x1000'后为完整图片url。'_296x1000'为缩略图标识符。不一定都是这个值也可能是其他值，需动态处理。
示例：src='https://static-eu-cdn.eporner.com/gallery/6s/QI/hbIdVGHQI6s/22644354-anna-l-finger-fucking-01-14000px_296x1000.jpg'
完整图片url：'https://static-eu-cdn.eporner.com/gallery/6s/QI/hbIdVGHQI6s/22644354-anna-l-finger-fucking-01-14000px.jpg'



提取标题：'img'元素下的'alt'属性。
示例：alt='amateur photo anna-l-finger-fucking-01-14000px'，标题为'anna-l-finger-fucking-01-14000px'。

标题也是名称，去除'-14000px'后为名称'anna-l-finger-fucking-01'。


写入CSV文件：字段：图片URL、标题、名称、所属集合
注意事项：所属集合字段需要从第一部分的图片集合标签中提取。

# 第三部分：启动下载图片
启动下载图片到本地文件夹
解耦式异步多线程下载图片url到本地文件夹，文件命名为标题字段，保留原始图片格式扩展名。
{人名}标签文档本地路径：“R:\py\Auto_Image-Spider\Requests\Eporner_R18\人名.txt”
"人名.txt"内容示例：
```txt
anna-l-vWIOQsU8
danny-vWIOQsU8
```

csv文件路径存储路径：“R:\py\Auto_Image-Spider\Requests\Eporner_R18\all_images_data.csv”
下载图片存储路径“R:\py\Auto_Image-Spider\Requests\Eporner_R18\images\”
示例：R:\py\Auto_Image-Spider\Requests\Eporner_R18\images\anna-l-and-danny-sexual-attraction-0013.jpg

