# Changelog

All notable changes to this project will be documented in this file.

## v0.1.0 - 2026-10-29

Initial alpha release.

### Features

- **L1 Structure checks** — 10 deterministic checks: frontmatter validity, core fields, description length (CJK-aware), vague word detection, trigger clarity, examples, size, recommended fields, structured body, output verifiability.
- **L2 LLM paper review** — optional judge that auto-generates 10 probe requests and scores 4 dimensions: trigger accuracy, boundary robustness, instruction clarity, output verifiability. Works with any OpenAI-compatible endpoint.
- **L3 Security gate** — scans for prompt-injection and judge-gaming patterns. Not a scored dimension — it's a gate that caps your grade: 1 hit → B cap, 2 hits → D cap, 3+ → F.
- **Score card PNG** — 680×620 card with big letter grade, dimension bars, and security status.
- **SVG badge** — shields.io-compatible static badge for your README.
- **Reproducible results** — every result.json carries judge model, prompt hash, and eval version.
- **Improvement suggestions** — failed checks come with "how to fix" + copy-paste snippet, sorted by lost points.

### Known limitations

- L2 requires an OpenAI-compatible API key; without it, L2 dimensions show as n/a.
- Card font rendering varies across platforms (falls back to default bitmap font if system fonts are missing).
- No real agent runtime — L2 is paper review only.
