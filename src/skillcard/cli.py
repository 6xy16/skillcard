"""skillcard CLI.

Usage:
    skillcard path/to/SKILL.md [--out ./skillcard-report] [--no-llm] [--json]
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from skillcard import EVAL_VERSION, __version__
from skillcard.badge import render_badge
from skillcard.card import render_card
from skillcard.l1_structure import l1_score, run_l1
from skillcard.l2_judge import JudgeConfig, run_l2
from skillcard.l3_injection import scan_injection
from skillcard.models import Dimension, EvalResult
from skillcard.parser import parse_skill


def evaluate(path: str, use_llm: bool = True) -> EvalResult:
    doc = parse_skill(path)
    result = EvalResult(path=str(path), skill_name=doc.name, eval_version=EVAL_VERSION)

    # L1 - deterministic structure
    result.checks = run_l1(doc)
    result.dimensions.append(
        Dimension(key="structure", label="Structure", score=l1_score(result.checks))
    )

    # L2 - LLM paper review (optional)
    judge_cfg = JudgeConfig.from_env() if use_llm else None
    l2_warnings: list[str] = []
    if judge_cfg:
        l2 = run_l2(doc, judge_cfg)
        if l2:
            result.judge_model = l2.model
            result.judge_prompt_hash = l2.prompt_hash
            l2_warnings = list(l2.warnings)
            labels = {
                "trigger_accuracy": "Trigger accuracy",
                "boundary_robustness": "Boundary robustness",
                "instruction_clarity": "Instruction clarity",
                "output_verifiability": "Output verifiability",
            }
            scores = {
                "trigger_accuracy": l2.trigger_accuracy,
                "boundary_robustness": l2.boundary_robustness,
                "instruction_clarity": l2.instruction_clarity,
                "output_verifiability": l2.output_verifiability,
            }
            for key, label in labels.items():
                result.dimensions.append(
                    Dimension(key=key, label=label, score=float(scores[key]))
                )
            if l2.rationale:
                result.warnings.append(f"judge rationale: {l2.rationale}")
            if l2.ambiguous:
                result.warnings.append(f"ambiguous probe ids: {l2.ambiguous}")
        else:
            # L2 was configured but failed; treat as skipped with a warning.
            for key, label in [
                ("trigger_accuracy", "Trigger accuracy"),
                ("boundary_robustness", "Boundary robustness"),
                ("instruction_clarity", "Instruction clarity"),
                ("output_verifiability", "Output verifiability"),
            ]:
                result.dimensions.append(Dimension(key=key, label=label, score=None))
            result.warnings.append("L2 LLM review failed; falling back to structure-only score")
    else:
        for key, label in [
            ("trigger_accuracy", "Trigger accuracy"),
            ("boundary_robustness", "Boundary robustness"),
            ("instruction_clarity", "Instruction clarity"),
            ("output_verifiability", "Output verifiability"),
        ]:
            result.dimensions.append(Dimension(key=key, label=label, score=None))
        if use_llm:
            result.warnings.append(
                "SKILLCARD_API_KEY not set; L2 LLM review skipped (structure-only score)"
            )

    # Surface any L2-internal warnings (probe generation issues, etc.)
    result.warnings.extend(l2_warnings)

    # L3 - injection scan (security gate, not a scored dimension)
    injection = scan_injection(doc)
    result.injection_hits = injection.hits
    if injection.hits:
        result.warnings.append("injection patterns found: " + "; ".join(injection.hits))
    for why in injection.soft_warnings:
        result.warnings.append(f"possible injection wording (review): {why}")

    return result.finalize()


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        prog="skillcard",
        description="Generate a quality score card and badge for an Agent Skill (SKILL.md).",
    )
    ap.add_argument("skill", help="path to a SKILL.md file")
    ap.add_argument("--out", default="skillcard-report", help="output directory")
    ap.add_argument("--no-llm", action="store_true", help="skip LLM paper review (L2)")
    ap.add_argument("--json", action="store_true", help="print JSON result to stdout")
    ap.add_argument("--version", action="version", version=f"skillcard {__version__}")
    args = ap.parse_args(argv)

    if not Path(args.skill).is_file():
        ap.error(f"file not found: {args.skill}")

    result = evaluate(args.skill, use_llm=not args.no_llm)

    out_dir = Path(args.out)
    card_path = render_card(result, out_dir / "card.png")
    badge_path = render_badge(result, out_dir / "badge.svg")
    json_path = out_dir / "result.json"
    json_path.write_text(json.dumps(result.to_dict(), indent=2, ensure_ascii=False), "utf-8")

    if args.json:
        print(json.dumps(result.to_dict(), indent=2, ensure_ascii=False))
    else:
        print(f"Grade: {result.grade}  ({result.total_score}/100)")
        for dim in result.dimensions:
            s = f"{dim.score:.0f}" if dim.score is not None else "n/a"
            print(f"  {dim.label:<22} {s}")
        n_hits = len(result.injection_hits)
        security = "clean" if n_hits == 0 else f"{n_hits} pattern(s) found"
        print(f"  {'Security':<22} {security}")

        # Improvement suggestions: list failed checks sorted by lost points.
        failed = [c for c in result.checks if not c.passed and c.suggestion]
        failed.sort(key=lambda c: -c.weight)
        if failed:
            total_potential = sum(c.weight for c in failed)
            print(f"\nHow to improve (+{total_potential} potential):")
            for c in failed:
                print(f"  [-{c.weight}] {c.name}: {c.message}")
                for line in c.suggestion.split("\n"):
                    print(f"        {line}")
            print("\n  Run skillcard again after fixing to see your score improve.")

        for warn in result.warnings:
            print(f"  ! {warn}", file=sys.stderr)
        print(f"\ncard:  {card_path}")
        print(f"badge: {badge_path}")
        print(f"json:  {json_path}")
        badge_rel = Path(badge_path).as_posix()
        print("\nEmbed in README:\n" f"  ![skill score]({badge_rel})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
