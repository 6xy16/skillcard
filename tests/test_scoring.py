"""Tests for weighted score calculation."""

from __future__ import annotations

from skillcard.models import Dimension, EvalResult


def make_result_with_dimensions(scores: dict[str, float]) -> EvalResult:
    """Build an EvalResult with the given dimension scores."""
    r = EvalResult(path="test/SKILL.md")
    labels = {
        "structure": "Structure",
        "trigger_accuracy": "Trigger accuracy",
        "boundary_robustness": "Boundary robustness",
        "instruction_clarity": "Instruction clarity",
        "output_verifiability": "Output verifiability",
    }
    for key, score in scores.items():
        r.dimensions.append(Dimension(key=key, label=labels.get(key, key), score=score))
    return r.finalize()


class TestWeightedAverage:
    def test_only_structure(self):
        r = make_result_with_dimensions({"structure": 80.0})
        assert r.total_score == 80.0

    def test_all_dimensions_equal_80(self):
        r = make_result_with_dimensions({
            "structure": 80.0,
            "trigger_accuracy": 80.0,
            "boundary_robustness": 80.0,
            "instruction_clarity": 80.0,
            "output_verifiability": 80.0,
        })
        assert r.total_score == 80.0

    def test_structure_dominates(self):
        """Structure has 40% weight, so it should pull the average more."""
        r = make_result_with_dimensions({
            "structure": 100.0,
            "trigger_accuracy": 0.0,
            "boundary_robustness": 0.0,
            "instruction_clarity": 0.0,
            "output_verifiability": 0.0,
        })
        # structure weight = 0.40, total weight = 1.0
        # score = 100 * 0.40 / 1.0 = 40
        assert r.total_score == 40.0

    def test_partial_dimensions_normalize(self):
        """Only structure + trigger_accuracy: weights normalize."""
        r = make_result_with_dimensions({
            "structure": 100.0,
            "trigger_accuracy": 50.0,
        })
        # weights: structure 0.40, trigger 0.20, total = 0.60
        # score = (100*0.40 + 50*0.20) / 0.60 = (40 + 10) / 0.60 = 83.3
        assert abs(r.total_score - 83.3) < 0.2


class TestGradeMapping:
    def test_95_is_A(self):
        r = make_result_with_dimensions({"structure": 95.0})
        assert r.grade == "A"

    def test_85_is_B(self):
        r = make_result_with_dimensions({"structure": 85.0})
        assert r.grade == "B"

    def test_75_is_C(self):
        r = make_result_with_dimensions({"structure": 75.0})
        assert r.grade == "C"

    def test_65_is_D(self):
        r = make_result_with_dimensions({"structure": 65.0})
        assert r.grade == "D"

    def test_50_is_F(self):
        r = make_result_with_dimensions({"structure": 50.0})
        assert r.grade == "F"
