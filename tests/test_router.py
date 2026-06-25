from __future__ import annotations

import json
import subprocess
import sys
import unittest

from paw.router import RouteRequest, route


class RouterV0Tests(unittest.TestCase):
    def test_complex_public_code_uses_proven_team_shape(self) -> None:
        decision = route(
            RouteRequest(
                task="Refactor the parser across several files and fix its tests.",
                complexity="complex",
                risk="medium",
                sensitivity="public",
            )
        )

        self.assertEqual(decision.status, "success")
        self.assertEqual(decision.strategy, "team")
        self.assertEqual(decision.roles["planner"], "codex")
        self.assertEqual(decision.roles["implementer"], "deepseek")
        self.assertEqual(decision.roles["reviewer"], "codex")
        self.assertEqual(decision.max_iterations, 3)

    def test_restricted_work_never_routes_to_external_workhorse(self) -> None:
        decision = route(
            RouteRequest(
                task="Fix the proprietary authentication service.",
                complexity="complex",
                risk="high",
                sensitivity="restricted",
            )
        )

        self.assertNotIn("deepseek", decision.roles.values())
        self.assertIn("privacy:restricted", decision.constraints)

    def test_simple_low_risk_work_uses_lean_solo_route(self) -> None:
        decision = route(
            RouteRequest(
                task="Rename a local variable.",
                complexity="simple",
                risk="low",
                sensitivity="public",
            )
        )

        self.assertEqual(decision.strategy, "solo")
        self.assertEqual(decision.roles, {"implementer": "deepseek"})
        self.assertEqual(decision.max_iterations, 1)

    def test_cli_emits_machine_readable_decision(self) -> None:
        result = subprocess.run(
            [
                sys.executable,
                "-m",
                "paw",
                "route",
                "Refactor the parser across several files.",
                "--complexity",
                "complex",
                "--risk",
                "medium",
                "--sensitivity",
                "public",
                "--json",
            ],
            check=False,
            capture_output=True,
            text=True,
        )

        self.assertEqual(result.returncode, 0, result.stderr)
        payload = json.loads(result.stdout)
        self.assertEqual(payload["strategy"], "team")
        self.assertEqual(payload["roles"]["implementer"], "deepseek")
        self.assertTrue(payload["reasons"])


class SmartRouterTests(unittest.TestCase):
    def test_auto_complexity_keeps_tiny_documentation_work_solo(self) -> None:
        decision = route(
            RouteRequest(
                task="Fix a typo in README.md.",
                complexity="auto",
                risk="auto",
                sensitivity="public",
            )
        )

        self.assertEqual(decision.classification["complexity"], "simple")
        self.assertEqual(decision.classification["task_kind"], "docs")
        self.assertEqual(decision.strategy, "solo")
        self.assertGreaterEqual(decision.confidence, 0.7)

    def test_auto_classification_escalates_security_migration(self) -> None:
        decision = route(
            RouteRequest(
                task=(
                    "Refactor authentication across multiple modules, migrate the "
                    "credential schema, and add regression tests."
                ),
                complexity="auto",
                risk="auto",
                sensitivity="private",
            )
        )

        self.assertEqual(decision.classification["complexity"], "complex")
        self.assertEqual(decision.classification["risk"], "high")
        self.assertEqual(decision.classification["task_kind"], "security")
        self.assertEqual(decision.strategy, "team")
        self.assertEqual(decision.roles["implementer"], "deepseek")

    def test_budget_pressure_degrades_public_medium_risk_team_to_workhorse(self) -> None:
        decision = route(
            RouteRequest(
                task="Refactor the parser across several files and fix its tests.",
                complexity="complex",
                risk="medium",
                sensitivity="public",
                max_budget_usd=0.20,
            )
        )

        self.assertEqual(decision.status, "warning")
        self.assertEqual(decision.strategy, "solo")
        self.assertEqual(decision.roles, {"implementer": "deepseek"})
        self.assertIn("budget:degraded", decision.constraints)
        self.assertLessEqual(decision.estimated_cost_usd, 0.20)

    def test_budget_never_overrides_restricted_privacy(self) -> None:
        decision = route(
            RouteRequest(
                task="Refactor proprietary authentication code.",
                complexity="complex",
                risk="high",
                sensitivity="restricted",
                max_budget_usd=0.20,
            )
        )

        self.assertEqual(decision.status, "error")
        self.assertEqual(decision.strategy, "stop")
        self.assertIn("privacy:restricted", decision.constraints)
        self.assertIn("budget:insufficient", decision.constraints)

    def test_unknown_agent_inventory_stops_with_recovery_action(self) -> None:
        decision = route(
            RouteRequest(
                task="Implement a parser.",
                complexity="complex",
                risk="medium",
                sensitivity="public",
                available_agents=("mystery-agent",),
            )
        )

        self.assertEqual(decision.status, "error")
        self.assertEqual(decision.strategy, "stop")
        self.assertTrue(decision.next_actions)


if __name__ == "__main__":
    unittest.main()
