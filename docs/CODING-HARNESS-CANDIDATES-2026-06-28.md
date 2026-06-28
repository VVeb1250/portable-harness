# Coding Harness Candidate Scan

Snapshot: 2026-06-28 JST.

Purpose: compare current paw bundle coverage against current coding-focused
harness/tools, and identify candidates to add, replace, or benchmark.

This is a research note, not a registry change. Do not promote a tool into
`paw init` from this file alone.

## Current Bundle Coverage

Current paw sets already cover:

- token/search starter: `efficiency-starter`
- security guardrails: `secure-agent`
- current docs: `context-quality`
- web research: `web-research`
- browser driving: `browser-automation`
- document/data extraction: `doc-extract`, `data-query`
- repo packing: `repo-pack`
- affected tests: `test-affected`
- CI/docs/API checks: `quality-gate`, `api-quality`
- bulky context: `context-workbench`
- harness reuse detector: `harness-foundation`

Main gaps for coding:

1. code-intelligence alternatives are not represented as a benchmarked
   candidate pool;
2. semantic edit/refactor tools are missing;
3. MCP/agent/skill security scanning is broader than current secret/vuln tools;
4. browser debugging/performance is different from browser-driving automation;
5. coding-agent eval/runtime candidates are not classified;
6. repo-pack may have a stronger replacement candidate than `code2prompt`.

## High-Priority Candidates

| Candidate | Covers gap | Evidence found | Initial posture |
| --- | --- | --- | --- |
| `codebase-memory-mcp` | Code intelligence, graph, semantic search, impact analysis | Project claims static C binary, Windows/macOS/Linux, 158 languages, local-only, 31-repo eval with 83% answer quality, 10x fewer tokens, 2.1x fewer tool calls, and project benchmark showing ~120x token reduction for structural queries. Source: <https://deusdata.github.io/codebase-memory-mcp/> | **Benchmark first.** Strong candidate to challenge/replace CodeGraph in `code-intelligence`, project-linked only. |
| Serena | IDE-like semantic retrieval/edit/refactor | Docs describe symbol-level retrieval, editing, refactoring, debugging via MCP; supports Claude Code, Codex, OpenCode, Gemini CLI, IDE clients. Source: <https://oraios.github.io/serena/01-about/000_intro.html> | **Add to code-intelligence candidate pool.** Likely project-linked optional. |
| grepai | Local semantic search + call graph CLI/MCP | Maintainer benchmark on Excalidraw claims -27.5% cost, -55% tool calls, -97% fresh input tokens, -71% cache-creation tokens. Source: <https://yoanbernabeu.github.io/grepai/blog/benchmark-grepai-vs-grep-claude-code/> | **Evaluate for `efficiency-min`/`coding`.** Caveat: maintainer benchmark, Mac/Ollama setup, quality not measured. |
| Repomix | Repo packing / context artifact | Packs local or remote repos into AI-friendly XML/Markdown/JSON/plain text; token counts, compression, security scanning, remote repo support. Sources: <https://github.com/yamadashy/repomix>, <https://repomix.com/> | **Compare with code2prompt.** Candidate replacement or sibling for `repo-pack`. |
| Snyk Agent Scan | Agent/MCP/skill security | Scans installed agent components, MCP servers, and skills for prompt injection, tool poisoning/shadowing, toxic flows, malware payloads, credential handling, hardcoded secrets; supports multiple agents and OS scopes. Source: <https://github.com/snyk/agent-scan> | **Add to `secure-agent` candidate pool.** Not default until privacy/network/API-token behavior is understood. |
| Chrome DevTools MCP | Browser debugging/performance | Gives agents DevTools access for performance traces, network, console, screenshots, automation; has CLI and slim mode. Source: <https://github.com/ChromeDevTools/chrome-devtools-mcp> | **Separate from browser-harness.** Optional frontend/debug profile, never default. |

## Secondary Candidates

| Candidate | Why it matters | Posture |
| --- | --- | --- |
| `zilliztech/claude-context` | Popular code-search MCP for Claude Code / coding agents; likely overlaps CodeGraph/codebase-memory/Serena. | Candidate for code-intelligence shootout only. |
| Playwright MCP | Browser automation baseline; current bundle has browser-harness, but Playwright MCP is mature and broad. | Keep as optional reference; tool schema may be heavy. |
| MCP Context Protector | MCP security wrapper by Trail of Bits. | Research for secure-agent; compare with Snyk Agent Scan and `nah`. |
| OpenHands | Full coding-agent runtime. | Runtime reference, not a paw bundle default. |
| Aider | Mature terminal pair-programming workflow and edit format precedent. | Reference for patch/edit protocol and repo-map ideas, not a default dependency. |
| Inspect AI / Harbor | Eval frameworks. | Future `eval` profile; not `paw init`. |

## Gap Matrix

| Coding capability | Current paw coverage | Gap | Candidate action |
| --- | --- | --- | --- |
| Fast lexical search | `rg`, `ast-grep` via efficiency starter | Good enough for global init | Keep global. |
| Structural code graph | CodeGraph in efficiency starter / host anchors | Needs benchmarked alternatives and project-linked policy | Compare CodeGraph, codebase-memory-mcp, Serena, grepai, raw `rg`, ast-grep. |
| Semantic code search | Not explicit | Missing global/project candidate | Bench grepai and codebase-memory-mcp; do not default. |
| Semantic edit/refactor | Own mutation runner, text-based | Missing IDE-level symbol edits | Evaluate Serena. |
| Repo context packing | `code2prompt` | Repomix may be stronger/more active | Bench code2prompt vs Repomix. |
| Current API/library docs | Context7 | Covered, but MCP-tax conditional | Keep conditional profile. |
| Browser driving | browser-harness | Covered for driving, not DevTools perf/debug | Add Chrome DevTools MCP candidate. |
| Browser performance/debug | Not explicit | Missing | Optional frontend/debug profile. |
| Security: secrets/deps/actions | `gitleaks`, `osv-scanner`, `nah`, quality-gate | Missing MCP/skill prompt-injection/tool-poisoning scan | Add Snyk Agent Scan / MCP Context Protector research. |
| Test selection | `pytest-testmon` | Python-only | Keep conditional; later find JS/Go analogs if needed. |
| API contract testing | `hurl` | Covered | Keep optional API profile. |
| Coding-agent eval | bench scripts internal | No reusable eval profile | Research Inspect AI / Harbor / SWE-bench-lite harnessing later. |
| Runtime/team | Team Kernel v0 | Runtime candidates not catalogued | Keep OpenHands/Aider/Citadel as references, not bundle defaults. |

## Init Impact

None of these new candidates should be added to blind `paw init`.

Likely target placement:

- `codebase-memory-mcp`, Serena, grepai, CodeGraph, Graphify:
  `code-intelligence.research`, project-linked only.
- Repomix:
  `repo-pack` candidate; global CLI if it wins cross-OS/install/ergonomics bench.
- Snyk Agent Scan:
  `secure-agent.experimental` until privacy/API behavior is clear.
- Chrome DevTools MCP:
  `frontend-debug` or `browser-debug`, conditional MCP.
- OpenHands/Aider:
  runtime/reference only.

## Recommended Bench Order

1. **Code-intelligence shootout**: CodeGraph vs codebase-memory-mcp vs Serena vs
   grepai vs ast-grep/raw `rg`.
2. **Repo-pack shootout**: code2prompt vs Repomix.
3. **Secure-agent extension**: Snyk Agent Scan vs current `nah/gitleaks/osv`
   coverage; decide if it is local/private enough.
4. **Frontend debug profile**: Chrome DevTools MCP vs browser-harness vs
   Playwright MCP on one real app debugging task.

Metrics:

- setup time;
- Windows/macOS/Linux install path;
- MCP tool count / token tax;
- query/task correctness;
- file reads/tool calls;
- input/output tokens;
- wall time;
- privacy/network behavior;
- cleanup/unlink behavior.

## Working Recommendation

For coding, paw's biggest near-term gap is **not another broad harness**.

It is a well-benchmarked `code-intelligence` profile that can choose between:

- cheap global search (`rg`, `ast-grep`);
- semantic CLI search (`grepai`);
- graph MCP (`CodeGraph`, `codebase-memory-mcp`);
- IDE-like semantic edit/refactor (`Serena`);
- heavyweight/experimental graphing (`Graphify`).

Graphify should remain out of init. It can stay in the candidate pool only if a
bench proves its quality gain outweighs setup/token cost.
