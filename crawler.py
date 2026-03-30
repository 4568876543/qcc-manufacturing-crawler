# 企查查重庆制造业爬虫 - 基于实际页面操作流程
import asyncio
import re
import os
import json
from datetime import datetime
from playwright.async_api import async_playwright, TimeoutError as PlaywrightTimeoutError
from config import *
from utils.excel_utils import (
    create_excel_template,
    create_district_sheets,
    create_summary_sheet,
    update_excel_data,
    update_district_sheet,
    update_summary_sheet,
    update_all_district_sheets
)
from utils.data_utils import (
    save_temp_data,
    load_temp_data,
    random_delay,
    format_company_count,
    get_progress_bar
)

COOKIE_FILE = "data/qcc_cookies.json"


class QccCrawler:
    def __init__(self, use_existing_browser=False, cdp_url=None):
        self.browser = None
        self.page = None
        self.context = None
        self.playwright = None
        self.data = []
        self.processed_industries = set()
        self.industries = dict(MANUFACTURING_SUBCATEGORIES)
        self.districts = list(CHONGQING_DISTRICTS)
        self.screenshot_dir = "logs/screenshots"
        self.use_existing_browser = use_existing_browser
        self.cdp_url = cdp_url
        os.makedirs(self.screenshot_dir, exist_ok=True)
        
    async def init_browser(self):
        """初始化浏览器"""
        self.log("正在启动浏览器...")
        
        if self.use_existing_browser and self.cdp_url:
            self.log(f"[模式] 连接到已有浏览器: {self.cdp_url}")
            self.playwright = await async_playwright().start()
            self.browser = await self.playwright.chromium.connect_over_cdp(self.cdp_url)
            contexts = self.browser.contexts
            if contexts:
                self.context = contexts[0]
                pages = self.context.pages
                if pages:
                    self.page = pages[0]
                    self.log(f"[模式] 已连接到现有页面: {self.page.url}")
                else:
                    self.page = await self.context.new_page()
            else:
                self.context = await self.browser.new_context()
                self.page = await self.context.new_page()
        else:
            self.log("[模式] 启动新浏览器")
            self.playwright = await async_playwright().start()
            self.browser = await self.playwright.chromium.launch(
                headless=False,  # 非无头模式，方便调试
                slow_mo=50
            )
            self.context = await self.browser.new_context(
                viewport={'width': 1920, 'height': 1080}
            )
            self.page = await self.context.new_page()
        
        self.page.set_default_timeout(TIMEOUT)
        self.log("浏览器启动完成")
    
    async def screenshot(self, name: str):
        """截图保存"""
        try:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"{timestamp}_{name}.png"
            filepath = os.path.join(self.screenshot_dir, filename)
            await self.page.screenshot(path=filepath, full_page=True)
            self.log(f"截图: {filepath}")
        except Exception as e:
            self.log(f"截图失败: {e}")
    
    def log(self, message: str):
        """日志输出"""
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        log_line = f"[{timestamp}] {message}"
        print(log_line)
        log_file = os.path.join("logs", "crawler.log")
        os.makedirs(os.path.dirname(log_file), exist_ok=True)
        with open(log_file, "a", encoding="utf-8") as f:
            f.write(log_line + "\n")
    
    async def check_login(self):
        """检查登录状态"""
        try:
            # 检查是否有登录按钮
            login_btn = self.page.locator('button:has-text("登录"), text=登录').first
            if await login_btn.is_visible(timeout=2000):
                return False
            return True
        except:
            return True
    
    async def navigate_to_search(self):
        """第一步&第二步：访问企查查，搜索重庆"""
        try:
            self.log("第一步：访问企查查首页...")
            await self.page.goto("https://www.qcc.com/", wait_until='networkidle')
            await self.page.wait_for_timeout(2000)
            
            # 关闭可能的弹窗
            try:
                close_btn = self.page.locator('.qcc-login-modal-close, .close-btn, [class*="close"]').first
                if await close_btn.is_visible(timeout=2000):
                    await close_btn.click()
                    await self.page.wait_for_timeout(500)
            except:
                pass
            
            # 检查登录状态
            if not await self.check_login():
                self.log("未登录，请在浏览器中手动登录...")
                # 等待用户登录
                for i in range(60):
                    await self.page.wait_for_timeout(2000)
                    if await self.check_login():
                        self.log("检测到已登录")
                        break
                    if i % 5 == 0:
                        self.log(f"等待登录... ({i*2}秒)")
            
            self.log("第二步：输入重庆，点击查一下...")
            
            # 清空并输入搜索词
            search_input = self.page.locator('input[placeholder*="企业"], input[type="text"]').first
            await search_input.click()
            await search_input.fill("")
            await search_input.fill("重庆")
            await self.page.wait_for_timeout(500)
            
            # 点击查一下
            search_btn = self.page.get_by_role("button", name="查一下").first
            await search_btn.click()
            
            await self.page.wait_for_load_state('networkidle')
            await self.page.wait_for_timeout(2000)
            
            self.log(f"当前页面: {self.page.url}")
            await self.screenshot("step2_search_result")
            
            return True
            
        except Exception as e:
            self.log(f"导航失败: {e}")
            await self.screenshot("navigate_error")
            return False
    
    async def setup_filters(self):
        """第三步：设置筛选条件"""
        try:
            self.log("第三步：设置筛选条件...")
            
            # 勾选"地址"
            self.log("  勾选地址...")
            try:
                address_checkbox = self.page.get_by_role("checkbox", name="地址")
                if await address_checkbox.is_visible(timeout=3000):
                    await address_checkbox.check()
                    await self.page.wait_for_timeout(500)
            except Exception as e:
                self.log(f"  勾选地址失败: {e}")
            
            # 点击"更多"展开省份地区
            self.log("  点击更多展开省份地区...")
            try:
                more_btn = self.page.locator("a").filter(has_text="更多").first
                if await more_btn.is_visible(timeout=3000):
                    await more_btn.click()
                    await self.page.wait_for_timeout(1000)
            except Exception as e:
                self.log(f"  点击更多失败: {e}")
            
            # 点击重庆市
            self.log("  点击重庆市...")
            try:
                chongqing = self.page.get_by_text("重庆市").first
                await chongqing.click()
                await self.page.wait_for_timeout(1000)
            except Exception as e:
                self.log(f"  点击重庆市失败: {e}")
            
            # 点击登记状态
            self.log("  点击登记状态...")
            try:
                status_btn = self.page.get_by_text("登记状态").first
                await status_btn.click()
                await self.page.wait_for_timeout(500)
            except Exception as e:
                self.log(f"  点击登记状态失败: {e}")
            
            # 勾选正常状态（存续/在业）
            self.log("  勾选存续/在业...")
            try:
                normal_status = self.page.get_by_text("存续/在业").first
                await normal_status.click()
                await self.page.wait_for_timeout(500)
            except Exception as e:
                self.log(f"  勾选存续/在业失败: {e}")
            
            await self.screenshot("step3_filters_set")
            
            return True
            
        except Exception as e:
            self.log(f"设置筛选条件失败: {e}")
            return False
    
    async def get_district_distribution(self):
        """第四步：获取区县分布数据"""
        try:
            self.log("第四步：获取区县分布数据...")
            
            # 等待页面加载
            await self.page.wait_for_timeout(2000)
            
            # 获取页面文本
            body_text = await self.page.text_content('body')
            
            # 解析区县数据
            district_data = {}
            
            # 匹配格式：区县名(数字)
            pattern = r'([\u4e00-\u9fa5]+[区县]|[\u4e00-\u9fa5]+开发区|[\u4e00-\u9fa5]+新区|[\u4e00-\u9fa5]+自治县)\s*[\(（]([\d,]+)[\)）]'
            matches = re.findall(pattern, body_text)
            
            for match in matches:
                district = match[0]
                count = int(match[1].replace(',', ''))
                district_data[district] = count
            
            if district_data:
                self.log(f"  获取到 {len(district_data)} 个区县")
                for d, c in list(district_data.items())[:5]:
                    self.log(f"    {d}: {c}")
                return district_data
            else:
                self.log("  未获取到区县数据")
                await self.screenshot("no_district_data")
                return {}
                
        except Exception as e:
            self.log(f"获取区县分布失败: {e}")
            return {}
    
    async def click_manufacturing(self):
        """点击制造业"""
        try:
            self.log("  点击制造业...")
            manufacturing = self.page.get_by_text("制造业").first
            await manufacturing.click()
            await self.page.wait_for_timeout(2000)
            return True
        except Exception as e:
            self.log(f"  点击制造业失败: {e}")
            return False
    
    async def click_industry(self, industry_name: str):
        """点击指定行业"""
        try:
            self.log(f"  点击行业: {industry_name}")
            industry = self.page.get_by_text(industry_name).first
            await industry.click()
            await self.page.wait_for_timeout(2000)
            return True
        except Exception as e:
            self.log(f"  点击行业失败: {e}")
            return False
    
    async def deselect_industry(self, industry_name: str):
        """取消选择行业"""
        try:
            self.log(f"  取消选择: {industry_name}")
            # 点击已选条件中的行业标签
            selected_tag = self.page.locator(f'span:has-text("{industry_name}")').nth(2)
            await selected_tag.click()
            await self.page.wait_for_timeout(1000)
            return True
        except Exception as e:
            self.log(f"  取消选择失败: {e}")
            return False
    
    async def crawl_all_industries(self):
        """第五步-第七步：爬取所有行业数据"""
        try:
            self.log("第五步：点击制造业，获取制造业各区县数据...")
            
            # 点击制造业
            await self.click_manufacturing()
            await self.screenshot("manufacturing_selected")
            
            # 获取制造业区县数据
            manufacturing_data = await self.get_district_distribution()
            
            if manufacturing_data:
                # 保存制造业汇总数据
                for district, count in manufacturing_data.items():
                    self.data.append({
                        "区县": district,
                        "行业代码": "C",
                        "行业类别": "制造业合计",
                        "企业数量": count
                    })
                self.log(f"  制造业合计: {len(manufacturing_data)} 个区县")
            
            # 第六步-第七步：遍历所有细分行业
            self.log("第六步-第七步：遍历所有制造业细分行业...")
            
            industry_list = list(self.industries.items())
            total = len(industry_list)
            
            for i, (code, name) in enumerate(industry_list):
                if code in self.processed_industries:
                    continue
                
                progress = get_progress_bar(i, total)
                self.log(f"{progress} 处理: {name} ({code})")
                
                # 点击行业
                if await self.click_industry(name):
                    await self.screenshot(f"industry_{code}_selected")
                    
                    # 获取区县数据
                    district_data = await self.get_district_distribution()
                    
                    if district_data:
                        for district, count in district_data.items():
                            self.data.append({
                                "区县": district,
                                "行业代码": code,
                                "行业类别": name,
                                "企业数量": count
                            })
                        self.log(f"  {name}: {len(district_data)} 个区县")
                        
                        # 更新Excel
                        update_excel_data(OUTPUT_FILE, self.data)
                        for district, count in district_data.items():
                            update_district_sheet(OUTPUT_FILE, district, code, name, count)
                    
                    # 标记为已处理
                    self.processed_industries.add(code)
                    
                    # 取消选择（为下一个行业做准备）
                    await self.deselect_industry(name)
                    
                    # 保存临时数据
                    save_temp_data(TEMP_DATA_FILE, {
                        "processed_industries": list(self.processed_industries),
                        "data": self.data
                    })
                    
                    # 随机延迟
                    random_delay(1, 2)
            
            return True
            
        except Exception as e:
            self.log(f"爬取行业数据失败: {e}")
            await self.screenshot("crawl_industries_error")
            return False
    
    async def run(self):
        """运行爬虫"""
        try:
            self.log("=" * 60)
            self.log("重庆市制造业企业数据爬虫启动")
            self.log("=" * 60)
            
            # 初始化浏览器
            await self.init_browser()
            
            # 加载临时数据（断点续爬）
            temp_data = load_temp_data(TEMP_DATA_FILE)
            if temp_data:
                self.processed_industries = set(temp_data.get("processed_industries", []))
                self.data = temp_data.get("data", [])
                self.log(f"已加载 {len(self.processed_industries)} 个已处理行业")
            
            # 创建Excel文件
            self.log("创建Excel文件...")
            create_excel_template(OUTPUT_FILE)
            create_district_sheets(OUTPUT_FILE, self.districts, self.industries)
            create_summary_sheet(OUTPUT_FILE, self.districts, self.industries)
            
            # 第一步&第二步：导航到搜索页
            if not await self.navigate_to_search():
                return
            
            # 第三步：设置筛选条件
            if not await self.setup_filters():
                return
            
            # 第五步-第七步：爬取所有行业数据
            await self.crawl_all_industries()
            
            # 更新汇总表
            self.log("更新汇总表...")
            update_summary_sheet(OUTPUT_FILE, self.data)
            update_all_district_sheets(OUTPUT_FILE, self.data, self.districts, self.industries)
            
            # 清理临时文件
            if os.path.exists(TEMP_DATA_FILE):
                os.remove(TEMP_DATA_FILE)
                self.log("已清理临时文件")
            
            self.log("=" * 60)
            self.log(f"爬取完成！共获取 {len(self.data)} 条数据")
            self.log(f"输出文件: {OUTPUT_FILE}")
            self.log("=" * 60)
            
        except Exception as e:
            self.log(f"爬虫运行失败: {e}")
            await self.screenshot("run_error")
            
        finally:
            if not self.use_existing_browser and self.browser:
                await self.browser.close()
                self.log("浏览器已关闭")
            elif self.use_existing_browser:
                self.log("使用已有浏览器模式，不关闭浏览器")


async def main():
    """主函数"""
    import sys
    cdp_url = None
    use_existing = False
    
    if len(sys.argv) > 1:
        if sys.argv[1] == "--connect" and len(sys.argv) > 2:
            cdp_url = sys.argv[2]
            use_existing = True
    
    crawler = QccCrawler(use_existing_browser=use_existing, cdp_url=cdp_url)
    await crawler.run()


if __name__ == "__main__":
    asyncio.run(main())
