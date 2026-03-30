# 数据验证模块 - 爬取完成后的数据比对验证
import json
import os
from datetime import datetime
from typing import Dict, List, Tuple
from collections import defaultdict


class DataValidator:
    """数据验证器
    
    用于验证爬取数据的完整性：
    1. 城市区县制造业数量 vs 细分行业数量合计比对
    2. 区县行业覆盖率检查
    3. 数据一致性检查
    """
    
    def __init__(self, output_dir: str):
        self.output_dir = output_dir
        self.validation_results: Dict = {}
    
    def validate(self, data: List[Dict], index_cache, task_manager) -> Dict:
        """执行完整的数据验证
        
        Args:
            data: 爬取的数据列表 [{区县, 行业代码, 行业类别, 企业数量}, ...]
            index_cache: 索引缓存对象
            task_manager: 任务管理器对象
        
        Returns:
            验证结果字典
        """
        results = {
            'validated_at': datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            'is_valid': True,
            'checks': {},
            'warnings': [],
            'errors': []
        }
        
        # 1. 制造业合计 vs 细分行业合计比对
        check1 = self._check_total_vs_sum(data)
        results['checks']['total_vs_sum'] = check1
        if not check1['passed']:
            results['errors'].append(f"制造业合计与细分行业总和不一致: 差异 {check1['difference']} 家企业")
            results['is_valid'] = False
        
        # 2. 区县行业覆盖率检查
        check2 = self._check_district_coverage(data, index_cache)
        results['checks']['district_coverage'] = check2
        if check2['missing_industries']:
            results['warnings'].append(f"部分区县缺少行业数据: {len(check2['missing_industries'])} 个区县")
        
        # 3. 行业区县覆盖率检查
        check3 = self._check_industry_coverage(data, index_cache)
        results['checks']['industry_coverage'] = check3
        if check3['missing_districts']:
            results['warnings'].append(f"部分行业缺少区县数据: {len(check3['missing_districts'])} 个行业")
        
        # 4. 任务完成情况检查
        check4 = self._check_task_completion(task_manager)
        results['checks']['task_completion'] = check4
        if not check4['all_completed']:
            results['errors'].append(f"有未完成的任务: {check4['pending_count']} 个行业待处理")
            results['is_valid'] = False
        
        # 5. 数据完整性检查（检查是否有0值或异常值）
        check5 = self._check_data_integrity(data)
        results['checks']['data_integrity'] = check5
        if check5['zero_count'] > 0:
            results['warnings'].append(f"存在 {check5['zero_count']} 条零值记录")
        
        self.validation_results = results
        return results
    
    def _check_total_vs_sum(self, data: List[Dict]) -> Dict:
        """检查制造业合计与细分行业总和是否一致"""
        # 获取制造业合计数据
        manufacturing_total = defaultdict(int)
        industry_sum = defaultdict(int)
        
        for record in data:
            district = record['区县']
            count = record['企业数量']
            industry = record['行业类别']
            
            if industry == '制造业合计':
                manufacturing_total[district] = count
            else:
                industry_sum[district] += count
        
        # 比对
        differences = []
        all_districts = set(manufacturing_total.keys()) | set(industry_sum.keys())
        
        for district in all_districts:
            total = manufacturing_total.get(district, 0)
            sum_val = industry_sum.get(district, 0)
            diff = total - sum_val
            
            if diff != 0:
                differences.append({
                    'district': district,
                    'manufacturing_total': total,
                    'industry_sum': sum_val,
                    'difference': diff
                })
        
        return {
            'passed': len(differences) == 0,
            'differences': differences,
            'total_difference': sum(d['difference'] for d in differences),
            'difference_count': len(differences)
        }
    
    def _check_district_coverage(self, data: List[Dict], index_cache) -> Dict:
        """检查各区县的行业覆盖率"""
        # 从缓存获取所有行业
        all_industries = set(index_cache.get_industries().values()) if index_cache else set()
        if not all_industries:
            # 如果缓存为空，从数据推断
            all_industries = set(r['行业类别'] for r in data if r['行业类别'] != '制造业合计')
        
        # 统计每个区县拥有的行业
        district_industries = defaultdict(set)
        for record in data:
            if record['行业类别'] != '制造业合计':
                district_industries[record['区县']].add(record['行业类别'])
        
        # 检查缺失
        missing_industries = {}
        for district, industries in district_industries.items():
            missing = all_industries - industries
            if missing:
                missing_industries[district] = list(missing)
        
        return {
            'total_districts': len(district_industries),
            'expected_industries': len(all_industries),
            'missing_industries': missing_industries,
            'coverage_rate': sum(len(i) for i in district_industries.values()) / (len(district_industries) * len(all_industries)) * 100 if all_industries and district_industries else 0
        }
    
    def _check_industry_coverage(self, data: List[Dict], index_cache) -> Dict:
        """检查各行业的区县覆盖率"""
        # 从缓存获取所有区县
        all_districts = set(index_cache.get_districts()) if index_cache else set()
        if not all_districts:
            # 如果缓存为空，从数据推断
            all_districts = set(r['区县'] for r in data)
        
        # 统计每个行业拥有的区县
        industry_districts = defaultdict(set)
        for record in data:
            if record['行业类别'] != '制造业合计':
                industry_districts[record['行业类别']].add(record['区县'])
        
        # 检查缺失
        missing_districts = {}
        for industry, districts in industry_districts.items():
            missing = all_districts - districts
            if missing:
                missing_districts[industry] = list(missing)
        
        return {
            'total_industries': len(industry_districts),
            'expected_districts': len(all_districts),
            'missing_districts': missing_districts,
            'coverage_rate': sum(len(d) for d in industry_districts.values()) / (len(industry_districts) * len(all_districts)) * 100 if all_districts and industry_districts else 0
        }
    
    def _check_task_completion(self, task_manager) -> Dict:
        """检查任务完成情况"""
        if not task_manager:
            return {'all_completed': True, 'pending_count': 0, 'pending_industries': []}
        
        pending = task_manager.get_pending_industries()
        return {
            'all_completed': len(pending) == 0,
            'pending_count': len(pending),
            'pending_industries': [{'code': t.code, 'name': t.name} for t in pending]
        }
    
    def _check_data_integrity(self, data: List[Dict]) -> Dict:
        """检查数据完整性"""
        zero_count = 0
        negative_count = 0
        empty_fields = 0
        
        for record in data:
            if record['企业数量'] == 0:
                zero_count += 1
            if record['企业数量'] < 0:
                negative_count += 1
            if not record['区县'] or not record['行业类别']:
                empty_fields += 1
        
        return {
            'total_records': len(data),
            'zero_count': zero_count,
            'negative_count': negative_count,
            'empty_fields': empty_fields,
            'passed': negative_count == 0 and empty_fields == 0
        }
    
    def generate_report(self, results: Dict = None) -> str:
        """生成验证报告"""
        if results is None:
            results = self.validation_results
        
        if not results:
            return "无验证结果"
        
        lines = [
            "=" * 60,
            "数据验证报告",
            f"验证时间: {results.get('validated_at', 'N/A')}",
            f"验证结果: {'✅ 通过' if results.get('is_valid') else '❌ 未通过'}",
            "=" * 60,
            ""
        ]
        
        # 检查项详情
        checks = results.get('checks', {})
        
        # 1. 总量比对
        if 'total_vs_sum' in checks:
            check = checks['total_vs_sum']
            lines.append("【制造业合计 vs 细分行业合计】")
            lines.append(f"  状态: {'✅ 一致' if check['passed'] else '❌ 不一致'}")
            if not check['passed']:
                lines.append(f"  总差异: {check['total_difference']} 家企业")
                lines.append(f"  差异区县数: {check['difference_count']}")
                if check['differences']:
                    lines.append("  差异详情:")
                    for diff in check['differences'][:10]:  # 只显示前10个
                        lines.append(f"    - {diff['district']}: 制造业{diff['manufacturing_total']} vs 行业和{diff['industry_sum']} (差{diff['difference']})")
            lines.append("")
        
        # 2. 区县覆盖率
        if 'district_coverage' in checks:
            check = checks['district_coverage']
            lines.append("【区县行业覆盖率】")
            lines.append(f"  区县数: {check['total_districts']}")
            lines.append(f"  期望行业数: {check['expected_industries']}")
            lines.append(f"  覆盖率: {check['coverage_rate']:.1f}%")
            if check['missing_industries']:
                lines.append(f"  缺失行业的区县: {len(check['missing_industries'])} 个")
            lines.append("")
        
        # 3. 行业覆盖率
        if 'industry_coverage' in checks:
            check = checks['industry_coverage']
            lines.append("【行业区县覆盖率】")
            lines.append(f"  行业数: {check['total_industries']}")
            lines.append(f"  期望区县数: {check['expected_districts']}")
            lines.append(f"  覆盖率: {check['coverage_rate']:.1f}%")
            if check['missing_districts']:
                lines.append(f"  缺失区县的行业: {len(check['missing_districts'])} 个")
            lines.append("")
        
        # 4. 任务完成情况
        if 'task_completion' in checks:
            check = checks['task_completion']
            lines.append("【任务完成情况】")
            lines.append(f"  状态: {'✅ 全部完成' if check['all_completed'] else '❌ 有未完成任务'}")
            if not check['all_completed']:
                lines.append(f"  待处理行业数: {check['pending_count']}")
                if check['pending_industries']:
                    lines.append("  待处理行业:")
                    for ind in check['pending_industries'][:5]:
                        lines.append(f"    - {ind['name']} ({ind['code']})")
            lines.append("")
        
        # 5. 数据完整性
        if 'data_integrity' in checks:
            check = checks['data_integrity']
            lines.append("【数据完整性】")
            lines.append(f"  总记录数: {check['total_records']}")
            lines.append(f"  零值记录: {check['zero_count']}")
            lines.append(f"  负值记录: {check['negative_count']}")
            lines.append(f"  空字段记录: {check['empty_fields']}")
            lines.append("")
        
        # 错误和警告
        if results.get('errors'):
            lines.append("【错误】")
            for err in results['errors']:
                lines.append(f"  ❌ {err}")
            lines.append("")
        
        if results.get('warnings'):
            lines.append("【警告】")
            for warn in results['warnings']:
                lines.append(f"  ⚠️ {warn}")
            lines.append("")
        
        lines.append("=" * 60)
        
        return "\n".join(lines)
    
    def save_report(self, results: Dict = None, filename: str = None):
        """保存验证报告"""
        if filename is None:
            filename = f"validation_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
        
        filepath = os.path.join(self.output_dir, filename)
        os.makedirs(self.output_dir, exist_ok=True)
        
        report = self.generate_report(results)
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(report)
        
        print(f"[数据验证] 报告已保存: {filepath}")
        return filepath
