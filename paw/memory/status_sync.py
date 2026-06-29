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


# Default host-context files. ALL existing ones are targets — a project with
# both AGENTS.md and CLAUDE.md gets the block in each, so every host's agent
# reads the same instruction regardless of which file it loads.
DEFAULT_TARGETS = ("AGENTS.md", "CLAUDE.md")


def resolve_target(*, cwd: str | None = None) -> Path | None:
    """Pick the FIRST existing DEFAULT_TARGET under cwd.

    Kept for backwards compatibility (older callers, tests). New code should
    prefer ``resolve_targets`` so the block lands in every context file.
    """
    targets = resolve_targets(cwd=cwd)
    return targets[0] if targets else None


def resolve_targets(*, cwd: str | None = None) -> list[Path]:
    """All existing DEFAULT_TARGET files under cwd, in declared order."""
    base = Path(cwd) if cwd else Path.cwd()
    out: list[Path] = []
    for name in DEFAULT_TARGETS:
        candidate = base / name
        if candidate.exists() and candidate.is_file():
            out.append(candidate)
    return out


def _apply_one(target: Path, name: str) -> SyncResult:
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


def _remove_one(target: Path, name: str) -> SyncResult:
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


def _verify_one(target: Path, name: str) -> SyncResult:
    present = has_block(target.read_text(encoding="utf-8"), name)
    return SyncResult(
        applied=present, changed=False, path=target,
        message=f"{'present' if present else 'absent'} in {target.name}",
    )


def apply(cwd: str | None = None, name: str = SET_NAME) -> SyncResult:
    """Inject the status-sync block into EVERY host context file. Idempotent.

    Returns an aggregate SyncResult: ``applied`` is True if the block is now
    present in all targets; ``changed`` is True if at least one file was
    modified; ``path`` is the first target; ``message`` summarises per-file.
    """
    targets = resolve_targets(cwd=cwd)
    if not targets:
        return SyncResult(
            applied=False, changed=False,
            path=Path(cwd or ".") / DEFAULT_TARGETS[0],
            message=f"no host context file found ({'/'.join(DEFAULT_TARGETS)})",
        )
    results = [_apply_one(t, name) for t in targets]
    changed = any(r.changed for r in results)
    all_present = all(r.applied for r in results)
    summary = "; ".join(r.message for r in results)
    return SyncResult(
        applied=all_present, changed=changed, path=targets[0], message=summary,
    )


def remove(cwd: str | None = None, name: str = SET_NAME) -> SyncResult:
    """Strip the status-sync block from EVERY host context file. Idempotent."""
    targets = resolve_targets(cwd=cwd)
    if not targets:
        return SyncResult(
            applied=False, changed=False,
            path=Path(cwd or ".") / DEFAULT_TARGETS[0],
            message="no host context file found",
        )
    results = [_remove_one(t, name) for t in targets]
    changed = any(r.changed for r in results)
    all_absent = all(not r.applied for r in results)
    summary = "; ".join(r.message for r in results)
    return SyncResult(
        applied=not all_absent, changed=changed, path=targets[0], message=summary,
    )


def verify(cwd: str | None = None, name: str = SET_NAME) -> SyncResult:
    """Report whether the block is present in EVERY host context file.

    ``applied`` is True only when present in ALL targets. Never modifies files.
    """
    targets = resolve_targets(cwd=cwd)
    if not targets:
        return SyncResult(
            applied=False, changed=False,
            path=Path(cwd or ".") / DEFAULT_TARGETS[0],
            message="no host context file found",
        )
    results = [_verify_one(t, name) for t in targets]
    all_present = all(r.applied for r in results)
    summary = "; ".join(r.message for r in results)
    return SyncResult(
        applied=all_present, changed=False, path=targets[0], message=summary,
    )
