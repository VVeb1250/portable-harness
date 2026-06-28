# Paw North Star

Purpose: stop future AI sessions from shrinking paw into "just a CLI helper"
or drifting into rebuilding every harness from scratch.

## One Sentence

**paw is a portable harness curator, linker, and launcher for AI-agent teams.**

It gathers scattered MCP servers, CLI tools, skills, hooks, memory systems, and
agent runtimes into curated stacks that can be installed globally, linked into a
project only when needed, and used across Claude Code, Codex, Gemini, DeepSeek,
and future hosts.

Thai short form:

> paw คือศูนย์รวมและตัวประกอบ harness สำหรับ AI agents: โหลดมาแล้วได้ stack
> ที่คัดแล้ว ใช้ข้ามหลายเจ้าได้ ลด token เพิ่ม quality และ link เข้าโปรเจค
> เฉพาะเท่าที่จำเป็น

## The Real Problem

The agent-harness ecosystem is not empty. It is too scattered.

Good pieces exist everywhere: `rtk`, CodeGraph, Graphify, ICM, Context7, ECC,
OpenAI Skills, browser-harness, NEXO, Hivemind, AgentOps, agenttrace, Harbor,
security CLIs, document tools, and many more. A user should not need to discover,
vet, install, and wire all of that by hand for every project.

paw exists to provide taste, policy, evidence, and wiring.

## Product Concept

paw should become a **portable meta-harness / agent-team workbench**.

The first implementation surface is CLI because CLI is measurable, portable,
and debuggable. CLI is the kernel, not the final product ceiling.

Growth ladder:

1. **Pure CLI** — install, verify, brief, recall, link, route, and run small team
   flows without background services.
2. **Thin hooks** — reduce manual prompt tax by injecting small, bounded memory
   and harness hints at host-supported lifecycle points.
3. **Optional local sidecar** — add local event bus, coordination, and background
   curation only after CLI+hooks expose a real ergonomic gap.
4. **Workbench/app** — make catalog, recipes, memory, team runs, and telemetry
   visible and operable.
5. **Agent-team runtime** — compose planner/implementer/reviewer/evaluator teams
   from the best available hosts and tools.

No stage should erase the lower stage. The sidecar must be optional; the CLI
must remain useful.

## Non-Negotiable Concepts

- **Less token** — prefer CLI tools, progressive disclosure, small briefs,
  bounded memory recall, and global installs over always-loaded MCP/tool schemas.
- **Improve AI quality** — give agents the right context, rules, skills,
  memory, and evaluators; do not merely add more tools.
- **Multi-vendor collaboration** — Claude, Codex, Gemini, DeepSeek, and future
  agents should share state and handoffs through portable protocols.
- **Portable and convenient** — global-first installation, clean project linkers,
  reversible managed blocks, and host-native output.
- **Local-first memory** — ICM is the primary brain until a better local,
  portable, measurable alternative proves itself.
- **Reuse before rebuild** — paw curates, scores, wires, and launches existing
  harnesses. It builds only the missing control plane and glue.

## Global-First Rule

Default to global tools. Link per-project only when the capability genuinely
needs project-local state.

| Scope | Use for | Examples | paw responsibility |
| --- | --- | --- | --- |
| Global tool | Same across repositories | `rtk`, `icm`, `nah`, `gitleaks`, `osv-scanner`, `infisical`, `markitdown`, `duckdb`, `jq` | install and verify |
| Global agent capability | Reusable skill/rule/profile | OpenAI Skills, ECC skills, AGENTS templates, routing rules | sync into host-native locations |
| Project-linked capability | Needs repo index/state/config | CodeGraph, Graphify, repo-local MCP, repo-local skills, project memory namespace | link, verify, unlink managed state |

Heuristic:

1. If it works the same in every repo, install globally.
2. If it indexes the repo, stores repo state, or writes repo config, use a linker.
3. If it is instruction/policy, keep it global and inject only small managed
   blocks per project.
4. If uninstalling should leave no trace, it must be under linker ownership.

## Harness Means Capability Pack

In paw, a harness is not only an MCP server. A harness is a capability pack:

- tools
- MCP servers
- skills
- prompts or instruction blocks
- hooks
- checks
- install commands
- usage policy
- evidence about token, quality, cost, maturity, and host support

Example shape:

```yaml
id: local-memory
default_scope: global-first
global:
  tools:
    - icm
project_link:
  optional:
    - project memory namespace
    - AGENTS.md managed block
    - thin lifecycle hooks
checks:
  - icm.exe recall test --read-only
policy:
  - inject only bounded summaries
  - never store secrets or raw transcripts by default
```

## Reuse Map

| External piece | paw reuse posture |
| --- | --- |
| ICM | Core local memory engine and blackboard backend |
| AGENTS.md | Portable instruction format |
| OpenAI Skills | Skill package format and import target |
| ECC | Rich harness source to detect, import, and wrap; not root truth |
| rtk | Global token-cut layer |
| nah / gitleaks / osv-scanner / infisical | Global security and supply-chain guardrails |
| CodeGraph / Graphify | Project-linked code intelligence when repo indexing is worth it |
| Context7 | Documentation lookup when current library docs matter |
| browser-harness | Optional browser automation capability pack |
| NEXO | Reference for local cognitive runtime, not default baseline |
| Hivemind | Reference for trace-to-memory/skill mining, not local-first core |
| AgentOps / agenttrace | Future telemetry adapters after paw has enough run data |
| Harbor | Future evaluation/improvement reference |
| Citadel | UX and orchestration reference; do not clone wholesale |

## What Paw Owns

paw owns the control plane:

- catalog and registry
- global vs project-linked state
- recipe/profile selection
- linker apply/verify/unlink
- host-native config generation
- ICM-backed memory policy
- token/cost/quality evidence ledger
- team composition glue
- doctor and drift detection

paw should not own broad replacements for mature tools unless evidence shows a
clear gap.

## Product Surface

Near-term CLI:

```powershell
paw catalog sync
paw harness list
paw harness apply coding
paw harness apply local-memory
paw link codegraph
paw unlink codegraph
paw brief "fix failing memory tests"
paw recall "what did we decide about sidecar"
paw team run "refactor parser safely" --profile cheap
paw doctor --global
paw doctor --project
```

Future workbench:

- Catalog: available harnesses and capability packs
- Recipes: curated stacks for coding, research, security, frontend, memory, team
- Memory: local ICM-backed project and team brain
- Team Runs: planner, implementer, reviewer, evaluator status
- Telemetry: tokens, cost, turns, quality, failures
- Wiring: Claude/Codex/Gemini/DeepSeek host state and drift

## Anti-Wander Rules For Agents

- Do not reduce paw to only a personal CLI helper. CLI is the kernel.
- Do not rebuild every harness. Curate, score, wire, and launch first.
- Do not blindly adopt ECC or any other pack wholesale. Detect and wrap.
- Do not scatter per-project config when a global install is enough.
- Do not make sidecar mandatory. Prove the CLI+hook gap first.
- Do not treat MCP count as free. Active tool schemas are token budget.
- Do not store secrets, raw transcripts, or noisy pending memory by default.
- Do not promote a capability without evidence or an explicit uncertainty note.

## Current Strategic Bet

Build paw as the easiest way to download and use a curated harness stack today,
while preserving a path to an agent-team platform tomorrow.

The moat is not owning every tool. The moat is:

- taste
- wiring
- portability
- low-token defaults
- local-first memory
- evidence-backed recipes
- agent-team composition across vendors
