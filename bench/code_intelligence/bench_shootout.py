"""Code-intelligence shootout: compare tools on the same queries.

Tools in the ring:
  rg             — lexical baseline (zero setup, fastest)
  ast-grep       — structural/AST baseline (zero setup, shape matching)
  codegraph      — SQLite knowledge graph (init then query)
  codebase-memory-mcp — Go binary code graph (index then search_graph)
  serena         — Python embedding index via uvx (index-only; no CLI query)

Each tool answers the same questions about a temp copy of this repo.
We measure wall-clock time, output byte size, and whether the answer
includes the expected symbol.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
OUT_DIR = ROOT / "bench" / "out"
WORK_DIR = ROOT / "bench" / "code_intelligence"
RAW_DIR = OUT_DIR / "code_intel_raw"

IGNORE_DIRS = {
    ".git",
    ".codegraph",
    ".serena",
    "bench",
    "node_modules",
    ".venv",
    "venv",
    "__pycache__",
    ".pytest_cache",
    ".mypy_cache",
    ".ruff_cache",
}

# ── Queries that every tool answers ──────────────────────────────────────────
# Each query: (name, pattern/rg-pattern, astgrep-pattern, expected_symbol)
# We use the same expected symbol check across all tools.

QUERIES: list[tuple[str, str, str, str]] = [
    # name,            rg-pattern,       astgrep-pattern,              expect
    ("find_teamkernel", "class TeamKernel", "class TeamKernel $$$BODY", "TeamKernel"),
    ("find_doctorreport","class DoctorReport","class DoctorReport $$$BODY","DoctorReport"),
    ("find_run_doctor",  "def run_doctor",   "def run_doctor $$$BODY",  "run_doctor"),
    ("find_route",       "def route",        "def route $$$BODY",       "route"),
    # rg does substring matching; ast-grep requires exact name — use the real
    # function name for ast-grep so both tools are compared fairly.
    ("find_parse_search","def parse_search", "def parse_search_output $$$BODY","parse_search_output"),
]

# ── Helpers (reused from bench/dev_foundation) ───────────────────────────────


def utc_stamp() -> str:
    return datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")


def output_size(text: str) -> int:
    return len(text.encode("utf-8", errors="replace"))


def approx_tokens(text: str) -> int:
    return max(1, round(output_size(text) / 4))


def make_worktree(stamp: str) -> Path:
    target = WORK_DIR / f"worktree-{stamp}"
    if target.exists():
        shutil.rmtree(target)

    def ignore(dir_path: str, names: list[str]) -> set[str]:
        ignored: set[str] = set()
        for name in names:
            if name in IGNORE_DIRS or name.endswith(".pyc"):
                ignored.add(name)
        return ignored

    shutil.copytree(ROOT, target, ignore=ignore)
    return target


def run(
    *,
    name: str,
    tool: str,
    command: str | list[str],
    cwd: Path,
    timeout: int = 60,
    expect: str | None = None,
) -> dict[str, Any]:
    started = time.perf_counter()
    shell = isinstance(command, str)
    raw_command = command if isinstance(command, str) else " ".join(command)
    try:
        proc = subprocess.run(
            command,
            cwd=str(cwd),
            shell=shell,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
        )
        exit_code = proc.returncode
        stdout = proc.stdout
        stderr = proc.stderr
    except FileNotFoundError as exc:
        exit_code = 127
        stdout = ""
        stderr = str(exc)
    except subprocess.TimeoutExpired as exc:
        exit_code = 124
        stdout = exc.stdout or ""
        stderr = (exc.stderr or "") + f"\nTIMEOUT after {timeout}s"

    wall_ms = round((time.perf_counter() - started) * 1000, 1)
    combined = f"{stdout}\n{stderr}"
    correct = (expect is not None) and (expect.lower() in combined.lower())
    zero_ok = exit_code == 0

    RAW_DIR.mkdir(parents=True, exist_ok=True)
    raw_path = RAW_DIR / f"{name}.log"
    raw_path.write_text(combined, encoding="utf-8", errors="replace")

    return {
        "name": name,
        "tool": tool,
        "command": raw_command,
        "exit_code": exit_code,
        "wall_ms": wall_ms,
        "stdout_bytes": output_size(stdout),
        "stderr_bytes": output_size(stderr),
        "output_bytes": output_size(combined),
        "approx_output_tokens": approx_tokens(combined),
        "expect": expect,
        "correct": correct,
        "zero_ok": zero_ok,
        "raw_log": str(raw_path),
        "first_lines": "\n".join(combined.splitlines()[:6]),
    }


def command_exists(name: str) -> bool:
    return shutil.which(name) is not None


def codebase_memory_path() -> Path | None:
    local = ROOT / "bench" / "_tools" / "codebase-memory-mcp" / "codebase-memory-mcp.exe"
    if local.exists():
        return local
    found = shutil.which("codebase-memory-mcp")
    return Path(found) if found else None


# ── Shot grouping helpers ────────────────────────────────────────────────────


def _fmt_ms(ms: float) -> str:
    return f"{ms:>8.0f}"


def _fmt_bytes(b: int) -> str:
    return f"{b:>8d}"


def make_comparison_table(results: list[dict[str, Any]]) -> str:
    """Compact comparison showing each query across all tools."""
    header = "| query | tool | ms | bytes | tokens | correct |"
    sep = "| --- | --- | ---: | ---: | ---: | ---: |"
    rows: list[str] = []
    for r in results:
        status = "PASS" if r["correct"] else "FAIL" if r["exit_code"] != 127 else "SKIP"
        rows.append(
            f"| {r['name']} | {r['tool']} | {_fmt_ms(r['wall_ms'])}"
            f" | {_fmt_bytes(r['output_bytes'])}"
            f" | {r['approx_output_tokens']:>7d}"
            f" | {status} |"
        )
    return "\n".join([header, sep, *rows])


def summarize(results: list[dict[str, Any]]) -> str:
    """Generate findings from the shootout results."""
    by_tool: dict[str, list[dict[str, Any]]] = {}
    for r in results:
        by_tool.setdefault(r["tool"], []).append(r)

    lines: list[str] = []
    for tool, tool_results in sorted(by_tool.items()):
        passed = sum(1 for r in tool_results if r["correct"])
        skipped = sum(1 for r in tool_results if r["exit_code"] == 127)
        total = len(tool_results)
        avg_ms = sum(r["wall_ms"] for r in tool_results) / max(total, 1)
        avg_tok = sum(r["approx_output_tokens"] for r in tool_results) / max(total, 1)
        avg_bytes = sum(r["output_bytes"] for r in tool_results) / max(total, 1)
        lines.append(
            f"- **{tool}**: {passed}/{total} correct"
            f" ({skipped} skipped)"
            f" — avg {avg_ms:.0f}ms, {avg_tok:.0f} tok, {avg_bytes:.0f} bytes"
        )

    # Cross-tool comparison: fastest tool per query
    lines.append("")
    lines.append("**Fastest per query:**")
    by_name: dict[str, list[dict[str, Any]]] = {}
    for r in results:
        by_name.setdefault(r["name"], []).append(r)
    for name, name_results in sorted(by_name.items()):
        correct_results = [r for r in name_results if r["correct"]]
        if not correct_results:
            lines.append(f"- {name}: no correct results")
            continue
        fastest = min(correct_results, key=lambda r: r["wall_ms"])
        lines.append(f"- {name}: **{fastest['tool']}** ({fastest['wall_ms']:.0f}ms)")
        # Show best output size among correct results
        smallest = min(correct_results, key=lambda r: r["output_bytes"])
        if smallest["tool"] != fastest["tool"]:
            lines.append(f"  smallest output: **{smallest['tool']}** ({smallest['output_bytes']} bytes)")

    return "\n".join(lines)


# ── Main ─────────────────────────────────────────────────────────────────────


def main() -> int:
    stamp = utc_stamp()
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    worktree = make_worktree(stamp)

    results: list[dict[str, Any]] = []

    # ── Phase 1: Indexing ─────────────────────────────────────────────────
    # Tools that need a pre-built index.

    # codegraph init
    results.append(run(
        name="codegraph_init",
        tool="codegraph",
        command=f'codegraph init "{worktree}"',
        cwd=ROOT,
        timeout=120,
        expect="Indexed",
    ))

    # codebase-memory-mcp index
    cbm = codebase_memory_path()
    cbm_project = worktree.as_posix().replace(":/", "-").replace("/", "-").replace("\\", "-").replace(":", "")
    cbm_payload = json.dumps({"repo_path": worktree.as_posix()})
    if cbm:
        results.append(run(
            name="cbm_index",
            tool="codebase-memory",
            command=[str(cbm), "cli", "index_repository", cbm_payload],
            cwd=ROOT,
            timeout=180,
            expect="indexed",
        ))
    else:
        results.append({
            "name": "cbm_index",
            "tool": "codebase-memory",
            "command": "codebase-memory-mcp cli index_repository",
            "exit_code": 127,
            "wall_ms": 0.0,
            "stdout_bytes": 0,
            "stderr_bytes": 0,
            "output_bytes": 0,
            "approx_output_tokens": 0,
            "expect": "indexed",
            "correct": False,
            "zero_ok": False,
            "raw_log": "",
            "first_lines": "codebase-memory-mcp not found",
        })

    # serena index
    if command_exists("uvx"):
        results.append(run(
            name="serena_index",
            tool="serena",
            command=f'uvx --from git+https://github.com/oraios/serena serena project index "{worktree}" --language python --timeout 10 --log-level WARNING',
            cwd=ROOT,
            timeout=180,
            expect="Indexed files",
        ))
    else:
        results.append({
            "name": "serena_index",
            "tool": "serena",
            "command": "uvx serena project index",
            "exit_code": 127,
            "wall_ms": 0.0,
            "stdout_bytes": 0,
            "stderr_bytes": 0,
            "output_bytes": 0,
            "approx_output_tokens": 0,
            "expect": "Indexed files",
            "correct": False,
            "zero_ok": False,
            "raw_log": "",
            "first_lines": "uvx not found",
        })

    # ── Phase 2: Queries ───────────────────────────────────────────────────
    # Each tool answers the same questions.

    search_dir = worktree / "paw"

    for q_name, rg_pat, ast_pat, expect in QUERIES:
        # rg — lexical baseline
        results.append(run(
            name=q_name,
            tool="rg",
            command=f'rg -n "{rg_pat}" "{search_dir}"',
            cwd=worktree,
            timeout=30,
            expect=expect,
        ))

        # ast-grep — structural baseline
        results.append(run(
            name=q_name,
            tool="ast-grep",
            command=f'ast-grep run --lang python -p "{ast_pat}" "{search_dir}"',
            cwd=worktree,
            timeout=30,
            expect=expect,
        ))

        # codegraph — graph query
        results.append(run(
            name=q_name,
            tool="codegraph",
            command=f'codegraph query -p "{worktree}" -j -l 20 {expect}',
            cwd=ROOT,
            timeout=45,
            expect=expect,
        ))

        # codebase-memory-mcp — search_graph
        if cbm:
            cbm_query = json.dumps({"project": cbm_project, "name_pattern": expect})
            results.append(run(
                name=q_name,
                tool="codebase-memory",
                command=[str(cbm), "cli", "search_graph", cbm_query],
                cwd=ROOT,
                timeout=45,
                expect=expect,
            ))
        else:
            results.append({
                "name": q_name,
                "tool": "codebase-memory",
                "command": "codebase-memory-mcp cli search_graph",
                "exit_code": 127,
                "wall_ms": 0.0,
                "stdout_bytes": 0,
                "stderr_bytes": 0,
                "output_bytes": 0,
                "approx_output_tokens": 0,
                "expect": expect,
                "correct": False,
                "zero_ok": False,
                "raw_log": "",
                "first_lines": "codebase-memory-mcp not found",
            })

    # ── Output ──────────────────────────────────────────────────────────────
    data: dict[str, Any] = {
        "stamp": stamp,
        "repo": str(ROOT),
        "worktree": str(worktree),
        "worktree_removed_after_run": True,
        "python": sys.version,
        "platform": sys.platform,
        "results": results,
    }

    json_path = OUT_DIR / f"code_intel_shootout_{stamp}.json"
    md_path = OUT_DIR / f"code_intel_shootout_{stamp}.md"
    data["json_path"] = str(json_path)
    json_path.write_text(json.dumps(data, indent=2), encoding="utf-8")

    md = f"""# Code-Intelligence Shootout

Run stamp: `{stamp}`
Repo: `{ROOT}`
Worktree: `{worktree}`

## Indexing Phase

| name | tool | ms | bytes | correct |
| --- | --- | ---: | ---: | ---: |
"""
    for r in results:
        if "index" in r["name"] or "Index" in r.get("first_lines", ""):
            status = "PASS" if r["correct"] else "FAIL"
            md += f"| {r['name']} | {r['tool']} | {_fmt_ms(r['wall_ms'])} | {_fmt_bytes(r['output_bytes'])} | {status} |\n"

    md += "\n## Query Phase\n\n"
    md += make_comparison_table(results) + "\n\n"

    md += "## Summary\n\n"
    md += summarize(results) + "\n\n"

    md += "## Raw Artifacts\n\n"
    md += f"- JSON: `{json_path}`\n"
    md += f"- Raw logs: `{RAW_DIR}`\n"

    md_path.write_text(md, encoding="utf-8")
    shutil.rmtree(worktree, ignore_errors=True)
    print(str(md_path))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
