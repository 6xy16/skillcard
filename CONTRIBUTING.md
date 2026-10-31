# Contributing to skillcard

Thanks for helping out. This file covers the local setup and the two most
common contributions: adding a new check and adding a new injection pattern.

## Setup

```bash
git clone https://github.com/6xy16/skillcard.git
cd skillcard
python -m venv .venv
# Windows:
.venv\Scripts\activate
# macOS / Linux:
source .venv/bin/activate
pip install -e ".[dev]"
```

Verify everything works before changing anything:

```bash
ruff check .
pytest tests/ -q
```

## Project layout

```
src/skillcard/
  cli.py            # entry point: orchestrates L1 -> L2 -> L3 -> L4 -> render
  parser.py         # lenient SKILL.md frontmatter + body parsing
  l1_structure.py   # deterministic structural checks (scored)
  l2_judge.py       # optional LLM paper review (scored)
  l3_injection.py   # prompt-injection security gate (caps the grade)
  l4_execution.py   # optional dynamic execution (--run, runs the skill's code)
  cache.py          # disk cache for L2 verdicts (skill+model+prompt keyed)
  batch.py          # directory batch scan + snapshot diff
  stability.py      # re-run the judge N times, report score variation
  models.py         # EvalResult, Dimension, grade mapping
  card.py           # PNG score card rendering
  badge.py          # SVG badge rendering
benchmarks/
  cases.yaml        # hand-annotated trigger/no_trigger/borderline probes
  benchmark.py      # deterministic approximation + agreement statistics
tests/
  conftest.py       # shared fixtures (reuses the real parser)
  test_*.py         # unit + end-to-end tests
```

## Adding a new L1 check

1. Add the check in `run_l1` (`src/skillcard/l1_structure.py`). Give it a
   `weight` and, when it fails, a `message` plus a copy-paste `suggestion`.
2. Add a test in `tests/test_l1_structure.py` that covers both the pass and
   fail paths.
3. Run `pytest tests/ -q` and `ruff check .`.

## Adding a new L3 injection pattern

1. Add a `Pattern(regex, reason)` to `PATTERNS` in
   `src/skillcard/l3_injection.py`.
2. Think about severity: a phrase in the frontmatter `description` is always
   `hard`; a lone body match is `soft`; a cluster of body matches is `hard`.
   See the module docstring for the full rule.
3. Add a test to `tests/test_parser.py` or a new `test_l3_*.py`.

## Conventions

- Python 3.9+ (type hints use `from __future__ import annotations`).
- Format with Ruff (`ruff check .`); line length 100.
- Keep the output reproducible: every `result.json` carries the judge model,
  prompt hash, and eval version.

## Pull requests

- Keep changes small and focused; one concern per PR.
- Update `CHANGELOG.md` under an `## Unreleased` section.
- Make sure `ruff check .` and `pytest tests/ -q` both pass.
