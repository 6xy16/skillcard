"""Tests for the L2 cache and stability experiment."""

from __future__ import annotations

from skillcard.cache import cache_key, run_l2_cached
from skillcard.l2_judge import JudgeConfig, L2Result
from skillcard.parser import SkillDoc
from skillcard.stability import measure_stability, render_stability


def _cfg() -> JudgeConfig:
    return JudgeConfig(api_key="k", model="gpt-4o-mini")


def _doc(text: str = "---\nname: t\ndescription: x\n---\nbody") -> SkillDoc:
    from skillcard.parser import parse_skill_text

    return parse_skill_text(text, path="SKILL.md")


def test_cache_key_changes_with_skill_text():
    a = _doc("---\nname: a\ndescription: x\n---\nbody")
    b = _doc("---\nname: a\ndescription: x\n---\ndifferent body")
    assert cache_key(a, _cfg()) != cache_key(b, _cfg())


def test_cache_key_changes_with_model():
    doc = _doc()
    c1 = _cfg()
    c2 = JudgeConfig(api_key="k", model="different-model")
    assert cache_key(doc, c1) != cache_key(doc, c2)


def test_cache_key_stable_for_same_input():
    doc = _doc()
    assert cache_key(doc, _cfg()) == cache_key(doc, _cfg())


def test_run_l2_cached_hit_skips_llm(monkeypatch, tmp_path):
    doc = _doc()
    calls = {"n": 0}

    def fake_run_l2(doc, config):
        calls["n"] += 1
        return L2Result(
            trigger_accuracy=85,
            boundary_robustness=70,
            instruction_clarity=90,
            output_verifiability=80,
        )

    monkeypatch.setattr("skillcard.cache.run_l2", fake_run_l2)
    first = run_l2_cached(doc, _cfg(), cache_dir=tmp_path)
    second = run_l2_cached(doc, _cfg(), cache_dir=tmp_path)

    assert calls["n"] == 1  # second call served from cache
    assert first.from_cache is False
    assert second.from_cache is True
    assert second.trigger_accuracy == 85  # cached scores round-trip


def test_run_l2_cached_none_config_returns_none():
    assert run_l2_cached(_doc(), None) is None


def test_run_l2_cached_preserves_na_dimensions(monkeypatch, tmp_path):
    doc = _doc()

    def fake_run_l2(doc, config):
        return L2Result(trigger_accuracy=None, instruction_clarity=90)

    monkeypatch.setattr("skillcard.cache.run_l2", fake_run_l2)
    run_l2_cached(doc, _cfg(), cache_dir=tmp_path)
    cached = run_l2_cached(doc, _cfg(), cache_dir=tmp_path)
    assert cached.trigger_accuracy is None  # n/a survives JSON round-trip
    assert cached.instruction_clarity == 90


def test_measure_stability_aggregates_scores(monkeypatch):
    doc = _doc()
    # Simulate three runs with slightly different scores.
    results = [
        L2Result(trigger_accuracy=84.0, boundary_robustness=70.0,
                 instruction_clarity=90.0, output_verifiability=80.0, total_tokens=100),
        L2Result(trigger_accuracy=86.0, boundary_robustness=70.0,
                 instruction_clarity=90.0, output_verifiability=80.0, total_tokens=102),
        L2Result(trigger_accuracy=85.0, boundary_robustness=71.0,
                 instruction_clarity=89.0, output_verifiability=80.0, total_tokens=101),
    ]
    it = iter(results)

    def fake_run_l2(doc, config):
        return next(it)

    monkeypatch.setattr("skillcard.stability.run_l2", fake_run_l2)
    report = measure_stability(doc, _cfg(), runs=3)

    assert report.successful == 3
    ts = report.dimensions["trigger_accuracy"]
    assert ts.mean is not None
    assert abs(ts.mean - 85.0) < 0.01
    assert ts.min == 84.0
    assert ts.max == 86.0
    assert ts.stddev is not None and ts.stddev > 0
    # Token spread across runs.
    tmin, tmax, _tmean = report.token_spread
    assert tmin == 100
    assert tmax == 102


def test_measure_stability_handles_failures(monkeypatch):
    doc = _doc()
    seq = [None, L2Result(trigger_accuracy=80.0)]

    def fake_run_l2(doc, config):
        return seq.pop(0)

    monkeypatch.setattr("skillcard.stability.run_l2", fake_run_l2)
    report = measure_stability(doc, _cfg(), runs=2)
    assert report.successful == 1
    assert len(report.failures) == 1


def test_measure_stability_no_config_is_empty():
    report = measure_stability(_doc(), None, runs=3)
    assert report.runs == 3
    assert report.successful == 0


def test_render_stability_outputs_rows():
    from skillcard.stability import StabilityReport

    r = StabilityReport(skill="t", model="m", runs=1, successful=1)
    out = render_stability(r)
    assert "t" in out
    assert "model: m" in out
