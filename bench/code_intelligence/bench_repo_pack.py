"""Bench repo-pack: compare Repomix vs code2prompt on a scoped fixture.

Both tools pack the same subdirectory with the same include pattern,
then we compare wall time and output size.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
OUT_DIR = ROOT / "bench" / "out"
RAW_DIR = OUT_DIR / "repo_pack_raw"


def utc_stamp() -> str:
    return datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")


def output_size(text: str) -> int:
    return len(text.encode("utf-8", errors="replace"))


def approx_tokens(text: str) -> int:
    return max(1, round(output_size(text) / 4))


def run(
    *,
    name: str,
    command: str | list[str],
    cwd: Path,
    timeout: int = 120,
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

    RAW_DIR.mkdir(parents=True, exist_ok=True)
    raw_path = RAW_DIR / f"{name}.log"
    raw_path.write_text(combined, encoding="utf-8", errors="replace")

    return {
        "name": name,
        "command": raw_command,
        "exit_code": exit_code,
        "wall_ms": wall_ms,
        "stdout_bytes": output_size(stdout),
        "stderr_bytes": output_size(stderr),
        "output_bytes": output_size(combined),
        "approx_output_tokens": approx_tokens(combined),
        "expect": expect,
        "correct": correct,
        "raw_log": str(raw_path),
    }


def main() -> int:
    stamp = utc_stamp()
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    RAW_DIR.mkdir(parents=True, exist_ok=True)

    results: list[dict[str, Any]] = []

    # Scoped fixture: pack paw/ with include=*.py, exclude=tests
    fixture = ROOT / "paw"
    include_pat = "*.py"

    # code2prompt via paw pack (which runs vendored binary)
    results.append(run(
        name="code2prompt_paw_scope",
        command=f'code2prompt "{fixture}" --include "{include_pat}" --token-format format',
        cwd=ROOT,
        timeout=60,
        expect="Token count",
    ))

    # code2prompt raw token format
    results.append(run(
        name="code2prompt_paw_scope_rawtokens",
        command=f'code2prompt "{fixture}" --include "{include_pat}" --token-format raw',
        cwd=ROOT,
        timeout=60,
        expect="Token count",
    ))

    # Repomix scoped + compressed via npx
    results.append(run(
        name="repomix_paw_scope",
        command=f'npx -y repomix@latest "{fixture}" --stdout --style markdown --compress --quiet --include "{include_pat}"',
        cwd=ROOT,
        timeout=120,
        expect="paw",
    ))

    # ── Output ──────────────────────────────────────────────────────────
    data: dict[str, Any] = {
        "stamp": stamp,
        "repo": str(ROOT),
        "fixture": str(fixture),
        "include": include_pat,
        "python": sys.version,
        "platform": sys.platform,
        "results": results,
    }

    json_path = OUT_DIR / f"repo_pack_bench_{stamp}.json"
    md_path = OUT_DIR / f"repo_pack_bench_{stamp}.md"
    data["json_path"] = str(json_path)
    json_path.write_text(json.dumps(data, indent=2), encoding="utf-8")

    rows = []
    for r in results:
        status = "PASS" if r["correct"] else "FAIL"
        rows.append(
            f"| {r['name']} | {r['wall_ms']:>7.0f} ms"
            f" | {r['approx_output_tokens']:>7d} tok"
            f" | {r['output_bytes']:>8d} bytes"
            f" | {status} |"
        )

    md = f"""# Repo-Pack Bench

Run stamp: `{stamp}`
Fixture: `{fixture}` (include: `{include_pat}`)

| Mode | Wall | Approx tok | Output bytes | Status |
| --- | ---: | ---: | ---: | ---: |
{chr(10).join(rows)}

## Findings

"""
    by_name = {r["name"]: r for r in results}

    c2p = by_name.get("code2prompt_paw_scope", {})
    c2p_raw = by_name.get("code2prompt_paw_scope_rawtokens", {})
    rm = by_name.get("repomix_paw_scope", {})

    finds = []
    if c2p.get("correct"):
        finds.append(
            f"- code2prompt packed {c2p['approx_output_tokens']} tok in {c2p['wall_ms']}ms"
        )
    if c2p_raw.get("correct"):
        finds.append(
            f"- code2prompt raw token count: {c2p_raw['approx_output_tokens']} tok"
            f" ({c2p_raw['wall_ms']}ms, machine-parsable)"
        )
    if rm.get("correct"):
        finds.append(
            f"- Repomix compressed: {rm['approx_output_tokens']} tok in {rm['wall_ms']}ms"
        )

    if c2p.get("correct") and rm.get("correct"):
        c2p_t = c2p["approx_output_tokens"]
        rm_t = rm["approx_output_tokens"]
        ratio = f"{rm_t / max(c2p_t, 1):.2f}x"
        finds.append(
            f"- Token ratio vs code2prompt: Repomix --compress = {ratio}"
        )

    if not finds:
        finds.append("No tools produced correct output on this fixture.")

    md += "\n".join(finds) + "\n\n"

    md += "## Raw Artifacts\n\n"
    md += f"- JSON: `{json_path}`\n"
    md += f"- Raw logs: `{RAW_DIR}`\n"

    md_path.write_text(md, encoding="utf-8")
    print(str(md_path))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
