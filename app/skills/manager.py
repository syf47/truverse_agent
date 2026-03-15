"""Skills 管理模块。

扫描 skills/ 目录，加载 SKILL.md（frontmatter + markdown body）。
支持两种检索模式：
1. 关键词匹配（默认回退）
2. OpenViking skill-scoped 语义检索（通过 add_skill() 注入 Viking）
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
    tags: list[str] = field(default_factory=list)
    context: str = ""
    path: Path = field(default_factory=lambda: Path("."))


class SkillManager:
    """Skills 管理器，负责加载和检索 skills。

    使用 SKILL.md 格式（YAML frontmatter + markdown body），
    通过 OpenViking add_skill() 注入以获得 skill-scoped 语义检索，
    保留关键词匹配作为回退策略。
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
            skill_md = child / "SKILL.md"
            if not skill_md.exists():
                continue
            try:
                self._load_skill(child, skill_md)
            except Exception as e:
                logger.warning("Failed to load skill from %s: %s", child, e)

    def _load_skill(self, skill_dir: Path, skill_md: Path) -> None:
        """加载单个 skill 的 SKILL.md（frontmatter + body）。"""
        raw = skill_md.read_text(encoding="utf-8")

        # Parse YAML frontmatter between --- delimiters
        frontmatter, body = self._parse_frontmatter(raw)

        name = frontmatter.get("name", skill_dir.name)
        description = frontmatter.get("description", "")
        tags = frontmatter.get("tags", [])

        skill = Skill(
            name=name,
            description=description,
            tags=tags,
            context=body.strip(),
            path=skill_dir,
        )
        self._skills[name] = skill
        logger.info("Loaded skill: %s (%d tags)", name, len(tags))

    @staticmethod
    def _parse_frontmatter(text: str) -> tuple[dict, str]:
        """解析 SKILL.md 的 YAML frontmatter 和 markdown body。"""
        if not text.startswith("---"):
            return {}, text

        # Find the closing ---
        end = text.find("---", 3)
        if end == -1:
            return {}, text

        fm_raw = text[3:end]
        body = text[end + 3:]

        try:
            fm = yaml.safe_load(fm_raw) or {}
        except yaml.YAMLError:
            fm = {}

        return fm, body

    def register_with_viking(self, viking_ctx) -> None:
        """将所有 skill 目录通过 add_skill() 注入 OpenViking。

        Args:
            viking_ctx: VikingContextManager 实例。
        """
        self._viking = viking_ctx
        for skill in self._skills.values():
            if skill.path:
                try:
                    viking_ctx.add_skill(
                        path=str(skill.path.resolve()),
                        wait=False,
                    )
                    logger.info("Registered skill '%s' with OpenViking", skill.name)
                except Exception as e:
                    logger.warning("Failed to register skill '%s' with Viking: %s", skill.name, e)

        try:
            viking_ctx.wait_processed(timeout=120)
            self._viking_ready = True
            logger.info("All skills registered and indexed in OpenViking")
        except Exception as e:
            logger.warning("Viking indexing timeout/error, falling back to keyword match: %s", e)
            self._viking_ready = False

    def match(self, query: str, top_k: int = 3) -> list[Skill]:
        """根据用户查询匹配相关 skills（关键词方式，使用 tags）。"""
        if not query:
            return []

        scored: list[tuple[int, Skill]] = []
        query_lower = query.lower()
        for skill in self._skills.values():
            hits = sum(1 for tag in skill.tags if tag.lower() in query_lower)
            if hits > 0:
                scored.append((hits, skill))

        scored.sort(key=lambda x: x[0], reverse=True)
        return [s for _, s in scored[:top_k]]

    def get_context_for_query(self, query: str, top_k: int = 3) -> str:
        """获取与用户查询相关的 skill 上下文。

        优先使用 OpenViking skill-scoped 语义检索，如未就绪则回退到关键词匹配。
        """
        if not query:
            return ""

        if self._viking_ready and self._viking:
            return self._get_context_via_viking(query, top_k)

        return self._get_context_via_keywords(query, top_k)

    def _get_context_via_viking(self, query: str, top_k: int) -> str:
        """通过 OpenViking skill-scoped 语义检索获取 skill 上下文。"""
        try:
            results = self._viking.find(
                query,
                target_uri="viking://agent/skills",
                limit=top_k,
            )
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
            {"name": s.name, "description": s.description, "tags": s.tags}
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
