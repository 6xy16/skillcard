"""Tests for the L4 dynamic execution layer.

L4 runs the skill's code in a subprocess, so these tests use tiny, harmless
scripts (``print`` / ``exit``) driven by the ``python`` runtime, which is
cross-platform. The timeout and output-cap paths are exercised with a slow
or loud subprocess.
"""

from __future__ import annotations

from skillcard.l4_execution import (
    MAX_OUTPUT_BYTES,
    ExecutionResult,
    _detect_runtime,
    _extract_steps,
    run_l4,
)
from skillcard.parser import SkillDoc, parse_skill_text


def _doc(raw: str) -> SkillDoc:
    return parse_skill_text(raw, path="test/SKILL.md")


def _py_script(body: str) -> SkillDoc:
    return _doc(f"---\nname: foo\ndescription: x\nruntime: python\n---\n```python\n{body}\n```")


def test_detect_runtime_defaults_to_bash():
    assert _detect_runtime(_doc("---\nname: foo\ndescription: x\n---\nbody")) == "bash"


def test_detect_runtime_from_frontmatter():
    doc = _doc("---\nname: foo\ndescription: x\nruntime: python\n---\nbody")
    assert _detect_runtime(doc) == "python"


def test_detect_runtime_from_name_hint():
    doc = _doc("---\nname: foo.py\ndescription: x\n---\nbody")
    assert _detect_runtime(doc) == "python"


def test_extract_steps_finds_code_blocks():
    doc = _doc("---\nname: foo\ndescription: x\n---\n```bash\necho hi\n```")
    assert _extract_steps(doc) == ["echo hi"]


def test_extract_steps_returns_empty_without_code_blocks():
    doc = _doc("---\nname: foo\ndescription: x\n---\njust prose, no code")
    assert _extract_steps(doc) == []


def test_run_l4_no_steps_reports_ran_false():
    doc = _doc("---\nname: foo\ndescription: x\n---\nno code blocks here")
    result = run_l4(doc)
    assert result.ran is False
    assert any("no executable steps" in w for w in result.warnings)


def test_run_l4_successful_python_print():
    doc = _py_script("print('hello-from-l4')")
    result = run_l4(doc)
    assert result.ran is True
    assert result.completed is True
    assert result.exit_code == 0
    assert "hello-from-l4" in result.stdout
    assert result.timed_out is False


def test_run_l4_nonzero_exit_is_not_completed():
    doc = _py_script("import sys\nprint('oops')\nsys.exit(3)")
    result = run_l4(doc)
    assert result.completed is False
    assert result.exit_code == 3


def test_run_l4_timeout_is_reported():
    # A script that sleeps past a tiny timeout -> timed_out.
    doc = _py_script("import time\ntime.sleep(5)")
    result = run_l4(doc, timeout=0.2)
    assert result.timed_out is True
    assert result.completed is False


def test_run_l4_truncates_large_output():
    # Emit more than MAX_OUTPUT_BYTES of data and confirm truncation is marked.
    doc = _py_script(f"print('x' * {MAX_OUTPUT_BYTES + 10000})")
    result = run_l4(doc)
    assert result.truncated is True
    assert len(result.stdout) + len(result.stderr) <= MAX_OUTPUT_BYTES


def test_run_l4_missing_interpreter_warns(monkeypatch):
    doc = _doc("---\nname: foo\ndescription: x\nruntime: python\n---\n```python\nprint(1)\n```")
    import skillcard.l4_execution as mod

    def _raise(*a, **kw):
        raise FileNotFoundError("no python")

    monkeypatch.setattr(mod.subprocess, "run", _raise)
    result = mod.run_l4(doc)
    assert result.ran is True
    assert result.completed is False
    assert any("not found" in w for w in result.warnings)


def test_result_is_execution_result_type():
    assert isinstance(run_l4(_doc("---\nname: x\ndescription: x\n---\nbody")), ExecutionResult)
