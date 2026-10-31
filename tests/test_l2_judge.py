"""Tests for the L2 LLM paper-review layer.

The OpenAI SDK is never called here: `_chat` is monkeypatched so the tests
are fast, deterministic, and cover the retry/timeout/accounting paths that
an interviewer will ask about.
"""

from __future__ import annotations

import pytest

from skillcard.l2_judge import JudgeConfig, L2Result, _chat, run_l2

# A valid verdict JSON the judge is expected to return.
_VERDICT_JSON = (
    '{"trigger_accuracy": 85, "boundary_robustness": 70, '
    '"instruction_clarity": 90, "output_verifiability": 80, '
    '"ambiguous_probes": [3, 7], "rationale": "mostly clear"}'
)

_USAGE = {"prompt_tokens": 120, "completion_tokens": 40, "total_tokens": 160}


def _cfg(**kw) -> JudgeConfig:
    return JudgeConfig(api_key="test-key", **kw)


def test_config_from_env_missing_key_returns_none(monkeypatch):
    monkeypatch.delenv("SKILLCARD_API_KEY", raising=False)
    assert JudgeConfig.from_env() is None


def test_config_from_env_reads_all_vars(monkeypatch):
    monkeypatch.setenv("SKILLCARD_API_KEY", "k")
    monkeypatch.setenv("SKILLCARD_BASE_URL", "http://x/v1")
    monkeypatch.setenv("SKILLCARD_MODEL", "m")
    monkeypatch.setenv("SKILLCARD_TIMEOUT", "30")
    cfg = JudgeConfig.from_env()
    assert cfg is not None
    assert cfg.base_url == "http://x/v1"
    assert cfg.model == "m"
    assert cfg.timeout == 30.0


def test_run_l2_returns_none_when_config_none(good_skill):
    assert run_l2(good_skill, None) is None


def _patch_openai(monkeypatch, create_fn):
    """Replace the `openai` module so `_chat`'s `from openai import OpenAI` works."""
    import sys

    fake = _FakeOpenAIModule(_FakeClient(create_fn))
    monkeypatch.setitem(sys.modules, "openai", fake)
    return fake


def test_chat_returns_content_usage_and_elapsed(monkeypatch):
    calls = {"n": 0}

    def fake_create(**kw):
        calls["n"] += 1
        return _FakeResp("hello", _USAGE)

    _patch_openai(monkeypatch, fake_create)
    content, usage, elapsed, retries = _chat(_cfg(), "prompt")
    assert content == "hello"
    assert usage["prompt_tokens"] == 120
    assert retries == 0
    assert elapsed >= 0
    assert calls["n"] == 1


def test_chat_retries_transient_error_then_succeeds(monkeypatch):
    calls = {"n": 0}

    def fake_create(**kw):
        calls["n"] += 1
        if calls["n"] < 3:
            raise TimeoutError("connection timed out")
        return _FakeResp("ok", _USAGE)

    _patch_openai(monkeypatch, fake_create)
    monkeypatch.setattr("skillcard.l2_judge.time.sleep", lambda s: None)
    content, _usage, _elapsed, retries = _chat(_cfg(), "prompt")
    assert content == "ok"
    assert retries == 2  # two failed attempts, third succeeded
    assert calls["n"] == 3


def test_chat_does_not_retry_non_transient_error(monkeypatch):
    calls = {"n": 0}

    def fake_create(**kw):
        calls["n"] += 1
        raise RuntimeError("401 unauthorized: bad api key")

    _patch_openai(monkeypatch, fake_create)
    monkeypatch.setattr("skillcard.l2_judge.time.sleep", lambda s: None)
    with pytest.raises(RuntimeError):
        _chat(_cfg(), "prompt")
    assert calls["n"] == 1  # no retry on auth error


def test_run_l2_success_aggregates_accounting(monkeypatch, good_skill):
    # First call (probe gen) and second call (verdict) both succeed.
    probe_out = '["probe one", "probe two"]'
    verdict_out = _VERDICT_JSON
    seq = [probe_out, verdict_out]

    def fake_chat(config, prompt):
        content = seq.pop(0)
        return content, _USAGE, 1.5, 0

    monkeypatch.setattr("skillcard.l2_judge._chat", fake_chat)
    result = run_l2(good_skill, _cfg(model="gpt-4o-mini"))
    assert isinstance(result, L2Result)
    assert result.trigger_accuracy == 85
    assert result.boundary_robustness == 70
    assert result.instruction_clarity == 90
    assert result.output_verifiability == 80
    assert result.ambiguous == [3, 7]
    assert result.model == "gpt-4o-mini"
    # Two calls x 1.5s each, tokens summed across both calls.
    assert result.duration_seconds == 3.0
    assert result.prompt_tokens == 240
    assert result.completion_tokens == 80
    assert result.total_tokens == 320
    assert result.retries == 0


def test_run_l2_probe_generation_failure_continues_without_probes(monkeypatch, good_skill):
    def fake_chat(config, prompt):
        if "generate 10 short user requests" in prompt:
            raise TimeoutError("probe gen failed")
        return _VERDICT_JSON, _USAGE, 1.0, 0

    monkeypatch.setattr("skillcard.l2_judge._chat", fake_chat)
    result = run_l2(good_skill, _cfg())
    assert result is not None
    assert result.trigger_accuracy == 85
    # Probe-gen failure is surfaced as a warning, not a fatal error.
    assert any("probe generation failed" in w for w in result.warnings)


def test_run_l2_verdict_failure_returns_none(monkeypatch, good_skill):
    def fake_chat(config, prompt):
        if "generate 10 short user requests" in prompt:
            return '["probe"]', _USAGE, 1.0, 0
        raise TimeoutError("judge call failed")

    monkeypatch.setattr("skillcard.l2_judge._chat", fake_chat)
    assert run_l2(good_skill, _cfg()) is None


def test_run_l2_unparseable_json_returns_none(monkeypatch, good_skill):
    def fake_chat(config, prompt):
        if "generate 10 short user requests" in prompt:
            return '["probe"]', _USAGE, 1.0, 0
        return "sorry, no JSON here", _USAGE, 1.0, 0

    monkeypatch.setattr("skillcard.l2_judge._chat", fake_chat)
    assert run_l2(good_skill, _cfg()) is None


# --- minimal fakes for the OpenAI SDK surface ---


class _FakeOpenAIModule:
    """Stand-in for the `openai` package; exposes OpenAI(api_key, base_url, timeout)."""

    def __init__(self, client):
        self._client = client

    def OpenAI(self, api_key=None, base_url=None, timeout=None):
        return self._client


class _FakeResp:
    def __init__(self, content, usage):
        self.choices = [_FakeChoice(content)]
        self.usage = _FakeUsage(**usage)


class _FakeChoice:
    def __init__(self, content):
        self.message = _FakeMessage(content)


class _FakeMessage:
    def __init__(self, content):
        self.content = content


class _FakeUsage:
    def __init__(self, prompt_tokens=0, completion_tokens=0, total_tokens=0):
        self.prompt_tokens = prompt_tokens
        self.completion_tokens = completion_tokens
        self.total_tokens = total_tokens


class _FakeClient:
    def __init__(self, create_fn):
        self.chat = _FakeChat(create_fn)


class _FakeChat:
    def __init__(self, create_fn):
        self.completions = _FakeCompletions(create_fn)


class _FakeCompletions:
    def __init__(self, create_fn):
        self._create = create_fn

    def create(self, **kw):
        return self._create(**kw)
