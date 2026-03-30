# 企查查重庆制造业爬虫 - 优化版本
# 支持完善的断点续爬、条件验证、索引缓存、数据验证
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
from utils.task_manager import TaskManager, TaskStatus
from utils.index_cache import IndexCache
from utils.data_validator import DataValidator

COOKIE_FILE = "data/qcc_cookies.json"


class QccCrawlerV2:
    """企查查爬虫 - 优化版本"""
    
    def __init__(self, use_existing_browser=False, cdp_url=None):
        self.browser = None
        self.page = None
        self.context = None
        self.playwright = None
        self.data = []
        
        # 新增：任务管理器
        self.task_manager = TaskManager(TASK_FILE)
        # 新增：索引缓存
        self.index_cache = IndexCache(INDEX_CACHE_FILE)
        # 新增：数据验证器
        self.validator = DataValidator(VALIDATION_DIR)
        
        self.screenshot_dir = "logs/screenshots"
        self.use_existing_browser = use_existing_browser
        self.cdp_url = cdp_url
        os.makedirs(self.screenshot_dir, exist_ok=True)
        os.makedirs(VALIDATION_DIR, exist_ok=True)
    
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
                headless=False,
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
                for i in range(60):
                    await self.page.wait_for_timeout(2000)
                    if await self.check_login():
                        self.log("检测到已登录")
                        break
                    if i % 5 == 0:
                        self.log(f"等待登录... ({i*2}秒)")
            
            self.log("第二步：输入重庆，点击查一下...")
            
            search_input = self.page.locator('input[placeholder*="企业"], input[type="text"]').first
            await search_input.click()
            await search_input.fill("")
            await search_input.fill("重庆")
            await self.page.wait_for_timeout(500)
            
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
            
            # 缓存当前选择的条件
            await self.cache_current_conditions()
            
            await self.screenshot("step3_filters_set")
            
            return True
            
        except Exception as e:
            self.log(f"设置筛选条件失败: {e}")
            return False
    
    async def cache_current_conditions(self):
        """缓存当前选择的条件"""
        try:
            # 获取已选条件区域的文本
            conditions_area = self.page.locator('.has-selected, .selected-conditions, [class*="selected"]').first
            if await conditions_area.is_visible(timeout=2000):
                conditions_text = await conditions_area.text_content()
                conditions = {
                    'text': conditions_text,
                    'city': CITY,
                    'status': COMPANY_STATUS,
                    'timestamp': datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                }
                self.task_manager.set_selected_conditions(conditions)
                self.log(f"  已缓存筛选条件")
        except Exception as e:
            self.log(f"  缓存筛选条件失败: {e}")
    
    async def verify_conditions_on_resume(self) -> bool:
        """续爬时验证筛选条件是否一致"""
        if not VERIFY_CONDITIONS_ON_RESUME:
            return True
        
        saved_conditions = self.task_manager.get_selected_conditions()
        if not saved_conditions:
            self.log("[条件验证] 无历史条件记录，跳过验证")
            return True
        
        self.log("[条件验证] 正在验证筛选条件...")
        
        try:
            # 获取当前已选条件
            conditions_area = self.page.locator('.has-selected, .selected-conditions, [class*="selected"]').first
            if not await conditions_area.is_visible(timeout=2000):
                self.log("[条件验证] 无法获取当前条件")
                return False
            
            current_text = await conditions_area.text_content()
            
            # 提取关键条件进行比对
            # 检查城市
            if saved_conditions.get('city', CITY) not in current_text:
                self.log(f"[条件验证] ❌ 城市不匹配: 期望 {saved_conditions.get('city')}")
                return False
            
            # 检查登记状态
            if saved_conditions.get('status', COMPANY_STATUS) not in current_text:
                self.log(f"[条件验证] ❌ 登记状态不匹配: 期望 {saved_conditions.get('status')}")
                return False
            
            # 检查制造业
            if "制造业" not in current_text:
                self.log("[条件验证] ❌ 制造业未选中")
                return False
            
            self.log("[条件验证] ✅ 筛选条件验证通过")
            return True
            
        except Exception as e:
            self.log(f"[条件验证] 验证失败: {e}")
            return False
    
    async def get_district_distribution(self):
        """第四步：获取区县分布数据"""
        try:
            await self.page.wait_for_timeout(2000)
            body_text = await self.page.text_content('body')
            
            district_data = {}
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
            # 在已选条件中点击行业标签的关闭按钮
            close_btn = self.page.locator(f'.has-selected span:has-text("{industry_name}"), .selected-conditions span:has-text("{industry_name}")').first
            if await close_btn.is_visible(timeout=2000):
                await close_btn.click()
                await self.page.wait_for_timeout(1000)
                return True
            
            # 备用方案：点击行业列表中的已选中项
            industry = self.page.locator(f'a:has-text("{industry_name}").active, .active:has-text("{industry_name}")').first
            if await industry.is_visible(timeout=1000):
                await industry.click()
                await self.page.wait_for_timeout(1000)
                return True
            
            return False
        except Exception as e:
            self.log(f"  取消选择失败: {e}")
            return False
    
    async def init_task_session(self):
        """初始化任务会话"""
        # 检查是否有未完成的任务
        pending = self.task_manager.get_pending_industries()
        
        if pending and self.task_manager.session:
            self.log(f"[断点续爬] 发现未完成任务: {len(pending)} 个行业待处理")
            progress = self.task_manager.get_progress()
            self.log(f"[断点续爬] 进度: {self.task_manager.get_progress_bar()}")
            
            # 加载已有数据
            temp_data = load_temp_data(TEMP_DATA_FILE)
            if temp_data:
                self.data = temp_data.get('data', [])
                self.log(f"[断点续爬] 已加载 {len(self.data)} 条历史数据")
            
            return True
        else:
            # 新建任务会话
            self.log("[新建会话] 初始化任务...")
            
            # 使用配置中的行业和区县列表
            industries = dict(MANUFACTURING_SUBCATEGORIES)
            districts = list(CHONGQING_DISTRICTS)
            
            self.task_manager.init_session(
                city=CITY,
                status_filter=COMPANY_STATUS,
                industries=industries,
                districts=districts
            )
            
            # 设置索引缓存
            self.index_cache.set_city(CITY)
            self.index_cache.set_districts(districts)
            self.index_cache.set_industries(industries)
            
            return False
    
    async def crawl_all_industries(self):
        """爬取所有行业数据"""
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
                    # 更新索引缓存
                    self.index_cache.set_district_enterprise_count(district, count)
                
                # 缓存制造业总数
                total = sum(manufacturing_data.values())
                self.index_cache.set_manufacturing_total(total)
                self.log(f"  制造业合计: {len(manufacturing_data)} 个区县, 共 {total} 家企业")
            
            # 第六步-第七步：遍历所有细分行业
            self.log("第六步-第七步：遍历所有制造业细分行业...")
            
            # 获取待处理的行业列表
            pending_industries = self.task_manager.get_pending_industries()
            total = len(pending_industries)
            
            self.log(f"待处理行业数: {total}")
            
            for i, task in enumerate(pending_industries):
                industry_code = task.code
                industry_name = task.name
                
                progress = f"[{i+1}/{total}]"
                self.log(f"{progress} 处理: {industry_name} ({industry_code})")
                
                # 标记开始
                self.task_manager.start_industry(industry_code)
                
                # 点击行业
                if await self.click_industry(industry_name):
                    await self.screenshot(f"industry_{industry_code}_selected")
                    
                    # 获取区县数据
                    district_data = await self.get_district_distribution()
                    
                    if district_data:
                        for district, count in district_data.items():
                            self.data.append({
                                "区县": district,
                                "行业代码": industry_code,
                                "行业类别": industry_name,
                                "企业数量": count
                            })
                            # 更新任务管理器
                            self.task_manager.update_district(district, industry_code, industry_name, count)
                        
                        self.log(f"  {industry_name}: {len(district_data)} 个区县, 共 {sum(district_data.values())} 家企业")
                        
                        # 立即保存到Excel
                        if SAVE_ON_EACH_INDUSTRY:
                            update_excel_data(OUTPUT_FILE, self.data)
                            for district, count in district_data.items():
                                update_district_sheet(OUTPUT_FILE, district, industry_code, industry_name, count)
                            self.log(f"  已保存到Excel")
                        
                        # 标记完成
                        self.task_manager.complete_industry(
                            industry_code, 
                            len(district_data), 
                            sum(district_data.values())
                        )
                    else:
                        self.log(f"  {industry_name}: 未获取到数据")
                        self.task_manager.fail_industry(industry_code, "未获取到区县数据")
                    
                    # 取消选择（为下一个行业做准备）
                    await self.deselect_industry(industry_name)
                    
                    # 保存临时数据
                    save_temp_data(TEMP_DATA_FILE, {
                        "processed_industries": [t.code for t in self.task_manager.get_completed_industries()],
                        "data": self.data
                    })
                    
                    # 随机延迟
                    random_delay(RANDOM_DELAY_MIN, RANDOM_DELAY_MAX)
                else:
                    self.task_manager.fail_industry(industry_code, "点击行业失败")
            
            return True
            
        except Exception as e:
            self.log(f"爬取行业数据失败: {e}")
            await self.screenshot("crawl_industries_error")
            return False
    
    def run_validation(self):
        """运行数据验证"""
        self.log("=" * 60)
        self.log("开始数据验证...")
        self.log("=" * 60)
        
        results = self.validator.validate(
            data=self.data,
            index_cache=self.index_cache,
            task_manager=self.task_manager
        )
        
        # 打印报告
        report = self.validator.generate_report(results)
        print(report)
        
        # 保存报告
        self.validator.save_report(results)
        
        return results
    
    async def run(self):
        """运行爬虫"""
        try:
            self.log("=" * 60)
            self.log("重庆市制造业企业数据爬虫启动 (优化版)")
            self.log("=" * 60)
            
            # 初始化浏览器
            await self.init_browser()
            
            # 初始化任务会话（检查断点续爬）
            is_resume = await self.init_task_session()
            
            # 创建Excel文件
            self.log("创建Excel文件...")
            create_excel_template(OUTPUT_FILE)
            create_district_sheets(OUTPUT_FILE, CHONGQING_DISTRICTS, MANUFACTURING_SUBCATEGORIES)
            create_summary_sheet(OUTPUT_FILE, CHONGQING_DISTRICTS, MANUFACTURING_SUBCATEGORIES)
            
            # 第一步&第二步：导航到搜索页
            if not await self.navigate_to_search():
                return
            
            # 第三步：设置筛选条件
            if not await self.setup_filters():
                return
            
            # 如果是续爬，验证条件
            if is_resume:
                if not await self.verify_conditions_on_resume():
                    self.log("❌ 条件验证失败，请手动检查筛选条件")
                    self.log("提示：确保已选择重庆市、存续/在业、制造业")
                    return
            
            # 第五步-第七步：爬取所有行业数据
            await self.crawl_all_industries()
            
            # 更新汇总表
            self.log("更新汇总表...")
            update_summary_sheet(OUTPUT_FILE, self.data)
            update_all_district_sheets(OUTPUT_FILE, self.data, CHONGQING_DISTRICTS, MANUFACTURING_SUBCATEGORIES)
            
            # 运行数据验证
            validation_results = self.run_validation()
            
            # 清理临时文件（如果验证通过）
            if validation_results.get('is_valid'):
                if os.path.exists(TEMP_DATA_FILE):
                    os.remove(TEMP_DATA_FILE)
                    self.log("已清理临时文件")
                self.task_manager.clear()
            
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
    
    crawler = QccCrawlerV2(use_existing_browser=use_existing, cdp_url=cdp_url)
    await crawler.run()


if __name__ == "__main__":
    asyncio.run(main())
