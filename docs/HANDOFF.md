# Handoff -> Claude (blackboard + memory)

> Updated by Codex 2026-06-26 after Team Kernel mutation/evaluation layer v0.
> This file is the human-readable handoff. The live cross-host handoff is also
> in ICM blackboard run `claude-handoff-2026-06-26`.
> Read `docs/STATUS.md` section 0, then this file, before changing code.

## First Commands

Use PowerShell from `E:\portable-harness`.

```powershell
git status --short --branch
python -m paw blackboard read --project portable-harness --run-id claude-handoff-2026-06-26 --kind handoff --query "handoff mutation blackboard" --limit 10
python -m paw recall "portable-harness Team Kernel mutation blackboard memory" --host claude-code --limit 5
python -m paw curate --surface --limit 10
```

When writing back to the shared team thread:

```powershell
python -m paw blackboard write --project portable-harness --run-id claude-handoff-2026-06-26 --role claude --kind observation --content "<short status/update>" --importance medium
```

Use `icm.exe` explicitly for direct ICM commands on PowerShell; bare `icm` can
resolve to `Invoke-Command`.

## Current State

- `main` is clean at the time of this handoff.
- Latest local work: Team Kernel now supports
  `Planner -> Implementer -> optional Mutator -> Reviewer -> Evaluator`.
- The mutator is injected as `mutation_runner`; it records role `mutator`,
  kind `result`, and artifact references in the blackboard/result.
- Evaluator failures are already fed into the next planner/implementer context.
- Mock CLI emits a deterministic patch artifact (`mock-patch-1.diff`), so the
  blackboard path is testable without external models.
- **Real mutation now lands (2026-06-26).** `paw/mutation.py` applies the
  implementer's SEARCH/REPLACE handoff to the working tree transactionally, with
  backup + rollback + path-traversal guard + unified-diff artifact.
  `codex-deepseek` opts in via `paw team run --mutate {off,dry,apply}` (default
  `off`; `dry` = diff only, `apply` = write with backups). The remaining gap is a
  focused **verification** runner that tests the mutated tree and feeds the
  evaluator.

Verification already run by Codex:

```powershell
python -m compileall -q paw
python -m paw sets list
python -m paw sets show secure-agent
python -m pytest tests/test_team_kernel.py -q
python -m pytest tests/ -q
```

Most recent observed full suite: `173 passed, 4 subtests passed`.

## Memory / Blackboard Status

The memory stack is live enough to use, but not polished enough to trust without
human curation.

Working evidence:

- `python -m paw blackboard write/read` works with isolated SQLite and default
  ICM-backed storage.
- `python -m paw recall ... --host codex|claude-code` returns ICM memories plus
  committed repo conventions.
- `python -m paw reflect --host codex --dry-run --json` resolves the current
  Codex rollout transcript and extracts candidates.
- `~/.codex/hooks.json` contains Stop hook:
  `py -m paw reflect --capture --host codex`.
- Reflect watermarks exist under `~/.paw/state/reflect/`.
- `python -m paw curate --surface` sees pending items.

Known weakness:

- Live pending was noisy with expected TDD/diagnostic failures like
  `shell_command failed: ...F [100%] -> fixed by ...`. **Tuned 2026-06-26**:
  capture now suppresses harness-protocol errors, test-runner red-phase reports,
  and throwaway inline probes at source (`paw/reflection.py` `_HARNESS_NOISE` /
  `_TEST_FAIL` / `_PROBE_CMD`), plus a self-slip dismissal guard. Live pending
  drained 4→1. Still review before promoting — real assertion/env lessons do
  capture by design, and curation (Phase 3) remains the human-gated step.
- `docs/HANDOFF.md` previously said Codex Stop stdin was unverified. It is now
  at least partially exercised on this machine (hook configured, watermark
  present, pending exists), but stdin shape should still be treated as a decayable
  host contract.

Useful checks:

```powershell
icm.exe list -t pending --format json --no-embeddings --read-only
python -m paw reflect --host codex --dry-run --json
python -m paw curate --surface --limit 10
```

## What To Work On Next

Ordered next work:

1. ~~Implement a real mutation runner~~ **DONE 2026-06-26** — `paw/mutation.py`
   (`apply_to_tree`): transactional SEARCH/REPLACE apply with backup + rollback +
   path-traversal guard + unified-diff artifact; wired via
   `team_adapters.make_mutation_runner` and `paw team run --mutate {off,dry,apply}`.
2. **(now the top open item)** Implement a focused verification runner (affected
   tests, `compileall`, selected `paw verify`, or explicit command artifact) that
   runs against the **mutated** tree and feeds its output into the existing
   evaluator loop. This closes the mutate→verify→revise cycle.
3. Add CI that runs Python/runtime surfaces on `paw/**`, `tests/**`, and docs
   changes. Current GitHub workflow for bundle smoke is green, but path filters
   do not cover the latest Team Kernel code.
4. Tune memory capture/curation noise before treating live pending as durable
   project knowledge.
5. Keep benchmark cohorts frozen. Do not append to
   `bench/swe_probe/FROZEN_N8_2026-06-25.json`; create a new dated cohort for
   any new benchmark.

## Guardrails

- Do not edit/clean/reset/move benchmark files unless explicitly asked.
- Do not spawn hidden subagents inside measured benchmark arms.
- Do not claim uniform hook/security parity. Portable claim is decision/data
  protocol; execution/enforcement remains host-tiered.
- Use `python -m paw ...`; the Windows `py` launcher may be stale for this repo.
- Use `icm.exe`, not bare `icm`, in PowerShell.
- Use isolated `--db <temp.db>` for smoke tests unless intentionally writing to
  shared ICM.
- `pending` is not durable knowledge until curated/promoted.
