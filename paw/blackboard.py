"""Thin, portable shared-blackboard protocol backed by the ICM CLI."""

from __future__ import annotations

import json
import os
import platform
import re
import subprocess
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Callable, Literal

EntryKind = Literal[
    "plan",
    "handoff",
    "observation",
    "review",
    "decision",
    "result",
    "blocker",
]
Importance = Literal["critical", "high", "medium", "low"]
Status = Literal["success", "warning", "error"]

SCHEMA = "paw-blackboard/v1"
ENTRY_KINDS = frozenset(
    {"plan", "handoff", "observation", "review", "decision", "result", "blocker"}
)
MAX_CONTENT_CHARS = 4_000
MAX_LIMIT = 50

_SEGMENT_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")
_SECRET_PATTERNS = (
    re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"),
    re.compile(r"\b[A-Z][A-Z0-9_]*(?:KEY|TOKEN|SECRET|PASSWORD)\s*=\s*\S+"),
    re.compile(r"\bBearer\s+[A-Za-z0-9._~+/=-]{16,}", re.IGNORECASE),
    re.compile(r"\b(?:sk|ghp|github_pat)_[A-Za-z0-9_-]{16,}", re.IGNORECASE),
)

Runner = Callable[[list[str]], str]


@dataclass(frozen=True)
class BlackboardScope:
    project: str
    run_id: str

    @property
    def topic(self) -> str:
        project = _validate_segment(self.project, "project")
        run_id = _normalize_run_id(self.run_id)
        return f"{project}/blackboard/{run_id}"


@dataclass(frozen=True)
class BlackboardEntry:
    role: str
    kind: EntryKind
    content: str
    artifact: str | None = None
    importance: Importance = "medium"


@dataclass(frozen=True)
class BlackboardResult:
    status: Status
    summary: str
    entries: tuple[BlackboardEntry, ...] = ()
    next_actions: tuple[str, ...] = ()
    artifacts: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


class IcmBlackboard:
    """Store and retrieve explicit team handoffs through an ICM topic."""

    def __init__(
        self,
        *,
        executable: str | None = None,
        database: Path | None = None,
        runner: Runner | None = None,
    ) -> None:
        self.executable = executable or _default_executable()
        self.database = database
        self.runner = runner or _run_command

    def write(
        self,
        scope: BlackboardScope,
        entry: BlackboardEntry,
    ) -> BlackboardResult:
        try:
            topic = scope.topic
            _validate_entry(entry)
        except ValueError as error:
            return _error(str(error))

        if _contains_secret(entry.content):
            return _error(
                "Content looks like a secret and was not written.",
                "Redact credentials and store only the durable conclusion.",
            )

        payload = json.dumps(
            {
                "schema": SCHEMA,
                "project": scope.project,
                "run_id": _normalize_run_id(scope.run_id),
                "role": entry.role,
                "kind": entry.kind,
                "content": entry.content,
                "artifact": entry.artifact,
            },
            ensure_ascii=False,
            separators=(",", ":"),
        )
        keywords = ",".join(
            (
                "blackboard",
                f"run:{_normalize_run_id(scope.run_id)}",
                f"role:{entry.role}",
                f"kind:{entry.kind}",
            )
        )
        command = self._base_command("store")
        command.extend(
            (
                "--topic",
                topic,
                "--content",
                payload,
                "--importance",
                entry.importance,
                "--keywords",
                keywords,
                "--no-embeddings",
            )
        )

        try:
            self.runner(command)
        except RuntimeError as error:
            return _error(
                f"ICM write failed: {error}",
                "Check `icm health`, the database path, and retry once.",
            )

        artifacts = (entry.artifact,) if entry.artifact else ()
        return BlackboardResult(
            status="success",
            summary=f"Shared {entry.kind} from {entry.role} in {topic}.",
            next_actions=("Let the next role recall this run before acting.",),
            artifacts=artifacts,
        )

    def read(
        self,
        scope: BlackboardScope,
        *,
        query: str = "blackboard",
        role: str | None = None,
        kind: EntryKind | None = None,
        limit: int = 10,
    ) -> BlackboardResult:
        try:
            topic = scope.topic
            _validate_read_filters(query, role, kind, limit)
        except ValueError as error:
            return _error(str(error))

        command = self._base_command("recall")
        command.extend(
            (
                query.strip() or "blackboard",
                "--topic",
                topic,
                "--limit",
                str(limit),
                "--format",
                "json",
                "--no-embeddings",
                "--read-only",
            )
        )
        try:
            output = self.runner(command)
            memories = _load_memories(output)
        except (RuntimeError, ValueError) as error:
            return _error(
                f"ICM read failed: {error}",
                "Check `icm health` and retry with a keyword-rich query.",
            )

        entries = tuple(
            entry
            for entry in (_parse_entry(memory, scope) for memory in memories)
            if entry is not None
            and (role is None or entry.role == role)
            and (kind is None or entry.kind == kind)
        )
        artifacts = tuple(
            entry.artifact for entry in entries if entry.artifact is not None
        )
        return BlackboardResult(
            status="success",
            summary=f"Recalled {len(entries)} blackboard entries from {topic}.",
            entries=entries,
            next_actions=(
                "Use the newest relevant entry; query again with exact task vocabulary on miss.",
            ),
            artifacts=artifacts,
        )

    def _base_command(self, subcommand: str) -> list[str]:
        command = [self.executable, subcommand]
        if self.database is not None:
            command.extend(("--db", str(self.database)))
        return command


def _default_executable() -> str:
    return "icm.exe" if platform.system() == "Windows" else "icm"


def _run_command(command: list[str]) -> str:
    env = os.environ.copy()
    result = subprocess.run(
        command,
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        env=env,
    )
    if result.returncode != 0:
        message = result.stderr.strip() or result.stdout.strip() or "unknown ICM error"
        raise RuntimeError(message)
    return result.stdout


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


def _validate_entry(entry: BlackboardEntry) -> None:
    _validate_segment(entry.role, "role")
    if entry.kind not in ENTRY_KINDS:
        raise ValueError(f"kind must be one of: {', '.join(sorted(ENTRY_KINDS))}.")
    content = entry.content.strip()
    if not content:
        raise ValueError("content must not be empty.")
    if len(content) > MAX_CONTENT_CHARS:
        raise ValueError(f"content must be at most {MAX_CONTENT_CHARS} characters.")
    if entry.artifact is not None:
        if "\n" in entry.artifact or "\r" in entry.artifact:
            raise ValueError("artifact must be a single path or identifier.")
        if len(entry.artifact) > 500:
            raise ValueError("artifact must be at most 500 characters.")


def _validate_read_filters(
    query: str,
    role: str | None,
    kind: str | None,
    limit: int,
) -> None:
    if len(query) > 500:
        raise ValueError("query must be at most 500 characters.")
    if role is not None:
        _validate_segment(role, "role")
    if kind is not None and kind not in ENTRY_KINDS:
        raise ValueError(f"kind must be one of: {', '.join(sorted(ENTRY_KINDS))}.")
    if not 1 <= limit <= MAX_LIMIT:
        raise ValueError(f"limit must be between 1 and {MAX_LIMIT}.")


def _contains_secret(content: str) -> bool:
    return any(pattern.search(content) for pattern in _SECRET_PATTERNS)


def _load_memories(output: str) -> list[dict[str, object]]:
    try:
        payload = json.loads(output or "[]")
    except json.JSONDecodeError as error:
        raise ValueError("ICM returned invalid JSON.") from error
    if isinstance(payload, dict):
        payload = payload.get("memories", [])
    if not isinstance(payload, list):
        raise ValueError("ICM JSON must contain a memory list.")
    return [item for item in payload if isinstance(item, dict)]


def _parse_entry(
    memory: dict[str, object],
    scope: BlackboardScope,
) -> BlackboardEntry | None:
    raw = memory.get("content")
    if not isinstance(raw, str):
        return None
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError:
        return None
    if not isinstance(payload, dict) or payload.get("schema") != SCHEMA:
        return None
    if payload.get("project") != scope.project:
        return None
    if payload.get("run_id") != _normalize_run_id(scope.run_id):
        return None
    try:
        entry = BlackboardEntry(
            role=str(payload["role"]),
            kind=str(payload["kind"]),  # type: ignore[arg-type]
            content=str(payload["content"]),
            artifact=(
                str(payload["artifact"])
                if payload.get("artifact") is not None
                else None
            ),
        )
        _validate_entry(entry)
    except (KeyError, ValueError):
        return None
    return entry


def _error(summary: str, next_action: str | None = None) -> BlackboardResult:
    return BlackboardResult(
        status="error",
        summary=summary,
        next_actions=(next_action,) if next_action else (),
    )
