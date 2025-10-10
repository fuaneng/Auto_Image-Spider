import os
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options

# ChromeDriver 路径
CHROME_DRIVER_PATH = r"C:\Program Files\Google\chromedriver-win64\chromedriver.exe"

# Chrome 用户数据路径（建议新建一个独立配置目录）
USER_DATA_DIR = r"R:\py\Auto_Image-Spider\保存和导入 Cookies\civitai_data"
LOGIN_URL = "https://civitai.com/"

def open_persistent_browser():
    """
    使用 Chrome 用户配置目录保持登录状态。
    第一次运行：手动登录 civitai.com（或通过 Google/GitHub 登录）
    之后运行：自动保持登录状态。
    """
    print("--- 启动持久化浏览器 ---")

    chrome_options = Options()
    # 使用你自己的 Chrome 用户数据路径
    chrome_options.add_argument(f"--user-data-dir={USER_DATA_DIR}")
    # 可选：指定一个 profile 目录（可创建多个不同账号）
    chrome_options.add_argument("--profile-directory=Default")  # 使用默认配置目录

    service = Service(executable_path=CHROME_DRIVER_PATH)
    driver = webdriver.Chrome(service=service, options=chrome_options)

    driver.get(LOGIN_URL)
    print(f"🌐 已打开 {LOGIN_URL}")
    print("✅ 如果是第一次使用，请手动登录（Google/GitHub 均可）")
    print("✅ 登录一次后，下次将自动保持登录状态。")
    input(">>> 按回车键关闭浏览器...")
    driver.quit()


if __name__ == "__main__":
    open_persistent_browser()
