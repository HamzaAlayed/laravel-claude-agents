"""Parses the Guild pack into the catalog the console needs.

Single source of truth is the pack itself: agent slug, human name, model, tools
and colour all come from `agents/*.md` frontmatter. Deliberately introduces no
new registry — a sixth place to register an agent would fight
scripts/check_inventory_sync.py. Stdlib only.
"""

from __future__ import annotations

import re
from pathlib import Path

COORDINATOR = "delivery-coordinator"
FALLBACK_STAGE = "Working"
STAGES = ["Discover", "Design", "Build", "Review", "Test", "Ship", "Docs", FALLBACK_STAGE]

# Role home, not a claim about the run's phase. The coordinator is the board's
# own header and deliberately absent.
STAGE_BY_AGENT = {
    "business-analyst": "Discover",
    "product-owner": "Discover",
    "scrum-master": "Discover",
    "solution-architect": "Design",
    "ui-ux-designer": "Design",
    "database-developer": "Build",
    "backend-developer": "Build",
    "frontend-developer": "Build",
    "mobile-developer": "Build",
    "package-developer": "Build",
    "tech-lead": "Review",
    "security-engineer": "Review",
    "performance-engineer": "Review",
    "qa-engineer": "Test",
    "devops-engineer": "Ship",
    "technical-writer": "Docs",
}

# Eight declared hue families cover seventeen agents, so families collide. Each
# member of a family takes a distinct shade, indexed by its position in the
# family's alphabetically sorted membership.
COLOR_RAMPS = {
    "green": ["#22c55e", "#15803d", "#4ade80", "#065f46"],
    "blue": ["#3b82f6", "#1d4ed8", "#60a5fa", "#1e3a8a"],
    "yellow": ["#eab308", "#a16207", "#fde047", "#713f12"],
    "red": ["#ef4444", "#b91c1c", "#f87171", "#7f1d1d"],
    "cyan": ["#06b6d4", "#0e7490", "#67e8f9", "#164e63"],
    "orange": ["#f97316", "#c2410c", "#fdba74", "#7c2d12"],
    "purple": ["#a855f7", "#7e22ce", "#d8b4fe", "#581c87"],
    "pink": ["#ec4899", "#be185d", "#f9a8d4", "#831843"],
}
UNKNOWN_COLOR = "#64748b"

_FRONTMATTER = re.compile(r"\A---\s*\n(.*?)\n---\s*\n", re.S)
_NAME_PREFIX = re.compile(r"^\s*([A-Z][\w'-]*)\s+—")


def _frontmatter(text: str) -> dict[str, str]:
    """Top-level `key: value` pairs only. Values may be wrapped in quotes."""
    match = _FRONTMATTER.match(text)
    if not match:
        return {}
    fields: dict[str, str] = {}
    for line in match.group(1).splitlines():
        if line.startswith((" ", "\t", "#")) or ":" not in line:
            continue
        key, _, value = line.partition(":")
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
            value = value[1:-1]
        fields[key.strip()] = value
    return fields


def stage_for(slug: str) -> str:
    """Column for an agent. Unknown agents land in Working rather than vanishing."""
    return STAGE_BY_AGENT.get(slug, FALLBACK_STAGE)


def _human_name(description: str, slug: str) -> str:
    match = _NAME_PREFIX.match(description)
    if match:
        return match.group(1)
    return slug.replace("-", " ").title()


def _assign_colors(agents: list[dict]) -> None:
    families: dict[str, list[str]] = {}
    for agent in agents:
        families.setdefault(agent["_family"], []).append(agent["slug"])
    for slugs in families.values():
        slugs.sort()
    for agent in agents:
        ramp = COLOR_RAMPS.get(agent["_family"])
        if not ramp:
            agent["color"] = UNKNOWN_COLOR
        else:
            index = families[agent["_family"]].index(agent["slug"]) % len(ramp)
            agent["color"] = ramp[index]
        del agent["_family"]


def load_catalog(root: Path) -> dict:
    agents = []
    for path in sorted((root / "agents").glob("*.md")):
        fields = _frontmatter(path.read_text(encoding="utf-8"))
        slug = fields.get("name") or path.stem
        description = fields.get("description", "")
        agents.append(
            {
                "slug": slug,
                "name": _human_name(description, slug),
                "description": description,
                "model": fields.get("model", ""),
                "tools": [t.strip() for t in fields.get("tools", "").split(",") if t.strip()],
                "stage": None if slug == COORDINATOR else stage_for(slug),
                "_family": fields.get("color", ""),
            }
        )
    _assign_colors(agents)

    commands = []
    for path in sorted((root / "commands").glob("*.md")):
        fields = _frontmatter(path.read_text(encoding="utf-8"))
        commands.append(
            {
                "slug": path.stem,
                "description": fields.get("description", ""),
                "argument_hint": fields.get("argument-hint", ""),
            }
        )

    skills = []
    for path in sorted((root / "skills").glob("*/SKILL.md")):
        fields = _frontmatter(path.read_text(encoding="utf-8"))
        skills.append(
            {
                "slug": fields.get("name") or path.parent.name,
                "description": fields.get("description", ""),
            }
        )

    return {"agents": agents, "commands": commands, "skills": skills, "stages": STAGES}
