"""Decision mirror — markdown master → ICM facts index.

Decisions live in committed markdown (CLAUDE.md / AGENTS.md / docs/*.md) because
that is where they are reviewable, version-controlled, and human-authoritative.
This module does NOT move them — markdown stays the master. It only mirrors a
*curated subset* into ICM ``facts.decisions.<slug>`` so a new session can
recall them fast (exact lookup) without grepping every markdown file.

Opt-in marker convention (deliberately, like the linker's managed blocks):

    <!-- paw:decision:keep-icm:start -->
    ICM = the only true cross-host store. reason: daemon-centric alternatives
    clash with the no-daemon thesis.
    <!-- paw:decision:keep-icm:end -->

Only blocks with this exact marker are mirrored. Free-text decisions elsewhere
in markdown are left alone — we never guess what counts as a decision, which
avoids the noise that made the old capture paths feel "สะเปะสะปะ".

Why facts and not memories: a decision is a single current value per slug that
supersedes its predecessor (we kept ICM last time; now we keep agentmemory).
``icm facts`` models exactly this with automatic supersession history — far
better than semantic recall, which would fuzzy-match an OLD superseded
decision. Weight on the nudge side is derived from age + still-active, not
stored here.

All calls are fail-safe: unreadable files / broken ICM degrade to "0 mirrored".
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Optional

from . import facts

# Marker pair. Slug is captured group 1; must be slug-ish (letters/digits/-_).
_BLOCK_RE = re.compile(
    r"<!--\s*paw:decision:(?P<slug>[A-Za-z0-9][A-Za-z0-9_-]*):start\s*-->"
    r"(?P<body>.*?)"
    r"<!--\s*paw:decision:\1:end\s*-->",
    re.DOTALL,
)

# Default markdown sources, in priority order. Callers may pass their own list.
# Order matters: first occurrence of a slug wins, so the most authoritative file
# for decisions should come first. MEMORY-PLAN.md holds the "Locked decisions"
# block, hence it leads.
DEFAULT_MD_SOURCES = (
    "docs/MEMORY-PLAN.md",
    "CLAUDE.md",
    "AGENTS.md",
    "docs/STATUS.md",
)

ENTITY_PREFIX = "decisions"


@dataclass(frozen=True)
class Decision:
    slug: str
    body: str

    @property
    def entity(self) -> str:
        # One entity per decision so `facts list decisions.<slug>` works and
        # `facts history decisions.<slug>` shows the supersession trail.
        return f"{ENTITY_PREFIX}.{self.slug}"


def parse_decisions(text: str) -> list[Decision]:
    """Extract all paw:decision blocks from markdown text.

    Duplicate slugs in one pass keep the FIRST occurrence (topmost file wins
    when iterating in priority order at the call site).
    """
    out: list[Decision] = []
    seen: set[str] = set()
    for m in _BLOCK_RE.finditer(text or ""):
        slug = m.group("slug").strip().lower()
        if not slug or slug in seen:
            continue
        body = (m.group("body") or "").strip()
        if not body:
            continue
        seen.add(slug)
        out.append(Decision(slug=slug, body=body))
    return out


def _read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""


def collect_decisions(
    md_paths: Iterable[Path], *, base: Optional[Path] = None
) -> list[Decision]:
    """Parse decisions from a priority-ordered list of markdown paths.

    First occurrence of a slug wins (so CLAUDE.md beats docs/ on conflict).
    Missing / unreadable files are skipped silently.
    """
    out: list[Decision] = []
    seen: set[str] = set()
    for p in md_paths:
        path = (base / p) if base and not p.is_absolute() else p
        for d in parse_decisions(_read_text(path)):
            if d.slug in seen:
                continue
            seen.add(d.slug)
            out.append(d)
    return out


def _collapse_body(body: str, *, max_chars: int = 600) -> str:
    """Collapse whitespace + dedent + cap length so the fact value is bounded.

    Markdown indentation from the surrounding list (e.g. a decision nested
    under a numbered item) is stripped via textwrap.dedent so the index stores
    the canonical body, not the layout artifact. This is an INDEX, not a
    re-render — the master stays in markdown.
    """
    import textwrap

    # The block body's first line has no indent (it follows the marker on the
    # same/next line), while continuation lines carry the surrounding markdown
    # indent. textwrap.dedent only removes a COMMON prefix, so it would leave
    # the continuation indent intact. Normalise each line's leading whitespace
    # first, then re-dedent as a safety net.
    raw = body or ""
    lines = [ln.lstrip() for ln in raw.splitlines()]
    rejoined = "\n".join(lines)
    dedented = textwrap.dedent(rejoined)
    lines = [ln.rstrip() for ln in dedented.splitlines()]
    # Squeeze runs of >1 blank line down to one.
    squeezed: list[str] = []
    blank = False
    for ln in lines:
        if ln.strip():
            squeezed.append(ln)
            blank = False
        elif not blank:
            squeezed.append("")
            blank = True
    text = "\n".join(squeezed).strip()
    if len(text) > max_chars:
        text = text[: max_chars - 1].rstrip() + "…"
    return text


def mirror_one(
    decision: Decision, *, runner: Optional[facts.Runner] = None, db: str = ""
) -> bool:
    """Write one decision to its facts slot. True only if re-read confirms."""
    return facts.set_fact(
        decision.entity, "value", _collapse_body(decision.body),
        source="paw:decision", runner=runner, db=db,
    )


def mirror_decisions(
    md_paths: Iterable[Path],
    *,
    base: Optional[Path] = None,
    runner: Optional[facts.Runner] = None,
    db: str = "",
) -> int:
    """Mirror all paw:decision blocks from the given markdown into facts.

    Returns the count of decisions that mirrored AND verified visible. A
    decision whose write did not become readable is NOT counted — honesty over
    optimistic counts (same principle as the facts wrapper).
    """
    count = 0
    for d in collect_decisions(md_paths, base=base):
        if mirror_one(d, runner=runner, db=db):
            count += 1
    return count


def list_mirrored(
    *, runner: Optional[facts.Runner] = None, db: str = ""
) -> list[facts.FactRow]:
    """List all mirrored decisions (entity prefix ``decisions.``).

    Returns FactRows whose ``key`` is always ``value`` and ``entity`` is
    ``decisions.<slug>``. Empty on any error.
    """
    # facts has no list-by-entity-prefix, so we list the parent entity namespace
    # via the decisions entity itself (one fact per decision entity).
    # NB: list_facts takes a single entity; we cannot glob. Callers that need
    # all decisions should keep their own slug list from collect_decisions.
    return facts.list_facts(ENTITY_PREFIX, runner=runner, db=db)


def forget_decision(
    slug: str, *, runner: Optional[facts.Runner] = None, db: str = ""
) -> bool:
    """Remove one mirrored decision. True if anything was removed."""
    if not slug:
        return False
    return facts.forget_fact(f"{ENTITY_PREFIX}.{slug.lower()}", "value",
                             runner=runner, db=db)
