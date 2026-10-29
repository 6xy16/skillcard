"""L3: prompt-injection / judge-gaming detection.

Skills that try to sweet-talk the evaluator get penalized. This matters
once scores become social currency - and they will.

Findings are split into two severities so the security gate doesn't false-fire
on skills that merely *quote* a single injection string as a teaching example:

- ``hard``: unambiguous judge-gaming intent -> caps the grade (security gate).
- ``soft``: suspicious wording that could be legitimate (e.g. a security-tutorial
  skill quoting "ignore previous instructions" once as a counter-example) ->
  warning only, no grade penalty.

Classification rule (context-aware):

1. A phrase in the frontmatter ``description`` (the skill's own self-description)
   is always ``hard`` — self-description has no legitimate reason to contain
   attack instructions.
2. A phrase in the body is ``hard`` when several patterns fire together (a real
   attack stacks multiple overrides). A lone body match is ``soft`` — likely a
   quoted example in a security tutorial.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from skillcard.parser import SkillDoc


@dataclass(frozen=True)
class Pattern:
    regex: str
    reason: str


PATTERNS: list[Pattern] = [
    Pattern(
        r"ignore (all |any |the )?(previous|prior|above) instructions",
        "classic instruction override",
    ),
    Pattern(
        r"you are (now )?(a|an) [^\n]{0,60} (judge|evaluator|reviewer)",
        "attempts to redefine judge role",
    ),
    Pattern(
        r"score of (100|a hundred)",
        "demands a specific score",
    ),
    Pattern(
        r"(do not|don't) (penalize|deduct|lower|mark down)",
        "tries to suppress penalties",
    ),
    Pattern(
        r"(ignore|disregard|bypass).{0,20}(system|your) prompt",
        "attempts to override evaluator system prompt",
    ),
    Pattern(
        r"(give|assign|award)[^\n.]{0,50}(perfect|full|top|high|100|hundred)[^\n.]{0,30}(score|rating|grade)",
        "directly begs for a high score",
    ),
    Pattern(r"<\s*(system|instructions?)\s*>", "hidden markup-style instruction block"),
    Pattern(
        r"as an ai (assistant|model).{0,40}(must|should) (reward|favor|give high)",
        "manipulates AI behavior",
    ),
    Pattern(
        r"(the|this|our|your) (evaluation|grading|scoring|judge) (prompt|pipeline|system|rubric)",
        "references the evaluation pipeline",
    ),
]


@dataclass
class InjectionFinding:
    reason: str
    severity: str  # "hard" | "soft"


@dataclass
class InjectionReport:
    findings: list[InjectionFinding] = field(default_factory=list)

    @property
    def hits(self) -> list[str]:
        """Backwards-compatible list of hard-hit reasons (drives the grade gate)."""
        return [f.reason for f in self.findings if f.severity == "hard"]

    @property
    def soft_warnings(self) -> list[str]:
        """Reasons for soft (non-gating) findings."""
        return [f.reason for f in self.findings if f.severity == "soft"]


def scan_injection(doc: SkillDoc) -> InjectionReport:
    description_hits: list[str] = []
    body_hits: list[str] = []

    for pattern in PATTERNS:
        if re.search(pattern.regex, doc.description, re.IGNORECASE):
            description_hits.append(pattern.reason)
        elif re.search(pattern.regex, doc.body, re.IGNORECASE):
            body_hits.append(pattern.reason)

    report = InjectionReport()
    for reason in description_hits:
        report.findings.append(InjectionFinding(reason=reason, severity="hard"))
    for reason in body_hits:
        # A lone body match is a likely quote/example; a cluster of them is a real attack.
        severity = "hard" if len(body_hits) > 1 else "soft"
        report.findings.append(InjectionFinding(reason=reason, severity=severity))
    return report
