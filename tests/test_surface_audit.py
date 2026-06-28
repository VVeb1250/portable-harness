from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest import mock

import paw.router_block as rb
from paw.surface_audit import (
    build_surface_decision,
    summarize_surface_audit,
    write_surface_audit,
)


class SurfaceAuditTests(unittest.TestCase):
    def test_surface_decision_records_set_state_and_action(self) -> None:
        with (
            mock.patch.object(rb, "_LINK_STATE_PROBE", lambda s, cwd: "healthy"),
            mock.patch.object(rb, "_PATH_PROBE", lambda b: "/usr/bin/" + b),
        ):
            decision = build_surface_decision(
                "find all callers of estimate_cost",
                cwd=".",
                recall_runner=lambda p: "[]",
            )

        self.assertIn("code-intelligence", {entry.name for entry in decision.sets})
        code = next(entry for entry in decision.sets if entry.name == "code-intelligence")
        self.assertEqual(code.state, "healthy")
        self.assertEqual(code.action, "use")
        self.assertEqual(code.posture, "conditional")
        self.assertTrue(any("codegraph" in rung for rung in code.routing))
        self.assertIn("code-intelligence (live)", decision.block)
        self.assertIn("code_impact", decision.inferred_intents)

    def test_surface_decision_routes_absent_conditional_to_plan(self) -> None:
        with mock.patch.object(rb, "_LINK_STATE_PROBE", lambda s, cwd: "absent"):
            decision = build_surface_decision(
                "find all callers of estimate_cost",
                cwd=".",
                recall_runner=lambda p: "[]",
            )

        code = next(entry for entry in decision.sets if entry.name == "code-intelligence")
        self.assertEqual(code.action, "paw plan code-intelligence (conditional)")

    def test_surface_decision_records_host_context(self) -> None:
        with mock.patch.object(rb, "_LINK_STATE_PROBE", lambda s, cwd: "absent"):
            decision = build_surface_decision(
                "run only tests for this change",
                cwd=".",
                changed_files=("paw/router_block.py",),
                phase="verify",
                recall_runner=lambda p: "[]",
            )

        self.assertEqual(decision.context["phase"], "verify")
        self.assertIn("affected_tests", decision.inferred_intents)
        self.assertIn("test-affected", {entry.name for entry in decision.sets})

    def test_audit_summary_counts_sets_and_actions(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "surface-audit.jsonl"
            with mock.patch.object(rb, "_LINK_STATE_PROBE", lambda s, cwd: "absent"):
                write_surface_audit(
                    build_surface_decision(
                        "find all callers of estimate_cost",
                        cwd=directory,
                        recall_runner=lambda p: "[]",
                    ),
                    path=path,
                )
                write_surface_audit(
                    build_surface_decision(
                        "query a csv with sql",
                        cwd=directory,
                        recall_runner=lambda p: "[]",
                    ),
                    path=path,
                )

            summary = summarize_surface_audit(path)

        self.assertEqual(summary["events"], 2)
        self.assertIn("code-intelligence", summary["sets"])
        self.assertTrue(summary["actions"])
        self.assertIn("conditional", summary["postures"])
        self.assertIn("default", summary["postures"])

    def test_surface_decision_marks_ready_non_default_as_task_specific(self) -> None:
        with mock.patch.object(rb, "_LINK_STATE_PROBE", lambda s, cwd: "absent"):
            decision = build_surface_decision(
                "package the current git diff and relevant repo context",
                cwd=".",
                intent="repo handoff",
                recall_runner=lambda p: "[]",
            )

        pack = next(entry for entry in decision.sets if entry.name == "repo-pack")
        self.assertEqual(pack.posture, "task-specific")
        self.assertEqual(pack.action, "paw plan repo-pack (task-specific)")


if __name__ == "__main__":
    unittest.main()
