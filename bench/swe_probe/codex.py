"""Codex CLI patch generation via `codex exec` (non-interactive).

Codex runs on a ChatGPT-subscription seat (auth.json, chatgpt-login) — $0
marginal, automation OK (STATUS §G: `codex exec` is OpenAI-sanctioned for
CI/scripting; no clause bans programmatic sub-auth). This makes Codex the
first real 2nd heterogeneous member of the team.

Mechanics (recipe FEASIBILITY-VERIFIED 2026-06-24, STATUS §F.4):
  stage oracle_files in a throwaway git repo -> `codex exec -C <dir>` edits
  them in-place -> read the working-tree `git diff` back as the patch. Real
  token usage comes from the final `turn.completed` event (better than a
  tiktoken proxy); turns = number of command_execution items the agent ran.

Only the gold-touched paths are staged, so retrieval is oracle-equivalent and
the diff is naturally scoped (codex may spawn extra scratch files; we still
restrict `git diff` to the staged paths before scoring).
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import tempfile
from pathlib import Path

CODEX_BIN = os.environ.get("CODEX_BIN", "codex")
_TIMEOUT = int(os.environ.get("CODEX_TIMEOUT", "900"))


class CodexError(RuntimeError):
    """codex exec failed, or produced no diff."""


def _git(args: list[str], cwd: Path) -> str:
    r = subprocess.run(
        ["git", "-c", "user.email=probe@local", "-c", "user.name=probe", *args],
        cwd=cwd, capture_output=True, text=True, encoding="utf-8", errors="replace",
    )
    if r.returncode != 0:
        raise CodexError(f"git {args[0]} failed: {r.stderr.strip()[:200]}")
    return r.stdout


def _stage_repo(d: Path, oracle_files: dict[str, str]) -> None:
    """Write oracle files into a fresh git repo and commit the base state."""
    for path, content in oracle_files.items():
        f = d / path
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_text(content, encoding="utf-8")
    _git(["init", "-q"], d)
    _git(["add", "-A"], d)
    _git(["commit", "-q", "-m", "base"], d)


def build_prompt(problem: str, plan: str | None = None,
                 feedback: str | None = None) -> str:
    parts = [
        "Fix the bug described below by editing the files already in this "
        "repository. Make the minimal change needed to satisfy the described "
        "behavior. Do not add new test files or unrelated changes.",
        f"## Problem\n{problem}",
    ]
    if plan:
        parts.append(f"## Implementation plan (follow it)\n{plan}")
    if feedback:
        # agentic retry: prior failure signal so codex fixes the real failure.
        parts.append(
            "## Your previous attempt FAILED — fix it\n"
            "The test harness output for your last patch is below. Diagnose why "
            "the tests still fail and correct the change.\n\n" + feedback)
    return "\n\n".join(parts)


def _parse_events(stream: str) -> tuple[dict, int]:
    """(usage, turns) from the `--json` event stream.

    usage = last `turn.completed` event's usage dict (input_tokens,
    cached_input_tokens, output_tokens, reasoning_output_tokens). turns =
    count of completed command_execution items (the shell calls the agent ran).
    """
    usage: dict = {}
    turns = 0
    for line in stream.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            ev = json.loads(line)
        except json.JSONDecodeError:
            continue
        if ev.get("type") == "turn.completed":
            usage = ev.get("usage", {}) or usage
        # command items arrive as {"type":"item.completed","item":{"type":
        # "command_execution",...}}; tolerate a flattened shape too.
        item = ev.get("item") if isinstance(ev.get("item"), dict) else ev
        if (ev.get("type") in ("item.completed", "command_execution")
                and item.get("type") == "command_execution"):
            turns += 1
    return usage, turns


def generate_patch(problem: str, oracle_files: dict[str, str],
                   plan: str | None = None, feedback: str | None = None,
                   keep: bool = False) -> tuple[str, dict, int]:
    """Run codex on the staged oracle repo; return (patch, usage, turns).

    `patch` = working-tree `git diff` restricted to the staged (gold-touched)
    paths. Raises CodexError if codex exits non-zero.
    """
    d = Path(tempfile.mkdtemp(prefix="cxprobe_"))
    try:
        _stage_repo(d, oracle_files)
        prompt = build_prompt(problem, plan, feedback)
        # Prompt goes via stdin (`-`), never the command line: it dodges Windows
        # cmdline-length + quoting hell, and lets shell=True resolve the npm
        # `codex` shim through PATHEXT (codex.cmd) — a bare-name CreateProcess
        # can't (WinError 2). Only the controlled temp dir path is interpolated.
        cmd = (f'{CODEX_BIN} exec -C "{d}" -s workspace-write '
               f'--skip-git-repo-check --json -')
        r = subprocess.run(cmd, shell=True, input=prompt, capture_output=True,
                           text=True, encoding="utf-8", errors="replace",
                           timeout=_TIMEOUT)
        if r.returncode != 0:
            raise CodexError(
                f"codex exec rc={r.returncode}: {r.stderr.strip()[:300]}")
        usage, turns = _parse_events(r.stdout)
        # restrict to staged paths so codex scratch files never enter the patch
        patch = _git(["diff", "--", *oracle_files.keys()], d)
        return patch, usage, turns
    finally:
        if not keep:
            shutil.rmtree(d, ignore_errors=True)
