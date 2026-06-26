# portable-harness — Codex operating guide

This repository is a personal, cross-host agent-team substrate: curated tools,
token reduction, and shared memory across heterogeneous agents. It is not a
general-purpose harness competing with ECC.

## Start here

Before non-trivial work:

1. Read `CLAUDE.md` for the owner's working mindset and current context-mode
   routing experiment.
2. Read `docs/STATUS.md`, especially sections A and D, for current truth and
   active benchmark work.
3. Run `git status --short --branch`. Treat existing changes as another
   agent's work unless the user explicitly puts them in scope.
4. **Resuming the memory system?** Read `docs/HANDOFF.md` — the capture →
   curate → recall loop is live on Codex too; your first task is to verify your
   own capture fires (the Codex Stop-stdin shape is the one unverified contract).

`bundle/AGENTS.md` is the canonical future linker source. This root file is the
active Codex bridge while `paw link` is still WIP.

## Current work boundary

- Claude may be running `bench/swe_probe/` experiments concurrently.
- Do not edit, clean, reset, move, or reformat dirty benchmark files unless the
  user explicitly asks.
- Do not spawn subagents inside a measured solo/team arm unless the benchmark
  protocol explicitly defines them. Hidden fan-out invalidates cost and turn
  comparisons.
- Read-only exploration and review may use subagents when requested; summarize
  evidence back to the parent rather than dumping logs.

## Operating principles

- Reuse before rebuilding. Search primary sources and existing packages before
  adding custom machinery.
- Verify load-bearing facts, versions, prices, policies, and APIs before
  asserting them.
- Measure token and quality deltas; do not lock decisions from vibes.
- Keep host wiring replaceable and record assumptions that can decay.
- Prefer CLI or hooks over MCP when capability is equivalent. Keep this
  project's active MCP set at three or fewer.
- Never expose secrets. Use environment variables or a secret manager.
- Preserve user config and unrelated worktree changes.

## Codex harness

- Shared memory target: ICM CLI. On PowerShell call `icm.exe` explicitly
  because `icm` may resolve to `Invoke-Command`.
- Before non-trivial work, recall relevant project facts with
  `icm.exe recall "<question>"`.
- Store a durable correction or failure immediately with
  `icm.exe store -t mistakes -c "trigger -> fix" -i high -k "<term>"`.
  Do not store secrets, raw transcripts, or temporary benchmark noise.
- Security tools available on this machine: `nah`, `gitleaks`, `osv-scanner`,
  and `infisical`. Codex enforcement is sandbox/instruction based; do not claim
  Claude Code hook parity.
- Use `python -m paw ...` in this repository. The Windows `py` launcher may be
  stale even when `python` is healthy.

## context-mode routing

The project config exposes context-mode for the live routing experiment.
Route only when the output would otherwise be bulky:

- Analyze or summarize a large file with `ctx_execute_file`.
- Run/filter verbose commands with `ctx_execute` or `ctx_batch_execute`.
- Fetch and search large web/docs with `ctx_fetch_and_index` then `ctx_search`.
- Use normal shell/read for short output, exact read-to-edit work, and small
  diffs.

This experiment has a large static token cost. Follow the keep/kill gate in
`docs/STATUS.md`; do not silently broaden it to other repositories.

## Verification

For changes to the Python package:

```powershell
python -m compileall -q paw
python -m paw sets list
python -m paw sets show secure-agent
```

Run focused benchmark commands only when their fixtures and external runtime
requirements are understood. Review `git diff` before any commit or push.
