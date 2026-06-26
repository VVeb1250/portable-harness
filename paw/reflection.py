"""paw reflect — capture mistake candidates from a session transcript into ICM.

Phase 2 of docs/MEMORY-PLAN.md. Capture is deliberately COARSE: it scans a
finished session's transcript for multi-signal mistake candidates and parks them
in the ICM ``pending`` topic with a provisional type guess. It does NOT extract
the final lesson or write the wiki — that is curation (Phase 3), which runs later
and reconciles against existing memory. Capture favours recall over precision;
curation discards false positives.

Signals (CC / Codex transcript JSONL — assistant ``message.content[]`` holds
``tool_use`` blocks, results ride user ``tool_result`` blocks with ``is_error``):

  - execution-error : tool_use whose result ``is_error`` is true; a later success
                      on the same tool is recorded as the in-session fix. Reliable.
  - misalignment    : a real user turn carrying a strong correction marker
                      (revert / wrong / ผิด / กดผิด). Heuristic, partial — gated
                      hard to keep ``pending`` lean (owner's core worry = noise).
  - silent-bug      : NOT captured here — undetectable in-session; needs a later
                      test-fail/revert or an explicit flag (cross-session only).

Host-agnostic: any host emitting the Claude hook transcript contract (CC today;
Codex schema pending verify). Hook-safe: capture never raises across the boundary.
``paw reflect --capture [--transcript PATH]`` (else reads the Stop-hook stdin).
"""

from __future__ import annotations

import json
import os
import platform
import re
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Iterator

StoreRunner = Callable[[list[str]], int]

_WORD = re.compile(r"[^\W_]+", re.UNICODE)
PENDING_TOPIC = "pending"
_MAX_CANDIDATES = 8          # cap per session — pending stays lean
_MISALIGN_MAXLEN = 240       # real corrections are terse; long turns = specs/instructions
_STOP = {
    "the", "and", "for", "that", "this", "with", "not", "was", "are", "from",
    "have", "you", "your", "use", "using", "into", "out", "via", "but", "all",
}

# strong correction markers only — soft cues ("instead", "maybe") are too noisy
_CORRECTION = re.compile(
    r"\b(revert|undo|rollback|roll back|that'?s wrong|that'?s not|"
    r"wrong (?:approach|file|fix|way)|not what i|don'?t do that)\b"
    r"|ไม่ใช่|กดผิด|อย่าเพิ่ง|ย้อนกลับ|แก้ใหม่|ทำผิด",
    re.I,
)

# is_error=True that is NOT an execution mistake: user denial/interrupt, or the
# nah guard doing its job. These are signals, not lessons — never capture them.
_NON_ERROR = re.compile(
    r"doesn'?t want to proceed|tool use was rejected|user (?:rejected|cancelled|interrupted)|"
    r"nah blocked|operation was aborted|request was aborted|cancelled by user|"
    r"requested.{0,20}stop",
    re.I,
)

# Mechanical agent/harness-contract errors (read-before-write, stale-edit, no-match).
# Already enforced by the tool layer and recovered in-session — storing them as
# "lessons" adds nothing the harness doesn't already force. Pure pending noise.
_HARNESS_NOISE = re.compile(
    r"file has not been read yet|string to replace not found|"
    r"file has (?:already )?been (?:read|modified)|"
    r"has been (?:unexpectedly )?modified since|"
    r"no replacement was performed|old_string|"
    r"must read the file|cannot apply edit",
    re.I,
)

# Test-runner output. A failing test during normal red→green TDD is expected
# iteration, not a mistake — this is the single biggest pending-flood source
# (HANDOFF: "...F [100%] → fixed by ..."). Suppress exec candidates whose error
# text is a test report.
_TEST_FAIL = re.compile(
    r"=+ (?:FAILURES|ERRORS|short test summary) =+|"
    r"\b\d+ failed(?:,| \b)|\bFAILED\s|\bF+\s*\[\s*\d+%\]|"
    r"\btests? failed\b",
    re.I,
)

# Throwaway inline probes (py -c / python -c / node -e). Scratch one-liners used to
# poke at state during exploration — a failure here is iteration, not a workflow
# lesson worth remembering.
_PROBE_CMD = re.compile(r"^\s*(?:py|python\d?|node)\s+-[ce]\b", re.I)

# The user waving off their own slip ("misclicked, continue") rather than correcting
# the agent's approach. The correction marker fires on the slip word but the turn
# dismisses it — only a strong, agent-directed marker survives a dismissal.
_DISMISSAL = re.compile(
    r"\b(?:continue|proceed|go on|carry on|keep going|never ?mind|ignore (?:that|it)|as you were)\b"
    r"|ต่อเลย|ต่อได้เลย|เอาต่อ|ไปต่อ|ทำต่อ|ช่างมัน|ข้ามไป|ไม่เป็นไร",
    re.I,
)
_STRONG_CORRECTION = re.compile(
    r"\b(?:revert|undo|rollback|roll back|wrong (?:approach|file|fix|way)|"
    r"that'?s (?:wrong|not)|don'?t do that)\b|ไม่ใช่|ย้อนกลับ|แก้ใหม่|ทำผิด",
    re.I,
)


# --------------------------------------------------------------------------- #
# transcript parsing (stdlib, fail-soft per line)
# --------------------------------------------------------------------------- #
def iter_entries(path: str | Path, start_line: int = 0) -> Iterator[dict]:
    """Parsed entries from ``start_line`` onward (0-based, fail-soft per line)."""
    entries, _ = read_entries(path, start_line)
    yield from entries


def read_entries(path: str | Path, start_line: int = 0) -> tuple[list[dict], int]:
    """Return (entries from start_line onward, total physical line count).

    The line count is the watermark for incremental capture: CC's Stop hook fires
    once per agent turn, so re-scanning the whole transcript each time would flood
    ``pending`` with duplicates. Callers persist the returned total and pass it
    back as ``start_line`` next turn so only new lines are scanned.
    """
    p = Path(path)
    if not p.exists():
        return [], start_line
    lines = p.read_text(encoding="utf-8", errors="ignore").splitlines()
    out: list[dict] = []
    for line in lines[start_line:]:
        line = line.strip()
        if not line:
            continue
        try:
            obj = json.loads(line)
        except ValueError:
            continue
        if isinstance(obj, dict):
            out.append(obj)
    return out, len(lines)


# --------------------------------------------------------------------------- #
# per-session watermark (incremental capture across per-turn Stop firings)
# --------------------------------------------------------------------------- #
def _watermark_path(session_id: str) -> Path:
    safe = re.sub(r"[^A-Za-z0-9_.-]", "_", session_id)[:48] or "nosession"
    return Path(os.path.expanduser("~/.paw/state/reflect")) / f"{safe}.json"


def load_watermark(session_id: str) -> int:
    if not session_id:
        return 0
    try:
        return int(json.loads(_watermark_path(session_id).read_text(encoding="utf-8"))["line"])
    except (OSError, ValueError, KeyError, TypeError):
        return 0


def newest_codex_transcript(session_id: str = "") -> str:
    """Best-effort resolve a Codex rollout when the Stop stdin omits a transcript
    path (its hook payload shape is unverified). Prefer the rollout whose filename
    carries the session id (Codex names files rollout-<ts>-<uuid>.jsonl); else the
    most recent. Returns '' if none — capture then safely no-ops."""
    import glob
    base = os.path.expanduser("~/.codex/sessions")
    files = sorted(glob.glob(os.path.join(base, "**", "*.jsonl"), recursive=True))
    if not files:
        return ""
    if session_id:
        tail = session_id.split("-")[-1] if "-" in session_id else session_id
        matched = [f for f in files if tail and tail in os.path.basename(f)]
        if matched:
            return matched[-1]
    return files[-1]


def save_watermark(session_id: str, line: int) -> None:
    if not session_id:
        return
    try:
        p = _watermark_path(session_id)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps({"line": line}), encoding="utf-8")
    except OSError:
        pass


def _is_meta(entry: dict) -> bool:
    """Injected, non-conversational turns (compact summary, meta) — never a lesson."""
    return bool(entry.get("isCompactSummary") or entry.get("isMeta"))


def _content_blocks(entry: dict) -> list:
    msg = entry.get("message") or {}
    content = msg.get("content")
    if isinstance(content, list):
        return content
    if isinstance(content, str):
        return [{"type": "text", "text": content}]
    return []


def _flatten(content) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return " ".join(
            b.get("text", "") for b in content
            if isinstance(b, dict) and b.get("type") == "text"
        )
    return ""


def _terms(text: str) -> tuple[str, ...]:
    seen: list[str] = []
    for w in _WORD.findall((text or "").lower()):
        if len(w) >= 4 and w not in _STOP and w not in seen:
            seen.append(w)
        if len(seen) >= 6:
            break
    return tuple(seen)


# --------------------------------------------------------------------------- #
# candidate model
# --------------------------------------------------------------------------- #
@dataclass
class Candidate:
    type: str            # execution | misalignment
    signal: str          # is_error | fail-fix | correction
    trigger: str         # short, retrieval-phrased
    detail: str          # one-line context (the fix / what was wanted)
    raw: str = ""        # verbatim error or command excerpt
    terms: tuple[str, ...] = ()

    @property
    def content(self) -> str:
        return f"{self.trigger} → {self.detail}" if self.detail else self.trigger

    @property
    def fingerprint(self) -> str:
        return re.sub(r"\s+", " ", self.trigger.lower()).strip()[:80]


# --------------------------------------------------------------------------- #
# signal scanners
# --------------------------------------------------------------------------- #
def _cmd_of(event: dict) -> str:
    inp = event.get("input") or {}
    if isinstance(inp, dict):
        if inp.get("command"):
            return str(inp["command"]).strip().splitlines()[0][:160]
        if inp.get("file_path") or inp.get("path"):
            return f"{event.get('name')} {inp.get('file_path') or inp.get('path')}"[:160]
    return str(event.get("name") or "?")


def _first_err_line(text: str) -> str:
    for line in (text or "").splitlines():
        line = line.strip()
        if line:
            return line[:140]
    return "(no output)"


def _tool_events(entries: list[dict], host: str = "claude-code") -> list[dict]:
    """Normalize a transcript into ordered tool events {name,input,is_error,text}.

    Host-dispatched: Claude Code uses ``message.content[]`` tool_use/tool_result
    blocks paired by tool_use_id; Codex rollouts use ``response_item`` payloads
    (function_call / custom_tool_call → *_output) paired by call_id, with the error
    signal derived from the output's ``Exit code:`` line."""
    return _tool_events_codex(entries) if host == "codex" else _tool_events_cc(entries)


def _tool_events_cc(entries: list[dict]) -> list[dict]:
    results: dict[str, tuple[bool, str]] = {}
    uses: list[tuple[str, dict, str]] = []
    for e in entries:
        etype = e.get("type")
        for b in _content_blocks(e):
            if not isinstance(b, dict):
                continue
            if etype == "assistant" and b.get("type") == "tool_use":
                uses.append((b.get("name") or "?", b.get("input") or {}, b.get("id") or ""))
            elif b.get("type") == "tool_result":
                results[b.get("tool_use_id") or ""] = (
                    bool(b.get("is_error")),
                    _flatten(b.get("content")),
                )
    events = []
    for name, inp, tid in uses:
        is_err, text = results.get(tid, (False, ""))
        events.append({"name": name, "input": inp, "is_error": is_err, "text": text})
    return events


def _codex_output(output) -> tuple[bool, str]:
    """Codex tool output is a string like 'Exit code: N\\nWall time..\\nOutput:\\n..'.
    is_error = a non-zero exit code (the explicit signal); exit-0-with-failure is the
    silent-bug class left to the LLM pass, mirroring CC's is_error semantics."""
    s = str(output or "")
    m = re.search(r"Exit code:\s*(\d+)", s)
    is_err = bool(m and int(m.group(1)) != 0)
    body = s.split("Output:\n", 1)[1] if "Output:\n" in s else s
    return is_err, body.strip()


def _tool_events_codex(entries: list[dict]) -> list[dict]:
    calls: dict[str, tuple[str, dict]] = {}
    results: dict[str, tuple[bool, str]] = {}
    order: list[str] = []
    for e in entries:
        if e.get("type") != "response_item":
            continue
        p = e.get("payload") or {}
        pt = p.get("type")
        if pt in ("function_call", "custom_tool_call"):
            cid = p.get("call_id") or p.get("id") or ""
            raw_args = p.get("arguments")
            inp: dict = {}
            if isinstance(raw_args, str):
                try:
                    inp = json.loads(raw_args)
                except ValueError:
                    inp = {"command": raw_args}
            elif isinstance(p.get("input"), dict):
                inp = p["input"]
            if not isinstance(inp, dict):
                inp = {}
            calls[cid] = (p.get("name") or "?", inp)
            order.append(cid)
            if pt == "custom_tool_call" and p.get("status") not in (None, "completed"):
                results.setdefault(cid, (True, f"status={p.get('status')}"))
        elif pt in ("function_call_output", "custom_tool_call_output"):
            results[p.get("call_id") or ""] = _codex_output(p.get("output"))
    return [
        {"name": calls[cid][0], "input": calls[cid][1],
         "is_error": results.get(cid, (False, ""))[0], "text": results.get(cid, (False, ""))[1]}
        for cid in order
    ]


def _user_texts(entries: list[dict], host: str = "claude-code") -> list[str]:
    """Real (non-meta) user-turn texts, host-normalized."""
    out: list[str] = []
    if host == "codex":
        for e in entries:
            if e.get("type") != "response_item":
                continue
            p = e.get("payload") or {}
            if p.get("type") != "message" or p.get("role") != "user":
                continue
            text = " ".join(
                b.get("text", "") for b in (p.get("content") or [])
                if isinstance(b, dict) and b.get("type") == "input_text"
            ).strip()
            if text:
                out.append(text)
        return out
    for e in entries:
        if e.get("type") != "user" or _is_meta(e):
            continue
        blocks = _content_blocks(e)
        if any(isinstance(b, dict) and b.get("type") == "tool_result" for b in blocks):
            continue
        text = " ".join(
            b.get("text", "") for b in blocks
            if isinstance(b, dict) and b.get("type") == "text"
        ).strip()
        if text:
            out.append(text)
    return out


def _exec_candidates(events: list[dict]) -> list[Candidate]:
    out: list[Candidate] = []
    for i, ev in enumerate(events):
        if not ev["is_error"]:
            continue
        if _NON_ERROR.search(ev["text"]):   # user denial / nah guard — not a mistake
            continue
        cmd = _cmd_of(ev)
        # noise gates: mechanical harness errors, TDD red-phase test output, and
        # throwaway inline probes are expected iteration, not durable lessons.
        if _HARNESS_NOISE.search(ev["text"]) or _TEST_FAIL.search(ev["text"]):
            continue
        if _PROBE_CMD.match(cmd):
            continue
        err = _first_err_line(ev["text"])
        fix = ""
        for nxt in events[i + 1:]:
            if nxt["name"] == ev["name"] and not nxt["is_error"]:
                fix = _cmd_of(nxt)
                break
        out.append(Candidate(
            type="execution",
            signal="fail-fix" if fix else "is_error",
            trigger=f"{ev['name']} failed: {err}"[:170],
            detail=(f"fixed by: {fix}" if fix else "no in-session fix found")[:170],
            raw=f"$ {cmd}\n{ev['text']}"[:600],
            terms=_terms(f"{ev['name']} {cmd} {err}"),
        ))
    return out


def _misalign_candidates(texts: list[str]) -> list[Candidate]:
    out: list[Candidate] = []
    for text in texts:
        # terse turns only — long turns are specs/instructions that merely mention
        # a correction word, not corrections themselves
        if len(text) > _MISALIGN_MAXLEN or not _CORRECTION.search(text):
            continue
        # a self-slip waved off ("misclicked, continue") is a dismissal, not a
        # correction of the agent — only a strong agent-directed marker survives it
        if _DISMISSAL.search(text) and not _STRONG_CORRECTION.search(text):
            continue
        snippet = re.sub(r"\s+", " ", text)[:130]
        out.append(Candidate(
            type="misalignment",
            signal="correction",
            trigger=f"user correction: {snippet}",
            detail="",
            raw=text[:400],
            terms=_terms(text),
        ))
    return out


def dedup_cap(cands: list[Candidate]) -> list[Candidate]:
    seen: set[str] = set()
    uniq: list[Candidate] = []
    for c in cands:
        fp = c.fingerprint
        if fp in seen:
            continue
        seen.add(fp)
        uniq.append(c)
    return uniq[:_MAX_CANDIDATES]


def scan_transcript(entries: Iterator[dict] | list[dict], host: str = "claude-code") -> list[Candidate]:
    entries = list(entries)
    cands = (_exec_candidates(_tool_events(entries, host))
             + _misalign_candidates(_user_texts(entries, host)))
    return dedup_cap(cands)


# --------------------------------------------------------------------------- #
# ICM write (pending topic)
# --------------------------------------------------------------------------- #
def _icm_exe() -> str:
    return "icm.exe" if platform.system() == "Windows" else "icm"


def _default_store(cmd: list[str]) -> int:
    try:
        return subprocess.run(cmd, check=False, capture_output=True, text=True, timeout=10).returncode
    except (OSError, subprocess.SubprocessError):
        return 1


def _store_cmd(c: Candidate, session_id: str) -> list[str]:
    kws = [f"type:{c.type}", f"signal:{c.signal}"]
    if session_id:
        kws.append(f"session:{session_id[:12]}")
    kws.extend(c.terms)
    cmd = [_icm_exe(), "store", "-t", PENDING_TOPIC, "-c", c.content,
           "-i", "medium", "-k", ",".join(kws)]
    if c.raw:
        cmd += ["-r", c.raw]
    return cmd


@dataclass
class CaptureResult:
    transcript: str
    candidates: list[Candidate]
    stored: int
    wrote: bool
    next_line: int = 0

    def to_dict(self) -> dict:
        return {
            "transcript": self.transcript,
            "stored": self.stored,
            "wrote": self.wrote,
            "next_line": self.next_line,
            "candidates": [
                {"type": c.type, "signal": c.signal, "trigger": c.trigger, "detail": c.detail}
                for c in self.candidates
            ],
        }

    def render(self) -> str:
        if not self.candidates:
            return "🔍 reflect: no mistake candidates in new transcript lines"
        verb = f"stored {self.stored}" if self.wrote else "would store"
        out = [f"🔍 reflect: {verb} → ICM pending ({len(self.candidates)} candidate(s))"]
        for c in self.candidates:
            out.append(f"  • [{c.type}/{c.signal}] {c.content[:120]}")
        return "\n".join(out)


def capture(
    transcript_path: str | Path,
    *,
    session_id: str = "",
    start_line: int = 0,
    host: str = "claude-code",
    llm: bool = False,
    llm_caller=None,
    store_runner: StoreRunner | None = None,
    write: bool = True,
) -> CaptureResult:
    """Scan a transcript from ``start_line`` → park coarse candidates in ICM
    ``pending``. Never raises. ``next_line`` is the new watermark to persist.

    ``llm`` adds the opt-in silent-bug second pass (DeepSeek; bench-justified) on
    top of the heuristic — off on the hook hot path to keep per-turn Stop cheap."""
    runner = store_runner or _default_store
    next_line = start_line
    try:
        entries, next_line = read_entries(transcript_path, start_line)
        candidates = scan_transcript(entries, host)
        if llm or llm_caller is not None:
            from paw.reflect_llm import silent_bug_candidates
            extra = silent_bug_candidates(_tool_events(entries, host), caller=llm_caller)
            candidates = dedup_cap(candidates + extra)
    except Exception:
        candidates = []
    stored = 0
    if write:
        for c in candidates:
            try:
                if runner(_store_cmd(c, session_id)) == 0:
                    stored += 1
            except Exception:
                continue
    return CaptureResult(str(transcript_path), candidates, stored, write, next_line)
