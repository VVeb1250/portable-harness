# portable-harness — Working Mindset

> เป้าหมายโปรเจกต์: harness พกพา (curated tools + token-cut + shared-memory ข้าม heterogeneous agents).
> ออกแบบ: [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) · L0 brain: [docs/SHARED-BRAIN.md](docs/SHARED-BRAIN.md) · doc map: [docs/README.md](docs/README.md)
> **ทุก session คิดแบบนี้** (mindset ของเจ้าของ — เขียนไว้ให้ส่งต่อข้าม session).

---

## AI navigation — กัน session หลงทาง

ก่อนงาน non-trivial ให้อ่านตามลำดับนี้:

1. `CLAUDE.md` ไฟล์นี้ — mindset/decision rules.
2. `AGENTS.md` — Codex-specific bridge.
3. `docs/STATUS.md` section 0 — current truth เท่านั้น.
4. `docs/PAW-NORTH-STAR.md` — product concept: portable harness curator/linker/launcher.
5. `docs/NO-DAEMON-BASELINE-BACKLOG.md` — next work.
6. `docs/README.md` — map ว่าไฟล์ไหน authoritative / historical.

ห้าม resume TODO จากไฟล์ historical draft โดยตรง ถ้า `STATUS.md` หรือ backlog
ไม่ได้ชี้ให้ทำ. หลักปัจจุบัน: **no-daemon / CLI-first ก่อน**; optional
sidecar, Memoir graph, และ `skills.sh` bundle เป็น later experiments.

## North star (ใช้ตัดสินทุกอย่าง)

1. **Possibility + user-impact มาก่อน** — คิดว่า "ทำได้แค่ไหน" และ "ผู้ใช้ได้อะไร" ก่อนเรื่องเทคนิค.
2. **Win condition = best *และ* สะดวกที่สุด** — ความซับซ้อนที่ตกถึงผู้ใช้ = ล้มเหลว ต่อให้ฉลาดแค่ไหน. ไม่ยุ่งยากสำหรับผู้ใช้.

## หลักคิด (every session)

1. **Challenge everything** — docs / code / คำตอบเก่าของฉัน / **ไฟล์นี้** อาจไม่จริงหรือไม่ดีที่สุด. โต้แย้งได้เสมอ. อย่าถือเป็น ground truth.
2. **Reuse, don't rebuild** (ethos หลัก) — search GitHub / registry / docs ก่อนเขียนอะไรใหม่. มีของแก้ 80% แล้ว → adopt / port / wrap. เขียนเองแค่ **glue บางๆ** ที่ยังไม่มี.
3. **Landscape เปลี่ยนรายวัน** — ของดีโผล่วันต่อวัน → re-search หาตัวแทนเสมอ. assumption เสื่อมอายุ (เช่น subscription/ToS พลิกในไม่กี่วัน) → mark + recheck, อย่า build บนสมมุติฐานตายตัว.
4. **Substance > stars** — ดาวไม่สำคัญ. vet ด้วย commits / releases / tests / recency / architecture / host-coverage. popular ≠ ถูก; obscure/solo ≠ ผิด.
5. **Anti-vibes / empirical** — วัดก่อน lock. token-delta benchmark (เช่น `portaw bench` / `ccusage`) ฆ่า vibes. อย่าเดาตัวเลข.
6. **Pivot freely** — sunk cost ไม่ใช่เหตุผลทำต่อ. ทรงไม่เวิค → archive แล้วเปลี่ยน. (เปลี่ยนบ่อยเป็นเรื่องปกติ.)
7. **Token budget เป็นของจริง** — tool-def = tokens ทุก turn. CLI > MCP บน load-all host (0 def). consolidate (many-tools-in-few-defs) > sprawl. เพดาน ≤2-3 active MCP/set.
8. **Cross-host by default** — CC / Codex / Gemini / Cursor / … portable. ไม่ผูก vendor เดียว. author-once → หลาย host (AGENTS.md / rulesync แนว).
9. **Verify before asserting** — fact / library / policy ที่ load-bearing → search + cite, ห้ามตอบจากความจำ.
10. **Compliance + privacy = constraint** — ToS (first-party interactive vs programmatic/metered), source code ไม่รั่วออกนอกเครื่องโดยไม่ตั้งใจ. เรื่องนี้ block ได้.

## วิธีทำงานกับฉัน

- ให้ **recommendation** ไม่ใช่ survey เฉยๆ — เลือกมาให้ พร้อมเหตุผล + tradeoff.
- **honest self-correction** — หลักฐานพลิก → บอกตรงๆ แล้วแก้.
- เก็บ **candidate backlog** (shortlist น่าสนใจ, ไม่ใช่ commitment) ก่อน deep-vet.
- ออกแบบให้ **replaceable** + มี **assumption ledger** (อะไร decay ได้ ระบุ trigger ที่ต้อง recheck).
- งานวิจัยหนักได้ — parallel scout / search เยอะ เพื่อหา "ตัวที่ดีที่สุด" จริง.

## Prior art ของฉันเอง (ดูเป็นตัวอย่างวิธีคิด)

- `~/.claude/port-a-whip` — portaw (**archived, ทรงไม่ค่อยเวิค**, ยังไม่ทำต่อ). ใช้เป็น *ตัวอย่าง* ของ:
  - `bench/` = A/B token benchmark จริง (native vs fetch vs scrapling, codegraph/rtk on-off)
  - `registry/candidate-backlog.md` = วิธี vet candidate (leverage / ↓tok↑qual / maturity / overlap / host)
  - kernel / sets / adapters split + cross-host (.claude/.agents/.cursor)
- อย่าถือ portaw เป็นฐานที่ต้องใช้ — salvage แนวคิดได้ แต่ของบางส่วนแทนได้ด้วย tool สำเร็จรูป (เช่น ICM ทำ memory + host-wiring เองได้).

> หลัก #1 ใช้กับไฟล์นี้ด้วย: ผิด/ล้าสมัย → แก้.

<!-- paw:ctx-routing-test start (STATUS §D live-test instrument — kill = ลบ block นี้ + .mcp.json) -->
## context-mode routing (repo นี้, live-test)

`.mcp.json` เปิด `context-mode` (ctx_* tools) ใน repo นี้ จ่าย ~7.9k tok/session → **ต้อง route จริงถึงคุ้ม** (replay: 8% compliance = ยัง net-negative; gate folded เข้า swe-work, route ด้วยมือ 3-5 session แล้ว terminal keep/kill — STATUS §D). กติกา:
- **bulky shell output** (git log/diff, grep/rg, ls -R, build/test logs, cat ไฟล์ใหญ่) → `ctx_execute` / `ctx_execute_file` (Think-in-Code: log เฉพาะคำตอบ).
- **doc/web/ไฟล์ใหญ่ที่ต้องค้น** → `ctx_fetch_and_index` + `ctx_search` (FTS5 lossless; query แบบ keyword ตรง doc-vocab → recall 100%).
- **ข้าม** (route ไม่คุ้ม): output < ~200 tok · read-to-edit (ต้องการ verbatim bytes) · git_diff สั้น. ของเล็กใช้ Bash/Read ปกติ.
- semantic memory = ICM (ไม่ใช่ ctx_search; complementary). guard = nah (survives).
<!-- paw:ctx-routing-test end -->


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
