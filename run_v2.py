# 运行脚本 - 优化版本
import asyncio
import os
import sys

def check_python_version():
    """检查Python版本"""
    if sys.version_info < (3, 8):
        print("[错误] 需要Python 3.8或更高版本")
        print(f"[信息] 当前版本: {sys.version}")
        sys.exit(1)
    print(f"[信息] Python版本: {sys.version.split()[0]}")

def check_dependencies():
    """检查依赖是否安装"""
    required = {
        'playwright': 'playwright',
        'pandas': 'pandas', 
        'openpyxl': 'openpyxl'
    }
    
    missing = []
    for module, package in required.items():
        try:
            __import__(module)
        except ImportError:
            missing.append(package)
    
    if missing:
        print(f"[错误] 缺少必要的依赖: {', '.join(missing)}")
        print("\n请运行以下命令安装依赖:")
        print("  pip install playwright pandas openpyxl")
        print("  playwright install chromium")
        sys.exit(1)
    
    print("[信息] 依赖检查通过")


def main():
    """主函数"""
    print("=" * 60)
    print("重庆市制造业企业数据爬虫 (优化版)")
    print("=" * 60)
    print()
    
    # 检查环境
    check_python_version()
    check_dependencies()
    
    print()
    print("=" * 60)
    print("运行模式选择：")
    print("  1. 连接已有浏览器（推荐，需先手动登录企查查）")
    print("  2. 启动新浏览器（需输入验证码登录）")
    print("=" * 60)
    
    choice = input("请选择模式 [1/2]: ").strip()
    
    if choice == "1":
        print()
        print("[模式] 连接已有浏览器")
        print()
        print("请按以下步骤操作：")
        print("1. 打开Chrome浏览器")
        print("2. 在地址栏输入: chrome://version  查看Chrome版本")
        print("3. 关闭所有Chrome窗口")
        print("4. 在终端运行以下命令启动Chrome（开启远程调试）：")
        print()
        
        # 根据操作系统给出不同命令
        if sys.platform == "darwin":  # macOS
            print('   /Applications/Google\\ Chrome.app/Contents/MacOS/Google\\ Chrome --remote-debugging-port=9222')
        elif sys.platform == "win32":  # Windows
            print('   "C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe" --remote-debugging-port=9222')
        else:  # Linux
            print('   google-chrome --remote-debugging-port=9222')
        
        print()
        print("5. 在打开的Chrome中访问企查查并登录")
        print("6. 登录成功后，回到这里按回车继续...")
        input()
        
        cdp_url = "http://localhost:9222"
        print(f"\n[信息] 正在连接到 {cdp_url} ...")
        
        from crawler_v2 import QccCrawlerV2
        crawler = QccCrawlerV2(use_existing_browser=True, cdp_url=cdp_url)
        asyncio.run(crawler.run())
        
    else:
        print()
        print("[模式] 启动新浏览器")
        print("[提示] 运行过程中需要手动输入短信验证码")
        print()
        
        from crawler_v2 import QccCrawlerV2
        crawler = QccCrawlerV2()
        asyncio.run(crawler.run())


if __name__ == "__main__":
    main()
