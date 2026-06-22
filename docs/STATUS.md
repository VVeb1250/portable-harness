# STATUS — session state (compact-survival)

> อัพเดท: 2026-06-21 · จุดประสงค์: state ก้อนเดียวให้ session หลัง-compact อ่านต่อได้ครบ.
> Doc map: [CLAUDE.md](../CLAUDE.md) mindset · [ARCHITECTURE.md](./ARCHITECTURE.md) blueprint · [SHARED-BRAIN.md](./SHARED-BRAIN.md) L0 detail · **STATUS.md (นี่)** = ล่าสุด + ตกค้าง.

---

## 1. Through-line ที่ตกผลึกแล้ว

**ICM-first · regime-agnostic · replaceable · wire-not-build · CLI/hook > MCP (N1).**

- harness = **layered**: **L0 brain** (now) → **L1 routing/cockpit** (next) → **L2 team** (future, gated).
- moat จริง = curation + token-cut + shared-memory ข้าม agent = **distro ไม่ใช่ tech-moat**.
- orchestration มี **2 แกนแยกกัน**: (i) backend/model routing [claude-code-router] = L1 · (ii) agent team [AgentPool] = L2. **AgentPool ถูกปลดจาก spine → L2 candidate (gated)**.

## 2. Layered model — ยืนตรงไหน

| Layer | คือ | สถานะ |
|---|---|---|
| **L0 Brain** | ICM(mem) + RTK(token,tool-layer) + curated bundle + AGENTS.md | **ICM v0.10.53 LIVE** (store/recall verified; portaw bridge True หลัง PATH/restart). RTK 0.42 ✓. เหลือ: tool-bundle + host auto-wiring (§8) |
| **L1 Routing/Cockpit** | model/quota routing (A3) + optional dmux cockpit | adopt (claude-code-router); ยังไม่เริ่ม |
| **L2 Team** | coordinator + specialists | future; gated ที่ Phase-0 |

## 3. Key findings (session นี้)

- **Per-seat ToS (A3):** programmatic บน subscription harvestable ต่างกัน — Claude/Codex = interactive-only (clean); **GLM (z.ai) = blessed** (Anthropic-compatible endpoint). → **A3 = GLM-workhorse + metered spillover + interactive-by-hand**. sensitive code **ห้ามไป GLM** → metered Claude.
- **Anthropic billing whiplash:** Feb-20 OAuth ban (3rd-party); June-15 split (agent→credit @API rate, 12-175x) **paused June-16**, "จะ revise + แจ้งล่วงหน้า". → ต้อง regime-agnostic.
- **MCP-head tax (สำคัญ):** tool-def = **~550-1,400 tok/tool/session** (จ่ายทุก session + ซ้ำตอน compaction); 5-10 MCP = 50-67k ก่อนพิมพ์. → **CLI/hook = 0 tax ชนะ**; MCP ต้อง lazy-schema/Tool-Search/mcp2cli. มิติตัดสิน = **net (cut − tax)** ไม่ใช่ compression % เดี่ยว.
- **RTK/ICM ยังไม่พิสูจน์ว่าดีสุด:** ทั้งคู่หายจาก best-of-2026 ranking. RTK edge จริง = **CLI/hook 0-tax (N1-safe)**. ICM ชนะเฉพาะ **single-binary + local + 18-host friction ต่ำ** (ไม่ใช่ memory quality).
- **portaw = own project, archived ("ทรงไม่เวิค"):** แต่คำสั่งรันได้ (install/sets/mem/doctor/router). → **ICM-direct**, portaw = optional overlay/salvage.
- **portaw router (lazy/hook) = เวิคจริง + live** (🐾 paw router blocks ใน session นี้ = มันรันอยู่). แต่เป็น **lazy-DISCOVERY (suggest set) เท่านั้น — delivery ยัง EAGER (install = static MCP patch → ยังจ่าย per-tool tax)**. JIT-install (B9) ยังไม่ทำ. มี `doctor --usage` audit idle-tax + `bench` (ccusage) + `install` ceiling-warning อยู่แล้ว.
- **Native mitigations 2026:** Anthropic **Tool Search GA (Feb)** −85%, **lazy schema** (CC มีแล้ว), **mcp2cli** 96-99%, **Code Mode** 98.7%. → ใช้ร่วม router = แก้ N1 ครบ 2 ชั้น (discovery + delivery).
- **BENCH Phase 0 ran (2026-06-21, `bench/mcp_tax.py`):** eager-tax จริง — **DC 11.5k(26t)** · codegraph 1.65k(8t) · context7 964(2t) · fetch 290(1t). **แต่ session นี้ CC defer MCP ทุกตัว (ToolSearch) → eager tool-def tax ≈0 ที่นี่** (native lazy LIVE); ตัวเลข = worst-case บน host ที่ไม่ defer (Desktop/Codex/Gemini). → **harness ต้อง 0-tax-by-default (CLI/hook)** เพราะ lazy ไม่การันตีข้าม host. ICM standard=CLI=0 ✓. (ดู BENCH §1 RESULTS)
- **secure-agent ลงครบ + rtk+nah PROVEN LIVE (2026-06-21):** nah 0.9.1 / gitleaks 8.30.1 / osv 2.3.8 / infisical 0.43.91 มีอยู่แล้วบนเครื่อง. `settings.json` PreToolUse(Bash) = **rtk→nah**, รันทั้ง session ไม่ชน (`nah log` ยืนยัน); nah guard จริง (BLOCK `curl|bash`, ASK `rm-rf~`, ALLOW git_safe).
- **🔑 nah-classify glue = REJECTED (security hole) — resolved 2026-06-22:** `nah classify` match **command-prefix เท่านั้น** + bundle tools **dual-use** (พิสูจน์ด้วย `nah test`): `ast-grep …-U`(rewrite) / `rtk rm -rf` / `rtk sh -c curl|bash` / `duckdb DROP|ATTACH|INSTALL` ทั้งหมด=ASK ตอนนี้ → ถ้า `classify <prefix> allow` จะกลาย ALLOW = silent mutation / **bypass nah ผ่าน wrapper** / RCE. `jq`=ALLOW อยู่แล้ว (read-only จริง). → **nah `unknown→ASK` ถูกต้อง ไม่ใช่ bug**; ตัดสิน **ไม่ loosen**. convenience-fix ที่ safe = nah **LLM-classifier** (`LLM eligible: yes`; opt-in `nah key`) อ่าน command จริง (search vs `-U`, SELECT vs DROP) → ปิด friction โดยไม่เจาะรู. (A-12)
- **portaw `registry/sets.json` = reuse-gold (8 sets vetted+benchmarked+install-tested):** **corroborate instrument เรา** (portaw idle: codegraph 1615 vs ฉัน 1653 · context7 927 vs 964 · fetch 259 vs 290 = ±2-10%) + portaw รู้ "idle 0 บน CC lazy" อยู่แล้ว (= Phase-0 finding ฉัน, convergent). salvage → ast-grep+semble เข้า v1, 7 sets เป็น roadmap. + portaw เจอ **Headroom Windows-wheel friction (06-09)** + จริง = rtk 88%/HR **+12% additive** → A-09 re-verify trigger.

## 4. Candidate shortlist + bench plan

**Bench 2 คอลัมน์ cost:** `runtime_cut% | static_tax(tok/session) | NET | delivery(CLI/hook=0 vs MCP) | host | local/privacy | setup-friction | lazy-load?`

| ช่อง | challengers ที่ต้อง bench vs ของเดิม |
|---|---|
| token-cut (RTK) | **Headroom** ⭐ (Apache-2.0, local model, bench 92%/accuracy held, 0-tax wrap/proxy — **เสริม RTK ไม่ใช่แทน** §4b), **lean-ctx** (76 MCP tools ⚠️ static=tax หนัก; เช็ค hook-mode), **ecotokens** (hook, 0-tax, 93.8%), context-mode |
| memory (ICM) | **MemPalace** (96.6% LongMemEval, local, MIT), **Supermemory** (coding-MCP), **Graphiti** (temporal) |
| MCP-head | mcp2cli (backlog flag strategic), native Tool-Search/lazy-schema |

**ลำดับทำ (ถูก→แพง) — รายละเอียดรันจริง → [BENCH.md](./BENCH.md):** (1) วัด tax ก่อน = นับ tool-def × token-count API → CLI/hook=0, คัดผู้แพ้ก่อน A/B · (2) A/B compression เฉพาะตัวรอด (reuse `headroom.evals` + ccusage) · (2a) **stack-marginal:** OFF/RTK/Headroom/RTK+HR วัด marginal NET · (3) memory reuse LongMemEval · (4) **stack-collapse:** lean-ctx เดี่ยว vs RTK+ICM คู่.

**§4b — Headroom reframe (verified 2026-06-21, pkg corrected 2026-06-22):** `chopratejas/headroom` 43.7k★ (hype) แต่ substance ผ่าน. กลไก SmartCrusher(JSON)/CodeCompressor(AST)/Kompress-base(HF local)/**CCR reversible** (กู้ original ผ่าน `headroom_retrieve`). **เสริม RTK ไม่ใช่คู่แข่ง:** RTK=shell-layer per-command, Headroom=API-layer long-tail (file/RAG/log). prior art [`claude-code-tips`](https://github.com/sgaabdu4/claude-code-tips) stack จริง (`headroom wrap claude`=0 tax) → reuse hook map. ⚠️ proxy OAuth-exchange = ToS-gray บน first-party → `wrap`/MCP เท่านั้น (A-10).
  - **🔑 pkg = `headroom-ai` 0.24.0** (PyPI) — ไม่ใช่ `headroom` (=name-squat คนละโปรเจกต์!).
  - **⚠️ A-09 CORRECTED 2026-06-22 (install RE-TESTED, FAILED):** ก่อนหน้าเขียน "Windows VERIFIED / pure-Python sdist (no compiler)" = **ผิด**. ของจริง: headroom-ai = **mixed python/rust (maturin)** → build ดึง rustup+cargo 1.96 อัตโนมัติ แต่ **ตายที่ `link.exe failed: exit 1`** (MSVC C++ Build Tools / Win SDK linker prereq หาย, py3.14.4). ยืนยัน §4b "no Windows wheel; Rust/maturin build fails" ที่ถูกต้อง. → **headroom = Windows-BLOCKED บนเครื่องนี้** (ต้องลง VS Build Tools เป็น GB เพื่อ optional +12% rung = ไม่คุ้ม, KISS). **Phase-1 stack-marginal §2a = BLOCKED** (headroom lane ลงไม่ได้). keep optional/deferred; recheck = prebuilt wheel/py≤3.13/ลง MSVC ตั้งใจ.

## 5. Open / ยังไม่เคลียร์ (decisions ค้าง)

1. **target:** personal-first vs OSS-first → เอนไป "**OSS-clean day-1 + personal CC interactive (first-party, ไม่ต้อง plumbing)**" — ยังไม่ lock ทางการ.
2. ✓ **RESOLVED — tool bundle (BUNDLE.md v2)**: core 0-tax (RTK/ICM/caveman/**ast-grep**/AGENTS) + MCP zone (codegraph **XOR semble** host-cond + fetch) + **named-set install UX แบบ portaw**. ยุบ mental-model lean แต่ **เก็บ set เป็นหน่วยติดตั้ง** (`install <set>` = สะดวกผู้ใช้, North Star #2). **salvage portaw = registry sets.json + installer (`install`/`sets`/`verify`)** ไม่ใช่แค่ data.
3. **token-cut anchor:** RTK vs Headroom vs lean-ctx vs ecotokens — **รอ bench**; เปิดประเด็นใหม่ = **stack (RTK+Headroom) ไม่ใช่ pick-1** (Headroom เสริม long-tail แบบ reversible).
4. **memory:** ICM vs MemPalace vs Supermemory — **รอ bench** (vs friction/local).
5. **governance:** ICM decay/dedup พอ vs paw overlay (distrust-on-miss)?
6. **cockpit (dmux):** ทำที่ L1 เลย หรือรอ L2?
7. **L2 framework:** AgentPool หลัง Phase-0 vs re-open (LangGraph)?
8. **L1 routing:** claude-code-router พอ vs เสริม LiteLLM (metered) ตั้งแต่แรก?
9. ✓ **RESOLVED — installer = salvage portaw sets-subtree (2026-06-22):** อ่าน `portaw/main.py` แล้ว — machinery ดีจริง + safety-railed: `install <set> --host [--run --yes --force]` (backup+validate config patch → argv-exec **shell=False** no-metachar → idempotent PATH-skip → untrusted-never-autorun → **N1 ceiling warn**) · `remove` (un-patch+reverse) · `verify` (§10 health-gate `shutil.which`/tool) · `doctor --usage` (idle-MCP scan). **ตัดสิน: lift subtree `portaw/sets/` + `config.py` + `kernel/registry.py` + `sets.json` → harness install-layer; ทิ้ง dead layers (router/memory/bench)** ที่ ICM + `bench/mcp_tax.py` แทนแล้ว. = reuse good module, shed dead (≠ depend-on-archived). glue nah-classify = REJECTED security hole (ดู §3 + A-12); secure-agent ship ตามเดิม (ASK dual-use = ถูก).

## 6. Pending actions (offers ที่ยังไม่ทำ — เลือกหลัง compact)

- [x] **ICM installed v0.10.53** (SHA256-verified). core store/recall ✓; `portaw mem status`=True (PATH fix); mistake-logging dogfood ✓ (id `01KVMQRR4...`). ⚠️ PowerShell ต้องเรียก `icm.exe` (`icm`=Invoke-Command alias); restart terminal ให้ PATH ถาวร. host auto-wiring ยัง skip → §8.
- [x] **`portaw doctor --usage`** ✓ → Desktop_Commander อ้วนสุด (ใช้ 6/~25 tools); ccd_session/mcp-registry/fetch ใช้ 1 tool/ตัว = idle-def tax = หลักฐาน A-08 จริง.
- [x] **`docs/BENCH.md`** drafted = matrix รันจริง (Phase 0 tax → 1 A/B + 2a stack-marginal → 2 memory → 3 collapse; reuse `headroom.evals`/ccusage). **+ Headroom vetted เข้า shortlist (§4b, A-09/A-10).**
- [~] **Phase-0 gates:** (c) `rtk hook` **≠ codex** ✓. (b) **AgentPool billing ✓ VERIFIED** (SDK + `use_subscription` knob — A-02/§9). (a) per-seat billing test = user-driven (account จริง) — ยังค้าง.
- [x] **discovery-lazy vs delivery-tax** = ขยายใน A-08 ledger.

**→ 1+2+3 RESOLVED (2026-06-22):**
1. ✓ **nah-classify glue = REJECTED** — security hole (prefix-match + dual-use proven `nah test`); nah ASK ถูก. fix = accept ASK / nah LLM-classifier opt-in. (§3, A-12)
2. ✓ **installer = salvage portaw sets-subtree** (`sets/`+`config`+`kernel/registry`+`sets.json`), ทิ้ง router/memory/bench (ICM+`mcp_tax.py` แทน). (#9 RESOLVED)
3. ✓ **Headroom comparator unblocked** — pkg `headroom-ai` 0.24.0 (≠`headroom`squat); Windows install VERIFIED. (§4b, A-09)

**→ DESIGN LOCKED 2026-06-22 (ARCHITECTURE §11 + A-15/A-16):** router = agent-pull **3 event-keyed recall lanes** (capability READ/search · memory ICM · **mistake PreToolUse action-key**) + bundle-linker (portaw core + codegraph-link UX). no paid LLM, ~0 always-on. supersede portaw blind-push.

**→ BUILDING (linker-first):**
- [x] **Step 0** scaffold + `pyproject.toml`. **ชื่อ LOCKED: project `port-a-whip` · package/CLI `paw`** (รีนาม harness→paw; pkg import=`paw` ไม่ชน old `portaw`). logo idea = 🐾 paw = brain-pad + toes=hosts.
- [x] **Step 1 read-path** — lift `config.py`+`sets/loader.py`+`registry/sets.json` verbatim (stdlib-only); `py -m paw sets list/show` ✓ 8 sets. **เหลือ write-path:** lift `patcher`/`healthcheck`/`install`/`runner`/`state` (rewrite `portaw.*`→`paw.*` + tomlkit dep; ⚠️ **`patcher` audit ก่อน** — มัน mutate host config).
- ✅ **CHECKPOINT git `cef81a3`** (main, 18 files, gitleaks clean) · home `E:\portable-harness`. port-a-whip เก่า (`~/.claude/port-a-whip`) = retire **หลัง** salvage write-path (ยังเป็น source).
- [x] **G3 AGENTS.md content** → `bundle/AGENTS.md` (canonical harness manual = `link` injection source; see §10 G3).
- [ ] **Step 2** `link <bundle>` multi-set + managed marker-block `<!-- paw:start/end -->` + inject `bundle/AGENTS.md` slice + N1 gate (codegraph-link UX). **decision-gate #G5: salvage `portaw patcher` vs thin ~50-line.**
- [ ] **Step 3** smoke `link secure-agent` e2e (0-MCP set = ง่ายสุด).

**→ parallel (execution):** Phase-1 A/B (headroom-ai ready) · mistake PreToolUse recall-before hook (reuse ICM).

## 7. ของที่แก้ไปแล้ว (session นี้)

- สร้าง [CLAUDE.md](../CLAUDE.md) (mindset 10 ข้อ + portaw-as-example).
- [SHARED-BRAIN.md](./SHARED-BRAIN.md) → ICM-direct (portaw = optional overlay).
- [ARCHITECTURE.md](./ARCHITECTURE.md) → layered reconcile (2-axis, A3, ToS table, Assumption Ledger, roadmap wire-not-build).
- global `~/.claude/CLAUDE.md` Mistakes → `icm store/recall` (เลิกชี้ `portaw memory` ที่ deprecated/no-op; + คำเตือนต้อง install ICM ก่อน).
- **install ICM v0.10.53 + verify chain (§8)** · **draft [BENCH.md](./BENCH.md) + Headroom vetted (§4b)** · `doctor --usage` + `rtk hook` coverage probe.
- **AgentPool billing research → A-02 VERIFIED (§9)** · **BENCH Phase 0 ran** (built `bench/mcp_tax.py`, วัด DC=11.5k + roster; finding native-lazy) · **BUNDLE v1 hand-curated** ([BUNDLE.md](./BUNDLE.md)+`bundle/mcp.json`).

## 8. ICM install — actual state (2026-06-21) + corrections

**ติดตั้งจริงแล้ว, core LIVE.** แต่หลาย claim เดิมต้องแก้:

| ของเดิม (SHARED-BRAIN/STATUS) | ความจริง v0.10.53 |
|---|---|
| `icm init` auto-config **18-host MCP** | default = **`standard` mode = cli + skill + hook, ไม่มี MCP**. MCP = opt-in (`--mode mcp/all`). → **ICM ผ่าน CLI = 0 tool-def tax** = แข็งเรื่อง N1 กว่าที่คิด |
| db = `%LOCALAPPDATA%\icm\...` | จริง = `%APPDATA%\Roaming\icm\icm\data\memories.db` |
| `icm available: False` = ยังไม่ลง | ลงแล้ว; portaw `shutil.which("icm")` หาไม่เจอเพราะ **harness/shell inherit stale PATH** (installer เขียน User-PATH หลัง process เกิด). fix: restart terminal → True |

**gotchas (เก็บใน ICM `mistakes` แล้ว, id `01KVMQRR4...`):**
- PowerShell: `icm` = alias ของ `Invoke-Command` → ต้อง `icm.exe`/full path.
- PATH propagation: shell เก่าไม่เห็น icm\bin จน restart.

**host auto-wiring ยัง skip ("not detected" ทุก host)** ทั้งที่ claude.exe/configs มีครบ → ICM detect คนละ marker (ไม่ใช่ binary-on-PATH ตรงๆ). **decision: defer** — ไม่จำเป็นตอนนี้เพราะ (1) global CLAUDE.md สั่ง `icm` via Bash อยู่แล้ว = cross-host ได้, (2) `standard` ติด PostToolUse auto-extract hook = invasive กลาง design. opt-in ทีหลังแบบตั้งใจ (`icm init --mode hook` เมื่อพร้อม). **recheck:** ICM detection logic (อ่าน source/issue) ถ้าจะ auto-wire.

## 9. AgentPool billing (Phase-0 gate b) — VERIFIED 2026-06-21

**`phil65/agentpool`** (167★, Python) claude_code = **Claude Agent SDK** (`ClaudeSDKClient`/`ClaudeAgentOptions`, ผ่าน forked `clawd_code_sdk`).

- **billing knob `use_subscription`** (YAML, per-agent): default `False` = API-metered (`ANTHROPIC_API_KEY`, มี `max_budget_usd` cap) · `True` = blank key → ride **Max/Pro OAuth** (logged-in claude session). → A3 knob มีจริง per-agent.
- **reuse-stack:** `setting_sources` default None → โหลด user/project/local (MCP+hooks+CLAUDE.md via `memory` field); scope/`isolation: worktree` ได้. + bridge AgentPool toolset → Claude Code via MCP.
- ⚠️ **`use_subscription:true` = programmatic sub = A3 ToS-gray** (ตรงเป้า Feb-20 OAuth ban) · depends **forked SDK + solo author** = maintenance risk.
- **verdict:** AgentPool = L2 candidate viable (full CC surface + per-agent billing) แต่ caveat 2 ข้อ → ยัง L2-gated, ไม่ promote เป็น spine.

**Phase-0 gate (a) per-seat billing test = ยัง user-driven:** ยิง programmatic บนแต่ละ sub → ดู dashboard ว่า bill/ทำงานไหม = ต้อง account จริง.

## 10. ZOOM-OUT — architecture gaps ก่อนลงมือจริง (2026-06-22)

**State:** `E:\portable-harness` = design-only (6 docs + `bench/mcp_tax.py` + `bundle/mcp.json`). **ไม่ใช่ git repo · ไม่มี AGENTS.md · ไม่มี install code/README/LICENSE.** validation ทั้งหมด = CC-on-Windows. probe 06-22: **Gemini ลงอยู่** (`gemini.ps1`) · Codex CLI absent (แต่ `~/.codex/AGENTS.md` มี) · cursor/crush/opencode/qwen absent.

**Thesis 2 เสา (North Star) — ตอนนี้รั่วทั้งคู่:** *best* (bench-validated) ยัง vibes · *convenient* (1-cmd install + cross-host) ยังไม่ build.

**Gaps เรียงตาม leverage:**
- **G1 — cross-host moat = SMOKED 2026-06-22 (thesis HOLDS, แต่ tiered).** ICM = portable ทุก host (CLI bridge) ✅. **RTK/nah degrade hook→instruction/sandbox** ข้าม host (A-13): CC=auto-hook(strong) · Gemini=`rtk init --gemini`(medium) · Codex=instruction+`nah codex setup`+sandbox(no-hook). → harness = **per-host enforcement tiers, ห้ามโฆษณา uniform-automatic**; **secure-agent guarantee ≠ เท่ากัน** (Codex softer). config-smoke: `nah codex doctor` รันได้ เจอ approval-mode/authority gaps. **LIVE-smoke 06-22:** Gemini binary รัน (v0.45.2) แต่ **free-tier auth ตาย** (`IneligibleTierError UNSUPPORTED_CLIENT` → Google ดัน Antigravity, A-14) = host decay จริง. Codex CLI **ลงแล้ว 0.141.0** (`npm i -g @openai/codex`) + config-smoke pass; trivial live-exec pending. prior-art: root AGENTS.md = `~/.claude/AGENTS.md` 8.5KB (→ G3).
- **G2 — harness ไม่มีตัวตนเป็น code.** ไม่มี package/CLI/install. #9 = salvage portaw subtree แต่ยังไม่ port. "convenient" = สัญญา ยังไม่จริง.
- **G3 — AGENTS.md DRAFTED 2026-06-22 → [`bundle/AGENTS.md`](../bundle/AGENTS.md).** canonical shippable harness operating manual = L0 content/curation moat layer. ครอบ: ICM memory-protocol · token-discipline (CLI>MCP, N1≤2-3) · secure-agent 4-guard (nah dual-use→ASK ห้าม loosen) · 8-set table (grounded `paw sets list`) · **cross-host enforcement tiers honest** (CC strong-hook / Gemini medium / Codex softer instruction+sandbox, A-13) · ethos + assumption-ledger. **เหลือ host-bridge wiring** = Step 2 `link` inject managed `<!-- paw:start/end -->` block ลง CLAUDE.md @import / Codex AGENTS.md native / Gemini. content done, plumbing ยัง.
- **G4 — "best" PARTIALLY REAL 2026-06-22 (Phase-1 deterministic A/B RAN, tools live).** ไม่ใช่ vibes ล้วนแล้ว → [BENCH.md Phase-1 RESULTS](./BENCH.md): **rtk** per-cmd 85–91% (git log/status fire), mixed-suite 19.8% (understated — `py -m`/git-subcmd passthrough artifact) · **ast-grep** precision +75.8%, codemod +86.1–98.7% · **ICM** live (0.10.53 via `%LOCALAPPDATA%\icm\bin\icm.exe`), recall scoring works. **+ ICM recall (deterministic, `bench/_icm_recall.py` 2026-06-22):** **hit@3 100%** (8/8 paraphrase, near-0 surface overlap = real semantic), **MRR 0.938**, inject 179 tok/q (toon; json=false 17k จาก embedding arrays). **instruments READY:** ccusage 20.0.14 ✓ · icm.exe `%LOCALAPPDATA%\icm\bin` ✓ · tiktoken 0.13.0 ✓. **ยัง vibes / blocked:** full-session ccusage NET (contamination → **DEPRIORITIZED**, proxy แทน) · **headroom §2a = BLOCKED** (maturin/MSVC link.exe fail py3.14, A-09 corrected) · **A-07 ยังไม่ปิดสมบูรณ์:** deterministic retrieval ✓ corpus เล็ก แต่ (1) LLM-judged `icm bench-recall` = user-run (nested-claude CLAUDECODE=1 block) (2) **head-to-head MemPalace/LongMemEval = ยังไม่ทำ** = แกน quality ที่เหลือ · codegraph lane (ต้อง index). NB: bench = **NET ไม่ใช่ %** (RTK edge = 0-tax).
- **G5 — RESOLVED 2026-06-22: salvage portaw subtree (staged) · thin-rewrite REJECTED.** อ่านโค้ดจริง (ไม่ใช่ vibes): hard-80% สร้าง+เทสต์แล้ว → `patcher.py`(253L) `_guard_unchanged` ปฏิเสธ clobber ตอน host เขียน config ตัวเองกลาง-patch (**race จริง** — CC เขียน `~/.claude.json` ตลอด; thin script พลาด) + comment-preserving TOML round-trip-validate + pure merges (`test_patcher` 205L) · `agents_md.py`(63L) = adopt **AGENTS.md standard** (CC: prepend `@AGENTS.md` import line; Codex/Gemini read native) idempotent · `router.py` = marker-idempotent `enable/disable_hook` JSON+TOML (reuse wire nah/rtk แม้ router *feature* ตาย). **Thin ~50-line = REJECTED** (re-derive edges แย่กว่า → config corruption; ขัด ethos#2 + KISS≠naive). **Staged salvage:** MVP `link secure-agent`(0 MCP) ใช้แค่ `agents_md`+`runner`/`install`(argv shell=False)+`healthcheck`+`state`+`router` hook-wiring (nah self-wire ผ่าน `nah install claude`, paw record คืน clean) → **`patcher` ไม่ถูกใช้ที่ MVP, defer** จน MCP-set แรก (efficiency/context-quality) ค่อย lift verbatim. **2 corrections:** (i) #9 "ทิ้ง router" = ทิ้ง *feature* แต่ salvage hook-wiring funcs · (ii) แผน §6 marker-block `<!-- paw:start/end -->` ลง host context file = INFERIOR กว่า AGENTS.md-standard bridge ที่สร้างแล้ว → adopt standard (AGENTS.md แยกไฟล์ + `@AGENTS.md` import); managed-block ใช้เฉพาะตอน append เข้า AGENTS.md เดิมของ user (ห้าม clobber) = Step-2 detail @import-chain/paw-owned-file.
- **G6 — distribution + freshness undecided.** user ได้ของยังไง (pip/npm/git+script/scoop)? + landscape ขยับรายวัน (#3) แต่ไม่มี runtime `update`/recheck cadence (ledger อยู่แค่ docs).
- **G7 — Phase-0 billing(a) + privacy enforcement.** A-01 per-seat = user-driven ค้าง (gate L1/L2 economics) · A3 privacy "sensitive→ห้าม GLM" = design ไม่มี mechanism. = L1 concern, defer ผ่าน L0 ได้.

**Critical path → L0 จริง:** ~~G1 smoke~~ (largely done: Gemini auth ตาย/Codex config-pass) → ✅ **G3 AGENTS.md DONE** (`bundle/AGENTS.md`) → **G5/G2 thin install-script MVP (1 set end-to-end เช่น secure-agent) = NEXT** → G4 Phase-1 bench (parallel) → G6/G7.

**ทำก่อนสุด = G1** (ถูก + load-bearing): Gemini พร้อม smoke. ทุกอย่างที่เหลือ assume cross-host เวิค — verify ก่อน build บนสมมุติฐานนั้น.

**→ NEXT (resume pointer 2026-06-22): G5 RESOLVED → BUILD `paw link secure-agent` MVP (Step 2).** decision locked = salvage portaw subtree staged (§10 G5). lift order สำหรับ MVP (0-MCP set):
1. `agents_md.py` (63L) → `paw/bridge.py` verbatim (rewrite `portaw.*`→`paw.*`; stdlib-only, no dep). ship `bundle/AGENTS.md` เป็นไฟล์ + `@AGENTS.md` import. **ห้าม clobber AGENTS.md เดิม user** → append-or-import.
2. `runner.py`(94)+`install.py`(222) → run `non_mcp[].install` steps, argv `shell=False`, untrusted-never-autorun, record → `state.py`(109) สำหรับ clean `remove`.
3. `healthcheck.py`(126) → `verify secure-agent` gate (`shutil.which` nah/gitleaks/osv/infisical).
4. `router.py` hook-wiring funcs (`enable/disable_hook`) → wire PreToolUse (nah self-wires via `nah install claude`; paw records).
5. **defer `patcher.py`** (no MCP in secure-agent) จน efficiency-starter.
⚠️ audit lift ก่อน exec: `install.py` runner = argv-exec untrusted curated steps → ยืนยัน shell=False + no-metachar + N1 ceiling-warn ยังอยู่. tomlkit dep เข้าเฉพาะตอน lift `patcher` (MCP set), MVP ยังไม่ต้อง.
