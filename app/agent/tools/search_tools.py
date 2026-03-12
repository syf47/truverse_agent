"""搜索和查询相关工具：上下文搜索、知识检索、商品查询。"""

from __future__ import annotations

from langchain_core.tools import tool

from app.agent.tools.base import get_context_manager


@tool
def search_context(query: str, session_id: str = "") -> str:
    """从 OpenViking 知识库中搜索与查询相关的信息。

    包括之前对话的记忆、已注入的 Skill 知识（如表结构）等。
    适用场景：查数据库表结构、回忆之前的对话内容、获取领域知识。

    Args:
        query: 搜索的问题或关键词，如"评论表有哪些字段"、"商品表和评论表怎么关联"。
        session_id: 会话ID，传入可获取该会话的记忆上下文。
    """
    ctx = get_context_manager()
    if ctx is None:
        return "上下文管理器未初始化"
    context = ctx.get_context(session_id, query)
    return context or "未找到相关上下文信息"


@tool
def search_knowledge(query: str) -> str:
    """从知识库中进行无会话上下文的快速语义搜索。

    直接搜索已注入的所有知识资源（Skill 上下文、文档等），
    不依赖特定会话的记忆。适合查表结构、SQL 写法等固定知识。

    Args:
        query: 搜索问题，如"ClickHouse 商品表字段"、"评论表排序键"。
    """
    ctx = get_context_manager()
    if ctx is None:
        return "上下文管理器未初始化"
    try:
        results = ctx.find(query, limit=3)
        parts = []
        for r in results.resources[:3]:
            try:
                overview = ctx.overview(r.uri)
                if overview:
                    parts.append(overview)
            except Exception:
                pass
        return "\n\n".join(parts) if parts else "未找到相关知识"
    except Exception as e:
        return f"知识检索失败: {e}"


@tool
def query_products(query: str) -> str:
    """查询商品信息。当前为占位实现，后续接入 ClickHouse。"""
    return f"[商品查询 placeholder] 查询: {query} — 商品数据库尚未接入，请稍后再试。"
