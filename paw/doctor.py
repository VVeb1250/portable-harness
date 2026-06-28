"""Paw init/doctor readiness checks.

This is intentionally read-only: it verifies the default foundation core,
surfaces install hints for missing tools, reports ICM/pending/hook/mesh
state, and points out host sessions that should be restarted/reloaded after
paw-owned config/env wiring.
"""

from __future__ import annotations

import json
import subprocess
import sys
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Literal

from paw.linker import host_mcp_file, install_command, ledger_path, resolve_binary
from paw.sets.loader import CuratedSet, load_all

DoctorStatus = Literal["healthy", "degraded"]
ToolStatus = Literal["present", "missing", "skipped"]

# ── ICM ──────────────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class ICMCheck:
    status: DoctorStatus
    topics: tuple[tuple[str, int], ...]
    pending_count: int
    summary: str

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


def _query_icm() -> ICMCheck | None:
    """Call icm.exe topics and parse the per-topic count table.

    Returns None when ICM is not installed or cannot be queried (no error
    — doctor is always read-only and non-blocking).
    """
    try:
        args = ["icm.exe", "topics", "--read-only"]
        proc = subprocess.run(args, capture_output=True, text=True, timeout=10)
        if proc.returncode != 0:
            return None
        topics: list[tuple[str, int]] = []
        pending_count = 0
        for line in proc.stdout.splitlines():
            if "Count" in line or "--------" in line or not line.strip():
                continue
            parts = line.strip().split(None, 1)
            if len(parts) == 2:
                name, count_str = parts
                try:
                    count = int(count_str)
                except ValueError:
                    continue
                topics.append((name, count))
                if name == "pending":
                    pending_count = count
        if not topics:
            return None
        status: DoctorStatus = "degraded" if pending_count > 20 else "healthy"
        summary = (
            f"{len(topics)} topics, {sum(c for _, c in topics)} total memories"
        )
        if pending_count:
            summary += f", {pending_count} pending"
        return ICMCheck(
            status=status,
            topics=tuple(topics),
            pending_count=pending_count,
            summary=summary,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired, OSError):
        return None


# ── Hooks ────────────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class HookCheck:
    host: str
    config_path: str | None
    config_present: bool
    memory_hooks: tuple[str, ...]

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


_PAW_MEMORY_COMMANDS = (
    "paw memory hook",
    "paw reflect",
    "paw curate --surface",
)


def _check_host_hooks(host: str) -> HookCheck:
    if host == "claude-code":
        path = Path.home() / ".claude" / "settings.json"
    elif host == "codex":
        path = Path.home() / ".codex" / "hooks.json"
    elif host == "z-code":
        path = Path.home() / ".zcode" / "skills" / "paw-bundle" / "SKILL.md"
    else:
        path = Path.home() / f".{host}" / "hooks.json"

    if not path.exists():
        return HookCheck(
            host=host,
            config_path=str(path),
            config_present=False,
            memory_hooks=(),
        )

    if host == "z-code":
        try:
            text = path.read_text(encoding="utf-8")
        except OSError:
            text = ""
        found = []
        for cmd in ("paw surface", "paw memory hook", "paw memory post"):
            if cmd in text:
                found.append(cmd)
        return HookCheck(
            host=host,
            config_path=str(path),
            config_present=True,
            memory_hooks=tuple(found),
        )

    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return HookCheck(
            host=host,
            config_path=str(path),
            config_present=True,
            memory_hooks=(),
        )

    found: list[str] = []
    hooks = data.get("hooks") if isinstance(data, dict) else None
    if isinstance(hooks, dict):
        text = json.dumps(hooks)
        for cmd in _PAW_MEMORY_COMMANDS:
            if cmd in text:
                found.append(cmd)

    return HookCheck(
        host=host,
        config_path=str(path),
        config_present=True,
        memory_hooks=tuple(found),
    )


# ── Mesh ─────────────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class MeshMemberSummary:
    member: str
    host: str
    role: str
    last_seen: float
    active: bool

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


@dataclass(frozen=True)
class MeshCheck:
    status: DoctorStatus
    member_count: int
    active_count: int
    stale_count: int
    members: tuple[MeshMemberSummary, ...]
    summary: str

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


def _query_mesh(project: str = "portable-harness") -> MeshCheck | None:
    """Read per-project mesh state from ~/.paw/state/memory-mesh/.

    Returns None when no mesh state file exists (no error — project may
    not have mesh activity yet, which is normal).
    """
    mesh_root = Path.home() / ".paw" / "state" / "memory-mesh"
    mesh_file = mesh_root / project / "live.json"
    if not mesh_file.exists():
        return None

    try:
        data = json.loads(mesh_file.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None

    members_raw = data.get("members") if isinstance(data, dict) else {}
    now = time.time()
    members_list: list[MeshMemberSummary] = []
    active = 0
    stale = 0

    for member_key, member_data in members_raw.items():
        if not isinstance(member_data, dict):
            continue
        last_seen = member_data.get("last_seen", 0)
        ttl = member_data.get("ttl_seconds", 300)
        is_active = (now - last_seen) < ttl
        if is_active:
            active += 1
        else:
            stale += 1
        members_list.append(MeshMemberSummary(
            member=member_key,
            host=member_data.get("host", "?"),
            role=member_data.get("role", "?"),
            last_seen=last_seen,
            active=is_active,
        ))

    total = len(members_list)
    status: DoctorStatus = "degraded" if stale > total / 2 else "healthy"
    summary = (
        f"{total} member{'s' if total != 1 else ''}"
        f" ({active} active, {stale} stale)"
    )
    return MeshCheck(
        status=status,
        member_count=total,
        active_count=active,
        stale_count=stale,
        members=tuple(members_list),
        summary=summary,
    )


# ── Existing checks ──────────────────────────────────────────────────────────


@dataclass(frozen=True)
class ToolCheck:
    set_name: str
    tool: str
    binary: str | None
    status: ToolStatus
    source: str
    location: str | None = None
    install_hint: str | None = None

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


@dataclass(frozen=True)
class SetCheck:
    name: str
    description: str
    health: DoctorStatus
    tools: tuple[ToolCheck, ...]

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


@dataclass(frozen=True)
class HostCheck:
    host: str
    config_path: str | None
    config_present: bool
    linked_sets: tuple[str, ...]
    restart_required: bool
    restart_reasons: tuple[str, ...]

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


@dataclass(frozen=True)
class DoctorReport:
    status: DoctorStatus
    sets: tuple[SetCheck, ...]
    hosts: tuple[HostCheck, ...]
    next_actions: tuple[str, ...]
    icm: ICMCheck | None = None
    hooks: tuple[HookCheck, ...] = ()
    mesh: MeshCheck | None = None

    def to_dict(self) -> dict[str, object]:
        base = asdict(self)
        return base


def default_init_sets() -> list[CuratedSet]:
    """The registry-declared default foundation core, in catalog order."""
    return [item for item in load_all() if item.default_init]


def run_doctor(
    *,
    root: Path | None = None,
    hosts: tuple[str, ...] = ("claude-code", "codex", "gemini", "z-code"),
) -> DoctorReport:
    root = root or Path.cwd()
    set_checks = tuple(_check_set(item, root) for item in default_init_sets())
    host_checks = tuple(_check_host(host, root) for host in hosts)
    missing = [
        tool
        for set_check in set_checks
        for tool in set_check.tools
        if tool.status == "missing"
    ]

    # New checks: ICM, hooks, mesh
    icm = _query_icm()
    hook_checks = tuple(_check_host_hooks(host) for host in hosts)
    mesh = _query_mesh()

    # Collect next-actions from all sources
    next_actions = list(_next_actions(missing, host_checks))
    if icm and icm.pending_count > 20:
        next_actions.append(f"curate {icm.pending_count} pending ICM items")
    if mesh and mesh.stale_count:
        next_actions.append(
            f"{mesh.stale_count} stale mesh member{'s' if mesh.stale_count != 1 else ''}"
        )

    status: DoctorStatus = "degraded" if missing else "healthy"
    # Downgrade overall status if ICM pending is high or mesh is degraded
    if icm and icm.status == "degraded":
        status = "degraded"
    if mesh and mesh.status == "degraded":
        status = "degraded"

    return DoctorReport(
        status=status,
        sets=set_checks,
        hosts=host_checks,
        icm=icm,
        hooks=hook_checks,
        mesh=mesh,
        next_actions=tuple(next_actions),
    )


def _check_set(item: CuratedSet, root: Path) -> SetCheck:
    tools = tuple(_check_tool(item.name, tool, root) for tool in item.non_mcp)
    missing = any(tool.status == "missing" for tool in tools)
    return SetCheck(
        name=item.name,
        description=item.description,
        health="degraded" if missing else "healthy",
        tools=tools,
    )


def _check_tool(set_name: str, tool: dict, root: Path) -> ToolCheck:
    binary = _health_binary(tool)
    if not binary:
        return ToolCheck(
            set_name=set_name,
            tool=tool["tool"],
            binary=None,
            status="skipped",
            source="no-health-binary",
            install_hint=install_command(tool),
        )
    location, source = resolve_binary(binary, root)
    if source == "missing":
        return ToolCheck(
            set_name=set_name,
            tool=tool["tool"],
            binary=binary,
            status="missing",
            source=source,
            install_hint=install_command(tool),
        )
    return ToolCheck(
        set_name=set_name,
        tool=tool["tool"],
        binary=binary,
        status="present",
        source=source,
        location=location,
    )


def _health_binary(tool: dict) -> str | None:
    """Registry health_binary wins; otherwise infer for installable CLI-ish tools.

    Some older catalog entries predate the explicit `health_binary` field but
    still represent ordinary binaries (`gitleaks`, `nah`, `rtk`, etc.). Doctor
    should verify those instead of silently skipping them.
    """
    explicit = tool.get("health_binary")
    if explicit:
        return str(explicit)
    if install_command(tool) and tool.get("kind") not in {"skill", "instructions"}:
        return str(tool["tool"])
    return None


def _load_ledger(root: Path) -> dict:
    path = ledger_path(root)
    if not path.exists():
        return {"sets": {}}
    try:
        return json.loads(path.read_text(encoding="utf-8-sig") or "{}")
    except json.JSONDecodeError:
        return {"sets": {}}


def _check_host(host: str, root: Path) -> HostCheck:
    mcp_file = host_mcp_file(host, root)
    ledger = _load_ledger(root)
    linked_sets: list[str] = []
    restart_reasons: list[str] = []
    for key, record in ledger.get("sets", {}).items():
        if not isinstance(record, dict) or record.get("host") != host:
            continue
        linked_sets.append(str(key).split(":", 1)[-1])
        if record.get("mcp_wiring"):
            restart_reasons.append("MCP config changed; restart/reload this host session")
        if record.get("path_wiring"):
            restart_reasons.append("PATH/env changed; restart this host session or shell")
    deduped_reasons = tuple(dict.fromkeys(restart_reasons))
    return HostCheck(
        host=host,
        config_path=str(mcp_file) if mcp_file is not None else None,
        config_present=bool(mcp_file and mcp_file.exists()),
        linked_sets=tuple(sorted(linked_sets)),
        restart_required=bool(deduped_reasons),
        restart_reasons=deduped_reasons,
    )


def _next_actions(
    missing: list[ToolCheck],
    hosts: tuple[HostCheck, ...],
) -> list[str]:
    actions: list[str] = []
    for tool in missing:
        if tool.install_hint:
            actions.append(f"install {tool.tool}: {tool.install_hint}")
        else:
            actions.append(f"install {tool.tool}: no install recipe in registry")
    for host in hosts:
        if host.restart_required:
            actions.append(f"restart/reload {host.host}")
    return actions


def _render_hook_events(hooks: tuple[str, ...]) -> str:
    events = set()
    for cmd in hooks:
        if "session-start" in cmd or "curate --surface" in cmd:
            events.add("SessionStart")
        if "user-prompt" in cmd or cmd == "paw memory hook":
            events.add("UserPromptSubmit")
        if "stop" in cmd or "reflect" in cmd:
            events.add("Stop")
    return ", ".join(sorted(events)) if events else "none"


def render_report(report: DoctorReport, *, command: str = "doctor") -> str:
    lines = [f"paw {command}: {report.status}"]
    lines.append("default core:")
    for set_check in report.sets:
        lines.append(f"  - {set_check.name}: {set_check.health}")
        for tool in set_check.tools:
            if tool.status == "present":
                detail = f"{tool.source}"
                if tool.location:
                    detail += f" ({tool.location})"
                lines.append(f"      ok: {tool.tool} [{detail}]")
            elif tool.status == "missing":
                lines.append(f"      missing: {tool.tool}")
                if tool.install_hint:
                    lines.append(f"        install: {tool.install_hint}")
            else:
                lines.append(f"      skipped: {tool.tool} (no health binary)")

    if report.icm:
        lines.append(f"icm: {report.icm.summary} ({report.icm.status})")
        for name, count in report.icm.topics:
            flag = " ← pending" if name == "pending" else ""
            lines.append(f"  - {name}: {count}{flag}")
    else:
        lines.append("icm: not detected")

    if report.hooks:
        lines.append("hooks:")
        for hook in report.hooks:
            if hook.config_present and hook.memory_hooks:
                events = _render_hook_events(hook.memory_hooks)
                lines.append(f"  - {hook.host}: paw hooks on {events}")
            elif hook.config_present:
                lines.append(f"  - {hook.host}: config found, no paw memory hooks")
            else:
                lines.append(f"  - {hook.host}: no hook config")

    if report.mesh:
        lines.append(f"mesh: {report.mesh.summary} ({report.mesh.status})")
        if report.mesh.stale_count:
            stale = [m for m in report.mesh.members if not m.active]
            for member in stale:
                lines.append(
                    f"  stale: {member.member} host={member.host} "
                    f"role={member.role}"
                )
    else:
        lines.append("mesh: no state (no mesh activity yet)")

    lines.append("hosts:")
    for host in report.hosts:
        state = "restart" if host.restart_required else "ok"
        lines.append(f"  - {host.host}: {state}")
        if host.config_path:
            present = "present" if host.config_present else "absent"
            lines.append(f"      config: {host.config_path} ({present})")
        if host.linked_sets:
            lines.append(f"      linked: {', '.join(host.linked_sets)}")
        for reason in host.restart_reasons:
            lines.append(f"      restart: {reason}")
    if report.next_actions:
        lines.append("next:")
        for action in report.next_actions:
            lines.append(f"  - {action}")
    return "\n".join(lines)
