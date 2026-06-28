"""MemorySink / MemoryPolicy — classify write intent before routing.

This is the anti-wander anchor for all memory write paths (hooks, TeamKernel,
Z Code, manual commands). Every path produces a MemoryEvent; the sink classifies
intent and returns a policy decision without performing live ICM writes.

Write intent classification:

    decision   → Memories topic ``decisions``.  Explicit/manual only.
    mistake    → Memories topic ``mistakes``.    After curate/classifier confidence.
    handoff    → Blackboard topic or mesh.       Depends durability need.
    memoir     → Memoirs layer.                  BLOCKED unless source is curated
                                                  decisions/lessons.
    pending    → ICM ``pending`` topic.          Allowed from reflect only.

First slice is pure planning — no live ICM writes.  One dataclass + pure
functions, DI-friendly so the TeamKernel seam can unit-test without ICM.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

WriteIntent = Literal["decision", "mistake", "handoff", "memoir", "pending"]
SinkAction = Literal["allow", "block", "plan"]

MEMOIR_ALLOWED_SOURCES = frozenset({"decisions", "lessons"})
MEMOIR_BLOCKED_SOURCES = frozenset({"pending"})


@dataclass(frozen=True)
class MemoryEvent:
    """Normalised memory write intent from any path (hook, team, manual)."""

    kind: WriteIntent
    source: str              # "hook:reflect", "team:handoff", "manual:curate", …
    content: str
    importance: str = "medium"
    keywords: list[str] = field(default_factory=list)
    project: str = ""
    run_id: str = ""
    source_topic: str = ""   # e.g. "pending" when promoting from pending


@dataclass(frozen=True)
class SinkDecision:
    action: SinkAction
    target: str              # topic / "drop" / "plan"
    reason: str
    event: MemoryEvent


# --------------------------------------------------------------------------- #
# pure policy functions  (no side effects, no ICM calls)
# --------------------------------------------------------------------------- #

def evaluate(event: MemoryEvent) -> SinkDecision:
    """Classify write intent and return a policy decision.

    No ICM calls — pure planning only.  The caller decides whether to
    execute the ``allow`` or ``plan`` action.
    """
    if event.kind == "memoir":
        return _eval_memoir(event)
    if event.kind == "decision":
        return _eval_decision(event)
    if event.kind == "mistake":
        return _eval_mistake(event)
    if event.kind == "handoff":
        return _eval_handoff(event)
    if event.kind == "pending":
        return _eval_pending(event)
    return SinkDecision(
        action="block",
        target="drop",
        reason=f"Unknown write kind: {event.kind}",
        event=event,
    )


def _eval_memoir(event: MemoryEvent) -> SinkDecision:
    """Memoir gate: only curated decisions/lessons, never pending/raw."""
    src = event.source_topic
    if src in MEMOIR_BLOCKED_SOURCES:
        return SinkDecision(
            action="block",
            target="drop",
            reason=f"Memoir source '{src}' is blocked. "
                   f"Only {sorted(MEMOIR_ALLOWED_SOURCES)} may produce Memoirs.",
            event=event,
        )
    if src and src not in MEMOIR_ALLOWED_SOURCES:
        return SinkDecision(
            action="block",
            target="drop",
            reason=f"Memoir source '{src}' not allowed. "
                   f"Allowed: {sorted(MEMOIR_ALLOWED_SOURCES)}.",
            event=event,
        )
    return SinkDecision(
        action="plan",
        target="memoir",
        reason="Memoir write planned (no live ICM write in first slice). "
               "Source is a curated topic.",
        event=event,
    )


def _eval_decision(event: MemoryEvent) -> SinkDecision:
    """Decisions require an explicit manual or high-confidence source."""
    if event.source.startswith("manual:"):
        return SinkDecision(
            action="allow",
            target="decisions",
            reason="Explicit manual decision write.",
            event=event,
        )
    if event.source.startswith("hook:") or event.source.startswith("team:"):
        return SinkDecision(
            action="plan",
            target="decisions",
            reason=(f"Decision write from {event.source} planned — "
                    "needs user confirmation before committing."),
            event=event,
        )
    return SinkDecision(
        action="block",
        target="drop",
        reason=f"Decision write from {event.source} not allowed without manual intent.",
        event=event,
    )


def _eval_mistake(event: MemoryEvent) -> SinkDecision:
    """Mistakes allowed after curate/classifier confidence."""
    if event.source.startswith("curate:") or event.source.startswith("manual:"):
        return SinkDecision(
            action="allow",
            target="mistakes",
            reason=f"Mistake write from {event.source}.",
            event=event,
        )
    return SinkDecision(
        action="plan",
        target="mistakes",
        reason=(f"Mistake candidate from {event.source} planned — "
                "run through curate/classifier first."),
        event=event,
    )


def _eval_handoff(event: MemoryEvent) -> SinkDecision:
    """Handoff targets the blackboard.  Always allowed as plan."""
    return SinkDecision(
        action="plan",
        target="blackboard",
        reason=f"Handoff planned (no live ICM write in first slice).",
        event=event,
    )


def _eval_pending(event: MemoryEvent) -> SinkDecision:
    """Pending writes allowed from reflect/capture paths only."""
    if event.source.startswith("reflect:") or event.source == "capture":
        return SinkDecision(
            action="allow",
            target="pending",
            reason=f"Pending write from {event.source}.",
            event=event,
        )
    return SinkDecision(
        action="block",
        target="drop",
        reason=f"Pending write from {event.source} not allowed. "
               "Only reflect/capture may write pending.",
        event=event,
    )
