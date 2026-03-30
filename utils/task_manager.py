# 任务管理模块 - 支持详细的断点续爬
import json
import os
from datetime import datetime
from typing import Dict, List, Set, Optional
from dataclasses import dataclass, asdict
from enum import Enum


class TaskStatus(Enum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"


@dataclass
class IndustryTask:
    """单个行业的爬取任务"""
    code: str
    name: str
    status: str = TaskStatus.PENDING.value
    district_count: int = 0  # 已爬取的区县数量
    total_districts: int = 0  # 总区县数量
    enterprise_count: int = 0  # 企业总数
    error_message: str = ""
    started_at: str = ""
    completed_at: str = ""


@dataclass
class DistrictTask:
    """单个区县在某行业下的爬取状态"""
    district: str
    industry_code: str
    industry_name: str
    enterprise_count: int = 0
    status: str = TaskStatus.PENDING.value


@dataclass
class CrawlSession:
    """爬取会话状态"""
    session_id: str
    city: str
    status_filter: str  # 登记状态筛选条件
    started_at: str
    last_updated: str
    
    # 索引数据缓存
    districts_cache: List[str] = None  # 区县列表
    industries_cache: Dict[str, str] = None  # 行业列表
    
    # 已选条件（用于验证）
    selected_conditions: Dict = None
    
    # 统计
    total_industries: int = 0
    completed_industries: int = 0
    total_records: int = 0
    
    def __post_init__(self):
        if self.districts_cache is None:
            self.districts_cache = []
        if self.industries_cache is None:
            self.industries_cache = {}
        if self.selected_conditions is None:
            self.selected_conditions = {}


class TaskManager:
    """任务管理器"""
    
    def __init__(self, task_file: str):
        self.task_file = task_file
        self.session: Optional[CrawlSession] = None
        self.industry_tasks: Dict[str, IndustryTask] = {}
        self.district_tasks: Dict[str, DistrictTask] = {}  # key: f"{district}_{industry_code}"
        self._load()
    
    def _load(self):
        """加载任务状态"""
        if not os.path.exists(self.task_file):
            return
        
        try:
            with open(self.task_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            # 加载会话信息
            if 'session' in data:
                session_data = data['session']
                self.session = CrawlSession(
                    session_id=session_data.get('session_id', ''),
                    city=session_data.get('city', ''),
                    status_filter=session_data.get('status_filter', ''),
                    started_at=session_data.get('started_at', ''),
                    last_updated=session_data.get('last_updated', ''),
                    districts_cache=session_data.get('districts_cache', []),
                    industries_cache=session_data.get('industries_cache', {}),
                    selected_conditions=session_data.get('selected_conditions', {}),
                    total_industries=session_data.get('total_industries', 0),
                    completed_industries=session_data.get('completed_industries', 0),
                    total_records=session_data.get('total_records', 0)
                )
            
            # 加载行业任务
            if 'industry_tasks' in data:
                for code, task_data in data['industry_tasks'].items():
                    self.industry_tasks[code] = IndustryTask(**task_data)
            
            # 加载区县任务
            if 'district_tasks' in data:
                for key, task_data in data['district_tasks'].items():
                    self.district_tasks[key] = DistrictTask(**task_data)
            
            print(f"[任务管理] 已加载任务状态: {len(self.industry_tasks)} 个行业, {len(self.district_tasks)} 条区县记录")
            
        except Exception as e:
            print(f"[任务管理] 加载任务状态失败: {e}")
    
    def save(self):
        """保存任务状态"""
        os.makedirs(os.path.dirname(self.task_file), exist_ok=True)
        
        data = {
            'session': asdict(self.session) if self.session else {},
            'industry_tasks': {code: asdict(task) for code, task in self.industry_tasks.items()},
            'district_tasks': {key: asdict(task) for key, task in self.district_tasks.items()}
        }
        
        with open(self.task_file, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        
        # 同时更新最后更新时间
        if self.session:
            self.session.last_updated = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    def init_session(self, city: str, status_filter: str, industries: Dict[str, str], districts: List[str]):
        """初始化新的爬取会话"""
        session_id = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        self.session = CrawlSession(
            session_id=session_id,
            city=city,
            status_filter=status_filter,
            started_at=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            last_updated=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            districts_cache=districts,
            industries_cache=industries,
            total_industries=len(industries)
        )
        
        # 初始化行业任务
        for code, name in industries.items():
            self.industry_tasks[code] = IndustryTask(
                code=code,
                name=name,
                total_districts=len(districts)
            )
        
        # 初始化区县任务
        for district in districts:
            for code, name in industries.items():
                key = f"{district}_{code}"
                self.district_tasks[key] = DistrictTask(
                    district=district,
                    industry_code=code,
                    industry_name=name
                )
        
        self.save()
        print(f"[任务管理] 已初始化会话: {session_id}")
        print(f"[任务管理] 共 {len(self.industry_tasks)} 个行业, {len(self.district_tasks)} 个区县任务")
    
    def set_cache(self, districts: List[str], industries: Dict[str, str]):
        """设置索引数据缓存"""
        if self.session:
            self.session.districts_cache = districts
            self.session.industries_cache = industries
            self.save()
    
    def set_selected_conditions(self, conditions: Dict):
        """设置已选条件（用于续爬验证）"""
        if self.session:
            self.session.selected_conditions = conditions
            self.save()
    
    def get_selected_conditions(self) -> Dict:
        """获取已选条件"""
        if self.session:
            return self.session.selected_conditions or {}
        return {}
    
    def start_industry(self, industry_code: str):
        """开始处理某个行业"""
        if industry_code in self.industry_tasks:
            task = self.industry_tasks[industry_code]
            task.status = TaskStatus.IN_PROGRESS.value
            task.started_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            self.save()
    
    def complete_industry(self, industry_code: str, district_count: int, enterprise_count: int):
        """完成某个行业"""
        if industry_code in self.industry_tasks:
            task = self.industry_tasks[industry_code]
            task.status = TaskStatus.COMPLETED.value
            task.district_count = district_count
            task.enterprise_count = enterprise_count
            task.completed_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            
            if self.session:
                self.session.completed_industries += 1
                self.session.total_records += enterprise_count
            
            self.save()
            print(f"[任务管理] 完成行业 {task.name}: {district_count} 区县, {enterprise_count} 家企业")
    
    def fail_industry(self, industry_code: str, error_message: str):
        """标记行业失败"""
        if industry_code in self.industry_tasks:
            task = self.industry_tasks[industry_code]
            task.status = TaskStatus.FAILED.value
            task.error_message = error_message
            self.save()
    
    def update_district(self, district: str, industry_code: str, industry_name: str, count: int):
        """更新区县数据"""
        key = f"{district}_{industry_code}"
        if key in self.district_tasks:
            self.district_tasks[key].enterprise_count = count
            self.district_tasks[key].status = TaskStatus.COMPLETED.value
        else:
            self.district_tasks[key] = DistrictTask(
                district=district,
                industry_code=industry_code,
                industry_name=industry_name,
                enterprise_count=count,
                status=TaskStatus.COMPLETED.value
            )
        self.save()
    
    def get_pending_industries(self) -> List[IndustryTask]:
        """获取待处理的行业列表"""
        return [task for task in self.industry_tasks.values() 
                if task.status in [TaskStatus.PENDING.value, TaskStatus.FAILED.value]]
    
    def get_completed_industries(self) -> List[IndustryTask]:
        """获取已完成的行业列表"""
        return [task for task in self.industry_tasks.values() 
                if task.status == TaskStatus.COMPLETED.value]
    
    def get_progress(self) -> Dict:
        """获取进度信息"""
        total = len(self.industry_tasks)
        completed = len([t for t in self.industry_tasks.values() if t.status == TaskStatus.COMPLETED.value])
        in_progress = len([t for t in self.industry_tasks.values() if t.status == TaskStatus.IN_PROGRESS.value])
        failed = len([t for t in self.industry_tasks.values() if t.status == TaskStatus.FAILED.value])
        
        return {
            'total': total,
            'completed': completed,
            'in_progress': in_progress,
            'pending': total - completed - in_progress - failed,
            'failed': failed,
            'percentage': round(completed / total * 100, 1) if total > 0 else 0
        }
    
    def get_progress_bar(self, width: int = 30) -> str:
        """获取进度条字符串"""
        progress = self.get_progress()
        filled = int(width * progress['completed'] / progress['total']) if progress['total'] > 0 else 0
        bar = '█' * filled + '░' * (width - filled)
        return f"[{bar}] {progress['percentage']}% ({progress['completed']}/{progress['total']})"
    
    def export_summary(self) -> Dict:
        """导出摘要信息"""
        progress = self.get_progress()
        return {
            'session': {
                'session_id': self.session.session_id if self.session else '',
                'city': self.session.city if self.session else '',
                'started_at': self.session.started_at if self.session else '',
                'last_updated': self.session.last_updated if self.session else '',
            },
            'progress': progress,
            'completed_industries': [
                {'code': t.code, 'name': t.name, 'count': t.enterprise_count}
                for t in self.get_completed_industries()
            ],
            'failed_industries': [
                {'code': t.code, 'name': t.name, 'error': t.error_message}
                for t in self.industry_tasks.values() if t.status == TaskStatus.FAILED.value
            ]
        }
    
    def clear(self):
        """清除所有任务状态"""
        self.session = None
        self.industry_tasks = {}
        self.district_tasks = {}
        if os.path.exists(self.task_file):
            os.remove(self.task_file)
        print("[任务管理] 已清除所有任务状态")
