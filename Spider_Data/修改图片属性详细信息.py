import os
import subprocess
from datetime import datetime, timedelta
import time
import glob

# =======================================
# ⚙️ 配置部分 (请根据你的实际路径修改!)
# =======================================
EXIFTOOL_PATH = r"R:\py\Auto_Image-Spider\Spider_Data\exiftool-13.41_64\exiftool.exe"
BASE_PATH = r"R:\py\Auto_Image-Spider\Selenium_Undetected-chromedriver\tw_8se_me\models\年年"

AUTHOR = "fuaneng"
SOFTWARE = "一刻相册"
COPYRIGHT = "fuaneng@163.com"
USER_COMMENT = "r17+" 

BATCH_SIZE = 50 
IMAGES_PER_DAY = 6 # ⭐ 新增：每 6 张图片增加一天
# =======================================


def rewrite_metadata_batch(folder_path, batch_size):
    """
    [V16 6图/天递增版] 
    修改日期递增逻辑：每处理 6 张图片，日期递增一天。
    同时，在同一天内，图片时间以小时递增。
    """
    folder_name = os.path.basename(folder_path)
    if not folder_name:
        folder_name = os.path.basename(os.path.dirname(folder_path)) or "RootImages"
        
    print(f"\n--- 正在处理文件夹: {folder_name} ---")

    try:
        folder_timestamp = os.path.getmtime(folder_path)
        # 获取文件夹日期作为基准日期，时间重置为 00:00:00
        base_date_only = datetime.fromtimestamp(folder_timestamp).date()
        base_time = datetime.combine(base_date_only, datetime.min.time())
        
    except FileNotFoundError:
        print(f"  ❌ 找不到文件夹: {folder_path}，跳过。")
        return

    extensions = ('.jpg', '.jpeg', '.webp', '.png', '.gif')
    image_files = [f for f in os.listdir(folder_path)
                   if f.lower().endswith(extensions) and os.path.isfile(os.path.join(folder_path, f))]
    
    if not image_files:
        print("  (未找到图片，跳过)")
        return
        
    image_files.sort()
    
    total_files = len(image_files)
    total_batches = (total_files + batch_size - 1) // batch_size
    total_counter = 0 
    cleaned_up_count = 0

    # --- 核心修改：将文件列表分批处理 ---
    for i in range(0, total_files, batch_size):
        
        current_batch_files = image_files[i:i + batch_size]
        current_batch_num = i // batch_size + 1
        
        # 构造当前批次的命令列表
        batch_commands = [
            EXIFTOOL_PATH,
            "-charset", "utf8", 
            "-lang", "en",      
            "-codedcharacters=utf8",
            
            # 中文乱码修复参数
            "-charset", "IPTC=UTF8",
            "-charset", "EXIF=UTF8",
            
            "-overwrite_original_in_place"
        ]
        
        # 为当前批次的每个文件构造命令
        for index_in_batch, image_file in enumerate(current_batch_files):
            file_path = os.path.join(folder_path, image_file)
            
            # ⭐ 核心逻辑修改：每 6 张图递增一天
            
            # 1. 计算天数和日内小时偏移
            # total_counter // IMAGES_PER_DAY 计算天数偏移（0, 0, 0, 0, 0, 0, 1, 1, ...）
            day_offset = total_counter // IMAGES_PER_DAY 
            # total_counter % IMAGES_PER_DAY 计算日内的小时偏移 (0, 1, 2, 3, 4, 5, 0, 1, ...)
            hour_offset = total_counter % IMAGES_PER_DAY 

            # 2. 计算最终时间
            current_time = base_time + timedelta(days=day_offset, hours=hour_offset)
            date_str = current_time.strftime("%Y:%m:%d %H:%M:%S")

            if index_in_batch > 0:
                batch_commands.append("-execute")

            # 2. 清理所有旧信息
            batch_commands.append("-all=")
            
            # 3. 写入所有新信息
            batch_commands.extend([
                # 标题/描述
                f"-XMP:Title={folder_name}",            
                f"-IFD0:ImageDescription={folder_name}",
                
                # 作者/版权
                f"-XMP:Creator={AUTHOR}",
                f"-IFD0:Artist={AUTHOR}",
                f"-IFD0:Software={SOFTWARE}",
                f"-XMP:Rights={COPYRIGHT}",
                f"-IFD0:Copyright={COPYRIGHT}",
                
                # 日期 (元数据标签)
                f"-ExifIFD:DateTimeOriginal={date_str}",
                f"-ExifIFD:CreateDate={date_str}",
                f"-IFD0:ModifyDate={date_str}",

                # 文件系统时间标签 
                f"-FileCreateDate={date_str}",
                f"-FileModifyDate={date_str}",

                # 标记/关键字 
                f"-XMP:Subject={folder_name}",          
                f"-IPTC:Keywords={folder_name}",
                f"-XMP:Rating=5", 
                
                # 备注 
                f"-XMP:UserComment={USER_COMMENT}",      
                f"-ExifIFD:UserComment={USER_COMMENT}",
                
                f"-IFD0:Model=Digital Archive", 
            ])
            
            batch_commands.append(file_path)
            total_counter += 1
        
        # --- 执行当前批次命令 ---
        try:
            subprocess.run(
                batch_commands, 
                check=True, 
                capture_output=True, 
                text=True, 
                encoding='utf-8', 
                errors='replace'
            )
            
            # 成功执行批次后，打印结果
            for image_file in current_batch_files:
                print(f"  ✅ 成功写入: {image_file} (批次 {current_batch_num}/{total_batches})")
            
            # 备份修复：手动清理当前文件夹中所有 *_original 文件
            backup_files = glob.glob(os.path.join(folder_path, '*_original'))
            for backup_file in backup_files:
                try:
                    os.remove(backup_file)
                    cleaned_up_count += 1
                except Exception as e:
                    print(f"  ⚠️ 无法删除备份文件 {os.path.basename(backup_file)}: {e}")


        except subprocess.CalledProcessError as e:
            error_message = e.stderr.strip() if e.stderr else e.stdout.strip()
            if not error_message:
                 error_message = e.stdout.strip()
            print(f"  ❌ 批次写入失败：{folder_name} (批次 {current_batch_num})")
            print(f"    错误: {error_message}")
            return
        except Exception as e:
            print(f"  ❌ 批次发生未知错误: {folder_name} | {e}")
            return
            
    if cleaned_up_count > 0:
        print(f"  🗑️ 已清理 {cleaned_up_count} 个备份文件。")


def process_all(base_folder):
    """处理根目录和所有子目录"""
    for root, dirs, files in os.walk(base_folder):
        rewrite_metadata_batch(root, BATCH_SIZE)


if __name__ == "__main__":
    if not os.path.exists(EXIFTOOL_PATH):
        print(f"❌ 致命错误: ExifTool 未在指定路径找到！\n请检查: {EXIFTOOL_PATH}")
    elif not os.path.isdir(BASE_PATH):
        print(f"❌ 致命错误: 根路径不存在或不是文件夹！\n请检查: {BASE_PATH}")
    else:
        start_time = time.time()
        
        print(f"🚀 开始批量写入元信息 (V16 6图/天递增版)...\n📁 根路径: {BASE_PATH}\n")
        
        process_all(BASE_PATH)
        
        end_time = time.time()
        print("\n" + "="*40)
        print(f"🎯 所有文件处理完成！总耗时：{end_time - start_time:.2f} 秒")
        print("="*40)