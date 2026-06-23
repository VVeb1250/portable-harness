"""DeepSeek patch generation via the Anthropic-compatible endpoint.

Single shot: given the problem statement + oracle file contents (+ optional
plan from the Claude planner in the team arm), return the FULL updated content
of each file it changes. The caller computes the unified diff locally against
the base content (see run.py:_files_to_patch). This kills the apply-fail
confound: small models routinely emit diffs with wrong @@ line numbers or
slightly off context that `git apply` rejects — whole-file output sidesteps
that entirely, so we score logic, not diff-formatting luck. [STATUS §16.6 #1]
"""
from __future__ import annotations

import re

import requests

from . import config

_SYS = (
    "You fix bugs in real Python projects. For each file you change, output "
    "the ENTIRE updated file content verbatim between a line `@@@FILE <path>` "
    "and a line `@@@ENDFILE`, where <path> is the repo-root-relative path. "
    "Emit every line of the file, not just the changed lines. Do not output "
    "diffs, markdown fences, or prose. Only the @@@FILE/@@@ENDFILE blocks."
)

# one block per changed file: @@@FILE <path>\n<full content>\n@@@ENDFILE
_BLOCK = re.compile(
    r"@@@FILE[ \t]+(?P<path>.+?)[ \t]*\n(?P<body>.*?)\n?@@@ENDFILE",
    re.DOTALL,
)


def _strip_fence(body: str) -> str:
    """Defensively drop a ```lang ... ``` fence if the model added one anyway."""
    b = body.strip("\n")
    if b.startswith("```"):
        lines = b.split("\n")
        lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        b = "\n".join(lines)
    return b


def parse_files(text: str) -> dict[str, str]:
    """Extract {path: full_new_content} from the model's @@@FILE blocks."""
    return {
        m.group("path").strip(): _strip_fence(m.group("body"))
        for m in _BLOCK.finditer(text)
    }


def _files_block(oracle_files: dict[str, str]) -> str:
    parts = []
    for path, content in oracle_files.items():
        parts.append(f"=== {path} ===\n{content}")
    return "\n\n".join(parts)


def build_prompt(problem: str, oracle_files: dict[str, str], plan: str | None) -> str:
    blocks = [
        f"## Problem\n{problem}",
        f"## Files at the buggy commit\n{_files_block(oracle_files)}",
    ]
    if plan:
        blocks.append(f"## Implementation plan (follow it)\n{plan}")
    blocks.append(
        "## Task\nReturn the full updated content of each file you modify, "
        "each wrapped in `@@@FILE <path>` / `@@@ENDFILE` markers."
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


def generate_files(problem, oracle_files, plan=None) -> tuple[dict[str, str], dict]:
    """Return ({path: full_new_content}, usage). Caller diffs locally."""
    text, usage = call(build_prompt(problem, oracle_files, plan))
    return parse_files(text), usage
