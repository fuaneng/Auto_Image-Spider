import os
import sys
import tempfile
from PIL import Image

# ========================== ⚙️ 配置区 ==========================
# 指定要遍历的根目录
ROOT_DIR = r"R:\py\Auto_Image-Spider\Selenium_Undetected-chromedriver\en_girlstop_info\models"

# 转换模式选择：
# 1. "AVIF_TO_PNG": 批量转换 .avif 文件为 .png 并删除原文件
# 2. "PNG_TO_WEBP": 批量转换 .png 文件为 .webp 并删除原文件
# 3. "AVIF_TO_WEBP": 批量转换 .avif 文件为 .webp 并删除原文件
# 4. "JPG_TO_WEBP": 批量转换 .jpg/.jpeg 文件为 .webp 并删除原文件 
# 5. "TIF_TO_WEBP": 批量转换 .tif 文件为 .webp 并删除原文件  
# 6. "BMP_TO_WEBP": 批量转换 .bmp 文件为 .webp 并删除原文件  
CONVERSION_MODE = "JPG_TO_WEBP"  # <-- 在这里选择您需要的模式！

# 多线程配置
MAX_WORKERS = 30  # 最大并发线程数（根据您的CPU核心数或IO速度调整）

# WebP 转换参数 (仅当 CONVERSION_MODE 为 PNG_TO_WEBP, AVIF_TO_WEBP, JPG_TO_WEBP 时有效)
QUALITY = 90      # 推荐 75~95：数字越低体积越小但画质下降越明显
METHOD = 6        # Pillow WEBP 的 method: 0~6，值越大压缩更好但更慢
LOSSLESS = True  # 是否使用无损 WebP，通常设 False，开启设为 True 设置为 True 时，QUALITY 会被忽略
PRINT_SUMMARY = True # 是否打印转换摘要
# =============================================================


# 辅助函数：将字节转换为可读单位
def human_size(n):
    """返回可读的字节单位"""
    for unit in ("B", "KB", "MB", "GB"):
        if n < 1024.0:
            return f"{n:.1f}{unit}"
        n /= 1024.0
    return f"{n:.1f}TB"


# ------------------------- 转换逻辑 (已包含 EXIF 保留) -------------------------

def convert_avif_to_png(avif_path):
    """处理 AVIF -> PNG 转换并删除原文件，保留 EXIF 信息"""
    folder, filename = os.path.split(avif_path)
    base, _ = os.path.splitext(filename)
    png_path = os.path.join(folder, base + ".png")

    try:
        # 获取原始大小，用于后续统计
        orig_size = os.path.getsize(avif_path)
        
        with Image.open(avif_path) as img:
            # 捕获原始 EXIF/Info 数据
            # **注意：PNG对EXIF支持有限，Pillow会尝试将其他元数据（如ICC Profile）传递**
            img_info = img.info

            # 确保使用 RGBA 模式
            img = img.convert("RGBA")
            
            # 保存为 PNG，通过 **img_info** 传递原始信息
            img.save(png_path, format="PNG", compress_level=0, **img_info)

        # 删除原始 .avif 文件
        os.remove(avif_path)
        
        # 获取新文件大小
        new_size = os.path.getsize(png_path)
        
        saved_pct = (1 - new_size / orig_size) * 100 if orig_size > 0 else 0.0
        msg = f"{avif_path} → {png_path} | {human_size(orig_size)} → {human_size(new_size)} | 节省 {saved_pct:.1f}%"
        return True, msg, orig_size, new_size

    except Exception as e:
        # 如果文件不存在，orig_size获取可能会失败，这里统一处理
        return False, f"❌ 转换失败：{avif_path}，错误：{e}", 0, 0


def convert_png_to_webp(png_path, quality, method, lossless):
    """处理 PNG -> WebP 转换并删除原文件，保留 EXIF 信息"""
    folder, filename = os.path.split(png_path)
    base, _ = os.path.splitext(filename)
    webp_path = os.path.join(folder, base + ".webp")

    # 获取原始大小
    try: orig_size = os.path.getsize(png_path)
    except OSError as e: return False, f"无法读取文件大小: {png_path} | {e}", 0, 0

    try:
        with Image.open(png_path) as img:
            # 捕获原始 EXIF/Info 数据
            img_info = img.info
            
            img = img.convert("RGBA")

            # 使用临时文件先保存（避免半文件覆盖）
            fd, tmpname = tempfile.mkstemp(suffix=".webp", dir=folder)
            os.close(fd)
            
            try:
                # 保存为 WEBP，通过 **img_info** 传递原始信息
                img.save(
                    tmpname,
                    format="WEBP",
                    quality=quality,
                    method=method,
                    lossless=lossless,
                    **img_info 
                )
                
                # 替换（覆盖）目标文件
                if os.path.exists(webp_path): os.remove(webp_path)
                os.replace(tmpname, webp_path)
            finally:
                # 尝试删除临时文件
                if os.path.exists(tmpname):
                    try: os.remove(tmpname)
                    except Exception: pass

        # 获取新文件大小
        new_size = os.path.getsize(webp_path)
        
        # 删除原 PNG
        os.remove(png_path)
        
        saved_pct = (1 - new_size / orig_size) * 100 if orig_size > 0 else 0.0
        msg = f"{png_path} -> {webp_path} | {human_size(orig_size)} → {human_size(new_size)} | 节省 {saved_pct:.1f}%"
        return True, msg, orig_size, new_size

    except Exception as e:
        return False, f"❌ 转换失败：{png_path}, 错误: {e}", 0, 0


def convert_avif_to_webp(avif_path, quality, method, lossless):
    """处理 AVIF -> WebP 转换并删除原文件，保留 EXIF 信息"""
    folder, filename = os.path.split(avif_path)
    base, _ = os.path.splitext(filename)
    webp_path = os.path.join(folder, base + ".webp")
    
    # 获取原始大小
    try: orig_size = os.path.getsize(avif_path)
    except OSError as e: return False, f"无法读取文件大小: {avif_path} | {e}", 0, 0

    try:
        with Image.open(avif_path) as img:
            # 捕获原始 EXIF/Info 数据
            img_info = img.info
            
            img = img.convert("RGBA")

            # 保存为 WebP，通过 **img_info** 传递原始信息
            # 简化：不使用临时文件
            img.save(
                webp_path,
                format="WEBP",
                quality=quality,
                method=method,
                lossless=lossless,
                **img_info
            )

        # 删除原始 .avif 文件
        os.remove(avif_path)
        new_size = os.path.getsize(webp_path)

        saved_pct = (1 - new_size / orig_size) * 100 if orig_size > 0 else 0.0
        msg = f"{avif_path} → {webp_path} | {human_size(orig_size)} → {human_size(new_size)} | 节省 {saved_pct:.1f}%"
        return True, msg, orig_size, new_size

    except Exception as e:
        return False, f"❌ 转换失败：{avif_path}，错误：{e}", 0, 0


def convert_jpg_to_webp(jpg_path, quality, method, lossless):
    """处理 JPG/JPEG -> WebP 转换并删除原文件，保留 EXIF 信息 (新增函数)"""
    folder, filename = os.path.split(jpg_path)
    base, _ = os.path.splitext(filename)
    webp_path = os.path.join(folder, base + ".webp")

    # 获取原始大小
    try: orig_size = os.path.getsize(jpg_path)
    except OSError as e: return False, f"无法读取文件大小: {jpg_path} | {e}", 0, 0

    try:
        with Image.open(jpg_path) as img:
            # 捕获原始 EXIF/Info 数据
            img_info = img.info
            
            # JPG通常没有Alpha通道，转换成RGBA以支持WebP
            img = img.convert("RGBA")

            # 使用临时文件先保存（避免半文件覆盖）
            fd, tmpname = tempfile.mkstemp(suffix=".webp", dir=folder)
            os.close(fd)
            
            try:
                # 保存为 WEBP，通过 **img_info** 传递原始信息
                img.save(
                    tmpname,
                    format="WEBP",
                    quality=quality,
                    method=method,
                    lossless=lossless,
                    **img_info 
                )
                
                # 替换（覆盖）目标文件
                if os.path.exists(webp_path): os.remove(webp_path)
                os.replace(tmpname, webp_path)
            finally:
                # 尝试删除临时文件
                if os.path.exists(tmpname):
                    try: os.remove(tmpname)
                    except Exception: pass

        # 获取新文件大小
        new_size = os.path.getsize(webp_path)
        
        # 删除原 JPG
        os.remove(jpg_path)
        
        saved_pct = (1 - new_size / orig_size) * 100 if orig_size > 0 else 0.0
        msg = f"{jpg_path} -> {webp_path} | {human_size(orig_size)} → {human_size(new_size)} | 节省 {saved_pct:.1f}%"
        return True, msg, orig_size, new_size

    except Exception as e:
        return False, f"❌ 转换失败：{jpg_path}, 错误: {e}", 0, 0

# ------------------------- 转换逻辑 (续 - TIF/TIFF) -------------------------

def convert_tif_to_webp(tif_path, quality, method, lossless):
    """处理 TIF/TIFF -> WebP 转换并删除原文件，保留 EXIF/Info 信息"""
    folder, filename = os.path.split(tif_path)
    base, _ = os.path.splitext(filename)
    webp_path = os.path.join(folder, base + ".webp")

    # 获取原始大小
    try: orig_size = os.path.getsize(tif_path)
    except OSError as e: return False, f"无法读取文件大小: {tif_path} | {e}", 0, 0

    try:
        with Image.open(tif_path) as img:
            # 捕获原始 EXIF/Info 数据
            img_info = img.info
            
            # 确保转换为支持透明度的 RGBA 模式
            img = img.convert("RGBA")

            # 使用临时文件保存
            fd, tmpname = tempfile.mkstemp(suffix=".webp", dir=folder)
            os.close(fd)
            
            try:
                img.save(
                    tmpname,
                    format="WEBP",
                    quality=quality,
                    method=method,
                    lossless=lossless,
                    **img_info 
                )
                
                # 替换目标文件
                if os.path.exists(webp_path): os.remove(webp_path)
                os.replace(tmpname, webp_path)
            finally:
                if os.path.exists(tmpname):
                    try: os.remove(tmpname)
                    except Exception: pass

        # 统计和清理
        new_size = os.path.getsize(webp_path)
        os.remove(tif_path)
        
        saved_pct = (1 - new_size / orig_size) * 100 if orig_size > 0 else 0.0
        msg = f"{tif_path} -> {webp_path} | {human_size(orig_size)} → {human_size(new_size)} | 节省 {saved_pct:.1f}%"
        return True, msg, orig_size, new_size

    except Exception as e:
        return False, f"❌ 转换失败：{tif_path}, 错误: {e}", 0, 0
    
# ------------------------- 转换逻辑 (续 - BMP) -------------------------

def convert_bmp_to_webp(bmp_path, quality, method, lossless):
    """处理 BMP -> WebP 转换并删除原文件，保留 Info 信息"""
    folder, filename = os.path.split(bmp_path)
    base, _ = os.path.splitext(filename)
    webp_path = os.path.join(folder, base + ".webp")

    # 获取原始大小
    try: orig_size = os.path.getsize(bmp_path)
    except OSError as e: return False, f"无法读取文件大小: {bmp_path} | {e}", 0, 0

    try:
        with Image.open(bmp_path) as img:
            # 捕获原始 Info 数据
            img_info = img.info
            
            # 确保转换为支持透明度的 RGBA 模式
            img = img.convert("RGBA")

            # 使用临时文件保存
            fd, tmpname = tempfile.mkstemp(suffix=".webp", dir=folder)
            os.close(fd)
            
            try:
                img.save(
                    tmpname,
                    format="WEBP",
                    quality=quality,
                    method=method,
                    lossless=lossless,
                    **img_info 
                )
                
                # 替换目标文件
                if os.path.exists(webp_path): os.remove(webp_path)
                os.replace(tmpname, webp_path)
            finally:
                if os.path.exists(tmpname):
                    try: os.remove(tmpname)
                    except Exception: pass

        # 统计和清理
        new_size = os.path.getsize(webp_path)
        os.remove(bmp_path)
        
        saved_pct = (1 - new_size / orig_size) * 100 if orig_size > 0 else 0.0
        msg = f"{bmp_path} -> {webp_path} | {human_size(orig_size)} → {human_size(new_size)} | 节省 {saved_pct:.1f}%"
        return True, msg, orig_size, new_size

    except Exception as e:
        return False, f"❌ 转换失败：{bmp_path}, 错误: {e}", 0, 0

# ------------------------- 主控逻辑 -------------------------

def walk_and_convert(root_dir, mode, workers, quality, method, lossless):
    """遍历文件并使用多线程执行转换"""
    
    # 根据模式确定目标扩展名、转换函数和所需参数
    if mode == "AVIF_TO_PNG":
        target_ext = (".avif",)
        converter_func = convert_avif_to_png
        func_args = []
        
    elif mode == "PNG_TO_WEBP":
        target_ext = (".png",)
        converter_func = convert_png_to_webp
        func_args = [quality, method, lossless]
        
    elif mode == "AVIF_TO_WEBP":
        target_ext = (".avif",)
        converter_func = convert_avif_to_webp
        func_args = [quality, method, lossless]

    elif mode == "JPG_TO_WEBP":
        target_ext = (".jpg", ".jpeg")
        converter_func = convert_jpg_to_webp
        func_args = [quality, method, lossless]

    elif mode == "TIF_TO_WEBP": # <--- 新增的模式
        target_ext = (".tif", ".tiff")
        converter_func = convert_tif_to_webp
        func_args = [quality, method, lossless]

    elif mode == "BMP_TO_WEBP": # <--- 新增的模式
        target_ext = (".bmp",)
        converter_func = convert_bmp_to_webp
        func_args = [quality, method, lossless]
        
    else:
        print(f"错误：不支持的转换模式：{mode}")
        return
    # ... (其余部分保持不变)


def main():
    if not os.path.isdir(ROOT_DIR):
        print(f"错误：指定路径不存在或不是文件夹：{ROOT_DIR}")
        sys.exit(1)
        
    print(f"*** 图像批量转换工具 ***")
    print(f"根目录: {ROOT_DIR}")
    print(f"模式: {CONVERSION_MODE}")
    # 在这里增加 TIF_TO_WEBP 和 BMP_TO_WEBP
    if CONVERSION_MODE in ["PNG_TO_WEBP", "AVIF_TO_WEBP", "JPG_TO_WEBP", "TIF_TO_WEBP", "BMP_TO_WEBP"]:
        print(f"WebP 参数: quality={QUALITY}, method={METHOD}, lossless={LOSSLESS}")
        
    walk_and_convert(
        ROOT_DIR, 
        CONVERSION_MODE, 
        MAX_WORKERS, 
        QUALITY, 
        METHOD, 
        LOSSLESS
    )
    
    print("转换过程完成。")