"""Tests for L1 deterministic structural checks."""

from __future__ import annotations

from conftest import make_skill_doc

from skillcard.l1_structure import l1_score, run_l1


class TestFrontmatter:
    def test_valid_frontmatter_passes(self, good_skill):
        checks = run_l1(good_skill)
        fm = next(c for c in checks if c.name == "frontmatter-valid")
        assert fm.passed is True
        assert "cleanly" in fm.message

    def test_missing_frontmatter_fails(self):
        doc = make_skill_doc(raw="# Just a heading\n\nNo frontmatter here.")
        checks = run_l1(doc)
        fm = next(c for c in checks if c.name == "frontmatter-valid")
        assert fm.passed is False
        assert "missing" in fm.message


class TestCoreFields:
    def test_both_present_passes(self, good_skill):
        checks = run_l1(good_skill)
        c = next(x for x in checks if x.name == "core-fields")
        assert c.passed is True

    def test_missing_name_fails(self):
        doc = make_skill_doc(frontmatter="description: some description here that is long enough.\n")
        checks = run_l1(doc)
        c = next(x for x in checks if x.name == "core-fields")
        assert c.passed is False
        assert "name" in c.message


class TestDescriptionLength:
    def test_good_length_passes(self, good_skill):
        checks = run_l1(good_skill)
        c = next(x for x in checks if x.name == "description-length")
        assert c.passed is True

    def test_too_short_fails(self):
        doc = make_skill_doc(
            frontmatter="name: test\ndescription: short\n",
            body="# Test\n",
        )
        checks = run_l1(doc)
        c = next(x for x in checks if x.name == "description-length")
        assert c.passed is False
        assert "chars" in c.message

    def test_cjk_chars_count_double(self):
        """19 Chinese chars should weigh ~38, passing the 20 threshold."""
        doc = make_skill_doc(
            frontmatter="name: test\ndescription: 这是一个用于生成提交信息的技能包帮助开发者写好\n",
            body="# Test\n",
        )
        checks = run_l1(doc)
        c = next(x for x in checks if x.name == "description-length")
        assert c.passed is True, f"19 CJK chars should pass, got: {c.message}"
        assert "weighted" in c.message


class TestVagueWords:
    def test_no_vague_words_passes(self, good_skill):
        checks = run_l1(good_skill)
        c = next(x for x in checks if x.name == "description-specific")
        assert c.passed is True

    def test_vague_words_fail(self):
        doc = make_skill_doc(
            frontmatter="name: test\ndescription: This skill handles stuff and things and etc.\n",
            body="# Test\n",
        )
        checks = run_l1(doc)
        c = next(x for x in checks if x.name == "description-specific")
        assert c.passed is False
        assert "vague" in c.message


class TestTriggerClarity:
    def test_with_when_to_use_passes(self, good_skill):
        checks = run_l1(good_skill)
        c = next(x for x in checks if x.name == "trigger-clarity")
        assert c.passed is True

    def test_no_trigger_fails(self):
        """Short vague description with no explicit trigger should fail."""
        doc = make_skill_doc(
            frontmatter="name: test\ndescription: short desc\n",
            body="# Test\n",
        )
        checks = run_l1(doc)
        c = next(x for x in checks if x.name == "trigger-clarity")
        assert c.passed is False

    def test_implicit_trigger_via_description_length(self):
        """A sufficiently long specific description should pass via implicit trigger."""
        doc = make_skill_doc(
            frontmatter="name: test\ndescription: Help with git operations like committing and branching.\n",
            body="# Test\n",
        )
        checks = run_l1(doc)
        c = next(x for x in checks if x.name == "trigger-clarity")
        assert c.passed is True
        assert "specific enough" in c.message


class TestHasExamples:
    def test_with_examples_heading_passes(self, good_skill):
        checks = run_l1(good_skill)
        c = next(x for x in checks if x.name == "has-examples")
        assert c.passed is True

    def test_no_examples_fails(self):
        doc = make_skill_doc(
            frontmatter="name: test\ndescription: A description that is long enough for testing.\n",
            body="# Test\n\nJust steps here, no examples section.\n",
        )
        checks = run_l1(doc)
        c = next(x for x in checks if x.name == "has-examples")
        assert c.passed is False


class TestRecommendedFields:
    def test_within_tolerance_passes(self, good_skill):
        """Good skill has when_to_use + license, missing triggers + examples = 2/4 missing."""
        checks = run_l1(good_skill)
        c = next(x for x in checks if x.name == "recommended-fields")
        assert c.passed is True
        assert "within tolerance" in c.message

    def test_too_many_missing_fails(self):
        doc = make_skill_doc(
            frontmatter="name: test\ndescription: A description that is long enough for testing.\n",
            body="# Test\n",
        )
        checks = run_l1(doc)
        c = next(x for x in checks if x.name == "recommended-fields")
        assert c.passed is False


class TestL1Score:
    def test_all_pass_is_100(self, good_skill):
        checks = run_l1(good_skill)
        score = l1_score(checks)
        assert score == 100.0

    def test_all_fail_is_0(self, bad_skill):
        checks = run_l1(bad_skill)
        score = l1_score(checks)
        assert score == 0.0
