# 连接已有浏览器运行脚本
import asyncio
import sys
import os

# 添加项目路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from crawler import QccCrawler

def main():
    print("=" * 60)
    print("重庆市制造业企业数据爬虫 - 连接已有浏览器模式")
    print("=" * 60)
    print()
    
    # 默认CDP地址
    cdp_url = "http://127.0.0.1:9222"
    
    # 可以通过命令行参数指定
    if len(sys.argv) > 1:
        cdp_url = sys.argv[1]
    
    print(f"[信息] 正在连接到: {cdp_url}")
    print("[提示] 请确保Chrome已用 --remote-debugging-port=9222 启动并登录企查查")
    print()
    
    crawler = QccCrawler(use_existing_browser=True, cdp_url=cdp_url)
    asyncio.run(crawler.run())


if __name__ == "__main__":
    main()
