"""Parallel-session memory coordination over a local, explicit state plane.

The ICM blackboard remains the durable handoff store.  This module adds the
missing live coordination layer: who is present, which entries are new since a
cursor, per-member/private lanes, and short-lived locks for shared write intent.
It is intentionally file-backed and stdlib-only so every local agent host can
participate through the same CLI without adding MCP tax.
"""

from __future__ import annotations

import json
import os
import re
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Callable, Literal

SCHEMA = "paw-memory-mesh/v1"
MAX_CONTENT_CHARS = 4_000
MAX_EVENTS = 500
DEFAULT_TTL_SECONDS = 300

Status = Literal["success", "blocked", "error"]
Lane = Literal["shared", "private"]

_SEGMENT_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")
_SECRET_PATTERNS = (
    re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"),
    re.compile(r"\b[A-Z][A-Z0-9_]*(?:KEY|TOKEN|SECRET|PASSWORD)\s*=\s*\S+"),
    re.compile(r"\bBearer\s+[A-Za-z0-9._~+/=-]{16,}", re.IGNORECASE),
    re.compile(r"\b(?:sk|ghp|github_pat)_[A-Za-z0-9_-]{16,}", re.IGNORECASE),
)


class MemoryMeshError(RuntimeError):
    """Raised when the local coordination state cannot be read or updated."""


@dataclass(frozen=True)
class MemberState:
    member: str
    host: str
    role: str
    session_id: str | None
    capabilities: tuple[str, ...] = ()
    first_seen: float = 0.0
    last_seen: float = 0.0
    ttl_seconds: int = DEFAULT_TTL_SECONDS
    active: bool = True


@dataclass(frozen=True)
class MeshEvent:
    seq: int
    ts: float
    member: str
    lane: str
    kind: str
    content: str
    artifact: str | None = None
    promoted_from: int | None = None


@dataclass(frozen=True)
class MeshLock:
    name: str
    owner: str
    purpose: str
    acquired_at: float
    expires_at: float


@dataclass(frozen=True)
class MeshResult:
    status: Status
    summary: str
    members: tuple[MemberState, ...] = ()
    events: tuple[MeshEvent, ...] = ()
    locks: tuple[MeshLock, ...] = ()
    cursor: int = 0
    next_actions: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


@dataclass(frozen=True)
class MeshScope:
    project: str
    run_id: str

    @property
    def directory_parts(self) -> tuple[str, str]:
        return (_validate_segment(self.project, "project"), _normalize_run_id(self.run_id))


class MemoryMesh:
    """Coordinate multiple local agent sessions sharing one project/run."""

    def __init__(
        self,
        *,
        root: Path | None = None,
        now: Callable[[], float] | None = None,
        lock_timeout_seconds: float = 5.0,
    ) -> None:
        self.root = root or Path.home() / ".paw" / "state" / "memory-mesh"
        self.now = now or time.time
        self.lock_timeout_seconds = lock_timeout_seconds

    def register(
        self,
        scope: MeshScope,
        *,
        member: str,
        host: str,
        role: str | None = None,
        session_id: str | None = None,
        capabilities: tuple[str, ...] = (),
        ttl_seconds: int = DEFAULT_TTL_SECONDS,
    ) -> MeshResult:
        try:
            member = _validate_segment(member, "member")
            host = _validate_segment(host, "host")
            role = _validate_segment(role or member, "role")
            _validate_ttl(ttl_seconds)
            capabilities = tuple(_validate_segment(c, "capability") for c in capabilities)
        except ValueError as error:
            return _error(str(error))

        def mutate(state: dict[str, object]) -> MeshResult:
            now = self.now()
            members = _members(state)
            prior = members.get(member)
            first_seen = float(prior.get("first_seen", now)) if prior else now
            members[member] = {
                "member": member,
                "host": host,
                "role": role,
                "session_id": session_id,
                "capabilities": list(capabilities),
                "first_seen": first_seen,
                "last_seen": now,
                "ttl_seconds": ttl_seconds,
            }
            action = "heartbeat" if prior else "registered"
            event = _append_event(
                state,
                ts=now,
                member=member,
                lane="shared",
                kind="presence",
                content=f"{member} {action} on {host} as {role}.",
            )
            return MeshResult(
                status="success",
                summary=f"{member} {action} for {scope.project}/{scope.run_id}.",
                members=(_member_from_record(members[member], now),),
                events=(event,),
                cursor=event.seq,
            )

        return self._update(scope, mutate)

    def heartbeat(self, scope: MeshScope, *, member: str) -> MeshResult:
        try:
            member = _validate_segment(member, "member")
        except ValueError as error:
            return _error(str(error))

        def mutate(state: dict[str, object]) -> MeshResult:
            now = self.now()
            members = _members(state)
            if member not in members:
                members[member] = {
                    "member": member,
                    "host": "unknown",
                    "role": member,
                    "session_id": None,
                    "capabilities": [],
                    "first_seen": now,
                    "last_seen": now,
                    "ttl_seconds": DEFAULT_TTL_SECONDS,
                }
            else:
                members[member]["last_seen"] = now
            return MeshResult(
                status="success",
                summary=f"{member} heartbeat recorded.",
                members=(_member_from_record(members[member], now),),
                cursor=_cursor(state),
            )

        return self._update(scope, mutate)

    def members(self, scope: MeshScope) -> MeshResult:
        try:
            state = self._read_state(scope)
        except (MemoryMeshError, ValueError) as error:
            return _error(str(error))
        now = self.now()
        records = tuple(_member_from_record(record, now) for record in _members(state).values())
        return MeshResult(
            status="success",
            summary=f"{len(records)} members known for {scope.project}/{scope.run_id}.",
            members=tuple(sorted(records, key=lambda m: (not m.active, m.member))),
            cursor=_cursor(state),
        )

    def post(
        self,
        scope: MeshScope,
        *,
        member: str,
        content: str,
        lane: Lane = "shared",
        kind: str = "note",
        artifact: str | None = None,
    ) -> MeshResult:
        try:
            member = _validate_segment(member, "member")
            lane_name = _lane_name(member, lane)
            kind = _validate_segment(kind, "kind")
            _validate_content(content)
            _validate_artifact(artifact)
        except ValueError as error:
            return _error(str(error))
        if _contains_secret(content):
            return _error(
                "Content looks like a secret and was not written.",
                ("Redact credentials and store only the durable conclusion.",),
            )

        def mutate(state: dict[str, object]) -> MeshResult:
            now = self.now()
            _ensure_member(state, member, now)
            event = _append_event(
                state,
                ts=now,
                member=member,
                lane=lane_name,
                kind=kind,
                content=content.strip(),
                artifact=artifact,
            )
            return MeshResult(
                status="success",
                summary=f"Posted {kind} to {lane_name}.",
                events=(event,),
                cursor=event.seq,
            )

        return self._update(scope, mutate)

    def promote(
        self,
        scope: MeshScope,
        *,
        member: str,
        seq: int,
        kind: str = "note",
    ) -> MeshResult:
        try:
            member = _validate_segment(member, "member")
            kind = _validate_segment(kind, "kind")
            if seq <= 0:
                raise ValueError("seq must be positive.")
        except ValueError as error:
            return _error(str(error))

        def mutate(state: dict[str, object]) -> MeshResult:
            now = self.now()
            source = next((_event_from_record(e) for e in _events(state) if int(e.get("seq", 0)) == seq), None)
            if source is None:
                return _error(f"No event with seq {seq}.")
            if source.lane != _lane_name(member, "private") or source.member != member:
                return _error("Only the owning member can promote its private lane entry.")
            event = _append_event(
                state,
                ts=now,
                member=member,
                lane="shared",
                kind=kind,
                content=source.content,
                artifact=source.artifact,
                promoted_from=source.seq,
            )
            return MeshResult(
                status="success",
                summary=f"Promoted private event {seq} to shared lane.",
                events=(event,),
                cursor=event.seq,
            )

        return self._update(scope, mutate)

    def poll(
        self,
        scope: MeshScope,
        *,
        member: str | None = None,
        since: int = 0,
        include_private: bool = True,
    ) -> MeshResult:
        try:
            if member is not None:
                member = _validate_segment(member, "member")
            if since < 0:
                raise ValueError("since must be zero or positive.")
            state = self._read_state(scope)
        except (MemoryMeshError, ValueError) as error:
            return _error(str(error))

        visible = []
        private_lane = _lane_name(member, "private") if member and include_private else None
        for record in _events(state):
            event = _event_from_record(record)
            if event.seq <= since:
                continue
            if event.lane == "shared" or event.lane == private_lane:
                visible.append(event)
        cursor = max((event.seq for event in visible), default=_cursor(state))
        members = tuple(_member_from_record(record, self.now()) for record in _members(state).values())
        return MeshResult(
            status="success",
            summary=f"{len(visible)} new events since {since}.",
            events=tuple(visible),
            members=tuple(sorted(members, key=lambda m: (not m.active, m.member))),
            locks=tuple(_lock_from_record(record) for record in _locks(state).values()),
            cursor=cursor,
        )

    def acquire_lock(
        self,
        scope: MeshScope,
        *,
        name: str,
        owner: str,
        purpose: str = "",
        ttl_seconds: int = DEFAULT_TTL_SECONDS,
    ) -> MeshResult:
        try:
            name = _validate_segment(name, "lock")
            owner = _validate_segment(owner, "owner")
            _validate_ttl(ttl_seconds)
            if len(purpose) > 500:
                raise ValueError("purpose must be at most 500 characters.")
        except ValueError as error:
            return _error(str(error))

        def mutate(state: dict[str, object]) -> MeshResult:
            now = self.now()
            locks = _locks(state)
            _prune_expired_locks(locks, now)
            existing = locks.get(name)
            if existing and existing.get("owner") != owner:
                lock = _lock_from_record(existing)
                return MeshResult(
                    status="blocked",
                    summary=f"Lock {name} is held by {lock.owner} until {lock.expires_at:.0f}.",
                    locks=(lock,),
                    next_actions=("Poll or retry after the lock expires.",),
                    cursor=_cursor(state),
                )
            lock_record = {
                "name": name,
                "owner": owner,
                "purpose": purpose,
                "acquired_at": now,
                "expires_at": now + ttl_seconds,
            }
            locks[name] = lock_record
            event = _append_event(
                state,
                ts=now,
                member=owner,
                lane="shared",
                kind="lock",
                content=f"{owner} acquired lock {name}. {purpose}".strip(),
            )
            return MeshResult(
                status="success",
                summary=f"Lock {name} acquired by {owner}.",
                events=(event,),
                locks=(_lock_from_record(lock_record),),
                cursor=event.seq,
            )

        return self._update(scope, mutate)

    def release_lock(
        self,
        scope: MeshScope,
        *,
        name: str,
        owner: str,
        force: bool = False,
    ) -> MeshResult:
        try:
            name = _validate_segment(name, "lock")
            owner = _validate_segment(owner, "owner")
        except ValueError as error:
            return _error(str(error))

        def mutate(state: dict[str, object]) -> MeshResult:
            now = self.now()
            locks = _locks(state)
            existing = locks.get(name)
            if existing is None:
                return MeshResult(
                    status="success",
                    summary=f"Lock {name} was already absent.",
                    cursor=_cursor(state),
                )
            if existing.get("owner") != owner and not force:
                return MeshResult(
                    status="blocked",
                    summary=f"Lock {name} is held by {existing.get('owner')}, not {owner}.",
                    locks=(_lock_from_record(existing),),
                    next_actions=("Use --force only after verifying the owner is dead.",),
                    cursor=_cursor(state),
                )
            del locks[name]
            event = _append_event(
                state,
                ts=now,
                member=owner,
                lane="shared",
                kind="lock",
                content=f"{owner} released lock {name}.",
            )
            return MeshResult(
                status="success",
                summary=f"Lock {name} released.",
                events=(event,),
                cursor=event.seq,
            )

        return self._update(scope, mutate)

    def _state_path(self, scope: MeshScope) -> Path:
        project, run_id = scope.directory_parts
        return self.root / project / f"{run_id}.json"

    def _read_state(self, scope: MeshScope) -> dict[str, object]:
        path = self._state_path(scope)
        if not path.exists():
            return _new_state(scope)
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as error:
            raise MemoryMeshError(f"Could not read memory mesh state: {error}") from error
        if not isinstance(data, dict) or data.get("schema") != SCHEMA:
            raise MemoryMeshError("Memory mesh state has an unknown schema.")
        return data

    def _update(
        self,
        scope: MeshScope,
        mutate: Callable[[dict[str, object]], MeshResult],
    ) -> MeshResult:
        try:
            path = self._state_path(scope)
            path.parent.mkdir(parents=True, exist_ok=True)
            with _FileLock(path.with_suffix(path.suffix + ".lock"), self.lock_timeout_seconds, self.now):
                state = self._read_state(scope)
                result = mutate(state)
                if result.status != "error":
                    _trim_events(state)
                    tmp = path.with_suffix(path.suffix + ".tmp")
                    tmp.write_text(
                        json.dumps(state, ensure_ascii=False, indent=2, sort_keys=True),
                        encoding="utf-8",
                    )
                    os.replace(tmp, path)
                return result
        except (OSError, MemoryMeshError, ValueError) as error:
            return _error(str(error))


class _FileLock:
    def __init__(self, path: Path, timeout_seconds: float, now: Callable[[], float]) -> None:
        self.path = path
        self.timeout_seconds = timeout_seconds
        self.now = now
        self.fd: int | None = None

    def __enter__(self) -> "_FileLock":
        deadline = self.now() + self.timeout_seconds
        while True:
            try:
                self.fd = os.open(str(self.path), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
                os.write(self.fd, str(os.getpid()).encode("ascii"))
                return self
            except FileExistsError:
                if self._stale():
                    try:
                        self.path.unlink()
                    except FileNotFoundError:
                        pass
                    continue
                if self.now() >= deadline:
                    raise MemoryMeshError(f"Timed out waiting for state lock {self.path}.")
                time.sleep(0.05)

    def __exit__(self, exc_type, exc, tb) -> None:  # type: ignore[no-untyped-def]
        if self.fd is not None:
            os.close(self.fd)
        try:
            self.path.unlink()
        except FileNotFoundError:
            pass

    def _stale(self) -> bool:
        try:
            return self.now() - self.path.stat().st_mtime > max(self.timeout_seconds * 2, 30)
        except FileNotFoundError:
            return False


def _new_state(scope: MeshScope) -> dict[str, object]:
    project, run_id = scope.directory_parts
    return {
        "schema": SCHEMA,
        "project": project,
        "run_id": run_id,
        "next_seq": 1,
        "members": {},
        "events": [],
        "locks": {},
    }


def _members(state: dict[str, object]) -> dict[str, dict[str, object]]:
    value = state.setdefault("members", {})
    if not isinstance(value, dict):
        raise MemoryMeshError("members must be an object.")
    return value  # type: ignore[return-value]


def _events(state: dict[str, object]) -> list[dict[str, object]]:
    value = state.setdefault("events", [])
    if not isinstance(value, list):
        raise MemoryMeshError("events must be a list.")
    return value  # type: ignore[return-value]


def _locks(state: dict[str, object]) -> dict[str, dict[str, object]]:
    value = state.setdefault("locks", {})
    if not isinstance(value, dict):
        raise MemoryMeshError("locks must be an object.")
    return value  # type: ignore[return-value]


def _cursor(state: dict[str, object]) -> int:
    return int(state.get("next_seq", 1)) - 1


def _append_event(
    state: dict[str, object],
    *,
    ts: float,
    member: str,
    lane: str,
    kind: str,
    content: str,
    artifact: str | None = None,
    promoted_from: int | None = None,
) -> MeshEvent:
    seq = int(state.get("next_seq", 1))
    state["next_seq"] = seq + 1
    record: dict[str, object] = {
        "seq": seq,
        "ts": ts,
        "member": member,
        "lane": lane,
        "kind": kind,
        "content": content,
        "artifact": artifact,
        "promoted_from": promoted_from,
    }
    _events(state).append(record)
    return _event_from_record(record)


def _ensure_member(state: dict[str, object], member: str, now: float) -> None:
    members = _members(state)
    members.setdefault(
        member,
        {
            "member": member,
            "host": "unknown",
            "role": member,
            "session_id": None,
            "capabilities": [],
            "first_seen": now,
            "last_seen": now,
            "ttl_seconds": DEFAULT_TTL_SECONDS,
        },
    )
    members[member]["last_seen"] = now


def _trim_events(state: dict[str, object]) -> None:
    events = _events(state)
    if len(events) > MAX_EVENTS:
        del events[: len(events) - MAX_EVENTS]


def _member_from_record(record: dict[str, object], now: float) -> MemberState:
    ttl = int(record.get("ttl_seconds", DEFAULT_TTL_SECONDS))
    last_seen = float(record.get("last_seen", 0.0))
    return MemberState(
        member=str(record.get("member", "")),
        host=str(record.get("host", "unknown")),
        role=str(record.get("role", record.get("member", ""))),
        session_id=(
            str(record["session_id"]) if record.get("session_id") is not None else None
        ),
        capabilities=tuple(str(c) for c in record.get("capabilities", []) if c),
        first_seen=float(record.get("first_seen", last_seen)),
        last_seen=last_seen,
        ttl_seconds=ttl,
        active=(now - last_seen) <= ttl,
    )


def _event_from_record(record: dict[str, object]) -> MeshEvent:
    return MeshEvent(
        seq=int(record.get("seq", 0)),
        ts=float(record.get("ts", 0.0)),
        member=str(record.get("member", "")),
        lane=str(record.get("lane", "shared")),
        kind=str(record.get("kind", "note")),
        content=str(record.get("content", "")),
        artifact=str(record["artifact"]) if record.get("artifact") is not None else None,
        promoted_from=(
            int(record["promoted_from"])
            if record.get("promoted_from") is not None
            else None
        ),
    )


def _lock_from_record(record: dict[str, object]) -> MeshLock:
    return MeshLock(
        name=str(record.get("name", "")),
        owner=str(record.get("owner", "")),
        purpose=str(record.get("purpose", "")),
        acquired_at=float(record.get("acquired_at", 0.0)),
        expires_at=float(record.get("expires_at", 0.0)),
    )


def _prune_expired_locks(locks: dict[str, dict[str, object]], now: float) -> None:
    for name, record in list(locks.items()):
        if float(record.get("expires_at", 0.0)) <= now:
            del locks[name]


def _lane_name(member: str | None, lane: Lane) -> str:
    if lane == "shared":
        return "shared"
    if member is None:
        raise ValueError("member is required for private lane.")
    return f"member:{member}"


def _validate_segment(value: str, label: str) -> str:
    clean = value.strip()
    if not _SEGMENT_RE.fullmatch(clean):
        raise ValueError(
            f"{label} must use only letters, numbers, dot, underscore, or hyphen."
        )
    return clean


def _normalize_run_id(value: str) -> str:
    normalized = re.sub(r"\s+", "-", value.strip())
    return _validate_segment(normalized, "run_id")


def _validate_ttl(ttl_seconds: int) -> None:
    if not 10 <= ttl_seconds <= 86_400:
        raise ValueError("ttl_seconds must be between 10 and 86400.")


def _validate_content(content: str) -> None:
    clean = content.strip()
    if not clean:
        raise ValueError("content must not be empty.")
    if len(clean) > MAX_CONTENT_CHARS:
        raise ValueError(f"content must be at most {MAX_CONTENT_CHARS} characters.")


def _validate_artifact(artifact: str | None) -> None:
    if artifact is None:
        return
    if "\n" in artifact or "\r" in artifact:
        raise ValueError("artifact must be a single path or identifier.")
    if len(artifact) > 500:
        raise ValueError("artifact must be at most 500 characters.")


def _contains_secret(content: str) -> bool:
    return any(pattern.search(content) for pattern in _SECRET_PATTERNS)


def _error(summary: str, next_actions: tuple[str, ...] | str | None = None) -> MeshResult:
    if isinstance(next_actions, str):
        actions = (next_actions,)
    else:
        actions = next_actions or ()
    return MeshResult(status="error", summary=summary, next_actions=actions)
