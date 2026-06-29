"""Optional LLM second pass — the silent-bug class the heuristic can't see.

Phase-4 hybrid (bench-justified). The regex heuristic in reflection.py catches
EXPLICIT failures (is_error / non-zero exit). It is blind, by design, to a tool
call that SUCCEEDS yet whose output reports a failure the assistant left
unaddressed (a test that printed FAILED on exit 0, a build warning, a "0 rows"
where rows were expected). The bench showed a dedicated model catches exactly
this class — at real per-session $ + latency, so this pass is OPT-IN
(`paw reflect --llm`) and the live hooks stay heuristic-only by default.

Cost is bounded two ways: (1) a local regex pre-filter keeps only successful
results that look suspicious — if none, there is NO API call ($0); (2) at most
_MAX_SUSPECT outputs go in a single batched call. The model is host-uniform
(DeepSeek) so lesson quality doesn't depend on which agent ran the session, and
it speaks over plain HTTPS so it works inside a Claude Code session (unlike a
nested `claude`). Network/parse failure → [] (the heuristic result still stands).

This module is imported only on the --llm path, keeping reflection.py (the hook
hot path) free of any network import.
"""

from __future__ import annotations

import json
import os
import re
import urllib.request
from typing import Callable

from .reflection import Candidate, _cmd_of, _terms

# DeepSeek pricing per 1M tokens — VERIFY at platform.deepseek.com/pricing.
DEEPSEEK_URL = "https://api.deepseek.com/chat/completions"
_MAX_SUSPECT = 6          # cap outputs sent in one call — bounds tokens/$
_MAX_OUT_CHARS = 600      # truncate each output before sending

# a successful result that nonetheless smells like an unaddressed failure
_SUSPECT = re.compile(
    r"\bFAILED\b|\bFAIL\b|\berror[: ]|\bexception\b|traceback|assertionerror|"
    r"did not|does not match|mismatch|expected .{0,30}\bgot\b|"
    r"\b0 (?:rows|results|matches|tests)\b|deprecat|\bwarning:|\bE\d{3}\b",
    re.I,
)

Caller = Callable[[str], str]   # prompt → raw model content (for tests)


def suspicious(events: list[dict]) -> list[dict]:
    """Successful tool events whose output looks like a hidden failure."""
    return [e for e in events
            if not e.get("is_error") and _SUSPECT.search(str(e.get("text", "")))][:_MAX_SUSPECT]


def _render(events: list[dict]) -> str:
    blocks = []
    for i, e in enumerate(events, 1):
        blocks.append(f"[{i}] command: {_cmd_of(e)}\noutput:\n{str(e.get('text',''))[:_MAX_OUT_CHARS]}")
    return "\n\n".join(blocks)


def _deepseek(prompt: str, key: str) -> str:
    body = json.dumps({
        "model": "deepseek-chat",
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0,
        "response_format": {"type": "json_object"},
    }).encode()
    req = urllib.request.Request(DEEPSEEK_URL, data=body, headers={
        "Authorization": f"Bearer {key}", "Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=60) as r:
        resp = json.loads(r.read())
    return resp["choices"][0]["message"]["content"]


def silent_bug_candidates(
    events: list[dict],
    *,
    api_key: str | None = None,
    caller: Caller | None = None,
) -> list[Candidate]:
    """Confirm genuine silent bugs among the suspicious successful results.

    ``caller`` overrides the network (tests). Returns [] on no suspects, missing
    key, or any failure — the heuristic pass is never blocked."""
    suspects = suspicious(events)
    if not suspects:
        return []
    key = api_key or os.environ.get("DEEPSEEK_API_KEY")
    if not key and caller is None:
        return []

    prompt = (
        "You review tool calls from an AI coding agent that ALL returned success "
        "(no error flag). Some outputs nonetheless reveal a real failure the agent "
        "may have left unaddressed (a failing test, a build warning, an empty result "
        "where data was expected). Identify ONLY those genuine silent bugs; ignore "
        "normal/expected output. Return JSON "
        '{"silent_bugs":[{"index":N,"summary":"trigger -> what was missed"}]}.\n\n'
        + _render(suspects)
    )
    try:
        raw = caller(prompt) if caller else _deepseek(prompt, key)
        found = json.loads(raw).get("silent_bugs", [])
    except (ValueError, OSError, AttributeError, KeyError):
        return []

    out: list[Candidate] = []
    for item in found:
        if not isinstance(item, dict):
            continue
        summary = str(item.get("summary", "")).strip()
        if not summary:
            continue
        idx = item.get("index")
        ev = suspects[idx - 1] if isinstance(idx, int) and 1 <= idx <= len(suspects) else {}
        out.append(Candidate(
            type="silent-bug",
            signal="llm-silent",
            trigger=summary[:170],
            detail="",
            raw=(f"$ {_cmd_of(ev)}\n{str(ev.get('text',''))}" if ev else summary)[:600],
            terms=_terms(summary + " " + _cmd_of(ev)),
            # LLM-inferred silent bug: more signal than a heuristic miss (it
            # confirmed a real exit-0 failure), but still inferred, not
            # deterministic. Mid confidence — must prove itself via recurrence
            # before it earns a SHOUT voice.
            confidence=0.45,
        ))
    return out
