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
from skillcard.cache import run_l2_cached
from skillcard.card import render_card
from skillcard.l1_structure import l1_score, run_l1
from skillcard.l2_judge import JudgeConfig, run_l2
from skillcard.l3_injection import scan_injection
from skillcard.l4_execution import run_l4
from skillcard.models import Dimension, EvalResult
from skillcard.parser import parse_skill


def evaluate(path: str, use_llm: bool = True, run: bool = False, use_cache: bool = True) -> EvalResult:
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
        # Serve from the disk cache when enabled so an unchanged skill is
        # re-scored for free and bit-stably.
        l2 = run_l2_cached(doc, judge_cfg) if use_cache else run_l2(doc, judge_cfg)
        if l2:
            result.judge_model = l2.model
            result.judge_prompt_hash = l2.prompt_hash
            result.judge_duration_seconds = l2.duration_seconds
            result.judge_prompt_tokens = l2.prompt_tokens
            result.judge_completion_tokens = l2.completion_tokens
            result.judge_total_tokens = l2.total_tokens
            result.judge_retries = l2.retries
            result.judge_base_url = l2.base_url
            result.judge_timeout = l2.timeout
            result.judge_probe_prompt_hash = l2.probe_prompt_hash
            result.judge_probes = list(l2.probes)
            result.judge_raw_verdict = l2.raw_verdict
            l2_warnings = list(l2.warnings)
            if l2.from_cache:
                l2_warnings.append("L2 verdict served from cache (unchanged skill)")
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
                # A dimension can be None (n/a) when the judge didn't score it
                # or probes were unavailable; never coerce it to a fake 0.
                result.dimensions.append(
                    Dimension(key=key, label=label, score=scores[key])
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

    # L4 - dynamic execution (optional, OFF by default: runs the skill's code)
    if run:
        exec_res = run_l4(doc)
        result.run_executed = exec_res.ran
        result.run_runtime = exec_res.runtime
        result.run_completed = exec_res.completed
        result.run_exit_code = exec_res.exit_code
        result.run_timed_out = exec_res.timed_out
        result.run_duration_seconds = exec_res.duration_seconds
        result.run_stdout = exec_res.stdout
        result.run_stderr = exec_res.stderr
        result.run_truncated = exec_res.truncated
        result.run_command = list(exec_res.command)
        for w in exec_res.warnings:
            result.warnings.append(f"L4 execution: {w}")

    # L3 - injection scan (security gate, not a scored dimension)
    injection = scan_injection(doc)
    result.injection_hits = injection.hits
    if injection.hits:
        result.warnings.append("injection patterns found: " + "; ".join(injection.hits))
    for why in injection.soft_warnings:
        result.warnings.append(f"possible injection wording (review): {why}")

    return result.finalize()


def _render_single(result: EvalResult, card_path: str, badge_path: str, json_path: str) -> None:
    print(f"Grade: {result.grade}  ({result.total_score}/100)")
    for dim in result.dimensions:
        s = f"{dim.score:.0f}" if dim.score is not None else "n/a"
        print(f"  {dim.label:<22} {s}")
    n_hits = len(result.injection_hits)
    security = "clean" if n_hits == 0 else f"{n_hits} pattern(s) found"
    print(f"  {'Security':<22} {security}")

    if result.run_executed:
        status = "completed" if result.run_completed else (
            "timed out" if result.run_timed_out else f"exit {result.run_exit_code}"
        )
        print(f"  {'Execution':<22} {status} ({result.run_duration_seconds}s)")

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
    print("\nEmbed in README:\n" f"  ![skill score]({Path(badge_path).as_posix()})")


def _cmd_single(args) -> int:
    if not Path(args.skill).is_file():
        raise SystemExit(f"file not found: {args.skill}")

    result = evaluate(args.skill, use_llm=not args.no_llm, run=args.run, use_cache=not args.no_cache)

    out_dir = Path(args.out)
    card_path = render_card(result, out_dir / "card.png")
    badge_path = render_badge(result, out_dir / "badge.svg")
    json_path = out_dir / "result.json"
    json_path.write_text(json.dumps(result.to_dict(), indent=2, ensure_ascii=False), "utf-8")

    if args.json:
        print(json.dumps(result.to_dict(), indent=2, ensure_ascii=False))
    else:
        _render_single(result, str(card_path), str(badge_path), str(json_path))
    return 0


def _cmd_batch(args) -> int:
    from skillcard.batch import evaluate_all

    snapshot = evaluate_all(args.directory, use_llm=not args.no_llm, run=args.run, use_cache=not args.no_cache)
    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)
    for path, result in snapshot.items():
        safe = path.replace("/", "__").replace("\\", "__")
        data = result.to_dict()
        # Preserve the stable relative key so `skillcard diff` can align
        # before/after snapshots even though result.path is absolute.
        data["key"] = path
        (out_dir / f"{safe}.json").write_text(
            json.dumps(data, indent=2, ensure_ascii=False), "utf-8"
        )

    # Print a summary table.
    print(f"{len(snapshot)} skills evaluated:")
    for path, result in sorted(snapshot.items()):
        print(f"  {result.grade}  {result.total_score:>5}  {path}")

    # A single-snapshot "diff" against nothing is just the summary, but if the
    # user also wants a diff they run `skillcard diff`.
    summary_path = out_dir / "summary.json"
    summary_path.write_text(
        json.dumps({p: r.grade for p, r in snapshot.items()}, indent=2, ensure_ascii=False),
        "utf-8",
    )
    print(f"\nper-skill results and summary written to {out_dir}")
    return 0


def _load_snapshot(directory: str) -> dict[str, EvalResult]:
    """Load a snapshot of EvalResult JSONs written by `skillcard batch`."""
    from skillcard.models import EvalResult as ER

    snap: dict[str, EvalResult] = {}
    root = Path(directory)
    for p in sorted(root.glob("*.json")):
        if p.name == "summary.json":
            continue
        data = json.loads(p.read_text(encoding="utf-8"))
        # Prefer the stable `key` written by `skillcard batch`; fall back to
        # the stored path when reading hand-made snapshots.
        path_key = data.get("key") or data.get("path", p.stem.replace("__", "/"))
        # Rebuild a minimal EvalResult carrying the fields diff needs.
        r = ER(path=path_key)
        r.skill_name = data.get("skill_name", "")
        r.total_score = data.get("total_score", 0.0)
        r.grade = data.get("grade", "F")
        r.judge_total_tokens = data.get("judge_total_tokens")
        from skillcard.models import Check, Dimension

        r.dimensions = [Dimension(**d) for d in data.get("dimensions", [])]
        r.checks = [Check(**c) for c in data.get("checks", [])]
        snap[path_key] = r
    return snap


def _cmd_diff(args) -> int:
    from skillcard.batch import diff_results, render_diff

    before = _load_snapshot(args.before)
    after = _load_snapshot(args.after)
    report = diff_results(before, after)
    print(render_diff(report))
    return 0


def _cmd_stability(args) -> int:
    from skillcard.l2_judge import JudgeConfig
    from skillcard.parser import parse_skill
    from skillcard.stability import measure_stability, render_stability

    if not Path(args.skill).is_file():
        raise SystemExit(f"file not found: {args.skill}")

    doc = parse_skill(args.skill)
    config = JudgeConfig.from_env()
    if config is None:
        print("SKILLCARD_API_KEY not set; stability requires L2 (LLM judge).", file=sys.stderr)
        return 2
    report = measure_stability(doc, config, runs=args.runs)
    print(render_stability(report))
    return 0


def main(argv: list[str] | None = None) -> int:
    if argv is None:
        argv = sys.argv[1:]

    # Handle --version / --help / bare invocation before command routing.
    if argv and argv[0] in ("--version", "-V"):
        print(f"skillcard {__version__}")
        return 0

    ap = argparse.ArgumentParser(
        prog="skillcard",
        description="Generate a quality score card and badge for an Agent Skill (SKILL.md).",
    )
    sub = ap.add_subparsers(dest="command")

    # Default command: evaluate a single SKILL.md.
    p_single = sub.add_parser("score", help="evaluate a single SKILL.md (default)")
    p_single.add_argument("skill", help="path to a SKILL.md file")
    p_single.add_argument("--out", default="skillcard-report", help="output directory")
    p_single.add_argument("--no-llm", action="store_true", help="skip LLM paper review (L2)")
    p_single.add_argument("--run", action="store_true", help="execute the skill's steps (L4, unsafe)")
    p_single.add_argument("--no-cache", action="store_true", help="bypass the L2 disk cache")
    p_single.add_argument("--json", action="store_true", help="print JSON result to stdout")
    p_single.set_defaults(func=_cmd_single)

    # Batch: evaluate a directory of skills.
    p_batch = sub.add_parser("batch", help="evaluate every SKILL.md under a directory")
    p_batch.add_argument("directory", help="directory to scan for SKILL.md files")
    p_batch.add_argument("--out", default="skillcard-batch", help="output directory")
    p_batch.add_argument("--no-llm", action="store_true", help="skip LLM paper review (L2)")
    p_batch.add_argument("--run", action="store_true", help="execute each skill's steps (L4, unsafe)")
    p_batch.add_argument("--no-cache", action="store_true", help="bypass the L2 disk cache")
    p_batch.set_defaults(func=_cmd_batch)

    # Diff: compare two batch snapshots.
    p_diff = sub.add_parser("diff", help="compare two batch snapshots (before/after)")
    p_diff.add_argument("before", help="directory of 'before' result JSONs")
    p_diff.add_argument("after", help="directory of 'after' result JSONs")
    p_diff.set_defaults(func=_cmd_diff)

    # Stability: re-run L2 N times and report score variation.
    p_stab = sub.add_parser("stability", help="measure LLM judge score variation")
    p_stab.add_argument("skill", help="path to a SKILL.md file")
    p_stab.add_argument("--runs", type=int, default=3, help="number of uncached L2 runs")
    p_stab.set_defaults(func=_cmd_stability)

    # Backward compatibility: `skillcard file.md ...` (no subcommand) routes to
    # the single-file command, preserving the original positional CLI.
    if argv and argv[0] not in ("score", "batch", "diff", "stability", "-h", "--help"):
        # Rebuild a single-file namespace from the legacy positional form.
        ap_single = argparse.ArgumentParser(add_help=False)
        ap_single.add_argument("skill")
        ap_single.add_argument("--out", default="skillcard-report")
        ap_single.add_argument("--no-llm", action="store_true")
        ap_single.add_argument("--run", action="store_true")
        ap_single.add_argument("--no-cache", action="store_true")
        ap_single.add_argument("--json", action="store_true")
        args = ap_single.parse_args(argv)
        return _cmd_single(args)

    args = ap.parse_args(argv)
    if getattr(args, "func", None) is None:
        ap.print_help()
        return 2
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
