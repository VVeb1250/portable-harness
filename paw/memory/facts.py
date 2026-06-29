"""Structured-facts wrapper — ICM's ``entity.key = value`` store.

Distinct from the semantic ``memories`` store: facts are EXACT lookups
(``entity.key``), keep supersession history automatically, and never embed.
They are the right home for project status snapshots and committed decisions,
which change over time and need precise retrieval — not a fuzzy recall match.

Two ICM gotchas this wrapper defends against:

1. **Set-honesty gap** — ``icm facts set`` prints a success line
   ("set: … = … (id=…)") optimistically. It does NOT prove the row is
   queryable. Same class as the ``icm store`` mismatch documented in
   docs/MEMORY-GOVERNANCE-NEXT. Every write is therefore verified by a
   follow-up ``get``; a write that does not become visible is reported as a
   failure, never silently accepted.

2. **``--read-only`` visibility gap** — ``icm facts get --read-only`` does NOT
   see rows written in the same short window, even though the same ``get``
   WITHOUT ``--read-only`` returns them immediately (verified live
   2026-06-29). So read paths here MUST NOT pass ``--read-only`` on facts,
   even though it is correct and cheap for the semantic ``memories`` reads.

3. **stdout/stderr split** — ``icm facts get`` writes the value to **stdout**
   and the source/created/id metadata line to **stderr** (verified live
   2026-06-29). Reads merge both streams so the meta is not lost.

All calls are fail-safe: a broken ICM degrades to ``None`` / ``[]`` /
``False`` rather than raising, because facts back the resume block that
SessionStart injects — a missing fact must never break the hook.
"""

from __future__ import annotations

import platform
import re
import subprocess
from dataclasses import dataclass
from typing import Callable, Optional

# Read commands are cheap and side-effect free; the default timeout matches the
# rest of the ICM call sites in paw. Writes get a little more headroom because
# the SQLite write + index update can briefly block under concurrent sessions.
_READ_TIMEOUT = 8
_WRITE_TIMEOUT = 12


def _icm_exe() -> str:
    return "icm.exe" if platform.system() == "Windows" else "icm"


Runner = Callable[[list[str]], subprocess.CompletedProcess]


def _default_runner(cmd: list[str], *, timeout: int) -> subprocess.CompletedProcess:
    return subprocess.run(
        cmd, check=False, capture_output=True, text=True, timeout=timeout
    )


@dataclass(frozen=True)
class FactRow:
    """A single active fact as read back from ICM."""

    entity: str
    key: str
    value: str
    source: str = ""
    created: str = ""
    id: str = ""

    @property
    def slot(self) -> str:
        return f"{self.entity}.{self.key}"


# Matches "  source: cli | created: 2026-06-29 06:18 | id: 01KW…"
_META_RE = re.compile(
    r"^\s*source:\s*(?P<source>.*?)\s*\|\s*created:\s*(?P<created>.*?)"
    r"\s*\|\s*id:\s*(?P<id>\S+)\s*$"
)


def _parse_get(blob: str, entity: str, key: str) -> Optional[FactRow]:
    """Parse the ``facts get`` output. None if absent / unparseable.

    The value may span MULTIPLE lines (e.g. a decision body), so we cannot
    just take line 0. Layout (stdout has the value, stderr has the meta):

        <value line(s)>
          source: cli | created: 2026-06-29 06:18 | id: 01KW81HX7…

    We treat everything before the indented ``source:`` meta line as the
    value. The absent case is signalled by the caller via a non-zero exit
    code (handled in ``get_fact``), so an empty blob here is a parse miss → None.
    """
    text = (blob or "").strip()
    if not text:
        return None
    lines = text.splitlines()
    value_lines: list[str] = []
    source = created = fact_id = ""
    meta_found = False
    for ln in lines:
        m = _META_RE.match(ln)
        if m and not meta_found:
            source = m.group("source").strip()
            created = m.group("created").strip()
            fact_id = m.group("id").strip()
            meta_found = True
            continue
        if not meta_found:
            value_lines.append(ln)
    value = "\n".join(value_lines).strip()
    if not value:
        return None
    return FactRow(
        entity=entity, key=key, value=value, source=source,
        created=created, id=fact_id,
    )


def get_fact(
    entity: str, key: str, *, runner: Optional[Runner] = None, db: str = ""
) -> Optional[FactRow]:
    """Read the active value for ``entity.key``. None if absent or ICM down.

    ``icm facts get`` exits 1 when the slot is empty — that is the *expected*
    miss path, not an error, so we swallow it and return None.

    ICM quirk: the value goes to **stdout** but the source/created/id metadata
    goes to **stderr** (verified live 2026-06-29). We merge both streams to find
    the value line and the meta line.
    """
    if not entity or not key:
        return None
    # NOTE: deliberately NOT passing --read-only. ``icm facts get --read-only``
    # does not see rows written in the same short window (verified live), so a
    # read-only read here would defeat the post-write honesty re-read in
    # ``set_fact``. ``--no-embeddings`` stays: facts never embed anyway.
    cmd = [_icm_exe(), "facts", "get", entity, key, "--no-embeddings"]
    if db:
        cmd += ["--db", db]
    try:
        proc = (runner or _default_runner)(cmd, timeout=_READ_TIMEOUT)
    except (OSError, subprocess.SubprocessError):
        return None
    if proc.returncode != 0:
        return None
    # Value on stdout, meta on stderr — search across both.
    blob = (proc.stdout or "") + (proc.stderr or "")
    return _parse_get(blob, entity, key)


def list_facts(
    entity: str, *, prefix: str = "", runner: Optional[Runner] = None, db: str = ""
) -> list[FactRow]:
    """List active facts for an entity. Output is a text table:

        key                              value
        ------------------------------------------------------------
        smoke_test                       value1

    No ``--format json`` on this subcommand, so we parse the table.
    """
    if not entity:
        return []
    # No --read-only: see note on get_fact — read-only misses freshly-written rows.
    cmd = [_icm_exe(), "facts", "list", entity, "--no-embeddings"]
    if prefix:
        cmd += ["--prefix", prefix]
    if db:
        cmd += ["--db", db]
    try:
        proc = (runner or _default_runner)(cmd, timeout=_READ_TIMEOUT)
    except (OSError, subprocess.SubprocessError):
        return []
    if proc.returncode != 0:
        return []
    rows: list[FactRow] = []
    for line in (proc.stdout or "").splitlines():
        stripped = line.strip()
        if not stripped:
            continue  # blank line
        # Separator rows are dashes/spaces only ("------  -----").
        if set(stripped) <= {"-", "=", " "}:
            continue
        if stripped.lower().startswith("key"):
            continue  # header row
        # Two whitespace-separated columns: key, then the rest is value.
        stripped = line.strip()
        parts = stripped.split(None, 1)
        if len(parts) < 2:
            continue
        key, value = parts[0].strip(), parts[1].strip()
        rows.append(FactRow(entity=entity, key=key, value=value))
    return rows


def history(
    entity: str, key: str, *, runner: Optional[Runner] = None, db: str = ""
) -> list[FactRow]:
    """Supersession history for a slot (oldest→newest superseded, then active).

    Output format varies across ICM versions; this returns parsed rows where the
    value column is recoverable and skips unparseable lines. Empty list on any
    error — history is a diagnostic, never load-bearing for the hot path.
    """
    if not entity or not key:
        return []
    # No --read-only: see note on get_fact.
    cmd = [_icm_exe(), "facts", "history", entity, key, "--no-embeddings"]
    if db:
        cmd += ["--db", db]
    try:
        proc = (runner or _default_runner)(cmd, timeout=_READ_TIMEOUT)
    except (OSError, subprocess.SubprocessError):
        return []
    if proc.returncode != 0:
        return []
    rows: list[FactRow] = []
    for line in (proc.stdout or "").splitlines():
        stripped = line.strip()
        if not stripped or set(stripped) <= {"-", "="} or stripped.lower().startswith(
            ("key", "value", "superseded", "history")
        ):
            continue
        # Best-effort: treat the rest of the line as the value if it looks like a
        # value cell. Full schema fidelity is not needed for diagnostics.
        rows.append(FactRow(entity=entity, key=key, value=stripped))
    return rows


def set_fact(
    entity: str,
    key: str,
    value: str,
    *,
    source: str = "paw",
    runner: Optional[Runner] = None,
    db: str = "",
    verify: bool = True,
) -> bool:
    """Write ``entity.key = value`` and confirm it became queryable.

    The follow-up ``get`` is the honesty guard: ICM's ``set`` prints a success
    id even when the row is not yet retrievable (same class of bug as
    ``icm store``). We never trust the write message alone. Pass ``verify=False``
    only for tests that stub the runner and assert the command shape directly.

    Returns True only when the post-write ``get`` returns our exact value.
    """
    if not entity or not key or value is None:
        return False
    cmd = [_icm_exe(), "facts", "set", entity, key, value, "--source", source]
    if db:
        cmd += ["--db", db]
    run = runner or _default_runner
    try:
        run(cmd, timeout=_WRITE_TIMEOUT)
    except (OSError, subprocess.SubprocessError):
        return False
    if not verify:
        return True
    # Re-read through the same runner so tests can stub both calls uniformly.
    row = get_fact(entity, key, runner=runner, db=db)
    return bool(row) and row.value == value


def forget_fact(
    entity: str, key: str, *, runner: Optional[Runner] = None, db: str = ""
) -> bool:
    """Delete a slot (active + history). True if anything was removed."""
    if not entity or not key:
        return False
    cmd = [_icm_exe(), "facts", "forget", entity, key]
    if db:
        cmd += ["--db", db]
    try:
        proc = (runner or _default_runner)(cmd, timeout=_WRITE_TIMEOUT)
    except (OSError, subprocess.SubprocessError):
        return False
    # "forgot N row(s) …" on success; anything else is a miss.
    return proc.returncode == 0 and "forgot" in (proc.stdout or "").lower()
