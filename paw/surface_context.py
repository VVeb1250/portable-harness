"""Bounded task context for paw capability surfacing.

The surface router should not infer everything from the user's last sentence.
Hosts can pass a small capsule of what the agent is about to do: phase/intent,
active tool, recent files, changed files, or the command it is preparing.  This
module keeps that context compact and deterministic so hook output stays lean.
"""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass
from pathlib import Path

_WORD = re.compile(r"[^\W_]+", re.UNICODE)


@dataclass(frozen=True)
class SurfaceContext:
    task: str
    cwd: str | None = None
    intent: str | None = None
    phase: str | None = None
    active_tool: str | None = None
    last_command: str | None = None
    changed_files: tuple[str, ...] = ()
    recent_files: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, object]:
        return asdict(self)

    def routing_text(self) -> str:
        parts = [
            self.task,
            self.intent or "",
            self.phase or "",
            self.active_tool or "",
            self.last_command or "",
            " ".join(self.changed_files),
            " ".join(self.recent_files),
            " ".join(_file_terms((*self.changed_files, *self.recent_files))),
        ]
        return " ".join(part for part in parts if part).strip()


def build_surface_context(
    task: str,
    *,
    cwd: str | None = None,
    intent: str | None = None,
    phase: str | None = None,
    active_tool: str | None = None,
    last_command: str | None = None,
    changed_files: tuple[str, ...] | list[str] = (),
    recent_files: tuple[str, ...] | list[str] = (),
) -> SurfaceContext:
    """Normalize host-provided context into a stable, serializable capsule."""
    return SurfaceContext(
        task=" ".join(task.split())[:500],
        cwd=str(Path(cwd).resolve()) if cwd else None,
        intent=_clean(intent),
        phase=_clean(phase),
        active_tool=_clean(active_tool),
        last_command=_clean(last_command, limit=300),
        changed_files=tuple(_clean_file(path) for path in changed_files if path),
        recent_files=tuple(_clean_file(path) for path in recent_files if path),
    )


def infer_intents(context: SurfaceContext) -> frozenset[str]:
    """Return coarse intent labels used only as boosts, never as sole truth."""
    text = _normalize(context.routing_text())
    toks = set(_WORD.findall(text))
    intents: set[str] = set()

    if _has(text, "agent handoff", "handoff context", "package git diff", "current git diff") or (
        "handoff" in toks and ("diff" in toks or "context" in toks or "repo" in toks)
    ):
        intents.add("repo_handoff")
    if _has(text, "huge log", "large file", "bulk output", "context overflow", "without dumping", "failure log") or (
        ("log" in toks or "output" in toks) and ("huge" in toks or "large" in toks or "dumping" in toks)
    ):
        intents.add("bulk_context")
    if _has(text, "affected tests", "only tests", "run related tests", "test selection") or (
        "tests" in toks and ("affected" in toks or "related" in toks or "only" in toks)
    ):
        intents.add("affected_tests")
    if _has(text, "find all callers", "callers", "impact", "callees", "symbol graph"):
        intents.add("code_impact")
    if _has(text, "exact search", "matching lines", "find where", "where is", "find text"):
        intents.add("code_search")
    if _has(text, "latest api", "library docs", "api reference", "current docs", "context7", "deprecated"):
        intents.add("docs_lookup")
    if _has(text, "http api contract", "http contract", "api contract", "rest endpoint", "graphql"):
        intents.add("api_contract")
    if _has(text, "fill the login form", "click submit", "browser automation", "open a browser", "web form") or (
        "browser" in toks and ("click" in toks or "fill" in toks or "login" in toks or "submit" in toks)
    ):
        intents.add("browser_action")
    if _has(text, "ai slop", "design audit", "design fidelity", "touch target") or (
        ("frontend" in toks or "ui" in toks) and ("audit" in toks or "spacing" in toks or "polish" in toks)
    ):
        intents.add("ui_quality")
    if _has(text, "query csv", "sql query", "grouped counts", "structured data") or (
        ("csv" in toks or "parquet" in toks or "sqlite" in toks) and ("query" in toks or "sql" in toks)
    ):
        intents.add("data_query")
    if _has(text, "secret scan", "api key", "leaked", "dependency audit", "before commit") or (
        ("secret" in toks or "credential" in toks) and ("scan" in toks or "leak" in toks)
    ):
        intents.add("security_gate")
    if _has(text, "web page", "fetch url", "extract relevant content", "read article", "search web"):
        intents.add("web_research")

    if any(path.endswith(".py") for path in context.changed_files) and "tests" in toks:
        intents.add("affected_tests")
    if any(path.endswith((".csv", ".json", ".parquet", ".sqlite", ".db")) for path in context.recent_files):
        intents.add("data_query")
    if any(path.endswith((".docx", ".xlsx", ".pptx", ".pdf")) for path in context.recent_files):
        intents.add("doc_extract")
    return frozenset(intents)


def _clean(value: str | None, *, limit: int = 120) -> str | None:
    if value is None:
        return None
    cleaned = " ".join(str(value).split())[:limit]
    return cleaned or None


def _clean_file(value: str) -> str:
    return str(value).replace("\\", "/")[:220]


def _file_terms(paths: tuple[str, ...]) -> tuple[str, ...]:
    terms: list[str] = []
    for raw in paths:
        suffix = Path(raw).suffix.casefold()
        if suffix == ".py":
            terms.append("python change")
        elif suffix in {".ts", ".tsx", ".js", ".jsx", ".css"}:
            terms.append("frontend code")
        elif suffix in {".csv", ".parquet", ".sqlite", ".db"}:
            terms.append("structured data")
        elif suffix in {".docx", ".xlsx", ".pptx", ".pdf"}:
            terms.append("binary document")
        elif raw.replace("\\", "/").startswith(".github/workflows/"):
            terms.append("github actions workflow")
    return tuple(terms)


def _normalize(text: str) -> str:
    return " ".join(text.casefold().replace("_", " ").replace("-", " ").split())


def _has(text: str, *phrases: str) -> bool:
    return any(phrase in text for phrase in phrases)
