"""Structured surface decisions and lightweight usage audit.

The router is intentionally heuristic. This module makes that explicit by
recording what it surfaced, why, and what action it suggested so we can improve
from evidence instead of treating prompt matching as truth.
"""

from __future__ import annotations

import hashlib
import json
import time
from collections import Counter
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Callable

from .surface_context import SurfaceContext, build_surface_context, infer_intents
from .router_block import (
    RecallRunner,
    _default_recall,
    _relevant_lessons,
    _rung_routing,
    _set_next_action,
    match_sets,
    set_link_state,
)


@dataclass(frozen=True)
class SurfaceSet:
    name: str
    score: float
    state: str
    action: str
    description: str
    routing: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


@dataclass(frozen=True)
class SurfaceDecision:
    prompt_hash: str
    prompt_preview: str
    cwd: str
    context: dict[str, object]
    inferred_intents: tuple[str, ...]
    sets: tuple[SurfaceSet, ...]
    memory_count: int
    block: str

    def to_dict(self) -> dict[str, object]:
        data = asdict(self)
        data["sets"] = [entry.to_dict() for entry in self.sets]
        return data


def build_surface_decision(
    prompt: str,
    *,
    cwd: str | None = None,
    intent: str | None = None,
    phase: str | None = None,
    active_tool: str | None = None,
    last_command: str | None = None,
    changed_files: tuple[str, ...] | list[str] = (),
    recent_files: tuple[str, ...] | list[str] = (),
    context: SurfaceContext | None = None,
    recall_runner: RecallRunner | None = None,
) -> SurfaceDecision:
    ctx = context or build_surface_context(
        prompt,
        cwd=cwd,
        intent=intent,
        phase=phase,
        active_tool=active_tool,
        last_command=last_command,
        changed_files=changed_files,
        recent_files=recent_files,
    )
    entries: list[SurfaceSet] = []
    blocks: list[str] = []
    matched = match_sets(prompt, context=ctx)
    if matched:
        lines = ["🐾 paw sets:"]
        for curated, score in matched:
            desc = (curated.description or "").strip().splitlines()[0][:70]
            root = cwd or ctx.cwd
            state = set_link_state(curated, root)
            routing: tuple[str, ...] = ()
            if state == "healthy":
                routing = tuple(_rung_routing(curated, prompt, root, context=ctx)[:2])
                if routing:
                    action = "use"
                    lines.append(f"• {curated.name} (live) → use:")
                    lines.extend(f"    → {hit}" for hit in routing)
                else:
                    action = "live-reminder"
                    lines.append(f"• {curated.name} (live) — {desc}")
            elif state in {"degraded", "drifted"}:
                action = "verify"
                lines.append(f"• {curated.name} ({state}) — {desc} · paw verify {curated.name}")
            else:
                action = _set_next_action(curated)
                lines.append(f"• {curated.name} — {desc} · {action}")
            entries.append(
                SurfaceSet(
                    name=curated.name,
                    score=score,
                    state=state,
                    action=action,
                    description=desc,
                    routing=routing,
                )
            )
        blocks.append("\n".join(lines))

    lessons = _relevant_lessons(prompt, recall_runner or _default_recall)
    if lessons:
        lines = ["🧠 paw memory (high-signal lessons):"]
        for memory in lessons:
            imp = memory.get("importance", "high")
            summary = str(memory.get("summary", "")).strip().replace("\n", " ")[:130]
            lines.append(f"• [{imp}] {summary}")
        blocks.append("\n".join(lines))

    return SurfaceDecision(
        prompt_hash=hashlib.sha256(prompt.encode("utf-8", "ignore")).hexdigest()[:16],
        prompt_preview=prompt.strip().replace("\n", " ")[:160],
        cwd=str(Path(cwd or ctx.cwd or ".").resolve()),
        context=ctx.to_dict(),
        inferred_intents=tuple(sorted(infer_intents(ctx))),
        sets=tuple(entries),
        memory_count=len(lessons),
        block="\n".join(blocks),
    )


def default_audit_path(root: Path | None = None) -> Path:
    return (root or Path.cwd()) / ".paw" / "surface-audit.jsonl"


def write_surface_audit(decision: SurfaceDecision, *, path: Path | None = None) -> Path:
    target = path or default_audit_path(Path(decision.cwd))
    target.parent.mkdir(parents=True, exist_ok=True)
    record = decision.to_dict()
    record["ts"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    with target.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, ensure_ascii=False, separators=(",", ":")) + "\n")
    return target


def summarize_surface_audit(path: Path) -> dict[str, object]:
    if not path.exists():
        return {"path": str(path), "events": 0, "sets": {}, "actions": {}}
    set_counts: Counter[str] = Counter()
    action_counts: Counter[str] = Counter()
    events = 0
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            try:
                record = json.loads(line)
            except ValueError:
                continue
            events += 1
            for entry in record.get("sets", []):
                if not isinstance(entry, dict):
                    continue
                name = str(entry.get("name", ""))
                action = str(entry.get("action", ""))
                if name:
                    set_counts[name] += 1
                if action:
                    action_counts[action] += 1
    return {
        "path": str(path),
        "events": events,
        "sets": dict(set_counts.most_common()),
        "actions": dict(action_counts.most_common()),
    }
