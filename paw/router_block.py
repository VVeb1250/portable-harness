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
import subprocess
from typing import Callable

from .sets.loader import CuratedSet, load_all

_WORD = re.compile(r"[^\W_]+", re.UNICODE)
_MIN_PROMPT = 8
_SET_FLOOR = 2.0       # min trigger score for a set to surface
_MAX_SETS = 2
_MAX_MEM = 2
_MEM_IMPORTANCE = {"high", "critical"}

RecallRunner = Callable[[str], str]


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
                lines.append(f"• {s.name} — {desc} · paw apply {s.name}")
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
