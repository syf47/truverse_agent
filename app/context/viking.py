"""OpenViking 上下文管理模块。

基于 OpenViking (https://github.com/volcengine/OpenViking) 实现 L0/L1/L2
分层上下文管理，使用嵌入式模式，无需额外服务器。
"""

from __future__ import annotations

import logging

import openviking as ov

from app.config import settings

logger = logging.getLogger(__name__)


class VikingContextManager:
    """基于 OpenViking 嵌入式模式的分层上下文管理器。

    使用 L0（摘要）、L1（概览）、L2（全文）三层结构管理上下文，
    支持语义搜索和会话记忆。

    Attributes:
        _data_dir: 数据存储目录路径。
        _client: OpenViking 客户端实例。
        _sessions: 会话 ID 到 Session 对象的映射缓存。
    """

    def __init__(self, data_dir: str = "./data/viking") -> None:
        self._data_dir = data_dir
        self._client = ov.OpenViking(path=data_dir)
        self._client.initialize()
        self._sessions: dict[str, ov.Session] = {}
        logger.info("VikingContextManager initialized, data_dir=%s", data_dir)

    def _get_session(self, session_id: str) -> ov.Session:
        """获取或创建指定 ID 的会话对象。

        Args:
            session_id: 会话标识符。

        Returns:
            对应的 OpenViking Session 实例。
        """
        if session_id not in self._sessions:
            self._sessions[session_id] = self._client.session(session_id)
        return self._sessions[session_id]

    def add_resource(self, path: str, reason: str = "") -> dict:
        """添加 URL、文件或目录作为上下文资源。

        Args:
            path: 资源路径（URL、文件路径或目录路径）。
            reason: 添加该资源的原因说明。

        Returns:
            添加操作的结果字典。
        """
        result = self._client.add_resource(path=path, reason=reason, wait=False)
        logger.info("Added resource: %s", path)
        return result

    def wait_processed(self, timeout: int = 60) -> None:
        """等待异步语义处理（L0/L1 生成）完成。

        Args:
            timeout: 最大等待时间，单位为秒。
        """
        self._client.wait_processed(timeout=timeout)

    def find(self, query: str, target_uri: str = "viking://resources/", limit: int = 5):
        """无会话上下文的快速语义搜索。

        Args:
            query: 搜索查询文本。
            target_uri: 搜索目标 URI 范围。
            limit: 最大返回结果数。

        Returns:
            搜索结果对象。
        """
        return self._client.find(query, target_uri=target_uri, limit=limit)

    def search(self, query: str, session_id: str = "", limit: int = 5):
        """带意图分析和会话上下文的复合检索。

        Args:
            query: 搜索查询文本。
            session_id: 会话标识符，用于关联上下文。
            limit: 最大返回结果数。

        Returns:
            搜索结果对象。
        """
        return self._client.search(query, session_id=session_id, limit=limit)

    def read(self, uri: str) -> str:
        """读取资源的 L2 全文内容。

        Args:
            uri: 资源的唯一标识 URI。

        Returns:
            资源的完整文本内容。
        """
        return self._client.read(uri)

    def abstract(self, uri: str) -> str:
        """读取资源的 L0 摘要（约 100 tokens）。

        Args:
            uri: 资源的唯一标识 URI。

        Returns:
            资源的简短摘要文本。
        """
        return self._client.abstract(uri)

    def overview(self, uri: str) -> str:
        """读取资源的 L1 概览（约 2k tokens）。

        Args:
            uri: 资源的唯一标识 URI。

        Returns:
            资源的概览文本。
        """
        return self._client.overview(uri)

    def add_message(self, session_id: str, role: str, content: str) -> None:
        """向会话的对话历史中添加一条消息。

        Args:
            session_id: 会话标识符。
            role: 消息角色（如 ``user`` 或 ``assistant``）。
            content: 消息文本内容。
        """
        session = self._get_session(session_id)
        session.add_message(role, content=content)

    def commit_session(self, session_id: str) -> None:
        """提交会话，归档对话记录并提取记忆。

        Args:
            session_id: 要提交的会话标识符。
        """
        if session_id in self._sessions:
            self._sessions[session_id].commit()
            logger.info("Session %s committed", session_id)

    def get_context(self, session_id: str, query: str = "") -> str:
        """构建用于提示注入的上下文字符串。

        采用渐进式加载策略：先用 L0 判断相关性，再用 L1 获取详细内容。

        Args:
            session_id: 会话标识符。
            query: 用户查询文本，为空时返回空字符串。

        Returns:
            拼接后的上下文字符串。
        """
        if not query:
            return ""

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

    def close(self) -> None:
        """释放资源并关闭客户端连接。"""
        self._client.close()
