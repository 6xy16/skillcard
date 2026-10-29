"""Core data structures for evaluation results."""

from __future__ import annotations

import hashlib
from dataclasses import asdict, dataclass, field
from typing import Any, ClassVar


@dataclass
class Check:
    """A single deterministic (L1) check result."""

    name: str
    passed: bool
    weight: int = 10
    message: str = ""
    suggestion: str = ""  # how to fix, with a copy-paste snippet


@dataclass
class Dimension:
    """One scored dimension shown on the card."""

    key: str
    label: str
    score: float | None  # 0-100, None = skipped
    detail: str = ""


@dataclass
class EvalResult:
    """Full evaluation result for one SKILL.md."""

    path: str
    skill_name: str = ""
    dimensions: list[Dimension] = field(default_factory=list)
    checks: list[Check] = field(default_factory=list)
    total_score: float = 0.0
    grade: str = "F"
    injection_hits: list[str] = field(default_factory=list)
    judge_model: str = "static-only"
    judge_prompt_hash: str = ""
    eval_version: str = "v1.0"
    warnings: list[str] = field(default_factory=list)

    # Weights per quality dimension. Security is a gate, not a scored dimension.
    DIMENSION_WEIGHTS: ClassVar[dict[str, float]] = {
        "structure": 0.40,
        "trigger_accuracy": 0.20,
        "boundary_robustness": 0.15,
        "instruction_clarity": 0.15,
        "output_verifiability": 0.10,
    }

    def finalize(self) -> EvalResult:
        # Base quality score: only quality dimensions, no security gate.
        scored = [d for d in self.dimensions if d.score is not None]
        if scored:
            weighted_sum = 0.0
            weight_total = 0.0
            for d in scored:
                w = self.DIMENSION_WEIGHTS.get(d.key, 1.0)
                weighted_sum += d.score * w
                weight_total += w
            if weight_total > 0:
                self.total_score = round(weighted_sum / weight_total, 1)

        # Security gate: cap the grade based on injection hits.
        self.grade = score_to_grade(self.total_score)
        n_hits = len(self.injection_hits)
        if n_hits >= 3:
            self.grade = "F"
            self.warnings.append("security gate: >=3 injection patterns found, grade capped at F")
        elif n_hits == 2:
            self.grade = cap_grade(self.grade, "D")
            self.warnings.append("security gate: 2 injection patterns found, grade capped at D")
        elif n_hits == 1:
            self.grade = cap_grade(self.grade, "B")
            self.warnings.append("security gate: 1 injection pattern found, grade capped at B")
        return self

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


GRADE_ORDER = ["A", "B", "C", "D", "F"]


def score_to_grade(score: float) -> str:
    if score >= 90:
        return "A"
    if score >= 80:
        return "B"
    if score >= 70:
        return "C"
    if score >= 60:
        return "D"
    return "F"


def cap_grade(grade: str, cap: str) -> str:
    """Return the worse of grade and cap (A is best, F is worst)."""
    g_rank = GRADE_ORDER.index(grade) if grade in GRADE_ORDER else 4
    c_rank = GRADE_ORDER.index(cap) if cap in GRADE_ORDER else 4
    return GRADE_ORDER[max(g_rank, c_rank)]


def grade_color(grade: str) -> str:
    return {
        "A": "#2da44e",  # green
        "B": "#6e9f18",  # yellow-green
        "C": "#bf8700",  # yellow
        "D": "#d1242f",  # orange-red
        "F": "#cf222e",  # red
    }.get(grade, "#57606a")


def prompt_hash(prompt: str) -> str:
    return hashlib.sha256(prompt.encode("utf-8")).hexdigest()[:6]
