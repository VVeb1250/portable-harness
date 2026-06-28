# portable-harness — Codex operating guide

This repository is a personal, cross-host agent-team substrate: curated tools,
token reduction, and shared memory across heterogeneous agents. It is not a
general-purpose harness competing with ECC.

## Start here

Before non-trivial work:

1. Read `CLAUDE.md` for the owner's working mindset and anti-wander rules.
2. Read `docs/STATUS.md`, especially section 0, for current truth.
3. Read `docs/PAW-NORTH-STAR.md` for the refined product concept: portable
   harness curator/linker/launcher, global-first policy, and anti-wander rules.
4. Read `docs/NO-DAEMON-BASELINE-BACKLOG.md` before choosing next work.
5. Use `docs/README.md` as the documentation map; it marks authoritative vs
   historical files.
6. Run `git status --short --branch`. Treat existing changes as another
   agent's work unless the user explicitly puts them in scope.
7. **Resuming the memory system?** Read `docs/MEMORY-PLAN.md`; Codex Stop
   payload/transcript shape is still a known verification gap.

`bundle/AGENTS.md` is a future managed-block source and may lag this root file.
This root file is the active Codex bridge until the linker source is reconciled.

Current focus: make the no-daemon / CLI-first baseline usable before optional
sidecar, Memoir graphing, or `skills.sh` integration.

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

<!-- paw:efficiency-starter:start -->
## paw capability · efficiency-starter
Legacy compatibility alias. Prefer efficiency-min for global CLI foundation and code-intelligence for project-linked graph/semantic code tools.

- **rtk** (`rtk`): PreToolUse hook rewrites Bash commands to rtk equivalents, compresses shell output (cargo/pytest/go test/git/grep/find/ls/tsc/eslint/docker/kubectl) before it enters context. 60-90% on common dev commands (vendor).
  - install: `winget install rtk-ai.rtk`
- **ast-grep** (`ast-grep`): AST-pattern search/lint/rewrite (Rust, tree-sitter, polyglot). Fills the STRUCTURAL rung between lexical grep (host-native ripgrep) and graph (codegraph/semble): matches code SHAPE (`foo($$$ARGS)`) not text — no comment/string/whitespace false-positive lines entering context; and a multi-file codemod (`--rewrite`) = ONE bounded command + unified diff instead of N Edit round-trips. 0 MCP tool-defs.
  - usage: `ast-grep run -p 'console.log($$$A)' src/   |   rewrite: ast-grep run -p '$F.unwrap()' --rewrite '$F.expect("msg")' -U   |   rules: ast-grep scan (sgconfig.yml)`
  - install: `npm install --global @ast-grep/cli`
<!-- paw:efficiency-starter:end -->

<!-- paw:secure-agent:start -->
## paw capability · secure-agent
Permissions + supply-chain guardrails for autonomous coding agents. Covers the harness component codegraph/rtk leave empty: a deterministic action-guard, secret leak prevention, and dependency-vuln defense. Entirely CLI/hook — ZERO MCP tool-defs, so it adds no per-session schema overhead on any host.

- **nah** (`nah`): Deterministic PreToolUse classifier that distinguishes safe vs dangerous shell actions (e.g. `rm dist/` vs `rm ~/.bashrc`, `curl evil | bash`). No LLM in the path = no latency. Project override is TIGHTEN-ONLY (supply-chain-safe: a repo cannot LOOSEN your guard).
  - install: `pip install "nah[config,keys]"`
- **gitleaks** (`gitleaks`): Fast (Go) regex+entropy secret scanner. Agent pipes staged content through `gitleaks ... stdin` before commit, or scans the repo. Structured JSON/SARIF output (file:line:rule:secret) = bounded, not a raw grep dump.
  - usage: `cat <file> | gitleaks -v stdin   |   gitleaks detect --report-format json --report-path -`
  - install: `winget install Gitleaks.Gitleaks`
- **osv-scanner** (`osv-scanner`): Google's multi-language dependency vulnerability scanner (npm/PyPI/cargo/Go/…) against the OSV database. Catches a known-bad dep BEFORE the agent runs `npm i`/`pip install`. Repo ships AGENTS.md + llms.txt = explicitly agent-aware. Structured advisory JSON.
  - usage: `osv-scanner scan source -r --format json .`
  - install: `go install github.com/google/osv-scanner/v2/cmd/osv-scanner@latest`
- **infisical** (`infisical`): Injects secrets as environment variables at runtime via `infisical run -- <cmd>`. The agent calls APIs/tools that need credentials WITHOUT the raw secret ever entering the prompt/context. Directly serves the Permissions principle: least-exposure of secrets.
  - usage: `infisical run -- <command-that-needs-secrets>`
  - install: `winget install infisical`
<!-- paw:secure-agent:end -->



<!-- paw:repo-pack:start -->
## paw capability · repo-pack
Deterministically package a selected repository subtree, git diff, or file set into a token-counted prompt artifact instead of repeated exploration and manual copying.

- **code2prompt** (`code2prompt`): Fast Rust repo packer with git-aware filtering, source tree, templates, token counting, and diff/log context. Produces stdout or a file for any agent host.
  - usage: `code2prompt src -O -   |   code2prompt . -d -O diff-context.md   |   always scope/includes before packing a large repo`
  - install: `cargo install code2prompt`
<!-- paw:repo-pack:end -->

<!-- paw:design-quality:start -->
## paw capability · design-quality
For anyone shipping UI who wants to kill 'AI slop' and keep design fidelity. Catches the visual tells of machine-made frontends (purple gradients, bounce easing, cramped padding, dark glows, skipped headings, tiny touch targets) BEFORE they ship, and pulls real design tokens from Figma into code. Saves tokens by replacing guess-restyle-reguess loops with one deterministic audit pass.

- **impeccable** (`impeccable`): Anti-AI-slop design audit. 27 deterministic anti-pattern rules + 12-rule LLM critique pass. Slash: /impeccable audit|polish|critique. CLI: npx impeccable detect src/. No API key for the deterministic rules.
  - install: `npx impeccable skills install`
- **figtree-cli** (`figtree`): Extract design tokens from Figma → CSS/SCSS/Tailwind/SwiftUI/Android/JSON. No Figma plugin / Dev Mode needed. Keeps implemented UI faithful to the design source (fidelity = quality axis).
  - install: `npm install -g figtree-cli`
<!-- paw:design-quality:end -->

<!-- paw:browser-automation:start -->
## paw capability · browser-automation
Lean browser-DRIVING capability for agents that must actually use a real browser (fill forms, upload files, navigate JS/SPA flows, scrape pages JS-render breaks). A thin self-healing CDP harness driven as a skill — ZERO MCP tool-defs — instead of the heavy playwright-MCP (47 tools) that blows the N1 ceiling for the same capability.

- **browser-harness** (`browser-harness`): Thin, editable CDP harness: connects the LLM directly to a real Chrome over ONE websocket (nothing between). The agent drives the browser by writing/running Python in agent-workspace, and the harness self-heals — it writes missing helpers + per-site domain-skills during execution and reuses them next run. ~1k lines across 4 core files. 0 MCP tool-defs (skill, not a server).
  - install: `Set up https://github.com/browser-use/browser-harness for me. Read `install.md` and follow the steps to install browser-harness and connect it to my browser.`
<!-- paw:browser-automation:end -->

<!-- paw:test-affected:start -->
## paw capability · test-affected
Run the tests a change can actually affect, reducing feedback time and test-log context while preserving a conservative full-suite fallback.

- **pytest-testmon** (`pytest-testmon`): Coverage-based dependency map selects tests affected by changed Python code and updates its local .testmondata cache after each run.
  - usage: `First run: python -m pytest --testmon   |   later runs select affected tests   |   use --testmon-noselect when safety requires full execution`
  - install: `python -m pip install pytest-testmon`
<!-- paw:test-affected:end -->

<!-- paw:quality-gate:start -->
## paw capability · quality-gate
Portable deterministic preflight gates that catch repository, CI, and documentation defects before an agent spends another reasoning or CI loop on them.

- **prek** (`prek`): Fast Rust, single-binary, pre-commit-compatible hook manager with monorepo support and shared toolchain environments.
  - install: `uv tool install prek`
- **actionlint** (`actionlint`): Static checker for GitHub Actions syntax, expressions, action inputs, reusable workflows, script injection, credentials, runner labels, cron, and dependency errors.
  - install: `go install github.com/rhysd/actionlint/cmd/actionlint@v1.7.12`
- **lychee** (`lychee`): Fast link checker for Markdown, HTML, websites, and text with structured output, retries, throttling, fragment checks, and a maintained GitHub Action.
  - install: `winget install --id lycheeverse.lychee`
<!-- paw:quality-gate:end -->

<!-- paw:api-quality:start -->
## paw capability · api-quality
Language-agnostic HTTP/API contract tests expressed as reviewable text, with compact test output and CI reports instead of ad-hoc curl sessions and large response dumps.

- **hurl** (`hurl`): Plain-text HTTP client and test runner for REST, GraphQL, SOAP, HTML, and XML with captures, assertions, parallel test mode, and JSON/JUnit/TAP/HTML reports.
  - usage: `hurl --test tests/api/*.hurl   |   use --error-format long only when compact failure output is insufficient`
  - install: `winget install Orange-OpenSource.Hurl`
<!-- paw:api-quality:end -->

<!-- paw:efficiency-min:start -->
## paw capability · efficiency-min
Token-lean dev baseline: lexical search, structural search/rewrite, and compact shell/build/test output. Global, cross-host, zero MCP.

- **rg** (`rg`): Fast lexical repo search. First rung for exact symbols, filenames, TODOs, and config keys; returns only matching lines instead of paging whole files into context.
  - usage: `rg -n 'symbol|pattern' src tests   |   rg --files -g '*.py'   |   rg -n --context 2 'error message'`
  - install: `winget install BurntSushi.ripgrep.MSVC`
- **rtk** (`rtk`): PreToolUse hook rewrites Bash commands to rtk equivalents, compresses shell output (cargo/pytest/go test/git/grep/find/ls/tsc/eslint/docker/kubectl) before it enters context. 60-90% on common dev commands (vendor).
  - install: `winget install rtk-ai.rtk`
- **ast-grep** (`ast-grep`): AST-pattern search/lint/rewrite (Rust, tree-sitter, polyglot). Fills the STRUCTURAL rung between lexical grep (host-native ripgrep) and graph (codegraph/semble): matches code SHAPE (`foo($$$ARGS)`) not text — no comment/string/whitespace false-positive lines entering context; and a multi-file codemod (`--rewrite`) = ONE bounded command + unified diff instead of N Edit round-trips. 0 MCP tool-defs.
  - usage: `ast-grep run -p 'console.log($$$A)' src/   |   rewrite: ast-grep run -p '$F.unwrap()' --rewrite '$F.expect("msg")' -U   |   rules: ast-grep scan (sgconfig.yml)`
  - install: `npm install --global @ast-grep/cli`
<!-- paw:efficiency-min:end -->

<!-- paw:doc-data-min:start -->
## paw capability · doc-data-min
Local file intelligence for dev work: query structured data and convert binary docs to markdown without loading whole files into context. Global, offline, zero MCP.

- **duckdb** (`duckdb`): In-process SQL engine that queries CSV/Parquet/JSON/SQLite FILES directly (`FROM 'data.csv'`, `sqlite_scan(...)`, globs over partitioned parquet) — no import step, no server. The agent answers filter/aggregate/join questions in one bounded call instead of paging a whole data file through context.
  - usage: `duckdb -c "SELECT col, count(*) FROM 'data.csv' GROUP BY 1 ORDER BY 2 DESC LIMIT 10"   |   schema first: duckdb -c "DESCRIBE SELECT * FROM 'data.csv'"   |   duckdb -json -c "FROM 'logs/*.parquet' LIMIT 5"   |   duckdb -c "FROM sqlite_scan('app.db','users') LIMIT 5"`
  - install: `winget install DuckDB.cli`
- **jq** (`jq`): Command-line JSON processor: pull exactly the fields/paths needed from a large JSON file or API response instead of Read-ing the whole document. Composable with curl/gh pipelines the agent already runs.
  - usage: `jq '.items[] | {id, name}' big.json   |   jq -r '.[].url' resp.json   |   shape first: jq 'keys' obj.json / jq 'length' arr.json`
  - install: `winget install jqlang.jq`
- **markitdown** (`markitdown`): Official Microsoft converter: docx/xlsx/pptx/pdf/html/images (15+ formats) → markdown that PRESERVES structure (headings, lists, tables, links) — built explicitly for LLM pipelines. One call makes a binary office file greppable/sliceable text.
  - usage: `markitdown report.docx -o report.md   |   markitdown sheet.xlsx   |   markitdown deck.pptx   |   then grep/slice the md instead of re-converting`
  - install: `pip install "markitdown[docx,xlsx,pptx,pdf]"`
<!-- paw:doc-data-min:end -->
