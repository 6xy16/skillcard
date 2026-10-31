"""L2: LLM paper review.

We never run the skill. The judge reasons over the SKILL.md text plus
auto-generated probe cases, and scores four dimensions:

- trigger accuracy      (would the right requests invoke this skill?)
- boundary robustness   (would irrelevant requests wrongly invoke it?)
- instruction clarity   (could a fresh agent follow the steps?)
- output verifiability  (is "done" checkable?)

The judge is any OpenAI-compatible endpoint. Configure with env vars:
    SKILLCARD_API_KEY   (required to enable L2)
    SKILLCARD_BASE_URL  (default: https://api.openai.com/v1)
    SKILLCARD_MODEL     (default: gpt-4o-mini)
"""

from __future__ import annotations

import json
import os
import re
import time
from dataclasses import dataclass, field

from skillcard.models import prompt_hash
from skillcard.parser import SkillDoc

# Timeout for a single LLM call, and the max number of retries for
# transient failures (timeouts, connection resets, 5xx, rate limits).
# These are the two numbers interviewers actually ask about.
DEFAULT_TIMEOUT_SECONDS = 60
MAX_RETRIES = 2

# Errors that are safe to retry — transient, not a problem with our request.
_RETRYABLE = (
    "timeout",
    "connection",
    "connect",
    "reset",
    "rate limit",
    "429",
    "500",
    "502",
    "503",
    "504",
    "temporary",
    "overloaded",
    "server error",
)

JUDGE_PROMPT_TEMPLATE = """You are a strict reviewer of Agent Skill definitions (SKILL.md files).

Below is a SKILL.md, followed by 10 auto-generated probe requests.
Some probes SHOULD trigger this skill, some SHOULD NOT.

<skill>
{skill_text}
</skill>

<probes>
{probes}
</probes>

Score the skill on four dimensions, each 0-100:
1. trigger_accuracy - is the description clear enough that the right probes would trigger it?
2. boundary_robustness - is it specific enough that irrelevant probes would NOT trigger it?
3. instruction_clarity - could a fresh agent execute the steps without guessing?
4. output_verifiability - does it define what a correct output looks like?

Also list any probe ids where the skill's description is ambiguous (could go either way).

Respond with ONLY a JSON object:
{{"trigger_accuracy": int, "boundary_robustness": int, "instruction_clarity": int,
  "output_verifiability": int, "ambiguous_probes": [int], "rationale": "one paragraph"}}
"""

PROBE_GEN_TEMPLATE = """Read this Agent Skill definition and generate 10 short user requests (probes):
- 4 that clearly SHOULD trigger this skill
- 3 that are borderline / partially related
- 3 that clearly should NOT trigger it

Return ONLY a JSON array of strings.

<skill>
{skill_text}
</skill>
"""


@dataclass
class JudgeConfig:
    api_key: str
    base_url: str = "https://api.openai.com/v1"
    model: str = "gpt-4o-mini"
    timeout: float = DEFAULT_TIMEOUT_SECONDS

    @staticmethod
    def from_env() -> JudgeConfig | None:
        key = os.environ.get("SKILLCARD_API_KEY")
        if not key:
            return None
        return JudgeConfig(
            api_key=key,
            base_url=os.environ.get("SKILLCARD_BASE_URL", "https://api.openai.com/v1"),
            model=os.environ.get("SKILLCARD_MODEL", "gpt-4o-mini"),
            timeout=float(os.environ.get("SKILLCARD_TIMEOUT", DEFAULT_TIMEOUT_SECONDS)),
        )


@dataclass
class L2Result:
    """Result of the optional LLM paper review."""

    trigger_accuracy: float
    boundary_robustness: float
    instruction_clarity: float
    output_verifiability: float
    rationale: str = ""
    ambiguous: list[int] = field(default_factory=list)
    prompt_hash: str = ""
    model: str = ""
    warnings: list[str] = field(default_factory=list)
    # Cost / latency accounting — what makes "LLM judge" defensible in an interview.
    duration_seconds: float = 0.0
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    retries: int = 0


def _chat(config: JudgeConfig, prompt: str) -> tuple[str, dict, float, int]:
    """Call the chat endpoint once, with timeout + retry on transient errors.

    Returns ``(content, usage_dict, elapsed_seconds, retry_count)``.
    ``usage_dict`` holds prompt/completion/total tokens when the provider
    reports them (many OpenAI-compatible endpoints do); it's empty otherwise.
    """
    try:
        from openai import OpenAI
    except ImportError as exc:
        raise RuntimeError("pip install 'skillcard[llm]' to enable LLM judging") from exc

    client = OpenAI(api_key=config.api_key, base_url=config.base_url, timeout=config.timeout)

    last_exc: Exception | None = None
    for attempt in range(MAX_RETRIES + 1):
        start = time.monotonic()
        try:
            resp = client.chat.completions.create(
                model=config.model,
                messages=[{"role": "user", "content": prompt}],
                temperature=0,
            )
            elapsed = time.monotonic() - start
            content = resp.choices[0].message.content or ""
            usage: dict = {}
            if getattr(resp, "usage", None):
                u = resp.usage
                usage = {
                    "prompt_tokens": getattr(u, "prompt_tokens", 0) or 0,
                    "completion_tokens": getattr(u, "completion_tokens", 0) or 0,
                    "total_tokens": getattr(u, "total_tokens", 0) or 0,
                }
            return content, usage, elapsed, attempt
        except Exception as exc:  # noqa: BLE001 - classify then maybe retry
            last_exc = exc
            msg = str(exc).lower()
            if not any(tok in msg for tok in _RETRYABLE):
                # Not transient (e.g. 401 bad key, 400 bad request): don't retry.
                break
            if attempt >= MAX_RETRIES:
                break
            # Small backoff before retrying a transient error.
            time.sleep(2**attempt)

    raise last_exc if last_exc is not None else RuntimeError("LLM call failed")


def _extract_json(text: str) -> dict:
    m = re.search(r"\{.*\}", text, re.DOTALL)
    if not m:
        raise ValueError("judge returned no JSON object")
    return json.loads(m.group(0))


def _truncate_skill_text(raw: str, max_chars: int = 12000) -> str:
    """Truncate to max_chars, but cut at a line boundary and mark the truncation."""
    if len(raw) <= max_chars:
        return raw
    cut = raw[:max_chars]
    # Back up to the last newline so we don't split a line.
    last_nl = cut.rfind("\n")
    if last_nl > max_chars * 0.8:  # don't back up too far
        cut = cut[:last_nl]
    return cut + "\n\n[... truncated ...]\n"


def run_l2(doc: SkillDoc, config: JudgeConfig | None) -> L2Result | None:
    """Return an L2Result, or None if L2 is disabled / unrecoverable."""
    if config is None:
        return None

    warnings: list[str] = []
    skill_text = _truncate_skill_text(doc.raw, 12000)

    # Accumulators for cost / latency accounting across both calls.
    total_elapsed = 0.0
    total_prompt_tokens = 0
    total_completion_tokens = 0
    total_retries = 0

    # Step 1: generate probes
    try:
        probes_raw, usage, elapsed, retries = _chat(config, PROBE_GEN_TEMPLATE.format(skill_text=skill_text))
        total_elapsed += elapsed
        total_prompt_tokens += usage.get("prompt_tokens", 0)
        total_completion_tokens += usage.get("completion_tokens", 0)
        total_retries += retries
        m = re.search(r"\[.*\]", probes_raw, re.DOTALL)
        if m:
            probes = json.loads(m.group(0))
        else:
            probes = []
            warnings.append("probe generation returned no JSON array; continuing without probes")
    except Exception as exc:  # noqa: BLE001 - optional LLM review falls back to L1
        probes = []
        warnings.append(f"probe generation failed ({exc}); continuing without probes")

    probe_text = "\n".join(f"{i + 1}. {p}" for i, p in enumerate(probes)) or "(none generated)"

    # Step 2: get verdict
    try:
        verdict, usage, elapsed, retries = _chat(
            config, JUDGE_PROMPT_TEMPLATE.format(skill_text=skill_text, probes=probe_text)
        )
        total_elapsed += elapsed
        total_prompt_tokens += usage.get("prompt_tokens", 0)
        total_completion_tokens += usage.get("completion_tokens", 0)
        total_retries += retries
    except Exception as exc:  # noqa: BLE001 - optional LLM review falls back to L1
        warnings.append(f"LLM judge call failed: {exc}")
        return None

    try:
        data = _extract_json(verdict)
    except ValueError as exc:
        warnings.append(f"could not parse judge JSON: {exc}")
        return None

    return L2Result(
        trigger_accuracy=float(data.get("trigger_accuracy", 0)),
        boundary_robustness=float(data.get("boundary_robustness", 0)),
        instruction_clarity=float(data.get("instruction_clarity", 0)),
        output_verifiability=float(data.get("output_verifiability", 0)),
        rationale=str(data.get("rationale", "")),
        ambiguous=data.get("ambiguous_probes", []),
        prompt_hash=prompt_hash(JUDGE_PROMPT_TEMPLATE),
        model=config.model,
        warnings=warnings,
        duration_seconds=round(total_elapsed, 2),
        prompt_tokens=total_prompt_tokens,
        completion_tokens=total_completion_tokens,
        total_tokens=total_prompt_tokens + total_completion_tokens,
        retries=total_retries,
    )
