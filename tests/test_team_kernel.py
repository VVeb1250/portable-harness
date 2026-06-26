from __future__ import annotations

import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path
from unittest.mock import patch

from paw.blackboard import BlackboardEntry, BlackboardResult, BlackboardScope
from paw.router import RouteDecision
from paw.team_adapters import TeamAdapterProfile
from paw.team_kernel import (
    EvaluationResult,
    RoleOutput,
    TeamKernel,
    TeamKernelContext,
)


class InMemoryBlackboard:
    def __init__(self) -> None:
        self.entries: list[BlackboardEntry] = []
        self.scopes: list[BlackboardScope] = []

    def write(
        self,
        scope: BlackboardScope,
        entry: BlackboardEntry,
    ) -> BlackboardResult:
        self.scopes.append(scope)
        self.entries.append(entry)
        return BlackboardResult(status="success", summary=f"stored {entry.kind}")

    def read(
        self,
        scope: BlackboardScope,
        *,
        query: str = "blackboard",
        role: str | None = None,
        kind: str | None = None,
        limit: int = 10,
    ) -> BlackboardResult:
        entries = tuple(
            entry
            for entry in self.entries[-limit:]
            if (role is None or entry.role == role)
            and (kind is None or entry.kind == kind)
        )
        return BlackboardResult(
            status="success",
            summary=f"read {len(entries)}",
            entries=entries,
        )


def _team_decision(*, max_iterations: int = 3) -> RouteDecision:
    return RouteDecision(
        status="success",
        summary="Selected team route",
        strategy="team",
        roles={"planner": "codex", "implementer": "deepseek", "reviewer": "codex"},
        max_iterations=max_iterations,
    )


class TeamKernelTests(unittest.TestCase):
    def test_team_kernel_writes_role_handoffs_and_stops_on_evaluation_pass(self) -> None:
        board = InMemoryBlackboard()
        seen: list[TeamKernelContext] = []

        def planner(context: TeamKernelContext) -> RoleOutput:
            seen.append(context)
            return RoleOutput(content="Plan: add focused tests, then implement.")

        def implementer(context: TeamKernelContext) -> RoleOutput:
            seen.append(context)
            self.assertTrue(
                any(entry.role == "planner" and entry.kind == "plan" for entry in context.entries)
            )
            return RoleOutput(content="Result: tests and implementation are updated.")

        def reviewer(context: TeamKernelContext) -> RoleOutput:
            seen.append(context)
            self.assertTrue(any(entry.role == "implementer" for entry in context.entries))
            return RoleOutput(content="PASS: focused tests cover the behavior.")

        def evaluator(context: TeamKernelContext) -> EvaluationResult:
            seen.append(context)
            self.assertTrue(any(entry.role == "reviewer" for entry in context.entries))
            return EvaluationResult(passed=True, summary="unit target passed")

        result = TeamKernel(
            project="portable-harness",
            run_id="kernel-1",
            blackboard=board,
            planner=planner,
            implementer=implementer,
            reviewer=reviewer,
            evaluator=evaluator,
        ).run(task="Refactor parser safely.", decision=_team_decision())

        self.assertEqual(result.status, "success")
        self.assertEqual(result.stopped_reason, "evaluation_passed")
        self.assertEqual(result.iterations, 1)
        self.assertEqual(
            [(entry.role, entry.kind) for entry in board.entries],
            [
                ("planner", "plan"),
                ("implementer", "result"),
                ("reviewer", "review"),
                ("evaluator", "result"),
            ],
        )
        self.assertEqual({context.scope.run_id for context in seen}, {"kernel-1"})

    def test_reviewer_revise_retries_without_evaluating_until_pass(self) -> None:
        board = InMemoryBlackboard()
        reviewer_outputs = [
            RoleOutput(content="REVISE: missing regression test."),
            RoleOutput(content="PASS: regression test added."),
        ]
        evaluator_calls = 0

        def planner(context: TeamKernelContext) -> RoleOutput:
            return RoleOutput(content=f"Plan iteration {context.iteration}")

        def implementer(context: TeamKernelContext) -> RoleOutput:
            return RoleOutput(content=f"Result iteration {context.iteration}")

        def reviewer(context: TeamKernelContext) -> RoleOutput:
            return reviewer_outputs.pop(0)

        def evaluator(context: TeamKernelContext) -> EvaluationResult:
            nonlocal evaluator_calls
            evaluator_calls += 1
            return EvaluationResult(passed=True, summary="tests passed after revise")

        result = TeamKernel(
            project="portable-harness",
            run_id="kernel-retry",
            blackboard=board,
            planner=planner,
            implementer=implementer,
            reviewer=reviewer,
            evaluator=evaluator,
        ).run(task="Fix a regression.", decision=_team_decision(max_iterations=2))

        self.assertEqual(result.status, "success")
        self.assertEqual(result.iterations, 2)
        self.assertEqual(evaluator_calls, 1)
        self.assertEqual(
            [entry.role for entry in board.entries],
            [
                "planner",
                "implementer",
                "reviewer",
                "planner",
                "implementer",
                "reviewer",
                "evaluator",
            ],
        )

    def test_max_iterations_stop_is_explicit_when_review_never_passes(self) -> None:
        board = InMemoryBlackboard()

        def planner(context: TeamKernelContext) -> RoleOutput:
            return RoleOutput(content="Plan")

        def implementer(context: TeamKernelContext) -> RoleOutput:
            return RoleOutput(content="Result")

        def reviewer(context: TeamKernelContext) -> RoleOutput:
            return RoleOutput(content="REVISE: still incomplete.")

        def evaluator(context: TeamKernelContext) -> EvaluationResult:
            self.fail("evaluator must not run until reviewer passes")

        result = TeamKernel(
            project="portable-harness",
            run_id="kernel-stop",
            blackboard=board,
            planner=planner,
            implementer=implementer,
            reviewer=reviewer,
            evaluator=evaluator,
        ).run(task="Fix a stubborn bug.", decision=_team_decision(max_iterations=2))

        self.assertEqual(result.status, "error")
        self.assertEqual(result.stopped_reason, "max_iterations")
        self.assertIn("max iterations", result.summary.lower())
        self.assertEqual(result.iterations, 2)
        self.assertEqual([entry.role for entry in board.entries].count("evaluator"), 0)
        self.assertTrue(result.next_actions)


class TeamKernelCliIntegrationTests(unittest.TestCase):
    @unittest.skipUnless(shutil.which("icm.exe"), "ICM CLI is not installed")
    def test_cli_mock_run_uses_isolated_icm_blackboard(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            database = str(Path(directory) / "team-kernel.db")
            run = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "paw",
                    "team",
                    "run",
                    "Refactor parser safely.",
                    "--project",
                    "portable-harness",
                    "--run-id",
                    "cli-smoke",
                    "--complexity",
                    "complex",
                    "--risk",
                    "medium",
                    "--sensitivity",
                    "public",
                    "--mock",
                    "--db",
                    database,
                    "--json",
                ],
                check=False,
                capture_output=True,
                text=True,
            )

            self.assertEqual(run.returncode, 0, run.stderr)
            payload = json.loads(run.stdout)
            self.assertEqual(payload["status"], "success")
            self.assertEqual(payload["stopped_reason"], "evaluation_passed")
            self.assertEqual(payload["iterations"], 1)
            self.assertEqual(
                [(entry["role"], entry["kind"]) for entry in payload["entries"]],
                [
                    ("planner", "plan"),
                    ("implementer", "result"),
                    ("reviewer", "review"),
                    ("evaluator", "result"),
                ],
            )

    def test_cli_codex_deepseek_profile_is_wired_without_claude(self) -> None:
        from paw import __main__ as paw_main

        board = InMemoryBlackboard()
        built_repos: list[Path] = []

        def planner(context: TeamKernelContext) -> RoleOutput:
            return RoleOutput(content="Plan from Codex")

        def implementer(context: TeamKernelContext) -> RoleOutput:
            return RoleOutput(content="Implementation from DeepSeek")

        def reviewer(context: TeamKernelContext) -> RoleOutput:
            return RoleOutput(content="PASS: review from Codex")

        def evaluator(context: TeamKernelContext) -> EvaluationResult:
            return EvaluationResult(passed=True, summary="local handoff ok")

        def build_profile(*, repo: Path) -> TeamAdapterProfile:
            built_repos.append(repo)
            return TeamAdapterProfile(
                planner=planner,
                implementer=implementer,
                reviewer=reviewer,
                evaluator=evaluator,
            )

        with (
            patch.object(paw_main, "IcmBlackboard", lambda database=None: board),
            patch.object(paw_main, "build_codex_deepseek_adapters", build_profile),
        ):
            stdout = StringIO()
            with redirect_stdout(stdout):
                code = paw_main.main(
                    [
                        "team",
                        "run",
                        "Fix the parser.",
                        "--project",
                        "portable-harness",
                        "--run-id",
                        "profile-test",
                        "--complexity",
                        "complex",
                        "--risk",
                        "medium",
                        "--sensitivity",
                        "public",
                        "--adapters",
                        "codex-deepseek",
                        "--json",
                    ]
                )

        self.assertEqual(code, 0)
        self.assertEqual(built_repos, [Path.cwd()])
        payload = json.loads(stdout.getvalue())
        self.assertEqual(payload["status"], "success")
        self.assertEqual(
            [entry["content"] for entry in payload["entries"]],
            [
                "Plan from Codex",
                "Implementation from DeepSeek",
                "PASS: review from Codex",
                "PASS: local handoff ok",
            ],
        )

    def test_cli_blocks_codex_deepseek_for_restricted_work_before_adapter_build(self) -> None:
        from paw import __main__ as paw_main

        def forbidden_build(*, repo: Path) -> TeamAdapterProfile:
            self.fail("restricted work must not build an external DeepSeek adapter")

        with patch.object(paw_main, "build_codex_deepseek_adapters", forbidden_build):
            stdout = StringIO()
            with redirect_stdout(stdout):
                code = paw_main.main(
                    [
                        "team",
                        "run",
                        "Fix proprietary authentication code.",
                        "--project",
                        "portable-harness",
                        "--run-id",
                        "restricted-profile",
                        "--complexity",
                        "complex",
                        "--risk",
                        "high",
                        "--sensitivity",
                        "restricted",
                        "--adapters",
                        "codex-deepseek",
                        "--json",
                    ]
                )

        self.assertEqual(code, 1)
        payload = json.loads(stdout.getvalue())
        self.assertEqual(payload["status"], "error")
        self.assertIn("restricted", payload["summary"].lower())
        self.assertIn("external", payload["summary"].lower())

    def test_cli_blocks_codex_deepseek_when_route_is_not_codex_deepseek_team(self) -> None:
        from paw import __main__ as paw_main

        def forbidden_build(*, repo: Path) -> TeamAdapterProfile:
            self.fail("route mismatch must block before adapter build")

        with patch.object(paw_main, "build_codex_deepseek_adapters", forbidden_build):
            stdout = StringIO()
            with redirect_stdout(stdout):
                code = paw_main.main(
                    [
                        "team",
                        "run",
                        "Fix a typo in README.md.",
                        "--project",
                        "portable-harness",
                        "--run-id",
                        "route-mismatch",
                        "--complexity",
                        "auto",
                        "--risk",
                        "auto",
                        "--sensitivity",
                        "public",
                        "--adapters",
                        "codex-deepseek",
                        "--json",
                    ]
                )

        self.assertEqual(code, 1)
        payload = json.loads(stdout.getvalue())
        self.assertEqual(payload["status"], "error")
        self.assertIn("route", payload["summary"].lower())
        self.assertIn("codex-deepseek", payload["summary"])


if __name__ == "__main__":
    unittest.main()
