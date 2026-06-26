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
from paw.curate import curate as curate_pending
from paw.reflection import (
    capture as reflect_capture,
    load_watermark,
    save_watermark,
)
from paw.router import RouteRequest, route
from paw.semantic_router import default_semantic_scorer
from paw.skill_graph import default_skill_graph_path, load_skill_graph
from paw.skill_router import default_skill_roots, discover_skills, suggest_skill
from paw.sets.loader import SetsError, get_set, load_all
from paw.team_adapters import AdapterError, build_codex_deepseek_adapters
from paw.team_kernel import EvaluationResult, RoleOutput, TeamKernel, TeamKernelContext


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


def _mock_planner(context: TeamKernelContext) -> RoleOutput:
    return RoleOutput(
        content=(
            f"Plan iteration {context.iteration}: route {context.decision.strategy} "
            f"for task: {context.task}"
        )
    )


def _mock_implementer(context: TeamKernelContext) -> RoleOutput:
    return RoleOutput(
        content=(
            f"Result iteration {context.iteration}: mock implementation completed "
            "for the planned handoff."
        )
    )


def _mock_mutation_runner(context: TeamKernelContext) -> RoleOutput:
    latest = next(
        (entry for entry in reversed(context.entries) if entry.role == "implementer"),
        None,
    )
    source = latest.content if latest is not None else "implementation handoff"
    return RoleOutput(
        content=f"Mock patch artifact generated from: {source}",
        artifact=f"mock-patch-{context.iteration}.diff",
        importance="high",
    )


def _mock_reviewer(context: TeamKernelContext) -> RoleOutput:
    return RoleOutput(content="PASS: mock review accepted the implementation handoff.")


def _mock_evaluator(context: TeamKernelContext) -> EvaluationResult:
    return EvaluationResult(passed=True, summary="mock evaluator accepted the run")


def _team(args: argparse.Namespace) -> int:
    if args.team_action != "run":
        return 2
    adapter_profile = "mock" if args.mock else args.adapters

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
    guard = _guard_team_adapter_profile(adapter_profile, decision)
    if guard is not None:
        if args.json:
            print(json.dumps(guard, ensure_ascii=False, indent=2))
        else:
            print(guard["summary"], file=sys.stderr)
        return 1

    board = IcmBlackboard(database=Path(args.db) if args.db else None)
    if adapter_profile == "mock":
        planner = _mock_planner
        implementer = _mock_implementer
        mutation_runner = _mock_mutation_runner
        reviewer = _mock_reviewer
        evaluator = _mock_evaluator
    else:
        adapters = build_codex_deepseek_adapters(repo=Path.cwd())
        planner = adapters.planner
        implementer = adapters.implementer
        mutation_runner = None
        reviewer = adapters.reviewer
        evaluator = adapters.evaluator

    try:
        result = TeamKernel(
            project=args.project,
            run_id=args.run_id,
            blackboard=board,
            planner=planner,
            implementer=implementer,
            mutation_runner=mutation_runner,
            reviewer=reviewer,
            evaluator=evaluator,
        ).run(task=args.task, decision=decision)
    except AdapterError as error:
        payload = {
            "status": "error",
            "summary": str(error),
            "next_actions": [
                "Check adapter authentication/configuration, then retry with the same run id.",
            ],
        }
        if args.json:
            print(json.dumps(payload, ensure_ascii=False, indent=2))
        else:
            print(payload["summary"], file=sys.stderr)
        return 1

    if args.json:
        print(json.dumps(result.to_dict(), ensure_ascii=False, indent=2))
    else:
        print(result.summary)
        print(f"stop: {result.stopped_reason}")
        for action in result.next_actions:
            print(f"next: {action}")
    return 0 if result.status != "error" else 1


def _guard_team_adapter_profile(
    adapter_profile: str,
    decision,
) -> dict[str, object] | None:
    if decision.status == "error" or decision.strategy == "stop":
        return None
    if adapter_profile != "codex-deepseek":
        return None
    if "privacy:restricted" in decision.constraints:
        return {
            "status": "error",
            "summary": (
                "codex-deepseek is blocked for restricted work because it uses "
                "an external DeepSeek implementer."
            ),
            "next_actions": [
                "Use --adapters mock, lower sensitivity only after redaction, or add a local codex-only adapter.",
            ],
        }
    expected_roles = {
        "planner": "codex",
        "implementer": "deepseek",
        "reviewer": "codex",
    }
    if decision.strategy != "team" or decision.roles != expected_roles:
        return {
            "status": "error",
            "summary": (
                "codex-deepseek adapter profile does not match the selected route "
                f"roles: {decision.roles}."
            ),
            "next_actions": [
                "Use --adapters mock for smoke tests or choose a task/routing policy that selects the codex-deepseek team.",
            ],
        }
    return None


def _recall(args: argparse.Namespace) -> int:
    result = recall_memory(args.query, host=args.host, limit=args.limit)
    if args.json:
        print(json.dumps(result.to_dict(), ensure_ascii=False, indent=2))
    else:
        print(result.render())
    return 0


def _reflect(args: argparse.Namespace) -> int:
    """Capture mistake candidates → ICM pending. Hook-safe: always returns 0.

    Called by the Stop hook (stdin = ``{transcript_path, session_id}``) or
    directly with ``--transcript``. Capture never breaks the session end.
    """
    transcript, session_id = args.transcript, args.session_id or ""
    if not transcript:
        try:
            payload = json.load(sys.stdin)
            transcript = payload.get("transcript_path")
            session_id = session_id or payload.get("session_id", "")
        except (ValueError, OSError):
            payload = {}
    if not transcript and args.host == "codex":
        # Codex Stop stdin shape is unverified; fall back to the session's rollout
        from paw.reflection import newest_codex_transcript
        transcript = newest_codex_transcript(session_id) or None
    if not transcript:
        if not args.json:
            print("reflect: no transcript (pass --transcript or pipe the Stop-hook payload)")
        return 0
    # incremental: CC fires Stop per turn, so resume from the per-session watermark
    # (unless --full forces a full rescan). dry-run never advances the watermark.
    use_wm = bool(session_id) and not args.full
    start = load_watermark(session_id) if use_wm else 0
    result = reflect_capture(
        transcript, session_id=session_id, start_line=start,
        host=args.host, llm=args.llm, write=not args.dry_run,
    )
    if use_wm and not args.dry_run:
        save_watermark(session_id, result.next_line)
    if args.json:
        print(json.dumps(result.to_dict(), ensure_ascii=False, indent=2))
    else:
        print(result.render())
    return 0


def _curate(args: argparse.Namespace) -> int:
    """Reconcile ICM pending → wiki. Hook-safe (SessionStart): always returns 0.

    ``--surface`` is quiet when pending is empty (so the SessionStart shim adds
    nothing on a clean start) and never writes — it only previews what curation
    would do, leaving the apply to an explicit ``paw curate`` run.
    """
    result = curate_pending(write=not (args.dry_run or args.surface), limit=args.limit)
    if args.json:
        print(json.dumps(result.to_dict(), ensure_ascii=False, indent=2))
    else:
        out = result.render(surface=args.surface)
        if out:
            print(out)
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

    team = sub.add_parser(
        "team",
        help="run Team Kernel handoffs through the ICM-backed blackboard",
    )
    team_sub = team.add_subparsers(dest="team_action", required=True)
    team_run = team_sub.add_parser(
        "run",
        help="execute a bounded Team Kernel run",
    )
    team_run.add_argument("task")
    team_run.add_argument("--project", required=True)
    team_run.add_argument("--run-id", required=True)
    team_run.add_argument(
        "--complexity",
        choices=("auto", "simple", "complex"),
        default="auto",
    )
    team_run.add_argument(
        "--risk",
        choices=("auto", "low", "medium", "high"),
        default="auto",
    )
    team_run.add_argument(
        "--sensitivity",
        choices=("public", "private", "restricted"),
        default="private",
    )
    team_run.add_argument(
        "--available",
        nargs="+",
        default=("codex", "deepseek"),
        metavar="AGENT",
    )
    team_run.add_argument("--max-budget-usd", type=float)
    team_run.add_argument(
        "--adapters",
        choices=("mock", "codex-deepseek"),
        default="mock",
        help="role adapter profile; codex-deepseek may call external tools/APIs",
    )
    team_run.add_argument("--mock", action="store_true", help="alias for --adapters mock")
    team_run.add_argument("--db", help="ICM SQLite path; omit to use configured memory")
    team_run.add_argument("--json", action="store_true")

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

    reflect_p = sub.add_parser(
        "reflect",
        help="capture mistake candidates from a session transcript into ICM pending",
    )
    reflect_p.add_argument("--capture", action="store_true", help="capture mode (default action)")
    reflect_p.add_argument("--host", default="claude-code", choices=("claude-code", "codex"),
                           help="transcript format (claude-code JSONL vs codex rollout)")
    reflect_p.add_argument("--transcript", help="transcript JSONL path (else read Stop-hook stdin)")
    reflect_p.add_argument("--session-id", help="session id for the pending keyword tag")
    reflect_p.add_argument("--dry-run", action="store_true", help="scan + print, do not write ICM")
    reflect_p.add_argument("--full", action="store_true", help="ignore the per-session watermark; rescan the whole transcript")
    reflect_p.add_argument("--llm", action="store_true", help="add the opt-in DeepSeek silent-bug pass (needs DEEPSEEK_API_KEY; $/latency)")
    reflect_p.add_argument("--json", action="store_true")

    curate_p = sub.add_parser(
        "curate",
        help="reconcile ICM pending candidates into the wiki (add / bump recurrence)",
    )
    curate_p.add_argument("--surface", action="store_true", help="preview only, quiet when pending empty (SessionStart)")
    curate_p.add_argument("--dry-run", action="store_true", help="show decisions, do not write ICM")
    curate_p.add_argument("--limit", type=int, help="cap how many pending entries to process")
    curate_p.add_argument("--json", action="store_true")

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
    if args.group == "team":
        return _team(args)
    if args.group == "recall":
        return _recall(args)
    if args.group == "reflect":
        return _reflect(args)
    if args.group == "curate":
        return _curate(args)
    p.print_help()
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
