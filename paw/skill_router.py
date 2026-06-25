"""Context-lean PUSH discovery with explicit PULL handoff.

The routing engine is deliberately model-agnostic. A multilingual semantic
backend may retrieve candidates from full skill text, while deterministic
routing-card constraints decide whether a candidate is eligible. Only IDs,
paths, and concise evidence leave this module; skill bodies remain outside the
agent context until the agent explicitly pulls one.
"""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Callable, Iterable, Literal, Sequence

if TYPE_CHECKING:
    from paw.skill_graph import SkillGraph

SuggestionStatus = Literal["suggested", "candidates", "silent"]
MatchLevel = Literal["clear", "candidate", "none"]
SemanticScorer = Callable[[str, Sequence["SkillRecord"]], dict[str, float]]
Reranker = Callable[[str, Sequence["SkillRecord"]], dict[str, float]]

_TOKEN_RE = re.compile(r"[^\W_]+", re.UNICODE)
_GENERIC_TOKENS = frozenset(
    {
        "a",
        "an",
        "and",
        "for",
        "in",
        "of",
        "on",
        "the",
        "to",
        "use",
        "using",
        "with",
    }
)
_SEMANTIC_RETRIEVAL_FLOOR = 0.40
_LEXICAL_RETRIEVAL_FLOOR = 0.40
_RERANK_CLEAR = 0.72
_DUPLICATE_JACCARD = 0.66
_MAX_SUGGESTIONS = 2
_MAX_CANDIDATES = 3
_MAX_ANCHORS = 6
_MAX_ROUTING_TEXT = 32 * 1024


@dataclass(frozen=True)
class TaskCapsule:
    goal: str

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


@dataclass(frozen=True)
class SkillRecord:
    name: str
    description: str
    path: str
    routing_text: str = ""
    requires_evidence: tuple[str, ...] = ()
    excludes_evidence: tuple[str, ...] = ()
    complements: tuple[str, ...] = ()
    substitute_group: str | None = None


@dataclass(frozen=True)
class SkillMatch:
    skill: str
    skill_path: str
    reason: str
    confidence: float
    action: Literal["load_skill"] = "load_skill"


@dataclass(frozen=True)
class SkillCandidate:
    skill: str
    description: str
    skill_path: str
    retrieval_score: float
    action: Literal["consider_skill"] = "consider_skill"


@dataclass(frozen=True)
class SkillSuggestionResult:
    status: SuggestionStatus
    mode: Literal["shadow"]
    match: MatchLevel
    suggestions: tuple[SkillMatch, ...]
    candidates: tuple[SkillCandidate, ...]
    reason: str
    capsule: TaskCapsule

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


@dataclass(frozen=True)
class _ScoredSkill:
    record: SkillRecord
    score: float
    source: Literal["semantic", "lexical", "hybrid"]
    tokens: frozenset[str]


def build_task_capsule(task: str) -> TaskCapsule:
    """Keep raw multilingual intent bounded; do not translate with word lists."""
    return TaskCapsule(goal=" ".join(task.split())[:240])


def suggest_skill(
    task: str,
    skills: Sequence[SkillRecord],
    *,
    active_skills: Iterable[str] = (),
    max_suggestions: int = _MAX_SUGGESTIONS,
    max_candidates: int = _MAX_CANDIDATES,
    semantic_scorer: SemanticScorer | None = None,
    reranker: Reranker | None = None,
    graph: "SkillGraph | None" = None,
) -> SkillSuggestionResult:
    """Return clear PUSH hints only; skill content remains an explicit PULL."""
    capsule = build_task_capsule(task)
    active = {name.casefold() for name in active_skills}
    eligible = tuple(
        skill
        for skill in skills
        if skill.name.casefold() not in active
        and _evidence_allows(capsule.goal, skill)
    )
    if not eligible:
        return _silent(capsule, "no eligible skill after routing-card filters")

    search_records = graph.search_records() if graph is not None else eligible
    semantic = _semantic_scores(
        capsule.goal,
        search_records,
        semantic_scorer,
    )
    if graph is not None and semantic:
        retrieved = _retrieve_from_graph(graph, semantic, eligible)
    else:
        retrieved = _retrieve_direct(capsule.goal, eligible, semantic)
    if not retrieved:
        return _silent(capsule, "no strong graph or skill anchor")

    candidate_limit = max(1, min(max_candidates, _MAX_CANDIDATES))
    retrieved = retrieved[:candidate_limit]
    candidates = _candidate_output(retrieved)
    if reranker is None:
        return SkillSuggestionResult(
            status="candidates",
            mode="shadow",
            match="candidate",
            suggestions=(),
            candidates=candidates,
            reason=(
                "bounded graph retrieval only; agent must compare compact "
                "candidate cards before PULL"
            ),
            capsule=capsule,
        )

    reranked = _rerank(capsule.goal, retrieved, reranker)
    clear = [item for item in reranked if item.score >= _RERANK_CLEAR]
    if not clear:
        return _candidates(capsule, candidates, "reranker found no clear match")

    selected = _select_set(clear, max_suggestions)
    if not selected:
        return _candidates(capsule, candidates, "ambiguous overlapping matches")

    matches = tuple(
        SkillMatch(
            skill=item.record.name,
            skill_path=item.record.path,
            reason="clear reranked relevance; agent must verify before PULL",
            confidence=round(min(item.score, 0.99), 3),
        )
        for item in selected
    )
    return SkillSuggestionResult(
        status="suggested",
        mode="shadow",
        match="clear",
        suggestions=matches,
        candidates=(),
        reason=f"{len(matches)} clear complementary match(es)",
        capsule=capsule,
    )


def _retrieve_direct(
    task: str,
    eligible: Sequence[SkillRecord],
    semantic: dict[str, float],
) -> list[_ScoredSkill]:
    task_tokens = _tokens(task) - _GENERIC_TOKENS
    retrieved = [
        candidate
        for skill in eligible
        if (candidate := _score(skill, task_tokens, semantic)).score
        >= _retrieval_floor(candidate.source)
    ]
    retrieved.sort(key=lambda item: (-item.score, item.record.name))
    return retrieved


def _retrieve_from_graph(
    graph: "SkillGraph",
    semantic: dict[str, float],
    eligible: Sequence[SkillRecord],
) -> list[_ScoredSkill]:
    top = max(semantic.values(), default=0.0)
    floor = max(_SEMANTIC_RETRIEVAL_FLOOR, top * 0.72)
    anchors = dict(
        sorted(
            (
                (node_id, score)
                for node_id, score in semantic.items()
                if score >= floor
            ),
            key=lambda item: (-item[1], item[0]),
        )[:_MAX_ANCHORS]
    )
    allowed = {skill.name for skill in eligible}
    expanded = graph.expand(anchors, max_hops=1, max_nodes=12)
    return [
        _ScoredSkill(
            record=item.skill,
            score=item.score,
            source="semantic",
            tokens=_tokens(item.skill.routing_text),
        )
        for item in expanded
        if item.skill.name in allowed
    ]


def discover_skills(roots: Sequence[Path]) -> tuple[SkillRecord, ...]:
    """Read routing metadata and bounded full text outside the agent context."""
    found: dict[str, SkillRecord] = {}
    for root in roots:
        try:
            files = sorted(root.rglob("SKILL.md"))
        except OSError:
            continue
        for skill_file in files:
            document = _read_skill_document(skill_file)
            name = document["metadata"].get("name", "").strip()
            description = document["metadata"].get("description", "").strip()
            if not name or not description or name.casefold() in found:
                continue
            try:
                resolved = str(skill_file.resolve())
            except OSError:
                resolved = str(skill_file)
            metadata = document["metadata"]
            found[name.casefold()] = SkillRecord(
                name=name,
                description=description,
                path=resolved,
                routing_text=document["routing_text"],
                requires_evidence=_csv(metadata.get("routing_requires", "")),
                excludes_evidence=_csv(metadata.get("routing_excludes", "")),
                complements=_csv(metadata.get("routing_complements", "")),
                substitute_group=metadata.get("routing_group") or None,
            )
    return tuple(found[key] for key in sorted(found))


def default_skill_roots(cwd: Path | None = None) -> tuple[Path, ...]:
    base = cwd or Path.cwd()
    home = Path.home()
    return (
        base / ".agents" / "skills",
        home / ".codex" / "skills",
        home / ".agents" / "skills",
    )


def _semantic_scores(
    task: str,
    skills: Sequence[SkillRecord],
    scorer: SemanticScorer | None,
) -> dict[str, float]:
    if scorer is None:
        return {}
    try:
        raw = scorer(task, skills)
    except Exception:
        return {}
    return {
        str(name): max(0.0, min(float(score), 1.0))
        for name, score in raw.items()
        if isinstance(name, str)
    }


def _rerank(
    task: str,
    retrieved: Sequence[_ScoredSkill],
    reranker: Reranker,
) -> list[_ScoredSkill]:
    records = tuple(item.record for item in retrieved)
    scores = _semantic_scores(task, records, reranker)
    output = [
        _ScoredSkill(
            record=item.record,
            score=scores.get(item.record.name, 0.0),
            source="semantic",
            tokens=item.tokens,
        )
        for item in retrieved
    ]
    output.sort(key=lambda item: (-item.score, item.record.name))
    return output


def _score(
    skill: SkillRecord,
    task_tokens: frozenset[str],
    semantic_scores: dict[str, float],
) -> _ScoredSkill:
    skill_tokens = _tokens(
        skill.routing_text or f"{skill.name}. {skill.description}"
    ) - _GENERIC_TOKENS
    overlap = task_tokens & skill_tokens
    lexical = len(overlap) / max(1, min(len(task_tokens), len(skill_tokens)))
    if _normalize(skill.description) in _normalize(" ".join(task_tokens)):
        lexical = min(1.0, lexical + 0.12)

    semantic = semantic_scores.get(skill.name, 0.0)
    if semantic and lexical:
        score = 0.82 * semantic + 0.18 * lexical
        source: Literal["semantic", "lexical", "hybrid"] = "hybrid"
    elif semantic:
        score = semantic
        source = "semantic"
    else:
        score = lexical
        source = "lexical"
    return _ScoredSkill(
        record=skill,
        score=score,
        source=source,
        tokens=skill_tokens,
    )


def _select_set(
    scored: Sequence[_ScoredSkill],
    max_suggestions: int,
) -> tuple[_ScoredSkill, ...]:
    limit = max(1, min(max_suggestions, _MAX_SUGGESTIONS))
    first = scored[0]
    if len(scored) >= 2 and _ambiguous_substitutes(first, scored[1]):
        return ()

    selected = [first]
    for candidate in scored[1:]:
        if any(_ambiguous_substitutes(candidate, prior) for prior in selected):
            continue
        if not _complementary(candidate, selected[0]):
            continue
        selected.append(candidate)
        if len(selected) == limit:
            break
    return tuple(selected)


def _evidence_allows(task: str, skill: SkillRecord) -> bool:
    normalized = _normalize(task)
    if skill.requires_evidence and not any(
        _normalize(term) in normalized for term in skill.requires_evidence
    ):
        return False
    if any(_normalize(term) in normalized for term in skill.excludes_evidence):
        return False
    return True


def _ambiguous_substitutes(left: _ScoredSkill, right: _ScoredSkill) -> bool:
    if (
        left.record.substitute_group
        and left.record.substitute_group == right.record.substitute_group
    ):
        return True
    union = left.tokens | right.tokens
    similarity = len(left.tokens & right.tokens) / max(1, len(union))
    return similarity >= _DUPLICATE_JACCARD


def _complementary(candidate: _ScoredSkill, first: _ScoredSkill) -> bool:
    if candidate.record.name in first.record.complements:
        return True
    if first.record.name in candidate.record.complements:
        return True
    union = candidate.tokens | first.tokens
    similarity = len(candidate.tokens & first.tokens) / max(1, len(union))
    return similarity < 0.45


def _retrieval_floor(source: str) -> float:
    if source in {"semantic", "hybrid"}:
        return _SEMANTIC_RETRIEVAL_FLOOR
    return _LEXICAL_RETRIEVAL_FLOOR


def _candidate_output(
    retrieved: Sequence[_ScoredSkill],
) -> tuple[SkillCandidate, ...]:
    return tuple(
        SkillCandidate(
            skill=item.record.name,
            description=item.record.description[:160],
            skill_path=item.record.path,
            retrieval_score=round(min(item.score, 0.99), 3),
        )
        for item in retrieved
    )


def _candidates(
    capsule: TaskCapsule,
    candidates: tuple[SkillCandidate, ...],
    reason: str,
) -> SkillSuggestionResult:
    return SkillSuggestionResult(
        status="candidates",
        mode="shadow",
        match="candidate",
        suggestions=(),
        candidates=candidates,
        reason=reason,
        capsule=capsule,
    )


def _silent(capsule: TaskCapsule, reason: str) -> SkillSuggestionResult:
    return SkillSuggestionResult(
        status="silent",
        mode="shadow",
        match="none",
        suggestions=(),
        candidates=(),
        reason=reason,
        capsule=capsule,
    )


def _read_skill_document(path: Path) -> dict[str, object]:
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return {"metadata": {}, "routing_text": ""}

    metadata: dict[str, str] = {}
    body = text
    if text.startswith("---"):
        parts = text.split("---", 2)
        if len(parts) == 3:
            body = parts[2]
            for line in parts[1].splitlines()[:80]:
                key, separator, value = line.partition(":")
                if separator:
                    metadata[key.strip()] = value.strip().strip("\"'")

    routing_text = (
        f"{metadata.get('name', '')}. {metadata.get('description', '')}\n{body}"
    )[:_MAX_ROUTING_TEXT]
    return {"metadata": metadata, "routing_text": routing_text}


def _csv(value: str) -> tuple[str, ...]:
    return tuple(part.strip() for part in value.split(",") if part.strip())


def _tokens(text: str) -> frozenset[str]:
    return frozenset(_TOKEN_RE.findall(_normalize(text)))


def _normalize(text: str) -> str:
    return " ".join(text.casefold().replace("-", " ").split())
