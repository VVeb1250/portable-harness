# BENCH — runnable token-cut + memory benchmark

> สถานะ: **plan, design-only** · 2026-06-21 · เจ้าของ: supimol.web@gmail.com
> จุดประสงค์: **ฆ่า vibes** — วัด NET ก่อน lock anchor. mindset #5 (anti-vibes/empirical).
> คู่กับ: [STATUS.md](./STATUS.md) §4 · [ARCHITECTURE.md](./ARCHITECTURE.md) §6 ledger.

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

### 2a. **stack-marginal** (คำถามใหม่จาก Headroom)

Headroom เสริม RTK ไม่ใช่แทน → วัด **marginal NET ของการเพิ่ม layer 2**:

| arm | token (5-task suite) | accuracy | NET |
|---|---|---|---|
| OFF (baseline) | | | — |
| RTK only | | | |
| Headroom only | | | |
| **RTK + Headroom** | | | |

- prior art: [`sgaabdu4/claude-code-tips`](https://github.com/sgaabdu4/claude-code-tips) stack จริง (`headroom wrap claude` + rtk PreToolUse Bash) → **ศึกษา hook map ก่อน wire เอง**.
- decision: stack เฉพาะถ้า marginal NET(layer2) > added complexity/latency (local HF model).
- **accuracy guard:** ทุก arm ต้อง hold task-success. Headroom เคลม GSM8K Δ0 / TruthfulQA +0.03 — verify บน task เรา (lossy + retrieve round-trip อาจกระทบงานจริง).

## 3. Phase 2 — memory (ICM · MemPalace · Supermemory)

- subset **LongMemEval** (MemPalace เคลม 96.6%). รัน ICM + Supermemory metric เดียวกัน.
- คอลัมน์เพิ่ม: local/privacy · setup-friction · host-coverage (ICM=18-host เด่นตรงนี้ ไม่ใช่ quality).
- ICM ไม่อยู่ใน leaderboard → นี่คือ A-07 ที่ต้องปิด.

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
| token+accuracy harness | `headroom.evals` (fork) |
| A/B token delta | `ccusage --offline` · `portaw bench` |
| tax count | Anthropic `count_tokens` API |
| stack wiring ตัวอย่าง | `sgaabdu4/claude-code-tips` hook map |
| memory eval | LongMemEval (public) |
