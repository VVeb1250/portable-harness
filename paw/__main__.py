"""`py -m paw ...` — thin CLI entrypoint.

Stdlib argparse, zero runtime deps for the read-path (sets list/show). The
write-path (`link`/`verify`) lands in the next increment once patcher/healthcheck
are lifted; it pulls in click + tomlkit (see pyproject `[cli]` extra).
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from paw.blackboard import (
    ENTRY_KINDS,
    BlackboardEntry,
    BlackboardResult,
    BlackboardScope,
    IcmBlackboard,
)
from paw.linker import LinkerError, apply_plan, build_plan, remove, verify
from paw.recall import recall as recall_memory
from paw.router import RouteRequest, route
from paw.semantic_router import default_semantic_scorer
from paw.skill_graph import default_skill_graph_path, load_skill_graph
from paw.skill_router import default_skill_roots, discover_skills, suggest_skill
from paw.sets.loader import SetsError, get_set, load_all


def _sets_list() -> int:
    for s in load_all():
        print(f"  {s.name:<18} mcp={s.mcp_count} non_mcp={len(s.non_mcp)}  — {s.description[:70]}")
    return 0


def _sets_show(name: str) -> int:
    try:
        s = get_set(name)
    except SetsError as e:
        print(f"error: {e}", file=sys.stderr)
        return 1
    print(f"{s.name}  (mcp={s.mcp_count}, non_mcp={len(s.non_mcp)})")
    print(s.description)
    if s.trigger_terms:
        print(f"\ntrigger: {', '.join(s.trigger_terms)}")
    if s.mcp:
        print("\nMCP:")
        for m in s.mcp:
            print(f"  - {m['tool']} ({m.get('ref', '?')})")
    if s.non_mcp:
        print("\nnon-MCP:")
        for m in s.non_mcp:
            print(f"  - {m['tool']} ({m.get('ref', '?')})")
    return 0


def _route(args: argparse.Namespace) -> int:
    decision = route(
        RouteRequest(
            task=args.task,
            complexity=args.complexity,
            risk=args.risk,
            sensitivity=args.sensitivity,
            available_agents=tuple(args.available),
            max_budget_usd=args.max_budget_usd,
        )
    )
    if args.json:
        print(json.dumps(decision.to_dict(), ensure_ascii=False, indent=2))
    else:
        print(decision.summary)
        for label, values in (
            ("reasons", decision.reasons),
            ("constraints", decision.constraints),
        ):
            if values:
                print(f"{label}:")
                for value in values:
                    print(f"  - {value}")
    return 0 if decision.status != "error" else 1


def _suggest(args: argparse.Namespace) -> int:
    roots = (
        tuple(Path(root) for root in args.skills_root)
        if args.skills_root
        else default_skill_roots()
    )
    skills = discover_skills(roots)
    graph = load_skill_graph(default_skill_graph_path(), skills)
    result = suggest_skill(
        args.task,
        skills,
        active_skills=tuple(args.active_skill),
        max_suggestions=args.max_suggestions,
        semantic_scorer=default_semantic_scorer(),
        graph=graph,
    )
    if args.json:
        print(json.dumps(result.to_dict(), ensure_ascii=False, indent=2))
    elif result.suggestions:
        print("shadow skill suggestions:")
        for suggestion in result.suggestions:
            print(f"  - {suggestion.skill}: {suggestion.reason}")
            print(f"    pull: {suggestion.skill_path}")
    elif result.candidates:
        print("shadow skill candidates (agent must verify):")
        for candidate in result.candidates:
            print(f"  - {candidate.skill}: {candidate.description}")
            print(f"    score: {candidate.retrieval_score:.3f}")
            print(f"    consider: {candidate.skill_path}")
    else:
        print(f"shadow: silent ({result.reason})")
    return 0


def _print_blackboard_result(result: BlackboardResult, as_json: bool) -> int:
    if as_json:
        print(json.dumps(result.to_dict(), ensure_ascii=False, indent=2))
    else:
        print(result.summary)
        for entry in result.entries:
            print(f"[{entry.kind}] {entry.role}: {entry.content}")
            if entry.artifact:
                print(f"  artifact: {entry.artifact}")
        if result.next_actions:
            print("next:")
            for action in result.next_actions:
                print(f"  - {action}")
    return 0 if result.status != "error" else 1


def _blackboard(args: argparse.Namespace) -> int:
    board = IcmBlackboard(database=Path(args.db) if args.db else None)
    scope = BlackboardScope(project=args.project, run_id=args.run_id)
    if args.blackboard_action == "write":
        result = board.write(
            scope,
            BlackboardEntry(
                role=args.role,
                kind=args.kind,
                content=args.content,
                artifact=args.artifact,
                importance=args.importance,
            ),
        )
        return _print_blackboard_result(result, args.json)
    result = board.read(
        scope,
        query=args.query,
        role=args.role,
        kind=args.kind,
        limit=args.limit,
    )
    return _print_blackboard_result(result, args.json)


def _recall(args: argparse.Namespace) -> int:
    result = recall_memory(args.query, host=args.host, limit=args.limit)
    if args.json:
        print(json.dumps(result.to_dict(), ensure_ascii=False, indent=2))
    else:
        print(result.render())
    return 0


def _print_tx(result, as_json: bool) -> int:
    if as_json:
        print(json.dumps(result.to_dict(), ensure_ascii=False, indent=2))
        return 0 if result.status in ("ok", "blocked") else 1
    print(result.summary)
    for check in getattr(result, "checks", ()):
        print(f"  · {check}")
    if result.backup:
        print(f"  backup: {result.backup}")
    for action in result.next_actions:
        print(f"  next: {action}")
    return 0 if result.status in ("ok", "blocked") else 1


def _linker(args: argparse.Namespace) -> int:
    try:
        if args.group == "plan":
            plan = build_plan(
                args.set, args.host, context=args.context, scope=args.scope
            )
            if args.json:
                print(json.dumps(plan.to_dict(), ensure_ascii=False, indent=2))
            else:
                print(plan.summary)
                for action in plan.actions:
                    flag = " (needs approval)" if action.requires_approval else ""
                    print(f"  [{action.kind}] {action.summary}{flag}")
                for warning in plan.warnings:
                    print(f"  ! {warning}")
            return 0 if plan.status == "ok" else 1
        if args.group == "apply":
            plan = build_plan(
                args.set, args.host, context=args.context, scope=args.scope
            )
            return _print_tx(apply_plan(plan), args.json)
        if args.group == "verify":
            return _print_tx(
                verify(args.set, host=args.host, context=args.context), args.json
            )
        if args.group == "remove":
            return _print_tx(
                remove(args.set, host=args.host, context=args.context), args.json
            )
    except (SetsError, LinkerError) as e:
        print(f"error: {e}", file=sys.stderr)
        return 1
    return 2


def _add_linker_args(parser: argparse.ArgumentParser, *, with_scope: bool) -> None:
    parser.add_argument("set")
    parser.add_argument("--host", default="claude-code")
    parser.add_argument("--context", help="path to the host context file (default: detect by host)")
    if with_scope:
        parser.add_argument("--scope", default="project", choices=("project", "user"))
    parser.add_argument("--json", action="store_true")


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="paw",
                                description="port-a-whip (paw) — curated cross-host agent harness")
    sub = p.add_subparsers(dest="group", required=True)

    sets = sub.add_parser("sets", help="list / inspect curated sets")
    sets_sub = sets.add_subparsers(dest="action", required=True)
    sets_sub.add_parser("list", help="list curated sets")
    show = sets_sub.add_parser("show", help="show one set: tools + token profile")
    show.add_argument("name")

    router = sub.add_parser("route", help="choose an agent route without launching it")
    router.add_argument("task")
    router.add_argument(
        "--complexity",
        choices=("auto", "simple", "complex"),
        default="auto",
    )
    router.add_argument(
        "--risk",
        choices=("auto", "low", "medium", "high"),
        default="auto",
    )
    router.add_argument(
        "--sensitivity",
        choices=("public", "private", "restricted"),
        default="private",
    )
    router.add_argument(
        "--available",
        nargs="+",
        default=("codex", "deepseek"),
        metavar="AGENT",
    )
    router.add_argument("--max-budget-usd", type=float)
    router.add_argument("--json", action="store_true")

    suggest = sub.add_parser(
        "suggest",
        help="shadow-mode PUSH discovery with explicit PULL handoff",
    )
    suggest.add_argument("task")
    suggest.add_argument(
        "--skills-root",
        action="append",
        default=[],
        help="catalog root containing */SKILL.md; may be repeated",
    )
    suggest.add_argument(
        "--active-skill",
        action="append",
        default=[],
        help="suppress a skill already active in the task; may be repeated",
    )
    suggest.add_argument(
        "--max-suggestions",
        type=int,
        choices=(1, 2),
        default=2,
    )
    suggest.add_argument("--json", action="store_true")

    blackboard = sub.add_parser(
        "blackboard",
        help="share explicit team state through an ICM-backed blackboard",
    )
    blackboard_sub = blackboard.add_subparsers(
        dest="blackboard_action",
        required=True,
    )
    write = blackboard_sub.add_parser("write", help="share one bounded entry")
    write.add_argument("--project", required=True)
    write.add_argument("--run-id", required=True)
    write.add_argument("--role", required=True)
    write.add_argument("--kind", choices=sorted(ENTRY_KINDS), required=True)
    write.add_argument("--content", required=True)
    write.add_argument("--artifact")
    write.add_argument(
        "--importance",
        choices=("critical", "high", "medium", "low"),
        default="medium",
    )
    write.add_argument("--db", help="ICM SQLite path; omit to use configured memory")
    write.add_argument("--json", action="store_true")

    read = blackboard_sub.add_parser("read", help="recall bounded entries")
    read.add_argument("--project", required=True)
    read.add_argument("--run-id", required=True)
    read.add_argument("--query", default="blackboard")
    read.add_argument("--role")
    read.add_argument("--kind", choices=sorted(ENTRY_KINDS))
    read.add_argument("--limit", type=int, default=10)
    read.add_argument("--db", help="ICM SQLite path; omit to use configured memory")
    read.add_argument("--json", action="store_true")

    recall_p = sub.add_parser(
        "recall",
        help="pull relevant memory: ICM shared brain + host committed conventions",
    )
    recall_p.add_argument("query")
    recall_p.add_argument(
        "--host",
        default="claude-code",
        choices=("claude-code", "codex", "gemini"),
    )
    recall_p.add_argument("--limit", type=int, default=5)
    recall_p.add_argument("--json", action="store_true")

    plan_p = sub.add_parser("plan", help="preview wiring a CLI set into a host (no mutation)")
    _add_linker_args(plan_p, with_scope=True)
    apply_p = sub.add_parser("apply", help="wire a CLI set into a host (drift-guarded, backed up)")
    _add_linker_args(apply_p, with_scope=True)
    verify_p = sub.add_parser("verify", help="check a linked set's health")
    _add_linker_args(verify_p, with_scope=False)
    remove_p = sub.add_parser("remove", help="unlink a set (strip only paw-owned block)")
    _add_linker_args(remove_p, with_scope=False)

    args = p.parse_args(argv)
    if args.group in ("plan", "apply", "verify", "remove"):
        return _linker(args)
    if args.group == "sets":
        if args.action == "list":
            return _sets_list()
        if args.action == "show":
            return _sets_show(args.name)
    if args.group == "route":
        return _route(args)
    if args.group == "suggest":
        return _suggest(args)
    if args.group == "blackboard":
        return _blackboard(args)
    if args.group == "recall":
        return _recall(args)
    p.print_help()
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
