import pandas as pd
import os

def xlsx_to_markdown_table(xlsx_filepath: str, md_filepath: str, sheet_name: str | int = 0) -> None:
    """
    将 XLSX 文件内容转换为 Markdown 表格并写入到新文件。

    :param xlsx_filepath: 要读取的 XLSX 文件的完整路径。
    :param md_filepath: 要写入的 Markdown 文件的完整路径。
    :param sheet_name: 要读取的工作表名称（字符串）或索引（整数，0代表第一个工作表）。
    """
    print(f"🔄 正在尝试从 '{xlsx_filepath}' 读取数据...")
    
    try:
        # 1. 使用 pandas 读取 XLSX 文件
        # header=0 表示第一行是表头
        df = pd.read_excel(xlsx_filepath, sheet_name=sheet_name, header=0)

        # 2. 将 DataFrame 转换为 Markdown 字符串
        # tablefmt="github" 生成标准的 GitHub/通用 Markdown 表格格式
        # index=False 表示不包含 DataFrame 的行索引（通常不需要）
        markdown_table = df.to_markdown(tablefmt="github", index=False)
        
        # 3. 写入 Markdown 文件
        with open(md_filepath, 'w', encoding='utf-8') as mdfile:
            mdfile.write(markdown_table)
        
        print(f"✅ 转换成功！Markdown 表格已保存到: {md_filepath}")
        print("-" * 30)
        print("以下是生成的部分内容示例（前五行）：")
        print(markdown_table.split('\n', 6)[0:5])

    except FileNotFoundError:
        print(f"❌ 错误: 找不到文件 '{xlsx_filepath}'。请检查路径是否正确。")
        print("请确保文件扩展名是 .xlsx。")
    except ImportError:
        print(f"❌ 错误: 缺少必要的库。请运行 'pip install pandas openpyxl' 安装。")
    except ValueError as e:
        print(f"❌ 错误: 无法读取指定工作表。请检查 sheet_name 参数。详细信息: {e}")
    except Exception as e:
        print(f"❌ 发生错误: {e}")


# --- 脚本配置区 ---
# 待转换的 XLSX 文件路径 (注意: 文件名需要改为 .xlsx)
INPUT_XLSX_PATH = r"R:\py\Auto_Image-Spider\记录表.xlsx"

# 生成的 Markdown 文件路径
# 默认保存在当前脚本所在目录下，文件名为 '记录表.md'
BASE_DIR = os.path.dirname(os.path.abspath(__file__)) if '__file__' in locals() else os.getcwd()
OUTPUT_MD_PATH = os.path.join(BASE_DIR, "记录表.md")

# 要读取的工作表名称或索引 (0 代表第一个工作表)
XLSX_SHEET_NAME = 0 

# --- 执行函数 ---
if __name__ == "__main__":
    # 确保您已经将记录表.csv 更改为 记录表.xlsx
    xlsx_to_markdown_table(INPUT_XLSX_PATH, OUTPUT_MD_PATH, XLSX_SHEET_NAME)
