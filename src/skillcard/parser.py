"""Lenient SKILL.md parser.

The SKILL.md frontmatter spec is still drifting across platforms
(Claude Code, agentskills.io, various forks). We therefore parse
tolerantly and report what we found instead of hard-failing.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

import yaml

CORE_FIELDS = ["name", "description"]
RECOMMENDED_FIELDS = ["when_to_use", "triggers", "examples", "license"]


@dataclass
class SkillDoc:
    path: Path
    frontmatter: dict = field(default_factory=dict)
    body: str = ""
    raw: str = ""
    parse_errors: list[str] = field(default_factory=list)

    @property
    def name(self) -> str:
        return str(self.frontmatter.get("name", ""))

    @property
    def description(self) -> str:
        return str(self.frontmatter.get("description", ""))

    @property
    def line_count(self) -> int:
        return len(self.raw.splitlines())

    @property
    def has_examples(self) -> bool:
        if "examples" in self.frontmatter:
            return True
        # Must have an explicit "Examples" / "Example" heading, not just any code block.
        return bool(re.search(r"(?im)^#{1,4}\s+examples?\b", self.body))


def parse_skill(path: str | Path) -> SkillDoc:
    p = Path(path)
    raw = p.read_text(encoding="utf-8")
    doc = SkillDoc(path=p, raw=raw)

    m = re.match(r"^---\s*\n(.*?)\n---\s*\n?(.*)$", raw, re.DOTALL)
    if not m:
        doc.parse_errors.append("missing YAML frontmatter block (--- ... ---)")
        doc.body = raw
        return doc

    fm_text, doc.body = m.group(1), m.group(2)
    try:
        doc.frontmatter = yaml.safe_load(fm_text) or {}
        if not isinstance(doc.frontmatter, dict):
            doc.parse_errors.append("frontmatter is not a key-value mapping")
            doc.frontmatter = {}
    except yaml.YAMLError as exc:
        doc.parse_errors.append(f"frontmatter YAML parse error: {exc}")
        doc.frontmatter = {}
    return doc
