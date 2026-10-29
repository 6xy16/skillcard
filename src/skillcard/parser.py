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


def parse_skill_text(raw: str, path: str | Path = "SKILL.md") -> SkillDoc:
    """Parse SKILL.md contents from a string.

    ``path`` is only used to populate ``SkillDoc.path`` for display/reporting;
    nothing is read from disk.
    """
    doc = SkillDoc(path=Path(path), raw=raw)

    # Strip a UTF-8 BOM and normalize CRLF so the frontmatter anchors match.
    text = raw.lstrip("\ufeff")
    text = text.replace("\r\n", "\n").replace("\r", "\n")

    # Locate the frontmatter fence line-by-line for robustness against empty
    # frontmatter ("---\n---") and other edge cases.
    lines = text.split("\n")
    if not lines or lines[0].strip() != "---":
        doc.parse_errors.append("missing YAML frontmatter block (--- ... ---)")
        doc.body = text
        return doc

    end = None
    for i in range(1, len(lines)):
        if lines[i].strip() == "---":
            end = i
            break

    if end is None:
        doc.parse_errors.append("unterminated YAML frontmatter block (missing closing ---)")
        doc.body = text
        return doc

    fm_text = "\n".join(lines[1:end])
    # Drop the single conventional blank line that separates frontmatter from body.
    doc.body = "\n".join(lines[end + 1 :]).lstrip("\n")
    try:
        doc.frontmatter = yaml.safe_load(fm_text) or {}
        if not isinstance(doc.frontmatter, dict):
            doc.parse_errors.append("frontmatter is not a key-value mapping")
            doc.frontmatter = {}
    except yaml.YAMLError as exc:
        doc.parse_errors.append(f"frontmatter YAML parse error: {exc}")
        doc.frontmatter = {}
    return doc


def parse_skill(path: str | Path) -> SkillDoc:
    p = Path(path)
    raw = p.read_text(encoding="utf-8")
    return parse_skill_text(raw, path=p)
