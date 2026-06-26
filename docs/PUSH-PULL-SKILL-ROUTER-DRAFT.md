# PUSH + PULL Skill Router — ร่างแนวทาง

> สถานะ: เจ้าของเห็นชอบและมี shadow-mode prototype แล้ว (2026-06-26)

## เป้าหมาย

ลดการส่งรายการ skill ทั้งหมดเข้า context แต่ยังช่วยให้ agent ไม่พลาด skill
ที่เหมาะกับงาน

แนวคิดสั้นที่สุด:

> PUSH ชี้ว่า skill ไหนตรงกับงาน ส่วน PULL โหลดคำสั่งเต็มของ skill นั้น

## การทำงาน

```text
1. ผู้ใช้ส่งงาน
2. Router ดู prompt และ task state ขนาดเล็ก
3. Multilingual semantic retrieval หา anchor ใน compiled skill graph
4. Router เดินกราฟแบบ bounded 1 hop และยุบ skill ที่เป็น substitutes
5. Router PUSH compact candidate cards ไม่เกิน 3 ตัว
6. Agent ตรวจ/rerank candidate ตามความหมายของงานจริง
7. Agent PULL SKILL.md เฉพาะ skill ที่ยอมรับ
8. Agent ทำงานตาม skill
```

ถ้าไม่มี match ที่ชัดเจน Router ต้องเงียบ และ agent ยังสามารถค้นหรือเรียก skill
เองได้ตามปกติ

## สิ่งที่ PUSH ส่ง

PUSH ไม่ส่งเนื้อหา `SKILL.md` และไม่ส่ง catalog ทั้งหมด โดยส่งเพียง:

```json
{
  "skill": "agent-harness-construction",
  "match": "clear",
  "reason": "งานเกี่ยวกับการออกแบบ routing และ action space ของ agent",
  "action": "load_skill"
}
```

ข้อมูลนี้ควรมีขนาดเล็ก เป็นโครงสร้างคงที่ และส่ง candidate ไม่เกินสามตัว
ก่อนให้ agent เลือก skill ที่จะ PULL โดยผลลัพธ์สุดท้ายใช้ได้ 0–2 skills

## ระดับการตัดสินใจ

### Clear match

Router มีหลักฐานเพียงพอว่า description และ trigger ของ skill ตรงกับงาน

- PUSH skill ID และเหตุผล
- Agent ตรวจความสมเหตุสมผล
- ถ้าไม่มี conflict ให้ PULL `SKILL.md` และใช้ skill

### Possible match

ยังมีความกำกวมหรือมีหลาย skill ใกล้เคียงกัน

- MVP: ไม่ PUSH และปล่อยให้ agent ค้นเอง
- ระยะต่อไป: PUSH คำแนะนำให้ค้น เช่น `search skills for agent routing`

### Weak match

- เงียบ

## ใครมีอำนาจทำอะไร

| ส่วน | หน้าที่ | ห้ามทำ |
| --- | --- | --- |
| Router | ค้น, จัดอันดับ, อธิบายเหตุผลสั้น ๆ | โหลด skill เต็ม, บังคับทำ workflow, execute tool |
| Agent | ตรวจข้อเสนอและตัดสินใจขั้นสุดท้าย | เชื่อ PUSH โดยไม่ตรวจ task |
| Skill loader | โหลด `SKILL.md` ตาม ID | เลือก skill หรือเดา intent |

Router จึงเป็นตัวช่วยตรวจ trigger ไม่ใช่ผู้ควบคุม agent

## ตัวอย่าง

ผู้ใช้:

```text
ทำให้ PUSH skill router ฉลาดขึ้นได้ไหม
```

Router:

```text
clear match: agent-harness-construction
reason: งานเกี่ยวกับ agent routing, action space และ context budget
```

Agent:

```text
ตรวจแล้วตรงกับงาน
→ PULL agent-harness-construction/SKILL.md
→ ทำงานตามคำสั่งใน skill
```

กรณี Router เสนอ `design-quality` เพราะเห็นเพียงคำว่า “design”:

```text
Agent ตรวจพบว่าเป้าหมายคือออกแบบ router ไม่ใช่ UI
→ ปฏิเสธข้อเสนอ
→ ไม่โหลด SKILL.md
```

## MVP ที่เสนอ

เส้นทางเริ่มงานของ prototype:

```text
UserPromptSubmit
→ raw multilingual task capsule
→ semantic anchor search นอก context
→ bounded skill-graph traversal
→ compact candidate cards (≤3)
→ agent verification/rerank
→ PUSH accepted skill ID + reason
→ agent PULL SKILL.md
```

Task capsule เก็บ raw goal แบบ bounded เพื่อไม่ผูกกับ dictionary รายภาษา:

```json
{
  "goal": "สิ่งที่ผู้ใช้ต้องการ"
}
```

ยังไม่ทำใน MVP:

- การ PUSH ระหว่าง tool calls
- AI adjudicator
- การโหลด skill อัตโนมัติโดยไม่ผ่าน agent
- การแก้ weights จาก feedback แบบ online

## เกณฑ์วัดก่อนยอมรับ

เทียบกับระบบ catalog-in-context ปัจจุบัน:

1. Clear-match precision — skill ที่ PUSH ต้องถูกจริง
2. Miss rate — งานที่ควรใช้ skill แต่ Router เงียบ
3. False interruption rate — PUSH ที่ agent ปฏิเสธ
4. Skill-use rate — PUSH แล้ว agent โหลดและใช้จริง
5. Context tokens — metadata และคำแนะนำที่เพิ่มต่อ task
6. Outcome delta — งานสำเร็จหรือมีคุณภาพดีขึ้นหรือไม่

คุณภาพต้องวัดจาก frozen task corpus ไม่ปรับ threshold จากตัวอย่างที่เพิ่งทดสอบ
ไปเรื่อย ๆ

## Safety defaults

- ความไม่แน่ใจจบด้วย silence
- PUSH เป็นข้อเสนอ ไม่ execute และไม่ติดตั้งอะไร
- Agent เป็น final verifier
- Security/mistake warnings แยก lane จาก workflow skills
- เก็บ fallback ให้ agent ค้น skill เองได้เสมอ

## Decision ที่ต้องเห็นชอบก่อนลงมือ

1. ยอมรับหลัก `PUSH trigger, PULL content` หรือไม่
2. `clear match` เป็น must-consider ไม่ใช่ execute/load อัตโนมัติ
3. Candidate shortlist สูงสุด 3; accepted skill set สูงสุด 2
4. เริ่มด้วย shadow mode

## ผล dogfood เบื้องต้น

Catalog จริง 175 skills, query เรื่อง agent skill router:

- intended `agent-harness-construction` อยู่ใน top-3 ครบไทย จีน ญี่ปุ่น สเปน;
- ญี่ปุ่นได้ intended skill อันดับ 1;
- generic authentication + tests ได้ `security-review` และ `tdd-workflow`;
- unrelated Thai meeting-summary prompt ได้ silence;
- output JSON อยู่ราว 1.3 KB ต่อ query แทนการส่ง catalog ทั้งหมด;
- local ONNX inference หลัง warm-up ราว 3 วินาที จึงยังเป็น shadow prototype
  ไม่ควรผูกกับทุก prompt จนกว่าจะ cache corpus vectors และ benchmark latency.
