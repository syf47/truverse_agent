"""OpenViking context management wrapper.

Uses OpenViking (https://github.com/volcengine/OpenViking) for L0/L1/L2
layered context management. Embedded mode, no server needed.
"""

from __future__ import annotations

import logging

import openviking as ov

from app.config import settings

logger = logging.getLogger(__name__)


class VikingContextManager:
    """OpenViking context manager using embedded mode with L0/L1/L2 layers."""

    def __init__(self, data_dir: str = "./data/viking") -> None:
        self._data_dir = data_dir
        self._client = ov.OpenViking(path=data_dir)
        self._client.initialize()
        self._sessions: dict[str, ov.Session] = {}
        logger.info("VikingContextManager initialized, data_dir=%s", data_dir)

    def _get_session(self, session_id: str) -> ov.Session:
        if session_id not in self._sessions:
            self._sessions[session_id] = self._client.session(session_id)
        return self._sessions[session_id]

    def add_resource(self, path: str, reason: str = "") -> dict:
        """Add a URL, file, or directory as a resource."""
        result = self._client.add_resource(path=path, reason=reason, wait=False)
        logger.info("Added resource: %s", path)
        return result

    def wait_processed(self, timeout: int = 60) -> None:
        """Wait for async semantic processing (L0/L1 generation) to finish."""
        self._client.wait_processed(timeout=timeout)

    def find(self, query: str, target_uri: str = "viking://resources/", limit: int = 5):
        """Quick semantic search without session context."""
        return self._client.find(query, target_uri=target_uri, limit=limit)

    def search(self, query: str, session_id: str = "", limit: int = 5):
        """Complex retrieval with intent analysis and session context."""
        return self._client.search(query, session_id=session_id, limit=limit)

    def read(self, uri: str) -> str:
        """Read L2 full content of a resource."""
        return self._client.read(uri)

    def abstract(self, uri: str) -> str:
        """Read L0 abstract (~100 tokens)."""
        return self._client.abstract(uri)

    def overview(self, uri: str) -> str:
        """Read L1 overview (~2k tokens)."""
        return self._client.overview(uri)

    def add_message(self, session_id: str, role: str, content: str) -> None:
        """Add a message to a session's conversation history."""
        session = self._get_session(session_id)
        session.add_message(role, content=content)

    def commit_session(self, session_id: str) -> None:
        """Commit session to archive conversation and extract memories."""
        if session_id in self._sessions:
            self._sessions[session_id].commit()
            logger.info("Session %s committed", session_id)

    def get_context(self, session_id: str, query: str = "") -> str:
        """Build context string for prompt injection.

        Uses progressive loading: L0 for relevance check, L1 for detail.
        """
        if not query:
            return ""

        parts: list[str] = []

        # Search for relevant resources and memories
        try:
            if session_id:
                results = self.search(query, session_id=session_id, limit=5)
            else:
                results = self.find(query, limit=5)

            # Include resource overviews (L1) for top results
            for r in results.resources[:3]:
                try:
                    overview = self.overview(r.uri)
                    parts.append(f"[资源] {overview}")
                except Exception:
                    pass

            # Include memories
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
        """Release resources."""
        self._client.close()
