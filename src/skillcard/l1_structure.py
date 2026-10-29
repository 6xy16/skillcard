"""L1: deterministic structural checks on a SKILL.md.

Ten checks, each weighted. Score = 100 * earned_weight / total_weight.
"""

from __future__ import annotations

import re

from skillcard.models import Check
from skillcard.parser import CORE_FIELDS, RECOMMENDED_FIELDS, SkillDoc

VAGUE_WORDS = {"stuff", "things", "etc", "various", "something", "handle", "process"}


def run_l1(doc: SkillDoc) -> list[Check]:
    checks: list[Check] = []
    fm, desc = doc.frontmatter, doc.description

    def add(name: str, passed: bool, weight: int, message: str = "", suggestion: str = "") -> None:
        checks.append(Check(name=name, passed=passed, weight=weight, message=message, suggestion=suggestion))

    # 1. frontmatter-valid
    fm_ok = not doc.parse_errors
    fm_msg = "; ".join(doc.parse_errors) if doc.parse_errors else "frontmatter parses cleanly"
    fm_sugg = ""
    if not fm_ok:
        fm_sugg = (
            "Add a YAML frontmatter block at the very top of the file:\n"
            "  ---\n"
            "  name: my-skill\n"
            "  description: What this skill does and when to use it.\n"
            "  ---"
        )
    add("frontmatter-valid", fm_ok, 15, fm_msg, fm_sugg)

    # 2. core-fields
    missing_core = [f for f in CORE_FIELDS if not fm.get(f)]
    core_ok = not missing_core
    core_msg = "missing: " + ", ".join(missing_core) if missing_core else "name + description present"
    core_sugg = ""
    if not core_ok:
        core_sugg = (
            "Add the missing fields to frontmatter:\n"
            "  name: my-skill-name\n"
            "  description: One clear sentence describing what it does."
        )
    add("core-fields", core_ok, 15, core_msg, core_sugg)

    # CJK characters carry ~2x the information density of Latin chars.
    def _is_cjk(ch: str) -> bool:
        cp = ord(ch)
        return (
            0x4E00 <= cp <= 0x9FFF
            or 0x3400 <= cp <= 0x4DBF
            or 0x3040 <= cp <= 0x30FF
            or 0xAC00 <= cp <= 0xD7AF
        )

    # 3. description-length
    dlen = sum(2 if _is_cjk(ch) else 1 for ch in desc)
    len_ok = 20 <= dlen <= 500
    len_msg = f"description is {len(desc)} chars (weighted {dlen}, recommended 20-500)"
    len_sugg = ""
    if not len_ok:
        if dlen < 20:
            len_sugg = (
                "Expand the description to at least 20 weighted chars.\n"
                "  Bad:  'writes commits'\n"
                "  Good: 'Write conventional-commit messages from a git diff. Use when the user asks to commit.'"
            )
        else:
            len_sugg = "Trim the description to under 500 chars. Keep it to one or two sentences."
    add("description-length", len_ok, 10, len_msg, len_sugg)

    # 4. description-specific
    vague = [w for w in VAGUE_WORDS if re.search(rf"\b{w}\b", desc, re.IGNORECASE)]
    spec_ok = bool(desc) and not vague
    if vague:
        spec_msg = f"vague words found: {', '.join(vague)}"
    elif not desc:
        spec_msg = "description is empty"
    else:
        spec_msg = "no vague filler words"
    spec_sugg = ""
    if not spec_ok:
        if vague:
            spec_sugg = (
                "Replace vague filler words with specifics.\n"
                "  Bad:  'handles stuff and things'\n"
                "  Good: 'formats SQL queries and checks for injection patterns'"
            )
        else:
            spec_sugg = "Add a clear, specific description of what the skill does."
    add("description-specific", spec_ok, 10, spec_msg, spec_sugg)

    # 5. trigger-clarity
    has_explicit_trigger = bool(
        fm.get("when_to_use")
        or fm.get("triggers")
        or re.search(r"(?i)use (this|when|for)\b", desc)
    )
    has_implicit_trigger = len(desc) >= 40 and not vague
    trigger_hint = has_explicit_trigger or has_implicit_trigger

    if has_explicit_trigger:
        trigger_msg = "has when_to_use/triggers or explicit 'use when' phrasing"
        trigger_sugg = ""
    elif has_implicit_trigger:
        trigger_msg = "description is specific enough to infer trigger conditions"
        trigger_sugg = ""
    else:
        trigger_msg = "no clear trigger conditions; agent may fail to invoke this skill"
        trigger_sugg = (
            "Add a clear trigger condition. Either:\n"
            "  - frontmatter field: when_to_use: User asks to X or Y\n"
            "  - or in description: 'Use when the user asks to ...'"
        )
    add("trigger-clarity", trigger_hint, 15, trigger_msg, trigger_sugg)

    # 6. has-examples
    ex_ok = doc.has_examples
    ex_msg = "examples found" if ex_ok else "no examples section or code blocks"
    ex_sugg = ""
    if not ex_ok:
        ex_sugg = (
            "Add an ## Examples section with 1-2 input/output pairs:\n"
            "  ## Examples\n"
            "  Input: user asks to commit login changes\n"
            "  Output: feat(auth): add login endpoint with JWT"
        )
    add("has-examples", ex_ok, 10, ex_msg, ex_sugg)

    # 7. size-reasonable
    size_ok = 10 <= doc.line_count <= 500
    size_msg = f"{doc.line_count} lines (recommended 10-500)"
    size_sugg = ""
    if not size_ok:
        if doc.line_count < 10:
            size_sugg = "Expand the skill to at least 10 lines. Add steps, examples, and output format sections."
        else:
            size_sugg = "Trim the skill to under 500 lines. Split long skills into multiple smaller ones."
    add("size-reasonable", size_ok, 5, size_msg, size_sugg)

    # 8. recommended-fields
    missing_rec = [f for f in RECOMMENDED_FIELDS if f not in fm]
    rec_total = len(RECOMMENDED_FIELDS)
    rec_missing = len(missing_rec)
    rec_pass = rec_missing <= 2
    if not missing_rec:
        rec_msg = "all recommended fields present"
        rec_sugg = ""
    elif rec_pass:
        rec_msg = f"{rec_missing}/{rec_total} recommended fields missing (within tolerance): {', '.join(missing_rec)}"
        rec_sugg = ""
    else:
        rec_msg = f"{rec_missing}/{rec_total} recommended fields missing: {', '.join(missing_rec)}"
        rec_sugg = (
            f"Add the missing recommended fields: {', '.join(missing_rec)}.\n"
            "  Most impactful: when_to_use (helps agent trigger the skill)."
        )
    add("recommended-fields", rec_pass, 5, rec_msg, rec_sugg)

    # 9. structured-body
    has_steps = bool(
        re.search(r"(?m)^\s*(\d+\.|[-*])\s+\S", doc.body) or re.search(r"(?im)^#{1,4}\s", doc.body)
    )
    struct_ok = has_steps
    struct_msg = "body has headings or lists" if has_steps else "body is an unstructured wall of text"
    struct_sugg = ""
    if not struct_ok:
        struct_sugg = (
            "Break the body into sections with headings and numbered steps:\n"
            "  ## Steps\n"
            "  1. Read the input.\n"
            "  2. Process it.\n"
            "  3. Return the result."
        )
    add("structured-body", struct_ok, 10, struct_msg, struct_sugg)

    # 10. output-verifiable
    has_output_spec = bool(
        re.search(r"(?i)(output format|returns?|deliverable|acceptance criteria|验收|输出格式)", doc.body)
    )
    out_ok = has_output_spec
    out_msg = "declares expected output" if has_output_spec else "no declared output format or acceptance criteria"
    out_sugg = ""
    if not out_ok:
        out_sugg = (
            "Add an output format section so the agent knows what 'done' looks like:\n"
            "  ## Output format\n"
            "  Return only the result, no commentary. One paragraph max."
        )
    add("output-verifiable", out_ok, 5, out_msg, out_sugg)

    return checks


def l1_score(checks: list[Check]) -> float:
    total = sum(c.weight for c in checks)
    earned = sum(c.weight for c in checks if c.passed)
    return round(100.0 * earned / total, 1) if total else 0.0
