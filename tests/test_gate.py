"""Tests for the security gate logic."""

from __future__ import annotations

from skillcard.cli import main
from skillcard.models import Dimension, EvalResult, cap_grade


def make_result(structure_score: float = 100.0, injection_hits: list[str] | None = None) -> EvalResult:
    """Build an EvalResult with just structure + optional injection hits."""
    r = EvalResult(path="test/SKILL.md")
    r.dimensions.append(Dimension(key="structure", label="Structure", score=structure_score))
    r.injection_hits = injection_hits or []
    return r.finalize()


class TestCleanSkill:
    def test_clean_full_structure_is_A(self):
        r = make_result(structure_score=95.0, injection_hits=[])
        assert r.grade == "A"
        assert r.total_score == 95.0
        assert not any("security gate" in w for w in r.warnings)

    def test_clean_zero_structure_is_F(self):
        """No security bonus: clean but bad structure = F."""
        r = make_result(structure_score=0.0, injection_hits=[])
        assert r.grade == "F"
        assert r.total_score == 0.0


class TestOneInjectionHit:
    def test_caps_at_B(self):
        r = make_result(structure_score=100.0, injection_hits=["ignore previous instructions"])
        assert r.grade == "B", f"1 hit should cap at B, got {r.grade}"
        assert any("1 injection" in w for w in r.warnings)

    def test_does_not_raise_B_to_A(self):
        """A skill with base 95 (A) + 1 hit should be capped at B."""
        r = make_result(structure_score=95.0, injection_hits=["some pattern"])
        assert r.grade == "B"


class TestTwoInjectionHits:
    def test_caps_at_D(self):
        r = make_result(structure_score=100.0, injection_hits=["hit1", "hit2"])
        assert r.grade == "D", f"2 hits should cap at D, got {r.grade}"
        assert any("2 injection" in w for w in r.warnings)


class TestThreeOrMoreHits:
    def test_caps_at_F(self):
        r = make_result(structure_score=100.0, injection_hits=["h1", "h2", "h3"])
        assert r.grade == "F", f"3+ hits should be F, got {r.grade}"
        assert any(">=3" in w for w in r.warnings)

    def test_even_perfect_structure_is_F(self):
        """A perfect skill with 3 injection patterns gets F."""
        r = make_result(structure_score=100.0, injection_hits=["a", "b", "c", "d"])
        assert r.grade == "F"


class TestCapGradeFunction:
    def test_A_capped_at_B_returns_B(self):
        assert cap_grade("A", "B") == "B"

    def test_B_capped_at_B_returns_B(self):
        assert cap_grade("B", "B") == "B"

    def test_C_capped_at_B_returns_C(self):
        """Lower grade stays lower; cap only pulls down."""
        assert cap_grade("C", "B") == "C"

    def test_F_capped_at_anything_stays_F(self):
        assert cap_grade("F", "B") == "F"


def test_cli_prints_security_status(tmp_path, capsys):
    skill = tmp_path / "SKILL.md"
    skill.write_text(
        "---\nname: test\ndescription: A sufficiently detailed test skill description.\n---\n"
        "# Test\n\n## Steps\n\n1. Run the check.\n",
        encoding="utf-8",
    )

    assert main([str(skill), "--no-llm", "--out", str(tmp_path / "report")]) == 0
    output = capsys.readouterr().out
    assert "Security" in output
    assert "clean" in output
    assert "shields.io/endpoint" not in output
