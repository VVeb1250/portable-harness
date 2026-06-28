# Bundle Coverage Gaps

Snapshot: 2026-06-28 JST.

Purpose: check the proposed five user-facing bundles against current
coding-agent harness needs, and identify whether paw needs another bundle.

This is a research note. It does not change the registry.

## Proposed User-Facing Bundles

1. `core` — host detection, local memory, router, doctor
2. `coding` — code intelligence, repo context, affected tests, patch/edit help
3. `safety` — permissions, secrets, supply-chain, MCP/skill security
4. `knowledge` — docs, research, file/data extraction, bulky context
5. `app-debug` — browser, UI, API, frontend debugging

## Missing Bundle

Add one more bundle:

6. `observe-eval` — traces, cost, run telemetry, evals, regression gates

Reason: paw's future is an agent-team workbench. Teams need run visibility:
who did what, which tools were called, what memory was read/written, what tokens
and dollars were spent, why a run failed, and whether a new recipe beats the old
one. This does not belong inside `coding`; it is cross-cutting.

Primary candidates:

- OpenTelemetry GenAI semantic conventions: portable trace schema for GenAI,
  MCP, provider-specific spans/events/metrics.
  Source: <https://github.com/open-telemetry/semantic-conventions-genai>
- Langfuse: open-source LLM observability, tracing, prompt management, metrics,
  evals.
  Source: <https://github.com/langfuse/langfuse>
- Arize Phoenix: open-source AI observability and evaluation with
  OpenTelemetry-based tracing, datasets, experiments, and evals.
  Source: <https://github.com/Arize-ai/phoenix>
- Braintrust AutoEvals: reusable automatic eval methods.
  Source: <https://github.com/braintrustdata/autoevals>
- agenttrace: local-first TUI/CLI for coding-agent session history, cost,
  tokens, tool failures, diffs, reports, and CI gates.
  Source: <https://github.com/luoyuctl/agenttrace>

Initial posture:

- Do not add hosted observability to `paw init`.
- Start with a local `observe-eval` profile: JSONL run logs, cost counters,
  OpenTelemetry-compatible schema where practical, and optional adapters to
  Langfuse/Phoenix/Braintrust/AgentOps/agenttrace.

## Bundle-By-Bundle Gaps

### 1. Core

Current core idea:

- ICM local memory
- host detector
- harness readiness router
- doctor
- global-first policy

Gaps:

- explicit `local-memory` set does not exist yet in the registry;
- memory seeding is not defined: what gets stored from a new repo at init;
- OS support matrix is not encoded in registry fields;
- skill package baseline is not represented as a first-class set;
- router should be renamed/positioned as readiness router, not generic skill
  selector.

Candidate additions:

- OpenAI Skills package shape as first-class import/export target:
  <https://developers.openai.com/codex/skills>
- AGENTS.md as default portable instruction surface:
  <https://agents.md/>
- optional future plain-text fallback/export inspired by `duyet/kb`:
  <https://github.com/duyet/kb>

Decision:

- Keep ICM as memory core.
- Do not replace ICM with Graphify/NEXO/Hivemind at init.
- Add registry fields before changing set behavior.

### 2. Coding

Current coverage:

- `efficiency-starter`
- `repo-pack`
- `test-affected`
- CodeGraph/semble anchors in some hosts

Gaps:

- no benchmarked code-intelligence profile;
- semantic code search is not explicit;
- semantic edit/refactor is missing;
- repo-pack choice may be stale;
- no AI PR/code-review profile;
- test quality/mutation testing is not represented.

Candidates:

- CodeGraph: keep in shootout, already has tool-call/time claims.
  <https://colbymchenry.github.io/codegraph/getting-started/introduction/>
- codebase-memory-mcp: high-priority challenger.
  <https://deusdata.github.io/codebase-memory-mcp/>
- Serena: semantic retrieval/edit/refactor.
  <https://oraios.github.io/serena/01-about/000_intro.html>
- grepai: local semantic search/call graph.
  <https://yoanbernabeu.github.io/grepai/>
- Repomix: repo packing candidate.
  <https://repomix.com/>
- PR-Agent/Qodo legacy OSS: PR/code review candidate, but likely CI/PR-shaped
  rather than local init.
  <https://github.com/The-PR-Agent/pr-agent>
- mini-SWE-agent / SWE-agent: runtime/eval reference, not bundle default.
  <https://github.com/SWE-agent/mini-swe-agent>

Decision:

- Add `code-intelligence.research` candidate group.
- Keep all graph/MCP code tools project-linked.
- Do not put Graphify in init.

### 3. Safety

Current coverage:

- `nah`
- `gitleaks`
- `osv-scanner`
- `infisical`
- some CI/doc checks through `quality-gate`

Gaps:

- MCP/skill prompt-injection and tool-poisoning scan;
- repo instruction poisoning scan (`CLAUDE.md`, `AGENTS.md`, `.cursor/rules`,
  MCP config);
- skill supply-chain review before import;
- MCP gateway/wrapper policy;
- explicit allow/deny policy per host.

Candidates:

- Snyk Agent Scan: scans AI agents, MCP servers, and skills for prompt
  injection, tool poisoning/shadowing, toxic flows, malware payloads,
  credential handling, and secrets.
  <https://github.com/snyk/agent-scan>
- Trail of Bits MCP Context Protector: MCP security wrapper.
  <https://github.com/trailofbits/mcp-context-protector>
- Awesome Agent Skills Security: research list for skill/MCP risks.
  <https://github.com/LLMSecurity/awesome-agent-skills-security>
- Skill supply-chain attack paper:
  <https://arxiv.org/html/2604.03081v1>

Decision:

- Add `agent-safety` or extend `safety` with an experimental MCP/skill security
  subprofile.
- Keep default init to deterministic local tools until privacy/network behavior
  is understood.

### 4. Knowledge

Current coverage:

- Context7
- web research
- doc extraction
- data query
- context-mode as bulky context workbench

Gaps:

- source quality/scoring policy for research output;
- deduplication between Context7, web fetch, local docs, and memory;
- no explicit "artifact extraction first, memory second" flow;
- no benchmark for whether context-mode is net-positive outside best-case tasks.

Candidates:

- Keep Context7 conditional for current docs.
- Keep MarkItDown/DuckDB/jq global if install paths are cross-OS.
- Keep context-mode conditional and measured.
- Consider Repomix under coding/repo-pack, not knowledge.

Decision:

- No new bundle needed.
- `knowledge` should remain profile-based and task-triggered, not init default.

### 5. App-Debug

Current coverage:

- browser-harness
- design-quality
- api-quality

Gaps:

- browser performance/network/console debugging is different from browser
  driving;
- no mobile/responsive screenshot gate;
- no local visual regression option;
- API profile has hurl but not OpenAPI/schema validation policy.

Candidates:

- Chrome DevTools MCP: browser debugging, performance traces, network, console,
  screenshots, automation, and slim mode.
  <https://github.com/ChromeDevTools/chrome-devtools-mcp>
- Playwright MCP: broad browser automation baseline.
  <https://github.com/microsoft/playwright-mcp>
- Hurl: already in `api-quality`.
  <https://hurl.dev/>

Decision:

- Add `frontend-debug` / `browser-debug` subprofile under `app-debug`.
- Keep browser MCPs optional because active tool schemas can be heavy.

### 6. Observe-Eval

Current coverage:

- internal bench scripts
- some `ccusage`/token accounting notes
- no user-facing bundle

Gaps:

- standard run trace format;
- multi-agent run spans;
- tool-call and memory-operation tracing;
- cost attribution;
- eval datasets and regression gates;
- adapter boundary to hosted/self-hosted observability.

Candidates:

- OpenTelemetry GenAI conventions
- Langfuse
- Arize Phoenix
- Braintrust AutoEvals
- AgentOps
- agenttrace

Decision:

- Add `observe-eval` as sixth user-facing bundle.
- Default should be local JSONL/SQLite trace + optional OTel export, not a
  hosted SaaS dependency.

## Revised User-Facing Bundle Set

| Bundle | Default init? | Scope |
| --- | --- | --- |
| `core` | yes | ICM, host detection, doctor, readiness router |
| `coding` | optional profile | code intelligence, repo pack, affected tests, semantic edit |
| `safety` | partial default | local deterministic guardrails; agent/MCP scan optional |
| `knowledge` | optional profile | docs, research, data/doc extraction, bulky context |
| `app-debug` | optional profile | browser, UI, API, DevTools |
| `observe-eval` | optional profile | traces, cost, evals, regression gates |

## Recommendation

Add `observe-eval` as a first-class bundle before paw becomes a workbench.

Do not add more user-facing bundles yet. Instead, keep adding internal
subprofiles/candidates under the six bundles above.

Highest-priority candidate research:

1. code-intelligence shootout: CodeGraph, codebase-memory-mcp, Serena, grepai,
   ast-grep, raw `rg`.
2. agent-safety scan: Snyk Agent Scan, MCP Context Protector, current
   `nah/gitleaks/osv`.
3. observe-eval local trace design: paw JSONL/SQLite schema compatible with
   OpenTelemetry GenAI concepts.
4. app-debug split: Chrome DevTools MCP vs browser-harness vs Playwright MCP.
