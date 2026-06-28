"""Hook-safe adapter for the local parallel memory mesh.

This is the thin reliability layer that keeps agents from forgetting to poll the
mesh.  It is deliberately host-agnostic: hook systems pass JSON on stdin, this
module derives project/member/run identity, updates heartbeat/registration, and
returns a tiny additional-context block only when there is something new.

It also nudges the agent toward curation hygiene: when the ICM ``pending`` topic
grows past ``PENDING_WARN`` the hook appends a one-line reminder, and past
``PENDING_CRITICAL`` it runs a dry-run preview of curation so the agent can see
what would be promoted without waiting for the queue to overflow. The bulk write
itself is never done here — that stays an explicit ``paw curate`` call.
"""

from __future__ import annotations

import hashlib
import json
import os
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Literal

from .curate import PENDING_CRITICAL, PENDING_WARN, pending_count, pending_preview
from .memory_mesh import MemoryMesh, MeshEvent, MeshLock, MeshScope

HookEvent = Literal["session-start", "user-prompt", "stop"]

MAX_EVENTS_IN_CONTEXT = 6
MAX_LOCKS_IN_CONTEXT = 4
HOOK_EVENTS = ("SessionStart", "UserPromptSubmit", "Stop")

# Refresh the pending count at most this often per member so a chatty session
# does not spawn an ICM subprocess on every UserPromptSubmit. Cached in the
# per-member hook state file alongside the mesh cursor.
PENDING_COUNT_TTL_SECONDS = 300


@dataclass(frozen=True)
class MemoryHookConfig:
    host: str
    event: HookEvent
    project: str
    run_id: str
    member: str
    role: str
    session_id: str
    state_dir: Path | None = None
    hook_state_dir: Path | None = None


@dataclass(frozen=True)
class MemoryHookResult:
    status: str
    summary: str
    additional_context: str = ""
    cursor: int = 0

    def to_dict(self) -> dict[str, object]:
        return {
            "status": self.status,
            "summary": self.summary,
            "additional_context": self.additional_context,
            "cursor": self.cursor,
        }


@dataclass(frozen=True)
class HookInstallResult:
    status: str
    summary: str
    path: str
    added: tuple[str, ...] = ()
    existing: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, object]:
        return {
            "status": self.status,
            "summary": self.summary,
            "path": self.path,
            "added": list(self.added),
            "existing": list(self.existing),
        }


def load_hook_payload(raw: str) -> dict[str, object]:
    try:
        payload = json.loads(raw) if raw.strip() else {}
    except ValueError:
        return {}
    return payload if isinstance(payload, dict) else {}


def build_config(
    payload: dict[str, object],
    *,
    host: str,
    event: HookEvent,
    project: str | None = None,
    run_id: str | None = None,
    member: str | None = None,
    role: str | None = None,
    state_dir: Path | None = None,
    hook_state_dir: Path | None = None,
) -> MemoryHookConfig:
    cwd = _payload_str(payload, "cwd") or os.getcwd()
    session_id = _payload_str(payload, "session_id") or _payload_str(payload, "sessionId")
    session_id = session_id or _stable_hash(cwd)[:12]
    resolved_project = (
        project
        or os.environ.get("PAW_MEMORY_PROJECT")
        or _payload_str(payload, "project")
        or Path(cwd).resolve().name
        or "default"
    )
    resolved_run_id = (
        run_id
        or os.environ.get("PAW_MEMORY_RUN_ID")
        or _payload_str(payload, "run_id")
        or _payload_str(payload, "runId")
        or "live"
    )
    resolved_member = (
        member
        or os.environ.get("PAW_MEMORY_MEMBER")
        or f"{host}-{_stable_hash(session_id)[:8]}"
    )
    resolved_role = role or os.environ.get("PAW_MEMORY_ROLE") or host
    return MemoryHookConfig(
        host=host,
        event=event,
        project=resolved_project,
        run_id=resolved_run_id,
        member=resolved_member,
        role=resolved_role,
        session_id=session_id,
        state_dir=state_dir,
        hook_state_dir=hook_state_dir,
    )


def run_memory_hook(
    config: MemoryHookConfig,
    *,
    count_runner: Callable[[], int] | None = None,
    preview_runner: Callable[[], str] | None = None,
    now: Callable[[], float] | None = None,
) -> MemoryHookResult:
    mesh = MemoryMesh(root=config.state_dir)
    scope = MeshScope(project=config.project, run_id=config.run_id)
    hook_state = _load_state(config)
    registered = bool(hook_state.get("registered"))

    if config.event == "session-start" or not registered:
        mesh.register(
            scope,
            member=config.member,
            host=config.host,
            role=config.role,
            session_id=config.session_id,
        )
        hook_state["registered"] = True
    else:
        mesh.heartbeat(scope, member=config.member)

    since = int(hook_state.get("cursor", 0) or 0)
    hygiene = _hygiene_context(
        config,
        hook_state,
        count_runner=count_runner,
        preview_runner=preview_runner,
        now=now,
    )
    _save_state(config, hook_state)

    if config.event in ("session-start", "user-prompt"):
        poll = mesh.poll(scope, member=config.member, since=since)
        hook_state["cursor"] = poll.cursor
        _save_state(config, hook_state)
        context = _render_context(
            events=_interesting_events(poll.events, config.member),
            locks=_interesting_locks(poll.locks, config.member),
            cursor=poll.cursor,
        )
        context = "\n".join(part for part in (context, hygiene) if part)
        return MemoryHookResult(
            status="success",
            summary=f"memory hook {config.event} cursor {poll.cursor}",
            additional_context=context,
            cursor=poll.cursor,
        )

    hook_state["cursor"] = since
    _save_state(config, hook_state)
    # Stop: nothing new from the mesh to surface, but a pending-overflow nudge
    # is still useful on session end so the agent logs the curation todo.
    return MemoryHookResult(
        status="success",
        summary=f"memory hook {config.event} heartbeat recorded",
        additional_context=hygiene,
        cursor=since,
    )


def _hygiene_context(
    config: MemoryHookConfig,
    hook_state: dict[str, object],
    *,
    count_runner: Callable[[], int] | None,
    preview_runner: Callable[[], str] | None,
    now: Callable[[], float] | None,
) -> str:
    """Build the pending-hygiene context block, with a per-member count cache.

    Returns "" when pending is small or ICM is unavailable, so the hook adds
    nothing to the agent's prompt on a clean queue.
    """
    clock = now or time.time
    count, stamp = _pending_count_cached(config, hook_state, count_runner, clock)
    if count < PENDING_WARN:
        return ""
    if count >= PENDING_CRITICAL:
        # Dry-run preview only — never writes from the hook hot path.
        preview = _safe_preview(preview_runner)
        if preview:
            return preview
        # Preview unavailable (ICM down / curate error): still warn the count.
        return _nudge_line(count, critical=True)
    return _nudge_line(count, critical=False)


def _pending_count_cached(
    config: MemoryHookConfig,
    hook_state: dict[str, object],
    count_runner: Callable[[], int] | None,
    clock: Callable[[], float],
) -> tuple[int, float]:
    """Return (count, new_stamp). Reuses a cached count within the TTL window."""
    stamp = float(hook_state.get("pending_stamp", 0) or 0)
    cached = hook_state.get("pending_count")
    if cached is not None and (clock() - stamp) < PENDING_COUNT_TTL_SECONDS:
        try:
            return int(cached), stamp
        except (TypeError, ValueError):
            pass
    runner = count_runner or pending_count
    try:
        count = int(runner())
    except Exception:
        count = 0
    new_stamp = clock()
    hook_state["pending_count"] = count
    hook_state["pending_stamp"] = new_stamp
    return count, new_stamp


def _safe_preview(preview_runner: Callable[[], str] | None) -> str:
    runner = preview_runner or pending_preview
    try:
        return runner() or ""
    except Exception:
        return ""


def _nudge_line(count: int, *, critical: bool) -> str:
    flag = "🧠" if critical else "🧹"
    verb = "overflow — " if critical else ""
    return (f"{flag} paw memory: {verb}{count} pending in ICM. "
            "Run `paw curate --dry-run` to review, `paw curate` to promote.")


def hook_stdout(result: MemoryHookResult, *, hook_event_name: str) -> str:
    if not result.additional_context:
        return ""
    return json.dumps(
        {
            "hookSpecificOutput": {
                "hookEventName": hook_event_name,
                "additionalContext": result.additional_context,
            }
        },
        ensure_ascii=False,
    )


def install_memory_hooks(
    *,
    host: str,
    config_path: Path | None = None,
) -> HookInstallResult:
    """Add the memory hook shim to a Claude/Codex JSON hook config.

    The merge is add-only and idempotent.  Existing hooks keep their order; paw's
    memory shim is appended after existing hooks so it cannot preempt security or
    context-mode guards.
    """

    path = config_path or _default_hook_config(host)
    try:
        data = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
    except (OSError, ValueError) as error:
        return HookInstallResult(
            status="error",
            summary=f"Could not read hook config: {error}",
            path=str(path),
        )
    if not isinstance(data, dict):
        return HookInstallResult(
            status="error",
            summary="Hook config root must be a JSON object.",
            path=str(path),
        )

    hooks = data.setdefault("hooks", {})
    if not isinstance(hooks, dict):
        return HookInstallResult(
            status="error",
            summary="Hook config `hooks` must be an object.",
            path=str(path),
        )

    added: list[str] = []
    existing: list[str] = []
    for event, shim_event in (
        ("SessionStart", "session-start"),
        ("UserPromptSubmit", "user-prompt"),
        ("Stop", "stop"),
    ):
        command = f"py -m paw memory hook --host {host} --event {shim_event}"
        entries = hooks.setdefault(event, [])
        if not isinstance(entries, list):
            return HookInstallResult(
                status="error",
                summary=f"Hook event {event} must be a list.",
                path=str(path),
            )
        if _has_command(entries, command):
            existing.append(event)
            continue
        hook_entry: dict[str, object] = {
            "hooks": [{"type": "command", "command": command}],
        }
        if host == "claude-code":
            hook_entry["hooks"] = [
                {"type": "command", "command": command, "shell": "powershell"}
            ]
        entries.append(hook_entry)
        added.append(event)

    if added:
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            if path.exists():
                backup = path.with_suffix(path.suffix + ".paw-memory-hooks.bak")
                backup.write_text(path.read_text(encoding="utf-8"), encoding="utf-8")
            tmp = path.with_suffix(path.suffix + ".tmp")
            tmp.write_text(
                json.dumps(data, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )
            os.replace(tmp, path)
        except OSError as error:
            return HookInstallResult(
                status="error",
                summary=f"Could not write hook config: {error}",
                path=str(path),
            )

    summary = (
        f"Installed memory hooks for {host}: {', '.join(added)}."
        if added
        else f"Memory hooks for {host} already installed."
    )
    return HookInstallResult(
        status="success",
        summary=summary,
        path=str(path),
        added=tuple(added),
        existing=tuple(existing),
    )


def _payload_str(payload: dict[str, object], key: str) -> str:
    value = payload.get(key)
    return value.strip() if isinstance(value, str) else ""


def _default_hook_config(host: str) -> Path:
    home = Path.home()
    if host == "claude-code":
        return home / ".claude" / "settings.json"
    if host == "codex":
        return home / ".codex" / "hooks.json"
    return home / f".{host}" / "hooks.json"


def _has_command(entries: list[object], command: str) -> bool:
    for entry in entries:
        if not isinstance(entry, dict):
            continue
        hooks = entry.get("hooks")
        if not isinstance(hooks, list):
            continue
        for hook in hooks:
            if isinstance(hook, dict) and hook.get("command") == command:
                return True
    return False


def _stable_hash(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8", "ignore")).hexdigest()


def _state_path(config: MemoryHookConfig) -> Path:
    root = config.hook_state_dir or Path.home() / ".paw" / "state" / "memory-hooks"
    safe_project = _safe_name(config.project)
    safe_run = _safe_name(config.run_id)
    safe_member = _safe_name(config.member)
    return root / safe_project / safe_run / f"{safe_member}.json"


def _load_state(config: MemoryHookConfig) -> dict[str, object]:
    path = _state_path(config)
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return data if isinstance(data, dict) else {}


def _save_state(config: MemoryHookConfig, state: dict[str, object]) -> None:
    path = _state_path(config)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")
    os.replace(tmp, path)


def _safe_name(value: str) -> str:
    return "".join(ch if ch.isalnum() or ch in "._-" else "-" for ch in value) or "default"


def _interesting_events(events: tuple[MeshEvent, ...], member: str) -> tuple[MeshEvent, ...]:
    filtered = [
        event
        for event in events
        if not (event.member == member and event.kind in {"presence", "heartbeat"})
    ]
    return tuple(filtered[-MAX_EVENTS_IN_CONTEXT:])


def _interesting_locks(locks: tuple[MeshLock, ...], member: str) -> tuple[MeshLock, ...]:
    return tuple(lock for lock in locks if lock.owner != member)[:MAX_LOCKS_IN_CONTEXT]


def _render_context(
    *,
    events: tuple[MeshEvent, ...],
    locks: tuple[MeshLock, ...],
    cursor: int,
) -> str:
    if not events and not locks:
        return ""
    lines = ["🐾 paw memory mesh:"]
    for event in events:
        content = event.content.replace("\n", " ").strip()
        if len(content) > 220:
            content = content[:217] + "..."
        lines.append(f"• #{event.seq} [{event.lane}·{event.kind}] {event.member}: {content}")
        if event.artifact:
            lines.append(f"  artifact: {event.artifact}")
    for lock in locks:
        purpose = f" — {lock.purpose}" if lock.purpose else ""
        lines.append(f"• lock {lock.name} held by {lock.owner}{purpose}")
    lines.append(f"cursor: {cursor}")
    return "\n".join(lines)
