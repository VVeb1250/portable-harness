"""Compiled, bounded graph index for skill routing.

The graph stays outside the agent context. Semantic retrieval finds a few
anchor nodes; deterministic traversal expands only one hop to related skills.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Literal, Sequence

from paw.skill_router import SkillRecord

NodeKind = Literal["skill", "intent"]
Relation = Literal["routes_to", "complements", "substitutes"]

_RELATIONS = frozenset({"routes_to", "complements", "substitutes"})


@dataclass(frozen=True)
class GraphNode:
    id: str
    kind: NodeKind
    text: str
    skill: SkillRecord | None = None

    def as_search_record(self) -> SkillRecord:
        if self.skill is not None:
            return self.skill
        return SkillRecord(
            name=self.id,
            description=self.text[:280],
            path="",
            routing_text=self.text,
        )


@dataclass(frozen=True)
class GraphEdge:
    source: str
    target: str
    relation: Relation


@dataclass(frozen=True)
class ExpandedSkill:
    skill: SkillRecord
    score: float
    via: str


class SkillGraph:
    """Immutable graph compiled from skill records and optional overlay data."""

    def __init__(
        self,
        nodes: dict[str, GraphNode],
        edges: Sequence[GraphEdge],
    ) -> None:
        self._nodes = dict(nodes)
        self._edges = tuple(edges)
        adjacency: dict[str, list[GraphEdge]] = {}
        for edge in self._edges:
            adjacency.setdefault(edge.source, []).append(edge)
            if edge.relation in {"complements", "substitutes"}:
                adjacency.setdefault(edge.target, []).append(
                    GraphEdge(edge.target, edge.source, edge.relation)
                )
        self._adjacency = {
            node: tuple(sorted(items, key=lambda edge: (edge.relation, edge.target)))
            for node, items in adjacency.items()
        }

    @classmethod
    def from_dict(
        cls,
        data: dict[str, object],
        skills: Sequence[SkillRecord],
    ) -> "SkillGraph":
        nodes = {
            skill.name: GraphNode(
                id=skill.name,
                kind="skill",
                text=skill.routing_text
                or f"{skill.name}. {skill.description}",
                skill=skill,
            )
            for skill in skills
        }

        raw_nodes = data.get("nodes", [])
        if isinstance(raw_nodes, list):
            for raw in raw_nodes:
                if not isinstance(raw, dict):
                    continue
                node_id = str(raw.get("id", "")).strip()
                kind = str(raw.get("kind", "")).strip()
                text = str(raw.get("text", "")).strip()
                if not node_id or kind != "intent" or not text:
                    continue
                nodes[node_id] = GraphNode(
                    id=node_id,
                    kind="intent",
                    text=text,
                )

        edges: list[GraphEdge] = []
        raw_edges = data.get("edges", [])
        if isinstance(raw_edges, list):
            for raw in raw_edges:
                if not isinstance(raw, dict):
                    continue
                source = str(raw.get("from", "")).strip()
                target = str(raw.get("to", "")).strip()
                relation = str(raw.get("relation", "")).strip()
                if (
                    source in nodes
                    and target in nodes
                    and relation in _RELATIONS
                ):
                    edges.append(
                        GraphEdge(
                            source=source,
                            target=target,
                            relation=relation,  # type: ignore[arg-type]
                        )
                    )

        edges.extend(_record_edges(skills, nodes))
        return cls(nodes, _dedupe_edges(edges))

    def search_records(self) -> tuple[SkillRecord, ...]:
        return tuple(
            self._nodes[node_id].as_search_record()
            for node_id in sorted(self._nodes)
        )

    def expand(
        self,
        anchor_scores: dict[str, float],
        *,
        max_hops: int = 1,
        max_nodes: int = 12,
    ) -> tuple[ExpandedSkill, ...]:
        """Traverse a bounded subgraph and return scored skill nodes only."""
        if not anchor_scores or max_hops < 0 or max_nodes < 1:
            return ()

        frontier = sorted(
            (
                (node_id, score, 0, node_id)
                for node_id, score in anchor_scores.items()
                if node_id in self._nodes
            ),
            key=lambda item: (-item[1], item[0]),
        )
        best_node_score: dict[str, float] = {}
        best_skill: dict[str, ExpandedSkill] = {}
        visited = 0

        while frontier and visited < max_nodes:
            node_id, score, depth, via = frontier.pop(0)
            if score <= best_node_score.get(node_id, -1.0):
                continue
            best_node_score[node_id] = score
            visited += 1
            node = self._nodes[node_id]
            if node.kind == "skill" and node.skill is not None:
                prior = best_skill.get(node.skill.name)
                candidate = ExpandedSkill(node.skill, score, via)
                if prior is None or candidate.score > prior.score:
                    best_skill[node.skill.name] = candidate

            if depth >= max_hops:
                continue
            for edge in self._adjacency.get(node_id, ()):
                if edge.relation == "substitutes":
                    continue
                propagated = score * (
                    0.96 if edge.relation == "routes_to" else 0.84
                )
                frontier.append(
                    (edge.target, propagated, depth + 1, node_id)
                )
            frontier.sort(key=lambda item: (-item[1], item[0]))

        ranked = sorted(
            best_skill.values(),
            key=lambda item: (-item.score, item.skill.name),
        )
        return tuple(self._collapse_substitutes(ranked))

    def _collapse_substitutes(
        self,
        ranked: Sequence[ExpandedSkill],
    ) -> list[ExpandedSkill]:
        blocked: set[str] = set()
        output: list[ExpandedSkill] = []
        for item in ranked:
            if item.skill.name in blocked:
                continue
            output.append(item)
            for edge in self._adjacency.get(item.skill.name, ()):
                if edge.relation == "substitutes":
                    blocked.add(edge.target)
        return output


def _record_edges(
    skills: Sequence[SkillRecord],
    nodes: dict[str, GraphNode],
) -> list[GraphEdge]:
    edges: list[GraphEdge] = []
    groups: dict[str, list[str]] = {}
    for skill in skills:
        for complement in skill.complements:
            if complement in nodes:
                edges.append(
                    GraphEdge(skill.name, complement, "complements")
                )
        if skill.substitute_group:
            groups.setdefault(skill.substitute_group, []).append(skill.name)
    for members in groups.values():
        ordered = sorted(members)
        for index, source in enumerate(ordered):
            for target in ordered[index + 1 :]:
                edges.append(GraphEdge(source, target, "substitutes"))
    return edges


def _dedupe_edges(edges: Iterable[GraphEdge]) -> tuple[GraphEdge, ...]:
    unique = {
        (edge.source, edge.target, edge.relation): edge for edge in edges
    }
    return tuple(unique[key] for key in sorted(unique))


def load_skill_graph(
    path: Path,
    skills: Sequence[SkillRecord],
) -> SkillGraph:
    """Load a versioned graph overlay and compile it against live skills."""
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        data = {}
    if not isinstance(data, dict):
        data = {}
    return SkillGraph.from_dict(data, skills)


def default_skill_graph_path() -> Path:
    """Return the bundled graph overlay path in source or installed layouts."""
    return Path(__file__).resolve().parent / "registry" / "skill_graph.json"
