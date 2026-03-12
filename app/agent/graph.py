"""LangGraph agent: main conversation flow."""

from __future__ import annotations

import logging
from typing import Annotated, TypedDict

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI
from langgraph.graph import END, StateGraph
from langgraph.graph.message import add_messages
from langgraph.prebuilt import ToolNode

from app.agent.prompts import SYSTEM_PROMPT
from app.agent.tools import (
    analyze_image,
    annotate_image,
    ocr_image,
    query_products,
    search_context,
    set_dependencies,
)
from app.config import settings
from app.context.viking import VikingContextManager

logger = logging.getLogger(__name__)


class AgentState(TypedDict):
    messages: Annotated[list[BaseMessage], add_messages]
    session_id: str
    images: list[str]  # base64 encoded images for current turn


# Module-level singletons
_context_manager: VikingContextManager | None = None
_graph = None


def _get_context_manager() -> VikingContextManager:
    global _context_manager
    if _context_manager is None:
        _context_manager = VikingContextManager(data_dir=settings.viking_data_dir)
    return _context_manager


def _build_graph():
    tools = [ocr_image, analyze_image, annotate_image, search_context, query_products]

    llm = ChatOpenAI(
        model=settings.openai_model,
        api_key=settings.openai_api_key,
        temperature=0.3,
    )

    ctx_mgr = _get_context_manager()
    set_dependencies(llm, ctx_mgr)

    llm_with_tools = llm.bind_tools(tools)

    async def agent_node(state: AgentState) -> dict:
        session_id = state.get("session_id", "")
        images = state.get("images", [])
        messages = list(state["messages"])

        # Extract last user message text
        last_user_msg = ""
        for msg in reversed(messages):
            if isinstance(msg, HumanMessage):
                last_user_msg = msg.content if isinstance(msg.content, str) else str(msg.content)
                break

        # Inject context from OpenViking
        context = ctx_mgr.get_context(session_id, last_user_msg)
        system_prompt = SYSTEM_PROMPT.format(context=context)

        full_messages: list[BaseMessage] = [SystemMessage(content=system_prompt)]

        # If there are images in this turn, modify the last user message to include them
        if images and messages:
            for i in range(len(messages) - 1, -1, -1):
                if isinstance(messages[i], HumanMessage):
                    text = messages[i].content if isinstance(messages[i].content, str) else str(messages[i].content)
                    content = [{"type": "text", "text": text}]
                    for img_b64 in images:
                        url = img_b64 if img_b64.startswith("data:") else f"data:image/jpeg;base64,{img_b64}"
                        content.append({"type": "image_url", "image_url": {"url": url}})
                    messages = messages[:i] + [HumanMessage(content=content)] + messages[i + 1:]
                    break

        full_messages.extend(messages)

        response = await llm_with_tools.ainvoke(full_messages)

        # Store conversation in OpenViking session
        ctx_mgr.add_message(session_id, "user", last_user_msg)
        ctx_mgr.add_message(session_id, "assistant", response.content if isinstance(response.content, str) else str(response.content))

        return {"messages": [response]}

    tool_node = ToolNode(tools)

    def should_continue(state: AgentState) -> str:
        last_message = state["messages"][-1]
        if isinstance(last_message, AIMessage) and last_message.tool_calls:
            return "tools"
        return END

    graph = StateGraph(AgentState)
    graph.add_node("agent", agent_node)
    graph.add_node("tools", tool_node)
    graph.set_entry_point("agent")
    graph.add_conditional_edges("agent", should_continue, {"tools": "tools", END: END})
    graph.add_edge("tools", "agent")

    return graph.compile()


def get_graph():
    global _graph
    if _graph is None:
        _graph = _build_graph()
    return _graph


async def run_agent(message: str, session_id: str, images: list[str] | None = None) -> str:
    """Run the agent with a user message and return the final text reply."""
    graph = get_graph()
    result = await graph.ainvoke({
        "messages": [HumanMessage(content=message)],
        "session_id": session_id,
        "images": images or [],
    })
    last_msg = result["messages"][-1]
    return last_msg.content if isinstance(last_msg.content, str) else str(last_msg.content)
