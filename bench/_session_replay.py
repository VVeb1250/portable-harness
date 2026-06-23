"""Replay REAL Claude Code session transcripts through the A(context-mode) /
B(rtk) / raw token models — the self-runnable NET measurement.

Instead of spawning fresh CC sessions and reading ccusage, we take what already
happened: every tool_result in this project's transcripts, measure its real
token size (tiktoken cl100k proxy), classify it, and apply the per-lane ratios
MEASURED earlier this session:

  raw : the tokens the output actually cost (baseline)
  rtk : git/log/diff/status shell output -> keep 36% (rtk 64% cut, _compress_ab);
        everything else passthrough. fixed cost 0.
  cm  : context-mode. stats-able bulky output (git/grep/ls/build/test) routed
        through ctx_execute -> keep 4% + ~120 tok code-echo/op (gross, _cm_ab);
        big docs/web -> ctx_index/search keep ~5% + 120/op (lossless, recall
        caveat); read-to-EDIT and small outputs are NOT routed (need verbatim
        bytes / too small to help). + fixed 8817 tok/session (7017 tool defs +
        ~900 SessionStart inject, mcp_tax + hook probe).

Honest caveats: this is a MODEL replay (measured ratios applied to real output
sizes), not live re-execution. cl100k is a proxy for Anthropic's tokenizer.
read-to-edit detection is path-based and conservative (over-counts toward
'needs bytes', i.e. against cm). The decisive output is bulky_cm_ops/session
vs the ~12 break-even from the trade-off chart.
"""
import json, glob, os, collections, tiktoken

ENC = tiktoken.get_encoding("cl100k_base")
GLOBP = r"C:\Users\VVeb1250\.claude\projects\E--portable-harness\*.jsonl"

CM_FIXED = 7017 + 900          # tool defs + SessionStart inject
ECHO = 120                     # context-mode per-op code-echo (gross)
BULKY = 200                    # below this, no lane helps
RTK_KEEP = 0.36                # rtk 64% cut on its commands
CM_STATS_KEEP = 0.04           # execute_file digest (gross-adjusted)
CM_DOC_KEEP = 0.05             # index/search lossless

RTK_CMDS = ("git log", "git diff", "git status", "git show", "git stat")
STATS_HINT = ("git ", "grep", "rg ", "ls", "dir ", "find ", "pytest", "npm test",
              "build", "cat ", "tail", "head", "wc ", "log", "diff", "status")


def toks(s):
    if not isinstance(s, str):
        s = json.dumps(s)
    return len(ENC.encode(s, disallowed_special=()))


def cmd_of(inp):
    if not isinstance(inp, dict):
        return ""
    return (inp.get("command") or inp.get("query") or inp.get("pattern") or "") if inp else ""


def classify(name, cmd, size, edit_paths, inp):
    """-> (category, rtk_eligible). category in stats|doc|edit|small|other."""
    if size < BULKY:
        return "small", False
    low = cmd.lower()
    if name in ("Bash", "PowerShell"):
        rtk = any(k in low for k in RTK_CMDS)
        stats = any(h in low for h in STATS_HINT)
        return ("stats" if stats else "other"), rtk
    if name in ("Grep", "Glob"):
        return "stats", False
    if name in ("WebFetch", "WebSearch"):
        return "doc", False
    if name == "Read":
        p = (inp or {}).get("file_path", "") if isinstance(inp, dict) else ""
        if p and p in edit_paths:
            return "edit", False     # read-to-edit: needs verbatim bytes
        return "doc", False
    if name.startswith("mcp__"):
        return "doc", False
    return "other", False


def replay(path):
    use = {}                 # tool_use_id -> (name, input)
    edit_paths = set()
    results = []             # (name, cmd, size)
    ctx_used = 0             # actual ctx_* tool calls (live routing compliance)
    for line in open(path, encoding="utf-8"):
        line = line.strip()
        if not line:
            continue
        try:
            d = json.loads(line)
        except Exception:
            continue
        msg = d.get("message", {})
        cont = msg.get("content") if isinstance(msg, dict) else None
        if not isinstance(cont, list):
            continue
        for b in cont:
            if not isinstance(b, dict):
                continue
            if b.get("type") == "tool_use":
                use[b.get("id")] = (b.get("name", "?"), b.get("input", {}))
                if "ctx_" in (b.get("name") or ""):
                    ctx_used += 1
                if b.get("name") in ("Edit", "Write", "NotebookEdit"):
                    fp = (b.get("input", {}) or {}).get("file_path")
                    if fp:
                        edit_paths.add(fp)
            elif b.get("type") == "tool_result":
                nm, inp = use.get(b.get("tool_use_id"), ("?", {}))
                results.append((nm, cmd_of(inp), inp, toks(b.get("content", ""))))

    raw = rtk = cm = 0
    bulky_cm = 0
    cats = collections.Counter()
    for nm, cmd, inp, size in results:
        raw += size
        cat, rtk_ok = classify(nm, cmd, size, edit_paths, inp)
        cats[cat] += 1
        # rtk lane
        rtk += int(size * RTK_KEEP) if rtk_ok else size
        # cm lane
        if cat == "stats":
            cm += int(size * CM_STATS_KEEP) + ECHO; bulky_cm += 1
        elif cat == "doc":
            cm += int(size * CM_DOC_KEEP) + ECHO; bulky_cm += 1
        else:
            cm += size
    cm += CM_FIXED
    return dict(raw=raw, rtk=rtk, cm=cm, ops=len(results), bulky_cm=bulky_cm,
                ctx_used=ctx_used, cats=cats)


def main():
    files = sorted(glob.glob(GLOBP), key=lambda p: -os.path.getsize(p))
    print(f"{'session':<14}{'ops':>5}{'bulky':>6}{'raw':>9}{'rtk':>9}{'cm':>9}"
          f"{'NET_B':>9}{'NET_A':>9}{'win':>5}")
    agg = collections.Counter()
    for f in files:
        r = replay(f)
        net_b = r["raw"] - r["rtk"]
        net_a = r["raw"] - r["cm"]
        win = "A" if net_a > net_b else "B"
        sid = os.path.basename(f)[:12]
        print(f"{sid:<14}{r['ops']:>5}{r['bulky_cm']:>6}{r['raw']:>9}{r['rtk']:>9}"
              f"{r['cm']:>9}{net_b:>9}{net_a:>9}{win:>5}")
        for k in ("raw", "rtk", "cm", "ops", "bulky_cm", "ctx_used"):
            agg[k] += r[k]
    n = len(files)
    NB = agg["raw"] - agg["rtk"]
    NA = agg["raw"] - agg["cm"]
    print("-" * 75)
    print(f"{'TOTAL':<14}{agg['ops']:>5}{agg['bulky_cm']:>6}{agg['raw']:>9}"
          f"{agg['rtk']:>9}{agg['cm']:>9}{NB:>9}{NA:>9}{('A' if NA>NB else 'B'):>5}")
    print(f"\navg bulky cm-eligible ops/session = {agg['bulky_cm']/n:.1f}  "
          f"(break-even vs rtk ~ 12)")
    routed = agg["ctx_used"]
    denom = routed + agg["bulky_cm"]
    print(f"LIVE routing compliance = {routed} ctx_* calls / {agg['bulky_cm']} "
          f"modeled-eligible bulky = {100*routed/denom:.0f}%  "
          f"(0% = pre-context-mode baseline; re-run after restart + real sessions)")
    print(f"sessions where A wins: "
          f"{sum(1 for f in files if (replay(f)['raw']-replay(f)['cm'])>(replay(f)['raw']-replay(f)['rtk']))}/{n}")


if __name__ == "__main__":
    main()
