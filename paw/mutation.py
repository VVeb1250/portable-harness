"""paw.mutation — safe SEARCH/REPLACE applier with transactional rollback.

The Team Kernel implementer (DeepSeek today) hands off edits as Aider-style
``@@@FILE`` / ``<<<<<<< SEARCH`` / ``=======`` / ``>>>>>>> REPLACE`` / ``@@@ENDFILE``
blocks — the same contract proven in ``bench/swe_probe``. This module turns that
text into real changes on a working tree, but unlike the benchmark applier (which
edits in-memory oracle bases) it touches a live repo, so it adds the two things a
runtime mutator must have:

  - **transactional commit** — every file's new content is computed in memory first;
    if *any* SEARCH block misses, nothing is written. A miss never leaves a tree
    half-mutated. Only an all-clear set proceeds to disk.
  - **backup + rollback** — before overwriting, each original is copied into a
    timestamped backup dir. A mid-write failure restores every backup, so a crash
    between two file writes cannot leave the tree inconsistent.

It also refuses any edit whose resolved path escapes the working tree (no
``../`` traversal, no absolute paths outside root) and emits a unified diff of
exactly what changed, for the blackboard artifact.

Pure stdlib; the parse/apply core mirrors ``bench/swe_probe/deepseek.py`` rather
than importing it — the benchmark is frozen and must not become a runtime dep.
"""

from __future__ import annotations

import difflib
import re
import shutil
import time
from dataclasses import dataclass, field
from pathlib import Path

# one @@@FILE <path> ... @@@ENDFILE block per changed file
_FILE_BLOCK = re.compile(
    r"@@@FILE[ \t]+(?P<path>.+?)[ \t]*\n(?P<body>.*?)\n?@@@ENDFILE",
    re.DOTALL,
)
# one SEARCH/REPLACE edit; markers must each sit on their own line
_SR = re.compile(
    r"<{5,}[ \t]*SEARCH[ \t]*\n(?P<search>.*?)\n?={5,}[ \t]*\n"
    r"(?P<replace>.*?)\n?>{5,}[ \t]*REPLACE",
    re.DOTALL,
)


class EditMiss(Exception):
    """A SEARCH block did not match the current file content."""


@dataclass(frozen=True)
class FileEdit:
    path: str
    search: str
    replace: str


@dataclass
class MutationResult:
    status: str                                  # applied | aborted | noop
    summary: str
    applied: list[str] = field(default_factory=list)     # paths written
    misses: list[str] = field(default_factory=list)      # paths with unmatched SEARCH
    rejected: list[str] = field(default_factory=list)    # paths outside the tree
    diff: str = ""
    backup_dir: str = ""
    rolled_back: bool = False

    @property
    def ok(self) -> bool:
        return self.status == "applied"

    def to_dict(self) -> dict[str, object]:
        return {
            "status": self.status, "summary": self.summary, "applied": self.applied,
            "misses": self.misses, "rejected": self.rejected,
            "backup_dir": self.backup_dir, "rolled_back": self.rolled_back,
        }


# --------------------------------------------------------------------------- #
# parse + in-memory apply (mirrors the proven swe_probe contract)
# --------------------------------------------------------------------------- #
def parse_edits(text: str) -> list[FileEdit]:
    """Extract ordered ``FileEdit``s from the implementer's @@@FILE blocks."""
    out: list[FileEdit] = []
    for fm in _FILE_BLOCK.finditer(text or ""):
        path = fm.group("path").strip()
        for m in _SR.finditer(fm.group("body")):
            out.append(FileEdit(path=path, search=m.group("search"), replace=m.group("replace")))
    return out


def _flex_apply(content: str, search: str, replace: str) -> str | None:
    """Whole-line match of ``search`` ignoring trailing whitespace — the fallback
    for when only dropped/added trailing spaces break an exact substring match."""
    c_lines = content.splitlines(keepends=True)
    s_lines = [ln.rstrip() for ln in search.splitlines()]
    n = len(s_lines)
    if n == 0:
        return None
    offsets, pos = [], 0
    for ln in c_lines:
        offsets.append(pos)
        pos += len(ln)
    offsets.append(pos)
    for i in range(len(c_lines) - n + 1):
        window = [c_lines[i + j].rstrip("\r\n").rstrip() for j in range(n)]
        if window == s_lines:
            start, end = offsets[i], offsets[i + n]
            rep = replace
            if content[start:end].endswith("\n") and not rep.endswith("\n"):
                rep += "\n"
            return content[:start] + rep + content[end:]
    return None


def apply_edits(base: str, edits: list[tuple[str, str]]) -> str:
    """Apply ``(search, replace)`` edits to ``base`` in order; raise ``EditMiss`` on
    an unmatched SEARCH. Exact substring first, then trailing-ws-flexible whole-line
    fallback. An empty SEARCH means create/overwrite the file with REPLACE."""
    content = base
    for search, replace in edits:
        if search.strip() == "":
            content = replace
            continue
        if content.count(search) >= 1:
            content = content.replace(search, replace, 1)
            continue
        flexed = _flex_apply(content, search, replace)
        if flexed is None:
            raise EditMiss(search)
        content = flexed
    return content


# --------------------------------------------------------------------------- #
# working-tree apply (transactional, backed up, path-guarded)
# --------------------------------------------------------------------------- #
def _resolve_in_tree(root: Path, rel: str) -> Path | None:
    """Resolve ``rel`` under ``root``; return None if it escapes the tree."""
    root = root.resolve()
    try:
        target = (root / rel).resolve()
    except (OSError, ValueError, RuntimeError):
        return None
    if target == root or root not in target.parents:
        return None
    return target


def _unified(rel: str, old: str, new: str) -> str:
    return "".join(
        difflib.unified_diff(
            old.splitlines(keepends=True), new.splitlines(keepends=True),
            fromfile=f"a/{rel}", tofile=f"b/{rel}",
        )
    )


def apply_to_tree(
    text: str,
    root: str | Path,
    *,
    dry_run: bool = False,
    backup_root: str | Path | None = None,
) -> MutationResult:
    """Parse SEARCH/REPLACE blocks from ``text`` and apply them under ``root``.

    Two-phase and transactional: all new file contents are computed first; if any
    SEARCH misses or any path escapes the tree, **nothing is written** (status
    ``aborted``). Only when every edit resolves cleanly are originals backed up and
    overwritten; a disk error mid-write restores all backups (``rolled_back``).
    ``dry_run`` computes the diff without writing or backing up. Never raises.
    """
    root = Path(root)
    edits = parse_edits(text)
    if not edits:
        return MutationResult(status="noop", summary="no SEARCH/REPLACE edits in handoff")

    # group edits per file, preserving order
    by_path: dict[str, list[tuple[str, str]]] = {}
    rejected: list[str] = []
    for e in edits:
        target = _resolve_in_tree(root, e.path)
        if target is None:
            if e.path not in rejected:
                rejected.append(e.path)
            continue
        by_path.setdefault(e.path, []).append((e.search, e.replace))

    if rejected:
        return MutationResult(
            status="aborted",
            summary=f"refused {len(rejected)} path(s) outside the working tree; nothing written",
            rejected=rejected,
        )

    # phase 1 — compute every new content in memory; collect misses, write nothing
    planned: list[tuple[str, Path, str, str]] = []   # (rel, target, old, new)
    misses: list[str] = []
    diff_parts: list[str] = []
    for rel, file_edits in by_path.items():
        target = _resolve_in_tree(root, rel)
        assert target is not None  # rejected paths already filtered out
        old = target.read_text(encoding="utf-8") if target.exists() else ""
        try:
            new = apply_edits(old, file_edits)
        except EditMiss:
            misses.append(rel)
            continue
        if new != old:
            planned.append((rel, target, old, new))
            diff_parts.append(_unified(rel, old, new))

    if misses:
        return MutationResult(
            status="aborted",
            summary=f"{len(misses)} file(s) had unmatched SEARCH blocks; nothing written",
            misses=misses,
            diff="".join(diff_parts),
        )

    diff = "".join(diff_parts)
    if not planned:
        return MutationResult(status="noop", summary="edits produced no change", diff=diff)
    if dry_run:
        return MutationResult(
            status="applied",
            summary=f"dry-run: {len(planned)} file(s) would change (not written)",
            applied=[rel for rel, *_ in planned],
            diff=diff,
        )

    # phase 2 — back up originals, then commit; restore all on any write failure
    stamp = time.strftime("%Y%m%dT%H%M%S")
    backup_dir = Path(backup_root) if backup_root else root / ".paw" / "mutation-backups" / stamp
    written: list[tuple[Path, Path | None]] = []   # (target, backup_path or None for created)
    try:
        backup_dir.mkdir(parents=True, exist_ok=True)
        for rel, target, old, new in planned:
            backup_path: Path | None = None
            if target.exists():
                backup_path = backup_dir / rel
                backup_path.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(target, backup_path)
            else:
                target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(new, encoding="utf-8")
            written.append((target, backup_path))
    except OSError as error:
        for target, backup_path in reversed(written):
            try:
                if backup_path is not None:
                    shutil.copy2(backup_path, target)
                elif target.exists():
                    target.unlink()      # created file — remove on rollback
            except OSError:
                continue
        return MutationResult(
            status="aborted",
            summary=f"write failed ({error}); rolled back {len(written)} file(s)",
            misses=misses, diff=diff, backup_dir=str(backup_dir), rolled_back=True,
        )

    return MutationResult(
        status="applied",
        summary=f"applied {len(planned)} file(s); originals backed up to {backup_dir}",
        applied=[rel for rel, *_ in planned],
        diff=diff,
        backup_dir=str(backup_dir),
    )
