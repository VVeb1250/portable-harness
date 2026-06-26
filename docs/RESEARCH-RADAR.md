# Research Radar — Self-Improving Harness Papers (Phase-2 Optimizers)

> สถานะ: **watch / candidate-backlog** (ยังไม่ adopt) · logged 2026-06-25.
> mindset: [../CLAUDE.md](../CLAUDE.md) · architecture: [./ARCHITECTURE.md](./ARCHITECTURE.md) · session state: [./STATUS.md](./STATUS.md)
> เหตุผลที่มี doc นี้: รวม paper ที่ "harness/skill ปรับปรุงตัวเอง" ไว้ที่เดียว ให้ **AI ทุก host เห็น** (CC memory อยู่ ~/.claude เห็นคนเดียว). challenge everything (#1) — ตัวเลขในนี้ยังไม่ verify ที่ arxiv source.

---

## 0. ข้อสรุปสำคัญสุด (อ่านอันเดียวพอ)

ทั้ง 3 paper = **optimizer / refiner ไม่ใช่ originator**. ทุกตัวต้องมีก่อน: (a) harness ที่**รันได้แล้ว** · (b) **trace/rollouts** ให้ mine · (c) **benchmark + score** ให้ validate.

→ **ช่วยตั้งแต่ concept ตั้งต้นไม่ได้.** มันขัดเงาของที่มี ไม่ออกแบบของใหม่. ตอน concept = งานคน/ดีไซน์ยังแทนไม่ได้.

**ของจริงที่บล็อกอยู่ = ทุกเสายังไม่มี benchmark วัด** (router วัด route ถูก/ผิด · memory วัด recall · team วัด handoff). **สร้างตัววัดต่อเสา = งานที่ปลดล็อก paper ทั้ง 3 พร้อมกัน.** ตรงกับ #5 (measure-before-lock) + memory `concept-scorecard-2026-06-24`: อย่า polish เสาก่อน cost-axis ตอบ.

ลำดับที่ถูก:
```
1. ออกแบบ concept (คน)            ← ตอนนี้อยู่ตรงนี้
2. ทำให้รัน + วัดได้ (benchmark)   ← ด่านที่ขาด ทุกเสา
3. สะสม trace
4. ▶ paper ทั้ง 3 เข้าตรงนี้        ← phase-2
```

---

## 1. สาม paper (one-liner + กลไก)

### R-01 · SLM are the Future of Agentic AI (NVIDIA, 2506.02153)
- **คือ:** งาน agent ส่วนใหญ่ = แคบ/ซ้ำ → โมเดลเล็ก (SLM, <~10B, รันในเครื่อง ollama) พอ. ระบบควร heterogeneous (ผสมเล็ก+ใหญ่).
- **แตะเสา:** **router** — เพิ่มชั้น `local-slm`. งานง่าย/เสี่ยงต่ำ → SLM (ฟรี); งานลับ → SLM ในเครื่อง (โค้ดไม่รั่ว, #10).
- **status:** FUTURE — ยังไม่มี local SLM (detail: CC memory `slm-router-tier-future`).

### R-02 · SkillOpt — text-space optimizer for skills (Microsoft, 2605.23904)
- **คือ:** มอง skill `.md` = external state ของ frozen agent. optimizer LLM แปลง scored rollouts → edit **add/delete/replace** บน doc เดียว; รับเฉพาะถ้า **held-out val ดีขึ้น**. มี learning-rate budget + rejected-edit buffer + epoch meta-update. deploy = 0 overhead.
- **ผล (อ้าง):** SpreadsheetBench GPT-5.5 41.8%→80.7%; Claude Code +19.1.
- **แตะเสา:** แก้ **skill doc** (รวม router policy ถ้าเขียนเป็น doc + วัดได้). pilot ใกล้สุด = optimize coding skill เทียบ [bench/swe_probe/](../bench/swe_probe/) (มีคะแนนอยู่แล้ว).
- **ติด:** skill ส่วนใหญ่ (caveman/save/resume) ไม่มี scalar → optimize ไม่ได้. train แพง (optimizer frontier รัน rollouts เยอะ). transfer "not very consistent".

### R-03 · Self-Harness — harnesses that improve themselves (Shanghai AI Lab, 2606.09498) ★ ตรงเป้าโปรเจกต์สุด
- **คือ:** agent แก้ **harness ตัวเอง** (tools+instructions+filters) per-model. loop 3 ขั้น: **Weakness Mining** (หา failure เฉพาะโมเดลจาก trace) → **Harness Proposal** (แก้ harness น้อยแต่ตรงจุด) → **Proposal Validation** (รับเฉพาะผ่าน regression test).
- **ผล (อ้าง):** Terminal-Bench-2.0, 3 โมเดล: 40.5→61.9 / 23.8→38.1 / 42.9→57.1.
- **แตะเสา:** **harness ทั้งก้อน** (CLAUDE.md/AGENTS.md/router/ctx-mode rules) + **per-model** = ตรงกับ heterogeneous-agent goal สุด.

### R-04 · Squeez — Task-Conditioned Tool-Output Pruning (arxiv 2604.04979, Apr 2026) — *adjacent category (token-cut, ไม่ใช่ self-improving)*
- **คือ:** prune tool-output **ตาม task ปัจจุบัน** (ตัด noise เฉพาะที่ task ไม่ใช้, เก็บ signal) = next-gen rtk (rtk = static rules, task-agnostic).
- **แตะเสา:** **bundle token-cut core** — ↓token + ↑qual **พร้อมกัน** = ตอบ win-condition เสา bundle (A2 "ยังไม่พิสูจน์") ตรงสุดในบรรดา paper ทั้งหมด.
- **status:** WATCH (vetted 2026-06-25) — **code SHIPPED** [KRLabsOrg/squeez](https://github.com/KRLabsOrg/squeez) Apache-2.0 (CLI+model+dataset), perf −92% tokens / 0.86 recall. **แต่ engine = 2B-model infer ต่อ tool-output → gate เดียวกับ R-01 (local SLM ยังไม่มี)** + hot-path latency vs rtk. ไม่ drop-in. **unblock = local SLM (รวม R-01).** vs LLMLingua = REJECT (torch + format-lossy). detail: [BUNDLE.md §6 scout-b](./BUNDLE.md).

---

## 2. Tension ที่ paper เปิดออกมา (insight ใช้ได้จริง)

**Self-Harness: "harness ต้อง model-specific"  ⟷  โปรเจกต์: "portable / author-once" (#8). = ขัดกัน.**

ทางออก (paper ชี้ทาง): **core บางๆ portable + overlay เฉพาะโมเดลที่ learn เอง.**
- codex พังคนละแบบ deepseek → mine trace → gen harness delta คนละชุด → ทับบน core เดียว.
- ⚠️ overlay เฉพาะโมเดล = token เพิ่มต่อโมเดล → ชน token-budget (#7). overlay ยิ่งเยอะยิ่งหนัก.
- แก้ tension "พกพา vs เฉพาะโมเดล" ที่ ARCHITECTURE ยังไม่ตอบ.

---

## 3. ต่อเสา — ช่วยได้มั้ย + precondition

| เสา (ARCHITECTURE) | paper ที่เกี่ยว | ช่วย? | ต้องมีก่อน |
|---|---|---|---|
| **bundle** (L0) | — | ❌ อ่อน | packing deterministic ไม่ใช่ model-behavior → ไม่มี failure ให้ mine |
| **router** (L1, [paw/router.py](../paw/router.py)) | R-01 SLM · R-03 mine | ✅ ดี (ภายหลัง) | **benchmark วัด route ถูก/ผิด** — `_classify` มี label อยู่แล้ว + swe_probe มีคะแนน = ใกล้สุด |
| **memory** (L0, ICM) | R-03 | 🟡 กลาง | **recall benchmark** (hit-rate) แล้วค่อย tune retrieval harness |
| **agent-team** (L2, future) | R-03 | ✅ ดี (เชิงแนวคิด) | ทีมยังไม่มี = ไม่มี trace = รอ. fit สุดเชิงทฤษฎี (mine handoff fail → แก้ orchestration) |

---

## 4. วิจารณ์ร่วม (challenge everything)

1. **regime ไม่ตรง (ข้อใหญ่สุดของ R-03):** paper เริ่มจาก "minimal harness" แล้ว**เพิ่ม**. โปรเจกต์เรา harness **อ้วนแล้ว** (ECC ร้อยกว่า skill) — ปัญหาคือ **bloat ไม่ใช่ขาด**. method ต้องกลับด้าน (prune ไม่ใช่ add).
2. **ด่าน benchmark-cost:** ทุก loop ต้องมี benchmark + รัน rollouts เยอะ = token แพงตอน train (แม้ deploy ฟรี). ROI ต้องคุ้มกว่า hand-tune.
3. **transfer ไม่นิ่ง:** R-02/R-03 เคลม transfer ข้าม model/host แต่ "not very consistent" → อย่าคิดว่า optimize ครั้งเดียวใช้ทุก host.
4. **เทสบนโมเดลคนละชุด:** open models (MiniMax/Qwen/GLM/GPT-5.5) — เราใช้ codex/deepseek/Claude → gain จริงไม่รู้.
5. **เคลมใหญ่มาจาก task score คม** (spreadsheet/terminal). งานในโปรเจกต์ score คลุมเครือกว่า → gain น่าจะน้อยกว่า.

---

## 5. Recommendation + gate

- **อย่าเอา paper ไหนจับเสาตอนนี้** — premature (เสายัง deferred, ยังไม่ validate).
- **งานที่ปลดล็อกทั้งหมด = เขียน benchmark/score ต่อเสา.** router ทำก่อน (substrate ใกล้สุด).
- ใช้ R-03 เป็น **method** (mine→propose→regression-gate) กับ CLAUDE.md/router ได้แม้ไม่ลง code เขา.
- **recheck trigger:** (a) เสาใดมี benchmark วัดได้ → pilot paper ที่ตรงเสานั้น · (b) ลง local SLM → R-01 · (c) มี Terminal-Bench/swe_probe rollouts สะสม → R-03.

> ทั้ง 3 = **เครื่องมือ phase-2**. ห้าม block phase-0/1 (validate + wire L0) ด้วยมัน.
