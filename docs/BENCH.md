# BENCH — runnable token-cut + memory benchmark

> สถานะ: **mixed plan + measured evidence** · updated 2026-06-25 · เจ้าของ: supimol.web@gmail.com
> จุดประสงค์: **ฆ่า vibes** — วัด NET ก่อน lock anchor. mindset #5 (anti-vibes/empirical).
> คู่กับ: [STATUS.md](./STATUS.md) §C/§D · [ARCHITECTURE.md](./ARCHITECTURE.md) §6 ledger.

---

## Frozen agent-team evidence

The SymPy N=8 `swe_probe` cohort is frozen. Canonical truth lives in:

- `bench/swe_probe/FROZEN_N8_2026-06-25.json`
- `bench/swe_probe/_report.txt`
- `bench/swe_probe/results/*.json`
- `bench/swe_probe/preds/*`

Verify hashes and regenerate the report without paid model calls:

```powershell
python bench/swe_probe/verify_freeze.py
```

Result: `team3 5/8 > codex-solo 4/8 > claude-solo 2/6 ≈ deepseek-solo 2/8`.
Do not append future runs to this cohort; create a new dated manifest.

### Phase B — premium-quota projection (2026-06-26, no new runs)

> Phase A asked *does quality hold + quota shift?* — yes. Phase B converts the
> **already-frozen** per-arm token records (`results/sympy__sympy-*.json`) into the
> real seat model to answer the existential question directly: **how much scarce
> premium-Claude (Opus) quota does routing to the team actually free?** This is
> arithmetic over in-hand data — it adds no runs and does not touch the frozen cohort.

**Seat model.** Each arm taxes a *different* budget, and only one is the scarce
Max-plan seat:

| arm | resolved | seat it taxes | premium-Opus tokens | per **resolved** |
|---|---|---|---|---|
| claude-solo | 2/6 | **Claude Max (Opus)** — scarce | 91,286 in / 1,123 out | **45,643 in/resolved** |
| codex-solo | 4/8 | ChatGPT-sub (Codex) | 0 Opus | 0 |
| deepseek-solo | 2/8 | DeepSeek meter ($) | 0 Opus | 0 |
| **team3** | **5/8** | Codex-sub (plan/review) + DeepSeek meter | **0 Opus** | **0** |

**The projection.** Patch-generation done *solo on Claude* costs ≈15.2k Opus-in per
instance and, at the 33% single-shot resolve rate, ≈**45.6k Opus-in per resolved
task** (a tiktoken **floor** — hidden thinking tokens are not counted, so the true
cost is higher). Routed to `team3`, the same work resolves at 62.5% for **zero**
Opus: the bulk implementation rides DeepSeek's meter (cents) and the plan/review
rides the *separate* Codex-sub quota. So for a fixed Max budget `Q` of Opus-in:

| Q (Opus-in / window) | solo resolves | team3 resolves |
|---|---|---|
| 200,000 | ~4.4 tasks | unbounded by Claude quota — **Q fully freed** |
| 1,000,000 | ~21.9 tasks | unbounded by Claude quota — **Q fully freed** |

**Existential answer.** Direction is settled and robust: routing SWE patch-gen to
the team shifts **~100% of the premium-Claude quota it would otherwise burn off the
scarce seat**, while *raising* resolution (5/8 vs 2/6). Every Opus token not spent on
patch-gen is returned to the work only the premium seat can do. The deferred agentic
`claude-solo` arm would only *widen* this gap (single-shot already burns premium
quota for half the resolution); the floor caveat means the advantage here is
**understated, not overstated**.

⚠️ **Caveats (magnitude soft, direction firm):** N=8, one repo, single-shot, oracle
retrieval. claude-solo Opus cost is a floor (no thinking tokens) → conservative.
Codex-sub has its own (non-Claude) quota cap not modeled as scarce here — the claim
is specifically about the *Claude Max* seat. "Unbounded by Claude quota" means the
Claude seat is not the binding constraint for team3, not that the work is free.

---

## 0. มิติตัดสิน (อย่าวัดแค่ compression %)

**NET = runtime_cut − static_tax** + accuracy ต้องไม่ตก. ตารางผล:

| candidate | lane | mode | static_tax (tok/sess) | runtime_cut % | **NET** | accuracy Δ | local/priv | friction | model-weight |
|---|---|---|---|---|---|---|---|---|---|

- **static_tax** = tool-def tokens จ่ายทุก session. CLI/hook/proxy/wrap = **0 by construction**. MCP = นับจริง (Phase 0).
- **NET** บวกเยอะ + accuracy Δ ≥ −1% = ผ่าน. เท่ากัน → เลือก 0-tax delivery.

---

## 1. Phase 0 — นับ tax ก่อน (ถูกสุด, ทำแรก)

คัดผู้แพ้ก่อนเปลือง A/B. CLI/hook/proxy/wrap ข้าม (=0).

```powershell
# ดึง tool-list JSON ที่ host ส่งให้โมเดล (เช่น /context ของ CC, หรือ MCP listTools)
# แล้วนับด้วย Anthropic token-count API
py -c "import anthropic,json,sys; c=anthropic.Anthropic(); \
  tools=json.load(open('tools.json')); \
  print(c.messages.count_tokens(model='claude-opus-4-8', tools=tools, messages=[{'role':'user','content':'x'}]).input_tokens)"
```

- บันทึก per-tool + per-session total.
- **gate:** tax > plausible cut → ตัดทิ้งก่อน. (เป้าหลัก: **lean-ctx 76 tools** — ถ้า static = ~76k = ตายตั้งแต่ยังไม่ A/B เว้นมี lazy-load.)
- candidate tax (คาดการณ์ ต้องยืนยัน): RTK=0(CLI) · Headroom=0(wrap/proxy) หรือ ~3k(MCP 3 tools) · ecotokens=0(hook) · lean-ctx=? (เช็ค hook-mode) · ICM=**0 (standard=CLI)** · MemPalace=? · Supermemory=?

### Phase 0 — RESULTS (2026-06-21, instrument `bench/mcp_tax.py`, tiktoken cl100k proxy ±10%)

| server | tools | tok/session | avg | fattest tool |
|---|---|---|---|---|
| **Desktop_Commander** 🐋 | 26 | **11,502** | 442 | start_search 1,389 |
| codegraph | 8 | 1,653 | 206 | codegraph_node 373 |
| context7 | 2 | 964 | 482 | resolve-library-id 632 |
| fetch | 1 | 290 | 290 | — |
| caveman-shrink | ? | spawn-fail (npx cold >60s) — retry | | |

**ตัวเลข = "ถ้า eager" (worst-case บน host ที่ไม่ defer).** หลักฐาน N1 จริง: DC 11.5k/session, doctor บอกใช้ 6/26 → ~20 tool = idle tax ล้วน.

**Observation (สำคัญ):** Claude Code build นี้ **defer MCP ทุกตัว** (DC/codegraph/fetch/plugin_* อยู่ใน ToolSearch deferred list — โหลด schema เมื่อใช้). → **native lazy/Tool-Search = LIVE → eager-tax จริง ≈ 0 ที่นี่.** 11.5k คือสิ่งที่จ่ายบน **Claude Desktop / Codex / Gemini** ถ้าไม่ defer.

**บทสรุป Phase 0:** (1) tax จริงต่อ tool = 290–1,389 (ยืนยัน A-08 range). (2) whale = client ที่ ship tool เยอะ (DC). (3) **harness ต้องไม่ assume host มี lazy** → prefer CLI/hook (0-tax ทุก host) + บังคับ tool-subset/lazy บน host ที่ไม่ defer. (4) ICM standard=CLI = 0 → ถูกต้องแล้ว.

## 2. Phase 1 — token-cut A/B (RTK · Headroom · ecotokens · context-mode)

**task suite ตายตัว** (replay transcript จริง): code-search · file-read ใหญ่ · git/npm shell · RAG chunk · log dump.

วัด tokens in→out, tool ON vs OFF:
```powershell
ccusage --offline        # หรือ portaw bench (ccusage A/B wrapper)
```

**reuse harness — อย่าเขียนเอง:** Headroom มี eval suite พร้อม (token + accuracy):
```bash
python -m headroom.evals suite --tier 1   # GSM8K + TruthfulQA + workload tokens
```
รันให้ Headroom; ทำ parallel runner ให้ RTK ด้วย metric เดียวกัน.

### Phase 1 — RESULTS (2026-06-22, deterministic tiktoken cl100k A/B, tools LIVE this session, zero ccusage/cache noise)

**Method (reframe 06-22):** ใช้ **clean deterministic into-context proxy** (tiktoken บน tool-output จริง, encoder เดียวกันทั้ง 2 lane) — **ไม่ใช่** ccusage full-session (contaminated). = ทางเชื่อถือได้: reproducible, 0 cache noise. harness reuse: `bench/_compress_ab.py` (rtk) · `bench/_astgrep_ab.py` (ast-grep) จาก port-a-whip.

**rtk — shell-output cut** (portaw repo):

| command | raw tok | rtk tok | cut% |
|---|---|---|---|
| git_log_stat | 1310 | 115 | **91.2** |
| git_status | 83 | 12 | **85.5** |
| mixed 6-cmd suite | 6400 | 5134 | 19.8 |

→ per-command **85–91%** ที่ rtk fire จริง. mixed 19.8% = **UNDERSTATED artifact**: pytest row ใช้ `rtk py -m pytest` (rtk ไม่ rewrite `py -m` prefix → passthrough) + ls/grep ใช้ `git ls-files`/`git grep` (passthrough). lever จริง = bulky structured output (git/diff/build) → เรียก `rtk`-prefixed form. สอดคล้อง portaw anchor 26.3%-mixed.

**ast-grep — structural rung** (route→route_v2 over portaw/):

| mechanism | lane A (grep/read/edit) | lane B (ast-grep) | cut% |
|---|---|---|---|
| precision (find call sites) | text-grep 182 | 44 | **+75.8** |
| codemod (rename 4 files/7 sites) | 911 tight … 9452 full | diff 127 | **+86.1 … +98.7** |

**memory — ICM** live verified (icm 0.10.53 via `%LOCALAPPDATA%\icm\bin\icm.exe`); `recall` คืน scored relevant lessons. **LongMemEval ยังไม่รัน → A-07 เปิดอยู่** (quality vs MemPalace ยังไม่พิสูจน์).

**instruments READY:** ccusage 20.0.14 ✓ · icm.exe located (PATH fix = เพิ่ม `%LOCALAPPDATA%\icm\bin`) ✓ · tiktoken 0.13.0 ✓.

**ยัง vibes / open:** (1) full-session ccusage NET — contamination ยังไม่แก้ → **DEPRIORITIZED** (deterministic proxy แทนได้). (2) codegraph lane — ต้อง build index; prior proxy 06-08: callers/impact ~97% less, show-1-file 4.8x worse. (3) memory quality (LongMemEval).

### 2a. **stack-marginal** (คำถามใหม่จาก Headroom)

Headroom เสริม RTK ไม่ใช่แทน → วัด **marginal NET ของการเพิ่ม layer 2**:

| arm | token (6 saved tool-output fixtures) | accuracy | NET |
|---|---|---|---|
| OFF (baseline) | 2,732 | verbatim | — |
| RTK only | 1,406 (**-48.5%**) | verbatim/RTK-shaped | winner for normal shell path |
| Headroom core only | 2,732 (**0%**) | verbatim fail-open | Kompress dependency missing → passthrough |
| Headroom `[proxy]` only | 1,714 (**-37.3%**) | sentinels held | slower than RTK on this mix |
| **RTK + Headroom `[proxy]`** | 1,080 (**-60.5%**) | sentinels held | **+23.2% marginal** after RTK, but 0.3–1.8s per compressed fixture |

**§2a CLOSED 2026-06-24** — runner: `bench/_headroom_stack_ab.py`, Headroom
`0.27.0`, Linux Docker because current PyPI has no Windows wheel. Same saved
raw/RTK outputs, cl100k token proxy, 3 warm runs, exact semantic sentinels.

- **SmartCrusher home turf:** 500-row JSON 19,038→11,056 tok (**-41.9%**),
  11–26ms, all critical sentinels held. This is the useful deterministic rung.
- **Full Kompress/proxy:** 600-line build log 12,611→5,781 (**-54.2%**) but
  ~11.9s median in the CPU-only container. Source/search/code were 0–0.1%.
- **Packaging gate:** `0.27.0` installs on Linux; Windows falls back to maturin
  and fails without MSVC `link.exe`. Native Windows wheel is still open upstream.
- **Operational gate:** `headroom wrap codex` rewrites global provider/base URL
  and can add an MCP server. That collides with paw's preserve-user-config rule,
  ≤3 MCP ceiling, and Codex Desktop provider-scoped thread visibility.
- **Decision:** do **not** adopt global proxy/wrap/MCP or Headroom memory by
  default. Keep RTK as L1, context-mode as avoid-the-dump/search lane, ICM as
  memory. Consider Headroom SmartCrusher only as an optional L2 adapter for
  large JSON/API/DB outputs; require `HEADROOM_TELEMETRY=off`, no auto-apply,
  and a native-wheel/container deployment.

- prior art: [`sgaabdu4/claude-code-tips`](https://github.com/sgaabdu4/claude-code-tips) stack จริง (`headroom wrap claude` + rtk PreToolUse Bash) → **ศึกษา hook map ก่อน wire เอง**.
- decision: stack เฉพาะ JSON-heavy workload ที่ marginal NET > added complexity/latency; normal coding shell path ไม่ stack.
- **accuracy guard:** ทุก arm ต้อง hold task-success. Headroom เคลม GSM8K Δ0 / TruthfulQA +0.03 — verify บน task เรา (lossy + retrieve round-trip อาจกระทบงานจริง).

## 3. Phase 2 — memory (ICM · MemPalace · Supermemory)

- subset **LongMemEval** (MemPalace เคลม 96.6%). รัน ICM + Supermemory metric เดียวกัน.
- คอลัมน์เพิ่ม: local/privacy · setup-friction · host-coverage (ICM=18-host เด่นตรงนี้ ไม่ใช่ quality).
- ICM ไม่อยู่ใน leaderboard → นี่คือ A-07 ที่ต้องปิด.

### Phase 2 — RESULTS (2026-06-22, partial — deterministic in-session; LLM-judged user-run)

**deterministic ICM recall** (`bench/_icm_recall.py`, scratch db, no LLM, no moat pollution):

| metric | value | note |
|---|---|---|
| **hit@3** | **100%** (8/8) | paraphrase queries, near-zero surface-word overlap → real **semantic** recall (embeddings) |
| **MRR** | **0.938** | 7/8 ranked #1, 1 ranked #2 (Invoke-Command) |
| inject cost | **179 tok/query** avg (toon fmt) | NB: `-f json` reports false ~17k (carries 384-d embedding arrays) — measure `toon` |

→ retrieval **mechanically strong** บน corpus เล็ก. **caveat:** 8 lessons = ง่าย; moat จริงใหญ่กว่า → distractor เยอะ recall ยากขึ้น → 100% ที่นี่ ≠ 100% at scale.

**LLM-judged `icm bench-recall` = BLOCKED in-session** (shells out to `claude` CLI as answer backend; `CLAUDECODE=1` → nested claude exit 1). **user-run:** เปิด terminal ธรรมดา (นอก Claude Code) →
```
icm.exe bench-recall --runs 3            # with/without ICM answer accuracy
icm.exe bench-agent  --sessions 10       # end-to-end CC efficiency w/wo ICM
```

**A-07 ยังไม่ปิดสมบูรณ์:** (1) deterministic retrieval = ✓ (ดีบน corpus เล็ก). (2) LLM-judged answer-accuracy = pending standalone run. (3) **head-to-head vs MemPalace (LongMemEval) = ยังไม่ทำ** (ต้องลง MemPalace; likely Windows-friction เหมือน headroom) — นี่คือแกน "quality" ของ A-07 ที่ยังเปิด.

## 4. Phase 3 — stack-collapse

ของรวมร่าง vs ของแยกชิ้น:

| stack | total tax | NET รวม | ops complexity |
|---|---|---|---|
| lean-ctx เดี่ยว (token+mem+perm) | | | |
| RTK + ICM (+ Headroom?) แยกชิ้น | | | |

- ถ้า lean-ctx รวมร่างให้ NET ใกล้กันที่ tax ต่ำกว่า + ง่ายกว่า → พิจารณา collapse (mindset: best *และ* ง่าย).

---

## 5. Decision rules

1. anchor/ช่อง = **max NET** ที่ accuracy Δ ≥ −1% และ friction รับได้.
2. NET เท่ากัน → **0-tax delivery ชนะ** (CLI/hook/proxy/wrap > MCP).
3. stack layer 2 เฉพาะเมื่อ **marginal NET > added cost** (latency/weight/ops).
4. first-party OAuth (Claude/Codex sub) → **ห้าม proxy แบบ OAuth-exchange** (ToS-gray, A-10). proxy เก็บกับ GLM.

## 6. Reuse ledger (ไม่ rebuild)

| ต้องการ | reuse |
|---|---|
| token+accuracy harness | `headroom.evals` (fork) — ⚠️ headroom Windows-blocked (maturin/MSVC) |
| A/B token delta | `ccusage --offline` · `portaw bench` |
| tax count | Anthropic `count_tokens` API · `bench/mcp_tax.py` (tiktoken) |
| shell-output / structural A/B | **`bench/_compress_ab.py`** (rtk) · **`bench/_astgrep_ab.py`** (ast-grep) — lifted, ran 06-22 |
| memory recall (deterministic, no LLM) | **`bench/_icm_recall.py`** — ICM paraphrase hit@k, ran 06-22 |
| memory eval (LLM-judged) | `icm bench-recall` / `bench-agent` (standalone terminal) · LongMemEval (public, vs MemPalace) |
| stack wiring ตัวอย่าง | `sgaabdu4/claude-code-tips` hook map |
| compress + cross-host + session-mem | **`mksglu/context-mode`** (ELv2, local-first) — vetted + A/B 06-23, see §7 |

---

## 7. context-mode A/B (2026-06-23) — Think-in-Code vs rtk

> repo: `mksglu/context-mode` v1.0.165 · ELv2 (source-available, free personal use) · 18k★ · daily releases.
> harness: `bench/_cm_ab.py` (drives stdio MCP `ctx_execute_file`, tiktoken cl100k, same fixtures as `_compress_ab`).

**Privacy (constraint #10):** PASS. server bundle = 0 telemetry `fetch()`; only fetch = user-directed `ctx_fetch_and_index` wrapped in SSRF guard (classifyIp blocks 169.254 metadata). storage local (`~/.claude/context-mode/`). `ctx_insight` = opt-in browser launcher, not a POST. deps all-local (better-sqlite3 FTS5, mcp-sdk). postinstall 0 network.

**Mechanism:** not a compressor. `ctx_execute`/`ctx_execute_file` run agent-written code in a sandbox; **only `console.log()` enters context**, raw bytes stay in sandbox. Avoids the dump instead of shrinking it.

**Result (payload = durable context cost; same fixtures as rtk lane):**

| fixture | raw tok | rtk % | cm payload | **cm %** |
|---|---|---|---|---|
| git_log_stat | 2008 | 64 | 70 | **97** |
| grep_todo | 497 | 0 | 21 | **96** |
| ls_recursive | 132 | 0 | 9 | 93 |
| git_status | 48 | 85 | 7 | 85 |
| pytest_v | 38 | 0 | 17 | 55 |
| git_diff | 9 | 0 | 9 | 0 |
| **TOTAL mix** | **2732** | **49** | **133** | **95** |
| **BIG (raw≥400)** | **2505** | — | **91** | **96** |

- **96% headline = reproduced independently** (BIG lane). beats rtk (49% mix) on bulky aggregate-able output by avoiding the dump (97% vs 64% on git_log).
- **caveat 1 — code-echo overhead:** MCP result echoes the code+path back (git_log gross 233 vs payload 70). on already-tiny output (git_diff 9→gross 60) = **net loss**. route execute_file to BIG output only (context-mode hook matchers enforce this).
- **caveat 2 — lossy:** digest, not bytes. verbatim recall needs `ctx_index`/`ctx_search` (FTS5 BM25) lane — **not yet benched**.

**Overlap / direction:** context-mode SUBSUMES paw compress lane (rtk) + cross-host wiring + session-continuity. ICM survives (long-term governed brain ≠ working-ctx mem). nah survives (permission BLOCK/ASK guard ≠ SSRF/cred guard). → kills rationale to port paw write-path for self-built compress/cross-host. Build thin glue: wire context-mode + ICM + nah per host.

**Assumption ledger (recheck triggers):** (a) 96% verified ✓; (b) ELv2 license-key clause = no active paywall now, recheck on version bump that adds key enforcement; (c) bus-factor 1 (solo maintainer) + fast churn → mitigant: free-state source forkable.

### 7b. lossless lane — ctx_index + ctx_search (FTS5 BM25), 2026-06-23

> harness: `bench/_cm_search_ab.py` (fresh MCP session per cell). doc = context-mode README.md (94 KB = 23889 tok read-all). 8 (query, verbatim-answer-span) ground-truth pairs. matrix NL-paraphrase vs LEXICAL × limit {3,5}.

| lane | limit | recall | avg/q tok | savings/q |
|---|---|---|---|---|
| LEXICAL (doc vocab) | 3 & 5 | **8/8 = 100%** | 551 | 97.7% |
| NL (paraphrase) | 3 & 5 | **4/8 = 50%** | 506 | 97.9% |

- **savings ~98%/query, LOSSLESS** (verbatim chunk, exact answer span returned). engine solid: LEXICAL recall 100%.
- **recall is LEXICAL not semantic** — BM25 (Porter stem + trigram). query matching doc vocab → 100%; vague NL paraphrase → 50% first-shot (e.g. "snapshot size budget" misses the "priority-tiered XML snapshot" chunk). limit 3 vs 5 = no difference.
- **session dedup discovered:** ctx_search will not re-inject a chunk already served this session (re-querying same content in one session returns ~empty). benign context-saver; harness must use fresh session per measurement cell.
- **vs ICM (complementary, not overlapping):** ICM paraphrase recall = hit@3 100% (embeddings/semantic, §`_icm_recall`). context-mode FTS5 = lexical doc-search (fast, exact, lexical-sensitive). → keep ICM for semantic memory; context-mode for lexical doc/skill/MCP-list retrieval. Implication for wiring: agent should issue keyword-ish ctx_search queries (or retry with doc vocab on miss) to hit the 100% lexical regime.

**Next:** wire decision — see §7c (hook audit) for why blanket adoption is gated.

### 7c. hook/MCP wiring audit (2026-06-23) — why 0-def is not viable

> measured this session before wiring into CC.

**Static tax (mcp_tax on context-mode):** 11 tools = **7017 tok/session** (avg 637/tool; top: ctx_execute 1287, ctx_batch_execute 1148, ctx_search 1019). > codegraph(1653)+context7(964)+fetch(290) combined. Breaks north star #7 (cap ≤2-3 MCP).

**Hook map (plugin hooks.json):** PreToolUse[Bash|WebFetch|Read|Grep|Agent|mcp__] = interception (block curl/WebFetch, nudge to ctx_ tools). PostToolUse[*]/UserPromptSubmit/SessionStart/Stop/PreCompact = session-memory (record + inject). `posttooluse.mjs` = non-blocking, no output mutation → **hooks do NOT compress; compression = MCP tools only.**

**0-def NOT viable (key finding):** hooks are MCP-tool-entangled. SessionStart hook injects a **~900 tok routing block every session** that references `mcp__…ctx_*` heavily; session-memory is retrieved via `ctx_search` (an MCP tool). Without the 7k MCP tools, the hooks deliver only ~900 tok/session of instructions pointing at absent tools = pure waste. → any real value (compression OR memory) requires the 7k MCP tax.

**Collision vs existing CC stack (rtk + nah×9/×6 + portaw + graphify on Pre/PostToolUse):**
- ⚠️ **PreToolUse[Bash] race** — rtk rewrites the command (`git`→`rtk git`); context-mode also intercepts Bash. Two hooks mutating the same command = ordering/`updatedInput` conflict risk.
- ✅ **nah guard integrity preserved** — CC semantics: any hook `deny` wins; context-mode cannot approve-override nah.
- ✅ PostToolUse record / UserPromptSubmit / SessionStart / Stop = additive (latency + tokens, no conflict).
- overhead: PreToolUse[mcp__] fires on every MCP call.

**Decision:** blanket/global adoption rejected (7k tax + 900-tok injection + Bash race, against #7). **Recommended: project-scoped MCP, opt-in** — register context-mode MCP in this repo's `.mcp.json` only; tax confined to tool-output-heavy sessions where 97% compress + lossless search + session-mem clear the NET break-even. Keep **rtk as the global 0-tax compression default** (64%). Do NOT enable context-mode hooks globally. Re-measure real NET with `ccusage` over a few project sessions before any wider rollout.

### 7d. session-replay on REAL transcripts (2026-06-23) — overturns the B-lean

> harness: `bench/_session_replay.py`. Replays all 5 of this project's CC transcripts (464 tool_results) through measured A(context-mode)/B(rtk)/raw ratios. cl100k proxy. cm fixed = 8817/session (7017 defs + 900 inject); cm stats-keep 4%+120 echo, doc-keep 5%+120; rtk-keep 36% on git log/diff/status only; read-to-edit + small excluded.

| session | ops | bulky_cm | raw | rtk | cm | NET_B | NET_A | win |
|---|---|---|---|---|---|---|---|---|
| 7a38c3fe | 241 | 74 | 160342 | 159022 | 60131 | 1320 | 100211 | A |
| abf9a35f | 121 | 42 | 65425 | 65270 | 34857 | 155 | 30568 | A |
| e0daed1e | 81 | 39 | 47503 | 47322 | 18467 | 181 | 29036 | A |
| a67c415d | 14 | 11 | 10707 | 10707 | 9896 | 0 | 811 | A |
| 7ae3fc64 | 7 | 2 | 1187 | 1187 | 8350 | 0 | −7163 | B (tiny session) |
| **TOTAL** | 464 | 168 | 285164 | 283508 | 131701 | **1656** | **153463** | **A 4/5** |

- **avg bulky cm-eligible ops/session = 33.6** — far above the ~12 break-even. The §7c/chart B-lean assumed a typical session has <12 bulky ops; real data says 33.6. **Correction: earlier lean-B was wrong.**
- **why it flips:** the break-even chart credited rtk 64% on every bulky op. Real bulky ops are Grep / Read-to-analyze / WebSearch / MCP output — which rtk does NOT touch (it is git-output-specialized). rtk saved **1656 tok across all 464 ops** (~0); context-mode addresses all of them → 153k. So rtk's real per-op saving ≈ 0 on non-git output, and the bar to beat is near-zero, not 1280/op.
- **ceiling caveat:** the cm numbers assume 100% routing (agent actually calls ctx_execute/ctx_index on every bulky op). Real compliance ~60% (README's own hook-less figure). Sensitivity: at 50% compliance NET_A ≈ 76k, still ≫ rtk 1656. Robust to routing discount.
- **remaining unknown = live routing compliance** (agent behavior) — the one thing replay can't model. → resolved by the project-scoped live test: wire `.mcp.json`, run real sessions, compare `ccusage` deltas + observe actual ctx_ tool usage rate.

**Updated decision:** real-data NET strongly favors A. Proceed to project-scoped `.mcp.json` (this repo only) and measure live compliance + ccusage before wider rollout. rtk stays global default (harmless; just rarely fires here).

**CORROBORATION 2026-06-23 (live `ctx_execute`, 6 transcripts, bulky≥200tok):** category share of bulky output — **Read 62.1% · Bash:other 16.6% · Web 11.9% · Grep/Glob 5.8% · MCP 2.7% · Bash:git (rtk-able) 0.8%**. → **rtk addresses 0.8%, rtk-miss = 99.2%.** Hard-confirms §7d: the real token-killer for this workload = context-mode (Read→ctx_execute_file, Web→ctx_fetch, Grep→ctx_execute), not rtk. (call = first live compliance seed; ctx_execute verified working in CC.)
