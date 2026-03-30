# 数据处理工具函数
import json
import os
import random
import time
import re

def save_temp_data(file_path, data):
    """
    保存临时数据到JSON文件，用于断点续爬
    
    Args:
        file_path (str): 临时数据文件路径
        data (dict): 要保存的数据
    """
    # 确保输出目录存在
    os.makedirs(os.path.dirname(file_path), exist_ok=True)
    
    # 保存数据
    with open(file_path, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    
    print(f"[断点] 临时数据已保存: {len(data.get('data', []))} 条记录")


def load_temp_data(file_path):
    """
    从JSON文件加载临时数据，用于断点续爬
    
    Args:
        file_path (str): 临时数据文件路径
    
    Returns:
        dict: 加载的数据，如果文件不存在则返回空字典
    """
    if not os.path.exists(file_path):
        return {}
    
    with open(file_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    print(f"[断点] 临时数据已加载: {len(data.get('data', []))} 条记录")
    return data


def random_delay(min_delay=1, max_delay=3):
    """
    生成随机延迟，用于反爬
    
    Args:
        min_delay (int): 最小延迟时间（秒）
        max_delay (int): 最大延迟时间（秒）
    """
    delay = random.uniform(min_delay, max_delay)
    print(f"[延迟] 等待 {delay:.2f} 秒")
    time.sleep(delay)


def format_company_count(count_text):
    """
    格式化企业数量文本为整数
    
    Args:
        count_text (str): 企业数量文本，如 "2万+"、"1,234"
    
    Returns:
        int: 格式化后的企业数量
    """
    if not count_text:
        return 0
    
    # 移除空格和逗号
    count_text = str(count_text).replace(" ", "").replace(",", "")
    
    # 处理 "万+" 格式
    if "万" in count_text:
        match = re.search(r'([\d.]+)\s*万', count_text)
        if match:
            num = float(match.group(1))
            return int(num * 10000)
    
    # 处理 "千+" 格式
    if "千" in count_text:
        match = re.search(r'([\d.]+)\s*千', count_text)
        if match:
            num = float(match.group(1))
            return int(num * 1000)
    
    # 处理 "+" 格式
    count_text = count_text.replace("+", "").replace("家", "").replace("企业", "")
    
    # 尝试转换为整数
    try:
        return int(float(count_text))
    except ValueError:
        print(f"[警告] 无法转换企业数量: {count_text}")
        return 0


def parse_district_counts(count_text):
    """
    解析区县企业数量文本
    
    Args:
        count_text (str): 区县企业数量文本，如 "万州区(13093) 涪陵区(11169)..."
    
    Returns:
        dict: 区县名称和企业数量的字典
    """
    district_counts = {}
    
    if not count_text:
        return district_counts
    
    # 提取区县和数量
    # 匹配格式：区县名(数字) 或 区县名(数字万+) 等
    pattern = r'([\u4e00-\u9fa5]+区|[\u4e00-\u9fa5]+县|[\u4e00-\u9fa5]+开发区|[\u4e00-\u9fa5]+新区)\(([\d,万\+千]+)\)'
    matches = re.findall(pattern, count_text)
    
    for match in matches:
        district = match[0]
        count = format_company_count(match[1])
        district_counts[district] = count
    
    # 如果上面的模式没匹配到，尝试更宽松的模式
    if not district_counts:
        pattern2 = r'([\u4e00-\u9fa5]{2,10})\(([\d,万\+千]+)\)'
        matches2 = re.findall(pattern2, count_text)
        for match in matches2:
            district = match[0]
            # 过滤掉非区县名称
            if any(keyword in district for keyword in ['区', '县', '开发区', '新区', '城', '州']):
                count = format_company_count(match[1])
                district_counts[district] = count
    
    return district_counts


def get_progress_bar(current, total, bar_length=30):
    """
    获取进度条字符串
    
    Args:
        current (int): 当前进度
        total (int): 总进度
        bar_length (int): 进度条长度
    
    Returns:
        str: 进度条字符串
    """
    if total == 0:
        return "[░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░] 0.0% (0/0)"
    
    progress = current / total
    filled_length = int(bar_length * progress)
    bar = "█" * filled_length + "░" * (bar_length - filled_length)
    percentage = progress * 100
    
    return f"[{bar}] {percentage:.1f}% ({current}/{total})"


def clean_district_name(name):
    """
    清理区县名称
    
    Args:
        name (str): 原始区县名称
    
    Returns:
        str: 清理后的区县名称
    """
    if not name:
        return name
    
    # 移除前后空格
    name = name.strip()
    
    # 移除可能的括号内容
    name = re.sub(r'\([^)]*\)', '', name)
    
    return name


def clean_industry_name(name):
    """
    清理行业名称
    
    Args:
        name (str): 原始行业名称
    
    Returns:
        str: 清理后的行业名称
    """
    if not name:
        return name
    
    # 移除前后空格
    name = name.strip()
    
    # 移除行业代码部分
    name = re.sub(r'^\d+\s*', '', name)
    
    return name
