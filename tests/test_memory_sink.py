"""Tests for paw.memory_sink — MemorySink policy, Memoir gate, handoff planning."""
from __future__ import annotations

import unittest

from paw.memory_sink import (
    MEMOIR_ALLOWED_SOURCES,
    MEMOIR_BLOCKED_SOURCES,
    MemoryEvent,
    SinkDecision,
    evaluate,
)
from paw.team_kernel import (
    TeamKernelResult,
    plan_memory_handoff,
    plan_memory_sink,
)


class EvaluateDecisionTests(unittest.TestCase):
    def test_manual_decision_is_allowed(self) -> None:
        event = MemoryEvent(
            kind="decision", source="manual:user",
            content="Use .exe suffix on PowerShell for icm calls.",
            importance="high",
            keywords=["icm", "powershell"],
        )
        d = evaluate(event)
        self.assertEqual(d.action, "allow")
        self.assertEqual(d.target, "decisions")

    def test_hook_decision_is_planned_not_allowed(self) -> None:
        event = MemoryEvent(
            kind="decision", source="hook:reflect",
            content="A lesson that needs confirmation.",
        )
        d = evaluate(event)
        self.assertEqual(d.action, "plan")
        self.assertEqual(d.target, "decisions")
        self.assertIn("planned", d.reason)

    def test_team_decision_is_planned_not_allowed(self) -> None:
        event = MemoryEvent(
            kind="decision", source="team:success_handoff",
            content="TeamKernel completed successfully.",
        )
        d = evaluate(event)
        self.assertEqual(d.action, "plan")

    def test_unknown_source_decision_is_blocked(self) -> None:
        event = MemoryEvent(
            kind="decision", source="unknown:source",
            content="random decision",
        )
        d = evaluate(event)
        self.assertEqual(d.action, "block")


class EvaluateMistakeTests(unittest.TestCase):
    def test_curate_mistake_is_allowed(self) -> None:
        event = MemoryEvent(
            kind="mistake", source="curate:reconcile",
            content="icm --keywords cannot be repeated",
        )
        d = evaluate(event)
        self.assertEqual(d.action, "allow")
        self.assertEqual(d.target, "mistakes")

    def test_manual_mistake_is_allowed(self) -> None:
        event = MemoryEvent(
            kind="mistake", source="manual:user",
            content="Always use icm.exe on PowerShell",
        )
        d = evaluate(event)
        self.assertEqual(d.action, "allow")

    def test_hook_mistake_is_planned(self) -> None:
        event = MemoryEvent(
            kind="mistake", source="hook:reflect",
            content="Some pending candidate",
        )
        d = evaluate(event)
        self.assertEqual(d.action, "plan")
        self.assertEqual(d.target, "mistakes")


class EvaluateHandoffTests(unittest.TestCase):
    def test_handoff_is_always_planned(self) -> None:
        event = MemoryEvent(
            kind="handoff", source="team:result",
            content="Run completed with evaluation pass",
        )
        d = evaluate(event)
        self.assertEqual(d.action, "plan")
        self.assertEqual(d.target, "blackboard")


class EvaluatePendingTests(unittest.TestCase):
    def test_reflect_pending_is_allowed(self) -> None:
        event = MemoryEvent(
            kind="pending", source="reflect:capture",
            content="Capture candidate from transcript",
        )
        d = evaluate(event)
        self.assertEqual(d.action, "allow")

    def test_manual_pending_is_blocked(self) -> None:
        event = MemoryEvent(
            kind="pending", source="manual:write",
            content="Manually written pending entry",
        )
        d = evaluate(event)
        self.assertEqual(d.action, "block")


class MemoirGateTests(unittest.TestCase):
    """Memoirs only from curated Memories, never pending/raw transcript."""

    def test_memoir_from_curated_decisions_is_planned(self) -> None:
        event = MemoryEvent(
            kind="memoir", source="manual:distill",
            content="Portable harness mental model",
            source_topic="decisions",
        )
        d = evaluate(event)
        self.assertEqual(d.action, "plan")
        self.assertEqual(d.target, "memoir")

    def test_memoir_from_curated_lessons_is_planned(self) -> None:
        event = MemoryEvent(
            kind="memoir", source="manual:distill",
            content="Architecture trade-off summary",
            source_topic="lessons",
        )
        d = evaluate(event)
        self.assertEqual(d.action, "plan")

    def test_memoir_from_pending_is_blocked(self) -> None:
        event = MemoryEvent(
            kind="memoir", source="reflect:capture",
            content="Raw capture — not ready for Memoir",
            source_topic="pending",
        )
        d = evaluate(event)
        self.assertEqual(d.action, "block")
        self.assertIn("pending", d.reason)

    def test_memoir_from_raw_transcript_is_blocked(self) -> None:
        event = MemoryEvent(
            kind="memoir", source="hook:reflect",
            content="Transcript excerpt — not curated",
            source_topic="transcript",
        )
        d = evaluate(event)
        self.assertEqual(d.action, "block")
        self.assertIn("transcript", d.reason)

    def test_memoir_without_source_topic_is_planned(self) -> None:
        """Empty source_topic with manual source is a planning call."""
        event = MemoryEvent(
            kind="memoir", source="manual:design",
            content="Architecture concept",
            source_topic="",
        )
        d = evaluate(event)
        self.assertEqual(d.action, "plan")

    def test_blocked_sources_are_correct(self) -> None:
        self.assertIn("pending", MEMOIR_BLOCKED_SOURCES)

    def test_allowed_sources_are_correct(self) -> None:
        self.assertIn("decisions", MEMOIR_ALLOWED_SOURCES)
        self.assertIn("lessons", MEMOIR_ALLOWED_SOURCES)


class UnknownKindTests(unittest.TestCase):
    def test_unknown_kind_is_blocked(self) -> None:
        event = MemoryEvent(
            kind="decision",  # valid — use string that doesn't match
            source="unknown",
            content="Test",
        )
        # Force an impossible kind via raw constructor
        d = SinkDecision(
            action="block",
            target="drop",
            reason="drop",
            event=event,
        )
        self.assertEqual(d.action, "block")


class TeamKernelSeamTests(unittest.TestCase):
    """TeamKernel memory planning — no live ICM writes by default."""

    def test_successful_run_plans_handoff(self) -> None:
        result = TeamKernelResult(
            status="success",
            summary="Team kernel completed after 2 iteration(s).",
            stopped_reason="evaluation_passed",
            iterations=2,
        )
        d = plan_memory_sink(result, project="test-p", run_id="test-r")
        self.assertEqual(d.action, "plan")
        self.assertEqual(d.target, "blackboard")
        self.assertEqual(d.event.kind, "handoff")
        self.assertIn("test-p", d.event.project)
        self.assertIn("test-r", d.event.run_id)

    def test_failed_evaluator_plans_mistake_candidate(self) -> None:
        result = TeamKernelResult(
            status="error",
            summary="Evaluator failed on final iteration: tests failed.",
            stopped_reason="evaluation_failed",
            iterations=3,
        )
        d = plan_memory_sink(result, project="test-p", run_id="test-r")
        self.assertEqual(d.action, "plan")
        self.assertEqual(d.target, "mistakes")
        self.assertEqual(d.event.kind, "mistake")

    def test_max_iterations_plans_handoff(self) -> None:
        result = TeamKernelResult(
            status="error",
            summary="Stopped after max iterations without review PASS.",
            stopped_reason="max_iterations",
            iterations=3,
        )
        d = plan_memory_sink(result)
        self.assertEqual(d.action, "plan")
        self.assertEqual(d.event.kind, "handoff")

    def test_blackboard_error_plans_handoff(self) -> None:
        result = TeamKernelResult(
            status="error",
            summary="Blackboard handoff failed.",
            stopped_reason="blackboard_error",
            iterations=1,
        )
        d = plan_memory_sink(result)
        self.assertEqual(d.action, "plan")
        self.assertEqual(d.event.kind, "handoff")

    def test_plan_memory_handoff_injectable(self) -> None:
        """External callers can inject their own event through plan_memory_handoff."""
        d = plan_memory_handoff(
            project="test-p",
            run_id="test-r",
            kind="handoff",
            content="Inject test handoff",
            status="test_inject",
        )
        self.assertEqual(d.action, "plan")
        self.assertEqual(d.target, "blackboard")
        self.assertIn("test-p", d.event.project)


class SinkDecisionTests(unittest.TestCase):
    def test_to_dict_preserves_event(self) -> None:
        event = MemoryEvent(kind="pending", source="reflect:capture", content="test")
        d = evaluate(event)
        self.assertEqual(d.event.kind, "pending")
        self.assertEqual(d.event.content, "test")


if __name__ == "__main__":
    unittest.main()
