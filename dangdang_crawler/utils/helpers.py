"""
工具函数模块：提供URL构建、UA轮换、延迟控制等通用功能

本模块为爬虫系统提供基础设施支持，包括：
- 随机User-Agent生成：避免被目标网站识别为爬虫
- 随机延迟控制：模拟人类操作节奏，降低被封禁风险
- 数据格式转换：将HTML文本中的价格、数字等安全地转为Python类型
- 当当网URL构建：根据榜单类型和时间范围生成对应的榜单页面URL
- 批次ID生成：为每次爬取任务生成唯一标识，用于数据库存储和断点续爬
"""

import random
import re
import time
from datetime import date


# 预定义的User-Agent池，覆盖Windows/Mac/Linux三大平台的主流浏览器
# 每次请求随机选取一个，降低被反爬系统识别的概率
_USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Gecko/20100101 Firefox/121.0",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36 Edg/120.0.0.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.2 Safari/605.1.15",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
]


def generate_user_agent() -> str:
    """从User-Agent池中随机选取一个，用于HTTP请求头伪装"""
    return random.choice(_USER_AGENTS)


def random_delay(min_sec: float = 1.0, max_sec: float = 3.0):
    """
    随机延迟，模拟人类操作间隔

    当当网有反爬机制，固定间隔的请求容易被识别。
    在[min_sec, max_sec]范围内随机等待，使请求模式更自然。

    参数:
        min_sec: 最小等待秒数，默认1.0秒
        max_sec: 最大等待秒数，默认3.0秒
    """
    delay = random.uniform(min_sec, max_sec)
    time.sleep(delay)


def format_price(text: str | None) -> float | None:
    """
    将HTML中的价格文本转为浮点数

    当当网页面中的价格可能包含"¥"、"元"等符号，
    此函数提取其中的数字部分并转为float。

    参数:
        text: 原始价格文本，如"¥39.80"、"59.00元"

    返回:
        提取的价格数值，转换失败返回None
    """
    if not text:
        return None
    cleaned = re.sub(r"[^\d.]", "", str(text).strip())
    if not cleaned:
        return None
    try:
        return float(cleaned)
    except ValueError:
        return None


def safe_int(text: str | None) -> int | None:
    """
    安全地将文本转为整数，提取其中的数字部分

    用于处理评论数等字段，如"1,234条评论" -> 1234

    参数:
        text: 原始文本

    返回:
        提取的整数值，转换失败返回None
    """
    if not text:
        return None
    cleaned = re.sub(r"[^\d]", "", str(text).strip())
    if not cleaned:
        return None
    try:
        return int(cleaned)
    except ValueError:
        return None


def safe_float(text: str | None) -> float | None:
    """
    安全地将文本转为浮点数，提取其中的数字和小数点部分

    用于处理折扣、好评度等字段，如"7.5折" -> 7.5

    参数:
        text: 原始文本

    返回:
        提取的浮点数值，转换失败返回None
    """
    if not text:
        return None
    cleaned = re.sub(r"[^\d.]", "", str(text).strip())
    if not cleaned:
        return None
    try:
        return float(cleaned)
    except ValueError:
        return None


def build_dangdang_url(
    ranking_type: str,
    time_range: str,
    page: int = 1,
) -> str:
    """
    根据榜单类型、时间范围和页码构建当当网榜单页面URL

    当当网榜单URL结构：
    - 畅销榜基础路径: http://bang.dangdang.com/books/bestsellers
    - 新书热卖基础路径: http://bang.dangdang.com/books/newhotsales
    - 分类码: 01.00.00.00.00.00（全部图书）
    - 时间维度: 24hours/recent7/recent30/month-YEAR-MONTH/year-YEAR

    示例:
        build_dangdang_url("bestseller", "24hours", 2)
        -> http://bang.dangdang.com/books/bestsellers/01.00.00.00.00.00-24hours-0-0-1-2

        build_dangdang_url("bestseller", "month-2026-1", 1)
        -> http://bang.dangdang.com/books/bestsellers/01.00.00.00.00.00-month-2026-1-1-1

    参数:
        ranking_type: 榜单类型，"bestseller"（畅销榜）或 "newhot"（新书热卖榜）
        time_range: 时间范围标识，如 "24hours"、"month-2026-1"、"year-2022"
        page: 页码，从1开始

    返回:
        完整的当当网榜单页面URL
    """
    base_url = "http://bang.dangdang.com/books/bestsellers"
    if ranking_type == "newhot":
        base_url = "http://bang.dangdang.com/books/newhotsales"

    # 全部图书分类码
    category = "01.00.00.00.00.00"

    if time_range.startswith("month-"):
        # 月度榜单：month-2026-1 格式
        parts = time_range.split("-")
        year = parts[1]
        month = parts[2]
        url = f"{base_url}/{category}-month-{year}-{month}-1-{page}"
    elif time_range.startswith("year-"):
        # 年度榜单：year-2022 格式
        parts = time_range.split("-")
        year = parts[1]
        url = f"{base_url}/{category}-year-{year}-0-1-{page}"
    else:
        # 实时榜单：24hours/recent7/recent30
        url = f"{base_url}/{category}-{time_range}-0-0-1-{page}"

    return url


# 榜单类型中文映射，用于前端显示
RANKING_TYPE_MAP = {
    "bestseller": "畅销榜",
    "newhot": "新书热卖榜",
}

# 时间范围中文映射，动态生成至当前月份
_current_year = date.today().year
_current_month = date.today().month

TIME_RANGE_MAP = {
    "24hours": "24小时",
    "recent7": "近7日",
    "recent30": "近30日",
}
# 动态添加当年各月度选项
for _m in range(1, _current_month + 1):
    TIME_RANGE_MAP[f"month-{_current_year}-{_m}"] = f"{_current_year}年{_m}月"
# 动态添加历史年度选项（2022年起至去年）
for _y in range(2022, _current_year):
    TIME_RANGE_MAP[f"year-{_y}"] = f"{_y}年"

# 数据库字段中文映射，用于前端表头和导出CSV
FIELD_NAMES = {
    "rank_position": "排名",
    "book_title": "书名",
    "introduction": "介绍",
    "author": "创作者",
    "publisher": "出版社",
    "publish_date": "出版时间",
    "current_price": "当前价格",
    "original_price": "原价",
    "discount": "折扣",
    "comment_count": "评论数",
    "rating": "好评度",
    "category": "分类",
    "detail_url": "详情链接",
    "cover_image": "封面",
}

# 默认不选中的字段（介绍字段默认隐藏，减少表格宽度）
DEFAULT_UNSELECTED_FIELDS = {"introduction"}


def generate_batch_id(ranking_type: str, time_range: str) -> str:
    """
    为爬取任务生成唯一的批次ID，用于数据库存储和断点续爬

    批次ID编码规则：
    - 月度数据: MO_{类型码}_{年月}，如 MO_bs_202601（畅销榜2026年1月）
    - 年度数据: YR_{类型码}_{年份}，如 YR_bs_2022（畅销榜2022年）
    - 实时数据: RT_{类型码}_{时间码}_{日期}，如 RT_bs_24h_20260429

    类型码: bs=畅销榜, nh=新书热卖榜

    参数:
        ranking_type: 榜单类型
        time_range: 时间范围标识

    返回:
        批次ID字符串
    """
    type_code = "bs" if ranking_type == "bestseller" else "nh"
    if time_range.startswith("month-"):
        parts = time_range.split("-")
        return f"MO_{type_code}_{parts[1]}{parts[2].zfill(2)}"
    elif time_range.startswith("year-"):
        parts = time_range.split("-")
        return f"YR_{type_code}_{parts[1]}"
    else:
        range_code = {"24hours": "24h", "recent7": "7d", "recent30": "30d"}.get(time_range, time_range)
        return f"RT_{type_code}_{range_code}_{date.today().strftime('%Y%m%d')}"
