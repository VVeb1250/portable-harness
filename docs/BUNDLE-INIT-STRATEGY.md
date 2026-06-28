# Bundle Init Strategy

Snapshot: 2026-06-28 JST.

Purpose: define what `paw init` should make available immediately, what must
stay project-linked, and which harness gaps need more research before entering
the catalog.

This document follows the north star in [`PAW-NORTH-STAR.md`](PAW-NORTH-STAR.md):
global-first, project-linked only when repo-local state is required, reuse before
rebuild, and evidence before default wiring.

## Current Decision

`paw init` should be **small, global-first, cross-OS, and no-MCP by default**.

Default init should not mean "install every good harness." It should mean:

1. install or verify the tiny control plane;
2. make local memory available;
3. make common token/security utilities available;
4. detect host capabilities;
5. recommend project linkers and optional profiles only when a project needs
   them.

Any capability that adds always-loaded MCP schemas, indexes a repository, writes
project config, starts a background process, or depends on a specific language
stack must not be part of blind global init.

## Init Tiers

### Tier 0 — Built Into Paw

These should ship with paw itself and require no external tool install.

| Capability | Default | Why |
| --- | --- | --- |
| Catalog registry | yes | paw's primary value is curated harness discovery and policy. |
| Linker state ledger | yes | enables reversible apply/verify/unlink. |
| Host detector | yes | detects Claude, Codex, Gemini, shell, OS, and existing config. |
| Doctor | yes | reports missing global tools, linked project tools, drift, and token risk. |
| Harness readiness router | yes | paw-specific router: suggests `apply`, `verify`, `link`, or `use` from linker health. |

### Tier 1 — Essential Global Tools

These are the first candidates for `paw init --global` or an interactive
`paw init` prompt. They should have Windows/macOS/Linux install paths and no
project-local state.

| Set | Tooling | Default posture | Evidence / reason |
| --- | --- | --- | --- |
| `local-memory` | ICM | recommended core | Local semantic memory and cross-agent recall. Current best fit for paw's local-first brain. |
| `efficiency-min` | `rg`, `ast-grep`, maybe `rtk` | recommended | Fast search and structural search reduce read/grep waste without MCP tax. `rtk` stays optional when shell hook support is uneven. |
| `secure-agent-min` | `nah`, `gitleaks`, `osv-scanner`, `infisical` | recommended | Deterministic safety and supply-chain checks; global tools, no repo index. |
| `skill-format` | AGENTS.md + OpenAI Skills-compatible package shape | recommended | Portable instruction/skill format with progressive disclosure. |
| `doc-data-min` | `markitdown`, `jq`, `duckdb` | recommended if installable | High leverage across repos; no MCP schemas; handles binary docs and structured data without loading full files. |

Default init should verify before installing. If a tool is missing, paw should
show the per-OS install command and ask or emit a plan rather than silently
installing many dependencies.

### Tier 2 — Suggested Profiles

These are not required at machine init, but `paw doctor` should recommend them
based on the project and user intent.

| Profile | Include | Trigger |
| --- | --- | --- |
| `coding` | code-intelligence linker, repo-pack, affected tests | code repo detected |
| `research` | web research, context-quality, doc-data-min | research/docs-heavy task |
| `frontend` | design-quality, browser-automation | frontend app or visual QA |
| `api` | api-quality, quality-gate | REST/GraphQL/API repo |
| `team` | ICM blackboard, team kernel adapters, telemetry | multi-agent run |
| `eval` | Harbor/Inspect/agenttrace/AgentOps candidates | measuring harness behavior |

### Tier 3 — Project-Linked Only

These must be linked per project because they index or store repo-local state,
write repo config, or add active MCP schemas.

| Capability | Status | Decision |
| --- | --- | --- |
| CodeGraph | local bench pass | Keep as project-linked code-intelligence option. Do not include in global init. |
| Graphify | heavy / broad | Remove from init. Keep as optional project-linked or research candidate only. |
| codebase-memory-mcp | local bench pass, Windows wrapper needed | Promote to serious CodeGraph challenger in `code-intelligence.research`. Project-linked only. |
| Serena | local index pass, startup/runtime friction | Keep as advanced IDE-like toolkit candidate. Project-linked only. |
| Context7 | useful docs MCP | Conditional profile; do not keep active globally unless host/project needs current library docs. |
| context-mode | high static token tax in this repo | Conditional; route only for bulky analysis and keep/kill by measured usage. |
| repo-local skills | project-specific | Link via managed blocks or host-native skill dirs. |

Local bench update:

- `docs/FOUNDATION-BENCH-2026-06-28.md` is the first local Foundation bench
  after tool updates.
- CodeGraph 1.1.1 indexed the temp repo and queried `TeamKernel`; it also
  prints an anonymous telemetry notice during init, so registry entries need a
  telemetry/privacy field.
- codebase-memory-mcp 0.8.1 indexed and queried faster on this small repo, but
  Windows PowerShell JSON quoting is fragile. paw should call it via argv or a
  wrapper.
- Serena indexed successfully, but `uvx` startup and a Python 3.14/Pydantic
  warning keep it out of default init.
- Repomix scoped compressed packing passed; broad packing is too large without
  a scope guard.

## Candidate Research And Replacement Radar

The table below separates sourced facts from paw recommendations. External
claims are not treated as paw truth until benchmarked locally.

| Candidate | What it is | Evidence found | Paw posture |
| --- | --- | --- | --- |
| CodeGraph | MCP/code graph for code navigation | Its docs claim 58% fewer tool calls, 22% faster runs, and near-zero file reads across 7 repos/languages. Source: <https://colbymchenry.github.io/codegraph/getting-started/introduction/> | Keep; project-linked; benchmark against alternatives on paw tasks. |
| codebase-memory-mcp | static-binary code knowledge graph MCP | Claims ~120x fewer tokens, 158 languages, Linux kernel index in 3 minutes, Windows/macOS/Linux binary. Sources: <https://deusdata.github.io/codebase-memory-mcp/> and <https://github.com/DeusData/codebase-memory-mcp> | High-priority research candidate; do not default until local bench. |
| Serena | MCP toolkit with IDE-like semantic retrieval/editing/refactoring | Docs describe symbol-level retrieval and MCP integration. Source: <https://oraios.github.io/serena/01-about/000_intro.html> | Evaluate; likely project-linked optional, not init. |
| grepai | privacy-first semantic code search CLI | Maintainer benchmark claims 97% input-token reduction and 27.5% cost savings vs grep in Claude Code. Source: <https://yoanbernabeu.github.io/grepai/blog/benchmark-grepai-vs-grep-claude-code/> | Candidate for `efficiency-min` or `coding`; needs cross-OS/install/maturity check. |
| Repomix | repo packer with token counting and compressed output | Current docs cover packing directories, remote repos, diffs, logs, split outputs, token counts, and compressed code. Source: <https://repomix.com/guide/usage> | Evaluate as replacement or sibling for `code2prompt` in `repo-pack`. |
| OpenAI Skills | skill package format | Codex Skills use progressive disclosure: metadata is visible first, full skill files load on demand. Source: <https://developers.openai.com/codex/skills> | Make this the primary skill package baseline. |
| skills.sh | skill marketplace | Listed by awesome-harness-engineering as cross-runtime skill discovery/install channel. Source: <https://raw.githubusercontent.com/walkinglabs/awesome-harness-engineering/main/README.md> | Future import source, not init dependency. |
| NEXO | local shared-brain/runtime | Claims local shared brain and LoCoMo benchmark improvement. Source: <https://github.com/wazionapps/nexo> | Reference/optional; too broad for init. |
| Hivemind | trace-to-memory/skill system | Claims token/turn/cost reductions on memory benchmark. Source: <https://github.com/activeloopai/hivemind> | Reference for future trace mining; not local-first baseline. |
| AgentOps / agenttrace | observability | awesome-harness list identifies AgentOps for monitoring/cost/tracing and agenttrace as local-first TUI/CLI for coding-agent sessions. Source: awesome-harness README | Future telemetry adapters after paw has enough run data. |
| Harbor / Inspect AI | eval frameworks | awesome-harness list identifies Harbor for agent eval/improvement and Inspect AI for reproducible eval harnesses. | Future eval profile; not init. |

## Initial Bundle Proposal

Rename current sets into clearer scopes:

| Current set | Proposed fate |
| --- | --- |
| `harness-foundation` | Tier 0/Tier 1 detector, always safe, detect-only. |
| `secure-agent` | Split into `secure-agent-min` default global and stronger optional repo policy. |
| `efficiency-starter` | **Done:** legacy alias only. Use `efficiency-min` global CLI and `code-intelligence` project-linked. |
| `context-quality` | Move to conditional docs profile. |
| `web-research` | Conditional research profile. |
| `context-workbench` | Conditional bulky-context profile; never default. |
| `data-query` | **Done:** legacy alias; merged into `doc-data-min`. |
| `doc-extract` | **Done:** legacy alias; merged into `doc-data-min`. |
| `repo-pack` | Keep optional; compare `code2prompt` vs Repomix. |
| `quality-gate` | Optional project profile; not global init. |
| `api-quality` | Optional API profile. |
| `test-affected` | Optional Python/pytest profile. |
| `design-quality` | Optional frontend profile. |
| `browser-automation` | Optional browser profile. |

Graphify should not appear in any init path. If kept, it belongs under
`code-intelligence.experimental` with explicit warning: project-linked, likely
token/setup heavy, benchmark required.

## Skill Router Position

External skill routers exist, so paw should not claim "router" as unique.

Known evidence:

- `hussi9/skill-router` claims 90% routing accuracy and 30%+ savings.
- `DustyWalker/skill-router` uses BM25/TF-IDF and reports fast local indexing
  and query timings.

paw's router is different and should be named more precisely:

**harness readiness router**

It should route based on:

- prompt intent;
- installed set state;
- linker health;
- host support;
- token tax;
- privacy/budget policy;
- ICM recall hits.

Output should be operational:

- `use <tool>`
- `paw apply <set>`
- `paw verify <set>`
- `paw link <capability>`
- `avoid <capability> because ...`

This makes paw's router part of the control plane, not just another semantic
skill selector.

## Platform Policy

Every set must declare platform support before it can become default:

```yaml
platforms:
  windows: supported | partial | blocked
  macos: supported | partial | blocked
  linux: supported | partial | blocked
install:
  windows: ...
  macos: ...
  linux: ...
default_init: true | false
link_scope: global | project | conditional
token_tax: none | low | medium | high
evidence:
  benchmark: url-or-local-path
  caveat: maintainer-claim | third-party | local-bench
```

Default init rule:

> A set cannot be default-init unless it is useful across many repos, has a
> Windows/macOS/Linux path, does not require repo indexing, and does not add
> always-loaded MCP schemas.

## Current Layer Model

The older L0/L1/L2/L3 language is now too abstract. Use these layers instead:

1. **Paw Control Plane** — catalog, registry, doctor, linker state, recipes.
2. **Global Foundation** — ICM, security tools, token/search tools, skill format.
3. **Project Linker** — CodeGraph/codebase-memory/Serena/Graphify, repo MCP,
   project memory namespace, managed instruction blocks.
4. **Context And Router** — brief, recall, harness readiness router, bounded
   memory injection, apply/verify/link nudges.
5. **Team Runtime** — planner/implementer/reviewer/evaluator, blackboard,
   mutate/verify/revise loop.
6. **Workbench/App** — catalog UI, recipes, memory, telemetry, team-run control.

This layer model answers "where does it live?" better than the old labels:
global, project-linked, runtime, or UI.

## Benchmark Backlog

Run these only after the docs and registry schema are ready.

0. **Init/doctor operational smoke**
   - Implement real `paw init` / `paw doctor` behavior for the default core:
     `local-memory`, `efficiency-min`, `secure-agent`, and `doc-data-min`.
   - Doctor must report missing tools, install hints, linker drift, and which
     host sessions need restart after config or env changes.
1. **Code intelligence shootout**
   - Compare CodeGraph, codebase-memory-mcp, Serena, grepai, ast-grep, and raw
     `rg`.
   - Tasks: find callers, trace route to handler, impact analysis, locate
     config, identify dead/duplicate code.
   - Metrics: tool calls, input/output tokens, wall time, correct answer, setup
     time, cross-OS install friction.
   - Add the Windows-safe codebase-memory-mcp wrapper before treating its result
     as user-ready.
   - Run grepai only after Ollama/local embeddings are intentionally installed;
     do not pull an embedding stack into default init just to run the bench.
2. **Repo pack shootout**
   - Compare code2prompt and Repomix.
   - Metrics: token count accuracy, include/exclude ergonomics, diff/log support,
     remote repo support, output quality for agents.
   - Add a scope guard before promotion so broad whole-repo packing requires an
     explicit scope, split output, metadata-only mode, or override.
3. **Memory usefulness**
   - Compare ICM-only, plain-text `kb`, Hivemind/NEXO reference behavior if
     feasible.
   - Metrics: recall accuracy, token injected, wrong/noisy recall rate,
     cross-host availability, offline/local behavior.
4. **Router usefulness**
   - Compare paw lexical/link-state router vs external semantic skill routers.
   - Metrics: correct recommendation, false positives, token cost, latency,
     whether it suggests operational fixes (`apply`, `verify`, `link`).
5. **Default foundation cross-OS CI**
   - Smoke `efficiency-min`, `secure-agent`, and `doc-data-min` on Windows,
     macOS, and Linux before claiming default-init portability.

## Near-Term Migration Steps

1. ~~Add registry fields: `default_init`, `link_scope`, `platforms`,
   `token_tax`, `evidence`, `bench_status`.~~ **Done 2026-06-28** in
   `paw/registry/sets.json` schema `0.5.0`, with loader/CLI/router support.
2. ~~Split `efficiency-starter` into global CLI foundation and project-linked
   code intelligence.~~ **Done 2026-06-28** as `efficiency-min` +
   `code-intelligence`; the old set is a compatibility alias.
3. ~~Mark Graphify as project-linked experimental, never init.~~ **Done
   2026-06-28**; it is a deferred candidate under `code-intelligence`.
4. ~~Add `local-memory` as an explicit set for ICM instead of burying memory in
   docs.~~ **Done 2026-06-28**; `local-memory` is default-init core.
5. ~~Add `doc-data-min` as a proposed default profile combining doc extraction
   and structured data tools.~~ **Done 2026-06-28**; `data-query` and
   `doc-extract` remain compatibility aliases.
6. ~~Add `code-intelligence.research` candidates: CodeGraph,
   codebase-memory-mcp, Serena, grepai, Graphify.~~ **Done 2026-06-28** in
   `code-intelligence.optional_sources`.
7. Keep `context-workbench`, browser, frontend, API, eval, and telemetry sets
   conditional.
8. Keep `efficiency-starter` as a compatibility alias until managed blocks,
   router hints, host configs, and docs prove the split migration will not strand
   old installs.
