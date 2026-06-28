"""Hook bridge — surface matching curated sets + high-signal ICM memory.

Replaces the gutted ``portaw.adapters.router.paw_block``. Pure stdlib plus an
optional ICM subprocess; ANY failure returns ``""`` so the UserPromptSubmit
hook (shared by Claude Code and Codex via ~/.claude/hooks/skill-router.py)
never breaks a prompt. Two independent, fail-silent surfaces:

  - curated sets whose trigger_terms match the prompt (lexical, 0 subprocess)
  - L3 mistake lessons from ICM, gated by keyword overlap + importance so it
    stays quiet unless a lesson is genuinely relevant (ICM has no score cutoff,
    so we post-filter locally instead of surfacing every ranked hit)

The block is additive context; keep it lean — it rides every prompt.
"""

from __future__ import annotations

import json
import platform
import re
import shutil
import subprocess
from pathlib import Path
from typing import Callable, Literal

from .sets.loader import CuratedSet, load_all

_WORD = re.compile(r"[^\W_]+", re.UNICODE)
_MIN_PROMPT = 8
_SET_FLOOR = 2.0       # min trigger score for a set to surface
_MAX_SETS = 2
_MAX_MEM = 2
_MEM_IMPORTANCE = {"high", "critical"}

RecallRunner = Callable[[str], str]
LinkState = Literal["absent", "healthy", "degraded", "drifted"]


def _norm(text: str) -> str:
    return (text or "").lower()


def _tokens(text: str) -> set[str]:
    return set(_WORD.findall(_norm(text)))


# --------------------------------------------------------------------------- #
# curated-set matching (lexical, deterministic)
# --------------------------------------------------------------------------- #
def _score_set(s: CuratedSet, prompt_norm: str, toks: set[str]) -> float:
    """Phrase hit = 2.0; all words of a phrase present (any order) = 1.0."""
    score = 0.0
    for trig in s.trigger_terms:
        tn = _norm(trig)
        if tn and tn in prompt_norm:
            score += 2.0
        elif tn and all(w in toks for w in tn.split()):
            score += 1.0
    return score


def match_sets(prompt: str, limit: int = _MAX_SETS) -> list[tuple[CuratedSet, float]]:
    pn, toks = _norm(prompt), _tokens(prompt)
    scored = ((s, _score_set(s, pn, toks)) for s in load_all())
    hits = sorted((x for x in scored if x[1] >= _SET_FLOOR), key=lambda x: -x[1])
    return hits[:limit]


def _root(cwd: str | None) -> Path:
    return Path(cwd or ".").resolve()


def _which(binary: str, cwd: str | None = None) -> bool:
    """True if a rung binary resolves on PATH or in paw's vendored bin/."""
    if _PATH_PROBE is not None:
        return _PATH_PROBE(binary) is not None
    if shutil.which(binary) is not None:
        return True
    try:
        from .linker import resolve_binary

        return resolve_binary(binary, _root(cwd))[1] == "vendored"
    except Exception:
        return False


# test seam: swap the PATH lookup so live/install branches are deterministic.
_PATH_PROBE: Callable[[str], object] | None = None
# test seam: keep router tests independent of the real .paw ledger/filesystem.
_LINK_STATE_PROBE: Callable[[CuratedSet, str | None], LinkState] | None = None


def _ledger_records_for_set(data: dict, set_name: str) -> list[dict]:
    """Ledger records for a set across legacy and host-scoped keys."""
    records = []
    sets = data.get("sets", {})
    legacy = sets.get(set_name)
    if isinstance(legacy, dict):
        records.append(legacy)
    suffix = f":{set_name}"
    for key, record in sets.items():
        if key.endswith(suffix) and isinstance(record, dict):
            records.append(record)
    return records


def set_link_state(s: CuratedSet, cwd: str | None = None) -> LinkState:
    """Return whether paw has actually linked and verified enough to use a set.

    This deliberately does NOT treat a random binary on PATH as "live". The
    router rides every prompt, so this is a lightweight ledger/fingerprint check
    rather than a full mutating workflow. Any uncertainty collapses to absent.
    """
    if _LINK_STATE_PROBE is not None:
        return _LINK_STATE_PROBE(s, cwd)
    try:
        from .linker import (
            fingerprint,
            has_block,
            ledger_path,
            read_mcp_servers,
            resolve_binary,
        )

        root = _root(cwd)
        ledger = ledger_path(root)
        if not ledger.exists():
            return "absent"
        data = json.loads(ledger.read_text(encoding="utf-8"))
        records = _ledger_records_for_set(data, s.name)
        if not records:
            return "absent"
        record = next(
            (
                r for r in records
                if isinstance(r.get("context_path"), str)
                and Path(str(r["context_path"])).exists()
            ),
            records[0],
        )

        linked = False
        degraded = False
        drifted = False

        if s.non_mcp:
            ctx_raw = record.get("context_path")
            if not isinstance(ctx_raw, str):
                return "absent"
            ctx = Path(ctx_raw)
            if not ctx.is_absolute():
                ctx = root / ctx
            text = ctx.read_text(encoding="utf-8") if ctx.exists() else ""
            if not has_block(text, s.name):
                return "absent"
            linked = True
            after = record.get("after_fingerprint")
            if isinstance(after, str) and fingerprint(ctx) != after:
                drifted = True

        if s.mcp:
            mcp_wiring = record.get("mcp_wiring")
            if isinstance(mcp_wiring, dict):
                mcp_file = Path(str(mcp_wiring.get("mcp_file", "")))
                present = read_mcp_servers(mcp_file)
                missing = [n for n in mcp_wiring.get("servers", []) if n not in present]
                if missing:
                    degraded = True
                else:
                    linked = True
            elif not linked:
                return "absent"

        if not linked:
            return "absent"

        for tool in (*s.non_mcp, *s.mcp):
            binary = tool.get("health_binary")
            if binary and resolve_binary(binary, root)[1] == "missing":
                degraded = True

        if drifted:
            return "drifted"
        return "degraded" if degraded else "healthy"
    except Exception:
        return "absent"


def _rung_routing(s: CuratedSet, prompt: str, cwd: str | None = None) -> list[str]:
    """Matched concrete rung commands for a set already known healthy."""
    rules = s.usage_routing
    if not rules:
        return []
    pn, toks = _norm(prompt), _tokens(prompt)
    hits: list[str] = []
    for rule in rules:
        needs = str(rule.get("needs", "")).strip()
        installed = not needs or _which(needs, cwd)
        if not installed:
            continue
        when = rule.get("when", [])
        matched = any(
            (wn := _norm(w)) and (wn in pn or all(x in toks for x in wn.split()))
            for w in when
        )
        if matched:
            use = str(rule.get("use", "")).strip()
            if use:
                hits.append(use)
    return hits


def set_routing(s: CuratedSet, prompt: str, cwd: str | None = None) -> list[str] | None:
    """Return concrete rung hints only after the set is linked and healthy.

    ``None`` means "do not suggest use"; caller should offer apply/verify based
    on ``set_link_state``. An empty list means the set is healthy but no
    sub-intent rule matched this prompt.
    """
    if set_link_state(s, cwd) != "healthy":
        return None
    return _rung_routing(s, prompt, cwd)


def _set_next_action(s: CuratedSet) -> str:
    """Small, non-mutating-first hint when a matching set is not live."""
    if s.catalog_status == "detect-first" or s.link_scope == "detect-first":
        return f"paw plan {s.name} (detect first)"
    if s.catalog_status == "conditional" or s.link_scope == "conditional":
        return f"paw plan {s.name} (conditional)"
    if s.link_scope == "project":
        return f"paw apply {s.name} (project-linked)"
    if s.default_init:
        return f"paw apply {s.name} (foundation)"
    return f"paw apply {s.name}"


# --------------------------------------------------------------------------- #
# ICM memory recall (subprocess, fail-silent, keyword-gated)
# --------------------------------------------------------------------------- #
def _icm_exe() -> str:
    return "icm.exe" if platform.system() == "Windows" else "icm"


def _default_recall(prompt: str) -> str:
    cmd = [
        _icm_exe(), "recall", prompt.strip(),
        "--topic", "mistakes",
        "--limit", "5",
        "--format", "json",
        "--no-embeddings",
        "--read-only",
    ]
    out = subprocess.run(cmd, check=False, capture_output=True, text=True, timeout=8)
    return out.stdout or ""


def _relevant_lessons(prompt: str, runner: RecallRunner) -> list[dict]:
    """ICM ranks by relevance but gives no cutoff, so keep only high/critical
    lessons that share at least one keyword with the prompt."""
    try:
        raw = runner(prompt)
        memories = json.loads(raw) if raw.strip() else []
    except (ValueError, OSError, subprocess.SubprocessError):
        return []
    if not isinstance(memories, list):
        return []
    toks = _tokens(prompt)
    out: list[dict] = []
    for m in memories:
        if not isinstance(m, dict):
            continue
        if m.get("importance") not in _MEM_IMPORTANCE:
            continue
        kws = {str(k).lower() for k in (m.get("keywords") or [])}
        if not (kws & toks):
            continue
        out.append(m)
        if len(out) >= _MAX_MEM:
            break
    return out


# --------------------------------------------------------------------------- #
# the bridge
# --------------------------------------------------------------------------- #
def paw_block(
    prompt: str,
    cwd: str | None = None,
    session_id: str = "",
    *,
    recall_runner: RecallRunner | None = None,
) -> str:
    """Additional-context block for the prompt, or '' when nothing is strong.

    Never raises: any failure collapses to '' so the hook stays safe.
    """
    try:
        if not prompt or len(prompt.strip()) < _MIN_PROMPT:
            return ""
        parts: list[str] = []

        sets = match_sets(prompt)
        if sets:
            lines = ["🐾 paw sets:"]
            for s, _ in sets:
                desc = (s.description or "").strip().splitlines()[0][:70]
                state = set_link_state(s, cwd)
                if state == "healthy":
                    routing = _rung_routing(s, prompt, cwd)
                    if routing:
                        # live + sub-intent matched -> push the concrete rung(s) to USE now
                        lines.append(f"• {s.name} (live) → use:")
                        lines.extend(f"    → {hit}" for hit in routing[:2])
                    else:
                        # live but no specific rung matched -> compact reminder, no apply
                        lines.append(f"• {s.name} (live) — {desc}")
                elif state in {"degraded", "drifted"}:
                    lines.append(f"• {s.name} ({state}) — {desc} · paw verify {s.name}")
                else:
                    # not linked/verified yet -> install hint
                    lines.append(f"• {s.name} — {desc} · {_set_next_action(s)}")
            parts.append("\n".join(lines))

        lessons = _relevant_lessons(prompt, recall_runner or _default_recall)
        if lessons:
            lines = ["🧠 paw memory (high-signal lessons):"]
            for m in lessons:
                imp = m.get("importance", "high")
                summary = str(m.get("summary", "")).strip().replace("\n", " ")[:130]
                lines.append(f"• [{imp}] {summary}")
            parts.append("\n".join(lines))

        return "\n".join(parts)
    except Exception:
        return ""
