"""Resume block — the SessionStart orientation anchor.

This is the single most load-bearing output of the memory layer for the "no
more lost context on a new session" goal. It composes three bounded pieces
into one short additional-context block:

  • **status**      — from status_store (git ground truth + AI note)
  • **decisions**   — from decision_mirror (markdown → facts index)
  • **handoff**     — latest blackboard handoff for this project/run

Everything is fail-safe and bounded: any piece that errors or is empty simply
drops out, and the whole block returns '' when nothing is present (so the hook
never injects a hollow "📌 paw resume:" header).

The builder is a pure function over injected readers so it can be unit-tested
without a live ICM or git, and so the hook can pass cheap fakes on hot paths.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Optional, Sequence

from . import decision_mirror, facts, status_store

MAX_DECISIONS = 5
MAX_DECISION_CHARS = 90
MAX_HANDOFF_CHARS = 140


@dataclass(frozen=True)
class HandoffLine:
    """One bounded handoff line for the resume block."""

    text: str


# Reader type aliases keep the call sites readable and the seams testable.
StatusReader = Callable[[str], Optional[status_store.ProjectStatus]]
DecisionsReader = Callable[[Sequence[Path], Optional[Path]], list[decision_mirror.Decision]]
HandoffReader = Callable[[str, str], Optional[str]]
MirrorRunner = Callable[[Sequence[Path], Optional[Path]], int]


def _default_status_reader(project: str) -> Optional[status_store.ProjectStatus]:
    return status_store.read_status(project)


def _default_decisions_reader(
    md_paths: Sequence[Path], base: Optional[Path]
) -> list[decision_mirror.Decision]:
    return decision_mirror.collect_decisions(md_paths, base=base)


def _default_mirror_runner(
    md_paths: Sequence[Path], base: Optional[Path]
) -> int:
    return decision_mirror.mirror_decisions(md_paths, base=base)


def _truncate(text: str, limit: int) -> str:
    text = (text or "").strip().replace("\n", " ")
    if len(text) <= limit:
        return text
    return text[: limit - 1].rstrip() + "…"


def build_resume_block(
    project: str,
    *,
    cwd: Optional[str] = None,
    md_paths: Sequence[Path] = (),
    md_base: Optional[Path] = None,
    status_reader: StatusReader = _default_status_reader,
    decisions_reader: DecisionsReader = _default_decisions_reader,
    mirror_runner: Optional[MirrorRunner] = _default_mirror_runner,
    handoff_reader: Optional[HandoffReader] = None,
) -> str:
    """Compose the 📌 resume block. '' when nothing useful is present.

    ``mirror_runner`` runs the markdown→facts refresh BEFORE we read decisions
    from markdown, so a freshly-edited CLAUDE.md decision is indexed this
    session. Pass ``None`` to skip mirroring (tests, or when markdown is not
    authoritative for this host).
    """
    parts: list[str] = []

    # 1. status (git + note)
    status_text = ""
    try:
        status = status_reader(project)
        status_text = status_store.render_resume(status) if status else ""
    except Exception:
        status_text = ""
    if status_text:
        parts.append(status_text)

    # 2. mirror decisions markdown → facts, then read the canonical list
    decisions: list[decision_mirror.Decision] = []
    try:
        if mirror_runner is not None and md_paths:
            mirror_runner(md_paths, md_base)
        if md_paths:
            decisions = decisions_reader(md_paths, md_base)
    except Exception:
        decisions = []
    if decisions:
        lines = ["decisions:"]
        for d in decisions[:MAX_DECISIONS]:
            lines.append(f"  • {d.slug}: {_truncate(d.body, MAX_DECISION_CHARS)}")
        parts.append("\n".join(lines))

    # 3. handoff (optional — caller may not supply a reader)
    if handoff_reader is not None:
        try:
            handoff = handoff_reader(project, cwd or "")
        except Exception:
            handoff = None
        if handoff:
            parts.append("last handoff: " + _truncate(handoff, MAX_HANDOFF_CHARS))

    if not parts:
        return ""

    header = f"📌 paw resume ({project}):"
    return header + "\n" + "\n".join(parts)
