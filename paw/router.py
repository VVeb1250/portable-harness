"""Deterministic, side-effect-free routing for agent work."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Literal

Complexity = Literal["auto", "simple", "complex"]
Risk = Literal["auto", "low", "medium", "high"]
Sensitivity = Literal["public", "private", "restricted"]
Status = Literal["success", "warning", "error"]
Strategy = Literal["solo", "team", "stop"]

DEFAULT_AGENTS = ("codex", "deepseek")
KNOWN_AGENTS = frozenset(DEFAULT_AGENTS)

_COMPLEX_TERMS = (
    "across",
    "architecture",
    "debug",
    "design",
    "migrate",
    "migration",
    "multiple",
    "refactor",
    "regression",
    "หลายไฟล์",
    "สถาปัตยกรรม",
)
_SECURITY_TERMS = (
    "api key",
    "auth",
    "credential",
    "permission",
    "secret",
    "security",
    "token",
    "vulnerability",
    "สิทธิ์",
    "รหัสลับ",
)
_DOC_TERMS = ("docs", "documentation", "readme", "typo", "เอกสาร", "สะกด")
_RESEARCH_TERMS = ("compare", "investigate", "research", "verify", "ค้นคว้า", "เปรียบเทียบ")


@dataclass(frozen=True)
class RouteRequest:
    task: str
    complexity: Complexity = "auto"
    risk: Risk = "auto"
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
    classification: dict[str, object] = field(default_factory=dict)
    confidence: float = 0.0
    estimated_cost_usd: float = 0.0

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


def route(request: RouteRequest) -> RouteDecision:
    """Return a conservative route without launching agents or touching config."""
    if not request.task.strip():
        return _stop("Task is empty.", "Provide a non-empty task.")
    if request.max_budget_usd is not None and request.max_budget_usd < 0:
        return _stop("Budget cannot be negative.", "Provide a non-negative budget.")

    available = set(request.available_agents) & KNOWN_AGENTS
    classification, confidence = _classify(request)
    complexity = str(classification["complexity"])
    risk = str(classification["risk"])
    constraints: list[str] = []
    if request.sensitivity == "restricted":
        constraints.append("privacy:restricted")

    if request.sensitivity == "restricted":
        if "codex" not in available:
            return _stop(
                "No privacy-safe agent is available.",
                "Make codex available or change the repository privacy policy.",
                constraints=constraints,
                classification=classification,
                confidence=confidence,
            )
        decision = _decision(
            strategy="team" if complexity == "complex" else "solo",
            roles=_codex_roles(complexity),
            reasons=(
                "Restricted work stays on the approved local/subscription seat.",
                "Risk and privacy override the cheaper external workhorse.",
            ),
            constraints=constraints,
            max_iterations=3 if complexity == "complex" else 1,
            classification=classification,
            confidence=confidence,
        )
        return _apply_budget(request, decision, available, risk)

    if complexity == "simple" and risk == "low":
        implementer = _first_available(("deepseek", "codex"), available)
        if implementer is None:
            return _stop(
                "No implementer is available.",
                "Enable codex or deepseek.",
                classification=classification,
                confidence=confidence,
            )
        decision = _decision(
            strategy="solo",
            roles={"implementer": implementer},
            reasons=("Simple low-risk work does not justify team coordination cost.",),
            constraints=constraints,
            max_iterations=1,
            classification=classification,
            confidence=confidence,
        )
        return _apply_budget(request, decision, available, risk)

    if {"codex", "deepseek"}.issubset(available):
        decision = _decision(
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
            classification=classification,
            confidence=confidence,
        )
        return _apply_budget(request, decision, available, risk)

    if "codex" in available:
        decision = _decision(
            strategy="solo",
            roles={"implementer": "codex"},
            reasons=("The preferred team is unavailable; using the strongest safe fallback.",),
            constraints=constraints,
            max_iterations=2,
            status="warning",
            classification=classification,
            confidence=confidence,
        )
        return _apply_budget(request, decision, available, risk)

    if "deepseek" in available:
        decision = _decision(
            strategy="solo",
            roles={"implementer": "deepseek"},
            reasons=("Only the external workhorse is available; review must be manual.",),
            constraints=constraints,
            max_iterations=2,
            status="warning",
            classification=classification,
            confidence=confidence,
        )
        return _apply_budget(request, decision, available, risk)

    return _stop(
        "No compatible agent is available.",
        "Enable codex or deepseek.",
        classification=classification,
        confidence=confidence,
    )


def _classify(request: RouteRequest) -> tuple[dict[str, object], float]:
    text = request.task.casefold()
    words = text.split()
    task_kind = "code"
    if _contains_any(text, _SECURITY_TERMS):
        task_kind = "security"
    elif _contains_any(text, _DOC_TERMS):
        task_kind = "docs"
    elif _contains_any(text, _RESEARCH_TERMS):
        task_kind = "research"

    complexity_score = sum(term in text for term in _COMPLEX_TERMS)
    if len(words) >= 25:
        complexity_score += 1
    if task_kind == "docs" and len(words) <= 12:
        complexity_score = 0

    inferred_complexity = "complex" if complexity_score >= 2 else "simple"
    complexity = (
        inferred_complexity if request.complexity == "auto" else request.complexity
    )

    if task_kind == "security" or "migration" in text or "migrate" in text:
        inferred_risk = "high"
    elif task_kind == "docs" and complexity == "simple":
        inferred_risk = "low"
    else:
        inferred_risk = "medium"
    risk = inferred_risk if request.risk == "auto" else request.risk

    auto_fields = int(request.complexity == "auto") + int(request.risk == "auto")
    confidence = 0.9 if auto_fields == 0 else 0.78
    if auto_fields and (task_kind != "code" or complexity_score >= 2):
        confidence = 0.86

    return (
        {
            "task_kind": task_kind,
            "complexity": complexity,
            "risk": risk,
            "complexity_score": complexity_score,
        },
        confidence,
    )


def _contains_any(text: str, terms: tuple[str, ...]) -> bool:
    return any(term in text for term in terms)


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
    classification: dict[str, object],
    confidence: float,
) -> RouteDecision:
    estimated_cost = _estimate_cost(roles)
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
        classification=classification,
        confidence=confidence,
        estimated_cost_usd=estimated_cost,
    )


def _estimate_cost(roles: dict[str, str]) -> float:
    agents = tuple(roles.values())
    if agents == ("deepseek",):
        return 0.05
    if agents == ("codex",):
        return 1.05
    if "deepseek" in agents and "codex" in agents:
        return 0.95
    if agents and set(agents) == {"codex"}:
        return 1.50
    return 0.0


def _apply_budget(
    request: RouteRequest,
    decision: RouteDecision,
    available: set[str],
    risk: str,
) -> RouteDecision:
    budget = request.max_budget_usd
    if budget is None or decision.estimated_cost_usd <= budget:
        return decision

    constraints = list(decision.constraints)
    constraints.append("budget:insufficient")
    if (
        request.sensitivity != "restricted"
        and risk in {"low", "medium"}
        and "deepseek" in available
        and budget >= 0.05
    ):
        constraints[-1] = "budget:degraded"
        return _decision(
            strategy="solo",
            roles={"implementer": "deepseek"},
            reasons=decision.reasons
            + ("Budget pressure removed planner/reviewer coordination.",),
            constraints=constraints,
            max_iterations=1,
            status="warning",
            classification=decision.classification,
            confidence=decision.confidence,
        )

    return _stop(
        (
            f"Budget ${budget:.2f} is below the safe route estimate "
            f"${decision.estimated_cost_usd:.2f}."
        ),
        "Raise the budget, reduce scope, or explicitly choose a safer available agent.",
        constraints=constraints,
        classification=decision.classification,
        confidence=decision.confidence,
    )


def _stop(
    summary: str,
    next_action: str,
    *,
    constraints: list[str] | None = None,
    classification: dict[str, object] | None = None,
    confidence: float = 0.0,
) -> RouteDecision:
    return RouteDecision(
        status="error",
        summary=summary,
        strategy="stop",
        constraints=tuple(constraints or ()),
        next_actions=(next_action,),
        classification=classification or {},
        confidence=confidence,
    )
