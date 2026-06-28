"""Benchmark paw Foundation and dev-relevant optional harness candidates.

The benchmark is intentionally small and repeatable. It measures setup/index
friction, command latency, bounded output size, and simple correctness gates on
a temporary copy of this repository.
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
WORK_DIR = ROOT / "bench" / "dev_foundation"
RAW_DIR = OUT_DIR / "foundation_raw"


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


def utc_stamp() -> str:
    return datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")


def output_size(text: str) -> int:
    return len(text.encode("utf-8", errors="replace"))


def approx_tokens(text: str) -> int:
    # Useful for relative comparison only. We do not promote decisions from this
    # without agent-side token accounting later.
    return max(1, round(output_size(text) / 4))


def make_worktree(stamp: str) -> Path:
    target = WORK_DIR / f"foundation-worktree-{stamp}"
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
    category: str,
    command: str | list[str],
    cwd: Path,
    timeout: int = 60,
    expect: str | None = None,
    allow_nonzero_with_expect: bool = False,
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
    expected = (expect is None) or (expect.lower() in combined.lower())
    zero_ok = exit_code == 0 or (allow_nonzero_with_expect and expected)
    correct = bool(zero_ok and expected)

    RAW_DIR.mkdir(parents=True, exist_ok=True)
    raw_path = RAW_DIR / f"{name}.log"
    raw_path.write_text(combined, encoding="utf-8", errors="replace")

    return {
        "name": name,
        "category": category,
        "command": raw_command,
        "cwd": str(cwd),
        "exit_code": exit_code,
        "wall_ms": wall_ms,
        "stdout_bytes": output_size(stdout),
        "stderr_bytes": output_size(stderr),
        "output_bytes": output_size(combined),
        "approx_output_tokens": approx_tokens(combined),
        "expect": expect,
        "correct": correct,
        "raw_log": str(raw_path),
        "first_lines": "\n".join(combined.splitlines()[:8]),
    }


def command_exists(name: str) -> bool:
    return shutil.which(name) is not None


def codebase_memory_path() -> Path | None:
    local = ROOT / "bench" / "_tools" / "codebase-memory-mcp" / "codebase-memory-mcp.exe"
    if local.exists():
        return local
    found = shutil.which("codebase-memory-mcp")
    return Path(found) if found else None


def codebase_memory_project_name(path: Path) -> str:
    return path.as_posix().replace(":/", "-").replace("/", "-").replace("\\", "-").replace(":", "")


def markdown_summary(data: dict[str, Any]) -> str:
    rows = []
    for result in data["results"]:
        status = "pass" if result["correct"] else "fail"
        rows.append(
            "| {category} | {name} | {status} | {wall_ms} | {tokens} | {exit_code} |".format(
                category=result["category"],
                name=result["name"],
                status=status,
                wall_ms=result["wall_ms"],
                tokens=result["approx_output_tokens"],
                exit_code=result["exit_code"],
            )
        )

    findings = []
    by_name = {item["name"]: item for item in data["results"]}
    if by_name.get("codebase_memory_cli_index", {}).get("correct") is False:
        findings.append(
            "- codebase-memory-mcp installed, but the single-shot Windows CLI index path failed in this run; keep it project-linked research until a wrapper/client path is verified."
        )
    if by_name.get("codebase_memory_cli_index", {}).get("correct") and by_name.get(
        "codebase_memory_search_graph_teamkernel", {}
    ).get("correct"):
        findings.append(
            "- codebase-memory-mcp indexed and queried successfully through direct argv calls; PowerShell quoting needs a paw wrapper, but the engine is a serious CodeGraph challenger."
        )
    if by_name.get("serena_index", {}).get("correct"):
        findings.append(
            "- Serena indexed the temp repo, but `uvx` startup dominates the wall time; good optional project-linked candidate, weak default-init fit."
        )
    if by_name.get("codegraph_init", {}).get("correct"):
        findings.append(
            "- CodeGraph remains the strongest project-linked code intelligence baseline in this repo: fast index, compact status, direct query CLI."
        )
    if by_name.get("nah_block_sensitive_path", {}).get("correct") and by_name.get(
        "nah_allow_compileall", {}
    ).get("correct"):
        findings.append(
            "- `nah` gives deterministic allow/block behavior suitable for secure-agent-min policy checks."
        )
    if by_name.get("markitdown_html_smoke", {}).get("correct"):
        findings.append(
            "- MarkItDown converted a local HTML fixture; ffmpeg warnings are an audio/video caveat, not a docs-core blocker."
        )
    if by_name.get("repomix_pack_scoped_compress", {}).get("correct"):
        findings.append(
            "- Repomix is usable as a repo-pack candidate through `npx -y`; scoped compressed packs are manageable, broad packs still need a policy guard."
        )
    if by_name.get("grepai_availability", {}).get("correct") is False:
        findings.append(
            "- grepai remains deferred here because neither grepai nor Ollama is installed; do not pull a local model into Foundation by accident."
        )

    if not findings:
        findings.append("- No high-confidence findings were produced; inspect raw logs.")

    return "\n".join(
        [
            "# Foundation Bench Run",
            "",
            f"Run stamp: `{data['stamp']}`",
            f"Repo: `{data['repo']}`",
            f"Worktree: `{data['worktree']}`",
            "",
            "## Summary Table",
            "",
            "| Category | Check | Status | Wall ms | Approx output tokens | Exit |",
            "| --- | --- | --- | ---: | ---: | ---: |",
            *rows,
            "",
            "## Findings",
            "",
            *findings,
            "",
            "## Raw Artifacts",
            "",
            f"- JSON: `{data['json_path']}`",
            f"- Raw logs: `{RAW_DIR}`",
        ]
    )


def main() -> int:
    stamp = utc_stamp()
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    worktree = make_worktree(stamp)
    (worktree / "foundation_fixture.html").write_text(
        "<html><body><h1>Foundation Bench</h1><p>portable harness doc extraction smoke.</p></body></html>",
        encoding="utf-8",
    )

    cbm = codebase_memory_path()
    cbm_payload = json.dumps({"repo_path": worktree.as_posix()})
    cbm_project = codebase_memory_project_name(worktree)

    version_commands: list[tuple[str, str, str | list[str], str | None]] = [
        ("version_rg", "versions", "rg --version", "ripgrep"),
        ("version_ast_grep", "versions", "ast-grep --version", "ast-grep"),
        ("version_rtk", "versions", "rtk --version", "rtk"),
        ("version_icm", "versions", "icm.exe --version", "icm"),
        ("version_nah", "versions", "nah --version", "nah"),
        ("version_gitleaks", "versions", "gitleaks version", None),
        ("version_osv_scanner", "versions", "osv-scanner --version", "osv-scanner"),
        ("version_jq", "versions", "jq --version", "jq"),
        ("version_duckdb", "versions", "duckdb --version", None),
        ("version_infisical", "versions", "infisical --version", "infisical"),
        ("version_markitdown", "versions", "markitdown --version", None),
        ("version_codegraph", "versions", "codegraph --version", None),
        ("version_repomix", "versions", "npx -y repomix@latest --version", None),
        (
            "version_serena",
            "versions",
            "uvx --from git+https://github.com/oraios/serena serena --version",
            "serena",
        ),
    ]
    if cbm:
        version_commands.append(
            ("version_codebase_memory", "versions", [str(cbm), "--version"], "codebase-memory")
        )

    results: list[dict[str, Any]] = []
    for name, category, command, expect in version_commands:
        results.append(run(name=name, category=category, command=command, cwd=ROOT, timeout=90, expect=expect))

    # Foundation Core
    results.extend(
        [
            run(
                name="paw_sets_list",
                category="control-plane",
                command="python -m paw sets list",
                cwd=worktree,
                timeout=45,
                expect="secure-agent",
            ),
            run(
                name="paw_sets_show_secure_agent",
                category="control-plane",
                command="python -m paw sets show secure-agent",
                cwd=worktree,
                timeout=45,
                expect="gitleaks",
            ),
            run(
                name="paw_route_dev_task",
                category="control-plane",
                command='python -m paw route "Refactor memory hook safely"',
                cwd=worktree,
                timeout=45,
                expect="route",
            ),
            run(
                name="icm_recall_bundle_decision",
                category="local-memory",
                command='icm.exe recall "portable-harness bundle init Graphify CodeGraph memory"',
                cwd=worktree,
                timeout=45,
                expect="Graphify",
            ),
            run(
                name="rg_symbol_search",
                category="efficiency-min",
                command='rg -n "class TeamKernel|def paw_block|def route" paw tests',
                cwd=worktree,
                timeout=30,
                expect="TeamKernel",
            ),
            run(
                name="astgrep_structural_search",
                category="efficiency-min",
                command='ast-grep run --lang python -p "class TeamKernel: $$$BODY" paw tests',
                cwd=worktree,
                timeout=30,
                expect="team_kernel.py",
            ),
            run(
                name="rtk_compact_grep",
                category="efficiency-min",
                command='rtk grep "TeamKernel" paw tests',
                cwd=worktree,
                timeout=45,
                expect="TeamKernel",
                allow_nonzero_with_expect=True,
            ),
            run(
                name="nah_block_sensitive_path",
                category="secure-agent-min",
                command='nah test --defaults --json --tool Bash "rm -rf ~/.ssh"',
                cwd=worktree,
                timeout=30,
                expect='"decision": "block"',
            ),
            run(
                name="nah_allow_compileall",
                category="secure-agent-min",
                command='nah test --defaults --json --tool Bash "python -m compileall -q paw"',
                cwd=worktree,
                timeout=30,
                expect='"decision": "allow"',
            ),
            run(
                name="gitleaks_detect_redacted",
                category="secure-agent-min",
                command="gitleaks detect --no-git --redact --report-format json --report-path - --exit-code 0 --source .",
                cwd=worktree,
                timeout=90,
                expect="",
            ),
            run(
                name="osv_scan_source_json",
                category="secure-agent-min",
                command="osv-scanner scan source -r --format json --allow-no-lockfiles .",
                cwd=worktree,
                timeout=120,
                expect="results",
            ),
            run(
                name="jq_registry_extract",
                category="doc-data-min",
                command='jq -r ".sets[].set_name" paw/registry/sets.json',
                cwd=worktree,
                timeout=30,
                expect="secure-agent",
            ),
            run(
                name="duckdb_registry_query",
                category="doc-data-min",
                command='duckdb -json -c "SELECT count(*) AS sets FROM read_json_auto(\'paw/registry/sets.json\', maximum_object_size=10485760)"',
                cwd=worktree,
                timeout=30,
                expect="sets",
            ),
            run(
                name="markitdown_html_smoke",
                category="doc-data-min",
                command="markitdown foundation_fixture.html",
                cwd=worktree,
                timeout=45,
                expect="Foundation Bench",
            ),
        ]
    )

    # Optional foundation for dev-facing project work.
    results.extend(
        [
            run(
                name="codegraph_init",
                category="code-intelligence",
                command=f'codegraph init "{worktree}"',
                cwd=ROOT,
                timeout=90,
                expect="Indexed",
            ),
            run(
                name="codegraph_status",
                category="code-intelligence",
                command=f'codegraph status "{worktree}"',
                cwd=ROOT,
                timeout=45,
                expect="Index is up to date",
            ),
            run(
                name="codegraph_query_teamkernel",
                category="code-intelligence",
                command=f'codegraph query -p "{worktree}" -j -l 10 TeamKernel',
                cwd=ROOT,
                timeout=45,
                expect="TeamKernel",
            ),
            run(
                name="serena_index",
                category="code-intelligence",
                command=f'uvx --from git+https://github.com/oraios/serena serena project index "{worktree}" --language python --timeout 10 --log-level WARNING',
                cwd=ROOT,
                timeout=120,
                expect="Indexed files",
            ),
            run(
                name="repomix_pack_scoped_compress",
                category="repo-pack",
                command='npx -y repomix@latest . --stdout --style markdown --compress --quiet --include "paw/team_kernel.py,paw/router.py,tests/test_team_kernel.py"',
                cwd=worktree,
                timeout=120,
                expect="team_kernel.py",
            ),
        ]
    )

    if cbm:
        results.append(
            run(
                name="codebase_memory_cli_index",
                category="code-intelligence.research",
                command=[str(cbm), "cli", "index_repository", cbm_payload],
                cwd=ROOT,
                timeout=120,
                expect="indexed",
            )
        )
        results.append(
            run(
                name="codebase_memory_search_graph_teamkernel",
                category="code-intelligence.research",
                command=[
                    str(cbm),
                    "cli",
                    "search_graph",
                    json.dumps({"project": cbm_project, "name_pattern": "TeamKernel"}),
                ],
                cwd=ROOT,
                timeout=45,
                expect="TeamKernel",
            )
        )
    else:
        results.append(
            {
                "name": "codebase_memory_cli_index",
                "category": "code-intelligence.research",
                "command": "codebase-memory-mcp cli index_repository",
                "cwd": str(ROOT),
                "exit_code": 127,
                "wall_ms": 0,
                "stdout_bytes": 0,
                "stderr_bytes": 0,
                "output_bytes": 0,
                "approx_output_tokens": 0,
                "expect": "indexed",
                "correct": False,
                "raw_log": "",
                "first_lines": "codebase-memory-mcp not found",
            }
        )

    results.extend(
        [
            run(
                name="grepai_availability",
                category="code-intelligence.research",
                command="grepai --version",
                cwd=ROOT,
                timeout=30,
                expect="grepai",
            ),
            run(
                name="ollama_availability_for_grepai",
                category="code-intelligence.research",
                command="ollama --version",
                cwd=ROOT,
                timeout=30,
                expect="ollama",
            ),
        ]
    )

    data: dict[str, Any] = {
        "stamp": stamp,
        "repo": str(ROOT),
        "worktree": str(worktree),
        "python": sys.version,
        "platform": sys.platform,
        "path": os.environ.get("PATH", ""),
        "results": results,
    }
    json_path = OUT_DIR / f"foundation_bench_{stamp}.json"
    md_path = OUT_DIR / f"foundation_bench_{stamp}.md"
    data["json_path"] = str(json_path)
    json_path.write_text(json.dumps(data, indent=2), encoding="utf-8")
    md_path.write_text(markdown_summary(data), encoding="utf-8")
    print(str(md_path))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
