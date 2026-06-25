# Skill Router Research — PUSH discovery + PULL content

> วันที่: 2026-06-26  
> สถานะ: evidence review สำหรับแก้ prototype; ไม่ใช่ benchmark result ของ paw

## ข้อสรุป

แนว `PUSH trigger → PULL skill content` ถูกทาง แต่ตัว PUSH ไม่ควรเป็น
keyword classifier หรือ embedding top-k ตรง ๆ

สถาปัตยกรรมที่หลักฐานสนับสนุนคือ:

```text
full skill package (อยู่นอก agent context)
→ สร้าง routing document/card
→ multilingual retriever หา candidate 8–20 ตัว
→ reranker เทียบ task กับ candidate แบบละเอียด
→ abstention + near-duplicate gate
→ เลือก skill set ขนาดเล็ก
→ PUSH เฉพาะ ID + เหตุผล
→ agent ตรวจและ PULL SKILL.md
```

สิ่งที่ควรหยุดทำ:

- เพิ่ม dictionary แยกภาษาไทย จีน ญี่ปุ่น สเปน ฯลฯ
- hard-code รายชื่อ framework/product ใน router
- เชื่อ cosine threshold เดียวว่าเป็น confidence
- ใช้เพียง `name + description` เป็น routing document
- ตีความ top-1 accuracy ว่าเพียงพอสำหรับงานที่ต้องใช้หลาย skill

## หลักฐานสำคัญ

### 1. Retrieval model ทั่วไปไม่ได้เก่ง tool/skill routing โดยอัตโนมัติ

ToolRet ทดสอบ 7.6k retrieval tasks บน corpus 43k tools และพบว่า retriever
ที่แข็งแรงบน benchmark IR ทั่วไปยังทำ tool retrieval ได้ไม่ดี คุณภาพ retrieval
ที่ต่ำลด task pass rate ของ agent ด้วย

ผลต่อ paw: การเปลี่ยน TF-IDF เป็น generic embedding อย่างเดียวไม่ใช่คำตอบสุดท้าย
ต้องมี frozen corpus เฉพาะ skill-routing และ hard negatives จาก false positive จริง

แหล่ง:
[Retrieval Models Aren’t Tool-Savvy, ACL 2025](https://aclanthology.org/2025.findings-acl.1258/)

### 2. Full skill body มีข้อมูลแยก skill ที่ description แยกไม่ได้

SkillRouter ใช้ bi-encoder ลด 80k skills เหลือ top-20 แล้วใช้ cross-encoder
rerank โดยทั้งสองขั้นอ่าน `name + description + body` นอก context ของ agent
การตัด body ออกจาก reranker ทำให้ผลตกมาก: average Hit@1 ของหลาย configuration
เหลือประมาณ 0.19–0.33 เทียบกับประมาณ 0.55–0.67 เมื่อใช้ full input

นี่แก้ความเข้าใจผิดสำคัญ:

> Router อ่าน full skill body เพื่อจัดอันดับได้ โดยไม่ต้อง PUSH body เข้า agent context

ผลต่อ paw: index ต้องเก็บ routing text จาก package เต็มหรือส่วนที่มีสาระ ไม่ควรอ่าน
เพียง frontmatter description

แหล่ง:
[SkillRouter: Retrieve-and-Rerank Skill Selection for LLM Agents at Scale](https://arxiv.org/html/2603.22455)

### 3. Candidate generation และ final decision เป็นคนละปัญหา

SkillRouter ใช้สอง stage:

1. bi-encoder สำหรับ recall และลด 80k → 20;
2. cross-encoder สำหรับแยก candidate ที่คล้ายกันมาก

pipeline ขนาด 1.2B ที่ fine-tune เฉพาะงานได้ average Hit@1 74.0% ขณะที่
encoder-only ของระบบเดียวกันได้ 65.4% แสดงว่า reranking เพิ่มคุณค่าจริง

ผลต่อ paw: multilingual MiniLM เหมาะเป็น candidate generator แต่ไม่ควรถูกใช้เป็น
final authority โดยตรง

### 4. คุณภาพ routing document สำคัญพอ ๆ กับ model

Tool-DE พบว่า tool docs มักขาดข้อมูลสำคัญ เช่นควรใช้เมื่อไรและมีข้อจำกัดอะไร
การเพิ่ม structured fields ได้แก่ function, `when-to-use`, limitations และ tags
ช่วย retrieval และทำให้ฝึก retriever/reranker เฉพาะทางได้ โดย `function` และ
`when-to-use` ให้ผลมากกว่าการเพิ่ม usage example อย่างเดียว

ผลต่อ paw: เพิ่ม routing card นอก `SKILL.md` หรือสร้างจาก package:

```yaml
id: django-security
does: review Django security
when:
  - task uses Django
  - task changes Django authentication or authorization
not_when:
  - framework is unknown
  - task is generic authentication design
requires_evidence:
  - django
complements:
  - tdd-workflow
```

นี่เป็น catalog metadata ไม่ใช่ hard-code ใน router

แหล่ง:
[Tools are under-documented: Simple Document Expansion Boosts Tool Retrieval](https://arxiv.org/html/2510.22670)

### 5. Multilingual retrieval ควรอยู่ใน shared semantic space

BGE-M3 รองรับมากกว่า 100 ภาษาและ cross-lingual retrieval โดย map หลายภาษาเข้า
semantic space เดียว หลักการนี้ตรงกับโจทย์ prompt ไทย/จีน/ญี่ปุ่น/สเปนที่ต้องค้น
skill docs ภาษาอังกฤษ

เครื่องปัจจุบันมี
`paraphrase-multilingual-MiniLM-L12-v2` แบบ ONNX อยู่แล้ว จึงใช้เป็น baseline
candidate retriever ได้โดยไม่ต้องเพิ่ม dictionary รายภาษา แต่ต้อง benchmark
กับ BGE-M3 หรือ model อื่นก่อน lock ระยะยาว

แหล่ง:
[M3-Embedding](https://arxiv.org/html/2402.03216)

### 6. Query/document expansion ใช้ได้ แต่ควรทำที่ ingestion ก่อน

Re-Invoke สร้าง synthetic queries หลายแบบต่อ tool ตอน indexing แล้วดึง intent
จาก request ตอน inference ใช้ multi-view ranking และรายงาน relative nDCG@5
improvement 20% สำหรับ single-tool และ 39% สำหรับ multi-tool ในชุดทดลองของงาน

ผลต่อ paw: สร้างตัวอย่าง task หลายภาษา/หลายถ้อยคำต่อ skill แบบ offline แล้วเก็บใน
routing card ดีกว่าเพิ่ม synonym ใน runtime code

แหล่ง:
[Re-Invoke: Tool Invocation Rewriting for Zero-Shot Tool Retrieval](https://aclanthology.org/2024.findings-emnlp.270/)

### 7. Multi-skill ต้องเป็น set-selection ไม่ใช่ top-2 แบบตายตัว

SkillRouter benchmark มี multi-skill queries มากกว่างาน single-skill และชี้ว่า
Hit@1 อาจดูดีทั้งที่ยังเก็บ skill ที่จำเป็นไม่ครบ จึงรายงาน Recall@K และ
Full Coverage@10 เพิ่ม

ผลต่อ paw:

- อนุญาต 0–2 skill ใน UI รุ่นแรกได้;
- แต่ internal scorer ควรเลือก set ตาม complementarity และ marginal utility;
- ห้ามเลือกสอง skill ที่เป็น substitutes/near-duplicates;
- corpus ต้อง label ทั้ง expected set และ acceptable-but-unnecessary skills

### 8. PULL ลด context tax จริง แต่ยังต้องมี discovery trigger

Anthropic Tool Search โหลดเพียง search tool แล้วคืน reference ราว 3–5 tools;
เอกสารรายงานว่าลด tool-definition context ได้มากกว่า 85% ในตัวอย่างของตน
OpenAI Tool Search ก็รองรับ deferred loading และรักษา prompt cache โดย inject
เครื่องมือที่ค้นพบไว้ท้าย context

ผลต่อ paw: native Tool Search เป็น PULL delivery ที่ดี แต่ PUSH discovery ยังมี
คุณค่าเมื่อ agent ไม่รู้ว่าควรค้น โดย PUSH ควรส่ง reference ไม่ใช่ content

แหล่ง:

- [Anthropic Tool Search](https://platform.claude.com/docs/en/agents-and-tools/tool-use/tool-search-tool)
- [OpenAI Tool Search](https://developers.openai.com/api/docs/guides/tools-tool-search)
- [Codex Agent Skills](https://developers.openai.com/codex/skills)

## Architecture ที่เสนอ

### Offline / catalog build

```text
SKILL.md + references metadata
→ extract full routing text
→ audit/generate routing card
   - does
   - when
   - not_when
   - requires_evidence
   - complements
   - substitutes
   - example_tasks
→ embed/cache documents
```

การ generate routing card อาจใช้ LLM แบบ offline แล้วให้คน review จึงไม่เพิ่ม
runtime cost และ config สามารถ version/control diff ได้

### Runtime

```text
raw task + bounded task state
→ multilingual semantic retrieve top 8
→ lexical/exact fusion
→ apply requires_evidence / not_when filters
→ rerank top 3–8 using full routing cards
→ calibrated gate:
   - no candidate: silence
   - near tie among substitutes: silence
   - complementary clear winners: return set up to budget
→ PUSH IDs + evidence
→ agent verifies and PULLs selected SKILL.md
```

### Reranker choices

เรียงจาก MVP ไปสูงขึ้น:

1. deterministic routing-card constraints + semantic score;
2. local cross-encoder/reranker;
3. bounded AI-lite adjudicator เฉพาะ top 3 ที่กำกวม;
4. fine-tuned skill retriever/reranker เมื่อมี labeled corpus มากพอ

ไม่ควรเริ่มจากข้อ 4

## Revised MVP

MVP ใหม่ควรมี:

1. `SkillRecord.routing_text` ที่อ่าน body นอก agent context;
2. pluggable multilingual semantic scorer;
3. routing-card constraints แทน language/framework hard-code;
4. top-k candidate stage แยกจาก selection stage;
5. output 0–2 complementary skills;
6. shadow logs สำหรับสร้าง hard-negative corpus;
7. metrics:
   - Precision@1;
   - set precision/recall;
   - full required-skill coverage;
   - silence accuracy;
   - rejected PUSH rate;
   - context bytes;
   - latency.

## สิ่งที่ prototype ปัจจุบันสอน

Dogfood เจอ false positives ต่อเนื่อง:

- `write-a-skill` จากคำกว้าง `agent + skill`;
- `deploy-model` จากคำ overloaded ว่า `intent-based routing`;
- `django-security` / `quarkus-security` จาก generic authentication task.

สิ่งเหล่านี้ไม่ควรแก้ด้วยรายชื่อคำต้องห้ามใน source code แต่ควรกลายเป็น:

- hard negatives ใน corpus;
- `requires_evidence` ใน routing card;
- near-duplicate/substitute groups;
- reranker evaluation cases.

ดังนั้น prototype rule-based ปัจจุบันควรถูก refactor ก่อนนำไปต่อ hook จริง
ไม่ควรขยาย dictionary ต่อ

