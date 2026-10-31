"""Tests for the programmatic trigger benchmark.

These cover the deterministic approximation rule and the agreement
statistics, not a real agent. They must stay fast and offline.
"""

from __future__ import annotations

import sys
from pathlib import Path

from skillcard.parser import parse_skill_text

# Make benchmarks importable (it lives outside src/).
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "benchmarks"))

from benchmark import (
    _approximate_trigger,
    _keywords,
    _stem,
    run_benchmark,
)


def _skill(description: str) -> object:
    return parse_skill_text(
        f"---\nname: code-reviewer\ndescription: {description}\n---\nbody",
        path="SKILL.md",
    )


def test_stem_strips_suffixes():
    assert _stem("branching") == "branch"
    assert _stem("merging") == "merg"
    assert _stem("commit") == "commit"  # too short to strip 's'


def test_keywords_drops_stopwords_and_short_tokens():
    kw = _keywords("help me to create a branch")
    assert "help" not in kw
    assert "me" not in kw
    assert "to" not in kw
    assert "create" in kw
    assert "branch" in kw


def test_trigger_on_two_shared_words():
    skill = _skill("Review a pull request for code quality and security issues.")
    assert _approximate_trigger(skill, "review this pull request for bugs") == "trigger"


def test_trigger_on_one_specific_word():
    skill = _skill("Review a pull request for code quality and security issues.")
    assert _approximate_trigger(skill, "audit the security of this diff") == "trigger"


def test_no_trigger_on_zero_overlap():
    skill = _skill("Review a pull request for code quality and security issues.")
    assert _approximate_trigger(skill, "write me a poem about the ocean") == "no_trigger"


def test_borderline_on_generic_verb_only():
    skill = _skill("Review a pull request for code quality and security issues.")
    # "review" is a generic verb; alone it is a weak signal.
    assert _approximate_trigger(skill, "review my work") == "borderline"


def test_run_benchmark_reads_cases_file():
    cases_path = Path(__file__).resolve().parent.parent / "benchmarks" / "cases.yaml"
    report = run_benchmark(cases_path)
    assert report.total >= 10
    assert report.decided > 0
    assert 0 <= report.accuracy <= 100
    assert 0 <= report.false_positive_rate <= 100
    assert 0 <= report.false_negative_rate <= 100
