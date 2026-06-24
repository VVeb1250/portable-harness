"""Orchestrator for the team-vs-solo SWE-bench-Lite probe.

Arms (single shot, oracle retrieval):
  claude-solo    : Claude (you, on the seat) writes the whole patch.
  deepseek-solo  : DeepSeek writes the patch from problem + files (trap baseline).
  team           : Claude plans -> DeepSeek implements -> Claude reviews.

Claude-side steps are driven by you in the live session; DeepSeek and scoring
are automated here. Usage:

  py -m bench.swe_probe.run instances --repo psf/requests
  py -m bench.swe_probe.run pull psf__requests-2317
  py -m bench.swe_probe.run gold-validate psf__requests-2317      # env sanity
  py -m bench.swe_probe.run deepseek-solo psf__requests-2317
  py -m bench.swe_probe.run team-impl psf__requests-2317 --plan plan.md
  py -m bench.swe_probe.run claude-patch psf__requests-2317 claude-solo --file p.diff
  py -m bench.swe_probe.run eval psf__requests-2317 deepseek-solo
  py -m bench.swe_probe.run claude-usage psf__requests-2317 claude-solo --in 42000 --out 1800
  py -m bench.swe_probe.run report
"""
from __future__ import annotations

import argparse
import difflib
import json
import subprocess
import sys

from . import codex, config, deepseek, pull, tokens


# --- ledger ----------------------------------------------------------------
def _ledger_path(iid: str):
    return config.RESULTS / f"{iid}.json"


def ledger_load(iid: str) -> dict:
    p = _ledger_path(iid)
    if p.exists():
        return json.loads(p.read_text(encoding="utf-8"))
    return {"instance_id": iid, "arms": {}}


def ledger_update(iid: str, arm: str, **fields):
    led = ledger_load(iid)
    led["arms"].setdefault(arm, {}).update(fields)
    _ledger_path(iid).write_text(json.dumps(led, indent=2), encoding="utf-8")


# --- patch helpers ---------------------------------------------------------
def _clean_diff(text: str) -> str:
    text = text.strip()
    if text.startswith("```"):
        lines = text.splitlines()
        lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        text = "\n".join(lines)
    return text.strip() + "\n"


def _file_diff(path: str, old: str, new: str) -> str:
    """git-apply-compatible unified diff between base and new content of ONE file.

    Computed locally so a model's logic is scored, not its diff arithmetic
    (apply-fail confound, STATUS §16.6 #1). Handles file creation (old == "").
    """
    if old == new:
        return ""

    def _norm(s: str) -> str:  # avoid "no newline at eof" rejections
        return s if (s == "" or s.endswith("\n")) else s + "\n"

    old, new = _norm(old), _norm(new)
    fromfile = "/dev/null" if old == "" else f"a/{path}"
    body = "".join(difflib.unified_diff(
        old.splitlines(keepends=True), new.splitlines(keepends=True),
        fromfile=fromfile, tofile=f"b/{path}", lineterm="\n",
    ))
    if not body:
        return ""
    header = f"diff --git a/{path} b/{path}\n"
    if old == "":
        header += "new file mode 100644\n"
    return header + body


def _files_to_patch(bundle: dict, new_files: dict[str, str]) -> str:
    """Diff each model-returned full file against its base content in the bundle."""
    parts = []
    for path, new in new_files.items():
        old = bundle["oracle_files"].get(path, "")
        d = _file_diff(path, old, new)
        if d:
            parts.append(d)
    return "".join(parts)


def _write_pred(iid: str, arm: str, patch: str):
    pred = config.PREDS / f"{iid}__{arm}.jsonl"
    pred.write_text(
        json.dumps({
            "instance_id": iid,
            "model_name_or_path": arm,
            "model_patch": patch,
        }) + "\n",
        encoding="utf-8",
    )
    return pred


# --- commands --------------------------------------------------------------
def cmd_instances(args):
    for iid in pull.list_instances(args.repo):
        print(iid)


def cmd_pull(args):
    for iid in args.ids:
        out = pull.pull(iid)
        b = json.loads(out.read_text(encoding="utf-8"))
        print(f"{iid}: {len(b['oracle_files'])} oracle file(s) -> {out.name}")


def cmd_gold_validate(args):
    """Score the gold patch; it MUST resolve, else the env/scorer is wrong."""
    b = pull.load(args.id)
    _write_pred(args.id, "gold", b["gold_patch"])
    ok = _eval(args.id, "gold")
    print(f"gold-validate {args.id}: {'PASS (env trustworthy)' if ok else 'FAIL — do not trust scores; switch instance / backend'}")


def _apply(b: dict, edits: dict[str, list[tuple[str, str]]]) -> tuple[dict[str, str], list[str]]:
    """Apply each file's SEARCH/REPLACE edits to its oracle base content.

    Returns ({path: new_content}, [paths whose SEARCH did not match]).
    """
    new_files, misses = {}, []
    for path, file_edits in edits.items():
        base = b["oracle_files"].get(path, "")
        try:
            new_files[path] = deepseek.apply_edits(base, file_edits)
        except deepseek.EditError as e:
            misses.append(path)
            print(f"  ⚠ {path}: SEARCH block not found in base; edit skipped\n"
                  f"      {str(e)[:160]!r}")
    return new_files, misses


def _deepseek_arm(iid: str, arm: str, plan: str | None):
    """Shared: ask DeepSeek for SEARCH/REPLACE edits, apply + diff locally, ledger.

    The model returns only changed regions (scales to large files), we apply
    them to the oracle base and diff locally so logic is scored, not diff
    arithmetic (STATUS §16.6 #1 / §D search-replace fix).
    """
    b = pull.load(iid)
    edits, usage = deepseek.generate_edits(
        b["problem_statement"], b["oracle_files"], plan=plan)

    new_files, misses = _apply(b, edits)
    patch = _files_to_patch(b, new_files)
    (config.PREDS / f"{iid}__{arm}.diff").write_text(patch, encoding="utf-8")
    n_edits = sum(len(v) for v in edits.values())
    ledger_update(iid, arm,
                  deepseek_usage=usage, deepseek_usd=round(deepseek.cost_usd(usage), 6),
                  edit_misses=len(misses))
    if not edits:
        note = "  ⚠ model returned NO @@@FILE blocks (empty patch)"
    elif misses:
        note = f"  ⚠ {len(misses)} file(s) had unmatched SEARCH blocks"
    else:
        note = ""
    print(f"{arm} {iid}: {usage} (${deepseek.cost_usd(usage):.5f}) -> "
          f"{n_edits} edit(s) over {len(edits)} file(s), patch {len(patch)} bytes{note}")
    return patch


def _codex_arm(iid: str, arm: str, plan: str | None = None,
               feedback: str | None = None) -> str:
    """Codex member: stage oracle files, let `codex exec` edit them, take the diff.

    Unlike the DeepSeek arm, codex returns a real `git diff` (already scoped to
    the gold-touched paths in codex.generate_patch), so there is no local
    apply/diff step. Records the REAL token usage + agent turn count from the
    codex event stream (the scarce-quota numbers for the cost axis, STATUS §F.4).
    """
    b = pull.load(iid)
    patch, usage, turns = codex.generate_patch(
        b["problem_statement"], b["oracle_files"], plan=plan, feedback=feedback)
    (config.PREDS / f"{iid}__{arm}.diff").write_text(patch, encoding="utf-8")
    ledger_update(iid, arm, codex_usage=usage, codex_turns=turns)
    note = "" if patch.strip() else "  ⚠ empty diff (codex made no change)"
    print(f"{arm} {iid}: in={usage.get('input_tokens', 0)} "
          f"out={usage.get('output_tokens', 0)} "
          f"reason={usage.get('reasoning_output_tokens', 0)} turns={turns}, "
          f"patch {len(patch)} bytes{note}")
    return patch


def cmd_codex_solo(args):
    _codex_arm(args.id, "codex-solo", plan=None)
    print(f"  (codex patch saved — eval {args.id} codex-solo)")


def cmd_deepseek_solo(args):
    _deepseek_arm(args.id, "deepseek-solo", plan=None)


def cmd_team_impl(args):
    plan = open(args.plan, encoding="utf-8").read()
    _deepseek_arm(args.id, "team", plan=plan)
    print(f"  (team patch saved for Claude review — edit the .diff if needed, "
          f"then: eval {args.id} team)")


def cmd_claude_patch(args):
    """Register a Claude-authored patch (claude-solo, or team final after review)."""
    patch = _clean_diff(open(args.file, encoding="utf-8").read())
    (config.PREDS / f"{args.id}__{args.arm}.diff").write_text(patch, encoding="utf-8")
    print(f"registered {args.arm} patch for {args.id}")


def cmd_claude_usage(args):
    ledger_update(args.id, args.arm,
                  claude_tokens={"input": args.in_, "output": args.out})
    print(f"recorded claude usage {args.arm} {args.id}: in={args.in_} out={args.out}")


def _swebench_run(iid: str, arm: str) -> str:
    """Run the swebench harness for an already-written pred jsonl. Returns run_id.

    run_id = f"{iid}__{arm}", so an agentic loop passes a per-attempt arm
    (e.g. team__a2) to dodge swebench's run-id cache that would otherwise skip
    re-evaluating a changed patch.
    """
    run_id = f"{iid}__{arm}"
    if config.USE_WSL:
        script = config.win_to_wsl(config.BASE / "wsl_eval.sh")
        cmd = ["wsl", "-d", config.WSL_DISTRO, "bash", script, iid, arm]
    else:
        pred = config.PREDS / f"{iid}__{arm}.jsonl"
        cmd = [
            config.SWEBENCH_PYTHON, "-m", "swebench.harness.run_evaluation",
            "--dataset_name", config.DATASET,
            "--predictions_path", str(pred),
            "--instance_ids", iid,
            "--run_id", run_id,
            "--cache_level", config.CACHE_LEVEL,
            "--max_workers", "1",
        ]
    print("  $", " ".join(cmd))
    subprocess.run(cmd, cwd=config.EVAL_OUT, check=False)
    return run_id


def _report_dir(run_id: str, arm: str, iid: str):
    return config.EVAL_OUT / "logs" / "run_evaluation" / run_id / arm / iid


def _read_resolved(run_id: str, arm: str, iid: str) -> bool | None:
    """resolved bool from report.json, or None if the harness produced none."""
    report = _report_dir(run_id, arm, iid) / "report.json"
    if not report.exists():
        return None
    data = json.loads(report.read_text(encoding="utf-8"))
    return bool(data.get(iid, {}).get("resolved", False))


def _read_feedback(run_id: str, arm: str, iid: str, max_lines: int = 80) -> str:
    """Failing-test signal from the harness test_output.txt for an agentic retry."""
    out = _report_dir(run_id, arm, iid) / "test_output.txt"
    if not out.exists():
        return "(no test_output.txt — the patch likely failed to apply cleanly)"
    lines = out.read_text(encoding="utf-8", errors="replace").splitlines()
    fails = [ln for ln in lines if ln.startswith(("FAILED", "ERROR", "E   ", "assert"))]
    picked = fails[:40] + (["...(tail)..."] if fails else []) + lines[-max_lines:]
    return "\n".join(picked)


def _eval(iid: str, arm: str) -> bool:
    """Write prediction from saved .diff, run swebench harness, return resolved."""
    if arm != "gold":  # gold's pred jsonl is written by cmd_gold_validate
        diff_path = config.PREDS / f"{iid}__{arm}.diff"
        if not diff_path.exists():
            raise SystemExit(f"no patch for {iid} {arm} (generate/register it first)")
        _write_pred(iid, arm, diff_path.read_text(encoding="utf-8"))
    run_id = _swebench_run(iid, arm)
    resolved = _read_resolved(run_id, arm, iid)
    if resolved is None:
        print(f"  ! no report for {run_id} (eval failed / swebench not installed?)")
        return False
    if arm != "gold":
        ledger_update(iid, arm, resolved=resolved)
    return resolved


def cmd_eval(args):
    ok = _eval(args.id, args.arm)
    print(f"eval {args.id} {args.arm}: resolved={ok}")


def cmd_team_loop(args):
    """COST-AXIS team arm: Claude plans ONCE, DeepSeek implements + retries on
    real test feedback up to --max-iter. Records DeepSeek $ and the tiktoken
    claude_tok for the single planning step — the scarce-quota number that
    claude-solo agentic (which loops the seat) must beat.
    """
    b = pull.load(args.id)
    plan = open(args.plan, encoding="utf-8").read()
    problem, files = b["problem_statement"], b["oracle_files"]

    ds_usd, feedback, resolved, used = 0.0, None, False, 0
    for k in range(1, args.max_iter + 1):
        used = k
        edits, usage = deepseek.generate_edits(problem, files, plan=plan, feedback=feedback)
        ds_usd += deepseek.cost_usd(usage)
        new_files, misses = _apply(b, edits)
        patch = _files_to_patch(b, new_files)
        (config.PREDS / f"{args.id}__team.diff").write_text(patch, encoding="utf-8")

        arm_k = f"team__a{k}"  # per-attempt run_id dodges swebench cache-skip
        _write_pred(args.id, arm_k, patch)
        run_id = _swebench_run(args.id, arm_k)
        resolved = bool(_read_resolved(run_id, arm_k, args.id))
        print(f"  iter {k}: ${deepseek.cost_usd(usage):.5f} "
              f"{sum(len(v) for v in edits.values())} edit(s) "
              f"misses={len(misses)} resolved={resolved}")
        if resolved:
            break
        feedback = (f"### Previous patch (unified diff, still failing)\n{patch}\n\n"
                    f"### Test harness output\n{_read_feedback(run_id, arm_k, args.id)}")

    claude_in = tokens.count(problem) + tokens.count_many(files.values())
    claude_out = tokens.count(plan)
    ledger_update(args.id, "team",
                  resolved=resolved, deepseek_usd=round(ds_usd, 6), team_iters=used,
                  claude_tokens={"input": claude_in, "output": claude_out})
    print(f"team-loop {args.id}: resolved={resolved} after {used} iter | "
          f"DeepSeek ${ds_usd:.5f} | claude_tok≈{claude_in + claude_out} "
          f"(plan once: in={claude_in} out={claude_out})")


def cmd_claude_tokens(args):
    """Record claude_tokens for an arm from the ACTUAL seat content (tiktoken).

    --in-file: problem/files/feedback Claude READ (repeatable).
    --out-file: patches Claude WROTE (repeatable).
    Honest + free + symmetric with team's planning count — this is how the
    claude-solo agentic arm logs the quota it burned looping the seat by hand.
    """
    cin = tokens.count_many(open(f, encoding="utf-8").read() for f in (args.in_file or []))
    cout = tokens.count_many(open(f, encoding="utf-8").read() for f in (args.out_file or []))
    ledger_update(args.id, args.arm, claude_tokens={"input": cin, "output": cout})
    print(f"recorded claude_tokens {args.arm} {args.id}: in={cin} out={cout} (tiktoken)")


def cmd_feedback(args):
    """Print the saved failing-test output for an arm (drives a by-hand solo retry)."""
    print(_read_feedback(f"{args.id}__{args.arm}", args.arm, args.id))


def _arm_cost(a: dict) -> tuple[int, int]:
    """(output_tokens, turns) for an arm — the scarce, rate-limit-binding axis.

    Total tokens are dominated by oracle-file input-reads (team≈solo at 1-shot),
    so the cost signal lives in OUTPUT tokens + agent turns (STATUS §F.4). Pulls
    from whichever seat the arm used: claude (tiktoken), codex (real usage), or
    deepseek (api usage). Turns = team iterations or codex command-executions.
    """
    out = 0
    out += a.get("claude_tokens", {}).get("output", 0)       # claude-solo / team plan
    out += a.get("codex_usage", {}).get("output_tokens", 0)  # codex arms
    out += a.get("deepseek_usage", {}).get("output_tokens", 0)  # deepseek-solo
    turns = a.get("team_iters", 0) or a.get("codex_turns", 0)
    return out, turns


def _arm_usd(a: dict) -> float | None:
    """Total API-equivalent USD for an arm: every member's in+out+reasoning
    priced at API list rate (config.usd). One currency across sub seats +
    metered models (STATUS §F.4 cost axis). Claude side is a FLOOR — tiktoken
    on the plan text misses in-session hidden/thinking tokens.

    Returns None when NO usage was recorded (e.g. claude-solo measured by hand
    but not yet logged) — so an unmeasured arm shows `n/a`, never a fake $0.
    """
    total, seen = 0.0, False
    ct = a.get("claude_tokens")
    if ct:
        seen = True
        total += config.usd("claude", ct.get("input", 0), ct.get("output", 0))
    cx = a.get("codex_usage")
    if cx:
        seen = True
        total += config.usd("codex", cx.get("input_tokens", 0),
                            cx.get("output_tokens", 0),
                            cx.get("reasoning_output_tokens", 0))
    ds = a.get("deepseek_usage")
    if ds:  # deepseek-solo: per-call usage present
        seen = True
        total += config.usd("deepseek", ds.get("input_tokens", 0), ds.get("output_tokens", 0))
    elif "deepseek_usd" in a:  # team: per-iter usage not kept, $ already rolled up
        seen = True
        total += a["deepseek_usd"]
    return total if seen else None


def cmd_report(args):
    rows = []
    for p in sorted(config.RESULTS.glob("*.json")):
        led = json.loads(p.read_text(encoding="utf-8"))
        for arm in config.ARMS:
            if arm not in led["arms"]:
                continue
            a = led["arms"][arm]
            out_tok, turns = _arm_cost(a)
            usd = _arm_usd(a)
            rows.append((
                led["instance_id"], arm,
                "✓" if a.get("resolved") else ("✗" if "resolved" in a else "-"),
                out_tok, turns or "-", f"${usd:.5f}" if usd is not None else "n/a",
            ))
    print(f"{'instance':28} {'arm':16} {'pass':4} {'out_tok':>8} {'turns':>5} {'api_usd':>9}")
    for r in rows:
        print(f"{r[0]:28} {r[1]:16} {r[2]:4} {r[3]:>8} {str(r[4]):>5} {r[5]:>9}")
    print("\napi_usd = all members' in+out+reasoning at API list rate (one currency;"
          " sub seats priced at opportunity cost, not their $0 marginal).")
    print("win = team/codex pass == claude-solo pass at far lower api_usd (+ fewer"
          " out-tok/turns on the capped premium seat). NB: claude api_usd is a FLOOR"
          " (tiktoken misses hidden thinking tokens); codex input not cache-discounted.")


def main(argv=None):
    ap = argparse.ArgumentParser(prog="swe_probe")
    sub = ap.add_subparsers(dest="cmd", required=True)

    s = sub.add_parser("instances"); s.add_argument("--repo"); s.set_defaults(fn=cmd_instances)
    s = sub.add_parser("pull"); s.add_argument("ids", nargs="+"); s.set_defaults(fn=cmd_pull)
    s = sub.add_parser("gold-validate"); s.add_argument("id"); s.set_defaults(fn=cmd_gold_validate)
    s = sub.add_parser("deepseek-solo"); s.add_argument("id"); s.set_defaults(fn=cmd_deepseek_solo)
    s = sub.add_parser("codex-solo"); s.add_argument("id"); s.set_defaults(fn=cmd_codex_solo)
    s = sub.add_parser("team-impl"); s.add_argument("id"); s.add_argument("--plan", required=True); s.set_defaults(fn=cmd_team_impl)
    s = sub.add_parser("claude-patch"); s.add_argument("id"); s.add_argument("arm", choices=config.ARMS); s.add_argument("--file", required=True); s.set_defaults(fn=cmd_claude_patch)
    s = sub.add_parser("claude-usage"); s.add_argument("id"); s.add_argument("arm", choices=config.ARMS); s.add_argument("--in", dest="in_", type=int, required=True); s.add_argument("--out", type=int, required=True); s.set_defaults(fn=cmd_claude_usage)
    s = sub.add_parser("eval"); s.add_argument("id"); s.add_argument("arm", choices=(*config.ARMS, "gold")); s.set_defaults(fn=cmd_eval)
    s = sub.add_parser("team-loop"); s.add_argument("id"); s.add_argument("--plan", required=True); s.add_argument("--max-iter", dest="max_iter", type=int, default=3); s.set_defaults(fn=cmd_team_loop)
    s = sub.add_parser("claude-tokens"); s.add_argument("id"); s.add_argument("arm", choices=config.ARMS); s.add_argument("--in-file", dest="in_file", action="append"); s.add_argument("--out-file", dest="out_file", action="append"); s.set_defaults(fn=cmd_claude_tokens)
    s = sub.add_parser("feedback"); s.add_argument("id"); s.add_argument("arm"); s.set_defaults(fn=cmd_feedback)
    s = sub.add_parser("report"); s.set_defaults(fn=cmd_report)

    args = ap.parse_args(argv)
    args.fn(args)


if __name__ == "__main__":
    main()
