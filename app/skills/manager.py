"""Skills 管理模块。

扫描 skills/ 目录，加载 skill.yaml 配置和 context.md 内容。
支持两种检索模式：
1. 关键词匹配（默认回退）
2. OpenViking 语义检索（skill 内容注入 Viking 后，通过语义搜索匹配）
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path

import yaml

logger = logging.getLogger(__name__)


@dataclass
class Skill:
    """单个 Skill 的数据结构。"""

    name: str
    description: str
    trigger_keywords: list[str] = field(default_factory=list)
    context: str = ""
    path: Path = field(default_factory=lambda: Path("."))


class SkillManager:
    """Skills 管理器，负责加载和检索 skills。

    支持将 skill 内容注入 OpenViking 以获得语义检索能力，
    同时保留关键词匹配作为回退策略。
    """

    def __init__(self, skills_dir: str = "./skills") -> None:
        self._skills_dir = Path(skills_dir)
        self._skills: dict[str, Skill] = {}
        self._viking = None
        self._viking_ready = False
        self._load_all()

    def _load_all(self) -> None:
        """扫描 skills 目录，加载所有有效的 skill。"""
        if not self._skills_dir.exists():
            logger.warning("Skills directory not found: %s", self._skills_dir)
            return

        for child in sorted(self._skills_dir.iterdir()):
            if not child.is_dir():
                continue
            config_path = child / "skill.yaml"
            if not config_path.exists():
                continue
            try:
                self._load_skill(child, config_path)
            except Exception as e:
                logger.warning("Failed to load skill from %s: %s", child, e)

    def _load_skill(self, skill_dir: Path, config_path: Path) -> None:
        """加载单个 skill 的配置和上下文内容。"""
        with open(config_path, encoding="utf-8") as f:
            config = yaml.safe_load(f)

        name = config.get("name", skill_dir.name)
        description = config.get("description", "")
        trigger_keywords = config.get("trigger_keywords", [])

        context = ""
        context_path = skill_dir / "context.md"
        if context_path.exists():
            context = context_path.read_text(encoding="utf-8")

        skill = Skill(
            name=name,
            description=description,
            trigger_keywords=trigger_keywords,
            context=context,
            path=skill_dir,
        )
        self._skills[name] = skill
        logger.info("Loaded skill: %s (%d keywords)", name, len(trigger_keywords))

    def register_with_viking(self, viking_ctx) -> None:
        """将所有 skill 的 context.md 注入 OpenViking 进行语义索引。

        Args:
            viking_ctx: VikingContextManager 实例。
        """
        self._viking = viking_ctx
        for skill in self._skills.values():
            if skill.context and skill.path:
                context_path = skill.path / "context.md"
                if context_path.exists():
                    try:
                        viking_ctx.add_resource(
                            path=str(context_path.resolve()),
                            reason=f"Skill context: {skill.name} - {skill.description}",
                        )
                        logger.info("Registered skill '%s' with OpenViking", skill.name)
                    except Exception as e:
                        logger.warning("Failed to register skill '%s' with Viking: %s", skill.name, e)

        try:
            viking_ctx.wait_processed(timeout=30)
            self._viking_ready = True
            logger.info("All skills registered and indexed in OpenViking")
        except Exception as e:
            logger.warning("Viking indexing timeout/error, falling back to keyword match: %s", e)
            self._viking_ready = False

    def match(self, query: str, top_k: int = 3) -> list[Skill]:
        """根据用户查询匹配相关 skills（关键词方式）。"""
        if not query:
            return []

        scored: list[tuple[int, Skill]] = []
        query_lower = query.lower()
        for skill in self._skills.values():
            hits = sum(1 for kw in skill.trigger_keywords if kw.lower() in query_lower)
            if hits > 0:
                scored.append((hits, skill))

        scored.sort(key=lambda x: x[0], reverse=True)
        return [s for _, s in scored[:top_k]]

    def get_context_for_query(self, query: str, top_k: int = 3) -> str:
        """获取与用户查询相关的 skill 上下文。

        优先使用 OpenViking 语义检索，如未就绪则回退到关键词匹配。
        """
        if not query:
            return ""

        if self._viking_ready and self._viking:
            return self._get_context_via_viking(query, top_k)

        return self._get_context_via_keywords(query, top_k)

    def _get_context_via_viking(self, query: str, top_k: int) -> str:
        """通过 OpenViking 语义检索获取 skill 上下文。"""
        try:
            results = self._viking.find(query, limit=top_k)
            parts = []
            for r in results.resources[:top_k]:
                try:
                    overview = self._viking.overview(r.uri)
                    if overview:
                        parts.append(overview)
                except Exception:
                    pass
            if parts:
                return "\n\n".join(parts)
        except Exception as e:
            logger.warning("Viking skill retrieval failed, falling back to keywords: %s", e)

        return self._get_context_via_keywords(query, top_k)

    def _get_context_via_keywords(self, query: str, top_k: int) -> str:
        """通过关键词匹配获取 skill 上下文（回退策略）。"""
        matched = self.match(query, top_k=top_k)
        if not matched:
            return ""

        parts = []
        for skill in matched:
            if skill.context:
                parts.append(f"[Skill: {skill.name}]\n{skill.context}")
        return "\n\n".join(parts)

    def list_skills(self) -> list[dict]:
        """列出所有已加载的 skills 摘要信息。"""
        return [
            {"name": s.name, "description": s.description, "keywords": s.trigger_keywords}
            for s in self._skills.values()
        ]

    def get_skill(self, name: str) -> Skill | None:
        """按名称获取指定 skill。"""
        return self._skills.get(name)

    def reload(self) -> None:
        """重新扫描并加载所有 skills。"""
        self._skills.clear()
        self._viking_ready = False
        self._load_all()
        if self._viking:
            self.register_with_viking(self._viking)
