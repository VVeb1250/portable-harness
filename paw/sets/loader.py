"""Load curated sets from registry/sets.json.

Read-only. Locates the bundled registry whether running from source (repo
root has registry/) or installed (pyproject force-includes registry →
portaw/registry/). No schema framework — plain dict access + a thin dataclass
view so callers don't index raw JSON everywhere.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from functools import cache
from pathlib import Path

_HERE = Path(__file__).resolve().parent  # portaw/sets/


class SetsError(RuntimeError):
    """registry missing / unparseable / unknown set."""


def registry_path() -> Path:
    """Locate sets.json across source + installed layouts."""
    candidates = [
        _HERE.parent / "registry" / "sets.json",          # installed: portaw/registry/
        _HERE.parent.parent / "registry" / "sets.json",   # source: repo_root/registry/
    ]
    for p in candidates:
        if p.exists():
            return p
    raise SetsError(
        "sets.json not found (looked in " + ", ".join(str(c) for c in candidates) + ")"
    )


@dataclass(frozen=True)
class CuratedSet:
    """One set, as the loader exposes it. `raw` keeps the full JSON for install."""

    name: str
    description: str
    trigger_terms: tuple[str, ...]
    catalog_status: str
    default_init: bool
    link_scope: str
    foundation_tier: str
    bench_status: str
    platforms: dict
    token_tax: dict
    evidence: dict
    privacy: dict
    windows_ergonomics: dict
    mcp: tuple[dict, ...]      # MCP tool entries (config to patch)
    non_mcp: tuple[dict, ...]  # non-MCP tool entries (shim install steps)
    usage_routing: tuple[dict, ...]  # sub-intent -> rung hints (when/needs/use)
    raw: dict

    @property
    def mcp_count(self) -> int:
        """Active MCP servers = N1 ceiling unit (non-MCP don't count)."""
        return len(self.mcp)

    @classmethod
    def from_raw(cls, raw: dict) -> CuratedSet:
        return cls(
            name=raw["set_name"],
            description=raw.get("description", ""),
            trigger_terms=tuple(raw.get("trigger_terms", [])),
            catalog_status=raw.get("catalog_status", "ready"),
            default_init=bool(raw.get("default_init", False)),
            link_scope=raw.get("link_scope", "conditional"),
            foundation_tier=raw.get("foundation_tier", "specific"),
            bench_status=raw.get("bench_status", "unknown"),
            platforms=dict(raw.get("platforms", {})),
            token_tax=dict(raw.get("token_tax", {})),
            evidence=dict(raw.get("evidence", {})),
            privacy=dict(raw.get("privacy", {})),
            windows_ergonomics=dict(raw.get("windows_ergonomics", {})),
            mcp=tuple(raw.get("mcp", [])),
            non_mcp=tuple(raw.get("non_mcp", [])),
            usage_routing=tuple(raw.get("usage_routing", [])),
            raw=raw,
        )


@cache
def _load_raw() -> dict:
    path = registry_path()
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        raise SetsError(f"sets.json malformed: {e}") from e


def load_all() -> list[CuratedSet]:
    """All curated sets, in registry order."""
    data = _load_raw()
    return [CuratedSet.from_raw(s) for s in data.get("sets", [])]


def get_set(name: str) -> CuratedSet:
    """One set by name. Raises SetsError if unknown."""
    for s in load_all():
        if s.name == name:
            return s
    known = ", ".join(s.name for s in load_all()) or "(none)"
    raise SetsError(f"unknown set '{name}'. known: {known}")
