"""Deterministic, side-effect-free routing for agent work."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Literal

Complexity = Literal["auto", "simple", "complex"]
Risk = Literal["low", "medium", "high"]
Sensitivity = Literal["public", "private", "restricted"]
Status = Literal["success", "warning", "error"]
Strategy = Literal["solo", "team", "stop"]

DEFAULT_AGENTS = ("codex", "deepseek")


@dataclass(frozen=True)
class RouteRequest:
    task: str
    complexity: Complexity = "auto"
    risk: Risk = "medium"
    sensitivity: Sensitivity = "private"
    available_agents: tuple[str, ...] = DEFAULT_AGENTS
    max_budget_usd: float | None = None


@dataclass(frozen=True)
class RouteDecision:
    status: Status
    summary: str
    strategy: Strategy
    roles: dict[str, str] = field(default_factory=dict)
    reasons: tuple[str, ...] = ()
    constraints: tuple[str, ...] = ()
    next_actions: tuple[str, ...] = ()
    artifacts: tuple[str, ...] = ()
    max_iterations: int = 0

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


def route(request: RouteRequest) -> RouteDecision:
    """Return a conservative route without launching agents or touching config."""
    if not request.task.strip():
        return _stop("Task is empty.", "Provide a non-empty task.")

    available = set(request.available_agents)
    constraints: list[str] = []
    if request.sensitivity == "restricted":
        constraints.append("privacy:restricted")

    complexity = "complex" if request.complexity == "auto" else request.complexity

    if request.sensitivity == "restricted":
        if "codex" not in available:
            return _stop(
                "No privacy-safe agent is available.",
                "Make codex available or change the repository privacy policy.",
                constraints=constraints,
            )
        return _decision(
            strategy="team" if complexity == "complex" else "solo",
            roles=_codex_roles(complexity),
            reasons=(
                "Restricted work stays on the approved local/subscription seat.",
                "Risk and privacy override the cheaper external workhorse.",
            ),
            constraints=constraints,
            max_iterations=3 if complexity == "complex" else 1,
        )

    if complexity == "simple" and request.risk == "low":
        implementer = _first_available(("deepseek", "codex"), available)
        if implementer is None:
            return _stop("No implementer is available.", "Enable codex or deepseek.")
        return _decision(
            strategy="solo",
            roles={"implementer": implementer},
            reasons=("Simple low-risk work does not justify team coordination cost.",),
            constraints=constraints,
            max_iterations=1,
        )

    if {"codex", "deepseek"}.issubset(available):
        return _decision(
            strategy="team",
            roles={
                "planner": "codex",
                "implementer": "deepseek",
                "reviewer": "codex",
            },
            reasons=(
                "Complex work benefits from a strong planner and reviewer.",
                "Implementation is delegated to the lower-cost external workhorse.",
            ),
            constraints=constraints,
            max_iterations=3,
        )

    if "codex" in available:
        return _decision(
            strategy="solo",
            roles={"implementer": "codex"},
            reasons=("The preferred team is unavailable; using the strongest safe fallback.",),
            constraints=constraints,
            max_iterations=2,
            status="warning",
        )

    if "deepseek" in available:
        return _decision(
            strategy="solo",
            roles={"implementer": "deepseek"},
            reasons=("Only the external workhorse is available; review must be manual.",),
            constraints=constraints,
            max_iterations=2,
            status="warning",
        )

    return _stop("No compatible agent is available.", "Enable codex or deepseek.")


def _codex_roles(complexity: str) -> dict[str, str]:
    if complexity == "complex":
        return {
            "planner": "codex",
            "implementer": "codex",
            "reviewer": "codex",
        }
    return {"implementer": "codex"}


def _first_available(preferred: tuple[str, ...], available: set[str]) -> str | None:
    return next((agent for agent in preferred if agent in available), None)


def _decision(
    *,
    strategy: Strategy,
    roles: dict[str, str],
    reasons: tuple[str, ...],
    constraints: list[str],
    max_iterations: int,
    status: Status = "success",
) -> RouteDecision:
    return RouteDecision(
        status=status,
        summary=f"Selected {strategy} route: "
        + ", ".join(f"{role}={agent}" for role, agent in roles.items()),
        strategy=strategy,
        roles=roles,
        reasons=reasons,
        constraints=tuple(constraints),
        next_actions=("Execute the route with the declared budget and stop conditions.",),
        max_iterations=max_iterations,
    )


def _stop(
    summary: str,
    next_action: str,
    *,
    constraints: list[str] | None = None,
) -> RouteDecision:
    return RouteDecision(
        status="error",
        summary=summary,
        strategy="stop",
        constraints=tuple(constraints or ()),
        next_actions=(next_action,),
    )
