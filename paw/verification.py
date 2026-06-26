"""paw.verification — run focused checks on the mutated tree, drive the evaluator.

The Team Kernel applies the implementer's patch via ``paw.mutation`` and then asks
the evaluator whether the run passed. Until now the real-adapter evaluator was a
stub that always passed. This module makes the evaluator *actually verify* the
edits the mutator just wrote, and — because the kernel already feeds an evaluator
failure back into the next planner/implementer context — that closes the
mutate → verify → revise loop.

Verification is deliberately *focused*: by default it compiles only the Python
files the mutation touched (parsed from the diff artifact), so a syntax error in
the patch is caught in milliseconds with no project setup. A caller may instead
supply an explicit command (e.g. the affected-test subset) to run in the repo.

Pure stdlib; never raises across the evaluator boundary.
"""

from __future__ import annotations

import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Sequence

from paw.team_kernel import EvaluationResult, Evaluator, TeamKernelContext

# `+++ b/<path>` header lines in a unified diff name each changed file
_DIFF_PATH = re.compile(r"^\+\+\+ b/(.+)$", re.M)

CompletedProcessLike = subprocess.CompletedProcess
Runner = Callable[..., "subprocess.CompletedProcess[str]"]


@dataclass(frozen=True)
class VerificationResult:
    passed: bool
    summary: str
    returncode: int
    command: str
    output: str = ""

    def to_artifact(self) -> str | None:
        if not self.output:
            return None
        return f"verify({self.command}) rc={self.returncode}\n{self.output}"


def changed_paths_from_diff(diff: str) -> list[str]:
    """Files named by ``+++ b/<path>`` headers in a unified diff, in order."""
    seen: list[str] = []
    for m in _DIFF_PATH.finditer(diff or ""):
        path = m.group(1).strip()
        if path and path not in seen:
            seen.append(path)
    return seen


def _compileall_command(paths: Sequence[str]) -> list[str] | None:
    py = [p for p in paths if p.endswith(".py")]
    if not py:
        return None
    return [sys.executable, "-m", "compileall", "-q", *py]


def run_command(
    command: Sequence[str],
    *,
    cwd: str | Path,
    timeout: int = 300,
    runner: Runner | None = None,
) -> VerificationResult:
    """Run ``command`` in ``cwd``; map exit code to pass/fail. Never raises."""
    runner = runner or subprocess.run
    cmd = list(command)
    pretty = " ".join(cmd)
    try:
        cp = runner(
            cmd, cwd=str(cwd), capture_output=True, text=True,
            encoding="utf-8", errors="replace", timeout=timeout,
        )
    except (OSError, subprocess.SubprocessError) as error:
        return VerificationResult(False, f"verification could not run: {error}", 1, pretty)
    out = ((cp.stdout or "") + (cp.stderr or "")).strip()
    passed = cp.returncode == 0
    summary = (
        "verification passed" if passed
        else f"verification failed (rc={cp.returncode}): {_first_line(out)}"
    )
    return VerificationResult(passed, summary, cp.returncode, pretty, out[:2000])


def _first_line(text: str) -> str:
    for line in (text or "").splitlines():
        line = line.strip()
        if line:
            return line[:160]
    return "(no output)"


def make_verification_evaluator(
    *,
    repo: str | Path,
    command: Sequence[str] | None = None,
    timeout: int = 300,
    runner: Runner | None = None,
) -> Evaluator:
    """An evaluator that verifies the mutator's edits against the working tree.

    With no ``command`` it compiles only the Python files the mutation changed
    (read from the latest ``mutator`` diff artifact); a tree with no Python change
    passes with a note to run project tests. With a ``command`` it runs exactly
    that in ``repo``. Either way the boolean drives the kernel's revise loop.
    """
    repo = Path(repo)

    def evaluator(context: TeamKernelContext) -> EvaluationResult:
        mutator = next(
            (e for e in reversed(context.entries) if e.role == "mutator"),
            None,
        )
        cmd: list[str] | None
        if command is not None:
            cmd = list(command)
        else:
            diff = mutator.artifact if mutator and mutator.artifact else ""
            cmd = _compileall_command(changed_paths_from_diff(diff))
            if cmd is None:
                return EvaluationResult(
                    passed=True,
                    summary="no Python changes to verify; run project tests before committing",
                )
        result = run_command(cmd, cwd=repo, timeout=timeout, runner=runner)
        return EvaluationResult(
            passed=result.passed,
            summary=result.summary,
            artifact=result.to_artifact(),
        )

    return evaluator
