"""上下文管理模块。

优先使用 OpenViking 实现 L0/L1/L2 分层上下文管理。
如果 OpenViking 未配置或不可用，自动降级为简单的内存上下文管理。
"""

from __future__ import annotations

import logging
from collections import defaultdict

from app.config import settings

logger = logging.getLogger(__name__)


class VikingContextManager:
    """上下文管理器，支持 OpenViking 和内存两种模式。

    初始化时尝试连接 OpenViking，失败则降级为内存模式。
    内存模式下仅保留最近的对话历史，不支持语义搜索。
    """

    def __init__(self, data_dir: str = "./data/viking") -> None:
        self._data_dir = data_dir
        self._client = None
        self._sessions = {}
        self._available = False

        self._memory_messages: dict[str, list[dict]] = defaultdict(list)
        self._max_memory = 50

        try:
            import openviking as ov
            self._client = ov.OpenViking(path=data_dir)
            self._client.initialize()
            self._sessions = {}
            self._available = True
            logger.info("VikingContextManager initialized (OpenViking mode), data_dir=%s", data_dir)
        except Exception as e:
            logger.warning(
                "OpenViking not available (%s), falling back to in-memory context. "
                "To enable: create ~/.openviking/ov.conf or set OPENVIKING_CONFIG_FILE",
                e,
            )

    @property
    def available(self) -> bool:
        return self._available

    def _get_session(self, session_id: str):
        if not self._available:
            return None
        if session_id not in self._sessions:
            self._sessions[session_id] = self._client.session(session_id)
        return self._sessions[session_id]

    def add_resource(self, path: str, reason: str = "") -> dict:
        if not self._available:
            logger.debug("Skipping add_resource (in-memory mode): %s", path)
            return {}
        result = self._client.add_resource(path=path, reason=reason, wait=False)
        logger.info("Added resource: %s", path)
        return result

    def wait_processed(self, timeout: int = 60) -> None:
        if not self._available:
            return
        self._client.wait_processed(timeout=timeout)

    def find(self, query: str, target_uri: str = "viking://resources/", limit: int = 5):
        if not self._available:
            return _EmptySearchResult()
        return self._client.find(query, target_uri=target_uri, limit=limit)

    def search(self, query: str, session_id: str = "", limit: int = 5):
        if not self._available:
            return _EmptySearchResult()
        return self._client.search(query, session_id=session_id, limit=limit)

    def read(self, uri: str) -> str:
        if not self._available:
            return ""
        return self._client.read(uri)

    def abstract(self, uri: str) -> str:
        if not self._available:
            return ""
        return self._client.abstract(uri)

    def overview(self, uri: str) -> str:
        if not self._available:
            return ""
        return self._client.overview(uri)

    def add_message(self, session_id: str, role: str, content: str) -> None:
        if self._available:
            session = self._get_session(session_id)
            if session:
                from openviking.message.part import TextPart
                session.add_message(role, parts=[TextPart(text=content)])
        else:
            msgs = self._memory_messages[session_id]
            msgs.append({"role": role, "content": content})
            if len(msgs) > self._max_memory:
                self._memory_messages[session_id] = msgs[-self._max_memory:]

    def commit_session(self, session_id: str) -> None:
        if self._available and session_id in self._sessions:
            self._sessions[session_id].commit()
            logger.info("Session %s committed", session_id)

    def get_context(self, session_id: str, query: str = "") -> str:
        if not query:
            return ""

        if self._available:
            return self._get_context_viking(session_id, query)

        return self._get_context_memory(session_id)

    def _get_context_viking(self, session_id: str, query: str) -> str:
        parts: list[str] = []
        try:
            if session_id:
                results = self.search(query, session_id=session_id, limit=5)
            else:
                results = self.find(query, limit=5)

            for r in results.resources[:3]:
                try:
                    overview = self.overview(r.uri)
                    parts.append(f"[资源] {overview}")
                except Exception:
                    pass

            for m in results.memories[:3]:
                try:
                    content = self.read(m.uri)
                    parts.append(f"[记忆] {content}")
                except Exception:
                    pass
        except Exception as e:
            logger.warning("Context retrieval failed: %s", e)

        return "\n".join(parts)

    def _get_context_memory(self, session_id: str) -> str:
        """内存模式：返回最近几轮对话作为上下文。"""
        msgs = self._memory_messages.get(session_id, [])
        if not msgs:
            return ""
        recent = msgs[-10:]
        lines = []
        for m in recent:
            role = "用户" if m["role"] == "user" else "助手"
            lines.append(f"[{role}] {m['content'][:200]}")
        return "\n".join(lines)

    def close(self) -> None:
        if self._available and self._client:
            self._client.close()


class _EmptySearchResult:
    """Viking 不可用时返回的空搜索结果。"""
    resources = []
    memories = []
