from __future__ import annotations

import subprocess
import unittest

from paw.verification import (
    VerificationResult,
    changed_paths_from_diff,
    make_verification_evaluator,
    run_command,
)


def _fake_runner(returncode: int, stdout: str = "", stderr: str = ""):
    def runner(cmd, **kwargs):
        return subprocess.CompletedProcess(cmd, returncode, stdout=stdout, stderr=stderr)
    return runner


_DIFF = (
    "--- a/pkg/m.py\n+++ b/pkg/m.py\n@@ -1 +1 @@\n-x = 1\n+x = 2\n"
    "--- a/README.md\n+++ b/README.md\n@@ -1 +1 @@\n-old\n+new\n"
)


class DiffParseTests(unittest.TestCase):
    def test_changed_paths(self) -> None:
        self.assertEqual(changed_paths_from_diff(_DIFF), ["pkg/m.py", "README.md"])

    def test_empty_diff(self) -> None:
        self.assertEqual(changed_paths_from_diff(""), [])

    def test_dedup_preserves_order(self) -> None:
        diff = "+++ b/a.py\n+++ b/b.py\n+++ b/a.py\n"
        self.assertEqual(changed_paths_from_diff(diff), ["a.py", "b.py"])


class RunCommandTests(unittest.TestCase):
    def test_pass(self) -> None:
        res = run_command(["echo", "ok"], cwd=".", runner=_fake_runner(0, "fine"))
        self.assertTrue(res.passed)
        self.assertEqual(res.returncode, 0)

    def test_fail_captures_first_line(self) -> None:
        res = run_command(["x"], cwd=".", runner=_fake_runner(1, "", "SyntaxError: bad\nmore"))
        self.assertFalse(res.passed)
        self.assertIn("SyntaxError", res.summary)
        self.assertIn("SyntaxError", res.to_artifact())

    def test_runner_raises_is_caught(self) -> None:
        def boom(cmd, **kwargs):
            raise OSError("no exe")
        res = run_command(["x"], cwd=".", runner=boom)
        self.assertFalse(res.passed)
        self.assertIn("could not run", res.summary)

    def test_no_output_artifact_is_none(self) -> None:
        res = VerificationResult(True, "ok", 0, "cmd", "")
        self.assertIsNone(res.to_artifact())


def _ctx_with_mutator_diff(diff: str):
    from paw.blackboard import BlackboardEntry, BlackboardScope
    from paw.team_kernel import TeamKernelContext
    from paw.router import RouteDecision

    entry = BlackboardEntry(role="mutator", kind="result", content="applied", artifact=diff)
    return TeamKernelContext(
        task="t",
        decision=RouteDecision(status="success", strategy="team", summary="s", max_iterations=2),
        scope=BlackboardScope(project="p", run_id="r"),
        iteration=1,
        entries=(entry,),
    )


class VerificationEvaluatorTests(unittest.TestCase):
    def test_compileall_runs_on_changed_python_only(self) -> None:
        seen = {}

        def runner(cmd, **kwargs):
            seen["cmd"] = cmd
            return subprocess.CompletedProcess(cmd, 0, stdout="", stderr="")

        ev = make_verification_evaluator(repo=".", runner=runner)
        result = ev(_ctx_with_mutator_diff(_DIFF))
        self.assertTrue(result.passed)
        # only the .py file, never README.md
        self.assertIn("pkg/m.py", seen["cmd"])
        self.assertNotIn("README.md", seen["cmd"])
        self.assertIn("compileall", seen["cmd"])

    def test_compile_failure_fails_evaluation(self) -> None:
        ev = make_verification_evaluator(
            repo=".", runner=_fake_runner(1, "", "  File m.py line 2\nSyntaxError: bad"),
        )
        result = ev(_ctx_with_mutator_diff(_DIFF))
        self.assertFalse(result.passed)
        self.assertIn("failed", result.summary)
        self.assertIsNotNone(result.artifact)

    def test_no_python_change_passes_with_note(self) -> None:
        ev = make_verification_evaluator(repo=".", runner=_fake_runner(1))  # runner must not be called
        result = ev(_ctx_with_mutator_diff("+++ b/README.md\n"))
        self.assertTrue(result.passed)
        self.assertIn("no Python changes", result.summary)

    def test_explicit_command_overrides_compileall(self) -> None:
        seen = {}

        def runner(cmd, **kwargs):
            seen["cmd"] = cmd
            return subprocess.CompletedProcess(cmd, 0, stdout="2 passed", stderr="")

        ev = make_verification_evaluator(repo=".", command=["pytest", "-q", "test_m.py"], runner=runner)
        result = ev(_ctx_with_mutator_diff(_DIFF))
        self.assertTrue(result.passed)
        self.assertEqual(seen["cmd"], ["pytest", "-q", "test_m.py"])


class VerifyReviseLoopTests(unittest.TestCase):
    """Verification failure must drive the kernel into another revise iteration."""

    def test_failed_verify_triggers_revise_then_passes(self) -> None:
        from paw.blackboard import BlackboardEntry, BlackboardResult, BlackboardScope
        from paw.team_kernel import RoleOutput, TeamKernel
        from paw.router import RouteDecision

        class MemBoard:
            def __init__(self) -> None:
                self.entries: list[BlackboardEntry] = []

            def write(self, scope, entry):
                self.entries.append(entry)
                return BlackboardResult(status="success", summary="ok", entries=tuple(self.entries))

            def read(self, scope, *, query="", role=None, kind=None, limit=10):
                return BlackboardResult(status="success", summary="ok", entries=tuple(self.entries))

        calls = {"verify": 0}

        def planner(ctx): return RoleOutput(content=f"plan {ctx.iteration}")
        def implementer(ctx): return RoleOutput(content=f"impl {ctx.iteration}")
        def mutator(ctx): return RoleOutput(content="applied", artifact="+++ b/m.py\n", importance="high")
        def reviewer(ctx): return RoleOutput(content="PASS: looks good")

        def evaluator(ctx):
            from paw.team_kernel import EvaluationResult
            calls["verify"] += 1
            passed = calls["verify"] >= 2          # fail first, pass on revise
            return EvaluationResult(passed=passed, summary="syntax" if not passed else "ok")

        result = TeamKernel(
            project="p", run_id="r", blackboard=MemBoard(),
            planner=planner, implementer=implementer, reviewer=reviewer,
            mutation_runner=mutator, evaluator=evaluator,
        ).run(
            task="fix it",
            decision=RouteDecision(status="success", strategy="team", summary="go", max_iterations=3),
        )
        self.assertEqual(result.status, "success")
        self.assertEqual(result.iterations, 2)     # one revise after the failed verify
        self.assertEqual(calls["verify"], 2)


if __name__ == "__main__":
    unittest.main()
