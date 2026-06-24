"""DeepSeek patch generation via the Anthropic-compatible endpoint.

Single shot: given the problem statement + oracle file contents (+ optional
plan from the Claude planner in the team arm), return SEARCH/REPLACE edits —
for each changed region, the exact existing lines and what to replace them
with. The caller applies them to the base content and computes the unified
diff locally (see run.py:_deepseek_arm), so a model's *logic* is scored, not
its diff arithmetic (apply-fail confound, STATUS §16.6 #1).

Why SEARCH/REPLACE, not whole-file:
  whole-file output makes the model re-emit every line of the file, so a
  1000-line file blows the output token ceiling and parses to nothing
  (STATUS §D: cli.py 1050L -> max_tokens stall). SEARCH/REPLACE emits only
  the changed regions, so output stays ~constant in the edit size, not the
  file size, and scales to large files. The apply-fail confound stays killed
  because we still diff locally — the model never writes @@ line numbers.
"""
from __future__ import annotations

import re

import requests

from . import config

_SYS = (
    "You fix bugs in real Python projects. Describe every change as one or "
    "more SEARCH/REPLACE edits. For each file you touch, output:\n"
    "@@@FILE <repo-root-relative path>\n"
    "<<<<<<< SEARCH\n"
    "<exact lines that currently exist in the file>\n"
    "=======\n"
    "<the lines that should replace them>\n"
    ">>>>>>> REPLACE\n"
    "@@@ENDFILE\n"
    "Rules: the SEARCH text must match the current file EXACTLY (whitespace "
    "and all) and be just large enough to be unique. Use several "
    "SEARCH/REPLACE blocks inside one @@@FILE for separate regions. To create "
    "a new file, leave the SEARCH section empty and put the full content in "
    "REPLACE. Output only @@@FILE blocks — no diffs, no markdown fences, no "
    "prose."
)

# one @@@FILE <path> ... @@@ENDFILE block per changed file
_FILE_BLOCK = re.compile(
    r"@@@FILE[ \t]+(?P<path>.+?)[ \t]*\n(?P<body>.*?)\n?@@@ENDFILE",
    re.DOTALL,
)

# one SEARCH/REPLACE edit inside a file block; markers must be on their own line
_SR = re.compile(
    r"<{5,}[ \t]*SEARCH[ \t]*\n(?P<search>.*?)\n?={5,}[ \t]*\n(?P<replace>.*?)\n?>{5,}[ \t]*REPLACE",
    re.DOTALL,
)


class EditError(Exception):
    """A SEARCH block did not match the base file content."""


def parse_edits(text: str) -> dict[str, list[tuple[str, str]]]:
    """Extract {path: [(search, replace), ...]} from the model's @@@FILE blocks."""
    out: dict[str, list[tuple[str, str]]] = {}
    for fm in _FILE_BLOCK.finditer(text):
        path = fm.group("path").strip()
        edits = [(m.group("search"), m.group("replace"))
                 for m in _SR.finditer(fm.group("body"))]
        if edits:
            out.setdefault(path, []).extend(edits)
    return out


def _flex_apply(content: str, search: str, replace: str) -> str | None:
    """Whole-line match of `search` in `content` ignoring trailing whitespace.

    Fallback for when an exact substring match fails only because the model
    dropped or added trailing spaces. Returns the edited content, or None if
    no whole-line window matches.
    """
    c_lines = content.splitlines(keepends=True)
    s_lines = [ln.rstrip() for ln in search.splitlines()]
    n = len(s_lines)
    if n == 0:
        return None
    offsets, pos = [], 0
    for ln in c_lines:
        offsets.append(pos)
        pos += len(ln)
    offsets.append(pos)
    for i in range(len(c_lines) - n + 1):
        window = [c_lines[i + j].rstrip("\r\n").rstrip() for j in range(n)]
        if window == s_lines:
            start, end = offsets[i], offsets[i + n]
            rep = replace
            if content[start:end].endswith("\n") and not rep.endswith("\n"):
                rep += "\n"
            return content[:start] + rep + content[end:]
    return None


def apply_edits(base: str, edits: list[tuple[str, str]]) -> str:
    """Apply (search, replace) edits to `base` in order; raise on a missed SEARCH.

    Exact substring match first (replace first occurrence), then a
    trailing-whitespace-flexible whole-line fallback. An empty SEARCH means
    create/overwrite the whole file with REPLACE.
    """
    content = base
    for search, replace in edits:
        if search.strip() == "":
            content = replace
            continue
        if content.count(search) >= 1:
            content = content.replace(search, replace, 1)
            continue
        flexed = _flex_apply(content, search, replace)
        if flexed is None:
            raise EditError(search)
        content = flexed
    return content


def _files_block(oracle_files: dict[str, str]) -> str:
    return "\n\n".join(f"=== {path} ===\n{content}"
                       for path, content in oracle_files.items())


def build_prompt(problem: str, oracle_files: dict[str, str], plan: str | None) -> str:
    blocks = [
        f"## Problem\n{problem}",
        f"## Files at the buggy commit\n{_files_block(oracle_files)}",
    ]
    if plan:
        blocks.append(f"## Implementation plan (follow it)\n{plan}")
    blocks.append(
        "## Task\nReturn SEARCH/REPLACE edits for each file you modify, using "
        "the `@@@FILE` / `<<<<<<< SEARCH` / `=======` / `>>>>>>> REPLACE` / "
        "`@@@ENDFILE` format from the system message."
    )
    return "\n\n".join(blocks)


def call(prompt: str, max_tokens: int = 16000) -> tuple[str, dict]:
    """Return (text, usage). usage = {input_tokens, output_tokens}."""
    r = requests.post(
        f"{config.DEEPSEEK_BASE}/v1/messages",
        headers={
            "x-api-key": config.deepseek_key(),
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        },
        json={
            "model": config.DEEPSEEK_MODEL,
            "max_tokens": max_tokens,
            "system": _SYS,
            "messages": [{"role": "user", "content": prompt}],
        },
        timeout=300,
    )
    r.raise_for_status()
    data = r.json()
    text = "".join(b.get("text", "") for b in data.get("content", []))
    usage = data.get("usage", {})
    return text, {
        "input_tokens": usage.get("input_tokens", 0),
        "output_tokens": usage.get("output_tokens", 0),
    }


def cost_usd(usage: dict) -> float:
    return (
        usage.get("input_tokens", 0) * config.PRICE_IN
        + usage.get("output_tokens", 0) * config.PRICE_OUT
    )


def generate_edits(problem, oracle_files, plan=None) -> tuple[dict[str, list[tuple[str, str]]], dict]:
    """Return ({path: [(search, replace), ...]}, usage). Caller applies + diffs."""
    text, usage = call(build_prompt(problem, oracle_files, plan))
    return parse_edits(text), usage
