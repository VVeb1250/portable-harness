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


if __name__ == "__main__":
    unittest.main()
