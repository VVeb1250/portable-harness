"""Effectiveness governance — the one thing ICM lacks.

ICM stores corrections but NEVER distrusts one that keeps failing (persists by
decay alone regardless of whether it actually solved future problems — no
confidence, no miss-rate, no 'this fix didn't work'). That is paw's genuine add
ON TOP of the composed store: a tiny side-ledger overlay, memory-id → miss count.

A memory recalled while its error RECURS earns a miss; past a threshold it is
distrusted and paw suppresses / down-ranks it from an ICM recall result. paw
never writes ICM's DB — this is an overlay, poison-safe and reversible.

Storage reuses the lean jsonl primitives (`store.py`); every public call is
fail-safe so a broken ledger can never break a recall.
"""

from __future__ import annotations

import json

from . import store

_FILE = "governance.jsonl"
MISS_DISTRUST = 3   # an ICM memory whose fix fails this often → suppressed


def _path():
    return store.global_dir() / _FILE


def load() -> dict[str, int]:
    """mem_id → miss_count. {} on any error (governance must never break recall)."""
    try:
        text = _path().read_text(encoding="utf-8", errors="replace")
    except OSError:
        return {}
    out: dict[str, int] = {}
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            r = json.loads(line)
            if isinstance(r, dict) and r.get("id"):
                out[str(r["id"])] = int(r.get("miss", 0))
        except (json.JSONDecodeError, TypeError, ValueError):
            continue
    return out


def _save(d: dict[str, int]) -> None:
    store._write_jsonl_raw(
        _path(),
        [json.dumps({"id": i, "miss": m}, ensure_ascii=False) for i, m in d.items()],
    )


def record_miss(mem_id: str) -> None:
    """An error recurred despite this ICM memory being recalled — bump its miss."""
    if not mem_id:
        return
    try:
        with store.locked(_path()):
            d = load()
            d[mem_id] = d.get(mem_id, 0) + 1
            _save(d)
    except Exception:
        pass


def distrusted_ids(*, threshold: int = MISS_DISTRUST) -> set[str]:
    """ICM memory ids whose fix keeps failing → suppress. {} on any error."""
    try:
        return {i for i, m in load().items() if m >= threshold}
    except Exception:
        return set()


def forget(mem_id: str) -> bool:
    """Reset one id's miss counter (re-trust it). True if it existed."""
    try:
        with store.locked(_path()):
            d = load()
            if mem_id not in d:
                return False
            del d[mem_id]
            _save(d)
        return True
    except Exception:
        return False
