"""Shared fixtures for skillcard tests."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

# Make src importable when running pytest from project root.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from skillcard.parser import SkillDoc, parse_skill_text


def make_skill_doc(
    frontmatter: str = "",
    body: str = "",
    raw: str | None = None,
) -> SkillDoc:
    """Build a SkillDoc via the real parser (no duplicate parsing logic)."""
    if raw is None:
        raw = f"---\n{frontmatter}\n---\n\n{body}"
    return parse_skill_text(raw, path="test/SKILL.md")


@pytest.fixture
def good_skill() -> SkillDoc:
    """A well-formed skill that should pass all L1 checks."""
    return make_skill_doc(
        frontmatter=(
            "name: commit-message\n"
            "description: Write conventional-commit messages from a git diff. "
            "Use when the user asks to commit, write a commit message, or summarize staged changes.\n"
            "when_to_use: User asks to create a commit message or commit staged changes.\n"
            "license: MIT\n"
        ),
        body=(
            "# Commit Message Writer\n\n"
            "## Steps\n\n"
            "1. Run git diff --staged and read the changes.\n"
            "2. Identify the type: feat, fix, refactor, docs, test, chore.\n"
            "3. Write a one-line summary.\n\n"
            "## Output format\n\n"
            "Return ONLY the commit message text, no commentary.\n\n"
            "## Examples\n\n"
            "Input diff adds a login endpoint -> `feat(auth): add login endpoint with JWT`\n"
        ),
    )


@pytest.fixture
def bad_skill() -> SkillDoc:
    """A poorly-formed skill that should fail nearly all L1 checks."""
    # No frontmatter block at all - raw is just plain text.
    return make_skill_doc(
        raw="just some stuff about things and etc\n\nno structure here at all\n",
    )
