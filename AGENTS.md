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










<!-- paw:optional-surface:start -->
## paw optional capabilities
Optional/specific bundle capabilities are intentionally not kept in always-on context. Before using repo-pack, code-intelligence, context-quality, browser automation, quality gates, API tests, or design tools, run:

```powershell
python -m paw surface "<task>" --cwd . --audit
```
<!-- paw:optional-surface:end -->
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

<!-- paw:local-memory:start -->
## paw capability · local-memory
Local-first semantic memory and cross-agent recall through ICM. Keeps durable project decisions and high-signal lessons outside always-on prompt context, then recalls bounded slices when needed.

- **icm** (`icm`): Local semantic memory CLI for durable decisions, lessons, and cross-host recall without always-loaded MCP schema tax.
  - usage: `icm.exe recall "what did we decide about bundle init" --read-only   |   icm.exe store -t decisions -c "summary" -i high -k "bundle"`
  - install: `Follow ICM installer or existing machine install; verify with icm.exe --version`
<!-- paw:local-memory:end -->

<!-- paw:status-sync:start -->
## paw status-sync (อัพเดท snapshot)

เมื่อจบงานสำคัญ หรือก่อนปิด session ให้อัพเดท snapshot ของโปรเจค
เพื่อให้ session ถัดไปเห็นสถานะล่าสุดผ่าน paw resume block:

1. `paw memory status save` — เก็บ git layer อัตโนมัติ (branch/commit/dirty)
2. `paw memory status note "<ทำอะไร>/<เจออะไร>/<จะทำอะไรต่อ>"`

snapshot จะถูก inject กลับเป็น resume block ตอน SessionStart.
ห้ามลบ block นี้ด้วยมือ — ใช้ `paw memory status-sync remove`.
<!-- paw:status-sync:end -->
