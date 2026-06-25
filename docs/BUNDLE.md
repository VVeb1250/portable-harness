# BUNDLE — L0 curated tools

> v2 · 2026-06-21 · เจ้าของ: supimol.web@gmail.com · คู่กับ [SHARED-BRAIN](./SHARED-BRAIN.md) · [BENCH](./BENCH.md) · [STATUS](./STATUS.md)
> **2 layer แยกกัน:** *mental model* ยุบ lean (เกือบทุกตัว 0-tax CLI stack อิสระ) · *install UX* เก็บ **named-set แบบ portaw** (`install <set> --host` = ลงทีเดียว+wire+verify) เพราะ = ความสะดวกผู้ใช้ (North Star #2).

---

## กฎเดียว (mental model)

**0-tax core (always) + sets ลงตามต้องการ (named, on-demand) + MCP = zone เดียวที่ tax/N1 กัด.**
ลำดับเลือก: native host > CLI/hook (0-tax) > MCP (taxed, ≤2-3/host). วัด [`bench/mcp_tax.py`](../bench/mcp_tax.py).

## 1. Core — always-on, 0-tax (ทุก host)

| layer | tool | mode | สถานะ |
|---|---|---|---|
| token-cut (tool-output) | **RTK** 0.42 | hook (claude/cursor/gemini/copilot) · Codex=shim/pipe | ✓ installed |
| token-cut (assistant-output) | **caveman** | hook (SessionStart/UserPromptSubmit) | ✓ active |
| memory | **ICM** 0.10.53 `standard` | CLI+skill+hook (NO MCP) | ✓ installed |
| structural search/rewrite | **ast-grep** 0.43 | CLI | salvage — bench +69% precision/+76-97% codemod |
| instructions | **AGENTS.md / CLAUDE.md** | @import per host | ใช้อยู่ |

triad ครบ: lexical (grep native) / **struct (ast-grep)** / graph (codegraph). 0 tool-def tax.

## 2. MCP — zone เดียวที่ต้อง curate (tax + N1 ceiling)

| server | tools | tax eager | rule |
|---|---|---|---|
| **codegraph** | 8 | 1,653 | code-intel บน **CC** (lazy=idle 0, richer: callers/impact) |
| **semble** | 2 | ~509 | code-intel บน **load-all host** (Codex/Gemini) แทน codegraph — eager leaner, search-only |
| **fetch** | 1 | 290 | host-conditional: ข้ามถ้ามี WebFetch native (CC); ใส่ Codex/Gemini |

- **code-intel = codegraph XOR semble ต่อ host** (ห้ามโหลดคู่). CC=codegraph · Codex/Gemini=semble.
- **≤2-3 eager MCP/host.** **ตัด eager:** Desktop_Commander (11.5k, ซ้ำ native Read/Write/Bash) · context7 (→ on-demand) · plugin_*/chrome.

## 3. Installable sets — install UX แบบ portaw (named, ลงทีเดียว+wire+verify)

> ผู้ใช้เลือก **set** ไม่ใช่ tool ทีละตัว. `<harness> install <set> --host <host>` → ลง+patch config+verify-gate ในคำสั่งเดียว.
> **salvage portaw ทั้ง machinery:** `sets.json` (registry) **+ `install`/`sets list|show`/`verify`** (installer/wirer) — ไม่ใช่แค่ data. ส่วนใหญ่ 0-tax CLI → stack อิสระใต้ N1, install ตอนต้องใช้ (YAGNI).

| set | คือ | tools | tax | vet |
|---|---|---|---|---|
| **efficiency-starter** | coding (= core เรา) | codegraph/semble · rtk · ast-grep | host-cond | ✓ tested |
| **secure-agent** | permissions/supply-chain | nah(hook) · gitleaks · osv-scanner · infisical | **0 MCP** | ✓ tested PASS |
| **data-query** | query CSV/Parquet/SQLite/JSON | duckdb · jq | **0 MCP** | ✓ +99.96% vs Read |
| **doc-extract** | docx/xlsx/pptx → md | markitdown ⚠️`[docx,xlsx,pptx,pdf]` ไม่ใช่`[all]` | **0 MCP** | ✓ tested |
| **repo-pack** | subtree→LLM-prompt (token-counted) | **code2prompt** 4.2 (yek=speed-alt, ห้ามโหลดคู่) | **0 MCP** | ✓ Win install-test (`bin/code2prompt.exe`, pack docs/=28.9k tok, `-d` git-diff=3.1k) |
| **design-quality** | anti-slop UI | impeccable(skill) · figtree | **0 MCP** | ✓ slop-catch |
| **context-quality** | anti-halluc lib docs | context7 (2t) | 927/0 | ✓ idle-calc |
| **web-research** | research | fetch · ladder: scrapling→searxng→exa→firecrawl | 259/0 | ◐ CC: WebFetch พอ |
| **browser-automation** | browser driving | browser-harness (CDP skill) | **0 MCP** | ◐ ไม่ install-test · high-priv |

**อย่าใช้ MCP-wrap** (portaw rejected, idle-tax เปล่า): ast-grep-mcp · duckdb-mcp · playwright-mcp(47t) · **scrapling-mcp (15,859 tok 🐋)** · firecrawl-mcp. CLI form เสมอ.

## 4. Compat — tested 2026-06-21 (LIVE, secure-agent ลงครบบนเครื่องนี้)

- ✅ **rtk × CLI sets ไม่ชน** (rtk rewrite: git/ls→rewritten; ast-grep/duckdb/jq/markitdown/gitleaks/osv→**passthrough**).
- ✅ **rtk + nah PROVEN LIVE** — `settings.json` PreToolUse(Bash) = **rtk→nah**; รันทั้ง session ผ่าน 2 hook ไม่ชน (`nah log` ยืนยัน). nah guard จริง: `curl\|bash`→**BLOCK**(RCE) · `rm -rf ~`→ASK · `git status`→ALLOW.
- ⚠️ **FRICTION (intra-bundle) — RESOLVED don't-loosen (2026-06-22):** nah classify = `unknown→ASK` สำหรับ ast-grep/duckdb/rtk (jq=ALLOW อยู่แล้ว). **planned glue (classify→allow) = REJECTED = security hole:** `nah classify` match command-**prefix** + tools **dual-use** (พิสูจน์ `nah test`: `ast-grep -U`=rewrite · `rtk rm -rf`/`rtk sh -c 'curl|bash'`=wrapper bypass · `duckdb DROP/ATTACH/INSTALL`) → blanket-allow = silent-mutate / nah-bypass / RCE (A-12). nah `unknown→ASK` = **ถูกต้อง**. fix: accept ASK (ASK→proceed ไม่ block) หรือ nah **LLM-classifier** opt-in (`nah key`, content-aware). secure-agent ship ตามเดิม.
- ✅ **complement ไม่ทับ:** codegraph(code)/context7(lib docs)/web-research(remote)/data-query(local files)/doc-extract(binary) = 5 surface แยก.
- ✅ **repo-pack composition (2026-06-25):** code2prompt = context **producer** (subtree→token-counted prompt) ต้นน้ำ; ที่เหลือ = consumer ปลายน้ำ คนละ stage → ไม่ชน. **vs rtk** = code2prompt เป็น binary แปลกหน้า → **passthrough** (เหมือน ast-grep/duckdb; git ทับแค่ผิว: rtk=อ่าน git ad-hoc · c2p `-d`=แพ็ค PR-context) *(by-design; live rtk-probe ยังไม่รัน)*. **vs ctx-mode = synergy ไม่ใช่ overlap:** `ctx_execute` รัน `code2prompt … -O pack.md` (output 0-ctx) → `ctx_fetch_and_index` → `ctx_search` ดึงเฉพาะ slice = **context-compression แบบ routing แทน headroom** (portable, 0 compile-tax). **vs ast-grep/codegraph** = coarse(subtree) vs precise(symbol), c2p เลือกไฟล์→feed ast-grep ได้.
- ⚠️ **MCP eager tradeoff** (codegraph XOR semble · ≤2-3). CLI sets ไม่มี tradeoff (นอกจาก nah-classify glue ข้างบน).
- ✅ **live compat re-verify (2026-06-25, this machine, prep-real-use):** ทุก bundle CLI รันจริง + version ตรง — ast-grep 0.43.0 · duckdb 1.5.3 · jq 1.8.1 · gitleaks 8.30.1 · osv-scanner 2.3.8 · `bin/code2prompt.exe` 4.2.0. **rtk passthrough identity PROVEN** (`rtk <tool> --version` == `<tool> --version` byte-identical: ast-grep/jq/duckdb) → rtk-hook-active ไม่ mangle bundle CLI. **test-affected set (testmon 2.2.0) validated LIVE:** `pytest --testmon` baseline สร้าง `.testmondata` รัน 23/23; rerun no-change → **select 0** ("no tests ran") = AST-aware selection ทำงานจริงบน repo นี้. ⚠️ testmon = pytest **plugin** (`pytest --testmon`) ไม่ใช่ standalone binary. `.testmondata` → gitignored.
- 🐛 **FIX (2026-06-25): bare `pytest` collection bug** — default crawl ลง `bench/swe_probe/` frozen artifacts (`test_output.txt` docstring → doctest parser ValueError "inconsistent leading whitespace") = 5 collection error. fix = `pyproject.toml [tool.pytest.ini_options]` `testpaths=["tests"]` + `norecursedirs=["bench",...]`. หลัง fix: bare `pytest` = 23 passed 0 error; `verify_freeze.py` ยัง PASS (8 instances). real-use readiness ✓.

## 5. Host matrix

| host | core | MCP eager | token-cut | enforce tier (A-13) |
|---|---|---|---|---|
| Claude Code | RTK hook · ICM · caveman · ast-grep | codegraph (fetch ซ้ำ WebFetch→skip) | `rtk hook claude` ✓ | **A** auto-hook — token-cut + nah hard-BLOCK guaranteed |
| Gemini | RTK init · ICM · ast-grep | semble + fetch | `rtk init --gemini` ✓ | **B** init + some-hook |
| Codex | RTK by AGENTS.md instr · ICM(`icm.exe`) · ast-grep | semble + fetch | manual instr (rtk init ไม่มี `--codex`) | **C** instruction + `nah codex setup` + sandbox (no-hook) |

> ⚠️ **enforcement ไม่เท่ากันทุก host (smoke 2026-06-22, A-13):** shared brain (ICM memory + AGENTS.md) = portable จริง; แต่ **automatic guarantee (hook token-cut + nah hard-BLOCK) = Claude-only strong**, degrade → Gemini(medium) → Codex(instruction+sandbox, softer). **secure-agent บน Codex = `nah codex setup` (config approval-mode + `~/.codex/rules/nah-authority.rules` + sandbox) ไม่ใช่ hard-block** — โฆษณา guarantee ให้ตรง tier.

```powershell
# install UX (target — reuse/port portaw installer):
#   harness install secure-agent --host claude-code   # ลง+wire+verify ทีเดียว
#   harness sets list                                  # ดู catalog
# verify:
py bench/mcp_tax.py --all      # eager MCP เล็ก
icm.exe recall "smoke" ; rtk gain
```

## 6. Recheck (decay triggers)

### scout 2026-06-25 — new-set candidates (3 gaps probed)

> reuse-don't-rebuild (#2) + landscape #3. verdict: **1 คุ้มเพิ่ม · 1 optional-gated · 1 ปฏิเสธ.** อย่าเกินนี้ (scope-creep vs economics-gate A2).

- **LSP / type-aware nav — ❌ DON'T BUILD (commodity, native-absorbed).** CC v2.0.74 (Dec 2025) = LSP native 11 ภาษา · Kiro tree-sitter built-in · Qwen native LSP → platform ดูดไปแล้ว (STATUS "rent commodity"). gap เหลือแค่ **Codex/Gemini load-all host** → ถ้าจำเป็น = thin LSP-CLI (multilspy/lsp-cli) ต่อ host, ไม่ใช่ set. recheck: Codex/Gemini native-LSP coverage.
- **test-affected — ✅ CANDIDATE (gap จริง, ตรง repo).** รัน test เฉพาะที่ diff กระทบ (faster loop, ↓token จาก log). **testmon** (pytest, coverage-dep map, mature) = pick สำหรับ repo นี้ (python) · **Tach** (git+import-graph) = alt. 0-tax CLI. **VETTED 2026-06-25 (head-to-head บน repo นี้) → ✅ PROMOTE, scope = category set ไม่ใช่ single-tool.** empirical: testmon install=1 pip 0-config · baseline 23 tests/1.13s สร้าง `.testmondata` · selection: no-change=0 ✓, comment-only=0 ✓ (**AST-aware**, ตัด non-semantic edit), real edit `_estimate_cost`=**4/14 router tests, deselect 10, exclude blackboard ทั้งหมด** @ 0.14s (**8× cut**, scale ตาม suite-size). **codegraph-affected = แพ้สำหรับงานนี้:** (a) ไม่มี `.codegraph/` index บน repo นี้เลย → ต้อง build แยกก่อน (testmon build เองใน 1 baseline) · (b) static symbol→symbol, ต้องเขียน glue map symbol-impact→test-name เอง (testmon ทำ native) · (c) miss runtime-only dep (fixture/conftest/dynamic dispatch) ที่ coverage เห็น. **= ไม่ใช่คู่แข่ง คนละแกน** (codegraph=code-intel/refactor multi-lang · testmon=test-selection runtime python). ⚠️ caveat: testmon = **python/pytest only** → set `test-affected` ต้อง **language-tiered** (python=testmon ✓validated · JS=`jest --changedSince` · go=`go test`+impact). + payoff scale ตาม suite ใหญ่ → gate adoption ที่ slow-suite repo (harness นี้เล็กไป, marginal). fit core-concept: ↓CI-time/↓test-log-token + ↑qual (red-green loop เร็ว→iterate มาก).
- **semantic-search (4th search modality) — 🟡 CANDIDATE, portability-gated.** 2026 consensus ยืนยัน triad เรา (lexical grep / struct ast-grep / graph codegraph) = ถูก; semantic = optional 4th. **Gortex** (single-binary, BM25/FTS5 + GloVe-50d embedded 3.8MB zero-API + RRF + graph-rerank) = portable สุด · **CocoIndex Code** (AST + sentence-transformers local, "70% token save", trending) ⚠️ **torch-dep หนัก = ภาระแบบ headroom** (compile/size, ขัด portable). rule: เพิ่มได้ต่อเมื่อ **local + light (Gortex-style embedded), ห้าม torch.** ส่วนใหญ่ overlap codegraph → low-pri. **VETTED 2026-06-25 ([zzet/gortex](https://github.com/zzet/gortex)) → portability gate ✅ PASS + reframe = codegraph CHALLENGER ไม่ใช่ "4th-modality add-on".** Go single-binary · GloVe-50d baked 3.8MB · 100% local (#10 ✓) · **257 lang · multi-repo · BM25+vector+RRF+graph-centrality + impact analysis** = **superset codegraph** (codegraph=graph เดียว/single-repo). eval R@1 42.3 / R@5 55.1 / exact R@5 96.8 · cold ~200ms incremental. CocoIndex = ❌ (torch, ขัด rule). ⚠️ maturity (#4): **solo-dev (zzet), GitNexus rebrand = young/churn** → risk. **next vet = install Win binary + index repo นี้ + head-to-head vs codegraph** (replace-or-augment?). ถ้าชนะ = 2-in-1 (ลด MCP count, ตรง #7 token-budget). **HEAD-TO-HEAD DONE 2026-06-25 (v0.52.0 signed win zip → indexed repo → query) → verdict = AUGMENT-only via CLI, ❌ NOT drop-in replace, ⛔ NEVER `gortex init`.**
  - ✅ **portability gate PASS (beats codegraph here):** signed prebuilt `gortex_windows_amd64.zip` (SHA256 ✓ + cosign .sig/.pem) 48M single binary 0-compile → `bin/gortex.exe`. index **256,328 nodes / 1,157,579 edges / 98.8% py coverage in ~93s** (daemon+track). codegraph = ยังไม่มี `.codegraph/` index บน repo นี้เลยหลายเซสชัน (ต้อง node + per-repo build).
  - ✅ **symbol search exact** (`query symbol _estimate_cost` → `paw\router.py:278`) = par codegraph_search.
  - ❌ **`gortex init` = INVASIVE (deal-breaker, ขัด preserve-config + North Star #2):** default เขียนทับ **CLAUDE.md + AGENTS.md** (append 29-30 บรรทัด) + สร้าง **`.claude/ .cursor/ .gemini/ .vscode/`** + ติดตั้ง **CC PreToolUse deny-hooks + per-host MCP + 20 auto-skills** โดยไม่ถาม. ต้อง revert 2 md + 4 dir. — ใช้ได้แค่ `track` manual, ห้าม init.
  - ❌ **no ignore-by-default:** crawl `bench/swe_probe/.swebench-venv` + sympy → `query callers route` = **ambiguous** (โดน aiohttp site-packages กลบ) · auto-skills ตั้งชื่อตาม pandas-test dirs (garbage) · vector index **auto-OFF >100k texts → BM25-only** (= มีแล้วผ่าน grep/ast-grep). ต้องเขียน scoped-ignore เองก่อนใช้.
  - ❌ **MCP surface = 100+ tools** → ถ้าโหลด eager = tax มหาศาล (vs codegraph 8/1653 tok). ปลอดภัยเฉพาะ **CLI-daemon** (always-on ~493MB RAM).
  - **decision:** keep **codegraph** สำหรับ CC code-intel. gortex = augment-only, CLI `track` (NEVER init), mandatory scoped-ignore — ยังไม่เข้า bundle. binary เก็บ `bin/gortex.exe` (gitignored). **recheck-trigger:** init opt-in/non-invasive + ignore-by-default for vendored/venv.

### scout 2026-06-25b — ↓token+↑qual axis sweep (core-concept hunt)

> ค้นตรง win-condition เสา bundle (↓tok AND ↑qual พร้อมกัน = A2 "ยังไม่พิสูจน์"). **ผล: ส่วนใหญ่ยืนยัน bet เดิม; new actionable = 1 (Squeez, research→watch).**

- **↓token: rtk = anchor VALIDATED (external), ไม่มี portable challenger.** sweep ยืนยัน rtk = leading portable token-cutter (Rust single-binary, 0-dep, 39.5k★, v0.38, cut 60-90%) = partial validation A-06. **LLMLingua/-2 = ❌ REJECT** (neural perplexity-compressor → torch-dep + "loss of format crucial for agent tasks → substantial perf drop"; format-lossy = ขัด quality+portable). neural prompt-compression ทั้งตระกูล = อย่าไล่.
- **⭐ WATCH: Squeez** (arxiv 2604.04979, Apr 2026 "Task-Conditioned Tool-Output Pruning for Coding Agents") = next-gen rtk: prune tool-output **ตาม task** (rtk = static rules) → ตัด noise เฉพาะที่ task ไม่ใช้, เก็บ signal = **↓token + ↑qual พร้อมกัน** = ตอบ A2 ตรงๆ. **VETTED 2026-06-25 → code SHIPPED ✅ ([KRLabsOrg/squeez](https://github.com/KRLabsOrg/squeez), Apache-2.0): CLI + model `squeez-2b` (Qwen3.5-2B LoRA) + dataset.** perf: 0.86 recall / 0.80 F1 / **−92% input tokens** (เหนือ zero-shot 35B +11 recall). **แต่ไม่ drop-in:** engine = **2B-model inference ต่อ tool-output** → (a) gated บน local-model-runtime = **ผูก R-01 SLM gate เดียวกัน** (ยังไม่มี local SLM) · (b) hot-path 2B-infer/tool-call vs rtk's instant rust-rules = latency/cost tradeoff จริง. → **WATCH ต่อ, unblock-trigger = local SLM (รวมกับ R-01)**, ไม่ใช่ rtk-replacement วันนี้. cross-ref [RESEARCH-RADAR R-04](./RESEARCH-RADAR.md).
- **↑quality: field-consensus 2026 = ของที่เรามีในคอนเซปต์แล้ว.** ensemble/dual-review (2 solve→3rd judge) = **team3/santa-loop** ✓ · tiered-routing cheap-local→expensive = **R-01 SLM-router** (marked) ✓ · RAG/live-doc grounding = **context7 + web-research** ✓. SaaS hallucination-detector (Patronus LYNX/Braintrust) = ❌ cloud eval-platform, ไม่ portable CLI, code ออกนอกเครื่อง (#10). residual = deterministic guardrail (ruff/mypy pre-gate) แต่ overlap ECC quality-gate skill → low-pri.

- **Headroom** — **REJECTED จาก bundle 2026-06-25 (live-proof):** ลงจริงบนเครื่องนี้
  ล้มเหลวยืนยัน — `headroom-ai` ไม่มี prebuilt wheel **เลยทุก version/OS** → pip
  compile Rust จาก source ทุกครั้ง → ต้อง MSVC `link.exe` (VS BuildTools workload
  ไม่ได้ลง) + py3.14 ไม่มี wheel. = **compile-tax ทุก host** (ไม่ผูก Windows; mac/Linux
  เครื่องเปล่าไม่มี gcc/clang ก็เจอ). ขัด North Star portable+สะดวก. ตัด — rtk(binary)/
  ctx-mode(node) ไม่มีภาระนี้. bench พร้อม (`bench/_headroom_stack_ab.py`) ถ้าจะรื้อทีหลัง
  ต้องลง toolchain ก่อน. (A-09 → closed)
- **repo→prompt packer (NEW surface, candidate 2026-06-25):** gap จริง — bundle ไม่มี
  ตัว pack subtree→LLM-context (token-budget). **code2prompt** v4.2.0 = primary pick:
  **prebuilt Win .exe (GH Releases)** + brew + cargo + pip-sdk → 0-compile ผ่าน gate ที่
  headroom ตก; token-count built-in + git diff/log/branch (เสริม rtk PR-context) +
  template/JSON. **yek** = speed alt (Rust, 5s vs repomix 22min, `irm yek.ps1` native
  Win, git-priority + `--tokens 128k`). repomix = popular(21k★) แต่ Node+ช้า+MCP-lean =
  backup. **สถานะ ✓ install-tested Windows 2026-06-25** (prebuilt `*-pc-windows-msvc.exe`
  จาก GH release v4.2.0 → `bin/code2prompt.exe`, native PS run, pack docs/=28.9k tok;
  darwin+linux-gnu asset มีครบ → cross-OS by asset). promoted → §3 set `repo-pack`.
  **rtk-passthrough = live-confirmed ✓** (รันผ่าน Bash tool rtk-hook-active, exit=0,
  token-count ออกถูก, ไม่ mangling). **Linux exec smoke ✓** (linux-gnu ELF รันใน
  Debian/glibc Docker, pack docs/=7,001 tok = ตรงกับ Windows 7,002). **macOS** = Mach-O
  x64+arm64 valid (verify format) แต่ exec ไม่ได้ที่นี่ (ไม่มี mac host) = ค้างตัวเดียว.
- **nah-classify** — ✓ **RESOLVED: ไม่ loosen** (prefix-match + dual-use = security hole, A-12). dual-use ASK = by-design. ปิด friction → nah LLM-classifier opt-in (`nah key`), ห้าม prefix-allow.
- **installer salvage** — portaw `install`/`verify` archived; ตัดสิน reuse-as-is vs port-thin (decision ค้าง).
- portaw vet 06-05..15 (~2wk) → re-confirm tool version ตอน activate แต่ละ set.
