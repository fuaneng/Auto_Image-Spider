
import re

def get_original_url(preview_url):
    """
    传入 civitai 预览图 URL，自动转换为原图 URL
    支持数字 ID 和 UUID 两种格式
    """
    # 提取路径中的 UUID 或数字ID
    m = re.search(r'/([0-9a-fA-F-]{8,36})/', preview_url)
    if not m:
        return None
    image_id = m.group(1)
    # 提取前缀域名路径
    prefix = preview_url.split(f'/{image_id}/')[0]
    # 拼接原图链接
    return f"{prefix}/{image_id}/original=true"

# 示例
preview = "https://image.civitai.com/xG1nkqKTMzGDvpLrqFT7WA/1b60b9e7-5da9-4458-8c83-eb22be515f60/anim=false,width=450,optimized=true/99690108.jpeg"
print(get_original_url(preview))
