"""Deterministic ICM recall-quality eval — no LLM, scratch DB, reproducible.

The LLM-judged `icm bench-recall` shells out to the `claude` CLI as its answer
backend; that fails when run *inside* a Claude Code session (CLAUDECODE=1 →
nested claude exits 1). So it stays user-run (plain terminal). This harness
closes the gap that needs no model: does ICM's semantic recall surface the RIGHT
lesson for a PARAPHRASED query (near-zero surface-word overlap), and what does
the inject block cost?

Metric (same shape as portaw's _eval_recall, but targets ICM via its CLI):
  hit@k     : expected lesson's marker substring appears in top-k recall
  MRR       : 1/rank of the expected lesson (0 if absent) — ranking quality
  inj_tok   : tiktoken cl100k size of the top-k block (the cost side)

Scratch DB via `--db` so the real moat is never touched.

Usage: py bench/_icm_recall.py [-k 3]
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

import tiktoken

ICM = os.path.join(os.environ.get("LOCALAPPDATA", ""), "icm", "bin", "icm.exe")
ENC = tiktoken.get_encoding("cl100k_base")

# (topic, lesson content, marker substring that uniquely identifies it)
LESSONS = [
    ("tooling", "PowerShell: bare icm resolves to the Invoke-Command alias; call icm.exe or a full path", "Invoke-Command"),
    ("tooling", "rtk hook does not rewrite interpreter-prefixed py -m pytest; call rtk pytest explicitly", "rtk pytest"),
    ("tooling", "ast-grep --rewrite -U applies edits in place; omit -U to get a preview diff first", "preview diff"),
    ("tooling", "headroom-ai is a mixed python/rust maturin build; needs MSVC link.exe on Windows", "maturin"),
    ("arch", "Claude Code defers MCP tool definitions via ToolSearch so eager schema tax is near zero", "ToolSearch"),
    ("arch", "codegraph explore over-returns three files for a single-symbol lookup; use Read for one symbol", "single-symbol"),
    ("arch", "nah classify matches command prefix only so dual-use commands stay ASK by design", "dual-use"),
    ("arch", "git diff against the eighth ancestor fails on a repo with only two commits", "two commits"),
]

# (paraphrased query — minimal surface overlap, expected marker)
QUERIES = [
    ("my memory command keeps failing in the windows shell with an ambiguous parameter error", "Invoke-Command"),
    ("test output enters the context raw even though the shell compressor is enabled", "rtk pytest"),
    ("the structural codemod tool changed my source files without me confirming", "preview diff"),
    ("that token compressor will not build on my machine, the linker step errors out", "maturin"),
    ("do server tool schemas cost me tokens on every turn with this agent", "ToolSearch"),
    ("the code-graph tool dumps way too much when I only want one function", "single-symbol"),
    ("why does the permission guard keep prompting for commands that could be safe or dangerous", "dual-use"),
    ("a version-control diff against an old ancestor errored on a brand-new project", "two commits"),
]


def _icm(args: list[str], db: str) -> str:
    p = subprocess.run([ICM, *args, "--db", db], capture_output=True, text=True,
                       encoding="utf-8", errors="replace", timeout=120)
    return (p.stdout or "") + (p.stderr or "")


def _recall(query: str, db: str, k: int) -> list[dict]:
    out = _icm(["recall", query, "-l", str(k), "-f", "json"], db)
    try:
        data = json.loads(out)
    except json.JSONDecodeError:
        # find the JSON array if the binary prefixes a line
        s = out.find("[")
        data = json.loads(out[s:]) if s >= 0 else []
    return data if isinstance(data, list) else data.get("memories", [])


def main() -> int:
    k = 3
    if "-k" in sys.argv:
        k = int(sys.argv[sys.argv.index("-k") + 1])
    if not Path(ICM).exists():
        print(f"icm.exe not found at {ICM}", file=sys.stderr)
        return 2

    db = str(Path(tempfile.gettempdir()) / "icm_recall_bench.db")
    Path(db).unlink(missing_ok=True)
    for topic, content, _ in LESSONS:
        _icm(["store", "-t", topic, "-c", content, "-i", "high"], db)

    hits = 0
    rr_sum = 0.0
    tok_sum = 0
    rows = []
    for q, marker in QUERIES:
        mems = _recall(q, db, k)
        # token cost = the REAL inject block (toon = ICM's compact LLM-pipe format),
        # NOT the json dump (which carries 384-dim embedding arrays = a false ~17k).
        toon = _icm(["recall", q, "-l", str(k), "-f", "toon"], db)
        tok_sum += len(ENC.encode(toon, disallowed_special=()))
        rank = 0
        for i, m in enumerate(mems, 1):
            text = json.dumps(m)
            if marker.lower() in text.lower():
                rank = i
                break
        if rank:
            hits += 1
            rr_sum += 1.0 / rank
        rows.append((marker, rank, len(mems)))

    n = len(QUERIES)
    print(f"\nICM recall eval  (k={k}, scratch db, {len(LESSONS)} lessons / {n} paraphrase queries)\n")
    print(f"{'expected':<16}{'rank':>6}{'returned':>10}")
    for marker, rank, got in rows:
        print(f"{marker:<16}{(rank or '-'):>6}{got:>10}")
    print("-" * 32)
    print(f"hit@{k}   : {hits}/{n} = {100*hits/n:.1f}%")
    print(f"MRR     : {rr_sum/n:.3f}")
    print(f"inj_tok : {tok_sum} total / {tok_sum/n:.0f} avg per query")
    print(json.dumps({"hit_rate": hits / n, "mrr": rr_sum / n,
                      "avg_inj_tok": tok_sum / n, "k": k}))
    Path(db).unlink(missing_ok=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
