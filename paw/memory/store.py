"""Tiny jsonl storage primitives — no-daemon, offline, tolerant.

paw owns NO lesson store (ICM does that, cross-host). What remains here is the
minimal file-I/O backbone the local overlay ledgers need:
  - the distrust miss-count overlay (`distrust.py`)
  - the router outcome ledger (`outcomes.py`)
  - the session inject-dedup log (`sessionlog.py`)

I/O boundary only. Atomic writes (temp + os.replace) so a crash never corrupts
a ledger; a best-effort cross-process lock for read-modify-write spans (parallel
hooks). Everything degrades to tolerant no-ops rather than crashing a hook.
"""

from __future__ import annotations

import os
import time
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path


class MemoryStoreError(RuntimeError):
    """store dir unwritable / path resolution failure."""


def global_dir() -> Path:
    """~/.paw/memory — local ledger dir ($PAW_HOME redirects it for isolated runs)."""
    from ..config import paw_root

    return paw_root() / "memory"


def _replace_with_retry(tmp: Path, path: Path, attempts: int = 3) -> None:
    """os.replace is atomic, but on Windows it raises PermissionError while a
    concurrent reader holds the destination open — brief retry covers that window."""
    for i in range(attempts):
        try:
            os.replace(tmp, path)
            return
        except PermissionError as e:
            if i == attempts - 1:
                raise MemoryStoreError(f"store busy, could not replace {path}") from e
            time.sleep(0.05 * (i + 1))


def _write_jsonl_raw(path: Path, lines: list[str]) -> None:
    """Atomic write of pre-serialized jsonl lines. pid-suffixed tmp + replace-retry
    → no interleave, no half-written file even under concurrent hooks."""
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
    except OSError as e:
        raise MemoryStoreError(f"cannot create store dir {path.parent}: {e}") from e
    body = "\n".join(lines)
    tmp = path.with_suffix(path.suffix + f".{os.getpid()}.tmp")
    tmp.write_text(body + ("\n" if body else ""), encoding="utf-8")
    try:
        _replace_with_retry(tmp, path)
    finally:
        tmp.unlink(missing_ok=True)  # leftover only when replace failed


def write_text_atomic(path: Path, body: str) -> None:
    """Atomic write of a single text blob (json, markdown, etc.).

    Same pid-suffixed tmp + replace-retry as the jsonl writer, so a crash mid-
    write never leaves a truncated file. Use this anywhere a non-jsonl single
    file is written under the memory overlay (e.g. sessionlog dedup json).
    """
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
    except OSError as e:
        raise MemoryStoreError(f"cannot create store dir {path.parent}: {e}") from e
    tmp = path.with_suffix(path.suffix + f".{os.getpid()}.tmp")
    tmp.write_text(body, encoding="utf-8")
    try:
        _replace_with_retry(tmp, path)
    finally:
        tmp.unlink(missing_ok=True)


@contextmanager
def locked(path: Path, *, timeout: float = 2.0, stale: float = 10.0) -> Iterator[None]:
    """Best-effort cross-process lock for a read-modify-write on `path`.

    The atomic single-file write prevents CORRUPTION, but two concurrent hooks
    doing load→modify→save still lose one writer's update. This O_CREAT|O_EXCL
    lockfile serializes that span — portable (Windows + POSIX). Best-effort: a
    lock older than `stale` is broken (crashed holder), and on `timeout` we
    proceed UNLOCKED — a hook must never hang; worst case is pre-lock behavior.
    """
    lock = path.with_name(path.name + ".lock")
    acquired = False
    deadline = time.monotonic() + timeout
    try:
        lock.parent.mkdir(parents=True, exist_ok=True)
    except OSError:
        pass
    while True:
        try:
            os.close(os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY))
            acquired = True
            break
        except FileExistsError:
            try:
                if time.time() - lock.stat().st_mtime > stale:
                    lock.unlink(missing_ok=True)
                    continue
            except OSError:
                pass
            if time.monotonic() >= deadline:
                break  # proceed unlocked — never block a hook
            time.sleep(0.02)
        except OSError:
            break  # unwritable dir etc. → unlocked, tolerant
    try:
        yield
    finally:
        if acquired:
            try:
                lock.unlink(missing_ok=True)
            except OSError:
                pass
