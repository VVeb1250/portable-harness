"""paw curate — promote ICM ``pending`` capture candidates into the wiki (Phase 3).

Phase 3 of docs/MEMORY-PLAN.md. Capture (Phase 2) parks coarse candidates in the
``pending`` topic. Curation reconciles each against the existing wiki and either
promotes it to a real lesson or folds it into a recurrence counter, then clears
the pending entry. This is the Mem0 reconcile step over ICM primitives.

Reconcile decides one of three ops (the safe 80% — deterministic, no LLM):

  - **ADD**  : no near-duplicate in the wiki → store a new ``mistakes`` lesson
               (``seen:1``, carries the provisional ``type:``).
  - **BUMP** : a near-duplicate exists (Jaccard ≥ _DUP over summaries) → don't
               write a second copy; increment its ``seen:N`` and escalate
               importance on recurrence (seen≥3 → critical). This is the
               recurrence signal the whole memory loop is built to earn.
  - **SKIP** : an apply error — leave the pending entry for the next pass.

UPDATE-with-content-merge and DELETE-obsolete are intentionally NOT automated
here: rewriting a lesson's text or retiring it needs the judgement of the
reflection model (Phase 4 bench arms), not token overlap. Every processed
candidate's pending entry is forgotten regardless, so ``pending`` drains.

Cross-link (``related_ids``) is deferred — the ICM CLI exposes no flag for it and
flat recall is the locked 80% (plan decision #5).
"""

from __future__ import annotations

import json
import os
import platform
import re
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

from .memory_mesh import MemoryMesh, MeshScope
from .recall import icm_recall

_WORD = re.compile(r"[^\W_]+", re.UNICODE)
WIKI_TOPIC = "mistakes"
PENDING_TOPIC = "pending"
_DUP = 0.5                       # Jaccard ≥ this over summaries → near-dup → bump


def _env_int(name: str, default: int) -> int:
    """Bounded env override so a stray env cannot zero out a safety threshold."""
    raw = os.environ.get(name)
    if not raw:
        return default
    try:
        value = int(raw)
    except ValueError:
        return default
    return value if value > 0 else default


# pending-count thresholds drive the hook nudge (Layer 2) and the dry-run
# auto-preview. Tunable via env so owners can adapt without code edits.
PENDING_WARN = _env_int("PAW_PENDING_WARN", 30)
PENDING_CRITICAL = _env_int("PAW_PENDING_CRITICAL", 80)

# MeshLock that serialises the write path across Claude/Codex/Z Code Stop hooks
# firing close together. Opt out with PAW_CURATE_LOCK=0 (single-host / manual).
_CURATE_LOCK_TTL = 120
_CURATE_LOCK_NAME = "curate-write"
_CURATE_SCOPE = MeshScope(project="portable-harness", run_id="curate")


def _curate_lock_enabled() -> bool:
    return os.environ.get("PAW_CURATE_LOCK", "1") != "0"
_RANK = {"low": 0, "medium": 1, "high": 2, "critical": 3}
_RANK_INV = {v: k for k, v in _RANK.items()}

StrRunner = Callable[[list[str]], str]    # → stdout
RcRunner = Callable[[list[str]], int]     # → returncode
RecallFn = Callable[[str], list[dict]]


def _icm_exe() -> str:
    return "icm.exe" if platform.system() == "Windows" else "icm"


def _run_out(cmd: list[str]) -> str:
    try:
        return subprocess.run(cmd, check=False, capture_output=True, text=True, timeout=10).stdout or ""
    except (OSError, subprocess.SubprocessError):
        return ""


def _run_rc(cmd: list[str]) -> int:
    try:
        return subprocess.run(cmd, check=False, capture_output=True, text=True, timeout=10).returncode
    except (OSError, subprocess.SubprocessError):
        return 1


def _tokens(text: str) -> set[str]:
    return {w for w in _WORD.findall((text or "").lower()) if len(w) >= 3}


def _jaccard(a: set[str], b: set[str]) -> float:
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


def _seen_of(keywords) -> int:
    for k in keywords or []:
        m = re.fullmatch(r"seen:(\d+)", str(k))
        if m:
            return int(m.group(1))
    return 1


def _escalate(seen: int, current: str) -> str:
    """Recurrence raises importance, never lowers an already-higher one."""
    target = "critical" if seen >= 3 else "high" if seen >= 2 else "medium"
    return _RANK_INV[max(_RANK.get(target, 1), _RANK.get(current, 1))]


def _bump_keywords(keywords, seen: int) -> list[str]:
    out = [str(k) for k in (keywords or []) if not re.fullmatch(r"seen:\d+", str(k))]
    out.append(f"seen:{seen}")
    return out


# --------------------------------------------------------------------------- #
# pending listing + reconcile
# --------------------------------------------------------------------------- #
def list_pending(runner: StrRunner | None = None) -> list[dict]:
    runner = runner or _run_out
    cmd = [_icm_exe(), "list", "-t", PENDING_TOPIC, "--format", "json",
           "--no-embeddings", "--read-only"]
    try:
        data = json.loads(runner(cmd) or "[]")
    except ValueError:
        return []
    return [m for m in data if isinstance(m, dict)] if isinstance(data, list) else []


def pending_count(runner: StrRunner | None = None) -> int:
    """Cheap count of pending candidates without parsing content.

    Used by the memory hook (Layer 2) to decide whether to nudge the agent. A
    failed or malformed ICM response returns 0 — the hook must never crash an
    agent turn because curation telemetry is unavailable.
    """
    try:
        return len(list_pending(runner))
    except Exception:
        return 0


@dataclass
class Decision:
    pending_id: str
    op: str                       # add | bump | skip
    content: str
    importance: str
    keywords: list[str] = field(default_factory=list)
    target_id: str = ""
    score: float = 0.0
    reason: str = ""

    def to_dict(self) -> dict:
        return {
            "pending_id": self.pending_id, "op": self.op, "importance": self.importance,
            "target_id": self.target_id, "score": round(self.score, 3),
            "reason": self.reason, "content": self.content[:120],
        }


def reconcile(pending: dict, recall_fn: RecallFn | None = None) -> Decision:
    recall_fn = recall_fn or (lambda q: icm_recall(q, limit=5))
    summary = str(pending.get("summary", "")).strip()
    pid = str(pending.get("id", ""))
    pkw = [str(k) for k in (pending.get("keywords") or [])]
    ptype = next((k for k in pkw if k.startswith("type:")), "type:execution")
    terms = [k for k in pkw if ":" not in k]

    best, best_s = None, 0.0
    ptoks = _tokens(summary)
    for m in recall_fn(summary) or []:
        if not isinstance(m, dict) or m.get("topic") == PENDING_TOPIC:
            continue
        s = _jaccard(ptoks, _tokens(str(m.get("summary", ""))))
        if s > best_s:
            best, best_s = m, s

    if best is not None and best_s >= _DUP:
        seen = _seen_of(best.get("keywords")) + 1
        return Decision(
            pending_id=pid, op="bump",
            content=str(best.get("summary", "")),
            importance=_escalate(seen, str(best.get("importance", "medium"))),
            keywords=_bump_keywords(best.get("keywords"), seen),
            target_id=str(best.get("id", "")), score=best_s,
            reason=f"near-dup of {str(best.get('id',''))[:8]} (j={best_s:.2f}) → seen={seen}",
        )

    return Decision(
        pending_id=pid, op="add", content=summary,
        importance=str(pending.get("importance", "medium")),
        keywords=[ptype, *terms[:6], "seen:1"], score=best_s,
        reason="new lesson" + (f" (closest j={best_s:.2f})" if best_s else ""),
    )


# --------------------------------------------------------------------------- #
# apply
# --------------------------------------------------------------------------- #
def _apply(d: Decision, store: RcRunner, update: RcRunner, forget: RcRunner) -> bool:
    icm = _icm_exe()
    kw = ",".join(d.keywords)
    if d.op == "add":
        rc = store([icm, "store", "-t", WIKI_TOPIC, "-c", d.content, "-i", d.importance, "-k", kw])
    elif d.op == "bump":
        rc = update([icm, "update", d.target_id, "-c", d.content, "-i", d.importance, "-k", kw])
    else:
        return False
    if rc != 0:
        return False
    forget([icm, "forget", d.pending_id])   # drain pending regardless of forget rc
    return True


@dataclass
class CurateResult:
    decisions: list[Decision]
    applied: int
    wrote: bool
    reason: str = ""

    @property
    def counts(self) -> dict:
        c = {"add": 0, "bump": 0, "skip": 0}
        for d in self.decisions:
            c[d.op] = c.get(d.op, 0) + 1
        return c

    def to_dict(self) -> dict:
        return {"applied": self.applied, "wrote": self.wrote, "counts": self.counts,
                "reason": self.reason,
                "decisions": [d.to_dict() for d in self.decisions]}

    def render(self, surface: bool = False) -> str:
        if not self.decisions:
            base = "" if surface else "🧹 curate: pending is empty"
            if surface and self.reason:
                return f"🧹 curate: {self.reason}"
            return base
        c = self.counts
        head = (f"🧹 curate: {len(self.decisions)} pending — "
                f"add={c['add']} bump={c['bump']} skip={c['skip']}"
                + ("" if self.wrote else " (dry-run)"))
        out = [head]
        for d in self.decisions:
            out.append(f"  • [{d.op}·{d.importance}] {d.content[:80]} — {d.reason}")
        if self.reason:
            out.append(f"  note: {self.reason}")
        return "\n".join(out)


def pending_preview(*, limit: int | None = None) -> str:
    """One-line dry-run summary suitable for a hook context block.

    Returns "" when pending is empty or ICM is unavailable — the hook must
    stay quiet when there is nothing actionable.
    """
    try:
        result = curate(write=False, limit=limit)
    except Exception:
        return ""
    if not result.decisions:
        return ""
    c = result.counts
    n = len(result.decisions)
    return (f"🧹 paw: {n} pending → would ADD {c['add']}, BUMP {c['bump']}, "
            f"SKIP {c['skip']}. Run `paw curate` to apply.")


def curate(
    *,
    list_runner: StrRunner | None = None,
    recall_fn: RecallFn | None = None,
    store_runner: RcRunner | None = None,
    update_runner: RcRunner | None = None,
    forget_runner: RcRunner | None = None,
    write: bool = True,
    limit: int | None = None,
) -> CurateResult:
    """Reconcile every pending candidate into the wiki; drain pending. Never raises.

    When ``write=True`` and the cross-host lock is enabled (default), the write
    path is serialised through ``MemoryMesh.acquire_lock`` so that Claude/Codex/
    Z Code Stop hooks firing close together cannot race the store/forget cycle
    and double-bump the same lesson. If the lock is already held, the call
    returns an empty write-less result with ``reason`` set rather than writing.
    """
    store = store_runner or _run_rc
    update = update_runner or _run_rc
    forget = forget_runner or _run_rc
    try:
        pend = list_pending(list_runner)
    except Exception:
        pend = []
    if limit is not None:
        pend = pend[:limit]
    decisions = [reconcile(p, recall_fn) for p in pend]

    # Dry-run never needs the lock and never writes.
    if not write:
        return CurateResult(decisions, applied=0, wrote=False)

    # No work to persist: skip the lock entirely so an empty pending queue
    # never creates a coordination file.
    if not decisions:
        return CurateResult(decisions, applied=0, wrote=False)

    applied = 0
    if not _curate_lock_enabled():
        applied = _apply_all(decisions, store, update, forget)
        return CurateResult(decisions, applied=applied, wrote=True)

    owner = _curate_lock_owner()
    mesh = MemoryMesh()
    acquired = mesh.acquire_lock(
        _CURATE_SCOPE,
        name=_CURATE_LOCK_NAME,
        owner=owner,
        purpose="serialise curate write path across hosts",
        ttl_seconds=_CURATE_LOCK_TTL,
    )
    if acquired.status == "blocked":
        return CurateResult(
            decisions=decisions,
            applied=0,
            wrote=False,
            reason=f"another host ({acquired.locks[0].owner if acquired.locks else 'unknown'}) "
                   "is curating; re-run `paw curate` shortly",
        )
    try:
        applied = _apply_all(decisions, store, update, forget)
    finally:
        mesh.release_lock(_CURATE_SCOPE, name=_CURATE_LOCK_NAME, owner=owner)
    return CurateResult(decisions, applied=applied, wrote=True)


def _apply_all(
    decisions: list[Decision],
    store: RcRunner,
    update: RcRunner,
    forget: RcRunner,
) -> int:
    """Apply decisions defensively; downgrade to ``skip`` on any failure."""
    applied = 0
    for d in decisions:
        try:
            if _apply(d, store, update, forget):
                applied += 1
            else:
                d.op = "skip"
        except Exception:
            d.op = "skip"
    return applied


def _curate_lock_owner() -> str:
    """Stable owner id for the curate lock across a host's processes."""
    owner = f"host-{platform.node()}-pid-{os.getpid()}"
    # _validate_segment allows [A-Za-z0-9._-]; sanitize anything else.
    clean = re.sub(r"[^A-Za-z0-9._-]", "_", owner).strip("._-")
    return clean or "curate-host"
