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


# --------------------------------------------------------------------------- #
# transcript parsing (stdlib, fail-soft per line)
# --------------------------------------------------------------------------- #
def iter_entries(path: str | Path) -> Iterator[dict]:
    p = Path(path)
    if not p.exists():
        return
    for line in p.read_text(encoding="utf-8", errors="ignore").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            obj = json.loads(line)
        except ValueError:
            continue
        if isinstance(obj, dict):
            yield obj


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
        if inp.get("file_path"):
            return f"{event.get('name')} {inp['file_path']}"[:160]
    return str(event.get("name") or "?")


def _first_err_line(text: str) -> str:
    for line in (text or "").splitlines():
        line = line.strip()
        if line:
            return line[:140]
    return "(no output)"


def _tool_events(entries: list[dict]) -> list[dict]:
    """Ordered tool_use events joined to their tool_result by tool_use_id."""
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


def _exec_candidates(events: list[dict]) -> list[Candidate]:
    out: list[Candidate] = []
    for i, ev in enumerate(events):
        if not ev["is_error"]:
            continue
        if _NON_ERROR.search(ev["text"]):   # user denial / nah guard — not a mistake
            continue
        cmd = _cmd_of(ev)
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


def _misalign_candidates(entries: list[dict]) -> list[Candidate]:
    out: list[Candidate] = []
    for e in entries:
        if e.get("type") != "user" or _is_meta(e):
            continue
        blocks = _content_blocks(e)
        # a real user turn, not a tool_result carrier
        if any(isinstance(b, dict) and b.get("type") == "tool_result" for b in blocks):
            continue
        text = " ".join(
            b.get("text", "") for b in blocks
            if isinstance(b, dict) and b.get("type") == "text"
        ).strip()
        # terse turns only — long turns are specs/instructions that merely mention
        # a correction word, not corrections themselves
        if not text or len(text) > _MISALIGN_MAXLEN or not _CORRECTION.search(text):
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


def scan_transcript(entries: Iterator[dict] | list[dict]) -> list[Candidate]:
    entries = list(entries)
    cands = _exec_candidates(_tool_events(entries)) + _misalign_candidates(entries)
    seen: set[str] = set()
    uniq: list[Candidate] = []
    for c in cands:
        fp = c.fingerprint
        if fp in seen:
            continue
        seen.add(fp)
        uniq.append(c)
    return uniq[:_MAX_CANDIDATES]


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

    def to_dict(self) -> dict:
        return {
            "transcript": self.transcript,
            "stored": self.stored,
            "wrote": self.wrote,
            "candidates": [
                {"type": c.type, "signal": c.signal, "trigger": c.trigger, "detail": c.detail}
                for c in self.candidates
            ],
        }

    def render(self) -> str:
        if not self.candidates:
            return "🔍 reflect: no mistake candidates in transcript"
        verb = f"stored {self.stored}" if self.wrote else "would store"
        out = [f"🔍 reflect: {verb} → ICM pending ({len(self.candidates)} candidate(s))"]
        for c in self.candidates:
            out.append(f"  • [{c.type}/{c.signal}] {c.content[:120]}")
        return "\n".join(out)


def capture(
    transcript_path: str | Path,
    *,
    session_id: str = "",
    store_runner: StoreRunner | None = None,
    write: bool = True,
) -> CaptureResult:
    """Scan a transcript → park coarse candidates in ICM ``pending``. Never raises."""
    runner = store_runner or _default_store
    try:
        candidates = scan_transcript(iter_entries(transcript_path))
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
    return CaptureResult(str(transcript_path), candidates, stored, write)
