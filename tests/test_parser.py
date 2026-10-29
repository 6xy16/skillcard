"""Boundary tests for the SKILL.md parser."""

from __future__ import annotations

from skillcard.parser import parse_skill_text


def test_missing_frontmatter_is_tolerated():
    doc = parse_skill_text("# Just a heading\n\nNo frontmatter here.\n")
    assert doc.frontmatter == {}
    assert doc.body == "# Just a heading\n\nNo frontmatter here.\n"
    assert any("missing" in e for e in doc.parse_errors)


def test_empty_frontmatter_block():
    doc = parse_skill_text("---\n---\n\n# Body\n")
    assert doc.frontmatter == {}
    assert doc.body.startswith("# Body")


def test_yaml_syntax_error_is_reported():
    doc = parse_skill_text("---\nname: [unclosed\n---\n\nbody\n")
    assert doc.frontmatter == {}
    assert any("YAML" in e or "yaml" in e for e in doc.parse_errors)


def test_crlf_line_endings():
    raw = "---\r\nname: test\r\ndescription: A description long enough for testing.\r\n---\r\n\r\n# Body\r\n"
    doc = parse_skill_text(raw)
    assert doc.name == "test"
    assert doc.description == "A description long enough for testing."


def test_bom_is_tolerated():
    raw = "\ufeff---\nname: test\ndescription: A description long enough for testing.\n---\n\n# Body\n"
    doc = parse_skill_text(raw)
    assert doc.name == "test"


def test_non_mapping_frontmatter_is_reported():
    doc = parse_skill_text("---\n- just\n- a\n- list\n---\n\n# Body\n")
    assert doc.frontmatter == {}
    assert any("mapping" in e for e in doc.parse_errors)
