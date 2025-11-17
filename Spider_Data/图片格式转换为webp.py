import os
import sys
import tempfile
from PIL import Image
from concurrent.futures import ThreadPoolExecutor, as_completed
import time

# ========================== ⚙️ 配置区 ==========================
# 指定要遍历的根目录
ROOT_DIR = r"C:\Users\fuaneng\Downloads\Telegram Desktop\走路摇 (Zoulu"

# 转换模式选择：
# 1. "AVIF_TO_PNG": 批量转换 .avif 文件为 .png 并删除原文件
# 2. "PNG_TO_WEBP": 批量转换 .png 文件为 .webp 并删除原文件
# 3. "AVIF_TO_WEBP": 批量转换 .avif 文件为 .webp 并删除原文件
# 4. "JPG_TO_WEBP": 批量转换 .jpg/.jpeg 文件为 .webp 并删除原文件
# 5. "TIF_TO_WEBP": 批量转换 .tif/.tiff 文件为 .webp 并删除原文件
# 6. "BMP_TO_WEBP": 批量转换 .bmp 文件为 .webp 并删除原文件
CONVERSION_MODE = "JPG_TO_WEBP"  # <-- 在这里选择您需要的模式！

# 多线程配置
MAX_WORKERS = 30  # 最大并发线程数（根据您的CPU核心数或IO速度调整）

# WebP 转换参数 (仅当 CONVERSION_MODE 为 WebP 模式时有效)
QUALITY = 90      # 推荐 75~95：数字越低体积越小但画质下降越明显
METHOD = 6        # Pillow WEBP 的 method: 0~6，值越大压缩更好但更慢
LOSSLESS = False  # 是否使用无损 WebP，通常设 False ，开启设为 True 时，QUALITY 会被忽略
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


# ------------------------- 转换逻辑 (包含 EXIF 保留和临时文件处理) -------------------------

def convert_avif_to_png(avif_path):
    """处理 AVIF -> PNG 转换并删除原文件，保留 EXIF 信息"""
    folder, filename = os.path.split(avif_path)
    base, _ = os.path.splitext(filename)
    png_path = os.path.join(folder, base + ".png")

    try:
        orig_size = os.path.getsize(avif_path)
        
        with Image.open(avif_path) as img:
            img_info = img.info
            img = img.convert("RGBA")
            img.save(png_path, format="PNG", compress_level=0, **img_info)

        os.remove(avif_path)
        
        new_size = os.path.getsize(png_path)
        
        saved_pct = (1 - new_size / orig_size) * 100 if orig_size > 0 else 0.0
        msg = f"{avif_path} → {png_path} | {human_size(orig_size)} → {human_size(new_size)} | 节省 {saved_pct:.1f}%"
        return True, msg, orig_size, new_size

    except Exception as e:
        return False, f"❌ 转换失败：{avif_path}，错误：{e}", 0, 0


def convert_png_to_webp(png_path, quality, method, lossless):
    """处理 PNG -> WebP 转换并删除原文件，保留 EXIF 信息"""
    folder, filename = os.path.split(png_path)
    base, _ = os.path.splitext(filename)
    webp_path = os.path.join(folder, base + ".webp")

    try: orig_size = os.path.getsize(png_path)
    except OSError as e: return False, f"无法读取文件大小: {png_path} | {e}", 0, 0

    try:
        with Image.open(png_path) as img:
            img_info = img.info
            img = img.convert("RGBA")

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
                
                if os.path.exists(webp_path): os.remove(webp_path)
                os.replace(tmpname, webp_path)
            finally:
                if os.path.exists(tmpname):
                    try: os.remove(tmpname)
                    except Exception: pass

        new_size = os.path.getsize(webp_path)
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
    
    try: orig_size = os.path.getsize(avif_path)
    except OSError as e: return False, f"无法读取文件大小: {avif_path} | {e}", 0, 0

    try:
        with Image.open(avif_path) as img:
            img_info = img.info
            img = img.convert("RGBA")

            img.save(
                webp_path,
                format="WEBP",
                quality=quality,
                method=method,
                lossless=lossless,
                **img_info
            )

        os.remove(avif_path)
        new_size = os.path.getsize(webp_path)

        saved_pct = (1 - new_size / orig_size) * 100 if orig_size > 0 else 0.0
        msg = f"{avif_path} → {webp_path} | {human_size(orig_size)} → {human_size(new_size)} | 节省 {saved_pct:.1f}%"
        return True, msg, orig_size, new_size

    except Exception as e:
        return False, f"❌ 转换失败：{avif_path}，错误：{e}", 0, 0


def convert_jpg_to_webp(jpg_path, quality, method, lossless):
    """处理 JPG/JPEG -> WebP 转换并删除原文件，保留 EXIF 信息"""
    folder, filename = os.path.split(jpg_path)
    base, _ = os.path.splitext(filename)
    webp_path = os.path.join(folder, base + ".webp")

    try: orig_size = os.path.getsize(jpg_path)
    except OSError as e: return False, f"无法读取文件大小: {jpg_path} | {e}", 0, 0

    try:
        with Image.open(jpg_path) as img:
            img_info = img.info
            img = img.convert("RGBA")

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
                
                if os.path.exists(webp_path): os.remove(webp_path)
                os.replace(tmpname, webp_path)
            finally:
                if os.path.exists(tmpname):
                    try: os.remove(tmpname)
                    except Exception: pass

        new_size = os.path.getsize(webp_path)
        os.remove(jpg_path)
        
        saved_pct = (1 - new_size / orig_size) * 100 if orig_size > 0 else 0.0
        msg = f"{jpg_path} -> {webp_path} | {human_size(orig_size)} → {human_size(new_size)} | 节省 {saved_pct:.1f}%"
        return True, msg, orig_size, new_size

    except Exception as e:
        return False, f"❌ 转换失败：{jpg_path}, 错误: {e}", 0, 0


def convert_tif_to_webp(tif_path, quality, method, lossless):
    """处理 TIF/TIFF -> WebP 转换并删除原文件，保留 EXIF/Info 信息"""
    folder, filename = os.path.split(tif_path)
    base, _ = os.path.splitext(filename)
    webp_path = os.path.join(folder, base + ".webp")

    try: orig_size = os.path.getsize(tif_path)
    except OSError as e: return False, f"无法读取文件大小: {tif_path} | {e}", 0, 0

    try:
        with Image.open(tif_path) as img:
            img_info = img.info
            img = img.convert("RGBA")

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
                
                if os.path.exists(webp_path): os.remove(webp_path)
                os.replace(tmpname, webp_path)
            finally:
                if os.path.exists(tmpname):
                    try: os.remove(tmpname)
                    except Exception: pass

        new_size = os.path.getsize(webp_path)
        os.remove(tif_path)
        
        saved_pct = (1 - new_size / orig_size) * 100 if orig_size > 0 else 0.0
        msg = f"{tif_path} -> {webp_path} | {human_size(orig_size)} → {human_size(new_size)} | 节省 {saved_pct:.1f}%"
        return True, msg, orig_size, new_size

    except Exception as e:
        return False, f"❌ 转换失败：{tif_path}, 错误: {e}", 0, 0


def convert_bmp_to_webp(bmp_path, quality, method, lossless):
    """处理 BMP -> WebP 转换并删除原文件，保留 Info 信息"""
    folder, filename = os.path.split(bmp_path)
    base, _ = os.path.splitext(filename)
    webp_path = os.path.join(folder, base + ".webp")

    try: orig_size = os.path.getsize(bmp_path)
    except OSError as e: return False, f"无法读取文件大小: {bmp_path} | {e}", 0, 0

    try:
        with Image.open(bmp_path) as img:
            img_info = img.info
            img = img.convert("RGBA")

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
                
                if os.path.exists(webp_path): os.remove(webp_path)
                os.replace(tmpname, webp_path)
            finally:
                if os.path.exists(tmpname):
                    try: os.remove(tmpname)
                    except Exception: pass

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

    elif mode == "TIF_TO_WEBP":
        target_ext = (".tif", ".tiff")
        converter_func = convert_tif_to_webp
        func_args = [quality, method, lossless]

    elif mode == "BMP_TO_WEBP":
        target_ext = (".bmp",)
        converter_func = convert_bmp_to_webp
        func_args = [quality, method, lossless]
        
    else:
        print(f"错误：不支持的转换模式：{mode}")
        return

    print(f"开始扫描和处理文件 (模式: {mode}, 线程数: {workers})...")
    
    file_paths = []
    # 收集所有符合条件的文件路径
    for folder, _, files in os.walk(root_dir):
        for file in files:
            if file.lower().endswith(target_ext):
                file_paths.append(os.path.join(folder, file))

    total_count = len(file_paths)
    if total_count == 0:
        # target_ext 是元组时，将其漂亮地打印出来
        ext_str = "/".join(e.upper() for e in (target_ext if isinstance(target_ext, tuple) else [target_ext]))
        print(f"在 {root_dir} 及其子目录下未找到任何 {ext_str} 文件。")
        return

    # 启动多线程
    success_count = 0
    fail_count = 0
    total_orig_size = 0
    total_new_size = 0
    
    start_time = time.time()

    with ThreadPoolExecutor(max_workers=workers) as executor:
        # 提交所有任务
        futures = {executor.submit(converter_func, path, *func_args): path for path in file_paths}
        
        # 实时处理完成的任务
        for future in as_completed(futures):
            ok, msg, orig_size, new_size = future.result()
            
            if ok:
                success_count += 1
                total_orig_size += orig_size
                total_new_size += new_size
                print(f"✅ {msg}")
            else:
                fail_count += 1
                print(f"❌ {msg}")
                
    end_time = time.time()
    
    # 统计信息
    if PRINT_SUMMARY:
        print("\n==== 总结 ====")
        print(f"处理时间: {end_time - start_time:.2f} 秒")
        print(f"扫描目录: {root_dir}")
        print(f"找到文件总数: {total_count}")
        print(f"成功转换: {success_count}，失败: {fail_count}")
        
        # 根据实际转换结果计算节省
        if success_count > 0:
            total_saved_bytes = total_orig_size - total_new_size
            saved_pct = (total_saved_bytes / total_orig_size) * 100 if total_orig_size > 0 else 0.0
            
            print("--- 转换统计 (仅针对成功转换的文件) ---")
            print(f"转换前总大小: {human_size(total_orig_size)}")
            print(f"转换后总大小: {human_size(total_new_size)}")
            print(f"总计节省: {human_size(total_saved_bytes)} ({saved_pct:.1f}%)")
        else:
            print("没有成功转换的文件，跳过节省统计。")


def main():
    if not os.path.isdir(ROOT_DIR):
        print(f"错误：指定路径不存在或不是文件夹：{ROOT_DIR}")
        sys.exit(1)
        
    print(f"*** 图像批量转换工具 ***")
    print(f"根目录: {ROOT_DIR}")
    print(f"模式: {CONVERSION_MODE}")
    # 检查所有 WebP 模式
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

if __name__ == "__main__":
    main()