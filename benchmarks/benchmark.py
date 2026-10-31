"""Small, open, reproducible benchmark for skill triggering.

This is the programmatic side of the benchmark: a deterministic trigger
approximation that stands in for a real agent runtime, plus agreement
statistics against the hand-annotated ground truth in ``cases.yaml``.

Why a programmatic approximation instead of a real agent?

Running a real agent to decide "does this skill trigger on this request" is
expensive, non-deterministic, and needs an LLM + tools. For a *benchmark*
that must be re-runnable by anyone in a few seconds with no API key, a
deterministic rule is the honest choice — and it also gives a baseline that
a future agent-based scorer must beat. The approximation is deliberately
simple and its limitations are reported, not hidden.

The rule (see ``_approximate_trigger``):
  1. A request is OUT of scope (no_trigger) if it has no lexical overlap
     with the skill's description / when_to_use / name keywords.
  2. A request is IN scope (trigger) if it overlaps the skill's domain
     keywords above a small threshold.
  3. Otherwise it is borderline.

It does NOT read the skill's steps or examples — only its self-description,
which is exactly what a real agent's trigger matcher keys on.
"""

from __future__ import annotations

import json
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path

import yaml

from skillcard.parser import parse_skill

STOPWORDS = {
    "the", "a", "an", "and", "or", "but", "of", "to", "for", "with", "in",
    "on", "at", "by", "my", "me", "you", "your", "is", "are", "do", "does",
    "this", "that", "it", "what", "how", "when", "why", "can", "could",
    "help", "please", "i", "want", "need", "would", "like", "some", "any",
    "thing", "things", "something", "someone", "stuff",
}

# Generic action words that carry little domain signal on their own. A probe
# matching ONLY one of these against a skill is borderline, not a trigger.
GENERIC_VERBS = {"review", "check", "create", "make", "do", "get", "fix", "write"}


@dataclass
class CaseResult:
    skill: str
    probe: str
    expected: str  # trigger | no_trigger | borderline
    predicted: str  # trigger | no_trigger | borderline
    agreed: bool
    kind: str = ""  # correct | false_positive | false_negative | borderline


@dataclass
class BenchmarkReport:
    total: int = 0
    decided: int = 0  # excludes borderline expected
    agreed: int = 0
    false_positives: list[CaseResult] = field(default_factory=list)
    false_negatives: list[CaseResult] = field(default_factory=list)
    borderline: list[CaseResult] = field(default_factory=list)
    correct: list[CaseResult] = field(default_factory=list)

    @property
    def accuracy(self) -> float:
        if self.decided == 0:
            return 0.0
        return round(100.0 * self.agreed / self.decided, 1)

    @property
    def false_positive_rate(self) -> float:
        neg = sum(1 for r in self.false_positives) + sum(
            1 for c in self.correct if c.expected == "no_trigger"
        )
        if neg == 0:
            return 0.0
        return round(100.0 * len(self.false_positives) / neg, 1)

    @property
    def false_negative_rate(self) -> float:
        pos = sum(1 for r in self.false_negatives) + sum(
            1 for c in self.correct if c.expected == "trigger"
        )
        if pos == 0:
            return 0.0
        return round(100.0 * len(self.false_negatives) / pos, 1)


def _stem(token: str) -> str:
    """Lightweight suffix-strip so 'branch' matches 'branching', 'merge' matches 'merging'."""
    if len(token) <= 4:
        return token
    for suf in ("ing", "ed", "es", "s"):
        if token.endswith(suf) and len(token) - len(suf) >= 3:
            return token[: -len(suf)]
    return token


def _keywords(text: str) -> set[str]:
    """Lowercase, split on non-alphanumerics, drop stopwords and short tokens.

    Two-letter tokens are kept (e.g. "pr", "ai", "ci") because abbreviations
    are common in developer-facing skills.
    """
    tokens = re.findall(r"[a-z0-9]+", text.lower())
    return {_stem(t) for t in tokens if t not in STOPWORDS and len(t) >= 2}


def _domain_keywords(skill) -> set[str]:
    fm = skill.frontmatter
    blob = " ".join(
        str(fm.get(k, ""))
        for k in ("description", "when_to_use", "triggers", "name")
    )
    return _keywords(blob)


def _approximate_trigger(skill, probe: str) -> str:
    """Return 'trigger' | 'no_trigger' | 'borderline' for a probe request.

    Deterministic lexical-overlap rule over the skill's self-description:

    - 2+ shared content words            -> trigger (strong signal)
    - 1 shared *specific* word           -> trigger (domain term is distinctive)
    - 1 shared *generic* verb only       -> borderline (weak signal)
    - 0 shared words                     -> no_trigger
    """
    dom = _domain_keywords(skill)
    probe_kw = _keywords(probe)
    if not dom or not probe_kw:
        return "borderline"
    overlap = dom & probe_kw
    if len(overlap) >= 2:
        return "trigger"
    if len(overlap) == 1:
        word = next(iter(overlap))
        return "borderline" if word in GENERIC_VERBS else "trigger"
    return "no_trigger"


def load_cases(cases_path: Path) -> list[tuple[Path, dict]]:
    data = yaml.safe_load(cases_path.read_text(encoding="utf-8"))
    out = []
    base = cases_path.parent
    for entry in data:
        skill_rel = entry["skill"]
        out.append((base / skill_rel, entry))
    return out


def run_benchmark(cases_path: Path) -> BenchmarkReport:
    report = BenchmarkReport()
    for skill_path, entry in load_cases(cases_path):
        skill = parse_skill(skill_path)
        for case in entry["cases"]:
            expected = case["expected"]
            probe = case["probe"]
            predicted = _approximate_trigger(skill, probe)
            agreed = expected == predicted

            if expected == "borderline":
                kind = "borderline"
                agreed = True  # borderline: either trigger/no_trigger is acceptable
            elif agreed:
                kind = "correct"
            elif expected == "trigger" and predicted == "no_trigger":
                kind = "false_negative"
            elif expected == "no_trigger" and predicted == "trigger":
                kind = "false_positive"
            else:
                kind = "borderline"  # predicted borderline on a decided case

            result = CaseResult(
                skill=str(skill_path),
                probe=probe,
                expected=expected,
                predicted=predicted,
                agreed=agreed,
                kind=kind,
            )
            report.total += 1
            if expected == "borderline":
                report.borderline.append(result)
            elif kind == "correct":
                report.decided += 1
                report.agreed += 1
                report.correct.append(result)
            elif kind == "false_positive":
                report.decided += 1
                report.false_positives.append(result)
            elif kind == "false_negative":
                report.decided += 1
                report.false_negatives.append(result)
            else:
                # predicted borderline on a decided case: count as a miss,
                # but not a clean FP/FN.
                report.decided += 1
                report.borderline.append(result)
    return report


def _short_skill(path: str) -> str:
    """Render a skill path as just its filename for readable reports."""
    return Path(path).name


def render_markdown(report: BenchmarkReport) -> str:
    lines = [
        "# skillcard trigger benchmark",
        "",
        f"- cases: {report.total}",
        f"- decided (non-borderline): {report.decided}",
        f"- agreed: {report.agreed}",
        f"- accuracy: {report.accuracy}%",
        f"- false-positive rate: {report.false_positive_rate}%",
        f"- false-negative rate: {report.false_negative_rate}%",
        "",
        "## Limitations",
        "",
        "This is a programmatic (lexical-overlap) approximation, not a real agent.",
        "It reads only the skill's self-description, ignores steps/examples, and will",
        "miss semantic matches (e.g. 'PR review' vs 'check my code') and multi-step",
        "intents. The sample is deliberately small (a sanity check, not a leaderboard).",
        "Treat these numbers as a baseline a real agent scorer must beat, not as a",
        "claim about real-world trigger accuracy.",
        "",
    ]
    if report.false_positives:
        lines.append("## False positives (predicted trigger, expected no_trigger)")
        lines.append("")
        for r in report.false_positives:
            lines.append(f"- `{r.probe}` -> {_short_skill(r.skill)}")
        lines.append("")
    if report.false_negatives:
        lines.append("## False negatives (predicted no_trigger, expected trigger)")
        lines.append("")
        for r in report.false_negatives:
            lines.append(f"- `{r.probe}` -> {_short_skill(r.skill)}")
        lines.append("")
    if report.borderline:
        lines.append("## Borderline / skipped")
        lines.append("")
        for r in report.borderline:
            lines.append(f"- `{r.probe}` (expected {r.expected}, predicted {r.predicted})")
        lines.append("")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    here = Path(__file__).resolve().parent
    cases_path = here / "cases.yaml"
    report = run_benchmark(cases_path)

    out = render_markdown(report)
    print(out)

    # Persist both a human-readable report and machine-readable metrics, so
    # the benchmark is re-runnable and diffable in CI.
    (here / "report.md").write_text(out + "\n", encoding="utf-8")
    (here / "report.json").write_text(
        json.dumps(
            {
                "total": report.total,
                "decided": report.decided,
                "agreed": report.agreed,
                "accuracy": report.accuracy,
                "false_positive_rate": report.false_positive_rate,
                "false_negative_rate": report.false_negative_rate,
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    print(f"\nreports written to {here / 'report.md'} and {here / 'report.json'}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
