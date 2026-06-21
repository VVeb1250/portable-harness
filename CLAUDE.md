# portable-harness — Working Mindset

> เป้าหมายโปรเจกต์: harness พกพา (curated tools + token-cut + shared-memory ข้าม heterogeneous agents).
> ออกแบบ: [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) · L0 brain: [docs/SHARED-BRAIN.md](docs/SHARED-BRAIN.md)
> **ทุก session คิดแบบนี้** (mindset ของเจ้าของ — เขียนไว้ให้ส่งต่อข้าม session).

---

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
