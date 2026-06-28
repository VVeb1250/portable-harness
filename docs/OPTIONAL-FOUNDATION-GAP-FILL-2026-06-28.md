# Optional Foundation Gap Fill

Snapshot: 2026-06-28 JST.

Purpose: targeted research pass for optional foundations that were still thin:
`memory-context`, `skill-format-min`, `agent-safety`, `workspace`, `data-bi`,
and `automation`.

This file should be used before changing `paw/registry/sets.json`. It is a
candidate and trade-off map, not an adoption decision.

## Decision Summary

After this pass, the optional foundation taxonomy has enough candidates for the
first benchmark/design round. Do not keep broad-searching for tools until the
bench matrix starts producing misses.

Remaining work is not "find more tools"; it is:

1. add registry fields for scope/platform/token/evidence;
2. design benchmark tasks per optional foundation;
3. run focused shootouts;
4. only then promote winners into recipes.

## 1. Memory-Context

Goal: make paw remember and retrieve useful context across hosts without adding
large always-on context or heavy graph runtimes.

Current anchor:

- **ICM** remains the default local memory core.

Candidate additions:

| Candidate | What it adds | Posture |
| --- | --- | --- |
| agentmemory | Strong local coding-agent memory benchmark claims and hook-driven capture. | Reference / bench only. It is daemon-centric and heavier than paw init. |
| Mem0 | Widely used memory layer; 2026 benchmark reports position LoCoMo, LongMemEval, and BEAM as standard memory benchmarks and claim high scores at non-trivial token budgets. Source: <https://mem0.ai/blog/state-of-ai-agent-memory-2026> | Benchmark reference, not init baseline. Useful for metric design. |
| kb / plain text memory | Simple repo-readable fallback/export. | Add as fallback/export pattern, not semantic core. |
| NEXO / Hivemind | Stronger shared-brain or trace-to-skill products. | Reference only until local/offline/init-safe story is proven. |

Gaps to close:

- repo memory seeding policy;
- memory dedupe and conflict handling;
- pending-to-durable curation;
- plain text export/import;
- wrong/noisy recall benchmark.

Recommended local bench:

| Task | Metric |
| --- | --- |
| Recall old decision across host/session | correct recall, injected tokens |
| Updated fact replaces stale fact | conflict handling |
| Repo seeding from docs | useful facts stored vs noise |
| Stop-capture curation | false positive memory rate |
| Plain-text export/import | lossiness and portability |

Verdict:

Keep ICM. Do not replace it before a local bench shows a better option that is
also cross-OS, local-first, and init-safe.

## 2. Skill-Format-Min

Goal: support reusable skills/instructions without making skills a new supply
chain hole.

Current anchors:

- **AGENTS.md** is the portable project instruction baseline. The official site
  describes it as an open format used by 60k+ open-source projects.
  Source: <https://agents.md/>
- **OpenAI Codex Skills** are the best skill package baseline because they use
  progressive disclosure: metadata first, `SKILL.md` only when needed.
  Source: <https://developers.openai.com/codex/skills>

Candidate additions:

| Candidate | What it adds | Posture |
| --- | --- | --- |
| Anthropic public skills repo | Examples across creative, technical, and enterprise workflows. Source: <https://github.com/anthropics/skills> | Import/reference source. |
| SkillsMP / skills.sh / skill directories | Large discovery surface for SKILL.md packages. | Search/import source only; never blind install. |
| SkillFortify research | Formal supply-chain model and benchmark for skills. Source: <https://arxiv.org/abs/2603.00195> | Use for trust metadata design. |
| Orca / Snyk / Mitiga skill-risk research | Evidence that skills can carry supply-chain risk. Sources: <https://orca.security/resources/blog/ai-agent-skill-supply-chain-security/>, <https://snyk.io/blog/toxicskills-malicious-ai-agent-skills-clawhub/>, <https://www.mitiga.io/blog/ai-agent-supply-chain-risk-silent-codebase-exfiltration-via-skills> | Use to justify scan-before-import and provenance policy. |

Gaps to close:

- skill provenance field;
- source URL and version/commit pin;
- permission/capability declaration;
- scripts/assets inventory;
- safe import preview;
- trust score or policy status;
- conversion between OpenAI Skills, Claude skills, ECC skills, and AGENTS blocks.

Recommended paw behavior:

```text
paw skills search
paw skills inspect <source>
paw skills import <source> --dry-run
paw skills trust <skill> --pin <commit>
```

Verdict:

Do not adopt a public skill marketplace as a dependency. Treat marketplaces as
search sources, then let paw inspect, pin, and link skill packages.

## 3. Agent-Safety

Goal: protect users from poisoned MCP servers, malicious skills, config
tampering, tool poisoning, secret leaks, and unsafe agent actions.

Current anchors:

- `nah`
- `gitleaks`
- `osv-scanner`
- `infisical`

Candidate additions:

| Candidate | What it adds | Posture |
| --- | --- | --- |
| Snyk Agent Scan | Scans AI agent components, MCP servers, and skills for prompt injection, tool poisoning, toxic flows, malware payloads, credential handling, hardcoded secrets. Source: <https://github.com/snyk/agent-scan> | High-priority candidate; check privacy/network/API behavior. |
| MCP Context Protector | MCP security wrapper from Trail of Bits. Source: <https://github.com/trailofbits/mcp-context-protector> | Candidate for wrapping risky MCP traffic. |
| NSA MCP Security Design Considerations | Threat model and design guidance for MCP security. Source: <https://media.defense.gov/2026/Jun/02/2003943289/-1/-1/0/CSI_MCP_SECURITY.PDF> | Policy reference. |
| Cisco AI Agent Security Scanner / Watchdog | Detects hook injection, auto-memory poisoning, shell alias injection, MCP config tampering with snapshots/HMAC. Source: <https://blogs.cisco.com/ai/introducing-the-ai-agent-security-scanner-for-ides-verify-your-agents> | Candidate pattern for config integrity monitor. |
| Tool-poisoning research | Confirms MCP clients are exposed to tool poisoning and prompt injection classes. Source: <https://arxiv.org/html/2603.21642v1> | Threat model evidence. |

Gaps to close:

- local-only scan option;
- supported host/config paths;
- skill import scanner;
- MCP tool-description diffing;
- config tamper baseline;
- approval policy for write/post/pay actions;
- output format paw can ingest.

Recommended bench:

| Fixture | Expected |
| --- | --- |
| malicious skill with curl/source | scanner flags |
| MCP tool description exfiltration text | scanner/wrapper flags |
| `.mcp.json` command drift | baseline diff detects |
| AGENTS/CLAUDE instruction poisoning | policy scanner flags |
| hardcoded secret in skill asset | scanner flags |

Verdict:

This is the most important non-coding gap. Add `agent-safety.research` before
promoting more external skills/MCP servers.

## 4. Workspace

Goal: connect notes, docs, chat, email/calendar, tasks, and project management
without making account-heavy connectors part of init.

Candidate additions:

| Candidate | What it adds | Posture |
| --- | --- | --- |
| Notion MCP | Official hosted server for secure workspace access across AI tools. Source: <https://developers.notion.com/guides/mcp/overview> | Optional workspace connector; OAuth/account-heavy. |
| Google Workspace MCP | Official Google Workspace MCP servers for Gmail, Drive, Calendar, Chat, People APIs. Source: <https://developers.google.com/workspace/guides/configure-mcp-servers> | Optional workspace connector; needs Cloud project/API setup. |
| Slack MCP | Official Slack MCP guidance for secure workspace access and Slackbot MCP client behavior. Source: <https://slack.com/help/articles/48855576908307-Guide-to-Model-Context-Protocol-in-Slack> | Optional; strong approval boundaries. |
| Linear MCP | Official remote MCP for product/project management. Source: <https://linear.app/docs/mcp> | Optional product-operator connector. |
| Obsidian/local files | Local knowledge base fallback. | Candidate; local-first and low risk if read-only. |

Gaps to close:

- OAuth connect/disconnect UX;
- read-only vs write mode;
- per-connector action policy;
- workspace secret storage;
- project vs global account state;
- local fallback for users who do not want cloud connectors.

Recommended posture:

- read-only by default;
- draft actions allowed;
- send/post/delete/move/close require approval;
- connectors must be disabled/unlinked cleanly.

Verdict:

Workspace candidates are enough for the first version. The missing piece is not
more connectors; it is permission UX and account lifecycle.

## 5. Data-BI

Goal: let agents answer data questions without pulling raw databases or large
files into context.

Current anchors:

- DuckDB
- jq

Candidate additions:

| Candidate | What it adds | Posture |
| --- | --- | --- |
| Supabase MCP | Official MCP server with feature groups and dashboard-generated MCP URLs. Source: <https://supabase.com/docs/guides/ai-tools/mcp> | Optional project/data connector; read-only profile needed. |
| PostHog MCP | AI coding agent access to trends, funnels, retention, HogQL, dashboards. Source: <https://posthog.com/docs/product-analytics/build-insights-mcp> | Optional product analytics connector. |
| PostgreSQL/MySQL/ClickHouse/BigQuery/Snowflake MCPs | Direct DB querying and schema discovery. | Candidate group; prefer official or read-only wrappers. |
| Local chart/report tools | Generate charts/reports from DuckDB outputs. | Candidate gap; likely CLI/Python libs, not MCP. |

Gaps to close:

- read-only query guard;
- schema discovery without data exfiltration;
- row/byte limits;
- secret handling;
- query logging/audit;
- safe chart/report generation.

Recommended bench:

| Task | Metric |
| --- | --- |
| CSV/Parquet answer via DuckDB | tokens and correctness |
| DB schema discovery | secret/data leakage |
| BI connector query | least-privilege behavior |
| chart artifact generation | file artifact quality |

Verdict:

Keep DuckDB/jq global. Treat DB/analytics MCPs as optional workspace/data
connectors with strict read-only defaults.

## 6. Automation

Goal: execute browser, desktop, API, and workflow tasks while keeping actions
bounded and reversible.

Candidate additions:

| Candidate | What it adds | Posture |
| --- | --- | --- |
| browser-harness | Thin browser-driving harness. | Existing candidate; optional. |
| Playwright MCP | Broad browser automation. Source: <https://github.com/microsoft/playwright-mcp> | Optional; compare tool tax. |
| Chrome DevTools MCP | Browser debugging/performance/evidence. Source: <https://github.com/ChromeDevTools/chrome-devtools-mcp> | Optional browser-debug, not general automation. |
| PyAutoGUI MCP | Cross-app desktop automation surface. Source: <https://mcpmarket.com/server/pyautogui> | High-risk; research only until safety gates exist. |
| OpenClaw / Hermes-style local agents | Broader open-source automation agent pattern. Source: <https://www.techradar.com/pro/how-to-automate-workflows-using-open-source-ai-agents> | Reference for recipes, not dependency. |

Gaps to close:

- action approval model;
- dry-run for external actions;
- screenshot/evidence artifact policy;
- cross-OS desktop support;
- keyboard/mouse safety boundaries;
- credentials/session handling;
- rollback story where possible.

Verdict:

Automation is intentionally optional. It should split into subprofiles:

- `browser-automation`
- `browser-debug`
- `workspace-actions`
- `desktop-control.experimental`
- `api-actions`

Do not put desktop control in init or default recipes.

## Coverage Verdict

After this targeted pass:

- Candidate coverage is sufficient for the first optional-foundation design.
- The remaining gaps are mostly policy, schema, safety, and benchmark work.
- Do not continue broad candidate hunting until a bench reveals a concrete miss.

## Next Work Before Bundle Reshape

1. Add registry schema fields:
   - `foundation_core`
   - `optional_foundation`
   - `specific_bundle`
   - `default_init`
   - `link_scope`
   - `platforms`
   - `token_tax`
   - `requires_account`
   - `requires_project_state`
   - `evidence`
   - `bench_status`
2. Create benchmark specs:
   - `code-intelligence`
   - `repo-context`
   - `memory-context`
   - `agent-safety`
   - `browser-debug`
   - `data-bi`
3. Draft approval/action policy shared by workspace, automation, media, CRM, and
   DevOps recipes.
4. Only then migrate `sets.json`.
