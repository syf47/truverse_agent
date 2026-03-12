"""OpenViking context management wrapper.

OpenViking provides L0/L1/L2 layered context management.
This module wraps it for use with the Agent's conversation and product data.

NOTE: openviking is listed as a conceptual dependency. Until the package is
available on PyPI, this module provides a stub implementation that stores
context in-memory with a simple dict-based approach.
"""

from __future__ import annotations

import logging
from collections import defaultdict
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


@dataclass
class ContextEntry:
    key: str
    content: str
    layer: str = "L0"  # L0=immediate, L1=session, L2=long-term
    metadata: dict = field(default_factory=dict)


class VikingContextManager:
    """In-memory context manager following the OpenViking L0/L1/L2 pattern.

    Replace internals with actual OpenViking client when available.
    """

    def __init__(self, data_dir: str = "./data/viking") -> None:
        self._data_dir = data_dir
        # layer -> list[ContextEntry]
        self._store: dict[str, list[ContextEntry]] = defaultdict(list)
        logger.info("VikingContextManager initialized (in-memory stub), data_dir=%s", data_dir)

    def add_resource(self, key: str, content: str, layer: str = "L0", metadata: dict | None = None) -> None:
        entry = ContextEntry(key=key, content=content, layer=layer, metadata=metadata or {})
        self._store[layer].append(entry)

    def search(self, query: str, top_k: int = 5) -> list[ContextEntry]:
        """Simple keyword search across all layers. Replace with vector search."""
        results: list[ContextEntry] = []
        query_lower = query.lower()
        for entries in self._store.values():
            for entry in entries:
                if query_lower in entry.content.lower() or query_lower in entry.key.lower():
                    results.append(entry)
        return results[:top_k]

    def get_context(self, session_id: str, query: str = "") -> str:
        """Build context string from relevant entries for injection into prompts."""
        parts: list[str] = []

        # L0: immediate context (always include recent for this session)
        for entry in self._store.get("L0", []):
            if entry.metadata.get("session_id") == session_id:
                parts.append(entry.content)

        # L1/L2: search-based context
        if query:
            for entry in self.search(query):
                if entry.content not in parts:
                    parts.append(entry.content)

        return "\n".join(parts[-10:])  # limit context window
