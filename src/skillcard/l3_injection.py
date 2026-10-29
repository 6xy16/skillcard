"""L3: prompt-injection / judge-gaming detection.

Skills that try to sweet-talk the evaluator get penalized. This matters
once scores become social currency - and they will.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from skillcard.parser import SkillDoc

PATTERNS = [
    (r"ignore (all |any |the )?(previous|prior|above) instructions", "classic instruction override"),
    (r"you are (now )?(a|an) [^\n]{0,60} (judge|evaluator|reviewer)", "attempts to redefine judge role"),
    (r"(give|assign|award)[^\n.]{0,50}(perfect|full|top|high|100|hundred)[^\n.]{0,30}(score|rating|grade)", "directly begs for a high score"),
    (r"score of (100|a hundred)", "demands a specific score"),
    (r"(do not|don't) (penalize|deduct|lower|mark down)", "tries to suppress penalties"),
    (r"<\s*(system|instructions?)\s*>", "hidden markup-style instruction block"),
    (r"as an ai (assistant|model).{0,40}(must|should) (reward|favor|give high)", "manipulates AI behavior"),
    # Narrowed: only flag references to the *evaluator's* system prompt / eval pipeline,
    # not generic mentions of "system prompt" as a concept being taught to users.
    (r"(the|this|our|your) (evaluation|grading|scoring|judge) (prompt|pipeline|system|rubric)", "references the evaluation pipeline"),
    (r"(ignore|disregard|bypass).{0,20}(system|your) prompt", "attempts to override evaluator system prompt"),
]


@dataclass
class InjectionReport:
    hits: list[str] = field(default_factory=list)

    @property
    def score(self) -> float:
        # Start at 100, each hit costs 25, floor at 0.
        return max(0.0, 100.0 - 25.0 * len(self.hits))

    @property
    def clean(self) -> bool:
        return not self.hits


def scan_injection(doc: SkillDoc) -> InjectionReport:
    report = InjectionReport()
    for pattern, why in PATTERNS:
        if re.search(pattern, doc.raw, re.IGNORECASE):
            report.hits.append(why)
    return report
