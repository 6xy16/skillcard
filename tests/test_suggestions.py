"""Tests for improvement suggestions on failed L1 checks."""

from __future__ import annotations

from conftest import make_skill_doc

from skillcard.l1_structure import run_l1


class TestSuggestionsExistOnFailure:
    def test_bad_skill_has_suggestions(self):
        doc = make_skill_doc(raw="just some stuff\n")
        checks = run_l1(doc)
        failed = [c for c in checks if not c.passed]
        assert len(failed) > 0
        for c in failed:
            assert c.suggestion, f"check {c.name} failed but has no suggestion"

    def test_good_skill_no_suggestions(self):
        doc = make_skill_doc(
            frontmatter=(
                "name: commit-message\n"
                "description: Write conventional-commit messages from a git diff. "
                "Use when the user asks to commit, write a commit message, or summarize staged changes.\n"
                "when_to_use: User asks to create a commit message.\n"
                "license: MIT\n"
            ),
            body=(
                "# Commit Message Writer\n\n"
                "## Steps\n\n"
                "1. Run git diff --staged.\n\n"
                "## Output format\n\n"
                "Return only the commit message.\n\n"
                "## Examples\n\n"
                "Input: add login endpoint -> feat(auth): add login endpoint\n"
            ),
        )
        checks = run_l1(doc)
        for c in checks:
            if c.passed:
                assert c.suggestion == "", f"check {c.name} passed but has suggestion: {c.suggestion}"


class TestSuggestionContent:
    def test_frontmatter_suggestion_has_template(self):
        doc = make_skill_doc(raw="no frontmatter here at all\n")
        checks = run_l1(doc)
        fm = next(c for c in checks if c.name == "frontmatter-valid")
        assert not fm.passed
        assert "---" in fm.suggestion
        assert "name:" in fm.suggestion

    def test_has_examples_suggestion_has_snippet(self):
        doc = make_skill_doc(
            frontmatter="name: test\ndescription: A description that is long enough for testing.\n",
            body="# Test\n\nJust steps, no examples.\n",
        )
        checks = run_l1(doc)
        ex = next(c for c in checks if c.name == "has-examples")
        assert not ex.passed
        assert "## Examples" in ex.suggestion

    def test_output_suggestion_has_snippet(self):
        doc = make_skill_doc(
            frontmatter="name: test\ndescription: A description that is long enough for testing.\n",
            body="# Test\n\n## Examples\n\nInput: something\n",
        )
        checks = run_l1(doc)
        out = next(c for c in checks if c.name == "output-verifiable")
        assert not out.passed
        assert "Output format" in out.suggestion

    def test_trigger_suggestion_has_when_to_use(self):
        doc = make_skill_doc(
            frontmatter="name: test\ndescription: short\n",
            body="# Test\n",
        )
        checks = run_l1(doc)
        trig = next(c for c in checks if c.name == "trigger-clarity")
        assert not trig.passed
        assert "when_to_use" in trig.suggestion or "Use when" in trig.suggestion


class TestSuggestionSorting:
    def test_failed_checks_sorted_by_weight_desc(self):
        """Failed checks should be sortable by weight (highest lost points first)."""
        doc = make_skill_doc(raw="just stuff\n")
        checks = run_l1(doc)
        failed = [c for c in checks if not c.passed and c.suggestion]
        failed.sort(key=lambda c: -c.weight)
        weights = [c.weight for c in failed]
        assert weights == sorted(weights, reverse=True)
