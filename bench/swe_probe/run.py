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

from . import config, deepseek, pull


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


def _deepseek_arm(iid: str, arm: str, plan: str | None):
    """Shared: ask DeepSeek for SEARCH/REPLACE edits, apply + diff locally, ledger.

    The model returns only changed regions (scales to large files), we apply
    them to the oracle base and diff locally so logic is scored, not diff
    arithmetic (STATUS §16.6 #1 / §D search-replace fix).
    """
    b = pull.load(iid)
    edits, usage = deepseek.generate_edits(
        b["problem_statement"], b["oracle_files"], plan=plan)

    new_files, misses = {}, []
    for path, file_edits in edits.items():
        base = b["oracle_files"].get(path, "")
        try:
            new_files[path] = deepseek.apply_edits(base, file_edits)
        except deepseek.EditError as e:
            misses.append(path)
            print(f"  ⚠ {path}: SEARCH block not found in base; edit skipped\n"
                  f"      {str(e)[:160]!r}")

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


def _eval(iid: str, arm: str) -> bool:
    """Write prediction from saved .diff, run swebench harness, return resolved."""
    # gold's prediction jsonl is written by cmd_gold_validate; other arms have a .diff
    if arm != "gold":
        diff_path = config.PREDS / f"{iid}__{arm}.diff"
        if not diff_path.exists():
            raise SystemExit(f"no patch for {iid} {arm} (generate/register it first)")
        _write_pred(iid, arm, diff_path.read_text(encoding="utf-8"))
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

    report = (config.EVAL_OUT / "logs" / "run_evaluation" / run_id / arm / iid / "report.json")
    if not report.exists():
        print(f"  ! no report at {report} (eval failed / swebench not installed?)")
        return False
    data = json.loads(report.read_text(encoding="utf-8"))
    resolved = bool(data.get(iid, {}).get("resolved", False))
    if arm != "gold":
        ledger_update(iid, arm, resolved=resolved)
    return resolved


def cmd_eval(args):
    ok = _eval(args.id, args.arm)
    print(f"eval {args.id} {args.arm}: resolved={ok}")


def cmd_report(args):
    rows = []
    for p in sorted(config.RESULTS.glob("*.json")):
        led = json.loads(p.read_text(encoding="utf-8"))
        for arm in config.ARMS:
            a = led["arms"].get(arm, {})
            ct = a.get("claude_tokens", {})
            rows.append((
                led["instance_id"], arm,
                "✓" if a.get("resolved") else ("✗" if "resolved" in a else "-"),
                ct.get("input", 0) + ct.get("output", 0),
                f"${a.get('deepseek_usd', 0):.5f}",
            ))
    print(f"{'instance':28} {'arm':14} {'pass':4} {'claude_tok':>10} {'ds_usd':>9}")
    for r in rows:
        print(f"{r[0]:28} {r[1]:14} {r[2]:4} {r[3]:>10} {r[4]:>9}")
    print("\nwin = team pass == claude-solo pass, with team claude_tok << claude-solo claude_tok")


def main(argv=None):
    ap = argparse.ArgumentParser(prog="swe_probe")
    sub = ap.add_subparsers(dest="cmd", required=True)

    s = sub.add_parser("instances"); s.add_argument("--repo"); s.set_defaults(fn=cmd_instances)
    s = sub.add_parser("pull"); s.add_argument("ids", nargs="+"); s.set_defaults(fn=cmd_pull)
    s = sub.add_parser("gold-validate"); s.add_argument("id"); s.set_defaults(fn=cmd_gold_validate)
    s = sub.add_parser("deepseek-solo"); s.add_argument("id"); s.set_defaults(fn=cmd_deepseek_solo)
    s = sub.add_parser("team-impl"); s.add_argument("id"); s.add_argument("--plan", required=True); s.set_defaults(fn=cmd_team_impl)
    s = sub.add_parser("claude-patch"); s.add_argument("id"); s.add_argument("arm", choices=config.ARMS); s.add_argument("--file", required=True); s.set_defaults(fn=cmd_claude_patch)
    s = sub.add_parser("claude-usage"); s.add_argument("id"); s.add_argument("arm", choices=config.ARMS); s.add_argument("--in", dest="in_", type=int, required=True); s.add_argument("--out", type=int, required=True); s.set_defaults(fn=cmd_claude_usage)
    s = sub.add_parser("eval"); s.add_argument("id"); s.add_argument("arm", choices=(*config.ARMS, "gold")); s.set_defaults(fn=cmd_eval)
    s = sub.add_parser("report"); s.set_defaults(fn=cmd_report)

    args = ap.parse_args(argv)
    args.fn(args)


if __name__ == "__main__":
    main()
