"""Project status snapshot — the two-layer resume anchor.

The single most common "lost context on a new session" failure is that the AI
opens fresh and has to be TOLD, by the user, where the project is. This store
removes that prompt tax: a SessionStart hook reads this snapshot and injects a
short resume block so any AI on any host starts oriented.

Two layers, deliberately separate, because they have different trust profiles:

  • **git layer** — deterministic ground truth. Captured from `git` (branch,
    HEAD short sha, dirty-file count, head-changed-at). Never lies, never
    needs the AI to remember anything. Updated automatically on Stop.

  • **note layer** — meaningful, written by the AI per the status-sync managed
    block (the "โพย"). A short "did X / hit Y / next Z". This is the part git
    cannot see, so it carries the actual intent and blockers.

  • **stale flag** — derived: True when HEAD has moved since the note was last
    written. A stale note is still shown (better than nothing) but flagged, so
    the new session knows the note predates the current commit.

Stored as one fact: ``project:<slug>.status`` = JSON blob. Using ICM ``facts``
(not ``memories``) on purpose — status is an exact, single-valued, frequently
superseded slot, exactly what entity.key=value + supersede-history is for.
Semantic recall would fuzzy-match the WRONG old snapshot.

All calls are fail-safe: a broken git or ICM degrades to empty/None. The
resume block that depends on this must never break the SessionStart hook.
"""

from __future__ import annotations

import json
import platform
import subprocess
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Optional

from . import facts

STATUS_KEY = "status"
_NOTE_MAX = 480  # keep the resume block small; longer notes get truncated on read


# --------------------------------------------------------------------------- #
# git layer
# --------------------------------------------------------------------------- #

GitRunner = Callable[[list[str], str], subprocess.CompletedProcess]


def _git_default(cmd: list[str], cwd: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["git"] + cmd, cwd=cwd, capture_output=True, text=True, timeout=4,
        check=False,
    )


@dataclass(frozen=True)
class GitLayer:
    branch: str = ""
    head_short: str = ""
    dirty_count: int = 0
    head_changed_at: str = ""  # ISO8601 UTC of when we sampled this

    @property
    def present(self) -> bool:
        return bool(self.branch or self.head_short)


def capture_git_layer(
    cwd: str,
    *,
    runner: Optional[GitRunner] = None,
    now: Optional[Callable[[], datetime]] = None,
) -> GitLayer:
    """Read-only git snapshot of ``cwd``. Empty GitLayer if not a repo.

    Each field is captured independently so a missing branch (detached HEAD)
    or an unusual state does not blank the whole layer. All git failures
    degrade to "" / 0.
    """
    run = runner or _git_default
    clock = now or (lambda: datetime.now(timezone.utc))

    def _out(args: list[str]) -> str:
        try:
            proc = run(args, cwd)
        except (OSError, subprocess.SubprocessError):
            return ""
        return (proc.stdout or "").strip() if proc.returncode == 0 else ""

    branch = _out(["rev-parse", "--abbrev-ref", "HEAD"])
    head_short = _out(["rev-parse", "--short", "HEAD"])
    # `git status --porcelain` lists one line per dirty entry; empty = clean.
    dirty = _out(["status", "--porcelain"])
    dirty_count = 0
    if dirty:
        dirty_count = len([ln for ln in dirty.splitlines() if ln.strip()])
    # Detached HEAD has no branch name but still has a sha — label it so the
    # resume block is honest without making `.present` lie when git is absent.
    if not branch and head_short:
        branch = "(detached)"
    return GitLayer(
        branch=branch,
        head_short=head_short,
        dirty_count=dirty_count,
        head_changed_at=clock().isoformat(timespec="seconds"),
    )


# --------------------------------------------------------------------------- #
# note layer
# --------------------------------------------------------------------------- #


@dataclass(frozen=True)
class NoteLayer:
    summary: str           # "did X / hit Y / next Z"
    updated_at: str        # ISO8601 UTC
    updated_by: str        # member/host that wrote it, e.g. "claude-code:abc123"
    base_head: str         # HEAD short sha at write time — drives the stale flag


# --------------------------------------------------------------------------- #
# composite status
# --------------------------------------------------------------------------- #


@dataclass(frozen=True)
class ProjectStatus:
    project: str
    git: Optional[GitLayer] = None
    note: Optional[NoteLayer] = None

    @property
    def stale(self) -> bool:
        """True if git HEAD has moved since the note was last written.

        A missing git layer or note means we cannot tell, so we return False
        (do not cry stale when we simply don't know) — the renderer can still
        note "no note" separately.
        """
        if not self.git or not self.note:
            return False
        # If HEAD changed at all since the note's base, the note predates the
        # current state. A re-written note will refresh base_head.
        return bool(self.git.head_short) and self.note.base_head != self.git.head_short

    def to_dict(self) -> dict:
        return {
            "project": self.project,
            "git": asdict(self.git) if self.git else None,
            "note": asdict(self.note) if self.note else None,
        }

    def to_json(self) -> str:
        """Compact JSON for the fact value. Sorted keys for stable diffs."""
        return json.dumps(self.to_dict(), ensure_ascii=False, sort_keys=True)


def _entity(project: str) -> str:
    """Stable facts entity for a project's status slot."""
    slug = (project or "default").strip().replace(" ", "-").lower() or "default"
    return f"project:{slug}"


def from_row(row: Optional[facts.FactRow]) -> Optional[ProjectStatus]:
    """Parse a facts.FactRow's JSON value into a ProjectStatus. None if bad."""
    if not row or not row.value:
        return None
    try:
        data = json.loads(row.value)
    except (ValueError, TypeError):
        return None
    if not isinstance(data, dict):
        return None
    git = None
    g = data.get("git")
    if isinstance(g, dict):
        try:
            git = GitLayer(
                branch=str(g.get("branch", "") or ""),
                head_short=str(g.get("head_short", "") or ""),
                dirty_count=int(g.get("dirty_count", 0) or 0),
                head_changed_at=str(g.get("head_changed_at", "") or ""),
            )
        except (TypeError, ValueError):
            git = None
    note = None
    n = data.get("note")
    if isinstance(n, dict) and n.get("summary"):
        try:
            note = NoteLayer(
                summary=str(n.get("summary", ""))[:_NOTE_MAX],
                updated_at=str(n.get("updated_at", "") or ""),
                updated_by=str(n.get("updated_by", "") or ""),
                base_head=str(n.get("base_head", "") or ""),
            )
        except (TypeError, ValueError):
            note = None
    return ProjectStatus(project=str(data.get("project", "")), git=git, note=note)


def read_status(
    project: str, *, runner: Optional[facts.Runner] = None, db: str = ""
) -> Optional[ProjectStatus]:
    """Load the current snapshot for ``project``. None if absent / unparseable."""
    row = facts.get_fact(_entity(project), STATUS_KEY, runner=runner, db=db)
    return from_row(row)


def _write_status(
    status: ProjectStatus,
    *,
    runner: Optional[facts.Runner] = None,
    db: str = "",
) -> bool:
    """Persist a full snapshot. Returns True only if the re-read confirms it."""
    return facts.set_fact(
        _entity(status.project), STATUS_KEY, status.to_json(),
        source="paw:status", runner=runner, db=db,
    )


def save_git_layer(
    project: str,
    git: GitLayer,
    *,
    runner: Optional[facts.Runner] = None,
    db: str = "",
) -> bool:
    """Update only the git layer, preserving any existing note.

    This is the Stop-hook path: deterministic, cheap, never touches the note
    the AI wrote. A note that predates the new HEAD becomes stale (see
    ``ProjectStatus.stale``).
    """
    current = read_status(project, runner=runner, db=db)
    note = current.note if current else None
    return _write_status(
        ProjectStatus(project=project, git=git, note=note),
        runner=runner, db=db,
    )


def save_note(
    project: str,
    summary: str,
    *,
    updated_by: str,
    base_head: str,
    now: Optional[Callable[[], datetime]] = None,
    runner: Optional[facts.Runner] = None,
    db: str = "",
) -> bool:
    """Update only the note layer, preserving the git layer.

    ``base_head`` is the HEAD the note was written against — usually captured
    at the same moment from ``capture_git_layer`` so the stale flag is accurate
    until the next commit. The caller (AI, following the managed-block โพย)
    supplies both.
    """
    clock = now or (lambda: datetime.now(timezone.utc))
    current = read_status(project, runner=runner, db=db)
    git = current.git if current else None
    note = NoteLayer(
        summary=(summary or "").strip()[:_NOTE_MAX],
        updated_at=clock().isoformat(timespec="seconds"),
        updated_by=updated_by,
        base_head=base_head,
    )
    return _write_status(
        ProjectStatus(project=project, git=git, note=note),
        runner=runner, db=db,
    )


def reset_status(
    project: str, *, runner: Optional[facts.Runner] = None, db: str = ""
) -> bool:
    """Delete the status slot entirely. True if something was removed."""
    return facts.forget_fact(_entity(project), STATUS_KEY, runner=runner, db=db)


# --------------------------------------------------------------------------- #
# rendering (used by the SessionStart resume block)
# --------------------------------------------------------------------------- #


def render_resume(status: Optional[ProjectStatus], *, max_note_lines: int = 3) -> str:
    """Compact multi-line resume string for injection. '' if nothing to show.

    Shape:
        status: <note line(s) or git fallback> [stale?]
        git: <branch> · <sha> · dirty <N>
    """
    if not status:
        return ""
    parts: list[str] = []
    if status.note and status.note.summary:
        note_lines = status.note.summary.splitlines()[:max_note_lines]
        flag = "  ⚠️ stale (commit moved since note)" if status.stale else ""
        parts.append("status: " + " / ".join(ln.strip() for ln in note_lines) + flag)
    elif status.git and status.git.present:
        # No AI note yet — fall back to git ground truth so the session is not blind.
        parts.append("status: (no AI note) see git + STATUS.md")
    if status.git and status.git.present:
        parts.append(
            f"git: {status.git.branch} · {status.git.head_short} · "
            f"dirty {status.git.dirty_count}"
        )
    return "\n".join(parts)
