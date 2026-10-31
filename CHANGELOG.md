# Changelog

All notable changes to this project will be documented in this file.

## Unreleased

### Features

- **L4 dynamic execution** — `--run` executes a skill's code blocks in a local subprocess with a hard timeout and output cap, recording completion, exit code, duration, and (truncated) output. OFF by default because it runs untrusted code; see the README security warning.
- **Trigger benchmark** — `benchmarks/` adds a small, hand-annotated trigger benchmark (good/mid/poor skills + labeled `trigger`/`no_trigger`/`borderline` probes) and a deterministic approximation scorer that reports accuracy and FP/FN rates. Reproducible via `python benchmarks/benchmark.py`.
- **Batch evaluation + version diff** — `skillcard batch DIR` scores every SKILL.md in a directory into a diffable snapshot; `skillcard diff BEFORE AFTER` reports per-skill score/grade/failed-check/cost changes, regressions first.
- **L2 cache** — `.skillcard-cache/` stores L2 verdicts keyed on skill text + model + prompt hash; unchanged skills re-score for free and bit-stably. Bypassed by the stability command.
- **Stability experiment** — `skillcard stability FILE --runs N` re-runs the judge N times and reports per-dimension min/max/mean/stddev plus token and latency spread, quantifying LLM score nondeterminism.
- **Stronger L2 validation** — judge score fields are strictly validated (must be numeric 0–100); missing/out-of-range fields are marked n/a instead of silently defaulting. Probe-generation failure marks only probe-dependent dimensions n/a. Full reproducibility metadata (probes, prompt hashes, raw verdict, base URL, timeout) is captured in `result.json`.

### Docs

- README rewritten around real output and real numbers: live `deepseek-chat` runs, a faithful terminal screenshot (regenerated via `docs/make_demo.py`), and measured stability figures (e.g. `instruction_clarity` ±4.0 points across 3 runs, `trigger_accuracy` ±0.0). Added `--no-cache` flag and documented cache hit behavior.

## v0.1.0 - 2026-10-29

Initial alpha release.

### Features

- **L1 Structure checks** — 10 deterministic checks: frontmatter validity, core fields, description length (CJK-aware), vague word detection, trigger clarity, examples, size, recommended fields, structured body, output verifiability.
- **L2 LLM paper review** — optional judge that auto-generates 10 probe requests and scores 4 dimensions: trigger accuracy, boundary robustness, instruction clarity, output verifiability. Works with any OpenAI-compatible endpoint.
- **L3 Security gate** — scans for prompt-injection and judge-gaming patterns. Not a scored dimension — it's a gate that caps your grade: 1 hit → B cap, 2 hits → D cap, 3+ → F.
- **Score card PNG** — 680×620 card with big letter grade, dimension bars, and security status.
- **SVG badge** — static badge for your README.
- **Reproducible results** — every result.json carries judge model, prompt hash, and eval version.
- **Improvement suggestions** — failed checks come with "how to fix" + copy-paste snippet, sorted by lost points.

### Known limitations

- L2 requires an OpenAI-compatible API key; without it, L2 dimensions show as n/a.
- Card font rendering varies across platforms (falls back to default bitmap font if system fonts are missing).
- No real agent runtime — L2 is paper review only.
