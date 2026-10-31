"""Stability experiment: how much does the LLM judge's score move?

LLM judging is non-deterministic — even with temperature=0, providers may
return slightly different scores across runs (different sampling, internal
nondeterminism, or a retry hitting a different backend). Before you trust a
score, you should know how much it *wiggles*.

This module re-runs L2 on the same skill N times (bypassing the cache, since
the whole point is to observe variation) and reports, per dimension, the
min / max / mean / stddev of the scores, plus the spread of total score and
token cost.

Interpreting the result:

- A small stddev (a few points) means the score is stable — the grade is a
  reliable signal.
- A large stddev means the judge is noisy for this skill; a single score is
  not trustworthy, and you should average several runs or treat the grade as
  approximate.
"""

from __future__ import annotations

import statistics
from dataclasses import dataclass, field

from skillcard.l2_judge import JudgeConfig, run_l2
from skillcard.parser import SkillDoc

# The four scored dimensions, in card order.
DIMENSIONS = (
    "trigger_accuracy",
    "boundary_robustness",
    "instruction_clarity",
    "output_verifiability",
)


@dataclass
class DimensionStats:
    """Aggregated scores for one dimension across N runs."""

    key: str
    runs: int = 0
    min: float | None = None
    max: float | None = None
    mean: float | None = None
    stddev: float | None = None
    values: list[float] = field(default_factory=list)


@dataclass
class StabilityReport:
    """Result of re-evaluating one skill N times."""

    skill: str
    model: str
    runs: int
    successful: int
    dimensions: dict[str, DimensionStats] = field(default_factory=dict)
    total_tokens: list[int] = field(default_factory=list)
    total_seconds: list[float] = field(default_factory=list)
    failures: list[str] = field(default_factory=list)

    @property
    def token_spread(self) -> tuple[int, int, float]:
        """(min, max, mean) of total tokens across runs."""
        if not self.total_tokens:
            return (0, 0, 0.0)
        return (min(self.total_tokens), max(self.total_tokens), statistics.mean(self.total_tokens))

    @property
    def latency_mean(self) -> float:
        return statistics.mean(self.total_seconds) if self.total_seconds else 0.0


def _stats(values: list[float]) -> tuple[float | None, float | None, float | None, float | None]:
    if not values:
        return (None, None, None, None)
    mean = statistics.mean(values)
    std = statistics.stdev(values) if len(values) >= 2 else 0.0
    return (min(values), max(values), mean, std)


def measure_stability(
    doc: SkillDoc,
    config: JudgeConfig | None,
    runs: int = 3,
) -> StabilityReport:
    """Run L2 ``runs`` times (uncached) and aggregate score variation.

    ``config=None`` yields an empty report (L2 disabled). A run that returns
    ``None`` (judge failed) is recorded as a failure and excluded from stats.
    """
    report = StabilityReport(
        skill=doc.name or str(doc.path),
        model=config.model if config else "",
        runs=runs,
        successful=0,
    )
    if config is None or runs <= 0:
        return report

    collected: dict[str, list[float]] = {d: [] for d in DIMENSIONS}
    for _ in range(runs):
        result = run_l2(doc, config)
        if result is None:
            report.failures.append("judge returned no result")
            continue
        report.successful += 1
        report.total_tokens.append(result.total_tokens)
        report.total_seconds.append(result.duration_seconds)
        for d in DIMENSIONS:
            val = getattr(result, d)
            if val is not None:
                collected[d].append(float(val))

    for d in DIMENSIONS:
        vals = collected[d]
        mn, mx, mean, std = _stats(vals)
        report.dimensions[d] = DimensionStats(
            key=d, runs=len(vals), min=mn, max=mx, mean=mean, stddev=std, values=vals
        )
    return report


def render_stability(report: StabilityReport) -> str:
    lines = [
        f"Stability: {report.skill}  (model: {report.model or 'n/a'})",
        f"runs: {report.runs}, successful: {report.successful}",
        "",
    ]
    for key, ds in report.dimensions.items():
        if ds.runs == 0:
            lines.append(f"  {key:<22} n/a")
            continue
        std = f"±{ds.stddev:.1f}" if ds.stddev is not None else ""
        lines.append(
            f"  {key:<22} mean={ds.mean:.1f} {std}  range=[{ds.min:.0f}, {ds.max:.0f}]  (n={ds.runs})"
        )
    tmin, tmax, tmean = report.token_spread
    lines.append("")
    lines.append(f"  tokens/run:  mean={tmean:.0f}  range=[{tmin}, {tmax}]")
    lines.append(f"  latency/run: mean={report.latency_mean:.2f}s")
    if report.failures:
        lines.append("")
        lines.append(f"  failures: {len(report.failures)}")
    return "\n".join(lines)
