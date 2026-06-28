"""Lightweight memory governance over the durable ICM lesson layer.

The old ``~/.paw`` store had a useful loop:

    observation -> repeated miss count -> proposal to rewrite/retire a lesson

This module keeps that loop as a small JSONL sidecar.  It does not mutate ICM
memories by itself; it produces bounded proposals for a human/agent curate pass.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from datetime import date
from pathlib import Path
from typing import Iterable


DEFAULT_MEMORY_ROOT = Path.home() / ".paw" / "memory"
OBSERVATIONS_FILE = "observations.jsonl"
PROPOSALS_FILE = "proposals.jsonl"


@dataclass
class Observation:
    sig: str
    count: int = 1
    first_seen: str = ""
    last_seen: str = ""
    lesson_id: str = ""
    linked_at_count: int = 0

    @property
    def post_link_misses(self) -> int:
        return max(0, self.count - self.linked_at_count)


@dataclass
class Proposal:
    id: str
    kind: str
    target_id: str
    action: str
    rationale: str
    evidence: dict
    created: str
    status: str = "pending"


@dataclass
class GovernanceResult:
    observations: list[Observation]
    proposals: list[Proposal]
    created: list[Proposal]

    def to_dict(self) -> dict:
        return {
            "observations": [asdict(o) for o in self.observations],
            "proposals": [asdict(p) for p in self.proposals],
            "created": [asdict(p) for p in self.created],
        }

    def render(self) -> str:
        if not self.created:
            return (
                f"memory governance: {len(self.observations)} observation(s), "
                f"{len(self.proposals)} proposal(s), no new proposals"
            )
        lines = [
            f"memory governance: created {len(self.created)} proposal(s) "
            f"from {len(self.observations)} observation(s)"
        ]
        for proposal in self.created:
            lines.append(
                f"  - {proposal.action} {proposal.target_id}: "
                f"{proposal.rationale[:120]}"
            )
        return "\n".join(lines)


def _today() -> str:
    return date.today().isoformat()


def _jsonl_path(root: Path, name: str) -> Path:
    return root / name


def _read_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []
    out: list[dict] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            item = json.loads(line)
        except ValueError:
            continue
        if isinstance(item, dict):
            out.append(item)
    return out


def _write_jsonl(path: Path, rows: Iterable[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    data = "".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in rows)
    path.write_text(data, encoding="utf-8")


def load_observations(root: Path | None = None) -> list[Observation]:
    root = root or DEFAULT_MEMORY_ROOT
    rows = _read_jsonl(_jsonl_path(root, OBSERVATIONS_FILE))
    return [
        Observation(
            sig=str(row.get("sig", "")),
            count=int(row.get("count", 1) or 1),
            first_seen=str(row.get("first_seen", "") or ""),
            last_seen=str(row.get("last_seen", "") or ""),
            lesson_id=str(row.get("lesson_id", "") or ""),
            linked_at_count=int(row.get("linked_at_count", 0) or 0),
        )
        for row in rows if row.get("sig")
    ]


def load_proposals(root: Path | None = None) -> list[Proposal]:
    root = root or DEFAULT_MEMORY_ROOT
    rows = _read_jsonl(_jsonl_path(root, PROPOSALS_FILE))
    return [
        Proposal(
            id=str(row.get("id", "")),
            kind=str(row.get("kind", "fix")),
            target_id=str(row.get("target_id", "")),
            action=str(row.get("action", "rewrite")),
            rationale=str(row.get("rationale", "")),
            evidence=dict(row.get("evidence", {}) or {}),
            created=str(row.get("created", "") or ""),
            status=str(row.get("status", "pending") or "pending"),
        )
        for row in rows if row.get("id")
    ]


def record_observation(
    sig: str,
    *,
    lesson_id: str = "",
    root: Path | None = None,
    today: str | None = None,
) -> Observation:
    """Upsert one miss observation.

    ``linked_at_count`` is the count at which this miss signature became linked
    to a lesson.  Later repeats become evidence that the lesson is ineffective.
    """
    root = root or DEFAULT_MEMORY_ROOT
    now = today or _today()
    observations = load_observations(root)
    for obs in observations:
        if obs.sig == sig:
            obs.count += 1
            obs.last_seen = now
            if lesson_id and not obs.lesson_id:
                obs.lesson_id = lesson_id
                obs.linked_at_count = obs.count
            _write_jsonl(_jsonl_path(root, OBSERVATIONS_FILE), (asdict(o) for o in observations))
            return obs
    obs = Observation(
        sig=sig,
        count=1,
        first_seen=now,
        last_seen=now,
        lesson_id=lesson_id,
        linked_at_count=1 if lesson_id else 0,
    )
    observations.append(obs)
    _write_jsonl(_jsonl_path(root, OBSERVATIONS_FILE), (asdict(o) for o in observations))
    return obs


def _proposal_id(obs: Observation, action: str) -> str:
    raw = f"{obs.lesson_id}|{obs.sig}|{action}".encode("utf-8")
    return hashlib.sha1(raw).hexdigest()[:12]


def build_proposals(
    observations: Iterable[Observation],
    existing: Iterable[Proposal] = (),
    *,
    threshold: int = 3,
    today: str | None = None,
) -> list[Proposal]:
    now = today or _today()
    existing_ids = {p.id for p in existing if p.status != "closed"}
    out: list[Proposal] = []
    for obs in observations:
        if not obs.lesson_id or obs.post_link_misses < threshold:
            continue
        action = "rewrite"
        pid = _proposal_id(obs, action)
        if pid in existing_ids:
            continue
        misses = obs.post_link_misses
        out.append(Proposal(
            id=pid,
            kind="fix",
            target_id=obs.lesson_id,
            action=action,
            rationale=(
                f"error '{obs.sig}' recurred {misses}x after lesson existed; "
                "rewrite or retire the lesson"
            ),
            evidence={
                "sig": obs.sig,
                "count": obs.count,
                "linked_at_count": obs.linked_at_count,
                "post_link_misses": misses,
                "last_seen": obs.last_seen,
            },
            created=now,
        ))
    return out


def run_governance(
    *,
    root: Path | None = None,
    threshold: int = 3,
    today: str | None = None,
    write: bool = True,
) -> GovernanceResult:
    root = root or DEFAULT_MEMORY_ROOT
    observations = load_observations(root)
    proposals = load_proposals(root)
    created = build_proposals(observations, proposals, threshold=threshold, today=today)
    if write and created:
        proposals = proposals + created
        _write_jsonl(_jsonl_path(root, PROPOSALS_FILE), (asdict(p) for p in proposals))
    return GovernanceResult(observations, proposals, created)
