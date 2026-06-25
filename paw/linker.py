"""Bundle linker — slice-0 write-path: plan -> apply -> verify -> remove.

The thinnest honest transaction that wires a curated set into one host's
context file and can fully reverse itself. Scoped to CLI-only sets (no MCP,
no hooks) so it exercises the whole spine — discovery, preview, guarded apply,
ownership ledger, verification, reversible remove — without the TOML/MCP merge
path. repo-pack is the reference set.

Design invariants honored (docs/PAW-CLI-WORKFLOW-DRAFT.md §21):
  preview before mutation · no silent clobber (managed marker block only) ·
  explicit ownership ledger · every mutation backed up + fingerprinted ·
  drift stops automatic writes · remove touches only paw-owned text.

Stdlib only — read-path parity. No click/tomlkit needed for CLI sets.
"""
from __future__ import annotations

import hashlib
import json
import re
from dataclasses import asdict, dataclass, field
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
}

ABSENT = "absent"  # fingerprint sentinel for a non-existent target


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
    kind: Literal["detect-binary", "inject-context-block", "strip-context-block"]
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
    """unknown set/host or an unsupported set shape for slice-0."""


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

    if item.mcp:
        warnings.append(
            f"BLOCK: {set_name} has {len(item.mcp)} MCP server(s); MCP wiring is "
            "not in slice-0 (CLI-only sets). Use a later linker increment."
        )
    if host not in {h for t in item.non_mcp for h in t.get("host_support", [])} and item.non_mcp:
        warnings.append(f"host {host} is not listed in host_support for some tools")

    actions: list[Action] = []
    for tool in item.non_mcp:
        binary = tool.get("health_binary")
        if binary:
            present = which(binary) is not None
            actions.append(
                Action(
                    id=f"detect:{binary}",
                    kind="detect-binary",
                    target=binary,
                    summary=f"{binary} {'found on PATH' if present else 'MISSING — install before use'}",
                    reversible=True,
                    requires_approval=False,
                )
            )
            if not present:
                warnings.append(f"{binary} not on PATH; capability degraded until installed")

    if item.non_mcp and not any(w.startswith("BLOCK:") for w in warnings):
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
    return ChangePlan(
        intent="add-set",
        set_name=set_name,
        host=host,
        scope=scope,
        context_path=str(ctx),
        actions=tuple(actions),
        warnings=tuple(warnings),
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
    return json.loads(p.read_text(encoding="utf-8"))


def _save_ledger(root: Path, data: dict) -> None:
    p = ledger_path(root)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


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
    """Execute a plan with a drift guard + backup; commit ownership on success."""
    root = root or Path.cwd()
    if plan.status == "blocked":
        return TxResult("blocked", plan.summary, next_actions=("resolve plan warnings",))

    ctx = Path(plan.context_path)
    inject = next((a for a in plan.actions if a.kind == "inject-context-block"), None)
    if inject is None:
        return TxResult("ok", "nothing to wire (no CLI context action)", health="absent")

    # drift guard: the file must be exactly what the plan was built against.
    if fingerprint(ctx) != (inject.before_fingerprint or ABSENT):
        return TxResult(
            "drifted",
            f"{ctx.name} changed since the plan was built; refusing to write",
            next_actions=("regenerate the plan", "inspect the context diff"),
        )

    item = get_set(plan.set_name)
    backup = _backup(ctx)
    before = ctx.read_text(encoding="utf-8") if ctx.exists() else ""
    after = inject_block(before, item)
    ctx.parent.mkdir(parents=True, exist_ok=True)
    ctx.write_text(after, encoding="utf-8")

    data = _load_ledger(root)
    data["sets"][plan.set_name] = {
        "host": plan.host,
        "scope": plan.scope,
        "context_path": str(ctx),
        "block_owner": "paw-injected",
        "before_fingerprint": inject.before_fingerprint,
        "after_fingerprint": fingerprint(ctx),
        "backup": backup,
        "applied_at": _now(),
        "paw_version": PAW_VERSION,
    }
    _save_ledger(root, data)

    applied = tuple(a.id for a in plan.actions)
    return TxResult(
        "ok",
        f"linked {plan.set_name} into {ctx.name}",
        actions_applied=applied,
        health="healthy" if all("MISSING" not in a.summary for a in plan.actions) else "degraded",
        backup=backup,
        next_actions=(f"paw verify {plan.set_name}",),
    )


def verify(
    set_name: str,
    *,
    host: str = "claude-code",
    context: str | None = None,
    root: Path | None = None,
) -> TxResult:
    """Layered check: ownership ledger -> block present -> drift -> binary."""
    root = root or Path.cwd()
    item = get_set(set_name)
    ctx = _resolve_context(host, context, root)
    checks: list[str] = []

    record = _load_ledger(root)["sets"].get(set_name)
    text = ctx.read_text(encoding="utf-8") if ctx.exists() else ""

    if not has_block(text, set_name):
        checks.append(f"context block: ABSENT in {ctx.name}")
        return TxResult("ok", f"{set_name} not linked", health="blocked", checks=tuple(checks))
    checks.append(f"context block: present in {ctx.name}")

    if record and fingerprint(ctx) != record.get("after_fingerprint"):
        checks.append("fingerprint: DRIFTED since apply (file edited outside paw)")
        health: Health = "drifted"
    else:
        checks.append("fingerprint: matches ledger" if record else "fingerprint: no ledger record")
        health = "healthy"

    for tool in item.non_mcp:
        binary = tool.get("health_binary")
        if binary:
            ok = which(binary) is not None
            checks.append(f"binary {binary}: {'on PATH' if ok else 'MISSING'}")
            if not ok and health == "healthy":
                health = "degraded"

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
    """Strip only the paw-owned block; refuse on drift over user edits."""
    root = root or Path.cwd()
    ctx = _resolve_context(host, context, root)
    data = _load_ledger(root)
    record = data["sets"].get(set_name)

    if not ctx.exists() or not has_block(ctx.read_text(encoding="utf-8"), set_name):
        data["sets"].pop(set_name, None)
        _save_ledger(root, data)
        return TxResult("ok", f"{set_name} already unlinked", health="blocked")

    # drift guard: do not strip if the file changed since paw wrote it.
    if record and fingerprint(ctx) != record.get("after_fingerprint"):
        return TxResult(
            "drifted",
            f"{ctx.name} changed since paw wrote it; refusing to auto-remove",
            next_actions=("inspect the diff", "remove the paw block manually"),
        )

    backup = _backup(ctx)
    text = ctx.read_text(encoding="utf-8")
    ctx.write_text(strip_block(text, set_name), encoding="utf-8")
    data["sets"].pop(set_name, None)
    _save_ledger(root, data)
    return TxResult(
        "ok",
        f"unlinked {set_name} from {ctx.name}",
        actions_applied=(f"strip:{set_name}",),
        health="blocked",
        backup=backup,
    )
