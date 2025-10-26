import pandas as pd
import os
import shutil

# --- 可调整的变量和参数 ---

# 1. Excel 文件路径
EXCEL_PATH = r"R:\py\Auto_Image-Spider\Requests\Eporner_R18\image_data.xlsx"

# 2. 存放图片的根目录
IMAGE_DIR = r"R:\py\Auto_Image-Spider\Requests\Eporner_R18\images"

# 3. Excel 中对应的列名
TITLE_COLUMN = "标题"    # 包含图片主文件名的列名
FOLDER_COLUMN = "文件夹" # 包含目标子文件夹名称的列名

# --------------------------

def classify_images_flexible():
    """
    根据 Excel 表格中的信息，读取图片并移动到对应的子文件夹中，
    在匹配图片时，会忽略文件格式后缀。
    """
    print(f"✅ 开始读取 Excel 文件: {EXCEL_PATH}")
    
    # --- 1. 初始化检查和数据加载 ---
    if not os.path.exists(EXCEL_PATH) or not os.path.isdir(IMAGE_DIR):
        print("❌ 错误: 路径检查失败，请确保 Excel 文件和图片目录都存在。")
        return

    try:
        df = pd.read_excel(EXCEL_PATH, sheet_name=0)
    except Exception as e:
        print(f"❌ 错误: 读取 Excel 文件失败。错误信息: {e}")
        return

    if TITLE_COLUMN not in df.columns or FOLDER_COLUMN not in df.columns:
        print(f"❌ 错误: Excel 文件中缺少所需的列。请检查列名是否为: '{TITLE_COLUMN}' 和 '{FOLDER_COLUMN}'")
        return

    total_rows = len(df)
    success_count = 0
    
    print(f"📋 Excel 文件共有 {total_rows} 条数据。")

    # --- 2. 预处理图片文件：建立 (主文件名: 完整文件名) 的映射 ---
    # 遍历图片目录，找到所有图片文件
    image_files_map = {}
    for filename in os.listdir(IMAGE_DIR):
        # 排除目录和非图片文件（这里我们只关注有后缀的文件）
        if os.path.isfile(os.path.join(IMAGE_DIR, filename)):
            # 分离文件名和扩展名
            name_without_ext, ext = os.path.splitext(filename)
            
            # 忽略以点开头的隐藏文件，并且确保有后缀
            if ext and not name_without_ext.startswith('.'):
                # 以小写主文件名作为 Key，完整文件名作为 Value
                image_files_map[name_without_ext.lower()] = filename
    
    print(f"📸 在图片目录中找到 {len(image_files_map)} 个潜在的图片文件。开始匹配...")

    # --- 3. 遍历 Excel 进行匹配和移动 ---
    for index, row in df.iterrows():
        # 获取图片名称和目标文件夹名称
        excel_title = str(row[TITLE_COLUMN]).strip()
        target_folder_name = str(row[FOLDER_COLUMN]).strip()

        if not excel_title or not target_folder_name:
            continue

        # 将 Excel 标题转换为小写，用于进行无后缀匹配
        key_to_match = excel_title.lower()

        # 核心匹配逻辑：在预处理的 map 中查找
        if key_to_match in image_files_map:
            # 找到了匹配的图片，获取它的完整文件名（包含正确的后缀）
            actual_image_filename = image_files_map[key_to_match]
            
            # 构造源文件和目标文件夹的完整路径
            source_path = os.path.join(IMAGE_DIR, actual_image_filename)
            target_folder_path = os.path.join(IMAGE_DIR, target_folder_name)
            destination_path = os.path.join(target_folder_path, actual_image_filename)

            # 检查目标文件夹是否存在，如果不存在则创建
            if not os.path.exists(target_folder_path):
                try:
                    os.makedirs(target_folder_path)
                    print(f"📂 创建新文件夹: {target_folder_name}")
                except OSError as e:
                    print(f"❌ 错误: 无法创建文件夹 {target_folder_name}。错误信息: {e}")
                    continue

            # 移动文件
            try:
                shutil.move(source_path, destination_path)
                print(f"➡️ 成功移动: {actual_image_filename} 到 {target_folder_name}")
                success_count += 1
                # 从 map 中移除，避免重复处理
                del image_files_map[key_to_match] 
            except Exception as e:
                print(f"❌ 错误: 移动文件 {actual_image_filename} 失败。错误信息: {e}")
        else:
            print(f"🔎 未找到匹配的图片文件（忽略后缀）：{excel_title}")


    print("-" * 30)
    print(f"🎉 脚本运行完毕。")
    print(f"总处理数据: {total_rows}")
    print(f"成功分类图片: {success_count}")
    print(f"未匹配/跳过图片: {total_rows - success_count}")

# 运行主函数
if __name__ == "__main__":
    classify_images_flexible()



##------------------------------------------------------------------------------------------
# 移动图片文件夹结构扁平化脚本
# 将所有子文件夹中的图片文件移动到根目录，并删除空子文件夹

# import os
# import shutil

# # --- 可调整的变量和参数 ---

# # 目标根路径：所有文件将最终移动到这个文件夹下，并且脚本将从这里开始遍历子文件夹。
# ROOT_DIR = r"R:\py\Auto_Image-Spider\Requests\Eporner_R18\images"

# # --------------------------

# def flatten_and_clean_folders(root_path):
#     """
#     将所有子文件夹中的文件移动到根目录，并删除空子文件夹。
    
#     参数:
#         root_path (str): 需要处理的根目录路径。
#     """
#     if not os.path.isdir(root_path):
#         print(f"❌ 错误: 找不到指定的根目录: {root_path}")
#         return

#     print(f"✅ 开始处理根目录: {root_path}")
    
#     # 用于记录被删除的文件夹，以供最后总结。
#     deleted_folders = []
#     moved_files_count = 0

#     # 1. 遍历子文件夹，移动文件
#     # os.walk(top, topdown=False) 从底层向上遍历，确保我们先处理文件，再处理文件夹
#     # (topdown=False 非常关键，它确保我们在处理完子文件夹内容后，再尝试删除它。)
#     for dirpath, dirnames, filenames in os.walk(root_path, topdown=False):
#         # 忽略根目录本身
#         if dirpath == root_path:
#             continue

#         print(f"\n📁 正在处理文件夹: {dirpath}")
        
#         # 遍历当前子文件夹中的所有文件
#         for filename in filenames:
#             source_path = os.path.join(dirpath, filename)
#             destination_path = os.path.join(root_path, filename)

#             # 检查目标根目录中是否已存在同名文件
#             if os.path.exists(destination_path):
#                 # 如果文件已存在，为避免覆盖，可以添加逻辑来重命名文件，
#                 # 这里我们简单地跳过，并打印警告。
#                 print(f"⚠️ 目标根目录已存在同名文件，跳过移动: {filename}")
#                 continue

#             # 移动文件
#             try:
#                 shutil.move(source_path, destination_path)
#                 print(f"➡️ 移动文件: {filename}")
#                 moved_files_count += 1
#             except Exception as e:
#                 print(f"❌ 移动文件 {filename} 失败。错误信息: {e}")

#         # 2. 尝试删除空文件夹
#         # 在处理完 dirpath 下的所有文件后，如果 dirpath 变空了，就可以删除它。
#         # 我们需要确保 dirnames 中引用的文件夹也是空的，但 os.walk() 已经按
#         # bottom-up (topdown=False) 顺序处理，所以只需要检查当前的 dirpath 是否为空。
#         try:
#             # 只有当文件夹为空时，os.rmdir 才会成功
#             os.rmdir(dirpath)
#             print(f"🗑️ 成功删除空文件夹: {dirpath}")
#             deleted_folders.append(dirpath)
#         except OSError as e:
#             # 如果文件夹不为空，os.rmdir 会抛出 OSError，这是正常的，我们跳过即可。
#             # 也可能是权限问题导致删除失败。
#             if "Directory not empty" in str(e):
#                  print(f"👀 文件夹未清空或含有子文件夹，跳过删除: {dirpath}")
#             else:
#                  print(f"❌ 删除文件夹 {dirpath} 失败: {e}")

#     # 3. 总结结果
#     print("\n" + "=" * 30)
#     print("🎉 文件整理和清理工作完成。")
#     print(f"总共移动文件数量: {moved_files_count}")
#     print(f"总共删除空文件夹数量: {len(deleted_folders)}")
#     print("=" * 30)


# # 运行主函数
# if __name__ == "__main__":
#     flatten_and_clean_folders(ROOT_DIR)