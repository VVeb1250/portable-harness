"""`py -m paw ...` — thin CLI entrypoint.

Stdlib argparse, zero runtime deps for the read-path (sets list/show). The
write-path (`link`/`verify`) lands in the next increment once patcher/healthcheck
are lifted; it pulls in click + tomlkit (see pyproject `[cli]` extra).
"""

from __future__ import annotations

import argparse
import sys

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


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="paw",
                                description="port-a-whip (paw) — curated cross-host agent harness")
    sub = p.add_subparsers(dest="group", required=True)

    sets = sub.add_parser("sets", help="list / inspect curated sets")
    sets_sub = sets.add_subparsers(dest="action", required=True)
    sets_sub.add_parser("list", help="list curated sets")
    show = sets_sub.add_parser("show", help="show one set: tools + token profile")
    show.add_argument("name")

    args = p.parse_args(argv)
    if args.group == "sets":
        if args.action == "list":
            return _sets_list()
        if args.action == "show":
            return _sets_show(args.name)
    p.print_help()
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
