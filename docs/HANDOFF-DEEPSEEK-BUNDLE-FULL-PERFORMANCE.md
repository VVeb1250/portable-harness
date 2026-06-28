# Handoff: Bundle Full-Performance Finish

Audience: Claude Code driving a mid-tier implementer such as DeepSeek through a
dynamic workflow.

Repo: `E:\portable-harness`

## Objective

Finish the remaining bundle full-performance work without broadening the
project scope:

1. complete `paw init` / `paw doctor`;
2. wire the code-intelligence shootout runner;
3. polish the codebase-memory wrapper output;
4. add repo-pack scope guard and Repomix/code2prompt bench;
5. add cross-OS CI smoke for default foundation sets;
6. leave grepai deferred unless the user explicitly installs Ollama/local
   embeddings;
7. keep `efficiency-starter` cleanup for last, after migration safety is proven.

## First Commands

Use PowerShell from `E:\portable-harness`.

```powershell
git status --short --branch
icm.exe recall "portable-harness bundle full-performance paw init doctor codebase-memory wrapper shootout"
Get-Content -Raw CLAUDE.md
Get-Content -Raw AGENTS.md
Get-Content -Raw docs\STATUS.md
Get-Content -Raw docs\NO-DAEMON-BASELINE-BACKLOG.md
python -m paw doctor --host codex
python -m paw codebase-memory project-name tests
```

Use `python -m paw ...`; do not use stale `py` launcher assumptions. Use
`icm.exe`, not bare `icm`, in PowerShell.

## Current State

Already implemented by Codex:

- `paw init` / `paw doctor` first slice:
  - [paw/doctor.py](../paw/doctor.py)
  - [tests/test_doctor.py](../tests/test_doctor.py)
  - CLI wired in [paw/__main__.py](../paw/__main__.py)
  - Checks default-init core: `local-memory`, `efficiency-min`,
    `secure-agent`, `doc-data-min`.
  - Reports missing installable tools with registry install hints.
  - Reads linker ledger and flags hosts needing restart/reload after MCP/PATH
    wiring.
- Windows-safe `codebase-memory-mcp` wrapper first slice:
  - [paw/codebase_memory.py](../paw/codebase_memory.py)
  - [tests/test_codebase_memory.py](../tests/test_codebase_memory.py)
  - CLI: `python -m paw codebase-memory project-name|index|search`
  - Builds JSON payloads in Python and calls the binary via argv, avoiding
    PowerShell JSON quoting.
  - Local smoke indexed `tests/` as `E-portable-harness-tests` and found
    `DoctorTests`.

Latest focused verification known good:

```powershell
python -m pytest -q tests/test_doctor.py tests/test_codebase_memory.py tests/test_catalog.py tests/test_linker.py
python -m compileall -q paw
python -m paw doctor --host codex
python -m paw codebase-memory project-name tests
```

Expected focused test result: `55 passed, 18 subtests passed`.

## Dynamic Workflow

Use Claude Code as planner/reviewer and DeepSeek as implementer for bounded
patches. Do not ask DeepSeek to decide project direction from scratch. Give it
one lane at a time, exact files, and a verification command.

Suggested loop:

1. Claude reads current files and writes a short implementation brief.
2. DeepSeek proposes a small patch for one lane only.
3. Claude reviews for scope, Windows behavior, and repo conventions.
4. Apply only if the patch is local and testable.
5. Run focused tests.
6. Update `docs/STATUS.md` and `docs/NO-DAEMON-BASELINE-BACKLOG.md` only after
   the slice is actually verified.

Do not spawn hidden agents inside measured benchmark arms. For this handoff,
parallelism is only for independent repo reads or independent implementation
lanes with non-overlapping write surfaces.

## Lane Matrix

| Lane | Parallel? | Write Surface | Risk | Verification |
| --- | --- | --- | --- | --- |
| Doctor completion | No, do first | `paw/doctor.py`, `tests/test_doctor.py`, maybe `paw/__main__.py` | Medium | `pytest tests/test_doctor.py`; `python -m paw doctor --host codex --json` |
| codebase-memory output polish | Yes after doctor | `paw/codebase_memory.py`, `tests/test_codebase_memory.py`, maybe CLI rendering in `paw/__main__.py` | Low | `pytest tests/test_codebase_memory.py`; real `index tests` + bounded search |
| Code-intelligence shootout runner | After wrapper polish | `bench/dev_foundation/` or new `bench/code_intelligence/`, docs | Medium | runner creates JSON+MD artifact on temp worktree; no dirty main tree |
| Repo-pack scope guard | Yes, separate | `paw/__main__.py` or new `paw/repo_pack.py`, tests | Medium | unit tests for guard + safe small `paw pack` smoke |
| Cross-OS CI smoke | After default commands stable | `.github/workflows/*`, scripts | Medium | actionlint if available; local command syntax review |
| grepai bench | Gated | bench docs only until Ollama installed | Medium | do not install Ollama unless user explicitly asks |
| `efficiency-starter` cleanup | Last | registry/docs/managed-block logic | High | migration audit + tests; no stranded old installs |

## Lane Details

### 1. Complete `paw doctor`

Goal: make one command answer "is paw basically working?"

Already live:

- default core binary checks;
- install hints;
- ledger-linked host restart/reload hints.

Remaining:

- ICM topics / pending count summary;
- memory hook config coverage for Claude/Codex;
- mesh members and stale sessions;
- richer linker drift summary per linked set.

Implementation guidance:

- Keep doctor read-only.
- Do not parse huge ICM output into prompt; query bounded counts/summaries.
- Prefer small dataclasses like the existing `ToolCheck`, `SetCheck`,
  `HostCheck`.
- Tests first. Mock external commands where possible.
- JSON output must remain structured and stable.

Suggested DeepSeek prompt:

```text
Implement the next read-only paw doctor slice.

Repo: E:\portable-harness.
Files in scope: paw/doctor.py, tests/test_doctor.py, maybe paw/__main__.py.
Do not edit registry or unrelated docs.

Current doctor already checks default-init tools and host restart hints.
Add bounded memory/mesh/hook visibility:
- pending_count if ICM can be queried safely;
- hook config presence for claude-code and codex;
- mesh active/stale member summary if local mesh state exists;
- preserve existing JSON shape by adding new top-level sections rather than renaming old fields.

Write tests first. Mock subprocess/ICM filesystem where needed.
Verification: python -m pytest -q tests/test_doctor.py && python -m compileall -q paw.
```

### 2. Polish `codebase-memory` wrapper

Goal: wrapper output should be safe for agents and reusable by the shootout.

Already live:

- `project-name`;
- `index`;
- `search`;
- direct argv JSON payload.

Remaining:

- add `--limit` or output filtering for search results;
- optionally parse JSON stdout and print compact table/text by default;
- keep `--json` mode for full structured output;
- expose a reusable function for the shootout runner.

Suggested DeepSeek prompt:

```text
Polish the codebase-memory wrapper output.

Files in scope: paw/codebase_memory.py, paw/__main__.py, tests/test_codebase_memory.py.
Do not change the upstream binary or benchmark artifacts.

Add bounded output for `python -m paw codebase-memory search`:
- parse JSON stdout when possible;
- default human output should show total and compact rows: name, label, file_path, qualified_name;
- support --limit with default 10;
- --json should still emit the raw wrapper result structure.

Tests first. Mock subprocess.run outputs.
Verification: python -m pytest -q tests/test_codebase_memory.py.
```

### 3. Code-Intelligence Shootout

Goal: compare CodeGraph, codebase-memory-mcp, Serena, grepai, and
`rg`/`ast-grep` baseline on real tasks. grepai is skipped/deferred unless
Ollama/local embeddings are intentionally installed.

Recommended artifact:

- new runner under `bench/code_intelligence/` or extend
  `bench/dev_foundation/bench_foundation.py` only if that stays tidy;
- write JSON and Markdown under `bench/out/`;
- use temp copy/worktree so project-linked indexes do not dirty main tree.

Required tasks:

- find callers/usages of a known symbol;
- trace route/handler style relationship where available;
- impact query: "what changes if symbol X changes?";
- config trace;
- architecture query;
- exact baseline with `rg`;
- structural baseline with `ast-grep`.

Metrics:

- correctness;
- wall time;
- file/tool calls where measurable;
- approx output tokens;
- setup/index time;
- install friction notes;
- network/privacy notes;
- cleanup/unlink behavior.

DeepSeek should not invent numbers. If a metric is not measurable, mark it
`unknown` or `not_collected`.

### 4. Repo-Pack Scope Guard + Shootout

Goal: prevent accidental huge whole-repo packs before comparing Repomix vs
code2prompt.

Implementation order:

1. Add guard to existing `paw pack` or extract to `paw/repo_pack.py`.
2. Require at least one of:
   - explicit `--include`;
   - `--diff`;
   - path that is not repo root;
   - explicit override such as `--allow-large`.
3. Add tests for refusing broad root pack.
4. Then run Repomix vs code2prompt on scoped fixture.

Do not dump full repo pack into chat.

### 5. Cross-OS CI Smoke

Goal: back default-init portability claims with CI.

Scope:

- `efficiency-min`: `rg`, `ast-grep`, optional `rtk` version/help where
  installable;
- `secure-agent`: `nah`, `gitleaks`, `osv-scanner`, `infisical` version/help
  smoke;
- `doc-data-min`: `jq`, `duckdb`, `markitdown` tiny functional smoke.

Keep output compact. Prefer install/version/tiny behavior probes over broad
scans. Do not require secrets.

## Guardrails

- Preserve unrelated dirty worktree changes. There are many existing modified
  and untracked files; treat them as user/other-agent work.
- Do not edit, clean, reset, move, or reformat benchmark files unless the lane
  explicitly requires it.
- Do not install Ollama, embeddings, or new heavy tools without explicit user
  approval.
- Networked tools are read-only by default. Do not push, publish, merge, or
  alter third-party resources.
- Do not promote `efficiency-starter` cleanup before the migration audit.
- Keep `Graphify` out of init.
- Keep active MCP count small; do not add broad MCP defaults.
- Use TDD for production changes.

## Done Signal

The handoff is complete when:

- `python -m paw doctor` reports default core, memory/hook/mesh/linker state,
  missing tools, and host restart advice;
- code-intelligence shootout produces a local JSON+MD artifact with honest
  metrics and clear recommendation;
- codebase-memory wrapper is used by the shootout and returns bounded output;
- repo-pack refuses unsafe broad packs and has a Repomix/code2prompt result;
- cross-OS smoke workflow exists for default foundation sets;
- docs `STATUS.md` and `NO-DAEMON-BASELINE-BACKLOG.md` reflect verified work;
- focused tests and `python -m compileall -q paw` pass.
