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

from .surface_context import SurfaceContext, build_surface_context, infer_intents
from .sets.loader import CuratedSet, load_all

_WORD = re.compile(r"[^\W_]+", re.UNICODE)
_MIN_PROMPT = 8
_SET_FLOOR = 2.0       # min trigger score for a set to surface
_MAX_SETS = 2
_MAX_MEM = 2
_MEM_IMPORTANCE = {"high", "critical"}
_INTENT_BOOSTS: dict[str, dict[str, float]] = {
    "repo_handoff": {"repo-pack": 5.0, "context-workbench": -2.0},
    "bulk_context": {"context-workbench": 5.0, "doc-data-min": -1.0},
    "affected_tests": {"test-affected": 5.0},
    "code_impact": {"code-intelligence": 4.0, "efficiency-min": 1.0},
    "code_search": {"efficiency-min": 4.0, "code-intelligence": -1.0},
    "docs_lookup": {"context-quality": 5.0, "web-research": -1.0},
    "api_contract": {"api-quality": 5.0},
    "browser_action": {"browser-automation": 5.0, "doc-data-min": -2.0},
    "ui_quality": {"design-quality": 5.0, "browser-automation": -1.0},
    "data_query": {"doc-data-min": 5.0, "context-workbench": -1.0},
    "doc_extract": {"doc-data-min": 5.0},
    "security_gate": {"secure-agent": 5.0, "quality-gate": 2.0},
    "web_research": {"web-research": 5.0, "context-quality": -1.0},
}

RecallRunner = Callable[[str], str]
LinkState = Literal["absent", "healthy", "degraded", "drifted"]
AdoptionPosture = Literal["default", "task-specific", "conditional", "detect-first", "deferred"]


def _norm(text: str) -> str:
    return (text or "").lower()


def _tokens(text: str) -> set[str]:
    return set(_WORD.findall(_norm(text)))


def _phrase_matches(trigger: str, prompt_norm: str, toks: set[str]) -> bool:
    """Match triggers as words/phrases, never as substrings inside code words.

    This prevents noisy hits such as ``SurfaceDecision`` matching the
    ``decision`` memory trigger, ``build_plan`` matching ``ui``, or
    ``dashboard`` matching ``data``.
    """
    tn = _norm(trigger).strip()
    if not tn:
        return False
    words = _WORD.findall(tn)
    if len(words) == 1:
        return words[0] in toks
    boundary = rf"(?<!\w){re.escape(tn)}(?!\w)"
    return re.search(boundary, prompt_norm) is not None or all(w in toks for w in words)


# --------------------------------------------------------------------------- #
# curated-set matching (lexical, deterministic)
# --------------------------------------------------------------------------- #
def _score_set(
    s: CuratedSet,
    prompt_norm: str,
    toks: set[str],
    intents: frozenset[str] = frozenset(),
) -> float:
    """Phrase hit = 2.0; all words of a phrase present (any order) = 1.0."""
    score = 0.0
    for trig in s.trigger_terms:
        tn = _norm(trig).strip()
        if not tn:
            continue
        boundary = rf"(?<!\w){re.escape(tn)}(?!\w)"
        if re.search(boundary, prompt_norm):
            score += 2.0
        elif _phrase_matches(tn, prompt_norm, toks):
            score += 1.0
    for intent in intents:
        score += _INTENT_BOOSTS.get(intent, {}).get(s.name, 0.0)
    return score


def match_sets(
    prompt: str,
    limit: int = _MAX_SETS,
    *,
    context: SurfaceContext | None = None,
) -> list[tuple[CuratedSet, float]]:
    ctx = context or build_surface_context(prompt)
    routing_text = ctx.routing_text() or prompt
    pn, toks = _norm(routing_text), _tokens(routing_text)
    intents = infer_intents(ctx)
    # Router outcome loop: stop surfacing capability sets the user keeps ignoring.
    # Test seam (_OUTCOMES_PROBE) lets tests assert loop behavior without touching
    # the real ledger. Fail-closed to "no demotion" on any error.
    if _OUTCOMES_PROBE is not None:
        demoted, _mark = _OUTCOMES_PROBE
    else:
        try:
            from .memory.outcomes import demoted_names
            demoted = demoted_names()
        except Exception:
            demoted = set()
    candidates = (s for s in load_all() if s.name not in demoted)
    scored = ((s, _score_set(s, pn, toks, intents)) for s in candidates)
    hits = sorted((x for x in scored if x[1] >= _SET_FLOOR), key=lambda x: -x[1])
    hits = hits[:limit]
    # Count the emission AFTER demotion/dedup filtering — only sets actually
    # surfaced count toward the suggest tally. Fail-safe no-op.
    if hits:
        try:
            if _OUTCOMES_PROBE is not None:
                _mark([s.name for s, _ in hits])
            else:
                from .memory.outcomes import mark_suggested
                mark_suggested([s.name for s, _ in hits])
        except Exception:
            pass
    return hits


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
# test seam: inject the outcome-loop's (demoted_names, mark_suggested_fn) pair so
# tests can assert loop behavior WITHOUT touching the real ~/.paw ledger. When
# None, the production path reads/writes the real ledger (fail-safe no-op on
# any error). NOTE: production callers never set this — it is for tests only.
_OUTCOMES_PROBE: tuple[set[str], Callable[[list[str]], None]] | None = None


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


def _rung_routing(
    s: CuratedSet,
    prompt: str,
    cwd: str | None = None,
    context: SurfaceContext | None = None,
) -> list[str]:
    """Matched concrete rung commands for a set already known healthy."""
    rules = s.usage_routing
    if not rules:
        return []
    ctx = context or build_surface_context(prompt, cwd=cwd)
    routing_text = ctx.routing_text() or prompt
    pn, toks = _norm(routing_text), _tokens(routing_text)
    hits: list[str] = []
    for rule in rules:
        needs = str(rule.get("needs", "")).strip()
        installed = not needs or _which(needs, cwd)
        if not installed:
            continue
        when = rule.get("when", [])
        matched = any(_phrase_matches(str(w), pn, toks) for w in when)
        if matched:
            use = str(rule.get("use", "")).strip()
            if use:
                hits.append(use)
    return hits


def set_routing(
    s: CuratedSet,
    prompt: str,
    cwd: str | None = None,
    *,
    context: SurfaceContext | None = None,
) -> list[str] | None:
    """Return concrete rung hints only after the set is linked and healthy.

    ``None`` means "do not suggest use"; caller should offer apply/verify based
    on ``set_link_state``. An empty list means the set is healthy but no
    sub-intent rule matched this prompt.
    """
    if set_link_state(s, cwd) != "healthy":
        return None
    return _rung_routing(s, prompt, cwd, context=context)


def _set_next_action(s: CuratedSet) -> str:
    """Small, non-mutating-first hint when a matching set is not live."""
    posture = set_adoption_posture(s)
    if posture == "detect-first":
        return f"paw plan {s.name} (detect first)"
    if posture == "conditional":
        return f"paw plan {s.name} (conditional)"
    if posture == "deferred":
        return f"paw plan {s.name} (deferred)"
    if posture == "task-specific":
        return f"paw plan {s.name} (task-specific)"
    if s.link_scope == "project":
        return f"paw apply {s.name} (project-linked)"
    if s.default_init:
        return f"paw apply {s.name} (foundation)"
    return f"paw apply {s.name}"


def set_adoption_posture(s: CuratedSet) -> AdoptionPosture:
    """Classify whether a set belongs in daily habits or only a task gate.

    This is intentionally conservative: only ``default_init`` sets may become
    baseline habits. Ready-but-optional sets still need an explicit plan/use
    moment, because otherwise the router turns quality/capability tools into
    ambient nagging.
    """
    if s.default_init:
        return "default"
    if s.catalog_status == "detect-first" or s.link_scope == "detect-first":
        return "detect-first"
    if s.catalog_status in {"deferred", "candidate"}:
        return "deferred"
    if s.catalog_status == "conditional" or s.link_scope == "conditional":
        return "conditional"
    return "task-specific"


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
    # Suppress memories whose recalled fix keeps failing (effectiveness overlay).
    # Fail-closed to "no filtering" if the ledger is unreadable.
    try:
        from .memory.distrust import distrusted_ids
        suppressed = distrusted_ids()
    except Exception:
        suppressed = set()
    out: list[dict] = []
    for m in memories:
        if not isinstance(m, dict):
            continue
        if m.get("importance") not in _MEM_IMPORTANCE:
            continue
        if suppressed and str(m.get("id", "")) in suppressed:
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
    context: SurfaceContext | None = None,
) -> str:
    """Additional-context block for the prompt, or '' when nothing is strong.

    Never raises: any failure collapses to '' so the hook stays safe.
    """
    try:
        if not prompt or len(prompt.strip()) < _MIN_PROMPT:
            return ""
        parts: list[str] = []
        ctx = context or build_surface_context(prompt, cwd=cwd)

        sets = match_sets(prompt, context=ctx)
        if sets:
            lines = ["🐾 paw sets:"]
            for s, _ in sets:
                desc = (s.description or "").strip().splitlines()[0][:70]
                state = set_link_state(s, cwd or ctx.cwd)
                if state == "healthy":
                    routing = _rung_routing(s, prompt, cwd or ctx.cwd, context=ctx)
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
        # Session inject dedup: a lesson already injected this session (within
        # the ttl) doesn't re-surface — pure context rot otherwise. Pull-path
        # `paw recall` is on-demand and skips this. Fail-closed to no dedup.
        if session_id and lessons:
            try:
                from .memory import sessionlog
                already = sessionlog.seen(session_id)
                if already:
                    lessons = [m for m in lessons
                               if str(m.get("id", "")) not in already]
                if lessons:
                    sessionlog.mark(session_id, [str(m.get("id", "")) for m in lessons])
            except Exception:
                pass  # dedup unavailable — inject the lesson anyway
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
