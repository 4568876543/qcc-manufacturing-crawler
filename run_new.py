# 直接启动新浏览器运行
import asyncio
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from crawler import QccCrawler

def main():
    print("=" * 60)
    print("重庆市制造业企业数据爬虫 - 新浏览器模式")
    print("=" * 60)
    print()
    print("[提示] 浏览器将自动打开，请输入短信验证码登录")
    print()
    
    crawler = QccCrawler()
    asyncio.run(crawler.run())


if __name__ == "__main__":
    main()
