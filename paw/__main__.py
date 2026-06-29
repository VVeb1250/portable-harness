"""`py -m paw ...` — thin CLI entrypoint.

Stdlib argparse, zero runtime deps for the read-path (sets list/show). The
write-path (`link`/`verify`) lands in the next increment once patcher/healthcheck
are lifted; it pulls in click + tomlkit (see pyproject `[cli]` extra).
"""

from __future__ import annotations

import argparse
import json
import shlex
import sys
from pathlib import Path

from paw.blackboard import (
    ENTRY_KINDS,
    BlackboardEntry,
    BlackboardResult,
    BlackboardScope,
    IcmBlackboard,
)
from paw.codebase_memory import (
    codebase_memory_project_name,
    format_search_output,
    parse_search_output,
    require_binary,
    run_codebase_memory_tool,
)
from paw.linker import LinkerError, apply_plan, build_plan, remove, verify
from paw.memory_hook import (
    build_config,
    hook_stdout,
    install_memory_hooks,
    load_hook_payload,
    run_memory_hook,
)
from paw.memory_governance import record_observation, run_governance
from paw.memory_mesh import MemoryMesh, MeshResult, MeshScope
from paw.recall import recall as recall_memory
from paw.curate import curate as curate_pending
from paw.doctor import render_report, run_doctor
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
from paw.surface_audit import (
    build_surface_decision,
    default_audit_path,
    summarize_surface_audit,
    write_surface_audit,
)
from paw.team_adapters import (
    AdapterError,
    build_codex_deepseek_adapters,
    make_mutation_runner,
)
from paw.team_kernel import EvaluationResult, RoleOutput, TeamKernel, TeamKernelContext
from paw.verification import make_verification_evaluator
from paw.zcode import setup_zcode


def _sets_list() -> int:
    for s in load_all():
        init = "init" if s.default_init else "opt"
        print(
            f"  {s.name:<18} {init:<4} scope={s.link_scope:<11} "
            f"bench={s.bench_status:<12} mcp={s.mcp_count} non_mcp={len(s.non_mcp)}  "
            f"— {s.description[:60]}"
        )
    return 0


def _sets_show(name: str) -> int:
    try:
        s = get_set(name)
    except SetsError as e:
        print(f"error: {e}", file=sys.stderr)
        return 1
    print(
        f"{s.name}  (mcp={s.mcp_count}, non_mcp={len(s.non_mcp)}, "
        f"scope={s.link_scope}, default_init={str(s.default_init).lower()})"
    )
    print(s.description)
    print(
        f"\nstatus: catalog={s.catalog_status} · tier={s.foundation_tier} · "
        f"bench={s.bench_status}"
    )
    if s.token_tax:
        idle = s.token_tax.get("idle_mcp", "?")
        runtime = s.token_tax.get("runtime_output", "?")
        print(f"token_tax: idle_mcp={idle} · runtime_output={runtime}")
    if s.platforms:
        platform_bits = " · ".join(f"{name}={support}" for name, support in s.platforms.items())
        print(f"platforms: {platform_bits}")
    if s.evidence:
        bench = s.evidence.get("local_bench") or s.evidence.get("source")
        if bench:
            print(f"evidence: {bench}")
    if s.privacy:
        telemetry = s.privacy.get("telemetry", "?")
        network = s.privacy.get("network", "?")
        print(f"privacy: telemetry={telemetry} · network={network}")
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


def _surface(args: argparse.Namespace) -> int:
    decision = build_surface_decision(
        args.task,
        cwd=args.cwd,
        intent=args.intent,
        phase=args.phase,
        active_tool=args.active_tool,
        last_command=args.last_command,
        changed_files=tuple(args.changed_file or ()),
        recent_files=tuple(args.recent_file or ()),
    )
    audit_path = None
    if args.audit:
        audit_path = write_surface_audit(
            decision,
            path=Path(args.audit_path) if args.audit_path else None,
        )
    if args.json:
        payload = decision.to_dict()
        if audit_path is not None:
            payload["audit_path"] = str(audit_path)
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    elif decision.block:
        print(decision.block)
        if audit_path is not None:
            print(f"audit: {audit_path}")
    return 0


def _surface_audit(args: argparse.Namespace) -> int:
    path = Path(args.path) if args.path else default_audit_path(Path(args.cwd))
    summary = summarize_surface_audit(path)
    if args.json:
        print(json.dumps(summary, ensure_ascii=False, indent=2))
    else:
        print(f"surface audit: {summary['events']} event(s)")
        print(f"path: {summary['path']}")
        if summary["sets"]:
            print("sets:")
            for name, count in summary["sets"].items():
                print(f"  - {name}: {count}")
        if summary["actions"]:
            print("actions:")
            for action, count in summary["actions"].items():
                print(f"  - {action}: {count}")
        if summary.get("postures"):
            print("postures:")
            for posture, count in summary["postures"].items():
                print(f"  - {posture}: {count}")
    return 0


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


def _print_mesh_result(result: MeshResult, as_json: bool) -> int:
    if as_json:
        print(json.dumps(result.to_dict(), ensure_ascii=False, indent=2))
    else:
        print(result.summary)
        if result.members:
            print("members:")
            for member in result.members:
                state = "active" if member.active else "stale"
                print(
                    f"  - {member.member} [{state}] host={member.host} "
                    f"role={member.role} last_seen={member.last_seen:.0f}"
                )
        if result.events:
            print("events:")
            for event in result.events:
                print(
                    f"  - #{event.seq} [{event.lane}·{event.kind}] "
                    f"{event.member}: {event.content}"
                )
                if event.artifact:
                    print(f"    artifact: {event.artifact}")
                if event.promoted_from is not None:
                    print(f"    promoted_from: {event.promoted_from}")
        if result.locks:
            print("locks:")
            for lock in result.locks:
                print(
                    f"  - {lock.name}: owner={lock.owner} "
                    f"expires={lock.expires_at:.0f} purpose={lock.purpose}"
                )
        print(f"cursor: {result.cursor}")
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


def _memory_mesh(args: argparse.Namespace) -> int:
    if args.memory_action == "observe":
        obs = record_observation(
            args.sig,
            lesson_id=args.lesson_id or "",
            root=Path(args.memory_root) if args.memory_root else None,
        )
        if args.json:
            print(json.dumps(obs.__dict__, ensure_ascii=False, indent=2))
        else:
            linked = f" linked={obs.lesson_id}" if obs.lesson_id else ""
            print(f"memory observe: {obs.sig} count={obs.count}{linked}")
        return 0

    if args.memory_action == "governance":
        result = run_governance(
            root=Path(args.memory_root) if args.memory_root else None,
            threshold=args.threshold,
            write=not args.dry_run,
        )
        if args.json:
            print(json.dumps(result.to_dict(), ensure_ascii=False, indent=2))
        else:
            print(result.render())
        return 0

    if args.memory_action == "install-hooks":
        hosts = ("claude-code", "codex") if args.host == "all" else (args.host,)
        results = []
        for host in hosts:
            path = Path(args.config_path) if args.config_path and len(hosts) == 1 else None
            results.append(install_memory_hooks(host=host, config_path=path))
        if args.json:
            print(json.dumps([result.to_dict() for result in results], ensure_ascii=False, indent=2))
        else:
            for result in results:
                print(f"{result.summary} ({result.path})")
        return 0 if all(result.status == "success" for result in results) else 1

    if args.memory_action == "status":
        from .memory import status_store as status_store_mod

        project = args.project or Path.cwd().name
        if args.status_action == "show":
            snapshot = status_store_mod.read_status(project)
            if args.json:
                payload = snapshot.to_dict() if snapshot else {"project": project, "git": None, "note": None}
                print(json.dumps(payload, ensure_ascii=False, indent=2))
            else:
                rendered = status_store_mod.render_resume(snapshot)
                print(rendered if rendered else f"(no snapshot for {project})")
            return 0
        if args.status_action == "save":
            cwd = args.cwd or str(Path.cwd())
            git = status_store_mod.capture_git_layer(cwd)
            ok = status_store_mod.save_git_layer(project, git)
            if args.json:
                print(json.dumps({"project": project, "saved": ok, "git": git.__dict__}, ensure_ascii=False, indent=2))
            else:
                print(f"status save: {'ok' if ok else 'FAILED'} · {git.branch} · {git.head_short} · dirty {git.dirty_count}")
            return 0 if ok else 1
        if args.status_action == "note":
            updated_by = args.by or "paw:cli"
            cwd = str(Path.cwd())
            git = status_store_mod.capture_git_layer(cwd)
            ok = status_store_mod.save_note(project, args.summary, updated_by=updated_by, base_head=git.head_short)
            if args.json:
                print(json.dumps({"project": project, "saved": ok, "base_head": git.head_short}, ensure_ascii=False, indent=2))
            else:
                print(f"status note: {'ok' if ok else 'FAILED'} (base {git.head_short})")
            return 0 if ok else 1
        if args.status_action == "reset":
            ok = status_store_mod.reset_status(project)
            if args.json:
                print(json.dumps({"project": project, "reset": ok}, ensure_ascii=False, indent=2))
            else:
                print(f"status reset: {'ok' if ok else 'nothing to remove'}")
            return 0

    if args.memory_action == "status-sync":
        from .memory import status_sync as sync_mod

        cwd = args.cwd
        if args.status_sync_action == "apply":
            result = sync_mod.apply(cwd=cwd)
        elif args.status_sync_action == "remove":
            result = sync_mod.remove(cwd=cwd)
        else:
            result = sync_mod.verify(cwd=cwd)
        if args.json:
            print(json.dumps(result.__dict__, ensure_ascii=False, indent=2))
        else:
            print(f"status-sync {args.status_sync_action}: {result.message}")
        return 0

    if args.memory_action == "distrust":
        from .memory import distrust as distrust_mod
        if args.distrust_action == "list":
            data = distrust_mod.load()
            if args.json:
                print(json.dumps(data, ensure_ascii=False, indent=2))
            elif not data:
                print("(no distrust records)")
            else:
                for mid, miss in sorted(data.items()):
                    print(f"{mid}\tmiss={miss}")
            return 0
        if args.distrust_action == "forget":
            removed = distrust_mod.forget(args.mem_id)
            msg = f"forgot {args.mem_id}" if removed else f"{args.mem_id} not present"
            if args.json:
                print(json.dumps({"mem_id": args.mem_id, "forgot": removed}, ensure_ascii=False))
            else:
                print(f"distrust forget: {msg}")
            return 0
        if args.distrust_action == "record":
            # Manual miss recording per the plan: until transcript-watermark capture
            # is honest, the agent records a miss explicitly when a recalled fix
            # recurs. This closes the governance loop manually.
            distrust_mod.record_miss(args.mem_id)
            data = distrust_mod.load()
            miss = data.get(args.mem_id, 0)
            if args.json:
                print(json.dumps({"mem_id": args.mem_id, "miss": miss}, ensure_ascii=False))
            else:
                print(f"distrust record: {args.mem_id} miss={miss}")
            return 0

    if args.memory_action == "outcomes":
        from .memory import outcomes as outcomes_mod
        if args.outcomes_action == "list":
            data = outcomes_mod.load()
            if args.json:
                print(json.dumps(data, ensure_ascii=False, indent=2))
            elif not data:
                print("(no outcome records)")
            else:
                for name, rec in sorted(data.items()):
                    s = rec.get("suggested", 0)
                    u = rec.get("used", 0)
                    print(f"{name}\tsuggested={s}\tused={u}")
            return 0
        if args.outcomes_action == "forget":
            removed = outcomes_mod.forget(args.set_name)
            msg = f"forgot {args.set_name}" if removed else f"{args.set_name} not present"
            if args.json:
                print(json.dumps({"set": args.set_name, "forgot": removed}, ensure_ascii=False))
            else:
                print(f"outcomes forget: {msg}")
            return 0

    if args.memory_action == "session-reset":
        from .memory import sessionlog
        sessionlog.reset(args.session_id)
        if args.json:
            print(json.dumps({"session_id": args.session_id, "reset": True}, ensure_ascii=False))
        else:
            print(f"session-reset: cleared dedup for {args.session_id}")
        return 0

    if args.memory_action == "facts":
        from .memory import facts as facts_mod
        if args.facts_action == "get":
            row = facts_mod.get_fact(args.entity, args.key)
            if row is None:
                if args.json:
                    print(json.dumps({"entity": args.entity, "key": args.key, "value": None}))
                else:
                    print(f"(no fact {args.entity}.{args.key})")
                return 0
            if args.json:
                print(json.dumps(row.__dict__, ensure_ascii=False, indent=2))
            else:
                print(f"{args.entity}.{args.key} = {row.value}")
            return 0
        if args.facts_action == "list":
            rows = facts_mod.list_facts(args.entity)
            if args.json:
                print(json.dumps([r.__dict__ for r in rows], ensure_ascii=False, indent=2))
            elif not rows:
                print(f"(no facts under {args.entity})")
            else:
                for r in rows:
                    print(f"{r.key}\t{r.value}")
            return 0

    if args.memory_action == "hook":
        raw = sys.stdin.buffer.read().decode("utf-8", "ignore") if not sys.stdin.isatty() else ""
        payload = load_hook_payload(raw)
        config = build_config(
            payload,
            host=args.host,
            event=args.event,
            project=args.project,
            run_id=args.run_id,
            member=args.member,
            role=args.role,
            state_dir=Path(args.state_dir) if args.state_dir else None,
            hook_state_dir=Path(args.hook_state_dir) if args.hook_state_dir else None,
        )
        try:
            result = run_memory_hook(config)
            if args.json:
                print(json.dumps(result.to_dict(), ensure_ascii=False, indent=2))
            else:
                out = hook_stdout(result, hook_event_name=_hook_event_name(args.event))
                if out:
                    print(out)
            return 0
        except Exception:
            return 0

    mesh = MemoryMesh(root=Path(args.state_dir) if args.state_dir else None)
    scope = MeshScope(project=args.project, run_id=args.run_id)
    action = args.memory_action
    if action == "register":
        result = mesh.register(
            scope,
            member=args.member,
            host=args.host,
            role=args.role,
            session_id=args.session_id,
            capabilities=tuple(args.capability),
            ttl_seconds=args.ttl_seconds,
        )
    elif action == "heartbeat":
        result = mesh.heartbeat(scope, member=args.member)
    elif action == "members":
        result = mesh.members(scope)
    elif action == "post":
        result = mesh.post(
            scope,
            member=args.member,
            lane=args.lane,
            kind=args.kind,
            content=args.content,
            artifact=args.artifact,
        )
    elif action == "promote":
        result = mesh.promote(
            scope,
            member=args.member,
            seq=args.seq,
            kind=args.kind,
        )
    elif action == "poll":
        result = mesh.poll(
            scope,
            member=args.member,
            since=args.since,
            include_private=not args.shared_only,
        )
    elif action == "lock-acquire":
        result = mesh.acquire_lock(
            scope,
            name=args.name,
            owner=args.owner,
            purpose=args.purpose,
            ttl_seconds=args.ttl_seconds,
        )
    elif action == "lock-release":
        result = mesh.release_lock(
            scope,
            name=args.name,
            owner=args.owner,
            force=args.force,
        )
    else:
        return 2
    return _print_mesh_result(result, args.json)


def _hook_event_name(event: str) -> str:
    return {
        "session-start": "SessionStart",
        "user-prompt": "UserPromptSubmit",
        "stop": "Stop",
    }.get(event, event)


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
        reviewer = _mock_reviewer
        evaluator = _mock_evaluator
        # mutation is member-agnostic: it applies whatever SEARCH/REPLACE handoff the
        # implementer wrote, regardless of which model produced it. mutate=off keeps
        # the deterministic mock artifact for smoke; dry/apply runs the real applier.
        mutation_runner = _mock_mutation_runner
    else:
        adapters, _ = build_codex_deepseek_adapters(repo=Path.cwd())
        planner = adapters.planner
        implementer = adapters.implementer
        reviewer = adapters.reviewer
        evaluator = adapters.evaluator
        mutation_runner = None

    # --mutate is decoupled from the adapter profile so any team composition
    # (mock today; codex-deepseek; a future claude+deepseek) gets real patch
    # application from one switch. dry = compute diff only; apply = write+backup.
    if args.mutate in ("dry", "apply"):
        mutation_runner = make_mutation_runner(
            repo=Path.cwd(), dry_run=args.mutate == "dry",
        )

    # --verify swaps in an evaluator that actually checks the mutated tree, closing
    # the mutate->verify->revise loop (the kernel already feeds a fail back into the
    # next iteration). --verify-cmd runs an explicit command; --verify compileall
    # focuses on just the Python files the mutation touched.
    if args.verify_cmd:
        evaluator = make_verification_evaluator(
            repo=Path.cwd(), command=shlex.split(args.verify_cmd),
        )
    elif args.verify == "compileall":
        evaluator = make_verification_evaluator(repo=Path.cwd())

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


def _doctor(args: argparse.Namespace, *, command: str) -> int:
    hosts = tuple(args.host) if args.host else ("claude-code", "codex", "gemini", "z-code")
    report = run_doctor(root=Path(args.root) if args.root else Path.cwd(), hosts=hosts)
    if args.json:
        print(json.dumps(report.to_dict(), ensure_ascii=False, indent=2))
    else:
        print(render_report(report, command=command))
    return 0 if report.status == "healthy" else 1


def _codebase_memory(args: argparse.Namespace) -> int:
    try:
        if args.codebase_memory_action == "project-name":
            print(codebase_memory_project_name(Path(args.path).resolve()))
            return 0
        binary = require_binary(Path(args.root) if args.root else Path.cwd(), args.binary)
        if args.codebase_memory_action == "index":
            repo = Path(args.path).resolve()
            result = run_codebase_memory_tool(
                "index_repository",
                {"repo_path": repo.as_posix()},
                binary=binary,
                timeout=args.timeout,
            )
        elif args.codebase_memory_action == "search":
            payload: dict[str, object] = {"project": args.project}
            if args.name_pattern:
                payload["name_pattern"] = args.name_pattern
            result = run_codebase_memory_tool(
                "search_graph",
                payload,
                binary=binary,
                timeout=args.timeout,
            )
        else:
            return 2
    except (FileNotFoundError, TimeoutError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 1

    if args.codebase_memory_action == "search":
        output = parse_search_output(result)
        print(format_search_output(output, limit=args.limit, json_mode=args.json))
    elif args.json:
        print(json.dumps(result.to_dict(), ensure_ascii=False, indent=2))
    elif result.combined:
        print(result.combined)
    return result.returncode


def _z_code(args: argparse.Namespace) -> int:
    result = setup_zcode(overwrite=args.overwrite)
    if args.json:
        print(json.dumps(result.to_dict(), ensure_ascii=False, indent=2))
    else:
        print(result.summary)
        print(f"  skill: {result.skill_path}")
        if result.app_path:
            print(f"  app: {result.app_path}")
        print(f"  path: {'ready' if result.path_ready else 'restart shell/host'}")
    return 0 if result.status == "healthy" else 1


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


def _pack(args: argparse.Namespace) -> int:
    """Wrap code2prompt: pack a subtree into an LLM-context file with token count.

    Includes a scope guard that refuses broad root packs unless scoped
    with ``--include``, ``--diff``, or ``--allow-large``.
    """
    from paw.repo_pack import GuardRefused, guard_broad_pack, run_vendored_code2prompt

    path = Path(args.path).resolve()
    try:
        guard_broad_pack(
            path,
            has_include=bool(args.include),
            has_diff=bool(args.diff),
            allow_large=bool(args.allow_large),
        )
    except GuardRefused as exc:
        print(f"error: {exc.message}", file=sys.stderr)
        return 1

    return run_vendored_code2prompt(
        path,
        output=args.output,
        diff=args.diff,
        include=args.include,
        exclude=args.exclude,
    )


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

    surface = sub.add_parser(
        "surface",
        help="print hook-style paw router+memory context for hosts without hooks",
    )
    surface.add_argument("task")
    surface.add_argument("--cwd", default=".", help="repository/workspace path")
    surface.add_argument("--intent", help="host-provided task intent, e.g. repo_handoff or affected_tests")
    surface.add_argument("--phase", help="agent phase, e.g. explore, edit, verify, handoff")
    surface.add_argument("--active-tool", help="tool the agent is about to use")
    surface.add_argument("--last-command", help="command the agent is about to run or just ran")
    surface.add_argument("--changed-file", action="append", help="changed file path; repeatable")
    surface.add_argument("--recent-file", action="append", help="recently read or target file path; repeatable")
    surface.add_argument("--audit", action="store_true", help="append structured surface decision to .paw/surface-audit.jsonl")
    surface.add_argument("--audit-path", help="override audit JSONL path")
    surface.add_argument("--json", action="store_true")

    surface_audit = sub.add_parser(
        "surface-audit",
        help="summarize structured paw surface decisions",
    )
    surface_audit.add_argument("--cwd", default=".", help="repository/workspace path")
    surface_audit.add_argument("--path", help="audit JSONL path (default: <cwd>/.paw/surface-audit.jsonl)")
    surface_audit.add_argument("--json", action="store_true")

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

    memory = sub.add_parser(
        "memory",
        help="coordinate several local agent sessions over shared memory lanes",
    )
    memory_sub = memory.add_subparsers(dest="memory_action", required=True)

    observe = memory_sub.add_parser(
        "observe",
        help="record a repeated memory miss signature for governance",
    )
    observe.add_argument("--sig", required=True, help="stable miss signature, e.g. command not found|python")
    observe.add_argument("--lesson-id", help="lesson/memory id that should have prevented the miss")
    observe.add_argument("--memory-root", help="default ~/.paw/memory")
    observe.add_argument("--json", action="store_true")

    governance = memory_sub.add_parser(
        "governance",
        help="turn repeated observations into rewrite/retire proposals",
    )
    governance.add_argument("--threshold", type=int, default=3)
    governance.add_argument("--memory-root", help="default ~/.paw/memory")
    governance.add_argument("--dry-run", action="store_true")
    governance.add_argument("--json", action="store_true")

    def add_memory_scope(mp: argparse.ArgumentParser) -> None:
        mp.add_argument("--project", required=True)
        mp.add_argument("--run-id", required=True)
        mp.add_argument(
            "--state-dir",
            help="local memory-mesh state root; default ~/.paw/state/memory-mesh",
        )
        mp.add_argument("--json", action="store_true")

    register = memory_sub.add_parser(
        "register",
        help="register or refresh one live agent session",
    )
    add_memory_scope(register)
    register.add_argument("--member", required=True, help="stable member id, e.g. codex-1")
    register.add_argument("--host", required=True, help="agent host/vendor, e.g. codex")
    register.add_argument("--role", help="team role; defaults to member id")
    register.add_argument("--session-id")
    register.add_argument(
        "--capability",
        action="append",
        default=[],
        help="member capability tag; may be repeated",
    )
    register.add_argument("--ttl-seconds", type=int, default=300)

    heartbeat = memory_sub.add_parser("heartbeat", help="refresh one member heartbeat")
    add_memory_scope(heartbeat)
    heartbeat.add_argument("--member", required=True)

    members = memory_sub.add_parser("members", help="list active and stale members")
    add_memory_scope(members)

    post = memory_sub.add_parser("post", help="post to the shared or private lane")
    add_memory_scope(post)
    post.add_argument("--member", required=True)
    post.add_argument("--content", required=True)
    post.add_argument("--lane", choices=("shared", "private"), default="shared")
    post.add_argument("--kind", default="note")
    post.add_argument("--artifact")

    promote = memory_sub.add_parser(
        "promote",
        help="copy an owned private-lane event into the shared lane",
    )
    add_memory_scope(promote)
    promote.add_argument("--member", required=True)
    promote.add_argument("--seq", type=int, required=True)
    promote.add_argument("--kind", default="note")

    poll = memory_sub.add_parser(
        "poll",
        help="read shared events plus this member's private lane since a cursor",
    )
    add_memory_scope(poll)
    poll.add_argument("--member")
    poll.add_argument("--since", type=int, default=0)
    poll.add_argument("--shared-only", action="store_true")

    lock_acquire = memory_sub.add_parser(
        "lock-acquire",
        help="claim a short-lived write-intent lock",
    )
    add_memory_scope(lock_acquire)
    lock_acquire.add_argument("--name", required=True)
    lock_acquire.add_argument("--owner", required=True)
    lock_acquire.add_argument("--purpose", default="")
    lock_acquire.add_argument("--ttl-seconds", type=int, default=300)

    lock_release = memory_sub.add_parser("lock-release", help="release a write-intent lock")
    add_memory_scope(lock_release)
    lock_release.add_argument("--name", required=True)
    lock_release.add_argument("--owner", required=True)
    lock_release.add_argument("--force", action="store_true")

    hook = memory_sub.add_parser(
        "hook",
        help="hook-safe auto register/heartbeat/poll shim for Claude, Codex, Gemini, Z Code",
    )
    hook.add_argument(
        "--host",
        required=True,
        choices=("claude-code", "codex", "gemini", "z-code"),
    )
    hook.add_argument(
        "--event",
        required=True,
        choices=("session-start", "user-prompt", "stop"),
    )
    hook.add_argument("--project", help="default: payload project or cwd basename")
    hook.add_argument("--run-id", help="default: PAW_MEMORY_RUN_ID or live")
    hook.add_argument("--member", help="default: host + stable session hash")
    hook.add_argument("--role", help="default: host")
    hook.add_argument(
        "--state-dir",
        help="local memory-mesh state root; default ~/.paw/state/memory-mesh",
    )
    hook.add_argument(
        "--hook-state-dir",
        help="cursor state root; default ~/.paw/state/memory-hooks",
    )
    hook.add_argument("--json", action="store_true")

    install_hooks = memory_sub.add_parser(
        "install-hooks",
        help="add memory hook shim to Claude/Codex hook config (add-only, idempotent)",
    )
    install_hooks.add_argument(
        "--host",
        choices=("claude-code", "codex", "all"),
        default="all",
    )
    install_hooks.add_argument(
        "--config-path",
        help="override one host config path; only valid when --host is not all",
    )
    install_hooks.add_argument("--json", action="store_true")

    # ---- status snapshot (two-layer resume anchor) ----
    status = memory_sub.add_parser(
        "status",
        help="project status snapshot (git layer + AI note) for SessionStart resume",
    )
    status_sub = status.add_subparsers(dest="status_action", required=True)
    status_show = status_sub.add_parser("show", help="print the current snapshot")
    status_show.add_argument("--project", default=None)
    status_show.add_argument("--json", action="store_true")
    status_save = status_sub.add_parser(
        "save", help="capture git layer (deterministic; run on Stop or before close)"
    )
    status_save.add_argument("--project", default=None)
    status_save.add_argument("--cwd", default=None)
    status_save.add_argument("--json", action="store_true")
    status_note = status_sub.add_parser(
        "note", help="write the AI note layer (did X / hit Y / next Z)"
    )
    status_note.add_argument("summary")
    status_note.add_argument("--project", default=None)
    status_note.add_argument("--by", default=None, help="member/host that wrote the note")
    status_note.add_argument("--json", action="store_true")
    status_reset = status_sub.add_parser("reset", help="delete the status slot")
    status_reset.add_argument("--project", default=None)
    status_reset.add_argument("--json", action="store_true")

    # ---- status-sync managed block (the โพย) ----
    status_sync = memory_sub.add_parser(
        "status-sync",
        help="manage the status-sync instruction block in AGENTS.md/CLAUDE.md",
    )
    status_sync_sub = status_sync.add_subparsers(
        dest="status_sync_action", required=True
    )
    for verb in ("apply", "remove", "verify"):
        sp = status_sync_sub.add_parser(verb)
        sp.add_argument("--cwd", default=None)
        sp.add_argument("--json", action="store_true")

    # ---- governance overlays (inspect / reset / record-miss) ----
    distrust = memory_sub.add_parser(
        "distrust",
        help="inspect/reset the memory distrust overlay (recalled-but-recurring)",
    )
    distrust_sub = distrust.add_subparsers(dest="distrust_action", required=True)
    distrust_sub.add_parser("list", help="show mem_id → miss_count")
    distrust_forget = distrust_sub.add_parser("forget", help="re-trust one mem_id")
    distrust_forget.add_argument("mem_id")
    distrust_record = distrust_sub.add_parser(
        "record", help="record a miss on a mem_id (manual governance, per plan)"
    )
    distrust_record.add_argument("mem_id")
    for sp in distrust_sub.choices.values():
        sp.add_argument("--json", action="store_true")

    outcomes = memory_sub.add_parser(
        "outcomes",
        help="inspect/reset the set-adoption outcome overlay",
    )
    outcomes_sub = outcomes.add_subparsers(dest="outcomes_action", required=True)
    outcomes_sub.add_parser("list", help="show set → suggested/used counts")
    outcomes_forget = outcomes_sub.add_parser("forget", help="reset one set's record")
    outcomes_forget.add_argument("set_name")
    for sp in outcomes_sub.choices.values():
        sp.add_argument("--json", action="store_true")

    session_reset = memory_sub.add_parser(
        "session-reset",
        help="clear the once-per-session inject dedup for one session",
    )
    session_reset.add_argument("session_id")
    session_reset.add_argument("--json", action="store_true")

    facts_cmd = memory_sub.add_parser(
        "facts",
        help="read ICM structured facts (status/decision index) directly",
    )
    facts_sub = facts_cmd.add_subparsers(dest="facts_action", required=True)
    facts_get = facts_sub.add_parser("get", help="read entity.key value")
    facts_get.add_argument("entity")
    facts_get.add_argument("key")
    facts_list = facts_sub.add_parser("list", help="list keys under an entity")
    facts_list.add_argument("entity")
    for sp in facts_sub.choices.values():
        sp.add_argument("--json", action="store_true")

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
    team_run.add_argument(
        "--mutate",
        choices=("off", "dry", "apply"),
        default="off",
        help="apply implementer SEARCH/REPLACE edits to the cwd tree: off (handoff "
        "only), dry (compute diff, write nothing), apply (write with backup+rollback)",
    )
    team_run.add_argument(
        "--verify",
        choices=("off", "compileall"),
        default="off",
        help="verify the mutated tree before passing: compileall checks just the "
        "Python files the mutation touched, feeding failures into the revise loop",
    )
    team_run.add_argument(
        "--verify-cmd",
        help="explicit verification command run in the cwd (e.g. a focused test "
        "subset); overrides --verify and drives the same revise loop",
    )
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

    pack_p = sub.add_parser(
        "pack",
        help="pack a subtree into an LLM-context file via code2prompt (repo-pack set)",
    )
    pack_p.add_argument("path", nargs="?", default=".", help="directory to pack (default: cwd)")
    pack_p.add_argument("-o", "--output", help="write packed context to this file")
    pack_p.add_argument("-d", "--diff", action="store_true", help="append git diff")
    pack_p.add_argument("--include", action="append", default=[], metavar="GLOB")
    pack_p.add_argument("--exclude", action="append", default=[], metavar="GLOB")
    pack_p.add_argument("--allow-large", action="store_true", help="override root-pack guard")

    doctor_p = sub.add_parser(
        "doctor",
        help="check default core tools, linker state, and host restart advice",
    )
    doctor_p.add_argument(
        "--host",
        action="append",
        choices=("claude-code", "codex", "gemini", "z-code"),
        help="host to inspect; may be repeated (default: all known paw hosts)",
    )
    doctor_p.add_argument("--root", help="project root to inspect (default: cwd)")
    doctor_p.add_argument("--json", action="store_true")

    init_p = sub.add_parser(
        "init",
        help="safe foundation-core readiness check; prints installs, does not auto-install",
    )
    init_p.add_argument(
        "--host",
        action="append",
        choices=("claude-code", "codex", "gemini", "z-code"),
        help="host to inspect; may be repeated (default: all known paw hosts)",
    )
    init_p.add_argument("--root", help="project root to inspect (default: cwd)")
    init_p.add_argument("--json", action="store_true")

    cbm = sub.add_parser(
        "codebase-memory",
        help="Windows-safe argv wrapper for codebase-memory-mcp CLI JSON calls",
    )
    cbm_sub = cbm.add_subparsers(dest="codebase_memory_action", required=True)
    cbm_name = cbm_sub.add_parser("project-name", help="print codebase-memory project id")
    cbm_name.add_argument("path", nargs="?", default=".")

    cbm_index = cbm_sub.add_parser("index", help="index a repository without shell JSON quoting")
    cbm_index.add_argument("path", nargs="?", default=".")
    cbm_index.add_argument("--binary", help="path to codebase-memory-mcp binary")
    cbm_index.add_argument("--root", help="project root used to find bench/_tools binary")
    cbm_index.add_argument("--timeout", type=int, default=120)
    cbm_index.add_argument("--json", action="store_true")

    cbm_search = cbm_sub.add_parser("search", help="search graph without shell JSON quoting")
    cbm_search.add_argument("--project", required=True)
    cbm_search.add_argument("--name-pattern")
    cbm_search.add_argument("--limit", type=int, default=10, help="max rows (default: 10; 0 = all)")
    cbm_search.add_argument("--binary", help="path to codebase-memory-mcp binary")
    cbm_search.add_argument("--root", help="project root used to find bench/_tools binary")
    cbm_search.add_argument("--timeout", type=int, default=45)
    cbm_search.add_argument("--json", action="store_true")

    z_code = sub.add_parser(
        "z-code",
        help="setup/check Z Code as a paw bundle/router/memory host",
    )
    z_code_sub = z_code.add_subparsers(dest="z_code_action", required=True)
    z_code_setup = z_code_sub.add_parser("setup", help="install the paw-bundle Z Code skill")
    z_code_setup.add_argument("--overwrite", action="store_true")
    z_code_setup.add_argument("--json", action="store_true")

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
    if args.group == "doctor":
        return _doctor(args, command="doctor")
    if args.group == "init":
        return _doctor(args, command="init")
    if args.group == "codebase-memory":
        return _codebase_memory(args)
    if args.group == "z-code":
        return _z_code(args)
    if args.group == "sets":
        if args.action == "list":
            return _sets_list()
        if args.action == "show":
            return _sets_show(args.name)
    if args.group == "route":
        return _route(args)
    if args.group == "surface":
        return _surface(args)
    if args.group == "surface-audit":
        return _surface_audit(args)
    if args.group == "suggest":
        return _suggest(args)
    if args.group == "blackboard":
        return _blackboard(args)
    if args.group == "memory":
        return _memory_mesh(args)
    if args.group == "team":
        return _team(args)
    if args.group == "pack":
        return _pack(args)
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
