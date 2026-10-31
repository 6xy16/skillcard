"""Tests for batch evaluation and version diff."""

from __future__ import annotations

from skillcard.batch import DiffEntry, diff_results, evaluate_all, find_skills
from skillcard.models import Check, Dimension, EvalResult


def _result(score: float, failed_checks: int = 0, tokens: int | None = None) -> EvalResult:
    r = EvalResult(path="SKILL.md", skill_name="t")
    r.dimensions.append(Dimension(key="structure", label="Structure", score=score))
    r.total_score = score
    r.grade = "A" if score >= 90 else "B"
    r.checks = [
        Check(name=f"c{i}", passed=(i >= failed_checks), weight=10)
        for i in range(5)
    ]
    r.judge_total_tokens = tokens
    return r


def test_find_skills_recurses(tmp_path):
    (tmp_path / "a").mkdir()
    (tmp_path / "b").mkdir()
    (tmp_path / "a" / "SKILL.md").write_text("---\nname: a\ndescription: x\n---\nbody")
    (tmp_path / "b" / "skill.md").write_text("---\nname: b\ndescription: x\n---\nbody")
    (tmp_path / "README.md").write_text("not a skill")
    found = find_skills(tmp_path)
    assert len(found) == 2
    assert all(p.name in ("SKILL.md", "skill.md") for p in found)


def test_find_skills_empty_for_non_dir(tmp_path):
    assert find_skills(tmp_path / "does-not-exist") == []


def test_evaluate_all_returns_snapshot(tmp_path):
    (tmp_path / "SKILL.md").write_text(
        "---\nname: t\ndescription: A sufficiently detailed test skill description here.\n---\n"
        "# T\n\n## Steps\n\n1. Do a thing.\n"
    )
    snapshot = evaluate_all(tmp_path, use_llm=False)
    assert "SKILL.md" in snapshot
    assert snapshot["SKILL.md"].grade in ("A", "B", "C", "D", "F")


def test_diff_detects_improvement_and_regression():
    before = {"a": _result(80.0, failed_checks=2), "b": _result(95.0)}
    after = {"a": _result(95.0, failed_checks=0), "b": _result(85.0)}
    report = diff_results(before, after)
    assert len(report.entries) == 2
    # Regressions sort first (most negative score_delta).
    assert report.entries[0].path == "b"
    assert report.entries[0].score_delta == -10.0
    assert report.entries[1].path == "a"
    assert report.entries[1].score_delta == 15.0


def test_diff_detects_added_and_removed():
    before = {"a": _result(80.0)}
    after = {"a": _result(80.0), "b": _result(90.0)}
    report = diff_results(before, after)
    assert len(report.added) == 1
    assert report.added[0].path == "b"
    assert report.added[0].status == "added"

    report2 = diff_results(after, before)
    assert len(report2.removed) == 1
    assert report2.removed[0].path == "b"


def test_diff_entry_cost_delta():
    before = {"a": _result(80.0, tokens=1200)}
    after = {"a": _result(80.0, tokens=900)}
    report = diff_results(before, after)
    assert report.entries[0].cost_delta == -300


def test_diff_entry_grade_delta():
    e = DiffEntry(path="x", before=_result(85.0), after=_result(95.0))
    assert e.grade_delta == "B → A"
    e2 = DiffEntry(path="x", before=_result(95.0), after=_result(95.0))
    assert e2.grade_delta == "A"
    e3 = DiffEntry(path="x", before=None, after=_result(95.0))
    assert e3.grade_delta == "- → A"
