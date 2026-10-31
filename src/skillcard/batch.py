"""Batch evaluation and version diff.

Real AI-engineering work is not "score one file" — it is "score a directory,
change something, and see what moved". This module provides both halves:

- ``find_skills`` / ``evaluate_all``: recursively scan a directory for
  ``SKILL.md`` files and evaluate each one.
- ``diff_results``: compare two snapshots (before / after) of the same set of
  skills and report, per skill, how the score, grade, failed checks, and LLM
  cost changed.

A "snapshot" is a ``dict[str, EvalResult]`` keyed by skill path (or name).
Both halves are pure functions over ``EvalResult`` objects, so they compose
with the CLI and with tests without any I/O.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from skillcard.cli import evaluate
from skillcard.models import EvalResult

# A SKILL.md is the canonical filename, but people also use lowercase.
SKILL_FILENAMES = ("SKILL.md", "skill.md")


def find_skills(directory: str | Path) -> list[Path]:
    """Recursively find SKILL.md files under ``directory``."""
    root = Path(directory)
    if not root.is_dir():
        return []
    out: list[Path] = []
    for p in root.rglob("*"):
        if p.is_file() and p.name in SKILL_FILENAMES:
            out.append(p)
    return sorted(out)


def evaluate_all(
    directory: str | Path,
    use_llm: bool = True,
    run: bool = False,
    use_cache: bool = True,
) -> dict[str, EvalResult]:
    """Evaluate every SKILL.md under ``directory``.

    Returns a snapshot ``{path_str: EvalResult}``. Skills are keyed by their
    path relative to ``directory`` where possible, so the snapshot is stable
    across machines for diffing.
    """
    root = Path(directory)
    snapshot: dict[str, EvalResult] = {}
    for skill in find_skills(root):
        try:
            rel = skill.relative_to(root)
        except ValueError:
            rel = skill
        result = evaluate(str(skill), use_llm=use_llm, run=run, use_cache=use_cache)
        snapshot[str(rel)] = result
    return snapshot


@dataclass
class DiffEntry:
    """Score/grade/cost change for one skill between two snapshots."""

    path: str
    before: EvalResult | None = None
    after: EvalResult | None = None

    @property
    def status(self) -> str:
        if self.before is None:
            return "added"
        if self.after is None:
            return "removed"
        return "changed"

    @property
    def score_delta(self) -> float:
        if self.before is None or self.after is None:
            return 0.0
        return round(self.after.total_score - self.before.total_score, 1)

    @property
    def grade_delta(self) -> str:
        if self.before is None:
            return f"- → {self.after.grade}"
        if self.after is None:
            return f"{self.before.grade} → -"
        if self.before.grade == self.after.grade:
            return self.after.grade
        return f"{self.before.grade} → {self.after.grade}"

    @property
    def failed_check_delta(self) -> int:
        before = sum(1 for c in self.before.checks if not c.passed) if self.before else 0
        after = sum(1 for c in self.after.checks if not c.passed) if self.after else 0
        return after - before

    @property
    def cost_delta(self) -> int:
        before = (self.before.judge_total_tokens or 0) if self.before else 0
        after = (self.after.judge_total_tokens or 0) if self.after else 0
        return after - before


@dataclass
class DiffReport:
    """Aggregate diff between two snapshots."""

    entries: list[DiffEntry] = field(default_factory=list)

    @property
    def added(self) -> list[DiffEntry]:
        return [e for e in self.entries if e.status == "added"]

    @property
    def removed(self) -> list[DiffEntry]:
        return [e for e in self.entries if e.status == "removed"]

    @property
    def changed(self) -> list[DiffEntry]:
        return [e for e in self.entries if e.status == "changed"]

    @property
    def improved(self) -> list[DiffEntry]:
        return [e for e in self.changed if e.score_delta > 0]

    @property
    def regressed(self) -> list[DiffEntry]:
        return [e for e in self.changed if e.score_delta < 0]


def diff_results(
    before: dict[str, EvalResult],
    after: dict[str, EvalResult],
) -> DiffReport:
    """Compare two snapshots keyed by the same path.

    Entries are sorted so the biggest regressions and improvements surface
    first — the ones you actually care about after an edit.
    """
    all_paths = sorted(set(before) | set(after))
    entries = [
        DiffEntry(path=p, before=before.get(p), after=after.get(p)) for p in all_paths
    ]
    # Stable sort: regressions first (most negative), then improvements.
    entries.sort(key=lambda e: e.score_delta)
    return DiffReport(entries=entries)


def render_diff(report: DiffReport) -> str:
    lines = [
        (
            f"diff: {len(report.entries)} skills "
            f"({len(report.added)} added, {len(report.removed)} removed, "
            f"{len(report.changed)} changed)"
        ),
        "",
    ]
    for e in report.entries:
        if e.status == "added":
            lines.append(f"  + {e.path}  -> grade {e.grade_delta}  ({e.after.total_score}/100)")
        elif e.status == "removed":
            lines.append(f"  - {e.path}  was {e.grade_delta}")
        else:
            delta = e.score_delta
            sign = "+" if delta > 0 else ("-" if delta < 0 else " ")
            checks = e.failed_check_delta
            checks_s = f"{checks:+d}" if checks else "0"
            cost = e.cost_delta
            cost_s = f"{cost:+d} tok" if cost else "0 tok"
            lines.append(
                f"  {sign}{e.path}: {e.grade_delta}  ({delta:+g})  "
                f"failed-checks {checks_s}  cost {cost_s}"
            )
    return "\n".join(lines)
