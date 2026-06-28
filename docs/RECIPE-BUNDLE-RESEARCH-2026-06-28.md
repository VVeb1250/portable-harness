# Recipe And Bundle Research

Snapshot: 2026-06-28 JST.

Purpose: expand paw from a coding-focused harness catalog into a general
portable harness curator with two layers:

1. **Foundation Bundles** — reusable capability primitives aligned with paw's
   concept.
2. **Specific Bundles / Persona Recipes** — opinionated compositions for
   developers, UX/UI builders, content creators, researchers, operators, and
   other user types.

This is a research artifact, not a registry patch.

## Current Implementation Slice

Do not implement the whole recipe map at once.

The active registry work for this round is intentionally narrow:

- **Foundation Core:** `local-memory`, `efficiency-min`, `secure-agent`, and
  `doc-data-min`.
- **Developer recipe:** `code-intelligence`, `repo-pack`, `test-affected`,
  `quality-gate`, and `api-quality` as opt-in/project or workload-specific
  bundles.

All other personas below are preserved as roadmap/research context. They should
not be added to `default_init`, and they should not be wired into the registry
until the Foundation + Developer path is tested end to end in this repository.

## Core Recommendation

Use two nouns:

- **Foundation Bundle** = primitive capability pack, stable and reusable.
- **Recipe** = persona or job-to-be-done composition of foundation bundles plus
  specific tools.

Do not make every persona a top-level foundation bundle. That would recreate
the catalog-dump problem.

## Persona Discovery First

The first pass below is **not final market segmentation**. It is a working
persona map built from the kinds of MCP/connectors/harnesses that are already
appearing in the ecosystem:

- developer/coding tools: CodeGraph, Serena, codebase-memory, grepai, Repomix,
  Chrome DevTools MCP;
- design tools: Figma MCP, Storybook MCP, Axe MCP, Canva MCP;
- content/media tools: Notion, Google Workspace, Canva, fal.ai, Remotion,
  ElevenLabs, video editing wrappers;
- operator/productivity tools: Slack, Linear, Jira, Notion, Google Workspace,
  project-management MCPs;
- data/BI tools: database MCPs, DuckDB/jq, analytics connectors;
- agent-builder tools: MCP SDKs, OpenTelemetry GenAI, Langfuse, Phoenix,
  eval frameworks, safety scanners.

So the right order is:

1. identify user type;
2. identify repeated jobs-to-be-done;
3. compose foundation bundles;
4. only then pick candidate tools/MCP/harnesses.

This matters because "content creator" and "UX/UI developer" can both use Figma
or Canva, but the recipe should be different: one creates publishable assets,
the other validates implementation fidelity and component reuse.

### Candidate User Types

Sources behind this taxonomy:

- McKinsey's 2025 State of AI survey says the most common gen-AI function usage
  is service operations, with marketing/sales, software engineering, HR, and
  product/service development also prominent.
  Source: <https://www.mckinsey.com/capabilities/quantumblack/our-insights/the-state-of-ai>
- Anthropic Economic Index reporting highlights heavy Claude usage in
  computer/mathematical tasks, writing/editing, education/instruction, and
  business/financial operations.
  Source: <https://www.anthropic.com/news/the-anthropic-economic-index>
- MCP/server directories and vendor pages cluster heavily around developer
  tools, workspace/productivity, design, data, sales/CRM, support, DevOps, and
  content/media connectors.

| User type | Core jobs-to-be-done | Keep as recipe? | Notes |
| --- | --- | --- | --- |
| General personal user | remember context, work with files/docs, automate browser/workspace tasks | yes | Best onboarding path for non-devs if privacy is strong. |
| Developer / coding agent user | understand repo, edit safely, test, debug, review, ship | yes | Current strongest paw evidence. |
| UX/UI developer | use design source-of-truth, implement UI, inspect browser, test accessibility | yes | Different from pure designer because repo/browser/debug matter. |
| Designer / no-code visual builder | create/iterate designs and assets across Figma/Canva/Webflow-like tools | maybe | Useful, but account/OAuth-heavy and less local-first. |
| Content creator | research, script, design, generate media, repurpose, publish drafts | yes | Needs explicit boundary between draft/export and publish/post. |
| Researcher / writer / analyst | collect sources, extract docs, cite, synthesize, query structured data | yes | Strong fit for knowledge + memory. Keep separate from content creator: the quality bar is sourcing/evidence, not publishing cadence. |
| Academic / scientist | literature review, datasets, lab notes, citations, reproducible analysis | maybe | Overlaps researcher but has domain databases and citation/reproducibility needs. Local skills already include PubMed/literature review style workflows. |
| Student / teacher / trainer | lesson plans, exercises, grading drafts, study guides, knowledge recall | later | Strong AI-use segment, but product shape may be different from harness-first users. |
| Data analyst / BI operator | query files/databases/analytics without dumping data into context | yes | Needs read-only defaults and connector safety. |
| Product/project operator | issues, roadmap, meeting docs, status, team communication | yes | Good MCP fit: Linear/Jira/Notion/Slack/Google Workspace. |
| DevOps/SRE/IT operator | inspect infra, debug incidents, review CI/IaC, controlled ops | yes, later | High-risk: read-only first, mutation requires approval. |
| Founder/GTM/sales/marketing | market research, CRM, outreach drafts, content distribution | maybe | Valuable but many paid/proprietary connectors and posting risks. |
| Agent builder / harness engineer | build, secure, evaluate, observe agent systems | yes | Strategic for paw itself. |
| Customer support / success | inspect tickets/docs/accounts, draft replies, route issues | later | Likely overlaps workspace/CRM; needs PII controls. |
| HR / recruiting / people ops | job descriptions, candidate screening, interview loops, policy Q&A | later | Common business function, but bias/privacy/legal risk means strict audit and human approval. |
| Finance / accounting / admin ops | invoices, reimbursements, budgets, vendor docs, approvals | later | High-stakes data and money movement; read/draft first, no payment actions. |
| Legal / compliance / policy ops | contracts, policies, evidence packs, regulatory checklists | later | High-stakes; requires citations, audit trail, and jurisdiction-specific warnings. |
| Healthcare / clinical admin | patient docs, coding, scheduling, prior auth, medical literature | later/regulated | Only with PHI controls; not a near-term general recipe. |
| Procurement / supply chain / logistics | vendor research, RFPs, purchase orders, inventory, shipment exceptions | later | Good fit for agent workflows but needs enterprise connectors and approval gates. |
| Real estate / field sales / local services | listings, comps, appointments, local lead workflows, form filling | later | Persona is plausible but very connector/workflow-specific. |

### Near-Term Persona Priority

Start with these because they best match paw's current strengths:

1. **developer**
2. **agent-builder**
3. **researcher-writer**
4. **personal-productivity**
5. **content-creator**
6. **ux-ui-dev**
7. **data-analyst**
8. **product-operator**

Keep these as later/regulated:

- customer-support
- HR/recruiting
- finance/accounting
- legal/compliance
- healthcare
- procurement/supply-chain
- DevOps/SRE mutation mode

The later group can still use paw's foundation bundles, but should not be the
first public onboarding choices because they need stricter privacy, approval,
and audit UX.

### Collapse Rule

If the list grows too large, collapse by work surface:

- **personal-productivity**: general user + support/admin light workflows
- **developer**: developer + agent-builder core
- **creator**: content creator + designer
- **operator**: product/project + DevOps/SRE + business/regulated ops, with risk tiers
- **analyst**: researcher/writer + data/BI

Recipes can stay numerous later, but public onboarding should start with a small
set of choices.

## Foundation Core Vs Optional Foundations

Foundation has two tiers:

- **Foundation Core** — init-safe, near-universal, light on machine and context.
- **Optional Foundation** — reusable capability primitives used by many recipes,
  but not safe to install or load by default because they may add MCP schemas,
  account/OAuth setup, project indexes, background services, or security risk.

This distinction keeps `paw init` small while still letting paw support many
personas.

### Foundation Core

These are the only pieces that should be considered for default init:

| Core primitive | Purpose | Default init? |
| --- | --- | --- |
| `core-control-plane` | catalog, host detection, linker state, doctor, readiness router | yes |
| `memory-min` | ICM availability, recall/brief policy, pending/curate basics | yes/plan |
| `safety-min` | local deterministic safety checks: permissions, secrets, dependency vuln checks | yes/plan |
| `efficiency-min` | zero/low-tax search and shell/context hygiene (`rg`, `ast-grep`, maybe `rtk`) | yes/plan |
| `observe-min` | local run log, cost counters, diagnostics; no hosted dependency | yes/plan |
| `skill-format-min` | AGENTS.md + OpenAI Skills-compatible packaging/import/export policy | yes |

### Optional Foundations

Keep optional foundations concept-driven but more numerous than core:

| Foundation | Purpose | Default init? |
| --- | --- | --- |
| `code-intelligence` | repo graph, semantic search, semantic edit/refactor, impact analysis | no |
| `repo-context` | token-counted repo packs, diffs, logs, shareable context artifacts | no |
| `knowledge-research` | current docs, web/source research, document extraction, citation workflow | no |
| `data-bi` | file/database/analytics querying without dumping data into context | no |
| `workspace` | docs, notes, email/calendar, chat, project-management connectors | no |
| `browser-automation` | browser task execution and form/workflow automation | no |
| `browser-debug` | DevTools, performance, network, console, visual/debug evidence | no |
| `design-source` | Figma/Storybook/design tokens/accessibility source-of-truth | no |
| `media-generation` | image/video/audio/design asset production | no |
| `agent-safety` | MCP/skill/agent-config security scan and policy wrappers | no |
| `observe-eval` | traces, cost, eval datasets, regression gates, optional telemetry adapters | no |
| `team-runtime` | planner/implementer/reviewer/evaluator orchestration and shared-state runs | no |

Optional foundation admission gate:

1. useful across more than one recipe;
2. has clear global vs project-linked boundary;
3. not init-safe due to setup/token/account/security cost;
4. has at least one strong candidate or a benchmarkable candidate set;
5. can be verified and unlinked/disabled cleanly.

Why split `media-design` into `design-source` and `media-generation`:

- UX/UI developers need design tokens, component docs, Storybook, accessibility,
  and browser evidence.
- Content creators need assets, video, audio, image generation, and publishing
  workflows.

They overlap at Figma/Canva, but the jobs and safety gates differ.

### Optional Foundation Candidate Map

| Optional foundation | Candidate tools / harnesses | Current gap before bundling |
| --- | --- | --- |
| `code-intelligence` | CodeGraph, codebase-memory-mcp, Serena, grepai, ast-grep/raw `rg` baseline | Needs local shootout and platform/install scoring. |
| `repo-context` | Repomix, code2prompt | Need bench on token count, include/exclude, diff/log support, remote repo support. |
| `knowledge-research` | Context7, Exa/Firecrawl/fetch primitives, MarkItDown, local docs/RAG, citation skills | Need source-quality policy and dedupe between docs/web/memory. |
| `data-bi` | DuckDB, jq, database MCPs (Postgres/MySQL/Supabase/ClickHouse/BigQuery/Snowflake), PostHog/GA/Metabase candidates | Need read-only connector policy and secret handling. |
| `workspace` | Notion MCP, Google Workspace MCP/CLI, Slack MCP, Linear MCP, Jira/Asana/Todoist candidates | Need OAuth/account setup UX and write-action approval boundaries. |
| `browser-automation` | browser-harness, Playwright MCP, browser-use style harnesses | Need tool-schema/token comparison and cross-browser story. |
| `browser-debug` | Chrome DevTools MCP, Playwright traces/screenshots, browser-harness evidence capture | Need split between debugging and task automation. |
| `design-source` | Figma MCP, Storybook MCP, Axe MCP, figtree-cli, design-quality tooling | Need project/account linking and read-only defaults. |
| `media-generation` | Canva MCP, fal.ai MCP, Remotion skills, mcp-video/FFmpeg wrappers, ElevenLabs MCP | Need paid/API approval policy and artifact-first workflow. |
| `agent-safety` | Snyk Agent Scan, MCP Context Protector, LLMSecurity skill-security research, existing `nah/gitleaks/osv` | Need privacy/network behavior check and overlap matrix. |
| `observe-eval` | local JSONL/SQLite, OpenTelemetry GenAI, Langfuse, Phoenix, Braintrust AutoEvals, AgentOps, agenttrace | Need local schema first; adapters later. |
| `team-runtime` | paw Team Kernel, Codex/DeepSeek/Claude adapters, Citadel/OpenHands/Aider references, Harbor/Inspect eval references | Need clear boundary between paw runtime and external harness references. |

### Gaps Still Not Fully Covered

- **Skill/package supply chain:** OpenAI Skills and ECC skills can be imported,
  but paw still needs trust metadata, source provenance, and safe install policy.
- **Approval UX:** many optional foundations can read safely but write/post/pay
  dangerously. Need a shared permission model before broad recipes.
- **Cross-OS install matrix:** candidates must declare Windows/macOS/Linux
  support before becoming default recipe dependencies.
- **Token-tax accounting:** MCP candidates need approximate tool-schema cost and
  active/inactive state in the catalog.
- **Account/OAuth lifecycle:** workspace, media, CRM, and design tools need
  explicit connect/disconnect and credential handling.
- **Local-first fallback:** hosted SaaS adapters should have local artifact
  fallback where possible.
- **Benchmark harness:** code-intelligence, repo-context, memory, safety, and
  browser-debug need comparable tasks before default recommendations.

## Persona Recipes

### 1. Developer / Coding Agent

Goal: ship code with less token, better context, and measurable safety.

Composition:

- `core`
- `memory-context`
- `coding`
- `safety-trust`
- `observe-eval`

Candidate tools:

- CodeGraph: project-linked graph/code intelligence. Source: <https://colbymchenry.github.io/codegraph/getting-started/introduction/>
- codebase-memory-mcp: local static-binary code intelligence candidate. Source: <https://deusdata.github.io/codebase-memory-mcp/>
- Serena: IDE-like semantic retrieval/edit/refactor. Source: <https://oraios.github.io/serena/01-about/000_intro.html>
- grepai: local semantic search and call graph. Source: <https://yoanbernabeu.github.io/grepai/>
- Repomix: repo packing/token-counted context candidate. Source: <https://repomix.com/>
- Chrome DevTools MCP: runtime browser debugging/performance. Source: <https://github.com/ChromeDevTools/chrome-devtools-mcp>
- Snyk Agent Scan: agent/MCP/skill security scan. Source: <https://github.com/snyk/agent-scan>

Default posture:

- Do not install graph MCPs at init.
- Use `rg`/`ast-grep` globally first.
- Link CodeGraph/codebase-memory/Serena only per project after benchmark or
  explicit request.

### 2. UX/UI Developer

Goal: turn real design systems into working UI without generic AI slop.

Composition:

- `core`
- `coding`
- `media-design`
- `automation`
- `observe-eval`

Candidate tools:

- Figma MCP official: design context and read/write access through supported
  clients. Sources: <https://help.figma.com/hc/en-us/articles/32132100833559-Guide-to-the-Figma-MCP-server>, <https://www.figma.com/mcp-catalog/>
- Storybook MCP: exposes components/docs/stories to agents so they reuse the
  actual design system. Source: <https://storybook.js.org/docs/ai/mcp/overview>
- Axe MCP: accessibility analysis and remediation guidance. Sources:
  <https://github.com/dequelabs/axe-mcp-server-public>, <https://www.deque.com/axe/mcp-server/>
- Chrome DevTools MCP: performance/network/console/debug traces.
- Playwright MCP: browser automation and E2E checks. Source: <https://github.com/microsoft/playwright-mcp>
- design-quality deterministic tools already tracked in paw (`impeccable`,
  `figtree-cli`).

Default posture:

- Figma/Storybook/Axe are project/account-linked; never blind init.
- Prefer read-only design/context access first.
- Browser MCPs are conditional because tool schemas can be heavy.

### 3. Designer / No-Code Visual Builder

Goal: create, inspect, and iterate designs without living inside developer
tooling.

Composition:

- `core`
- `media-design`
- `automation`
- `knowledge`

Candidate tools:

- Figma MCP official.
- Canva MCP: design search/export/asset management and Claude/connector
  workflows. Sources: <https://docs.workato.com/en/mcp/registry/canva-mcp-server>, <https://www.canva.dev/docs/apps/mcp-server/>
- Webflow/Framer/Mobbin/Refero style design MCPs are mentioned in 2026 design
  MCP guides; treat as candidate-only until vetted. Sources:
  <https://www.toools.design/blog-posts/best-mcp-servers-for-designers>,
  <https://www.vibestack.in/blog/best-mcp-servers-for-designers>

Default posture:

- Account/OAuth heavy; recipe should generate setup plan, not auto-connect.
- Keep paid/proprietary integrations optional.

### 4. Content Creator

Goal: research, script, repurpose, design, audio/video produce, and publish.

Composition:

- `core`
- `memory-context`
- `knowledge`
- `media-design`
- `automation`
- `safety-trust`

Candidate tools:

- Notion MCP: hosted MCP for workspace read/write. Source: <https://developers.notion.com/guides/mcp/overview>
- Google Workspace MCP / CLI: Gmail, Drive, Docs, Sheets, Slides, Calendar.
  Sources: <https://developers.google.com/workspace/guides/configure-mcp-servers>,
  <https://github.com/taylorwilsdon/google_workspace_mcp>
- Canva MCP: create/export/manage designs and assets.
- fal.ai MCP: image/video/audio generation. Source: <https://github.com/raveenb/fal-mcp-server>
- Remotion skills: programmatic videos with coding agents. Source: <https://www.remotion.dev/docs/ai/skills>
- mcp-video / FFmpeg wrappers: structured video editing. Source: <https://github.com/KyaniteLabs/mcp-video>
- ElevenLabs MCP: TTS, transcription, voice cloning/audio processing. Source: <https://github.com/elevenlabs/elevenlabs-mcp>
- Social publishing candidates: Aidelly/social MCP style tools need deeper
  privacy and platform-policy review. Source: <https://feedsquad.com/blog/best-mcp-servers-social-media>

Default posture:

- Strongly separate draft/export from publish/post.
- Publishing needs explicit user approval.
- Brand voice and content memory should live in ICM/plain files, not scattered
  prompts.

### 5. Researcher / Writer / Analyst

Goal: collect sources, extract documents, reason over data, produce sourced
outputs.

Composition:

- `core`
- `memory-context`
- `knowledge`
- `observe-eval`

Candidate tools:

- Context7 for current library docs when technical.
- web research tools: Exa/Firecrawl/fetch-style primitives.
- MarkItDown for Office/PDF/media-to-markdown.
- DuckDB/jq for structured data.
- Notion/Google Drive/Obsidian connectors for knowledge bases.
- Domain-specific research skills/databases already exist in local skill stack
  (PubMed, USPTO, literature review, etc.).

Default posture:

- Prefer source-cited drafts and local artifacts.
- Avoid direct posting/publishing.

### 6. Data Analyst / BI Operator

Goal: query files/databases/analytics platforms without dumping data into model
context.

Composition:

- `core`
- `knowledge`
- `observe-eval`
- `safety-trust`

Candidate tools:

- DuckDB and jq as global no-MCP default.
- Database MCP candidates: Supabase, PostgreSQL, MySQL, MongoDB, ClickHouse,
  BigQuery/Snowflake/DBT/Metabase/PostHog depending on stack. Sources:
  <https://mcp.directory/blog/best-database-mcp-servers-2026>,
  <https://chatforest.com/guides/best-data-analytics-mcp-servers/>
- Google Analytics/Search Console/PostHog candidates for product/marketing
  analytics.

Default posture:

- Read-only first.
- No production writes by default.
- Prefer local DuckDB over database MCP when files are enough.

### 7. Product Manager / Project Operator

Goal: keep issues, roadmaps, docs, status, and team communication current.

Composition:

- `core`
- `knowledge`
- `automation`
- `observe-eval`
- `safety-trust`

Candidate tools:

- Linear MCP official. Sources: <https://linear.app/docs/mcp>,
  <https://linear.app/changelog/2026-02-05-linear-mcp-for-product-management>
- Notion MCP official.
- Slack MCP official. Sources: <https://docs.slack.dev/changelog/2026/02/17/slack-mcp>,
  <https://slack.com/help/articles/48855576908307-Guide-to-Model-Context-Protocol-in-Slack>
- Google Workspace MCP.
- Jira/Asana/ClickUp/Monday/Todoist/Shortcut/Plane candidates. Source:
  <https://chatforest.com/guides/best-project-management-mcp-servers/>

Default posture:

- Read/update drafts are fine.
- Creating tickets/comments can be allowed with explicit confirmation.
- Deleting/closing/moving high-impact work requires approval.

### 8. DevOps / SRE

Goal: inspect infrastructure, diagnose incidents, and run controlled operations.

Composition:

- `core`
- `automation`
- `safety-trust`
- `observe-eval`
- `knowledge`

Candidate tools:

- GitHub/GitLab MCP, Docker, Kubernetes, Terraform/IaC, Sentry/Datadog, Cloudflare,
  AWS/Azure/GCP MCP candidates. Sources:
  <https://lenshq.io/blog/best-devops-mcp-servers>,
  <https://github.com/WagnerAgent/awesome-mcp-servers-devops>
- Sentry and monitoring MCPs for error context.
- `hurl`, actionlint, lychee, prek already align with low-risk local checks.

Default posture:

- Read-only by default.
- No production mutation without explicit approval.
- This recipe should probably be "plan/check/diagnose" first, not "operate".

### 9. Founder / GTM / Sales / Marketing

Goal: market research, CRM context, campaigns, outreach drafts, and content
distribution.

Composition:

- `core`
- `knowledge`
- `automation`
- `media-design`
- `safety-trust`

Candidate tools:

- HubSpot MCP: CRM read/write and developer workflows. Sources:
  <https://pipeline.zoominfo.com/sales/hubspot-mcp>,
  <https://www.amplemarket.com/blog/best-mcp-servers-for-sales>
- Salesforce/Attio/Crunchbase/Google Analytics/Ahrefs/Search Console candidates.
  Sources:
  <https://databar.ai/blog/article/best-mcp-servers-for-sales-teams-in-2026>,
  <https://www.mcpbundles.com/blog/best-mcp-servers>
- X/LinkedIn/crosspost skills already exist locally and can be recipe-level
  workflows, not foundation.

Default posture:

- Draft and research by default.
- CRM writes and outreach send/post require approval.

### 10. Agent Builder / Harness Engineer

Goal: build, test, secure, observe, and evolve agent/harness systems.

Composition:

- `core`
- `coding`
- `safety-trust`
- `observe-eval`
- `automation`
- `knowledge`

Candidate tools:

- MCP SDKs and inspector/reference servers. Source: <https://github.com/modelcontextprotocol/servers>
- OpenAI Agents SDK / Codex Skills / AGENTS.md.
- Claude Agent SDK / Anthropic harness guidance. Source:
  <https://www.anthropic.com/engineering/effective-harnesses-for-long-running-agents>
- OpenTelemetry GenAI, Langfuse, Phoenix, Braintrust, AgentOps/agenttrace.
- Microsoft Agent Framework / Google ADK / LangChain/CrewAI/Mastra as runtime
  references, not init dependencies. Sources:
  <https://www.langchain.com/resources/ai-agent-frameworks>,
  <https://devblogs.microsoft.com/agent-framework/microsoft-agent-framework-at-build-2026-announce/>

Default posture:

- This is a power-user recipe.
- It should expose eval/security/observability early.

### 11. General Personal Productivity

Goal: everyday local memory, files, email/calendar/docs, browser tasks, and
simple automation.

Composition:

- `core`
- `memory-context`
- `knowledge`
- `automation`
- `safety-trust`

Candidate tools:

- Notion MCP.
- Google Workspace MCP/CLI.
- Slack MCP when workspace context matters.
- Todoist/Calendar/project-management MCPs.
- Browser automation only when needed.

Default posture:

- Strong privacy defaults.
- No send/delete/post/pay actions without approval.
- This recipe may become the easiest non-developer onboarding story for paw.

## Specific Bundle Candidates

Specific bundles are reusable subprofiles below recipes:

| Specific bundle | Used by recipes | Candidate tools |
| --- | --- | --- |
| `code-intelligence` | developer, agent-builder | CodeGraph, codebase-memory-mcp, Serena, grepai, ast-grep |
| `repo-context` | developer, researcher | Repomix, code2prompt |
| `design-source` | UX/UI, designer, content | Figma MCP, Storybook MCP, figtree-cli |
| `accessibility` | UX/UI, app-debug | Axe MCP, accessibility agents, Playwright |
| `browser-debug` | developer, UX/UI, DevOps | Chrome DevTools MCP, Playwright MCP, browser-harness |
| `creator-media` | content creator, designer | fal.ai MCP, Remotion skills, mcp-video, ElevenLabs MCP, Canva MCP |
| `workspace` | productivity, PM, founder | Notion, Google Workspace, Slack, Linear |
| `crm-gtm` | founder, sales, marketing | HubSpot, Salesforce, Attio, Crunchbase, Ahrefs/Search Console |
| `data-bi` | analyst, founder | DuckDB, jq, database MCPs, PostHog/GA/Metabase |
| `devops-readonly` | DevOps, developer | GitHub, Sentry, Docker, Kubernetes, Cloudflare, actionlint/hurl |
| `agent-safety` | all high-risk recipes | Snyk Agent Scan, MCP Context Protector, nah/gitleaks/osv |
| `observe-eval-local` | developer, agent-builder | JSONL/SQLite run log, OTel GenAI-compatible fields |

## What Should Be In `paw init`

Even with persona recipes, `paw init` should stay small:

- `core`
- ICM check/install plan
- readiness router
- doctor
- safety baseline checks
- optional prompt: "choose a recipe now?"

Example:

```powershell
paw init
paw recipe list
paw recipe apply developer
paw recipe apply content-creator
```

`paw init --persona developer` can be a shortcut, but under the hood it should
still apply a recipe after core setup.

## Open Questions / Bench Needs

1. Which code-intelligence tool wins on local paw tasks?
2. Is `media-design` a better foundation name than `app-debug`?
3. Should `workspace` be a foundation bundle or stay a specific bundle?
4. Which official MCPs are worth supporting directly vs via generic connector
   registries?
5. What is the minimum safe UX for OAuth-heavy recipes?
6. How should paw score paid/proprietary tools vs local OSS tools?

## Recommendation

Adopt this taxonomy:

- **7 foundation bundles:** `core`, `memory-context`, `coding`,
  `safety-trust`, `automation`, `observe-eval`, `media-design`.
- **11 initial recipes:** `developer`, `ux-ui-dev`, `designer`,
  `content-creator`, `researcher-writer`, `data-analyst`, `product-operator`,
  `devops-sre`, `founder-gtm`, `agent-builder`, `personal-productivity`.
- **specific bundles:** reusable subprofiles like `code-intelligence`,
  `creator-media`, `workspace`, `crm-gtm`, `agent-safety`, `browser-debug`.

This keeps paw broad enough to serve non-developers without letting the catalog
turn into a flat pile of tools.
