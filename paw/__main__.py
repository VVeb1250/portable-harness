"""`py -m paw ...` — thin CLI entrypoint.

Stdlib argparse, zero runtime deps for the read-path (sets list/show). The
write-path (`link`/`verify`) lands in the next increment once patcher/healthcheck
are lifted; it pulls in click + tomlkit (see pyproject `[cli]` extra).
"""

from __future__ import annotations

import argparse
import json
import sys

from paw.router import RouteRequest, route
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

    args = p.parse_args(argv)
    if args.group == "sets":
        if args.action == "list":
            return _sets_list()
        if args.action == "show":
            return _sets_show(args.name)
    if args.group == "route":
        return _route(args)
    p.print_help()
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
