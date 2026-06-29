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

from .command_mistakes import ClassifyResult, classify
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


_CONF_RE = re.compile(r"^conf:([0-9]*\.?[0-9]+)$")


def _conf_of(keywords) -> float | None:
    """Parse the stored confidence tag. None if absent (legacy entry)."""
    for k in keywords or []:
        m = _CONF_RE.fullmatch(str(k))
        if m:
            try:
                return float(m.group(1))
            except ValueError:
                return None
    return None


def _escalate(seen: int, current: str) -> str:
    """Recurrence raises importance, never lowers an already-higher one."""
    target = "critical" if seen >= 3 else "high" if seen >= 2 else "medium"
    return _RANK_INV[max(_RANK.get(target, 1), _RANK.get(current, 1))]


def _bump_confidence(keywords, seen: int) -> float:
    """Recurrence nudges confidence up, capped at 1.0.

    Each repeat sighting (seen≥2) adds 0.1 — a lesson seen 3+ times has earned
    real trust even if its initial signal was weak (e.g. silent-bug). Legacy
    entries without a stored conf default to 0.5 and still get bumped.
    """
    base = _conf_of(keywords)
    if base is None:
        base = 0.5
    bump = 0.1 * max(0, seen - 1)
    return min(1.0, round(base + bump, 2))


def _bump_keywords(keywords, seen: int) -> list[str]:
    # Strip both seen:N and conf:X so we re-emit fresh, single copies of each.
    out = [
        str(k) for k in (keywords or [])
        if not re.fullmatch(r"seen:\d+", str(k)) and not _CONF_RE.fullmatch(str(k))
    ]
    out.append(f"seen:{seen}")
    out.append(f"conf:{_bump_confidence(keywords, seen):.2f}")
    return out


_TOOL_PREFIX = re.compile(
    r"^(?:shell_command|Bash|PowerShell|Write|Read|Grep|Glob)\s+failed:\s*",
    re.I,
)
_STRUCTURED_FAIL = re.compile(
    r"\bcommand=(?P<cmd>.*?)\s+\|\s+error=(?P<error>.*)",
    re.I,
)
_FIX_SUFFIX = re.compile(r"\s*(?:→|\?)?\s*fixed by:\s*(?P<fix>.*)$", re.I)
_NO_FIX_SUFFIX = re.compile(r"\s*(?:→|\?)?\s*no in-session fix found\s*$", re.I)


def _strip_tool_prefix(text: str) -> str:
    """Strip ``<tool> failed: `` prefix from captured error text."""
    return _TOOL_PREFIX.sub("", text, count=1)


def _strip_detail_suffix(text: str) -> str:
    return _NO_FIX_SUFFIX.sub("", _FIX_SUFFIX.sub("", text)).strip()


def trigger_from_pending(pending: dict) -> str:
    """Extract a command trigger from a pending entry for the classifier.

    When raw is empty (common for low-quality captures), falls back to
    the original summary *before* the ``→ fixed by:`` heuristic suffix.
    """
    raw = str(pending.get("raw", "") or "")
    lines = raw.splitlines()
    for line in lines:
        line = line.strip()
        if line.startswith("$ "):
            return line[2:].splitlines()[0][:160]
    if lines:
        return lines[0][:160]
    summary = str(pending.get("summary", ""))
    summary = _strip_detail_suffix(summary)
    m = _STRUCTURED_FAIL.search(summary)
    if m:
        return m.group("cmd").strip()[:160]
    return summary[:200]


def has_structured_command(pending: dict) -> bool:
    """True when capture preserved the attempted command, not just an error line."""
    raw = str(pending.get("raw", "") or "")
    if any(line.strip().startswith("$ ") for line in raw.splitlines()):
        return True
    return bool(_STRUCTURED_FAIL.search(str(pending.get("summary", "") or "")))


def error_from_pending(pending: dict) -> str:
    """Extract the original error text, without the command wrapper if present."""
    raw_text = str(pending.get("raw", "") or "")
    if raw_text.strip():
        lines = raw_text.splitlines()
        return lines[1].strip()[:200] if len(lines) > 1 else lines[0].strip()[:200]
    summary = str(pending.get("summary", "") or "")
    summary = _strip_detail_suffix(summary)
    m = _STRUCTURED_FAIL.search(summary)
    if m:
        return m.group("error").strip()[:200]
    return _strip_tool_prefix(summary)[:200]


def fix_from_pending(pending: dict) -> str:
    """Extract the in-session fix command from a pending summary, if present."""
    summary = str(pending.get("summary", "") or "")
    m = _FIX_SUFFIX.search(summary)
    return m.group("fix").strip()[:160] if m else ""


def _looks_like_command_failure(pending: dict) -> bool:
    summary = str(pending.get("summary", "") or "")
    raw = str(pending.get("raw", "") or "")
    return bool(raw.strip() or _STRUCTURED_FAIL.search(summary) or _TOOL_PREFIX.search(summary))


def _lesson_content(pending: dict, cr: ClassifyResult) -> str | None:
    """Turn a command classification into a durable, old-style lesson line."""
    cmd = trigger_from_pending(pending)
    err = error_from_pending(pending)
    fix = fix_from_pending(pending)
    if cr.category != "one-off":
        return f"{cr.summary} -> {cr.fix}" if cr.fix else cr.summary
    if fix and has_structured_command(pending):
        return f"Command `{cmd}` failed with `{err}` -> use `{fix}`"
    if _looks_like_command_failure(pending):
        return None
    return str(pending.get("summary", "")).strip()


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
class ApplyReceipt:
    """Tracks store/forget verification state for a single Decision.

    returncode == 0 is necessary but not sufficient — the new memory must
    be visible through the read path.  Forget is successful only when the
    pending id disappears from the pending list.
    """
    stored: bool = False
    visible: bool = False
    forgotten: bool = False
    reason: str = ""


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
    receipt: ApplyReceipt | None = None

    def to_dict(self) -> dict:
        base = {
            "pending_id": self.pending_id, "op": self.op, "importance": self.importance,
            "target_id": self.target_id, "score": round(self.score, 3),
            "reason": self.reason, "content": self.content[:120],
        }
        if self.receipt:
            base["receipt"] = {
                "stored": self.receipt.stored,
                "visible": self.receipt.visible,
                "forgotten": self.receipt.forgotten,
                "reason": self.receipt.reason,
            }
        return base


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

    # Classify command-error candidates if this looks like a command failure.
    # If the classifier returns "skip", downgrade the decision.
    if ptype == "type:execution":
        cr = classify(trigger_from_pending(pending), error_from_pending(pending))
        lesson = _lesson_content(pending, cr)
        if cr.op == "skip":
            return Decision(
                pending_id=pid, op="skip", content=summary,
                importance=str(pending.get("importance", "medium")),
                keywords=[ptype, *terms[:6]],
                score=best_s,
                reason=f"classifier skip ({cr.category}): {cr.summary[:80]}",
            )
        if lesson is None:
            return Decision(
                pending_id=pid, op="skip", content=summary,
                importance=str(pending.get("importance", "medium")),
                keywords=[ptype, *terms[:6]],
                score=best_s,
                reason="classifier skip (one-off): no reusable fix",
            )
        # Promote — keep the classifier metadata so render can mention it
        return Decision(
            pending_id=pid, op="add", content=lesson,
            importance=str(pending.get("importance", "medium")),
            keywords=[ptype, *cr.mistake_keywords()[:4], *terms[:3], "seen:1"],
            score=best_s,
            reason=f"new lesson ({cr.category})" + (f" (closest j={best_s:.2f})" if best_s else ""),
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
def list_topic(topic: str, runner: StrRunner | None = None) -> list[dict]:
    """List all entries in an ICM topic.  Used for store/forget verification."""
    runner = runner or _run_out
    cmd = [_icm_exe(), "list", "-t", topic, "--format", "json",
           "--no-embeddings", "--read-only"]
    try:
        data = json.loads(runner(cmd) or "[]")
    except ValueError:
        return []
    return [m for m in data if isinstance(m, dict)] if isinstance(data, list) else []


def _verify_visible(list_fn: StrRunner | None, d: Decision) -> bool:
    """Verify the newly stored memory is visible in the wiki topic.

    Only entries with topic == WIKI_TOPIC are considered. For bump ops only
    the target_id is checked (no jaccard fallback — wrong-ID entries with
    similar content must not be accepted).
    """
    try:
        entries = list_topic(WIKI_TOPIC, list_fn)
        for m in entries:
            if m.get("topic") != WIKI_TOPIC:
                continue
            if d.op == "bump":
                if str(m.get("id", "")) == d.target_id:
                    return True
                continue
            s1 = _tokens(d.content)
            s2 = _tokens(str(m.get("summary", "") or ""))
            if s1 and s2 and _jaccard(s1, s2) >= _DUP:
                return True
    except Exception:
        return False
    return False


def _verify_forget_drained(pending_id: str, list_fn: StrRunner | None) -> bool:
    """Verify the pending id is no longer in the pending list.

    Fail-closed: returns False when ICM is unreachable or returns
    unparseable output — an empty list from a healthy ICM is the
    only path to ``True``.
    """
    icm = _icm_exe()
    cmd = [icm, "list", "-t", PENDING_TOPIC, "--format", "json",
           "--no-embeddings", "--read-only"]
    try:
        raw = (list_fn or _run_out)(cmd)
    except Exception:
        return False
    if not raw or not raw.strip():
        return False
    try:
        data = json.loads(raw)
    except ValueError:
        return False
    if not isinstance(data, list):
        return False
    return not any(str(m.get("id", "")) == pending_id
                   for m in data if isinstance(m, dict))


def _apply(d: Decision, store: RcRunner, update: RcRunner, forget: RcRunner,
           list_fn: StrRunner | None = None) -> bool:
    icm = _icm_exe()
    kw = ",".join(d.keywords)
    if d.op == "add":
        rc = store([icm, "store", "-t", WIKI_TOPIC, "-c", d.content, "-i", d.importance, "-k", kw])
    elif d.op == "bump":
        rc = update([icm, "update", d.target_id, "-c", d.content, "-i", d.importance, "-k", kw])
    else:
        # Classified skip — drain pending entry without storing a wiki lesson.
        forget([icm, "forget", d.pending_id])
        drained = _verify_forget_drained(d.pending_id, list_fn)
        d.receipt = ApplyReceipt(
            stored=False, visible=False, forgotten=drained,
            reason=f"skip drain {'ok' if drained else 'forget may have failed'}",
        )
        return drained

    stored_ok = rc == 0
    if not stored_ok:
        d.receipt = ApplyReceipt(stored=False, reason=f"store returned {rc}")
        return False

    # VERIFY:  store returncode == 0 is necessary but not sufficient.
    visible = _verify_visible(list_fn, d)
    if not visible:
        d.receipt = ApplyReceipt(
            stored=True, visible=False,
            reason="store verification failed — memory not visible through read path",
        )
        return False

    forget_rc = forget([icm, "forget", d.pending_id])
    forgotten = forget_rc == 0 and _verify_forget_drained(d.pending_id, list_fn)
    receipt = ApplyReceipt(
        stored=True, visible=True, forgotten=forgotten,
        reason=("ok" if forgotten else
                f"forget returned {forget_rc} but pending item still visible in list"),
    )
    d.receipt = receipt
    return forgotten


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
    verify_runner: StrRunner | None = None,
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
        applied = _apply_all(decisions, store, update, forget, list_fn=verify_runner)
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
        applied = _apply_all(decisions, store, update, forget, list_fn=verify_runner)
    finally:
        mesh.release_lock(_CURATE_SCOPE, name=_CURATE_LOCK_NAME, owner=owner)
    return CurateResult(decisions, applied=applied, wrote=True)


def _apply_all(
    decisions: list[Decision],
    store: RcRunner,
    update: RcRunner,
    forget: RcRunner,
    *,
    list_fn: StrRunner | None = None,
) -> int:
    """Apply decisions defensively; downgrade to ``skip`` on any failure."""
    applied = 0
    for d in decisions:
        try:
            if _apply(d, store, update, forget, list_fn=list_fn):
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
