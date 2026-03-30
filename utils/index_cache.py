# 索引数据缓存模块 - 保存区县、行业数据作为索引
import json
import os
from datetime import datetime
from typing import Dict, List, Optional


class IndexCache:
    """索引数据缓存
    
    用于保存从企查查页面获取的区县列表、行业大类、行业中类数据，
    避免手动输入筛选条件与企查查实际数据不一致的问题。
    """
    
    def __init__(self, cache_file: str):
        self.cache_file = cache_file
        self.cache: Dict = {}
        self._load()
    
    def _load(self):
        """加载缓存"""
        if not os.path.exists(self.cache_file):
            return
        
        try:
            with open(self.cache_file, 'r', encoding='utf-8') as f:
                self.cache = json.load(f)
            print(f"[索引缓存] 已加载缓存: {len(self.cache.get('districts', []))} 个区县, {len(self.cache.get('industries', {}))} 个行业")
        except Exception as e:
            print(f"[索引缓存] 加载失败: {e}")
            self.cache = {}
    
    def save(self):
        """保存缓存"""
        os.makedirs(os.path.dirname(self.cache_file), exist_ok=True)
        self.cache['last_updated'] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        with open(self.cache_file, 'w', encoding='utf-8') as f:
            json.dump(self.cache, f, ensure_ascii=False, indent=2)
        print(f"[索引缓存] 已保存到 {self.cache_file}")
    
    def set_city(self, city: str):
        """设置城市"""
        self.cache['city'] = city
    
    def get_city(self) -> Optional[str]:
        """获取城市"""
        return self.cache.get('city')
    
    def set_districts(self, districts: List[str]):
        """设置区县列表"""
        self.cache['districts'] = districts
        # 同时建立索引字典
        self.cache['district_index'] = {name: idx for idx, name in enumerate(districts)}
        self.save()
        print(f"[索引缓存] 已缓存 {len(districts)} 个区县")
    
    def get_districts(self) -> List[str]:
        """获取区县列表"""
        return self.cache.get('districts', [])
    
    def get_district_index(self, district: str) -> int:
        """获取区县索引"""
        return self.cache.get('district_index', {}).get(district, -1)
    
    def set_industry_category(self, category: str, code: str):
        """设置行业大类（如制造业）"""
        if 'industry_categories' not in self.cache:
            self.cache['industry_categories'] = {}
        self.cache['industry_categories'][category] = code
    
    def get_industry_category(self, category: str) -> Optional[str]:
        """获取行业大类代码"""
        return self.cache.get('industry_categories', {}).get(category)
    
    def set_industries(self, industries: Dict[str, str]):
        """设置行业列表（行业中类）
        
        Args:
            industries: {行业代码: 行业名称} 字典
        """
        self.cache['industries'] = industries
        # 建立反向索引
        self.cache['industry_name_to_code'] = {name: code for code, name in industries.items()}
        self.save()
        print(f"[索引缓存] 已缓存 {len(industries)} 个行业")
    
    def get_industries(self) -> Dict[str, str]:
        """获取行业列表"""
        return self.cache.get('industries', {})
    
    def get_industry_code(self, name: str) -> Optional[str]:
        """根据行业名称获取代码"""
        return self.cache.get('industry_name_to_code', {}).get(name)
    
    def get_industry_name(self, code: str) -> Optional[str]:
        """根据行业代码获取名称"""
        return self.cache.get('industries', {}).get(code)
    
    def set_district_enterprise_count(self, district: str, count: int):
        """设置区县企业总数（制造业合计）"""
        if 'district_totals' not in self.cache:
            self.cache['district_totals'] = {}
        self.cache['district_totals'][district] = count
    
    def get_district_enterprise_count(self, district: str) -> Optional[int]:
        """获取区县企业总数"""
        return self.cache.get('district_totals', {}).get(district)
    
    def get_district_totals(self) -> Dict[str, int]:
        """获取所有区县企业总数"""
        return self.cache.get('district_totals', {})
    
    def set_manufacturing_total(self, total: int):
        """设置制造业企业总数"""
        self.cache['manufacturing_total'] = total
    
    def get_manufacturing_total(self) -> Optional[int]:
        """获取制造业企业总数"""
        return self.cache.get('manufacturing_total')
    
    def update_from_page(self, districts_data: Dict[str, int], industry_name: str = None):
        """从页面数据更新缓存
        
        Args:
            districts_data: {区县名: 企业数量}
            industry_name: 当前行业名称（可选）
        """
        # 更新区县列表
        districts = list(districts_data.keys())
        if districts:
            self.set_districts(districts)
        
        # 如果是制造业合计，保存区县总数
        if industry_name == "制造业合计" or industry_name is None:
            for district, count in districts_data.items():
                self.set_district_enterprise_count(district, count)
    
    def validate_district(self, district: str) -> bool:
        """验证区县名称是否在缓存中"""
        return district in self.cache.get('district_index', {})
    
    def validate_industry(self, industry_name: str) -> bool:
        """验证行业名称是否在缓存中"""
        return industry_name in self.cache.get('industry_name_to_code', {})
    
    def get_missing_districts(self, crawled_districts: List[str]) -> List[str]:
        """获取缺失的区县"""
        all_districts = set(self.cache.get('districts', []))
        crawled = set(crawled_districts)
        return list(all_districts - crawled)
    
    def get_missing_industries(self, crawled_industries: List[str]) -> List[str]:
        """获取缺失的行业"""
        all_industries = set(self.cache.get('industries', {}).values())
        crawled = set(crawled_industries)
        return list(all_industries - crawled)
    
    def export_for_verification(self) -> Dict:
        """导出用于验证的数据"""
        return {
            'city': self.cache.get('city'),
            'districts': self.cache.get('districts', []),
            'district_totals': self.cache.get('district_totals', {}),
            'manufacturing_total': self.cache.get('manufacturing_total'),
            'industries': self.cache.get('industries', {}),
            'last_updated': self.cache.get('last_updated')
        }
    
    def clear(self):
        """清除缓存"""
        self.cache = {}
        if os.path.exists(self.cache_file):
            os.remove(self.cache_file)
        print("[索引缓存] 已清除缓存")
