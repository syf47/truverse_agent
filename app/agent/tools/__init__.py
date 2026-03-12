"""Agent 工具注册中心。

所有工具在此统一导出。添加新工具只需：
1. 在对应模块中用 @tool 定义函数
2. 把它加入下方的 ALL_TOOLS 列表
"""

from app.agent.tools.analytics_tools import (
    analyze_competitors,
    get_industry_trends,
    get_market_report,
    monitor_price,
)
from app.agent.tools.base import set_dependencies
from app.agent.tools.image_tools import analyze_image, annotate_image, ocr_image
from app.agent.tools.search_tools import query_products, search_context, search_knowledge

ALL_TOOLS = [
    # 图片类
    ocr_image,
    analyze_image,
    annotate_image,
    # 搜索 & 知识检索
    search_context,
    search_knowledge,
    query_products,
    # 行业数据分析 API
    get_industry_trends,
    analyze_competitors,
    monitor_price,
    get_market_report,
]

__all__ = [
    "ALL_TOOLS",
    "set_dependencies",
]
