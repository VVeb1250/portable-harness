"""Status-sync instruction block — the "โพย" that keeps snapshots fresh.

This is the static instruction layer (per the user's approved plan rev.3/4):
instead of a Stop hook dynamically prompting the AI to update the snapshot,
we inject a committed instruction block into AGENTS.md (the file every host's
agent reads). The AI then updates the snapshot on its own, every host, with
no hook dependency and no ZCode gap.

We deliberately reuse the linker's marker convention (`<!-- paw:<name>:start -->`)
so the block is discoverable by the same tooling and is visually consistent
with the capability blocks. But we do NOT route through CuratedSet — that
abstraction is for capability/tool sets, and an instruction block has no
tools, no install commands, no health binary. A thin dedicated renderer keeps
the linker's contract intact.

The block content is intentionally short and copy-pasteable: it tells the AI
exactly two commands and when to run them, nothing more.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

SET_NAME = "status-sync"


def _markers(name: str = SET_NAME) -> tuple[str, str]:
    return f"<!-- paw:{name}:start -->", f"<!-- paw:{name}:end -->"


def _block_re(name: str = SET_NAME) -> re.Pattern[str]:
    start, end = (re.escape(m) for m in _markers(name))
    return re.compile(rf"\n?{start}.*?{end}\n?", re.DOTALL)


def has_block(text: str, name: str = SET_NAME) -> bool:
    return _block_re(name).search(text or "") is not None


def render_block(name: str = SET_NAME) -> str:
    """The committed instruction body. Keep it short — it is always in context."""
    start, end = _markers(name)
    lines = [
        start,
        "## paw status-sync (อัพเดท snapshot)",
        "",
        "เมื่อจบงานสำคัญ หรือก่อนปิด session ให้อัพเดท snapshot ของโปรเจค",
        "เพื่อให้ session ถัดไปเห็นสถานะล่าสุดผ่าน paw resume block:",
        "",
        "1. `paw memory status save` — เก็บ git layer อัตโนมัติ (branch/commit/dirty)",
        "2. `paw memory status note \"<ทำอะไร>/<เจออะไร>/<จะทำอะไรต่อ>\"`",
        "",
        "snapshot จะถูก inject กลับเป็น resume block ตอน SessionStart.",
        "ห้ามลบ block นี้ด้วยมือ — ใช้ `paw memory status-sync remove`.",
        end,
    ]
    return "\n".join(lines)


def inject_block(text: str, name: str = SET_NAME) -> str:
    """Insert or replace the block; leave all other text intact."""
    body = render_block(name)
    pattern = _block_re(name)
    if pattern.search(text or ""):
        return pattern.sub("\n" + body + "\n", text, count=1)
    sep = "" if (not text or text.endswith("\n")) else "\n"
    return f"{text}{sep}\n{body}\n"


def strip_block(text: str, name: str = SET_NAME) -> str:
    """Remove only this block (and a single surrounding blank line)."""
    return _block_re(name).sub("\n", text or "", count=1).rstrip("\n") + (
        "\n" if (text or "").endswith("\n") else ""
    )


@dataclass(frozen=True)
class SyncResult:
    applied: bool          # True if the block is now present
    changed: bool          # True if the file was actually modified
    path: Path
    message: str


# Default host-context files, searched in order. First existing writable file
# is used as the target. Matches the linker's notion of host context files.
DEFAULT_TARGETS = ("AGENTS.md", "CLAUDE.md")


def resolve_target(*, cwd: str | None = None) -> Path | None:
    """Pick the first existing DEFAULT_TARGET under cwd (or cwd itself)."""
    base = Path(cwd) if cwd else Path.cwd()
    for name in DEFAULT_TARGETS:
        candidate = base / name
        if candidate.exists() and candidate.is_file():
            return candidate
    return None


def apply(cwd: str | None = None, name: str = SET_NAME) -> SyncResult:
    """Inject the status-sync block into the host context file. Idempotent."""
    target = resolve_target(cwd=cwd)
    if target is None:
        return SyncResult(
            applied=False, changed=False,
            path=Path(cwd or ".") / DEFAULT_TARGETS[0],
            message=f"no host context file found ({'/'.join(DEFAULT_TARGETS)})",
        )
    before = target.read_text(encoding="utf-8")
    if has_block(before, name):
        return SyncResult(
            applied=True, changed=False, path=target,
            message=f"already present in {target.name}",
        )
    target.write_text(inject_block(before, name), encoding="utf-8")
    return SyncResult(
        applied=True, changed=True, path=target,
        message=f"injected into {target.name}",
    )


def remove(cwd: str | None = None, name: str = SET_NAME) -> SyncResult:
    """Strip the status-sync block. Idempotent."""
    target = resolve_target(cwd=cwd)
    if target is None:
        return SyncResult(
            applied=False, changed=False,
            path=Path(cwd or ".") / DEFAULT_TARGETS[0],
            message="no host context file found",
        )
    before = target.read_text(encoding="utf-8")
    if not has_block(before, name):
        return SyncResult(
            applied=False, changed=False, path=target,
            message=f"not present in {target.name}",
        )
    target.write_text(strip_block(before, name), encoding="utf-8")
    return SyncResult(
        applied=False, changed=True, path=target,
        message=f"removed from {target.name}",
    )


def verify(cwd: str | None = None, name: str = SET_NAME) -> SyncResult:
    """Report whether the block is present. Never modifies the file."""
    target = resolve_target(cwd=cwd)
    if target is None:
        return SyncResult(
            applied=False, changed=False,
            path=Path(cwd or ".") / DEFAULT_TARGETS[0],
            message="no host context file found",
        )
    present = has_block(target.read_text(encoding="utf-8"), name)
    return SyncResult(
        applied=present, changed=False, path=target,
        message=f"{'present' if present else 'absent'} in {target.name}",
    )
