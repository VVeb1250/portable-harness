"""Host detection + config location/format.

Multi-host: Claude Code / Gemini (JSON `mcpServers`), Codex (TOML `[mcp_servers.<name>]`).
This is the foundation the patcher (sets/patcher.py) builds on. Read-only here;
writing/merging/backup lives in the patcher.
"""

from __future__ import annotations

import os
import platform
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

HostId = Literal["claude-code", "codex", "gemini", "z-code"]
ConfigFormat = Literal["json", "toml"]


def paw_root() -> Path:
    """The paw home dir — ``~/.paw`` by default, or ``$PAW_HOME`` when set.

    The override redirects EVERY paw-owned root (memory moat, session, state) so a
    live/CI dogfood run is fully self-contained and never touches the real moat.
    Read live each call so a process can set/clear it between runs."""
    override = os.environ.get("PAW_HOME")
    return Path(override) if override else Path.home() / ".paw"


@dataclass(frozen=True)
class HostConfig:
    """Where a host keeps its MCP config + how it's encoded."""

    host: HostId
    path: Path
    fmt: ConfigFormat
    # JSON path to the server map. CC/Gemini = ("mcpServers",); Codex TOML = ("mcp_servers",).
    servers_key: tuple[str, ...]


def _home() -> Path:
    return Path.home()


def _appdata() -> Path:
    # Windows roaming appdata; falls back to home for non-Windows callers.
    return Path(os.environ.get("APPDATA", str(_home())))


def host_config(host: HostId) -> HostConfig:
    """Return the config location + format for a host on the current platform.

    NOTE: paths are best-known defaults (verify per host version). Codex confirmed
    2026-06-05: ~/.codex/config.toml, table `[mcp_servers.<name>]`.
    """
    if host == "claude-code":
        # Claude Code: ~/.claude.json (project-scoped mcpServers also possible).
        return HostConfig(host, _home() / ".claude.json", "json", ("mcpServers",))
    if host == "gemini":
        # Gemini CLI: ~/.gemini/settings.json
        return HostConfig(host, _home() / ".gemini" / "settings.json", "json", ("mcpServers",))
    if host == "codex":
        # Codex CLI: ~/.codex/config.toml  → [mcp_servers.<name>]
        return HostConfig(host, _home() / ".codex" / "config.toml", "toml", ("mcp_servers",))
    if host == "z-code":
        # Z Code can import agent/MCP config; keep paw's shared layer in ~/.agents.
        return HostConfig(host, _home() / ".agents" / "mcp.json", "json", ("mcpServers",))
    raise ValueError(f"unknown host: {host}")


def detect_hosts() -> list[HostId]:
    """Return hosts whose config file currently exists on this machine."""
    found: list[HostId] = []
    for h in ("claude-code", "codex", "gemini", "z-code"):
        if host_config(h).path.exists():  # type: ignore[arg-type]
            found.append(h)  # type: ignore[arg-type]
    return found


def platform_name() -> str:
    return platform.system()
