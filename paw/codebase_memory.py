"""Windows-safe codebase-memory-mcp wrapper.

The upstream CLI accepts JSON as one positional argument, which is awkward from
PowerShell. This wrapper builds the JSON payload in Python and invokes the
binary with argv directly, avoiding shell quoting entirely.  Also provides
bounded search output suitable for agents and shootout runners.
"""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class CodebaseMemoryResult:
    command: tuple[str, ...]
    returncode: int
    stdout: str
    stderr: str

    @property
    def combined(self) -> str:
        return "\n".join(part for part in (self.stdout.strip(), self.stderr.strip()) if part)

    def to_dict(self) -> dict[str, object]:
        return {
            "command": list(self.command),
            "returncode": self.returncode,
            "stdout": self.stdout,
            "stderr": self.stderr,
        }


@dataclass(frozen=True)
class SearchRow:
    """One bounded row parsed from codebase-memory search JSON output."""

    name: str
    label: str | None = None
    file_path: str | None = None
    qualified_name: str | None = None

    def to_dict(self) -> dict[str, object]:
        return {
            "name": self.name,
            "label": self.label,
            "file_path": self.file_path,
            "qualified_name": self.qualified_name,
        }


@dataclass(frozen=True)
class SearchOutput:
    """Parsed and bounded search output for agent use."""

    total: int
    rows: tuple[SearchRow, ...]
    raw: str

    def to_dict(self) -> dict[str, object]:
        return {
            "total": self.total,
            "rows": [r.to_dict() for r in self.rows],
        }


def parse_search_output(result: CodebaseMemoryResult) -> SearchOutput:
    """Parse the search_graph JSON stdout into bounded rows.

    Returns a SearchOutput even when no JSON is parseable (total=0,
    rows=(), raw=raw_text).
    """
    text = result.stdout.strip()
    if not text:
        return SearchOutput(total=0, rows=(), raw=text)
    try:
        data = json.loads(text)
    except (json.JSONDecodeError, ValueError):
        return SearchOutput(total=0, rows=(), raw=text)

    # Upstream returns either a list of match dicts directly,
    # or a dict with a 'results' key.
    items = data if isinstance(data, list) else data.get("results", data.get("matches", []))
    if not isinstance(items, list):
        return SearchOutput(total=0, rows=(), raw=text)

    rows = [
        SearchRow(
            name=_safe_str(item, "name") or _safe_str(item, "symbol") or f"#{i}",
            label=_safe_str(item, "label") or _safe_str(item, "kind"),
            file_path=_safe_str(item, "file_path") or _safe_str(item, "file"),
            qualified_name=_safe_str(item, "qualified_name") or _safe_str(item, "full_name"),
        )
        for i, item in enumerate(items)
    ]
    return SearchOutput(total=len(rows), rows=tuple(rows), raw=text)


def format_search_output(
    output: SearchOutput,
    *,
    limit: int = 10,
    json_mode: bool = False,
) -> str:
    """Render search output as compact text or full JSON.

    ``json_mode`` emits the raw result structure.  Otherwise a compact
    table with total and bounded rows.
    """
    if json_mode:
        return output.raw

    lines = [f"found {output.total} symbol(s)"]
    if not output.rows:
        return "\n".join(lines)
    shown = output.rows[:limit]
    lines.append(f"showing {len(shown)}/{output.total}:")
    for row in shown:
        parts = [row.name]
        if row.label:
            parts.append(f"[{row.label}]")
        if row.file_path:
            parts.append(f"at {row.file_path}")
        if row.qualified_name and row.qualified_name != row.name:
            parts.append(f"({row.qualified_name})")
        lines.append("  - " + " ".join(parts))
    if len(output.rows) > limit:
        lines.append(f"  ... {output.total - limit} more (use --limit N to show more)")
    return "\n".join(lines)


def codebase_memory_project_name(path: Path) -> str:
    """Project id convention observed in the foundation bench."""
    return path.as_posix().replace(":/", "-").replace("/", "-").replace("\\", "-").replace(":", "")


def default_codebase_memory_binary(*, root: Path | None = None) -> Path | None:
    root = root or Path.cwd()
    suffix = ".exe" if sys.platform == "win32" else ""
    local = root / "bench" / "_tools" / "codebase-memory-mcp" / f"codebase-memory-mcp{suffix}"
    if local.exists():
        return local
    found = shutil.which("codebase-memory-mcp")
    return Path(found) if found else None


def run_codebase_memory_tool(
    tool_name: str,
    payload: dict[str, Any],
    *,
    binary: Path,
    timeout: int = 120,
) -> CodebaseMemoryResult:
    json_payload = json.dumps(payload, ensure_ascii=False)
    command = [str(binary), "cli", tool_name, json_payload]
    completed = subprocess.run(
        command,
        capture_output=True,
        text=True,
        timeout=timeout,
    )
    return CodebaseMemoryResult(
        command=tuple(command),
        returncode=completed.returncode,
        stdout=completed.stdout,
        stderr=completed.stderr,
    )


def require_binary(root: Path, binary: str | None = None) -> Path:
    if binary:
        path = Path(binary)
        if path.exists():
            return path
        raise FileNotFoundError(f"codebase-memory-mcp binary not found: {path}")
    found = default_codebase_memory_binary(root=root)
    if found is None:
        raise FileNotFoundError(
            "codebase-memory-mcp not found (checked bench/_tools and PATH)"
        )
    return found


def _safe_str(obj: dict[str, Any], key: str) -> str | None:
    value = obj.get(key)
    return str(value) if isinstance(value, str) and value.strip() else None
