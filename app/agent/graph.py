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
    llm_kwargs = dict(
        model=settings.openai_model,
        api_key=settings.openai_api_key,
        temperature=0.3,
    )
    if settings.openai_base_url:
        llm_kwargs["base_url"] = settings.openai_base_url
    llm = ChatOpenAI(**llm_kwargs)

    ctx_mgr = _get_context_manager()
    skill_mgr = _get_skill_manager()
    set_dependencies(llm, ctx_mgr)

    if ctx_mgr.available:
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


def _build_user_message(message: str, images: list[str] | None = None) -> HumanMessage:
    """构建用户消息（支持图片）。"""
    if images:
        content: list[dict] = [{"type": "text", "text": message}]
        for img_b64 in images:
            url = img_b64 if img_b64.startswith("data:") else f"data:image/jpeg;base64,{img_b64}"
            content.append({"type": "image_url", "image_url": {"url": url}})
        return HumanMessage(content=content)
    return HumanMessage(content=message)


async def run_agent(
    message: str,
    session_id: str,
    images: list[str] | None = None,
    recursion_limit: int = 25,
) -> str:
    """运行 ReAct Agent 处理用户消息（非流式）。"""
    graph = get_graph()
    ctx_mgr = _get_context_manager()
    user_message = _build_user_message(message, images)

    ctx_mgr.add_message(session_id, "user", message)

    result = await graph.ainvoke(
        {"messages": [user_message], "session_id": session_id},
        config={"recursion_limit": recursion_limit},
    )

    last_msg = result["messages"][-1]
    reply = last_msg.content if isinstance(last_msg.content, str) else str(last_msg.content)

    ctx_mgr.add_message(session_id, "assistant", reply)
    ctx_mgr.commit_session(session_id)
    return reply


async def stream_agent(
    message: str,
    session_id: str,
    images: list[str] | None = None,
    recursion_limit: int = 25,
):
    """运行 ReAct Agent 处理用户消息（流式输出）。

    通过 astream_events 输出每个 token、工具调用、推理步骤。
    Yields dict events: {"type": ..., "data": ...}
    """
    import json as _json

    graph = get_graph()
    ctx_mgr = _get_context_manager()
    user_message = _build_user_message(message, images)

    ctx_mgr.add_message(session_id, "user", message)

    full_reply = ""

    async for event in graph.astream_events(
        {"messages": [user_message], "session_id": session_id},
        config={"recursion_limit": recursion_limit},
        version="v2",
    ):
        kind = event.get("event", "")
        data = event.get("data", {})

        if kind == "on_chat_model_stream":
            chunk = data.get("chunk")
            if chunk and hasattr(chunk, "content") and chunk.content:
                content = chunk.content
                if isinstance(content, str):
                    full_reply += content
                    yield {"type": "token", "data": content}

        elif kind == "on_tool_start":
            tool_name = event.get("name", "unknown")
            tool_input = data.get("input", {})
            yield {
                "type": "tool_start",
                "data": _json.dumps(
                    {"tool": tool_name, "input": tool_input},
                    ensure_ascii=False,
                    default=str,
                ),
            }

        elif kind == "on_tool_end":
            tool_name = event.get("name", "unknown")
            output = data.get("output", "")
            output_str = output.content if hasattr(output, "content") else str(output)
            if len(output_str) > 2000:
                output_str = output_str[:2000] + "...(truncated)"
            yield {
                "type": "tool_end",
                "data": _json.dumps(
                    {"tool": tool_name, "output": output_str},
                    ensure_ascii=False,
                    default=str,
                ),
            }

    ctx_mgr.add_message(session_id, "assistant", full_reply)
    ctx_mgr.commit_session(session_id)
    yield {"type": "done", "data": ""}
