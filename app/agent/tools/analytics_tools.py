"""行业数据分析 API 工具。

提供外部行业数据分析能力，包括行业趋势、竞品分析、价格监控等。
每个工具通过 httpx 异步调用外部 API，返回结构化分析结果。

添加新 API 工具的步骤：
1. 在本文件中用 @tool 定义新函数
2. 在 __init__.py 的 ALL_TOOLS 中注册
完成 — graph.py 会自动加载。
"""

from __future__ import annotations

import logging

import httpx
from langchain_core.tools import tool

from app.config import settings

logger = logging.getLogger(__name__)

_HTTP_TIMEOUT = 30.0


async def _call_api(endpoint: str, params: dict) -> dict:
    """调用外部数据分析 API 的通用方法。

    Args:
        endpoint: API 路径（拼接到 analytics_api_base 后面）。
        params: 请求参数。

    Returns:
        API 返回的 JSON 数据。

    Raises:
        httpx.HTTPStatusError: 非 2xx 响应。
    """
    url = f"{settings.analytics_api_base.rstrip('/')}/{endpoint.lstrip('/')}"
    headers = {}
    if settings.analytics_api_key:
        headers["Authorization"] = f"Bearer {settings.analytics_api_key}"

    async with httpx.AsyncClient(timeout=_HTTP_TIMEOUT) as client:
        resp = await client.get(url, params=params, headers=headers)
        resp.raise_for_status()
        return resp.json()


@tool
async def get_industry_trends(category: str, period: str = "30d") -> str:
    """获取指定商品类目的行业趋势数据。

    分析该类目的搜索热度、销量走势、均价变化等核心指标。

    Args:
        category: 商品类目名称，如"连衣裙"、"运动鞋"、"手机壳"。
        period: 时间范围，支持 7d/30d/90d，默认 30d。
    """
    try:
        data = await _call_api("/trends", {"category": category, "period": period})
        return (
            f"【{category} 行业趋势 - 近{period}】\n"
            f"搜索热度: {data.get('search_index', 'N/A')}\n"
            f"销量趋势: {data.get('sales_trend', 'N/A')}\n"
            f"均价: ¥{data.get('avg_price', 'N/A')}\n"
            f"top 关键词: {', '.join(data.get('top_keywords', []))}"
        )
    except httpx.HTTPStatusError as e:
        logger.warning("Industry trends API error: %s", e)
        return f"行业趋势查询失败（HTTP {e.response.status_code}），请稍后重试。"
    except Exception as e:
        logger.warning("Industry trends API error: %s", e)
        return f"行业趋势查询失败: {e}"


@tool
async def analyze_competitors(product_name: str, top_n: int = 5) -> str:
    """分析指定商品的竞品数据。

    返回同类竞品的价格区间、销量排名、评分对比等信息。

    Args:
        product_name: 商品名称或关键词，如"蓝牙耳机"。
        top_n: 返回的竞品数量，默认 5 个。
    """
    try:
        data = await _call_api("/competitors", {"product": product_name, "top_n": top_n})
        competitors = data.get("competitors", [])
        if not competitors:
            return f"未找到 '{product_name}' 的竞品数据。"

        lines = [f"【{product_name} 竞品分析 - Top {top_n}】"]
        for i, c in enumerate(competitors[:top_n], 1):
            lines.append(
                f"{i}. {c.get('name', '未知')} | "
                f"¥{c.get('price', 'N/A')} | "
                f"月销 {c.get('monthly_sales', 'N/A')} | "
                f"评分 {c.get('rating', 'N/A')}"
            )
        return "\n".join(lines)
    except httpx.HTTPStatusError as e:
        logger.warning("Competitors API error: %s", e)
        return f"竞品分析查询失败（HTTP {e.response.status_code}），请稍后重试。"
    except Exception as e:
        logger.warning("Competitors API error: %s", e)
        return f"竞品分析查询失败: {e}"


@tool
async def monitor_price(sku_id: str) -> str:
    """查询指定 SKU 的价格监控数据。

    返回历史价格走势、当前价格在市场中的位置、是否处于低价区间。

    Args:
        sku_id: 商品 SKU ID。
    """
    try:
        data = await _call_api("/price-monitor", {"sku_id": sku_id})
        return (
            f"【SKU {sku_id} 价格监控】\n"
            f"当前价格: ¥{data.get('current_price', 'N/A')}\n"
            f"历史最低: ¥{data.get('min_price', 'N/A')}\n"
            f"历史最高: ¥{data.get('max_price', 'N/A')}\n"
            f"市场均价: ¥{data.get('market_avg', 'N/A')}\n"
            f"价格评级: {data.get('price_level', 'N/A')}"
        )
    except httpx.HTTPStatusError as e:
        logger.warning("Price monitor API error: %s", e)
        return f"价格监控查询失败（HTTP {e.response.status_code}），请稍后重试。"
    except Exception as e:
        logger.warning("Price monitor API error: %s", e)
        return f"价格监控查询失败: {e}"


@tool
async def get_market_report(category: str) -> str:
    """获取指定类目的市场分析报告摘要。

    包含市场规模、增长率、主要品牌份额、消费者画像等。

    Args:
        category: 商品类目名称。
    """
    try:
        data = await _call_api("/market-report", {"category": category})
        return (
            f"【{category} 市场报告】\n"
            f"市场规模: {data.get('market_size', 'N/A')}\n"
            f"同比增长: {data.get('yoy_growth', 'N/A')}\n"
            f"Top 品牌: {', '.join(data.get('top_brands', []))}\n"
            f"主力消费群: {data.get('target_audience', 'N/A')}\n"
            f"趋势洞察: {data.get('insight', 'N/A')}"
        )
    except httpx.HTTPStatusError as e:
        logger.warning("Market report API error: %s", e)
        return f"市场报告查询失败（HTTP {e.response.status_code}），请稍后重试。"
    except Exception as e:
        logger.warning("Market report API error: %s", e)
        return f"市场报告查询失败: {e}"
