# 补爬缺失行业脚本
import asyncio
import re
from playwright.async_api import async_playwright
from config import OUTPUT_FILE, MANUFACTURING_SUBCATEGORIES
from utils.excel_utils import update_excel_data, update_district_sheet, update_summary_sheet, update_all_district_sheets

# 重庆区县列表
CHONGQING_DISTRICTS = [
    "万州区", "涪陵区", "渝中区", "大渡口区", "江北区", "沙坪坝区",
    "九龙坡区", "南岸区", "北碚区", "綦江区", "大足区", "渝北区",
    "巴南区", "黔江区", "长寿区", "江津区", "合川区", "永川区",
    "南川区", "璧山区", "铜梁区", "潼南区", "荣昌区", "开州区",
    "梁平区", "武隆区", "城口县", "丰都县", "垫江县", "忠县",
    "云阳县", "奉节县", "巫山县", "巫溪县", "石柱土家族自治县",
    "秀山土家族苗族自治县", "酉阳土家族苗族自治县", "彭水苗族土家族自治县",
    "两江新区", "重庆高新技术产业开发区"
]

CHONGQING_DISTRICTS_SET = set(CHONGQING_DISTRICTS)


async def crawl_missing():
    print("=" * 60)
    print("补爬: 石油、煤炭及其他燃料加工业 (25)")
    print("=" * 60)
    
    playwright = await async_playwright().start()
    browser = await playwright.chromium.connect_over_cdp("http://127.0.0.1:9222")
    context = browser.contexts[0]
    page = context.pages[0]
    page.set_default_timeout(30000)
    
    print(f"当前URL: {page.url}")
    
    # 步骤1: 导航到搜索页
    print("\n1. 导航到搜索页...")
    await page.goto("https://www.qcc.com/web/search?key=%E9%87%8D%E5%BA%86", wait_until='networkidle')
    await page.wait_for_timeout(2000)
    
    # 步骤2: 勾选地址
    print("2. 勾选地址...")
    try:
        addr_cb = page.get_by_role("checkbox", name="地址")
        if await addr_cb.is_visible(timeout=3000):
            await addr_cb.check()
            await page.wait_for_timeout(1000)
    except:
        pass
    
    # 步骤3: 点击更多展开省份
    print("3. 展开省份地区...")
    try:
        more_btn = page.locator("a").filter(has_text="更多").first
        if await more_btn.is_visible(timeout=3000):
            await more_btn.click()
            await page.wait_for_timeout(1000)
    except:
        pass
    
    # 步骤4: 点击重庆市
    print("4. 点击重庆市...")
    try:
        cq_btn = page.get_by_text("重庆市").first
        await cq_btn.click()
        await page.wait_for_timeout(2000)
    except Exception as e:
        print(f"  点击重庆市失败: {e}")
    
    # 步骤5: 点击制造业
    print("5. 点击制造业...")
    try:
        mfg_btn = page.get_by_text("制造业").first
        await mfg_btn.click()
        await page.wait_for_timeout(2000)
    except Exception as e:
        print(f"  点击制造业失败: {e}")
    
    # 步骤6: 点击目标行业
    target_name = "石油、煤炭及其他燃料加工业"
    print(f"6. 点击 {target_name}...")
    try:
        ind_btn = page.get_by_text(target_name).first
        await ind_btn.click()
        await page.wait_for_timeout(2000)
    except Exception as e:
        print(f"  点击行业失败: {e}")
        await page.screenshot(path="logs/fix_step6_error.png")
        await playwright.stop()
        return
    
    await page.screenshot(path="logs/fix_step6_selected.png")
    
    # 步骤7: 获取区县数据
    print("7. 获取区县分布数据...")
    await page.wait_for_timeout(2000)
    
    body_text = await page.text_content('body')
    
    # 解析 - 只保留重庆区县
    district_data = {}
    pattern = r'([\u4e00-\u9fa5]+[区县]|两江新区|重庆高新技术产业开发区|[\u4e00-\u9fa5]+自治县)\s*[\(（]([\d,]+)[\)）]'
    matches = re.findall(pattern, body_text)
    
    for match in matches:
        district = match[0]
        count = int(match[1].replace(',', ''))
        if district in CHONGQING_DISTRICTS_SET:
            district_data[district] = count
    
    print(f"  获取到 {len(district_data)} 个区县")
    for d, c in sorted(district_data.items()):
        print(f"    {d}: {c}")
    
    if district_data:
        # 读取现有数据
        data = []
        try:
            import pandas as pd
            xl = pd.ExcelFile(OUTPUT_FILE)
            df = pd.read_excel(xl, sheet_name="总览", skiprows=2, names=["区县", "行业类别", "企业数量"])
            df = df.dropna(subset=["区县"])
            data = df.to_dict('records')
        except:
            pass
        
        # 添加新数据
        target_code = "25"
        for district, count in district_data.items():
            data.append({
                "区县": district,
                "行业代码": target_code,
                "行业类别": target_name,
                "企业数量": count
            })
        
        # 更新Excel
        print("\n8. 更新Excel...")
        update_excel_data(OUTPUT_FILE, data)
        for district, count in district_data.items():
            update_district_sheet(OUTPUT_FILE, district, target_code, target_name, count)
        update_summary_sheet(OUTPUT_FILE, data)
        update_all_district_sheets(OUTPUT_FILE, data, CHONGQING_DISTRICTS, MANUFACTURING_SUBCATEGORIES)
        
        print(f"\n完成! 新增 {len(district_data)} 条数据")
    else:
        print("\n未获取到数据")
        with open("logs/debug_fix_missing.txt", "w", encoding="utf-8") as f:
            f.write(body_text[:30000])
        print("页面文本已保存到 logs/debug_fix_missing.txt")
    
    await playwright.stop()


if __name__ == "__main__":
    asyncio.run(crawl_missing())
