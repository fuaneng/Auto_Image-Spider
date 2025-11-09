import os
import re

# 根目录路径
root_path = r"R:\py\Auto_Image-Spider\Selenium_Undetected-chromedriver\tw_8se_me\models\年年"

# 保留中文、英文、数字，其余全部替换为 "_"
def sanitize_name(name):
    # 将所有非中文、英文、数字的字符替换为下划线
    new_name = re.sub(r'[^a-zA-Z0-9\u4e00-\u9fa5]+', '_', name)
    # 去除多余的下划线（如开头结尾或连续）
    new_name = re.sub(r'_+', '_', new_name).strip('_')
    return new_name

# 从最深层文件夹开始遍历，避免路径变动问题
for dirpath, dirnames, filenames in os.walk(root_path, topdown=False):
    for dirname in dirnames:
        old_path = os.path.join(dirpath, dirname)
        new_name = sanitize_name(dirname)
        new_path = os.path.join(dirpath, new_name)

        if new_name != dirname:
            # 避免重名冲突
            if not os.path.exists(new_path):
                os.rename(old_path, new_path)
                print(f"✅ 重命名成功：{dirname} → {new_name}")
            else:
                print(f"⚠️ 已存在同名文件夹，跳过：{new_name}")

print("🎯 所有子文件夹名称清理完成！")
