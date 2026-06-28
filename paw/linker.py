"""Bundle linker — write-path: plan -> apply -> verify -> remove.

The thinnest honest transaction that wires a curated set into one host and
fully reverses itself. Three independent, reversible mutations:
  - context block  → host context file (CLAUDE.md / AGENTS.md / GEMINI.md)
  - MCP servers     → project-local JSON config (.mcp.json / .gemini/settings.json)
  - PATH wiring     → machine-local settings so vendored bin/ tools run by name

slice-0 = CLI-only sets (context + binary detection). slice-1 = MCP merge for
JSON-config hosts (claude-code, gemini). Codex TOML merge (comment-preserving)
is the remaining slice-1b gap; MCP sets BLOCK on --host codex with a clear note.

Design invariants honored (docs/PAW-CLI-WORKFLOW-DRAFT.md §21):
  preview before mutation · no silent clobber (managed marker block only) ·
  explicit ownership ledger · every mutation backed up + fingerprinted ·
  drift stops automatic writes · remove touches only paw-owned text.

Stdlib only — read-path parity. No click/tomlkit needed for CLI sets.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import sys
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from shutil import which
from typing import Literal

from paw.sets.loader import CuratedSet, get_set

SCHEMA_PLAN = "paw-change-plan/v1"
SCHEMA_LEDGER = "paw-ownership-ledger/v1"
PAW_VERSION = "0.0.1"

Intent = Literal["add-set", "remove-set"]
Health = Literal["healthy", "degraded", "blocked", "drifted", "absent"]

# Default host -> context file. Project-local, never user-global in slice-0.
HOST_CONTEXT = {
    "claude-code": "CLAUDE.md",
    "codex": "AGENTS.md",
    "gemini": "GEMINI.md",
    "z-code": "AGENTS.md",
}

ABSENT = "absent"  # fingerprint sentinel for a non-existent target

# Map sys.platform -> the per-OS key registry install entries use.
_OS_KEY = {"win32": "windows", "darwin": "macos"}


# --------------------------------------------------------------------------- #
# binary resolution + install hints
# --------------------------------------------------------------------------- #
def vendored_bin_dir(root: Path) -> Path:
    """Repo-local prebuilt binaries the bundle ships (portable, off-PATH)."""
    return root / "bin"


def resolve_binary(binary: str, root: Path) -> tuple[str | None, str]:
    """Find a tool binary, preferring PATH then the vendored bin/ dir.

    Returns (location, source) where source is one of "path", "vendored",
    or "missing". location is the resolved path (for vendored) or the binary
    name (for PATH) so callers can report where it came from.
    """
    on_path = which(binary)
    if on_path:
        return on_path, "path"
    bindir = vendored_bin_dir(root)
    for candidate in (bindir / binary, bindir / f"{binary}.exe"):
        if candidate.exists():
            return str(candidate), "vendored"
    return None, "missing"


def _os_key() -> str:
    return _OS_KEY.get(sys.platform, "linux")


# Hosts whose machine-local settings file injects env into the subprocesses
# they spawn (Bash tool / shell). Only these can safely get a PATH prepend.
HOST_ENV_FILE = {
    "claude-code": (".claude", "settings.local.json"),
}


def host_env_file(host: str, root: Path) -> Path | None:
    """The host's machine-local, git-ignored settings file, or None."""
    rel = HOST_ENV_FILE.get(host)
    return root.joinpath(*rel) if rel else None


def _path_entries(value: str) -> list[str]:
    return [p for p in value.split(os.pathsep) if p]


def ensure_bin_on_path(env_file: Path, bindir: Path) -> tuple[bool, str | None]:
    """Idempotently prepend the vendored bin dir to env.PATH in a host JSON.

    Claude Code's `env` block is applied literally (no ${PATH} expansion), so
    the value must carry a full PATH. We snapshot the live PATH once, prepend
    the abs bin dir, and write it to the *machine-local* (git-ignored) settings
    so the committed repo stays portable. Returns (changed, previous_value);
    previous_value is None when we introduced the key (used to fully reverse).
    """
    data: dict = {}
    if env_file.exists():
        data = json.loads(env_file.read_text(encoding="utf-8") or "{}")
    env = data.setdefault("env", {})
    prev = env.get("PATH")
    current = prev if prev is not None else os.environ.get("PATH", "")
    absbin = str(bindir.resolve())
    entries = _path_entries(current)
    if entries[:1] == [absbin]:
        return False, prev  # already at front — idempotent
    env["PATH"] = os.pathsep.join([absbin, *[e for e in entries if e != absbin]])
    env_file.parent.mkdir(parents=True, exist_ok=True)
    env_file.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return True, prev


def remove_bin_from_path(env_file: Path, bindir: Path, prev: str | None) -> bool:
    """Reverse ensure_bin_on_path: restore prev value, or drop the key/file."""
    if not env_file.exists():
        return False
    data = json.loads(env_file.read_text(encoding="utf-8") or "{}")
    env = data.get("env", {})
    if "PATH" not in env:
        return False
    if prev is not None:
        env["PATH"] = prev  # someone owned PATH before us — restore it
    else:
        env.pop("PATH", None)  # we introduced it — remove cleanly
    if not env:
        data.pop("env", None)
    if data:
        env_file.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    else:
        env_file.unlink()
    return True


# --------------------------------------------------------------------------- #
# MCP wiring (slice-1) — JSON-config hosts only; Codex TOML deferred
# --------------------------------------------------------------------------- #
# Project-local MCP config file per host. JSON hosts use a `mcpServers` map;
# Codex uses TOML `[mcp_servers.<name>]` tables (comment-preserving via tomlkit).
HOST_MCP_FILE = {
    "claude-code": (".mcp.json",),
    "gemini": (".gemini", "settings.json"),
    "codex": (".codex", "config.toml"),
    "z-code": (".agents", "mcp.json"),
}

# Top-level key holding the server map, per config format.
_MCP_TABLE = {"json": "mcpServers", "toml": "mcp_servers"}

# Registry per-host config blocks key on these host ids (not "claude-code").
_HOST_REGISTRY_KEY = {
    "claude-code": "claude",
    "codex": "codex",
    "gemini": "gemini",
    "z-code": "claude",
    "cursor": "cursor",
}

N1_CEILING = 3  # max active MCP servers per host before review


def host_mcp_file(host: str, root: Path) -> Path | None:
    """The host's project-local JSON MCP config file, or None if unsupported."""
    rel = HOST_MCP_FILE.get(host)
    return root.joinpath(*rel) if rel else None


def _clean_cfg(cfg: dict) -> dict:
    """Drop registry annotation keys (_target/_note/...) from a config block."""
    return {k: v for k, v in cfg.items() if not k.startswith("_")}


def _host_anchors(entry: dict) -> list[str] | None:
    anchor = entry.get("host_anchor")
    if anchor is None:
        return None
    return [anchor] if isinstance(anchor, str) else list(anchor)


def mcp_servers_for(item: CuratedSet, host: str) -> dict[str, dict]:
    """Resolve {server_name: config} for one host, honoring host_anchor.

    A tool whose host_anchor excludes this host is skipped (codegraph XOR
    semble). Per-host config block wins over the canonical mcp_config.
    """
    hostkey = _HOST_REGISTRY_KEY.get(host, host)
    out: dict[str, dict] = {}
    for entry in item.mcp:
        anchors = _host_anchors(entry)
        if anchors is not None and host not in anchors and hostkey not in anchors:
            continue
        per = entry.get("mcp_config_per_host", {})
        cfg = per.get(hostkey) or entry.get("mcp_config", {})
        out[entry["tool"]] = _clean_cfg(cfg)
    return out


def _mcp_format(mcp_file: Path) -> str:
    return "toml" if mcp_file.suffix == ".toml" else "json"


def mcp_toml_supported() -> bool:
    """Codex TOML merge needs tomlkit (the [cli] extra) to preserve comments."""
    try:
        import tomlkit  # noqa: F401
        return True
    except ImportError:
        return False


def read_mcp_servers(mcp_file: Path) -> dict[str, dict]:
    """The server map, format-detected. Always returns plain dicts."""
    if not mcp_file.exists():
        return {}
    text = mcp_file.read_text(encoding="utf-8")
    if _mcp_format(mcp_file) == "toml":
        import tomllib
        return tomllib.loads(text).get("mcp_servers", {})
    return (json.loads(text or "{}")).get("mcpServers", {})


def merge_mcp_servers(
    mcp_file: Path, servers: dict[str, dict]
) -> tuple[tuple[str, ...], dict[str, dict | None]]:
    """Merge servers into the host config; return (added_names, prior_values).

    Dispatches on file format. prior_values maps each touched server -> its
    previous config (None if introduced) so remove can restore or delete it.
    """
    if _mcp_format(mcp_file) == "toml":
        return _merge_mcp_toml(mcp_file, servers)
    return _merge_mcp_json(mcp_file, servers)


def remove_mcp_servers(mcp_file: Path, prior: dict[str, dict | None]) -> tuple[str, ...]:
    """Reverse merge_mcp_servers, format-detected."""
    if not mcp_file.exists():
        return ()
    if _mcp_format(mcp_file) == "toml":
        return _remove_mcp_toml(mcp_file, prior)
    return _remove_mcp_json(mcp_file, prior)


def _merge_mcp_json(mcp_file, servers):
    doc = json.loads(mcp_file.read_text(encoding="utf-8") or "{}") if mcp_file.exists() else {}
    registry = doc.setdefault("mcpServers", {})
    prior: dict[str, dict | None] = {}
    added: list[str] = []
    for name, cfg in servers.items():
        if registry.get(name) == cfg:
            continue  # idempotent — already exactly this
        prior[name] = registry.get(name)
        registry[name] = cfg
        added.append(name)
    if added:
        mcp_file.parent.mkdir(parents=True, exist_ok=True)
        mcp_file.write_text(
            json.dumps(doc, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
    return tuple(added), prior


def _remove_mcp_json(mcp_file, prior):
    doc = json.loads(mcp_file.read_text(encoding="utf-8") or "{}")
    registry = doc.get("mcpServers", {})
    removed: list[str] = []
    for name, prev in prior.items():
        if prev is None:
            if registry.pop(name, None) is not None:
                removed.append(name)
        else:
            registry[name] = prev
            removed.append(name)
    if not registry:
        doc.pop("mcpServers", None)
    if doc:
        mcp_file.write_text(
            json.dumps(doc, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
    else:
        mcp_file.unlink()  # JSON MCP file is paw-owned; safe to drop when empty
    return tuple(removed)


def _toml_table(cfg: dict):
    import tomlkit
    tbl = tomlkit.table()
    for k, v in cfg.items():
        tbl[k] = v
    return tbl


def _merge_mcp_toml(mcp_file, servers):
    """Comment-preserving merge into [mcp_servers.<name>] tables (Codex)."""
    import tomlkit

    text = mcp_file.read_text(encoding="utf-8") if mcp_file.exists() else ""
    plain = read_mcp_servers(mcp_file)  # tomllib -> plain dicts for compare
    doc = tomlkit.parse(text) if text else tomlkit.document()
    if "mcp_servers" not in doc:
        doc["mcp_servers"] = tomlkit.table(is_super_table=True)
    registry = doc["mcp_servers"]
    prior: dict[str, dict | None] = {}
    added: list[str] = []
    for name, cfg in servers.items():
        if plain.get(name) == cfg:
            continue  # idempotent
        prior[name] = plain.get(name)
        registry[name] = _toml_table(cfg)
        added.append(name)
    if added:
        mcp_file.parent.mkdir(parents=True, exist_ok=True)
        mcp_file.write_text(tomlkit.dumps(doc), encoding="utf-8")
    return tuple(added), prior


def _remove_mcp_toml(mcp_file, prior):
    """Reverse _merge_mcp_toml; never unlinks (config.toml holds user state)."""
    import tomlkit

    doc = tomlkit.parse(mcp_file.read_text(encoding="utf-8"))
    registry = doc.get("mcp_servers")
    if registry is None:
        return ()
    removed: list[str] = []
    for name, prev in prior.items():
        if prev is None:
            if name in registry:
                del registry[name]
                removed.append(name)
        else:
            registry[name] = _toml_table(prev)
            removed.append(name)
    if len(registry) == 0:
        del doc["mcp_servers"]
    mcp_file.write_text(tomlkit.dumps(doc), encoding="utf-8")
    return tuple(removed)


def install_command(tool: dict) -> str | None:
    """The install command for this host's OS, or None if the tool ships none.

    Registry `install[].cmd` is either a plain string (any OS) or a per-OS
    dict keyed windows/macos/linux. Pick the first install step that resolves.
    """
    for step in tool.get("install", ()):
        cmd = step.get("cmd")
        if isinstance(cmd, str):
            return cmd
        if isinstance(cmd, dict):
            resolved = cmd.get(_os_key())
            if resolved:
                return resolved
    return None


# --------------------------------------------------------------------------- #
# fingerprint + managed marker block
# --------------------------------------------------------------------------- #
def fingerprint(path: Path) -> str:
    """sha256 of file bytes, or ABSENT if the file does not exist."""
    if not path.exists():
        return ABSENT
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _markers(set_name: str) -> tuple[str, str]:
    return f"<!-- paw:{set_name}:start -->", f"<!-- paw:{set_name}:end -->"


def _block_re(set_name: str) -> re.Pattern[str]:
    start, end = (re.escape(m) for m in _markers(set_name))
    return re.compile(rf"\n?{start}.*?{end}\n?", re.DOTALL)


def has_block(text: str, set_name: str) -> bool:
    return _block_re(set_name).search(text) is not None


def render_block(item: CuratedSet) -> str:
    """The managed body: what the agent needs to know the capability exists."""
    start, end = _markers(item.name)
    lines = [
        start,
        f"## paw capability · {item.name}",
        item.description,
        "",
    ]
    for tool in item.non_mcp:
        binary = tool.get("health_binary") or tool["tool"]
        lines.append(f"- **{tool['tool']}** (`{binary}`): {tool.get('purpose', '').strip()}")
        if tool.get("usage_hint"):
            lines.append(f"  - usage: `{tool['usage_hint']}`")
        hint = install_command(tool)
        if hint:
            lines.append(f"  - install: `{hint}`")
    lines.append(end)
    return "\n".join(lines)


def inject_block(text: str, item: CuratedSet) -> str:
    """Insert or replace the set's managed block; leave all other text intact."""
    body = render_block(item)
    pattern = _block_re(item.name)
    if pattern.search(text):
        return pattern.sub("\n" + body + "\n", text, count=1)
    sep = "" if text.endswith("\n") or not text else "\n"
    prefix = text + sep
    return f"{prefix}\n{body}\n"


def strip_block(text: str, set_name: str) -> str:
    """Remove only the set's managed block (and a single surrounding blank)."""
    return _block_re(set_name).sub("\n", text, count=1).rstrip("\n") + (
        "\n" if text.endswith("\n") else ""
    )


# --------------------------------------------------------------------------- #
# change plan
# --------------------------------------------------------------------------- #
@dataclass(frozen=True)
class Action:
    id: str
    kind: Literal[
        "detect-binary",
        "inject-context-block",
        "strip-context-block",
        "wire-path",
        "inject-mcp",
    ]
    target: str
    summary: str
    reversible: bool
    requires_approval: bool
    before_fingerprint: str | None = None


@dataclass(frozen=True)
class ChangePlan:
    intent: Intent
    set_name: str
    host: str
    scope: str
    context_path: str
    actions: tuple[Action, ...] = ()
    warnings: tuple[str, ...] = ()
    wire_policy: str = "ready"
    wire_reason: str = "catalog default"
    schema: str = SCHEMA_PLAN

    @property
    def status(self) -> Literal["ok", "blocked"]:
        return "blocked" if any(w.startswith("BLOCK:") for w in self.warnings) else "ok"

    @property
    def summary(self) -> str:
        verb = "Add" if self.intent == "add-set" else "Remove"
        return (
            f"{verb} {self.set_name} {'to' if self.intent == 'add-set' else 'from'} "
            f"{self.host} ({self.scope}) · {len(self.actions)} action(s), "
            f"{len(self.warnings)} warning(s) [{self.status}]"
        )

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


def _resolve_context(host: str, context: str | None, root: Path) -> Path:
    if context:
        return Path(context)
    name = HOST_CONTEXT.get(host)
    if not name:
        raise LinkerError(f"unknown host '{host}' (known: {', '.join(HOST_CONTEXT)})")
    return root / name


class LinkerError(RuntimeError):
    """unknown set/host or an unsupported set shape."""


def _set_has_vendored_binary(item: CuratedSet, root: Path) -> bool:
    """True if any tool in the set resolves to a binary in the vendored bin/."""
    for tool in item.non_mcp:
        binary = tool.get("health_binary")
        if binary and resolve_binary(binary, root)[1] == "vendored":
            return True
    return False


def build_plan(
    set_name: str,
    host: str = "claude-code",
    *,
    context: str | None = None,
    scope: str = "project",
    root: Path | None = None,
) -> ChangePlan:
    """Pure: derive the change plan, no mutation, no I/O beyond reads."""
    root = root or Path.cwd()
    item = get_set(set_name)  # raises SetsError on unknown
    ctx = _resolve_context(host, context, root)
    warnings: list[str] = []
    wire_policy = str(item.raw.get("catalog_status") or "ready")
    wire_reason = "catalog status"

    if item.raw.get("catalog_status") == "detect-first":
        return ChangePlan(
            intent="add-set",
            set_name=set_name,
            host=host,
            scope=scope,
            context_path=str(ctx),
            actions=(),
            warnings=(
                f"BLOCK: {set_name} is detect-first, not a blind installable set. "
                "Detect existing foundation state and follow docs/ECC-INTEGRATION-LEDGER.md.",
            ),
            wire_policy="detect-first",
            wire_reason=(
                "foundation install state must be detected before mutation; "
                "see docs/ECC-INTEGRATION-LEDGER.md"
            ),
        )
    if item.raw.get("catalog_status") == "conditional":
        wire_reason = "host/workload tradeoff must clear docs/WIRE-DECISION-MATRIX.md"
        warnings.append(
            f"CONDITIONAL: {set_name} must clear host/workload tradeoff gates before "
            "default wiring; review docs/WIRE-DECISION-MATRIX.md and verify after apply."
        )

    # MCP wiring: JSON hosts (CC/gemini) + Codex TOML (comment-preserving).
    mcp_servers: dict[str, dict] = {}
    mcp_file: Path | None = None
    if item.mcp:
        mcp_file = host_mcp_file(host, root)
        if mcp_file is None:
            warnings.append(
                f"BLOCK: {set_name} has MCP server(s) but host '{host}' has no known "
                "MCP config file. Use claude-code, codex, or gemini."
            )
        elif _mcp_format(mcp_file) == "toml" and not mcp_toml_supported():
            warnings.append(
                "BLOCK: Codex TOML merge needs tomlkit. Install the cli extra: "
                "pip install 'port-a-whip[cli]'."
            )
            mcp_file = None
        else:
            mcp_servers = mcp_servers_for(item, host)
            if not mcp_servers:
                warnings.append(
                    f"{set_name}: no MCP server applies to {host} (host_anchor mismatch)"
                )

    if host not in {h for t in item.non_mcp for h in t.get("host_support", [])} and item.non_mcp:
        warnings.append(f"host {host} is not listed in host_support for some tools")

    actions: list[Action] = []
    # Detect health binaries for CLI tools + only the MCP tools wired on this
    # host (skip the XOR alternative, e.g. semble when codegraph is the anchor).
    mcp_to_detect = [t for t in item.mcp if t["tool"] in mcp_servers]
    for tool in (*item.non_mcp, *mcp_to_detect):
        binary = tool.get("health_binary")
        if binary:
            location, source = resolve_binary(binary, root)
            if source == "path":
                detail = "found on PATH"
            elif source == "vendored":
                rel = Path(location).relative_to(root)
                detail = f"found in vendored {rel.as_posix()}"
            else:
                hint = install_command(tool)
                detail = f"MISSING — install: {hint}" if hint else "MISSING — no install recipe"
            actions.append(
                Action(
                    id=f"detect:{binary}",
                    kind="detect-binary",
                    target=binary,
                    summary=f"{binary} {detail}",
                    reversible=True,
                    requires_approval=False,
                )
            )
            if source == "missing":
                hint = install_command(tool)
                tail = f" → {hint}" if hint else ""
                warnings.append(
                    f"{binary} not on PATH or vendored bin/; capability degraded until installed{tail}"
                )

    blocked = any(w.startswith("BLOCK:") for w in warnings)

    if mcp_servers and mcp_file is not None and not blocked:
        # count only active servers (Codex keeps enabled=false stubs that load no defs)
        existing_active = {
            n for n, c in read_mcp_servers(mcp_file).items()
            if not (isinstance(c, dict) and c.get("enabled") is False)
        }
        union = existing_active | set(mcp_servers)
        if len(union) > N1_CEILING:
            warnings.append(
                f"N1: {len(union)} active MCP servers on {host} after wiring "
                f"(ceiling {N1_CEILING}) — review token tax before applying"
            )
        actions.append(
            Action(
                id=f"mcp:{item.name}",
                kind="inject-mcp",
                target=str(mcp_file),
                summary=(
                    f"merge {len(mcp_servers)} MCP server(s) "
                    f"[{', '.join(sorted(mcp_servers))}] into {mcp_file.name}"
                ),
                reversible=True,
                requires_approval=True,
                before_fingerprint=fingerprint(mcp_file),
            )
        )

    if item.non_mcp and not blocked:
        actions.append(
            Action(
                id=f"context:{item.name}",
                kind="inject-context-block",
                target=str(ctx),
                summary=f"inject managed paw:{item.name} block into {ctx.name}",
                reversible=True,
                requires_approval=True,
                before_fingerprint=fingerprint(ctx),
            )
        )
        env_file = host_env_file(host, root)
        if env_file is not None and _set_has_vendored_binary(item, root):
            bindir = vendored_bin_dir(root)
            actions.append(
                Action(
                    id=f"path:{item.name}",
                    kind="wire-path",
                    target=str(env_file),
                    summary=(
                        f"prepend {bindir.name}/ to PATH in {env_file.name} "
                        "(machine-local, reversible) so vendored tools run by bare name"
                    ),
                    reversible=True,
                    requires_approval=True,
                    before_fingerprint=fingerprint(env_file),
                )
            )
    return ChangePlan(
        intent="add-set",
        set_name=set_name,
        host=host,
        scope=scope,
        context_path=str(ctx),
        actions=tuple(actions),
        warnings=tuple(warnings),
        wire_policy=wire_policy,
        wire_reason=wire_reason,
    )


# --------------------------------------------------------------------------- #
# ownership ledger
# --------------------------------------------------------------------------- #
def ledger_path(root: Path) -> Path:
    return root / ".paw" / "state.json"


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _load_ledger(root: Path) -> dict:
    p = ledger_path(root)
    if not p.exists():
        return {"schema": SCHEMA_LEDGER, "paw_version": PAW_VERSION, "sets": {}}
    return json.loads(p.read_text(encoding="utf-8-sig"))


def _ledger_key(set_name: str, host: str) -> str:
    return f"{host}:{set_name}"


def _ledger_record(data: dict, set_name: str, host: str) -> dict | None:
    """Host-scoped ledger lookup with legacy fallback for pre-host-key records."""
    record = data.get("sets", {}).get(_ledger_key(set_name, host))
    if isinstance(record, dict):
        return record
    legacy = data.get("sets", {}).get(set_name)
    return legacy if isinstance(legacy, dict) and legacy.get("host") == host else None


def _pop_ledger_record(data: dict, set_name: str, host: str) -> None:
    data.get("sets", {}).pop(_ledger_key(set_name, host), None)
    legacy = data.get("sets", {}).get(set_name)
    if isinstance(legacy, dict) and legacy.get("host") == host:
        data["sets"].pop(set_name, None)


def _save_ledger(root: Path, data: dict) -> None:
    p = ledger_path(root)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def _refresh_context_fingerprints(data: dict, context_path: Path, after: str) -> None:
    """A context file can contain many paw-owned blocks.

    Applying one more set legitimately changes the file fingerprint for every
    already-linked set in that same file. Without refreshing sibling records,
    `verify` misclassifies paw's own later writes as user drift.
    """
    resolved = str(context_path)
    for record in data.get("sets", {}).values():
        if isinstance(record, dict) and record.get("context_path") == resolved:
            record["after_fingerprint"] = after


# --------------------------------------------------------------------------- #
# apply / verify / remove
# --------------------------------------------------------------------------- #
@dataclass(frozen=True)
class TxResult:
    status: Literal["ok", "blocked", "error", "drifted"]
    summary: str
    actions_applied: tuple[str, ...] = ()
    health: Health | None = None
    checks: tuple[str, ...] = ()
    backup: str | None = None
    next_actions: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


def _backup(path: Path) -> str | None:
    if not path.exists():
        return None
    bak = path.with_name(f"{path.name}.paw-bak-{datetime.now(timezone.utc):%Y%m%dT%H%M%SZ}")
    bak.write_bytes(path.read_bytes())
    return str(bak)


def apply_plan(plan: ChangePlan, *, root: Path | None = None) -> TxResult:
    """Execute a plan with per-file drift guards + backups; commit ownership.

    Handles three independent mutations — context block, MCP server merge, and
    PATH wiring — so a set may be CLI-only, MCP-only, or both.
    """
    root = root or Path.cwd()
    if plan.status == "blocked":
        return TxResult("blocked", plan.summary, next_actions=("resolve plan warnings",))

    inject = next((a for a in plan.actions if a.kind == "inject-context-block"), None)
    mcp_action = next((a for a in plan.actions if a.kind == "inject-mcp"), None)
    wire = next((a for a in plan.actions if a.kind == "wire-path"), None)
    if inject is None and mcp_action is None:
        return TxResult("ok", "nothing to wire (no context or MCP action)", health="absent")

    # drift guard each target up front — refuse the whole tx if any drifted.
    for action in (inject, mcp_action):
        if action is not None and fingerprint(Path(action.target)) != (
            action.before_fingerprint or ABSENT
        ):
            name = Path(action.target).name
            return TxResult(
                "drifted",
                f"{name} changed since the plan was built; refusing to write",
                next_actions=("regenerate the plan", f"inspect the {name} diff"),
            )

    item = get_set(plan.set_name)
    record: dict = {
        "host": plan.host,
        "scope": plan.scope,
        "applied_at": _now(),
        "paw_version": PAW_VERSION,
    }
    wired: list[str] = []
    primary_backup: str | None = None

    injected_ctx: Path | None = None
    if inject is not None:
        ctx = Path(inject.target)
        backup = _backup(ctx)
        primary_backup = backup
        before = ctx.read_text(encoding="utf-8") if ctx.exists() else ""
        ctx.parent.mkdir(parents=True, exist_ok=True)
        ctx.write_text(inject_block(before, item), encoding="utf-8")
        injected_ctx = ctx
        record.update(
            context_path=str(ctx),
            block_owner="paw-injected",
            before_fingerprint=inject.before_fingerprint,
            after_fingerprint=fingerprint(ctx),
            backup=backup,
        )
        wired.append(f"context:{ctx.name}")

    if mcp_action is not None:
        mcp_file = Path(mcp_action.target)
        mcp_backup = _backup(mcp_file)
        servers = mcp_servers_for(item, plan.host)
        added, prior = merge_mcp_servers(mcp_file, servers)
        record["mcp_wiring"] = {
            "mcp_file": str(mcp_file),
            "servers": list(servers),
            "prior": prior,
            "backup": mcp_backup,
        }
        if primary_backup is None:
            primary_backup = mcp_backup
        if added:
            wired.append(f"mcp:{', '.join(added)}")

    path_wired = False
    if wire is not None:
        env_file = Path(wire.target)
        path_backup = _backup(env_file)
        changed, prev = ensure_bin_on_path(env_file, vendored_bin_dir(root))
        path_wired = changed
        record["path_wiring"] = {
            "env_file": str(env_file),
            "previous_path": prev,
            "introduced": prev is None,
            "backup": path_backup,
        }

    data = _load_ledger(root)
    if injected_ctx is not None:
        _refresh_context_fingerprints(data, injected_ctx, fingerprint(injected_ctx))
    data["sets"][_ledger_key(plan.set_name, plan.host)] = record
    _save_ledger(root, data)

    note = " (PATH wired)" if path_wired else ""
    detail = ", ".join(wired) or "no-op"
    # Router outcome loop: a successful apply is a suggestion CONVERSION. Record
    # it so the router's demotion logic stops suppressing a set the user actually
    # uses. Fail-safe no-op — a ledger failure must never fail an apply.
    try:
        from .memory.outcomes import mark_used
        mark_used(plan.set_name)
    except Exception:
        pass
    return TxResult(
        "ok",
        f"linked {plan.set_name} → {detail}{note}",
        actions_applied=tuple(a.id for a in plan.actions),
        health="healthy" if all("MISSING" not in a.summary for a in plan.actions) else "degraded",
        backup=primary_backup,
        next_actions=(f"paw verify {plan.set_name}",),
    )


def verify(
    set_name: str,
    *,
    host: str = "claude-code",
    context: str | None = None,
    root: Path | None = None,
) -> TxResult:
    """Layered check across context block, MCP servers, drift, and binaries."""
    root = root or Path.cwd()
    item = get_set(set_name)
    checks: list[str] = []
    record = _ledger_record(_load_ledger(root), set_name, host)
    linked = drifted = degraded = False

    if item.non_mcp:
        ctx = _resolve_context(host, context, root)
        text = ctx.read_text(encoding="utf-8") if ctx.exists() else ""
        if has_block(text, set_name):
            linked = True
            checks.append(f"context block: present in {ctx.name}")
            if record and fingerprint(ctx) != record.get("after_fingerprint"):
                checks.append("fingerprint: DRIFTED since apply (file edited outside paw)")
                drifted = True
            else:
                checks.append(
                    "fingerprint: matches ledger" if record else "fingerprint: no ledger record"
                )
        else:
            checks.append(f"context block: ABSENT in {ctx.name}")

    if item.mcp:
        mcp_file = host_mcp_file(host, root)
        if mcp_file is None:
            checks.append(f"mcp: host {host} not supported (slice-1 JSON config only)")
        else:
            present = read_mcp_servers(mcp_file)
            want = mcp_servers_for(item, host)
            have = [n for n in want if n in present]
            missing = [n for n in want if n not in present]
            if have:
                linked = True
                checks.append(f"mcp servers: present {', '.join(have)} in {mcp_file.name}")
            if missing:
                checks.append(f"mcp servers: MISSING {', '.join(missing)}")
                degraded = True

    if not linked:
        return TxResult("ok", f"{set_name} not linked", health="blocked", checks=tuple(checks))

    for tool in (*item.non_mcp, *item.mcp):
        binary = tool.get("health_binary")
        if binary:
            location, source = resolve_binary(binary, root)
            if source == "path":
                checks.append(f"binary {binary}: on PATH")
            elif source == "vendored":
                rel = Path(location).relative_to(root)
                checks.append(f"binary {binary}: vendored {rel.as_posix()}")
            else:
                hint = install_command(tool)
                checks.append(
                    f"binary {binary}: MISSING ({hint})" if hint else f"binary {binary}: MISSING"
                )
                degraded = True

    health: Health = "drifted" if drifted else "degraded" if degraded else "healthy"
    return TxResult(
        "ok" if health != "drifted" else "drifted",
        f"{set_name}: {health}",
        health=health,
        checks=tuple(checks),
    )


def remove(
    set_name: str,
    *,
    host: str = "claude-code",
    context: str | None = None,
    root: Path | None = None,
) -> TxResult:
    """Reverse paw-owned wiring (context block, MCP servers, PATH); drift-safe."""
    root = root or Path.cwd()
    item = get_set(set_name)
    ctx = _resolve_context(host, context, root)
    data = _load_ledger(root)
    record = _ledger_record(data, set_name, host)

    has_ctx_block = bool(
        item.non_mcp and ctx.exists() and has_block(ctx.read_text(encoding="utf-8"), set_name)
    )
    mcp_wiring = (record or {}).get("mcp_wiring")
    path_wiring = (record or {}).get("path_wiring")

    if not has_ctx_block and not mcp_wiring and not path_wiring:
        _pop_ledger_record(data, set_name, host)
        _save_ledger(root, data)
        return TxResult("ok", f"{set_name} already unlinked", health="blocked")

    applied: list[str] = []
    backup: str | None = None

    if has_ctx_block:
        # drift guard: do not strip if the file changed since paw wrote it.
        if record and fingerprint(ctx) != record.get("after_fingerprint"):
            return TxResult(
                "drifted",
                f"{ctx.name} changed since paw wrote it; refusing to auto-remove",
                next_actions=("inspect the diff", "remove the paw block manually"),
            )
        backup = _backup(ctx)
        ctx.write_text(strip_block(ctx.read_text(encoding="utf-8"), set_name), encoding="utf-8")
        applied.append(f"strip:{set_name}")
        _refresh_context_fingerprints(data, ctx, fingerprint(ctx))

    if mcp_wiring:
        removed = remove_mcp_servers(
            Path(mcp_wiring["mcp_file"]), mcp_wiring.get("prior", {})
        )
        if removed:
            applied.append(f"unwire-mcp:{', '.join(removed)}")

    if path_wiring:
        if remove_bin_from_path(
            Path(path_wiring["env_file"]), vendored_bin_dir(root), path_wiring.get("previous_path")
        ):
            applied.append(f"unwire-path:{set_name}")

    _pop_ledger_record(data, set_name, host)
    _save_ledger(root, data)
    return TxResult(
        "ok",
        f"unlinked {set_name}",
        actions_applied=tuple(applied),
        health="blocked",
        backup=backup,
    )
