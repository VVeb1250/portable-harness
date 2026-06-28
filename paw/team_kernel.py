"""Team Kernel v0: route-shaped role handoffs over the shared blackboard."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Callable, Protocol, Literal

from paw.blackboard import (
    BlackboardEntry,
    BlackboardResult,
    BlackboardScope,
)
from paw.memory_sink import MemoryEvent, SinkDecision, evaluate as sink_evaluate
from paw.router import RouteDecision

Status = Literal["success", "warning", "error"]
StoppedReason = Literal[
    "evaluation_passed",
    "evaluation_failed",
    "max_iterations",
    "route_stop",
    "blackboard_error",
]


@dataclass(frozen=True)
class TeamKernelContext:
    task: str
    decision: RouteDecision
    scope: BlackboardScope
    iteration: int
    entries: tuple[BlackboardEntry, ...] = ()


@dataclass(frozen=True)
class RoleOutput:
    content: str
    artifact: str | None = None
    importance: Literal["critical", "high", "medium", "low"] = "medium"


@dataclass(frozen=True)
class EvaluationResult:
    passed: bool
    summary: str
    artifact: str | None = None


@dataclass(frozen=True)
class TeamKernelResult:
    status: Status
    summary: str
    stopped_reason: StoppedReason
    iterations: int
    entries: tuple[BlackboardEntry, ...] = ()
    next_actions: tuple[str, ...] = ()
    artifacts: tuple[str, ...] = ()
    route: dict[str, object] = field(default_factory=dict)

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


class Blackboard(Protocol):
    def write(
        self,
        scope: BlackboardScope,
        entry: BlackboardEntry,
    ) -> BlackboardResult:
        ...

    def read(
        self,
        scope: BlackboardScope,
        *,
        query: str = "blackboard",
        role: str | None = None,
        kind: str | None = None,
        limit: int = 10,
    ) -> BlackboardResult:
        ...


RoleAdapter = Callable[[TeamKernelContext], RoleOutput]
Evaluator = Callable[[TeamKernelContext], EvaluationResult]


class TeamKernel:
    """Execute a bounded planner/implementer/reviewer/evaluator loop.

    The kernel owns orchestration and blackboard handoffs only. Agent launch,
    model choice, and tool execution stay behind injected role adapters.
    """

    def __init__(
        self,
        *,
        project: str,
        run_id: str,
        blackboard: Blackboard,
        planner: RoleAdapter,
        implementer: RoleAdapter,
        reviewer: RoleAdapter,
        evaluator: Evaluator,
        mutation_runner: RoleAdapter | None = None,
    ) -> None:
        self.scope = BlackboardScope(project=project, run_id=run_id)
        self.blackboard = blackboard
        self.planner = planner
        self.implementer = implementer
        self.reviewer = reviewer
        self.evaluator = evaluator
        self.mutation_runner = mutation_runner

    def run(self, *, task: str, decision: RouteDecision) -> TeamKernelResult:
        if decision.status == "error" or decision.strategy == "stop":
            return TeamKernelResult(
                status="error",
                summary=f"Route stopped before execution: {decision.summary}",
                stopped_reason="route_stop",
                iterations=0,
                next_actions=decision.next_actions,
                route=decision.to_dict(),
            )

        max_iterations = max(1, decision.max_iterations or 1)
        latest_entries: tuple[BlackboardEntry, ...] = ()
        last_review = ""
        for iteration in range(1, max_iterations + 1):
            plan = self.planner(self._context(task, decision, iteration))
            write = self._write("planner", "plan", plan)
            if write.status == "error":
                return self._blackboard_error(write, decision, iteration)

            implementation = self.implementer(
                self._context(task, decision, iteration)
            )
            write = self._write("implementer", "result", implementation)
            if write.status == "error":
                return self._blackboard_error(write, decision, iteration)

            if self.mutation_runner is not None:
                mutation = self.mutation_runner(
                    self._context(task, decision, iteration)
                )
                write = self._write("mutator", "result", mutation)
                if write.status == "error":
                    return self._blackboard_error(write, decision, iteration)

            review = self.reviewer(self._context(task, decision, iteration))
            last_review = review.content
            write = self._write("reviewer", "review", review)
            if write.status == "error":
                return self._blackboard_error(write, decision, iteration)

            latest_entries = self._read_entries()
            if not _is_pass(review.content):
                continue

            evaluation = self.evaluator(
                self._context(task, decision, iteration, latest_entries)
            )
            prefix = "PASS" if evaluation.passed else "FAIL"
            write = self._write(
                "evaluator",
                "result",
                RoleOutput(
                    content=f"{prefix}: {evaluation.summary}",
                    artifact=evaluation.artifact,
                    importance="high" if not evaluation.passed else "medium",
                ),
            )
            if write.status == "error":
                return self._blackboard_error(write, decision, iteration)

            latest_entries = self._read_entries()
            if evaluation.passed:
                return TeamKernelResult(
                    status="success",
                    summary=f"Team kernel completed after {iteration} iteration(s).",
                    stopped_reason="evaluation_passed",
                    iterations=iteration,
                    entries=latest_entries,
                    artifacts=_artifacts(latest_entries),
                    route=decision.to_dict(),
                )

            if iteration == max_iterations:
                return TeamKernelResult(
                    status="error",
                    summary=(
                        "Evaluator failed on the final iteration: "
                        f"{evaluation.summary}"
                    ),
                    stopped_reason="evaluation_failed",
                    iterations=iteration,
                    entries=latest_entries,
                    next_actions=(
                        "Inspect the evaluator result and start a new run with a narrower task.",
                    ),
                    artifacts=_artifacts(latest_entries),
                    route=decision.to_dict(),
                )

        latest_entries = self._read_entries()
        return TeamKernelResult(
            status="error",
            summary=(
                f"Stopped after max iterations ({max_iterations}) without review PASS. "
                f"Last review: {last_review}"
            ),
            stopped_reason="max_iterations",
            iterations=max_iterations,
            entries=latest_entries,
            next_actions=("Inspect reviewer feedback, reduce scope, then start a new run.",),
            artifacts=_artifacts(latest_entries),
            route=decision.to_dict(),
        )

    def _context(
        self,
        task: str,
        decision: RouteDecision,
        iteration: int,
        entries: tuple[BlackboardEntry, ...] | None = None,
    ) -> TeamKernelContext:
        return TeamKernelContext(
            task=task,
            decision=decision,
            scope=self.scope,
            iteration=iteration,
            entries=self._read_entries() if entries is None else entries,
        )

    def _write(
        self,
        role: str,
        kind: Literal["plan", "review", "result"],
        output: RoleOutput,
    ) -> BlackboardResult:
        return self.blackboard.write(
            self.scope,
            BlackboardEntry(
                role=role,
                kind=kind,
                content=output.content,
                artifact=output.artifact,
                importance=output.importance,
            ),
        )

    def _read_entries(self) -> tuple[BlackboardEntry, ...]:
        result = self.blackboard.read(self.scope, limit=50)
        return result.entries if result.status == "success" else ()

    def _blackboard_error(
        self,
        result: BlackboardResult,
        decision: RouteDecision,
        iteration: int,
    ) -> TeamKernelResult:
        return TeamKernelResult(
            status="error",
            summary=f"Blackboard handoff failed: {result.summary}",
            stopped_reason="blackboard_error",
            iterations=iteration,
            next_actions=result.next_actions
            or ("Check ICM health and retry the same run id once.",),
            route=decision.to_dict(),
        )


def plan_memory_sink(result: TeamKernelResult, *, project: str = "", run_id: str = "") -> SinkDecision:
    """Pure planning function — no live ICM writes.

    Produces a `SinkDecision` from a `TeamKernelResult`:

    - ``success`` → kind ``handoff`` or ``result``
    - ``error`` + evaluator_failed → kind ``pending`` or ``mistake-candidate``
    - ``error`` + other stopped reason → kind ``handoff`` (failure summary)

    The caller (CLI, adapter, or test) inspects the decision and chooses
    whether to execute it.
    """
    summary = result.summary
    status = ""
    if result.status == "success":
        status = "success_handoff"
        kind = "handoff"
    elif result.stopped_reason == "evaluation_failed":
        status = "failed_evaluator"
        kind = "mistake"
    else:
        status = "failed_other"
        kind = "handoff"

    event = MemoryEvent(
        kind=kind,
        source=f"team:{status}",
        content=(
            f"TeamKernel run {run_id}: {result.summary[:200]}"
        ),
        importance="low" if kind == "handoff" else "medium",
        project=project,
        run_id=run_id,
    )
    return sink_evaluate(event)


def plan_memory_handoff(*, project: str, run_id: str, kind: str,
                        content: str, status: str) -> SinkDecision:
    """Build a MemoryEvent for team handoff and run it through the sink.

    Inject this into any test or adapter that wants to verify its planned
    memory write without touching ICM.
    """
    event = MemoryEvent(
        kind=kind,  # type: ignore[arg-type]
        source=f"team:{status}",
        content=content[:1000],
        importance="medium",
        project=project,
        run_id=run_id,
    )
    return sink_evaluate(event)


def _is_pass(content: str) -> bool:
    return content.lstrip().casefold().startswith("pass")


def _artifacts(entries: tuple[BlackboardEntry, ...]) -> tuple[str, ...]:
    return tuple(entry.artifact for entry in entries if entry.artifact is not None)
