"""工具模块的共享依赖和配置。"""

from __future__ import annotations

_llm = None
_context_manager = None


def set_dependencies(llm, context_manager) -> None:
    """注入 LLM 和上下文管理器依赖。

    在图构建阶段调用，将模块级别的依赖设置为实际实例。
    """
    global _llm, _context_manager
    _llm = llm
    _context_manager = context_manager


def get_llm():
    return _llm


def get_context_manager():
    return _context_manager
