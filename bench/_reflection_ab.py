"""Reflection capture A/B — heuristic vs DeepSeek, on a synthetic gold transcript.

Phase 4 of docs/MEMORY-PLAN.md. The capture step (paw/reflection.py) decides
which session events become mistake candidates. Two arms answer "is a dedicated
LLM worth it over the regex heuristic?":

  - **heuristic** : paw.reflection.scan_transcript — 0 LLM tokens, ~0 latency, $0
  - **deepseek**  : one DeepSeek chat call extracts mistakes from the rendered log

Gold transcript = planted TRUE mistakes (execution fail→fix, user correction)
plus DISTRACTORS that must NOT be captured (permission denial, nah-guard block,
compact summary, a long spec that merely mentions "revert"). Each item carries a
unique marker; a captured candidate "covers" an item iff its text holds the
marker. Deterministic, reproducible, no hand-labeling.

Metrics per arm: precision / recall / F1 over the gold set, plus the cost side
(captured count, false positives, LLM tokens, latency, $). DeepSeek runs over
plain HTTPS so it works INSIDE a Claude Code session (unlike nested `claude`).

Usage: py bench/_reflection_ab.py        (needs DEEPSEEK_API_KEY for the LLM arm)
"""

from __future__ import annotations

import json
import os
import sys
import time
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from paw.reflection import scan_transcript  # noqa: E402

# DeepSeek pricing per 1M tokens — VERIFY at platform.deepseek.com/pricing
# (load-bearing for the $ column only; tokens themselves come from the API usage).
PRICE_IN_PER_M = 0.27
PRICE_OUT_PER_M = 1.10
DEEPSEEK_URL = "https://api.deepseek.com/chat/completions"

# Natural substrings that survive an LLM paraphrase (gibberish tokens get dropped,
# which unfairly penalised the LLM arm). Lowercase match.
#   3 easy mistakes any faithful extractor gets + 1 HARD silent-bug (a failure that
#   rode a NON-error result, so the is_error heuristic is blind to it by design).
POS = ["bogis", "assertion", "wrong approach", "flaky"]   # must be captured
NEG = ["proceed", "nah block", "compact", "feature"]      # distractors — must NOT be


# --------------------------------------------------------------------------- #
# gold transcript
# --------------------------------------------------------------------------- #
def _asst(name, tid, **inp):
    return {"type": "assistant", "message": {"role": "assistant",
            "content": [{"type": "tool_use", "id": tid, "name": name, "input": inp}]}}


def _res(tid, content, is_error=None):
    b = {"tool_use_id": tid, "type": "tool_result", "content": content}
    if is_error is not None:
        b["is_error"] = is_error
    return {"type": "user", "message": {"role": "user", "content": [b]}}


def _user(text, **extra):
    return {"type": "user", "message": {"role": "user", "content": text}, **extra}


def gold_transcript() -> list[dict]:
    return [
        # TP1 — execution fail→fix
        _asst("Bash", "a", command="py -m paw bogis"),
        _res("a", "error: invalid choice 'bogis' ERRTOKENALPHA", is_error=True),
        _asst("Bash", "b", command="py -m paw sets list"),
        _res("b", "ok", is_error=False),
        # TP2 — execution fail, no in-session fix
        _asst("Bash", "c", command="pytest tests/"),
        _res("c", "AssertionError ASSERTGAMMA: expected 3 got 4", is_error=True),
        # TP3 — user correction (terse)
        _user("no revert that change, wrong approach"),
        # TP4 (HARD) — silent bug: the command RAN (is_error False) but its output
        # reports a failure the assistant left unaddressed. is_error heuristic is
        # blind here by design; a reading LLM may catch it. This is the value test.
        _asst("Bash", "g", command="pytest tests/flow"),
        _res("g", "=== 1 failed, 2 passed === test_foo FAILED (flaky timing assert)", is_error=False),
        # distractor — permission denial
        _asst("Edit", "d", file_path="x.py"),
        _res("d", "The user doesn't want to proceed with this tool use. DENYDELTA", is_error=True),
        # distractor — nah guard block
        _asst("Edit", "e", file_path="hook.py"),
        _res("e", "nah blocked: this tries to modify Claude Code hooks. NAHEPSILON", is_error=True),
        # distractor — compact summary turn mentioning correction words
        _user("This session continued. ไม่ใช่ revert wrong COMPACTZETA " * 4, isCompactSummary=True),
        # distractor — long spec that merely mentions "revert"
        _user("please build a new feature " + "x" * 250 + " and add a revert button LONGSPECETA"),
        # distractor — clean success
        _asst("Bash", "f", command="ls"),
        _res("f", "file1 file2", is_error=False),
    ]


# --------------------------------------------------------------------------- #
# scoring
# --------------------------------------------------------------------------- #
def score(captured_texts: list[str]) -> dict:
    blob = [t.lower() for t in captured_texts]
    tp = sum(any(m in t for t in blob) for m in POS)        # distinct POS covered
    fp = 0
    for t in blob:
        hits_pos = any(m in t for m in POS)
        hits_neg = any(m in t for m in NEG)
        if hits_neg or not hits_pos:        # leaked a distractor, or spurious
            fp += 1
    recall = tp / len(POS)
    precision = tp / (tp + fp) if (tp + fp) else 0.0
    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) else 0.0
    return {"precision": precision, "recall": recall, "f1": f1,
            "captured": len(captured_texts), "tp": tp, "fp": fp}


# --------------------------------------------------------------------------- #
# arms
# --------------------------------------------------------------------------- #
def arm_heuristic(entries: list[dict]) -> tuple[dict, dict]:
    t0 = time.perf_counter()
    cands = scan_transcript(entries)
    ms = (time.perf_counter() - t0) * 1000
    texts = [f"{c.trigger} {c.detail} {c.raw}" for c in cands]
    s = score(texts)
    s.update({"latency_ms": round(ms, 2), "llm_in_tok": 0, "llm_out_tok": 0, "usd": 0.0})
    return s, {"candidates": texts}


def _render(entries: list[dict]) -> str:
    lines = []
    for e in entries:
        role = e.get("type")
        msg = e.get("message", {})
        c = msg.get("content")
        if isinstance(c, str):
            tag = " [compact-summary]" if e.get("isCompactSummary") else ""
            lines.append(f"{role}{tag}: {c[:300]}")
        elif isinstance(c, list):
            for b in c:
                if b.get("type") == "tool_use":
                    lines.append(f"assistant tool_use {b.get('name')}: {json.dumps(b.get('input'))[:200]}")
                elif b.get("type") == "tool_result":
                    err = " ERROR" if b.get("is_error") else ""
                    lines.append(f"tool_result{err}: {str(b.get('content'))[:300]}")
    return "\n".join(lines)


def arm_deepseek(entries: list[dict], key: str) -> tuple[dict, dict]:
    prompt = (
        "You are a reflection engine reviewing an AI coding-agent session transcript. "
        "Extract ONLY genuine mistakes the ASSISTANT made: execution errors it had to "
        "fix, or points where the USER corrected the assistant. Do NOT include: "
        "permission denials, security-guard blocks, the compact-summary turn, or the "
        "user merely describing/requesting features. Return a JSON object "
        '{"mistakes":[{"type":"execution|misalignment","summary":"..."}]} and nothing else.\n\n'
        "TRANSCRIPT:\n" + _render(entries)
    )
    body = json.dumps({
        "model": "deepseek-chat",
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0,
        "response_format": {"type": "json_object"},
    }).encode()
    req = urllib.request.Request(DEEPSEEK_URL, data=body, headers={
        "Authorization": f"Bearer {key}", "Content-Type": "application/json"})
    t0 = time.perf_counter()
    with urllib.request.urlopen(req, timeout=60) as r:
        resp = json.loads(r.read())
    ms = (time.perf_counter() - t0) * 1000
    content = resp["choices"][0]["message"]["content"]
    usage = resp.get("usage", {})
    try:
        mistakes = json.loads(content).get("mistakes", [])
    except (ValueError, AttributeError):
        mistakes = []
    texts = [f"{m.get('type','')} {m.get('summary','')}" for m in mistakes]
    s = score(texts)
    in_tok, out_tok = usage.get("prompt_tokens", 0), usage.get("completion_tokens", 0)
    usd = in_tok / 1e6 * PRICE_IN_PER_M + out_tok / 1e6 * PRICE_OUT_PER_M
    s.update({"latency_ms": round(ms, 1), "llm_in_tok": in_tok, "llm_out_tok": out_tok,
              "usd": round(usd, 6)})
    return s, {"candidates": texts}


# --------------------------------------------------------------------------- #
def _row(name: str, s: dict) -> str:
    return (f"{name:<11}P={s['precision']:.2f} R={s['recall']:.2f} F1={s['f1']:.2f}  "
            f"cap={s['captured']} tp={s['tp']} fp={s['fp']}  "
            f"{s['latency_ms']:>7}ms  in/out={s['llm_in_tok']}/{s['llm_out_tok']}  ${s['usd']:.5f}")


def main() -> int:
    entries = gold_transcript()
    print(f"\nReflection capture A/B  (gold: {len(POS)} true mistakes, {len(NEG)} distractors)\n")

    h_s, h_d = arm_heuristic(entries)
    print(_row("heuristic", h_s))
    for t in h_d["candidates"]:
        print(f"   · {t[:90]}")

    out = {"heuristic": h_s}
    key = os.environ.get("DEEPSEEK_API_KEY")
    if key:
        try:
            d_s, d_d = arm_deepseek(entries, key)
            print(_row("deepseek", d_s))
            for t in d_d["candidates"]:
                print(f"   · {t[:90]}")
            out["deepseek"] = d_s
        except Exception as e:
            print(f"deepseek   arm failed: {type(e).__name__}: {str(e)[:80]}")
    else:
        print("deepseek   skipped (no DEEPSEEK_API_KEY)")

    print()
    print(json.dumps(out))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
