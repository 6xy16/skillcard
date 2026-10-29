# skillcard

![grade](https://img.shields.io/badge/grade-A-brightgreen)
![python](https://img.shields.io/badge/python-3.9%2B-blue)
![status](https://img.shields.io/badge/status-alpha-orange)
![license](https://img.shields.io/badge/license-MIT-green)
[![CI](https://github.com/6xy16/skillcard/actions/workflows/test.yml/badge.svg)](https://github.com/6xy16/skillcard/actions/workflows/test.yml)

**Quality score cards for Agent Skills.** Point it at a `SKILL.md`, get a beautiful score card and a README badge — plus a list of exactly what to fix to level up.

给 Agent Skill（SKILL.md）生成质量评分卡和 README 徽章——让"晒分数"成为技能包生态的社交货币。

---

## What you get

```
$ skillcard examples/01-excellent.md

Grade: A  (100.0/100)
  Structure              100
  Trigger accuracy       n/a
  Boundary robustness    n/a
  Instruction clarity    n/a
  Output verifiability   n/a
  Security               clean

card:  skillcard-report/card.png
badge: skillcard-report/badge.svg
json:  skillcard-report/result.json
```

Three files in `./skillcard-report/`:

| File | What |
|------|------|
| `card.png` | 680×620 shareable score card — big letter grade, dimension bars, security status |
| `badge.svg` | shields.io-compatible static badge for your README |
| `result.json` | Machine-readable result with judge model + prompt hash for reproducibility |

Embed the badge in your README:

```md
![skill score](skillcard-report/badge.svg)
```

---

## Install

```bash
pip install git+https://github.com/6xy16/skillcard.git
```

## Usage

```bash
# Basic run (L1 structure + L3 security gate)
skillcard path/to/SKILL.md

# Skip LLM review explicitly
skillcard path/to/SKILL.md --no-llm

# Custom output directory
skillcard path/to/SKILL.md --out my-report

# Print JSON to stdout
skillcard path/to/SKILL.md --json
```

Enable L2 LLM paper review (optional). Install the LLM dependency, then configure the endpoint:

```bash
pip install "skillcard[llm] @ git+https://github.com/6xy16/skillcard.git"
export SKILLCARD_API_KEY=sk-...
export SKILLCARD_MODEL=gpt-4o-mini        # optional
export SKILLCARD_BASE_URL=https://...     # optional, any OpenAI-compatible endpoint
```

---

## How it works

Three layers:

### L1 — Structure (deterministic, always on)
10 checks: frontmatter validity, core fields, description length (CJK-aware), vague words, trigger clarity, examples, size, recommended fields, structured body, output verifiability.

### L2 — Paper review (LLM judge, optional)
Auto-generates 10 probe requests (should-trigger / borderline / should-not-trigger) and scores 4 dimensions: trigger accuracy, boundary robustness, instruction clarity, output verifiability.

### L3 — Security gate (always on)
Scans for prompt-injection and judge-gaming patterns. **Not a scored dimension — it's a gate:**
- 0 hits → grade is whatever your quality score says
- 1 hit → grade capped at B
- 2 hits → grade capped at D
- 3+ hits → straight F

Security can't be "bought back" by high quality scores.

---

## Why

The skills ecosystem has millions of indexed skills and zero quality standards. Existing tools are internal linters for developers. skillcard is different: **the output is the product** — a card worth sharing, a badge worth embedding, and a clear list of what to fix next.

技能包生态有百万级存量，但没有质量标准。现有工具都是给开发者自用的内部工具。skillcard 反过来：**输出物本身就是产品**——一张值得分享的评分卡，一个值得贴在 README 上的徽章，一份告诉你下一步怎么改的修复清单。

---

## Grades

`A (90+)  B (80+)  C (70+)  D (60+)  F (<60)` — the letter grade is the hero of the card.

---

## Roadmap

- **v0.1 (this)** — static checks + paper review, PNG card, static badge, improvement suggestions
- **v0.2** — real agent runs (headless harness), dynamic badge endpoint, multi-model comparison
- **v0.3** — batch scoring, diff between versions, opt-in leaderboard

---

## License

MIT
