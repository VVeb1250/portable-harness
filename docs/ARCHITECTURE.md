# Portable Harness — Architecture & Design

> สถานะ: **runtime spine started** · **UPDATED 2026-06-25**. Router v0 and ICM blackboard v1 are implemented; Team Kernel and installer write path remain.
> mindset: [../CLAUDE.md](../CLAUDE.md) · L0 brain detail: [./SHARED-BRAIN.md](./SHARED-BRAIN.md)

---

## 1. เป้าหมาย (Vision)

**harness แบบพกพา** ที่:

1. **รวม MCP + non-MCP tools** (curated bundle)
2. **ลด token ทุก agent** — **RTK ที่ tool layer** (ไม่ใช่ model-proxy)
3. **เพิ่มคุณภาพ context** (skills / KB / curated tools)
4. **memory ร่วมข้าม agent** — **ICM** (+ paw governance overlay, optional)
5. **agent team** ในอนาคต

**หลักการ:**
- **reuse, don't rebuild** — build แค่ glue บางๆ; orchestration/proxy/memory-store = commodity → adopt.
- **regime-agnostic** — ไม่ผูก billing/vendor เดียว (Anthropic พลิก billing รายสัปดาห์).
- **replaceable** — ทุก layer = adapter บางๆ, สลับได้ (landscape เปลี่ยนรายวัน).
- Moat จริง = **curation + token-cut + shared-memory ข้าม heterogeneous agents** (= distro, ไม่ใช่ tech moat ที่ป้องกันได้).

### Layered model (spine)

| Layer | คือ | เมื่อไหร่ | สถานะของ |
|---|---|---|---|
| **L0 Brain** | ICM + explicit shared blackboard + bundle + AGENTS.md | **now** | blackboard v1 live; host wiring/linker incomplete |
| **L1 Routing/Cockpit** | explainable task/seat policy + optional cockpit | **now** | deterministic router v0 live; execution adapter next |
| **L2 Team** | Planner → Implementer → Reviewer → evaluator | **next** | economics gate passed; build small Team Kernel first |

L1/L2 **inherit L0**. ลงทุน L0 ครั้งเดียว ไม่เสียเปล่า.

---

## 2. การตัดสินใจ — แยก 2 orchestration axes (เลิก conflate)

เดิมเขียนว่า "AgentPool = THE shell". **แก้:** orchestration มี **2 แกนคนละเรื่อง** — เอกสารเดิมรวมมันเป็นก้อนเดียว ซึ่งทำให้หลงทาง:

- **(i) task/seat routing** (complexity/risk/privacy/budget) → paw deterministic router v0. External gateways remain optional adapters. อยู่ **L1**.
- **(ii) agent team** (coordinator + delegation) → build the proven team3 contract first; AgentPool/LangGraph remain candidates if real gaps appear. อยู่ **L2**.

**AgentPool ย้ายจาก spine → L2 candidate** (ไม่ใช่ฐาน). adopt ได้ก็ต่อเมื่อ **Phase-0 gate** ผ่าน:
1. `claude_code` agent reuse ECC stack จริง (hooks/skills/RTK/paw fire) ไหม?
2. bill ทางไหน (subscription vs API key vs credit)?

ถ้า gate ไม่ผ่าน → AgentPool = thin wrapper, ใช้ของอื่น/ทำเองได้.

> framework table (AgentPool/Agent SDK/LangGraph/CrewAI/AutoGen) = เก็บไว้อ้างอิงตอนเลือก **L2** เท่านั้น — ไม่ใช่ตัวตัดสิน L0/L1.

---

## 3. สถาปัตยกรรม (layered)

```
┌───────────────────────────────────────────────────────────┐
│  HOSTS (first-party CLIs)                                   │
│  Claude Code · Codex · Gemini   (GLM via CC base-url)       │
└───────────────┬───────────────────────────────────────────┘
                │ each first-party on its own sub/auth
┌───────────────▼───────────────────────────────────────────┐
│  L0  SHARED BRAIN   (→ SHARED-BRAIN.md)                     │  ← moat, ToS-immune
│  ICM (mem, local SQLite) · paw blackboard protocol · RTK   │
│  curated mcp.json · AGENTS.md            (+ paw overlay opt)│
└───────────────┬───────────────────────────────────────────┘
                │
┌───────────────▼───────────────────────────────────────────┐
│  L1  ROUTING / COCKPIT                                      │
│  paw route: complexity/risk/privacy/budget/fallback        │
│  metered gateway: LiteLLM (เฉพาะ API/credit)               │
│  cockpit (optional): dmux (one view, many agents)          │
└───────────────┬───────────────────────────────────────────┘
                │
┌───────────────▼───────────────────────────────────────────┐
│  L2  TEAM (next)                                            │
│  Router → Planner → Implementer → Reviewer → evaluator     │
└───────────────────────────────────────────────────────────┘
```

---

## 4. Component Designs

### 4.1 Token-cut = **tool layer** (ไม่ใช่ model-proxy)

- **ทำไมไม่ใช่ model-proxy:** RTK ลด **tool output** ที่ tool boundary — model-proxy เห็น message ประกอบแล้ว ต้อง mutate prompt = lossy + คนละ algorithm. และ proxy plumbing = commodity (**LiteLLM** มีแล้ว).
- **ทำ:** RTK ที่ tool layer — `rtk hook` (Gemini/Copilot ✓), `pipe`, `rewrite`. bundle ที่ share อยู่แล้ว → cut universal ฟรี.
- **LiteLLM:** ใช้เฉพาะ **metered routing** (budget/cache/cost) — ไม่ใช่ subscription arbitrage (Feb-20 ToS).
- detail → [SHARED-BRAIN.md §5](./SHARED-BRAIN.md).

### 4.2 Memory = **ICM** (+ paw governance, optional)

- **ICM** (rtk-ai): single binary, MCP-native, SQLite local-only, `icm init` wire 18 hosts เอง. = store ร่วมข้าม agent.
- **ไม่ใช่** "paw ⇄ AgentPool storage adapter" (เดิม) — ผูก AgentPool เกินจำเป็น + reinvent (mem0/Letta/Graphiti มีแนวแล้ว).
- paw = **governance overlay optional** (distrust-on-miss) เหนือ ICM.
- ship: schema/empty เท่านั้น. detail → [SHARED-BRAIN.md §1-2](./SHARED-BRAIN.md).

### 4.3 Tool bundle (curated)

- MCP คัด: codegraph · context7 · fetch · desktop-commander (+ ตามใช้). non-MCP: RTK-wrapped CLI.
- หลัก: ลด overlap, token-per-call ต่ำ, signal สูง, **CLI > MCP บน load-all** (0 tool-def), ≤2-3 active MCP/set.
- รูปแบบ: `mcp.json` (hand-curated) หรือ `portaw sets` (opportunistic).

### 4.4 Model/quota routing (A3) — **L1, ดู §5**

---

## 5. Per-seat ToS + cost stance (A3)

**ของจริง:** subscription harvestable ต่อ seat ต่างกัน —

| Seat | programmatic บน sub? | lane สะอาด |
|---|---|---|
| Claude Max | gray (`claude -p`/SDK = June-15 target, paused) | interactive only |
| Codex (ChatGPT) | **ไม่ได้** (headless → API key, metered) | interactive only |
| GLM (z.ai) | **ได้ (blessed)** — Anthropic-compatible endpoint | programmatic ✅ |

**A3 — cheap-blessed-sub-first:** programmatic default → **GLM sub** (workhorse, ถูก); sensitive code → **metered** Claude; interactive → all subs **by hand**. RTK ยืด GLM quota. metered = spillover.
**Privacy rule:** sensitive/proprietary code → **ห้าม route ไป GLM** (z.ai) → metered Claude แทน. ทำเป็น per-repo rule.

---

## 6. Assumption Ledger (รับมือ assumption-decay)

ทุก assumption ที่ load-bearing → มี recheck trigger. (บทเรียน: premise พลิก 2 ครั้งใน 5 วัน)

```
A-01 Agents ride flat Max subscription
  status: LIVE (paused reprieve, post 2026-06-16) · breaks-if: Anthropic relands split (12-175x)
  recheck: ทุก Anthropic billing announcement · isolation: regime-agnostic + A3
A-02 AgentPool (phil65/agentpool) claude_code = Claude Agent SDK (ClaudeSDKClient, ผ่าน forked clawd_code_sdk)
  status: VERIFIED — reuse-stack: setting_sources=None default โหลด user/project/local (MCP+hooks+CLAUDE.md), scope/worktree-isolate ได้
  billing: knob `use_subscription` — default False=API-metered (ANTHROPIC_API_KEY, มี max_budget_usd cap); True=blank key→ride Max/Pro OAuth (logged-in claude session)
  ⚠️ use_subscription:true = programmatic multi-agent บน sub = A3 ToS-gray (Feb-20 ban target) · depends forked SDK + solo author = maintenance risk
A-03 Token-cut belongs at tool layer (not model-proxy)         status: HELD
A-04 ICM = memory foundation (standalone, multi-host)          status: LIVE (installed v0.10.53, store/recall verified, portaw bridge True หลัง PATH/restart)
A-05 portaw (own project) usable as base
  status: NO — archived/"ทรงไม่เวิค" → ICM-direct, portaw = optional overlay
A-06 RTK = best token-cut anchor
  status: UNVERIFIED — bench vs lean-ctx / ecotokens (vendor-claims only, ไม่มี neutral head-to-head)
  note: RTK edge จริง = CLI/hook = 0 tool-def tax (N1-safe), ไม่ใช่ compression % ที่พิสูจน์
A-07 ICM = best memory
  status: UNVERIFIED — ไม่อยู่ใน LongMemEval (MemPalace 96.6% / Supermemory coding / Graphiti temporal)
  note: ICM ชนะเฉพาะ single-binary + local + 18-host friction ต่ำ
A-08 MCP-head tax = ~550-1400 tok/tool/session (จ่ายทุก session, ซ้ำตอน compaction)
  status: HELD (Anthropic token-count API) · rule: prefer CLI/hook (0 tax); MCP ต้อง lazy-schema/Tool-Search/mcp2cli
  note: DISCOVERY-lazy (แนะ tool ช้า — router ทำได้/live) ≠ DELIVERY-tax (def โหลด→จ่าย tok ทุก turn). router แก้แค่ discovery; ลบ delivery-tax ต้อง lazy-schema/Tool-Search/mcp2cli
A-09 Headroom = token-cut เสริม RTK (ไม่ใช่คู่แข่ง)
  status: VETTED + Windows-installable VERIFIED (2026-06-22) — Apache-2.0, 43.7k★, CCR reversible-retrieval, published bench (code-search 92%, GSM8K Δ0)
  pkg: **`headroom-ai` 0.24.0** (PyPI) — ⚠️ ไม่ใช่ `headroom` (นั่น = name-squat "CLI AI assistant" คนละโปรเจกต์ SUNKENDREAMS, อย่าลงผิด). install: `pip install "headroom-ai[code,mcp]"` · npm `headroom-ai` · docker `ghcr.io/chopratejas/headroom`
  reuse: sgaabdu4/claude-code-tips stack RTK+Headroom จริง (`headroom wrap claude` = 0 tax; RTK=shell-layer, HR=API-layer long-tail)
  recheck: bench marginal NET (RTK vs HR vs RTK+HR) — BENCH §2a · **Phase-1 execution ยังไม่รัน** (comparator พร้อม)
  ✓ Windows: portaw 06-09 "no wheel (Rust/maturin)" = **DISPROVEN สำหรับ headroom-ai** — pip dry-run: deps ทุกตัว = win_amd64/none-any wheels (aiohttp/yarl/multidict/ast-grep-cli/tree-sitter-language-pack); เหลือ headroom-ai เอง = pure-Python sdist (build ไม่ต้อง compiler). heavy HF Kompress-base = gated `[ml]` extra (opt-in). NB: base ดึง **litellm + ast-grep-cli** (overlap core bundle)
A-10 Headroom proxy = ToS-gray บน first-party OAuth
  status: HOLD — proxy OAuth-exchange แทรก first-party (Claude/Copilot) = programmatic interception (A3 gray)
  rule: first-party → `wrap`/MCP เท่านั้น; proxy เก็บกับ GLM (own base_url). recheck: `headroom wrap claude` แทรก API call ยังไง (HTTPS_PROXY local MITM?) → กระทบ A3
A-11 ICM integration default = standard (cli+skill+hook, NO MCP) = 0 tool-def tax
  status: HELD (v0.10.53 init ยืนยัน) — MCP opt-in เท่านั้น (`--mode mcp/all`). → ICM N1-safe by default
  note: icm init host auto-detect ยัง miss (claude/codex/gemini "not detected") → wiring deferred; ใช้ CLAUDE.md+CLI bridge แทน
A-12 nah-classify glue (loosen bundle tools) = REJECTED security-hole
  status: RESOLVED don't-do (2026-06-22) — `nah classify` = command-PREFIX match เท่านั้น; bundle tools dual-use (พิสูจน์ `nah test`): `ast-grep -U`=rewrite · `rtk`=universal-wrapper (`rtk rm -rf` / `rtk sh -c 'curl|bash'`) · `duckdb`=DROP/ATTACH/INSTALL → blanket `classify <prefix> allow` = silent-mutation / **nah-bypass** / RCE. nah `unknown→ASK` ถูกต้อง ไม่ใช่ bug
  fix แทน: (a) accept ASK (dual-use, safe, friction ต่ำ — ASK→proceed ไม่ block) · (b) nah LLM-classifier opt-in (`nah key`; `LLM eligible: yes`) = content-aware (search vs -U, SELECT vs DROP) ปิด friction โดยไม่เจาะรู. jq=ALLOW อยู่แล้ว (read-only จริง)
  rule: secure-agent ห้าม ship prefix-allow สำหรับ wrapper / dual-use binary
A-13 Harness guarantees = HOST-TIERED (hooks ≠ universal) — smoke 2026-06-22
  finding: L0 "automatic" guarantee = hook-powered = Claude-Code-strong; degrade ข้าม host:
    - ICM (memory): CLI bridge (icm.exe via AGENTS.md instr) → PORTABLE ทุก host ✅
    - RTK (token-cut): CC=`rtk hook` auto · Gemini=`rtk init --gemini` ✓ · Codex=manual AGENTS.md instr (rtk init ไม่มี --codex) ◐ auto→instruction
    - nah (security): CC=PreToolUse hard-BLOCK auto · Codex=`nah codex setup` (config approval-mode + ~/.codex/rules/nah-authority.rules + sandbox, ไม่ใช่ hook) ◐ block→sandbox
  → enforcement TIERS: A=Claude(hook: auto+guaranteed) · B=Gemini(init+some-hook) · C=Codex(instruction+sandbox, no-hook)
  impact: harness **ห้ามโฆษณา "uniform automatic" cross-host**. shared brain (ICM+AGENTS.md) = portable จริง; automatic token-cut + hard-security = CC-only strong. **secure-agent guarantee ≠ เท่ากันทุก host** (Codex = softer: sandbox+instruction)
  evidence: codex binary absent บนเครื่องนี้ แต่ ~/.codex configured (ECC/paw, config.toml.paw-bak-0610); `nah codex doctor` รันได้ + เจอ 6 MCP approval-mode `missing` + nah-authority.rules missing. root AGENTS.md = `~/.claude/AGENTS.md` (8.5KB, ECC) = prior-art G3
  recheck: live-run codex (`npm i -g @openai/codex`) ยืนยัน AGENTS.md load + rtk/icm CLI จริง · Gemini live-smoke ยังไม่รัน
A-14 Gemini CLI (free individual tier) = DEPRECATED by Google — live-smoke 2026-06-22
  finding: `gemini -p` live → `IneligibleTierError: UNSUPPORTED_CLIENT` "Gemini Code Assist for individuals no longer supported; migrate to Antigravity suite (antigravity.google)". binary รัน (v0.45.2, oauth-personal) แต่ free-tier LLM call ตาย (~/.gemini/antigravity dir = migration hint)
  impact: Gemini CLI = host เสี่ยง deprecate → tier-B (A-13) สั่นคลอน; cross-host target ต้อง re-eval (Antigravity = ตัวแทน? / gemini ผ่าน GEMINI_API_KEY metered?)
  recheck: Antigravity CLI = host ใหม่ไหม (context-file/hooks/AGENTS.md support?) · gemini via API key (metered) ยัง smoke ได้ไหม
  lesson: CLAUDE.md #3 จริง — host ตายได้ใน weeks; harness host-adapter ต้อง replaceable + อย่า hard-depend host เดียว
A-15 Router = agent-PULL event-keyed (supersede portaw blind-push) — LOCKED 2026-06-22
  status: LOCKED — capability=read/search index (pull) · memory=ICM search (pull/capped) · mistake=PreToolUse action-key. NO paid LLM; ~0 always-on (ride native Tool Search / progressive skill-load)
  evidence: portaw push mis-fired LIVE (all-Thai prompt → TF-IDF=0 → embed tier-2 spurious → design-quality on a router-design prompt); pull = agent forms the query → precise. catalog ใหญ่ = search problem (เหมือน memory)
  recheck: native Tool Search coverage/host · catalog-size threshold (static menu → searchable index)
A-16 Mistake recall = ACTION-keyed at PreToolUse (not prompt-topic) — LOCKED 2026-06-22
  status: LOCKED — agent ไม่ pull lesson ที่ลืมว่ามี + topic-push mis-fires → key ด้วย ACTION, fire ที่ tool boundary (`icm recall <command>` → inject lesson ตรงนั้น). proactive/precise/bounded/local/0-always-on
  build: thin PreToolUse hook (ICM วันนี้ = PostToolUse learn-after; เพิ่ม PreToolUse recall-before). reuse ICM + mistake-learning skill. = nah shape (action→policy) แต่เป็น lesson
  tier: hook = Claude/Gemini; Codex no-hook → instruction+sandbox (A-13)
```

> session state + ตกค้าง + bench plan ล่าสุด → [STATUS.md](./STATUS.md) (อ่านก่อนถ้าเพิ่ง compact).

---

## 7. Roadmap (reordered by impact/risk)

| Phase | งาน | Output |
|---|---|---|
| **0 Validate** | SymPy N=8 frozen benchmark | **DONE:** heterogeneous team economics gate passed |
| **1 L0 brain** | ICM blackboard protocol + host wiring | protocol live; linker/cross-OS acceptance next |
| **2 L1 routing** | deterministic router policy + evidence feedback | v0 live; runtime executor next |
| **3 L2 team** | small Team Kernel using existing Codex/DeepSeek adapters | **current next** |
| **4 OSS** | bundle + profiles + glue + sanitizer (ไม่ ship subscription-arbitrage) | public repo |

> L0 net-new code ≈ 0 — ของอยู่ในตระกูล rtk-ai/paw แล้ว. ต้นทุนหลัก = curation + wiring + Phase-0 vet.

---

## 8. Risks & Mitigations

| Risk | Mitigation |
|---|---|
| Anthropic billing whiplash | regime-agnostic + A3; ledger A-01 |
| portaw (own) archived | ICM-direct; portaw optional overlay (A-05) |
| AgentPool solo/166⭐/churn | L2-gated + optional, ไม่ใช่ spine; fork+pin ถ้าใช้ |
| subscription arbitrage = ToS gray | first-party interactive only; ห้าม ship; A3 |
| GLM = code ออกนอกเครื่อง | per-repo privacy rule (§5); ICM memory local-only |
| assumption decay | Assumption Ledger (§6) |

---

## 9. Open-Source Split

- **Your layer** (curated bundle, profiles, RTK glue, wiring, skills) → IP, MIT.
- **ICM / RTK / claude-code-router / LiteLLM** → external deps (คง license, pin).
- **AgentPool** (ถ้าใช้ L2) → vendored fork, MIT attribution.
- **paw / ICM contents** → ห้าม ship. schema/empty เท่านั้น.
- **ห้าม ship subscription-arbitrage** (ToS). ใช้ `opensource-forker` strip secrets ก่อน public.

---

## 10. Next Decisions (ค้างไว้)

1. tool bundle รุ่นแรก: hand-curated `mcp.json` หรือ revive `portaw sets`? (เริ่ม hand-curated = พึ่งตัวเองน้อยสุด)
2. L1 routing: claude-code-router พอ หรือเสริม LiteLLM ตั้งแต่แรก?
3. cockpit (dmux): ทำที่ L1 เลย หรือรอ L2?
4. L2 team: AgentPool หลัง Phase-0 หรือ re-open framework (LangGraph) ตอนนั้น?

---

## 11. LOCKED 2026-06-22 — L0 brain = 3 recall lanes + linker (agent-pull, no LLM)

แทน portaw "ONE router push every prompt". หลัก: **event-keyed recall — match trigger ให้ตรง recall-type**. capability เล็ก/คงที่ = READ · memory ใหญ่/โต = SEARCH · mistake = ACTION-keyed. **ไม่มี paid LLM, ~0 always-on** (ride native Tool Search / progressive skill-load).

### 11.1 — 3 recall lanes

| lane | trigger event | กลไก | always-on tax |
|---|---|---|---|
| **capability** (skill/tool/set) | agent เจอ need | catalog เล็ก=static menu · ใหญ่=**searchable index / native Tool Search** (PULL — agent ตั้ง query) | 0 — โหลดเฉพาะ match |
| **knowledge memory** | task / file context | ICM local search (`icm recall`) — pull หรือ precise capped push | 0 — inject capped |
| **mistakes / lessons** | **about to run action** | **PreToolUse lookup keyed to command/tool** → `icm recall <cmd>` inject lesson | 0 — เฉพาะ lesson ที่ fire |

- **capability:** PULL ไม่ push → ไม่ mis-fire (portaw push-guess บอด: design-quality mis-fire 06-22 = หลักฐาน, A-15). scale ใหญ่ = search problem (เหมือน memory) → ride native Tool Search; local fallback ICM/MiniLM (no API).
- **memory:** ICM (A-04) local SQLite search, ไม่ใช่ TF-IDF router. portaw ย้าย memory→ICM ไปแล้ว (code: "memory recall is ICM's job") → เราทำต่อ.
- **mistakes (pull พลาดเคสนี้ → A-16):** agent ไม่ขอ lesson ที่ลืมว่ามี + topic-push mis-fire → key ด้วย ACTION fire ที่ tool boundary. = nah shape (action→policy) แต่เป็น lesson. build = thin PreToolUse hook → `icm recall <command>`. ICM วันนี้=PostToolUse learn-after; เพิ่ม PreToolUse recall-before.

### 11.2 — delivery = bundle-linker

codegraph-link UX generalized **1-tool → N-tool bundle**, บน portaw installer core:
- **core** (salvage portaw `sets/`+`config`+`kernel/registry`, #9): verify-gate · backup+validate patch · **argv-exec shell=false** · idempotent PATH-skip · **N1 ceiling-warn** · untrusted-never-autorun.
- **UX** (codegraph-link): link/unlink duality (incl `ยกเลิก/ลบ`) · **managed marker-block** `<!-- bundle:start/end -->` ใน context file · drift-check · auto-build · 1-line confirm.
- **bundle unit** = named presets (`coding`/`research`/`secure`) **+ composable** (`link secure-agent data-query`).
- `/bundle-link` skill wrapper = Claude; **CLI core = ทุก host**.

### 11.3 — host tiers (A-13) ติดทุก lane

hook lanes (mistake PreToolUse, optional push) = Claude/Gemini strong; **Codex no-hook → instruction + sandbox**. capability/memory pull (CLI+instruction) = portable ทุก host.

### 11.4 — durable value (rent the rest)

router/search = commodity (platform absorbing: Tool Search/skills/memory-tool). **VALUE = (a) curation · (b) action-keyed mistake layer · (c) cross-host.** build 3 อย่างนี้; เช่า mechanism ที่เหลือ.
