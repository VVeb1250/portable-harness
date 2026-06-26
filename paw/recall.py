"""paw recall — host-agnostic pull floor: ICM wiki + committed conventions.

The universal recall path: works on ANY host via CLI, no hook required.
Complements the push bridge (`router_block.paw_block`) — push is gated +
automatic on hook-capable hosts; pull is richer + on-demand everywhere.

One query unifies the two semantic stores without merging them: the
cross-host ICM brain (experiential lessons/mistakes/facts) AND the host's own
committed context file (CLAUDE.md / AGENTS.md / GEMINI.md — conventions/ADR).
Storage stays split; recall is unified (per the locked memory plan).
"""

from __future__ import annotations

import json
import platform
import re
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from .linker import HOST_CONTEXT

_WORD = re.compile(r"[^\W_]+", re.UNICODE)
Runner = Callable[[list[str]], str]


def _tokens(text: str) -> set[str]:
    return {w for w in _WORD.findall((text or "").lower()) if len(w) >= 3}


def _icm_exe() -> str:
    return "icm.exe" if platform.system() == "Windows" else "icm"


def _run(cmd: list[str]) -> str:
    out = subprocess.run(cmd, check=False, capture_output=True, text=True, timeout=8)
    return out.stdout or ""


def icm_recall(query: str, limit: int = 5, runner: Runner | None = None) -> list[dict]:
    """Top-K relevant ICM memories across all wiki topics. Fail-silent → []."""
    runner = runner or _run
    cmd = [
        _icm_exe(), "recall", query.strip(),
        "--limit", str(limit),
        "--format", "json",
        "--no-embeddings",
        "--read-only",
    ]
    try:
        raw = runner(cmd)
        data = json.loads(raw) if raw.strip() else []
    except (ValueError, OSError, subprocess.SubprocessError):
        return []
    return data if isinstance(data, list) else []


def grep_committed(query: str, host: str, root: Path, limit: int = 5) -> list[tuple[int, str]]:
    """Lines in the host's committed context file matching the query tokens."""
    name = HOST_CONTEXT.get(host)
    if not name:
        return []
    f = root / name
    if not f.exists():
        return []
    toks = _tokens(query)
    if not toks:
        return []
    hits: list[tuple[int, str, int]] = []
    for i, line in enumerate(f.read_text(encoding="utf-8", errors="ignore").splitlines(), 1):
        overlap = toks & _tokens(line)
        if overlap and line.strip():
            hits.append((i, line.strip()[:160], len(overlap)))
    hits.sort(key=lambda x: -x[2])
    return [(i, text) for i, text, _ in hits[:limit]]


@dataclass
class RecallResult:
    query: str
    icm: list[dict]
    committed: list[tuple[int, str]]
    host: str

    @property
    def empty(self) -> bool:
        return not self.icm and not self.committed

    def to_dict(self) -> dict:
        return {
            "query": self.query,
            "host": self.host,
            "icm": self.icm,
            "committed": [{"line": ln, "text": tx} for ln, tx in self.committed],
        }

    def render(self) -> str:
        if self.empty:
            return f'recall "{self.query}": no matches'
        out = [f'🧠 recall "{self.query}"']
        if self.icm:
            out.append("ICM (shared brain):")
            for m in self.icm:
                imp = m.get("importance", "?")
                topic = m.get("topic", "?")
                summary = str(m.get("summary", "")).strip().replace("\n", " ")[:140]
                out.append(f"  • [{imp}·{topic}] {summary}")
        if self.committed:
            name = HOST_CONTEXT.get(self.host, "context")
            out.append(f"committed ({name}):")
            for ln, text in self.committed:
                out.append(f"  • L{ln}: {text}")
        return "\n".join(out)


def recall(
    query: str,
    host: str = "claude-code",
    *,
    root: Path | None = None,
    limit: int = 5,
    icm_runner: Runner | None = None,
) -> RecallResult:
    root = root or Path.cwd()
    return RecallResult(
        query=query,
        icm=icm_recall(query, limit, icm_runner),
        committed=grep_committed(query, host, root, limit),
        host=host,
    )
