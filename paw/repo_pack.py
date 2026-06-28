"""Repo-pack scope guard: prevent accidental whole-repo packs.

Usage:
  from paw.repo_pack import guard_broad_pack, size_hint

The guard refuses to pack a repo root unless the request is scoped with
``--include``, ``--diff``, or ``--allow-large``.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path
from typing import Any


def is_repo_root(path: Path) -> bool:
    """Heuristic: path contains a .git directory."""
    return (path / ".git").is_dir()


def repo_name(path: Path) -> str:
    """Friendly repo name from path basename."""
    return path.resolve().name


def size_hint(path: Path) -> str:
    """Quick estimate of total file count (excluding .git) for error messaging."""
    total = 0
    try:
        for dirpath, dirnames, filenames in os.walk(str(path)):
            dn = os.path.basename(dirpath)
            if dn == ".git" or dirpath.startswith(".git"):
                dirnames.clear()
                continue
            if "node_modules" in dirnames:
                dirnames.remove("node_modules")
            total += len(filenames)
    except OSError:
        return "?"
    return str(total)


class GuardRefused(Exception):
    """Raised when the pack is refused by the scope guard."""

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


def guard_broad_pack(
    path: Path,
    *,
    has_include: bool = False,
    has_diff: bool = False,
    allow_large: bool = False,
) -> None:
    """Guard against broad root packs.

    Raises ``GuardRefused`` when the pack targets a repo root without
    an explicit scope (``--include``, ``--diff``, or ``--allow-large``).

    Returns silently when the path is not a repo root or a scope flag is set.
    """
    if not is_repo_root(path):
        return

    if has_include or has_diff or allow_large:
        return

    name = repo_name(path)
    hint = size_hint(path)
    raise GuardRefused(
        f"refusing broad pack of repo root {name} (~{hint} files).\n"
        f"  scope the pack with:\n"
        f"    --include <glob>    only pack matching files\n"
        f"    --diff              pack git diff instead of working tree\n"
        f"    --allow-large       override this guard\n"
        f"  or point to a subdirectory instead of the repo root."
    )


def run_vendored_code2prompt(
    path: Path,
    *,
    output: str | None = None,
    diff: bool = False,
    include: list[str] | None = None,
    exclude: list[str] | None = None,
) -> int:
    """Run vendored code2prompt with the given arguments.

    Returns the process exit code.
    """
    repo_root = Path(__file__).parent.parent
    vendored = repo_root / "bin" / "code2prompt.exe"
    binary = str(vendored) if vendored.exists() else "code2prompt"

    cmd = [binary, str(path)]
    if output:
        cmd += ["-O", output]
    if diff:
        cmd += ["-d"]
    for pat in include or []:
        cmd += ["--include", pat]
    for pat in exclude or []:
        cmd += ["--exclude", pat]

    # code2prompt defaults to stdout when no -O, so piping is natural.
    # When -O is given, it writes a file.
    kwargs: dict[str, Any] = {}
    if not output:
        kwargs["capture_output"] = False

    try:
        proc = subprocess.run(cmd, **kwargs)
        return proc.returncode
    except FileNotFoundError:
        print(f"error: code2prompt not found (checked {vendored})", file=sys.stderr)
        print(
            "  install: download prebuilt from https://github.com/mufeedvh/code2prompt/releases",
            file=sys.stderr,
        )
        return 1
