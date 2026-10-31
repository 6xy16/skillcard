"""Disk cache for L2 LLM judging.

Re-evaluating the same skill is expensive (LLM call + tokens + latency) and
non-deterministic. This cache stores the result of a completed L2 review keyed
on the *exact* inputs that produced it, so a repeat run is free and bit-stable.

Cache key = sha256 of:

    skill raw text + model + base_url + judge prompt hash + probe prompt hash

If any of those change (the skill was edited, the model swapped, the prompt
tuned, the endpoint moved), the key changes and the cache misses — we never
serve a stale verdict for a different input.

The cache is a plain JSON file per skill under a cache directory. It is
deliberately simple and transparent: open it and you can read the cached
verdict, probes, and token accounting.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict
from pathlib import Path

from skillcard.l2_judge import (
    JUDGE_PROMPT_TEMPLATE,
    PROBE_GEN_TEMPLATE,
    JudgeConfig,
    L2Result,
    run_l2,
)
from skillcard.models import prompt_hash
from skillcard.parser import SkillDoc

DEFAULT_CACHE_DIR = ".skillcard-cache"


def cache_key(doc: SkillDoc, config: JudgeConfig) -> str:
    """Deterministic cache key over the inputs that affect the verdict."""
    material = "\n".join(
        [
            doc.raw,
            config.model,
            config.base_url,
            prompt_hash(JUDGE_PROMPT_TEMPLATE),
            prompt_hash(PROBE_GEN_TEMPLATE),
        ]
    )
    return hashlib.sha256(material.encode("utf-8")).hexdigest()


def _cache_path(cache_dir: Path, key: str) -> Path:
    return cache_dir / f"{key}.json"


def _load(cache_dir: Path, key: str) -> L2Result | None:
    path = _cache_path(cache_dir, key)
    if not path.is_file():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    # Rebuild an L2Result from the stored dict. ``None`` scores round-trip as
    # JSON null, so n/a dimensions are preserved correctly.
    return L2Result(**data)


def _store(cache_dir: Path, key: str, result: L2Result) -> None:
    cache_dir.mkdir(parents=True, exist_ok=True)
    _cache_path(cache_dir, key).write_text(
        json.dumps(asdict(result), indent=2, ensure_ascii=False), encoding="utf-8"
    )


def run_l2_cached(
    doc: SkillDoc,
    config: JudgeConfig | None,
    cache_dir: Path | str = DEFAULT_CACHE_DIR,
) -> L2Result | None:
    """Run L2 with a disk cache.

    On a hit, returns the cached result with ``from_cache=True`` and does not
    call the LLM. On a miss, runs ``run_l2`` and stores the result.

    ``config=None`` (L2 disabled) returns ``None`` immediately, matching
    ``run_l2``.
    """
    if config is None:
        return None

    key = cache_key(doc, config)
    cached = _load(Path(cache_dir), key)
    if cached is not None:
        cached.from_cache = True
        return cached

    result = run_l2(doc, config)
    if result is not None:
        result.from_cache = False
        _store(Path(cache_dir), key, result)
    return result
