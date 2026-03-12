"""LangGraph ReAct Agent 工作流模块。

使用 LangGraph 的 create_react_agent 构建 ReAct 循环式 Agent，
支持多轮推理、自检和工具调用。上下文通过 OpenViking 进行语义检索，
Skill 知识在每次请求时按需注入到 system prompt。
"""

from __future__ import annotations

import logging

from langchain_core.messages import BaseMessage, HumanMessage
from langchain_openai import ChatOpenAI
from langgraph.prebuilt import create_react_agent

from app.agent.prompts import SYSTEM_PROMPT
from app.agent.tools import ALL_TOOLS, set_dependencies
from app.config import settings
from app.context.viking import VikingContextManager
from app.skills import SkillManager

logger = logging.getLogger(__name__)

_context_manager: VikingContextManager | None = None
_skill_manager: SkillManager | None = None
_graph = None


def _get_context_manager() -> VikingContextManager:
    """获取或初始化全局上下文管理器单例。"""
    global _context_manager
    if _context_manager is None:
        _context_manager = VikingContextManager(data_dir=settings.viking_data_dir)
    return _context_manager


def _get_skill_manager() -> SkillManager:
    """获取或初始化全局 SkillManager 单例。"""
    global _skill_manager
    if _skill_manager is None:
        _skill_manager = SkillManager(skills_dir=settings.skills_dir)
    return _skill_manager


def _build_prompt(ctx_mgr: VikingContextManager, skill_mgr: SkillManager):
    """构建动态 system prompt 生成函数。

    返回一个可被 create_react_agent 使用的 prompt 函数，
    每次调用时根据用户最新消息动态检索 Viking 上下文和 Skills 知识。
    """

    def prompt_fn(state: dict) -> list[BaseMessage]:
        messages: list[BaseMessage] = state.get("messages", [])
        session_id = state.get("session_id", "")

        last_user_msg = ""
        for msg in reversed(messages):
            if isinstance(msg, HumanMessage):
                last_user_msg = msg.content if isinstance(msg.content, str) else str(msg.content)
                break

        context = ctx_mgr.get_context(session_id, last_user_msg)
        skills_context = skill_mgr.get_context_for_query(last_user_msg)

        system_prompt = SYSTEM_PROMPT.format(
            context=context,
            skills_context=skills_context,
        )

        from langchain_core.messages import SystemMessage
        return [SystemMessage(content=system_prompt)] + messages

    return prompt_fn


def _build_graph():
    """构建 ReAct Agent 状态图。

    使用 langgraph.prebuilt.create_react_agent，它内置了：
    - 多轮 Thought → Action → Observation 循环
    - 自动 tool calling 和结果回注
    - 终止条件判断（LLM 不再调用工具时结束）

    recursion_limit 控制最大推理轮数，防止无限循环。
    """
    llm = ChatOpenAI(
        model=settings.openai_model,
        api_key=settings.openai_api_key,
        temperature=0.3,
    )

    ctx_mgr = _get_context_manager()
    skill_mgr = _get_skill_manager()
    set_dependencies(llm, ctx_mgr)

    skill_mgr.register_with_viking(ctx_mgr)

    prompt_fn = _build_prompt(ctx_mgr, skill_mgr)

    graph = create_react_agent(
        model=llm,
        tools=ALL_TOOLS,
        prompt=prompt_fn,
    )

    return graph


def get_graph():
    """获取或构建全局 ReAct Agent 单例。"""
    global _graph
    if _graph is None:
        _graph = _build_graph()
    return _graph


async def run_agent(
    message: str,
    session_id: str,
    images: list[str] | None = None,
    recursion_limit: int = 25,
) -> str:
    """运行 ReAct Agent 处理用户消息。

    Agent 会在多轮 Thought/Action/Observation 循环中推理，
    直到认为信息足够后给出最终回答。

    Args:
        message: 用户发送的文本消息。
        session_id: 会话标识符。
        images: Base64 编码的图片列表，可选。
        recursion_limit: 最大推理轮数（每轮 = 1次 LLM + 1次 tool），默认 25。

    Returns:
        Agent 的最终文本回复。
    """
    graph = get_graph()
    ctx_mgr = _get_context_manager()

    if images:
        text_content = message
        content = [{"type": "text", "text": text_content}]
        for img_b64 in images:
            url = img_b64 if img_b64.startswith("data:") else f"data:image/jpeg;base64,{img_b64}"
            content.append({"type": "image_url", "image_url": {"url": url}})
        user_message = HumanMessage(content=content)
    else:
        user_message = HumanMessage(content=message)

    ctx_mgr.add_message(session_id, "user", message)

    result = await graph.ainvoke(
        {"messages": [user_message], "session_id": session_id},
        config={"recursion_limit": recursion_limit},
    )

    last_msg = result["messages"][-1]
    reply = last_msg.content if isinstance(last_msg.content, str) else str(last_msg.content)

    ctx_mgr.add_message(session_id, "assistant", reply)

    return reply
