"""Runtime role adapters for Team Kernel.

These adapters lift the proven `swe_probe` contracts without importing the
benchmark cohort or result machinery.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import tempfile
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Protocol

from paw.blackboard import BlackboardEntry
from paw.team_kernel import EvaluationResult, RoleAdapter, RoleOutput, TeamKernelContext

CODEX_BIN_ENV = "CODEX_BIN"
CODEX_TIMEOUT_ENV = "CODEX_TIMEOUT"
DEEPSEEK_KEY_ENV = "DEEPSEEK_API_KEY"
DEEPSEEK_BASE = "https://api.deepseek.com/anthropic"
DEEPSEEK_MODEL = "deepseek-v4-flash"
DEEPSEEK_SYSTEM = (
    "You are the implementer in a small software team. Follow the latest "
    "planner handoff and reviewer feedback. Return concise implementation "
    "notes, commands to run, and any patch/artifact references. Do not invent "
    "credentials or claim tests passed unless the context shows evidence."
)


class AdapterError(RuntimeError):
    """A role adapter failed before producing a usable handoff."""


class CompletedProcessLike(Protocol):
    returncode: int
    stdout: str
    stderr: str


SubprocessRunner = Callable[..., CompletedProcessLike]
UrlOpener = Callable[..., object]


@dataclass(frozen=True)
class TeamAdapterProfile:
    planner: RoleAdapter
    implementer: RoleAdapter
    reviewer: RoleAdapter
    evaluator: Callable[[TeamKernelContext], EvaluationResult]


class CodexCliTextAdapter:
    """Codex read-only planner/reviewer adapter using `codex exec --json -o`."""

    def __init__(
        self,
        *,
        repo: Path,
        codex_bin: str | None = None,
        timeout: int | None = None,
        runner: SubprocessRunner | None = None,
    ) -> None:
        self.repo = repo
        self.codex_bin = codex_bin or os.environ.get(CODEX_BIN_ENV, "codex")
        self.timeout = timeout or int(os.environ.get(CODEX_TIMEOUT_ENV, "900"))
        self.runner = runner or subprocess.run

    def planner(self, context: TeamKernelContext) -> RoleOutput:
        text, usage, turns = self._exec_text(_planner_prompt(context))
        return RoleOutput(content=text, artifact=_usage_artifact("codex", usage, turns))

    def reviewer(self, context: TeamKernelContext) -> RoleOutput:
        text, usage, turns = self._exec_text(_reviewer_prompt(context))
        return RoleOutput(content=_normalize_review_verdict(text), artifact=_usage_artifact("codex", usage, turns))

    def _exec_text(self, prompt: str) -> tuple[str, dict[str, object], int]:
        directory = Path(tempfile.mkdtemp(prefix="paw_cxread_"))
        try:
            output_path = directory / "_last.txt"
            command = (
                f'{self.codex_bin} exec -C "{self.repo}" -s read-only '
                f'--skip-git-repo-check --json -o "{output_path}" -'
            )
            result = self.runner(
                args=command,
                shell=True,
                input=prompt,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=self.timeout,
            )
            if result.returncode != 0:
                message = (result.stderr or result.stdout or "unknown codex error").strip()
                raise AdapterError(f"codex exec failed: {message[:300]}")
            usage, turns = parse_codex_events(result.stdout)
            text = (
                output_path.read_text(encoding="utf-8", errors="replace").strip()
                if output_path.exists()
                else ""
            )
            if not text:
                raise AdapterError("codex exec produced an empty final message.")
            return text, usage, turns
        finally:
            shutil.rmtree(directory, ignore_errors=True)


class DeepSeekTextAdapter:
    """DeepSeek Anthropic-compatible implementer adapter."""

    def __init__(
        self,
        *,
        base_url: str = DEEPSEEK_BASE,
        model: str = DEEPSEEK_MODEL,
        key_env: str = DEEPSEEK_KEY_ENV,
        max_tokens: int = 8_000,
        opener: UrlOpener | None = None,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.key_env = key_env
        self.max_tokens = max_tokens
        self.opener = opener or urllib.request.urlopen

    def implementer(self, context: TeamKernelContext) -> RoleOutput:
        key = os.environ.get(self.key_env, "").strip()
        if not key:
            raise AdapterError(f"set ${self.key_env} before running DeepSeek adapters")

        payload = {
            "model": self.model,
            "max_tokens": self.max_tokens,
            "system": DEEPSEEK_SYSTEM,
            "messages": [{"role": "user", "content": _implementer_prompt(context)}],
        }
        body = json.dumps(payload).encode("utf-8")
        request = urllib.request.Request(
            f"{self.base_url}/v1/messages",
            data=body,
            headers={
                "x-api-key": key,
                "anthropic-version": "2023-06-01",
                "content-type": "application/json",
            },
            method="POST",
        )
        try:
            with self.opener(request, timeout=300) as response:
                data = json.loads(response.read().decode("utf-8"))
        except (OSError, urllib.error.URLError, json.JSONDecodeError) as error:
            raise AdapterError(f"DeepSeek request failed: {error}") from error

        text = "".join(
            block.get("text", "")
            for block in data.get("content", [])
            if isinstance(block, dict)
        ).strip()
        if not text:
            raise AdapterError("DeepSeek returned an empty message.")
        usage = data.get("usage", {}) if isinstance(data.get("usage"), dict) else {}
        return RoleOutput(content=text, artifact=_usage_artifact("deepseek", usage, 0))


def make_mutation_runner(*, repo: Path, dry_run: bool = True) -> RoleAdapter:
    """A mutation_runner that turns the latest implementer handoff into real
    SEARCH/REPLACE edits under ``repo`` (transactional, backed up — see
    ``paw.mutation``). ``dry_run`` computes the diff without writing, so a team run
    is non-destructive by default; the caller opts into writing explicitly."""
    from paw.mutation import apply_to_tree

    def mutation_runner(context: TeamKernelContext) -> RoleOutput:
        latest = next(
            (e for e in reversed(context.entries) if e.role == "implementer"),
            None,
        )
        if latest is None:
            return RoleOutput(content="no implementer handoff to apply", importance="medium")
        result = apply_to_tree(latest.content, repo, dry_run=dry_run)
        verb = "would change" if dry_run else "changed"
        head = f"mutation {result.status}: {result.summary}"
        body = (f"\n{verb}: {', '.join(result.applied)}" if result.applied else "")
        return RoleOutput(
            content=head + body,
            artifact=(result.diff or None),
            importance="high" if result.ok else "medium",
        )

    return mutation_runner


def build_codex_deepseek_adapters(
    *, repo: Path, mutate: str = "off",
) -> tuple[TeamAdapterProfile, RoleAdapter | None]:
    """Build the real role adapters plus an optional mutation runner.

    ``mutate``: ``off`` (no file changes — handoff only), ``dry`` (compute the patch
    diff, write nothing), or ``apply`` (write with backup + rollback)."""
    codex = CodexCliTextAdapter(repo=repo)
    deepseek = DeepSeekTextAdapter()
    profile = TeamAdapterProfile(
        planner=codex.planner,
        implementer=deepseek.implementer,
        reviewer=codex.reviewer,
        evaluator=local_handoff_evaluator,
    )
    runner: RoleAdapter | None = None
    if mutate == "dry":
        runner = make_mutation_runner(repo=repo, dry_run=True)
    elif mutate == "apply":
        runner = make_mutation_runner(repo=repo, dry_run=False)
    return profile, runner


def local_handoff_evaluator(context: TeamKernelContext) -> EvaluationResult:
    return EvaluationResult(
        passed=True,
        summary="handoff completed; run project verification before committing",
    )


def parse_codex_events(stream: str) -> tuple[dict[str, object], int]:
    usage: dict[str, object] = {}
    turns = 0
    for line in stream.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue
        if event.get("type") == "turn.completed" and isinstance(event.get("usage"), dict):
            usage = event["usage"]
        item = event.get("item") if isinstance(event.get("item"), dict) else event
        if (
            event.get("type") in ("item.completed", "command_execution")
            and item.get("type") == "command_execution"
        ):
            turns += 1
    return usage, turns


def _planner_prompt(context: TeamKernelContext) -> str:
    return (
        "Produce a concise implementation plan for the task below. List exact "
        "files/functions to inspect or change and why. Do NOT write the full patch.\n\n"
        f"## Task\n{context.task}\n\n"
        f"## Prior team handoffs\n{_entries_block(context.entries)}"
    )


def _implementer_prompt(context: TeamKernelContext) -> str:
    return (
        f"## Task\n{context.task}\n\n"
        f"## Current iteration\n{context.iteration}\n\n"
        f"## Team handoffs\n{_entries_block(context.entries)}\n\n"
        "Return the implementation handoff for the reviewer."
    )


def _reviewer_prompt(context: TeamKernelContext) -> str:
    return (
        "You are a code reviewer. Decide whether the implementer handoff is "
        "ready for evaluation. Reply with `VERDICT: PASS` or `VERDICT: REVISE` "
        "on the first line, then concise actionable notes.\n\n"
        f"## Task\n{context.task}\n\n"
        f"## Team handoffs\n{_entries_block(context.entries)}"
    )


def _entries_block(entries: tuple[BlackboardEntry, ...]) -> str:
    if not entries:
        return "(none)"
    return "\n\n".join(
        f"[{entry.kind}] {entry.role}: {entry.content}"
        + (f"\nartifact: {entry.artifact}" if entry.artifact else "")
        for entry in entries
    )


def _normalize_review_verdict(text: str) -> str:
    clean = text.strip()
    first = clean.splitlines()[0].casefold() if clean else ""
    if first.startswith("verdict: pass"):
        return "PASS: " + "\n".join(clean.splitlines()[1:]).strip()
    if first.startswith("verdict: revise"):
        return "REVISE: " + "\n".join(clean.splitlines()[1:]).strip()
    return clean


def _usage_artifact(member: str, usage: dict[str, object], turns: int) -> str:
    payload: dict[str, object] = {"member": member, "usage": usage}
    if turns:
        payload["turns"] = turns
    return f"{member}:{json.dumps(payload, sort_keys=True, separators=(',', ':'))}"
