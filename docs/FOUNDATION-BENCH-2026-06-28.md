# Foundation Bench

Snapshot: 2026-06-28 JST.

Purpose: turn the Foundation/Optional Foundation discussion into local evidence
before reshaping `paw init` and the catalog.

Canonical artifacts:

- Runner: `bench/dev_foundation/bench_foundation.py`
- Latest run summary: `bench/out/foundation_bench_20260627T204810Z.md`
- Latest run JSON: `bench/out/foundation_bench_20260627T204810Z.json`
- Temp worktree used during run: `bench/dev_foundation/foundation-worktree-20260627T204810Z`
  (removed after the run; recreate with the runner)

The run uses a temporary copy of this repository, so project-linked indexes do
not dirty the main worktree.

## Tool Updates Before Bench

Updated or verified the tools that affect Foundation decisions:

| Tool | Result |
| --- | --- |
| `ast-grep` | updated to 0.44.0 |
| `codegraph` | updated to 1.1.1 |
| `rtk` | updated to 0.42.4 |
| `jq` | updated to 1.8.2 |
| `duckdb` | updated to 1.5.4 |
| `infisical` | updated to 0.43.99 |
| `osv-scanner` | updated to 2.4.0 |
| `markitdown` | updated from 0.0.2 to 0.1.6 with docx/xlsx/pptx/pdf extras |
| `codebase-memory-mcp` | installed 0.8.1 to `bench/_tools/codebase-memory-mcp` with `--skip-config` |
| `icm.exe` | `icm.exe upgrade` says 0.10.57 is already latest |
| `nah` | pip says 0.9.1 is current |

## Result Matrix

| Capability | Check | Local result | Bundle implication |
| --- | --- | --- | --- |
| Paw control plane | `sets list`, `sets show secure-agent`, `route` | pass, 220-598 ms | Keep built into paw. |
| Local memory | `icm.exe recall` | pass, ~2.8 s, ~533 output-token proxy | Keep as Foundation Core; recall is useful but should stay bounded. |
| Fast search | `rg` | pass, ~151 ms, ~100 output-token proxy | Keep global baseline. |
| Structural search | `ast-grep` | pass, ~126 ms, but broad class match returned ~2.8k output-token proxy | Keep global, but teach scoped patterns. |
| Output compression | `rtk grep` | pass, ~243 ms, ~1.3k output-token proxy | Keep optional hook/CLI efficiency layer; do not treat as semantic search. |
| Action guard | `nah test` allow/block | pass, deterministic allow/block | Keep in `secure-agent-min`. |
| Secret/dependency scan | `gitleaks`, `osv-scanner` | pass, <640 ms on temp repo | Keep in `secure-agent-min`. |
| Structured data | `jq`, `duckdb` | pass, <60 ms | Keep in `doc-data-min`. |
| Document conversion | `markitdown` HTML smoke | pass, ~2.1 s | Keep as doc-extract candidate; warning: ffmpeg missing only affects audio/video paths. |
| Code graph baseline | CodeGraph init/status/query | pass; init wall ~1.7 s, query ~315 ms | Keep project-linked `code-intelligence` baseline, not default init. |
| Code graph challenger | codebase-memory-mcp index/search | pass; index ~494 ms, search ~19 ms | Promote to serious `code-intelligence.research`; needs paw wrapper for Windows argv/PowerShell ergonomics. |
| IDE/LSP toolkit | Serena index | pass; ~4.1 s via `uvx`, Python 3.14/Pydantic warning | Optional project-linked advanced toolkit, not Foundation default. |
| Repo pack | Repomix scoped compress | pass; ~2.5 s, ~2.5k output-token proxy | Candidate replacement/sibling for `code2prompt`; must enforce scope. |
| Semantic code search | grepai/Ollama | blocked: neither installed | Keep as deferred candidate; do not pull Ollama/model into Foundation by default. |

## Decisions

1. **Foundation Core is not too large if kept CLI/global/no-MCP.**
   The locally passing core is: paw control plane, ICM, `rg`, `ast-grep`,
   `rtk` optional hook/CLI, `nah`, `gitleaks`, `osv-scanner`, `infisical`,
   `jq`, `duckdb`, `markitdown`, and skill-format support.

2. **CodeGraph and codebase-memory both belong under project-linked
   `code-intelligence`, not blind init.**
   CodeGraph has the smoother direct CLI/MCP story and useful status/query
   surface. codebase-memory-mcp is faster on this small repo and indexes more
   file types, but Windows JSON quoting is fragile unless paw calls it through
   argv or a wrapper.

3. **Serena is valuable but not Foundation.**
   It brings symbol/edit/refactor tools that overlap future agent-team
   workflows, but `uvx` startup and Python 3.14 warning make it a profile
   candidate, not a default install.

4. **Repomix should replace or sit beside `code2prompt` in `repo-pack`.**
   The scoped run is manageable. A previous broad compressed run on `paw tests
   docs` produced about 159k output-token proxy, so paw must require include
   scope, split output, or metadata-only mode before handing packed context to
   an agent.

5. **Graphify stays out of init.**
   Nothing in this bench created a reason to re-add Graphify to Foundation.
   ICM handles memory, CodeGraph/codebase-memory cover code graph candidates,
   and Graphify remains experimental/project-linked only.

6. **Telemetry/privacy needs a registry field.**
   CodeGraph 1.1.1 prints an anonymous telemetry notice during init. Any
   project-linked tool that sends telemetry or can send telemetry needs a
   `telemetry`/`privacy` field plus a paw policy, such as setting an opt-out
   environment variable where available.

## Registry Changes Implemented

Implemented 2026-06-28 in `paw/registry/sets.json` schema `0.5.0`, exposed
through `paw.sets.loader.CuratedSet`, `paw sets list`, `paw sets show`, and
`paw.router_block`:

```yaml
default_init: true | false
link_scope: global | project | conditional
platforms:
  windows: supported | partial | blocked
token_tax:
  idle_mcp: none | low | medium | high
  runtime_output: measured | proxy | unknown
evidence:
  local_bench: docs/FOUNDATION-BENCH-2026-06-28.md
  artifact: bench/out/foundation_bench_20260627T204810Z.json
privacy:
  telemetry: none | opt-out | unknown
  network: none | optional | required
windows_ergonomics:
  powershell: ok | wrapper-needed | blocked
```

The registry now also has an explicit `local-memory` set for ICM. This closes
the earlier gap where ICM was Foundation Core in docs but not represented as a
catalog capability.

Implemented split after the bench:

- `efficiency-min` is now the default-init global dev-efficiency set:
  `rg`, `rtk`, and `ast-grep`; zero MCP.
- `code-intelligence` is now the project-linked dev intelligence set:
  CodeGraph/Semble active anchors plus codebase-memory-mcp, Serena, grepai, and
  Graphify as explicit candidates/deferred sources.
- `doc-data-min` is now the default-init local file intelligence set:
  DuckDB, jq, and MarkItDown; zero MCP.
- `efficiency-starter`, `data-query`, and `doc-extract` remain as
  compatibility aliases so existing managed blocks do not break.

Immediate bundle posture:

- `foundation-core`: paw control plane, `local-memory`/ICM, `efficiency-min`
  (`rg`, `ast-grep`, `rtk`), `secure-agent` (`nah`, `gitleaks`,
  `osv-scanner`, `infisical`), `doc-data-min` (`jq`, `duckdb`,
  `markitdown`), and AGENTS/OpenAI Skills format.
- `code-intelligence`: CodeGraph default candidate; codebase-memory-mcp
  research candidate; Serena advanced optional; grepai deferred until
  Ollama/local embedding setup is intentionally selected.
- `repo-pack`: Repomix primary candidate; keep `code2prompt` only if a later
  bench shows a better install/offline story.

Remaining registry work:

- Rename or split `secure-agent` into `secure-agent-min` only if later tests show
  the current set is too broad for default init.
- Add `repo-pack` scope guard before promoting Repomix or switching away from
  `code2prompt`.
- Build the code-intelligence shootout matrix before promoting
  codebase-memory-mcp, Serena, or grepai.

## Follow-Up Benches

1. CodeGraph vs codebase-memory on real tasks: callers, impact, architecture
   query, config tracing, and "what changes if symbol X changes?"
2. Repomix vs code2prompt after installing a current code2prompt path.
3. `markitdown` on real docx/xlsx/pptx/pdf fixtures, not only HTML smoke.
4. Optional grepai run only if we intentionally install Ollama and a small local
   embedding model.
