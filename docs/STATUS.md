# STATUS — session state (compact-survival)

> อัพเดท: 2026-06-24 · state ก้อนเดียวให้ session หลัง-compact resume ได้ครบ. **resume: อ่าน §A (identity) → §D (current work) ก่อน.**
> Doc map: [CLAUDE.md](../CLAUDE.md) mindset+routing · [ARCHITECTURE.md](./ARCHITECTURE.md) blueprint · [SHARED-BRAIN.md](./SHARED-BRAIN.md) L0 · [BENCH.md](./BENCH.md) bench detail · **STATUS.md (นี่)** = current truth.
> ⚠️ ประวัติ handoff ละเอียด §1-16 (pre-pivot harness framing → ECC collision → fork → context-mode adopt → swe-probe round 1) = **condensed ลงนี่แล้ว**; กู้เต็มได้ที่ git ก่อน commit `71a2815`.

---

## A. IDENTITY — paw คืออะไร (locked 2026-06-22, §12 เดิม)

> **paw = personal, cross-host, shared-brain agent-team substrate** — ไม่ใช่ "harness แข่ง ECC".

- **#1 personal** → ride seat *ตัวเอง* interactive = defensible. **ห้าม ship/resell/OSS-arbitrage.** personal-tool, อย่า over-engineer เป็น product.
- **#2 coordination = B (shared-state/blackboard) + heterogeneous members** — แต่ละตัวมี brain+specialty เอง (Opus reason · DeepSeek/GLM bulk · Codex/Gemini ฯลฯ) แชร์ ICM blackboard. two-tier memory (shared + per-member private).
- **coordination ladder:** A task-handoff = table-stakes (ฟรี) · **B shared-state = moat (build)** · C mesh/role-protocol = commodity (LangGraph/AutoGen/ECC → rent, อย่าสร้าง = portaw รอบ 4).
- **L0 scope = thin + team-shaped:** สร้างเฉพาะ shared-brain(ICM) + cross-host wiring + seat-router. general-harness breadth (skills/instincts) = ECC ทำแล้ว → wrap/ปล่อย.
- **moat:** distro ตาย (ECC ทำแล้ว). moat จริง = personal cost/quota economics (ride seat) + agentic + shared-brain glue ที่ Fusion/ECC ไม่มี. L2-team value = **cost/quota ไม่ใช่ quality** (literature: solo ≥ team on quality compute-controlled).

## A2. CONCEPT SCORECARD — เสา 3 ต้น อยู่ตรงไหน (audit 2026-06-24)

> meta-verdict: **track ถูก (measure-before-build), เสายังเป็นโครง — โดยตั้งใจ.** เสา 1-3 ยังไม่ครบเพราะ **ยังไม่มี consumer จริง** (heterogeneous members ยังไม่เกิด → gate ด้วย economics §D). ⚠️ อย่า polish เสาก่อน #3 ตอบ = portaw รอบ 4 (build C-tier ที่ rent ได้).

| เสา | แพลน (§A) | สถานะจริงวันนี้ | gap ที่เหลือ |
|---|---|---|---|
| **1 bundle** (↓tok+↑qual) | curated mcp+non-mcp net-win | ICM ✅net-pos · rtk ✅เล็ก(workload 0.8%) · nah ✅ · **ctx-mode ❌ +7.9k/compliance 8% = net-neg, folded** | "↓tok AND ↑qual พร้อมกัน" = **ยังไม่พิสูจน์**. qual empirical มีแค่ swe-probe sandbox ไม่ใช่ daily-use |
| **2 router** (skills/mcp/seat) | smart routing | ctx-route = **static nudge ใน CLAUDE.md, compliance 8%** · skill-router = ECC(suggestion-only) · seat-router = planned | **ฉลาดขึ้น = ยัง**. hook-enforce REJECTED (Read บีบไม่ได้, ไม่มี portable hard-enforce, ชน #8) |
| **3 memory** (two-tier shared) | shared blackboard + per-member private | ICM single-agent ✅ใช้จริง (governed recall + L3 overlay) | **shared-brain ข้าม member = ยังไม่มี** (ไม่มี member อื่น; DeepSeek=bare API ไม่อ่าน/เขียน ICM). per-member private tier = ไม่ build |

→ unblock ถัดไป = **#3 agentic cost axis** (§F.3): ตอบ team<solo บน cost จริงไหม → ค่อยตัดสินว่า build เสา 1-3 ให้ครบคุ้มไหม. ตอนนี้ oracle-mode → quota-delta marginal → ตอบไม่ได้.

## B. 🔱 FORK / REUSE ledger — fork จริงน้อยมาก (mental model 5 ชั้น)

| ชั้น | นิยาม | ตัว |
|---|---|---|
| ① vendored subtree | portaw installer subtree (agents_md/runner/install/healthcheck/state/router-wiring) → `paw/` |
| ② dependency (install+call) | **ICM**(mem) · **rtk**(token) · **nah**/gitleaks/osv/infisical(secure) · codegraph/ast-grep/context7(sets) · **context-mode**(compress+session-mem+cross-host MCP) · **DeepSeek API**(workhorse cross-vendor) · OpenRouter Fusion |
| ③ fork skeleton (1 ตัว, ยังไม่เลือก) | agent-team: **Agyn** OR **MASAI** — port pattern จาก HyperAgent/ALMAS · +AgentPool(seat-riding) |
| ④ wrap/interop | **ECC** (member รัน ECC เป็น L0; paw bridge บนนั้น) |
| ⑤ reference only | agentmemory(mem ceiling) · MoA(ensemble ref) · SWE-bench-Lite(task data) |

→ fork จริง = ① portaw subtree + ③ agent-team skeleton 1 ตัว (ยังไม่เลือก). ที่เหลือ = install+call หรือ read-then-port-idea. **ไม่ใช่ merge N codebase.**

## C. LIVE env + components (what actually runs)

- **ICM 0.10.53** (`%LOCALAPPDATA%\icm\bin\icm.exe`) — semantic memory, CLI=0-tax. ⚠️ PowerShell `icm`=Invoke-Command alias → เรียก `icm.exe`/full path. store/recall LIVE.
- **rtk** — token-cut Bash-hook (global). บีบ git ดี แต่ workload นี้ rtk-able แค่ ~0.8% (Read 62% ครอง).
- **nah 0.9.1** — security guard PreToolUse (BLOCK curl|bash · ASK dual-use/rm-rf · ALLOW git_safe). dual-use→ASK ห้าม loosen.
- **context-mode MCP** (project-scoped `.mcp.json`, ELv2 local-first) — ctx_* 11 tools, +7.9k tok/session repo นี้. routing nudge block ใน CLAUDE.md. **gate = folded (§D).**
- **swe-probe** `bench/swe_probe/` — team-vs-solo measurement harness (committed `71a2815`).
- WSL Ubuntu + swebench + Docker Desktop (flask env-image cached, eval ~1-2min). `$env:DEEPSEEK_API_KEY` set. ccusage 20.0.14 · tiktoken 0.13.0 · iii.exe PATH.
- **GateGuard hook** = ECC, fact-forcing บน Bash/Edit/Write (fires ทุก op session นี้). disable = `ECC_GATEGUARD=off`.

## D. CURRENT WORK — swe-probe (existential: team ถูกกว่า solo จริงไหม)

**คำถาม:** Claude-plan + DeepSeek-implement → hold resolution-rate vs Claude-solo ที่ quota ถูกกว่าไหม? (fork ③ gate)
**design:** oracle retrieval · single-shot · 3 arm (claude-solo / team / deepseek-solo) · objective = swebench `resolved`. NOT agent-team framework — "team" = Claude ขับมือ + DeepSeek API.

**🟢 N=2 QUALITY result (clean):**
| instance | claude-solo | team ($DeepSeek) | deepseek-solo |
|---|---|---|---|
| flask-4992 (easy, `text` param) | ✓ | ✓ ($0.001) | ✗ (เดา `mode` ≠ gold API) |
| flask-5063 (harder, ~40L rewrite) | ✓ | ✓ ($0.003) | ✗ (FQDN semantics + always-on col + ไม่เพิ่ม sort choice) |

- **🔑 team-value = planner (Claude) inject spec-detail ที่ cheap-model เดาเองไม่ได้.** deepseek-solo fail เพราะเดา interface/format ผิด ไม่ใช่ logic. signal hold ทั้ง easy+harder.
- **patch-apply fixes DONE:** (1) whole-file→local-diff (`@@@FILE` markers + difflib, ฆ่า apply-fail confound; ทุก arm clean-apply). (2) clean instance flask-4992/5063 (hermetic, gold-validate PASS).
- **review-step protocol = light** (apply-check+sanity, ไม่ rewrite สิ่ง plan ระบุไม่ครบ) ไม่งั้น team=solo trivially.

**🔴 caveats (อย่าลืม):**
- **cost axis ยังไม่วัด.** oracle mode → claude-solo+team อ่าน oracle เท่ากัน → quota-delta marginal. EXISTENTIAL ตอบไม่ได้จน **agentic mode** (claude-solo loop แพง vs team plan-once→DeepSeek loop). `claude_tok=0` ทุก arm (ไม่ปลอม).
- N=2 เล็ก + flask public (contaminated) → absolute optimistic; **delta** อ่านได้.
- **whole-file ไม่ scale → FIXED ด้วย SEARCH/REPLACE blocks** (Aider-style, commit pending). โมเดลคืนเฉพาะ region ที่แก้ → apply locally (exact + trailing-ws flex + new-file) → diff locally (confound-kill เดิมคงอยู่). proof บน flask-5063 (cli.py 1050L ที่เคย stall): output **2457 tok vs 10626 whole-file = -77%**, 0 miss, fresh eval **resolved=True**. miss-tracking ใน ledger (`edit_misses`). ICM `01KVTVC8...` = closed.

**ctx-mode gate = FOLDED (not killed):**
- replay compliance = **8%** (20 ctx_/219 bulky). user: 8% = habit confound (Claude reflex Bash/Read) ไม่ใช่ tool อ่อน.
- hook-B booster = **rejected** — category Read 62%/Bash-other 17%/Web 12%/Grep 6%; hook บีบได้แค่ Bash ~17% < 30% gate; Read บีบ hook ไม่ได้ (read-to-edit verbatim). machinery ช่วยไม่ได้; ไม่มี portable hard-enforce (ชน #8).
- **decision: fold เข้า swe-work** (Read/log/diff-heavy = ctx-mode best case). route ctx_ ด้วยมือ 3-5 swe session → replay+ccusage → **terminal keep/kill** (best-case fail=kill เด็ดขาด · clear=keep). tax 7.9k/session bleed = ราคาของ clean read.

## E. cross-host verdict (harness ใช้ AI ตัวอื่น/DeepSeek ได้ไหม)

**harness วันนี้ = CC-only. cross-host = GOAL ยังไม่จริง.**
| component | mechanism | portable | DeepSeek |
|---|---|---|---|
| ICM | CLI | ✅ any shell | ✅ ถ้า runtime shell ได้ |
| context-mode | MCP | ✅ any MCP-client host | ⚠️ ต้องมี MCP-capable runtime |
| rtk/nah | CC hook | ❌ CC-only enforce | ❌ |
| routing block | CLAUDE.md | ⚠️ → AGENTS.md via rulesync | n/a |

- DeepSeek วันนี้ได้ harness = 0 (probe = bare API single-shot; "team" = Claude+harness ขับ bare DeepSeek).
- monthly subs (Claude/Codex/Gemini chat) = ไม่มี MCP/hook/CLI surface + programmatic seat = **ban risk** → interactive-by-hand. **DeepSeek = metered API = automate ปลอดภัย.**
- **DECISION (user): bench-now-wire-later.** ไม่ port harness ก่อนรู้ team คุ้ม. ให้ DeepSeek กิน harness ต้อง MCP-capable runtime (Cline/Codex/custom loop) = build รอ economics ผ่าน.

## F. OPEN / NEXT (resume จากตรงนี้)

1. ~~search/replace blocks~~ **DONE** (§D) — SR แทน whole-file, -77% output บนไฟล์ใหญ่, resolved hold. พร้อมขยาย N.
2. **N=5-10 quality axis** — flask Lite หมด (เหลือ 4045 messy) → repo hermetic อื่น (pylint/sqlfluff/sympy/sphinx), gold-validate ก่อน. ดู team≥solo & team>deepseek-solo hold.
3. **🔴 cost axis = agentic mode** — ออกแบบ arm claude-solo loop จริง vs team(plan→DeepSeek loop). = ที่ตอบ EXISTENTIAL จริง. record claude_tok + ccusage.
4. **ctx-mode compliance** หลัง 3-5 swe session → replay+ccusage → keep/kill.
5. **(parked)** H3 `paw link` skill/CLI (delivery undecided) · DeepSeek+harness runtime wiring · fork ③ เลือก Agyn/MASAI (รอ economics) · per-seat billing test (user-driven) · docs reframe ARCHITECTURE L0→L2.

## G. ASSUMPTION LEDGER (decay → recheck trigger)

- **ToS (load-bearing):** Anthropic billing whiplash (agent→credit paused June-16, "จะ revise"). programmatic บน Claude/Codex sub = ban-risk → interactive-only. DeepSeek/GLM metered = safe. → regime-agnostic, recheck on policy change.
- **DeepSeek:** `deepseek-chat/reasoner` deprecate **2026-07-24** → ใช้ `deepseek-v4-flash` ($0.14/$0.28 per M). Anthropic-compat endpoint `/anthropic` live. recheck price/endpoint.
- **context-mode ELv2:** ใช้/fork personal ฟรี; ห้าม hosted-service คู่แข่ง; license-key clause ยังไม่ active → recheck on version bump. bus-factor 1 (solo) → mitigant fork free-state.
- **ECC:** affaan-m/ECC ทำ harness layer 90% overlap (mature, user รันอยู่) → paw redundant as standalone harness; defensible = semantic-mem + measurement + team-axis. recheck if ECC adds vector memory.
- **agentmemory:** ceiling > ICM (LongMemEval R@5 95.2%) แต่ Windows out-of-box bm25-only (semantic dormant) → ICM ชนะ convenient. head-to-head full-mode = deferred.
- **headroom-ai:** Windows-BLOCKED (maturin/MSVC link.exe fail py3.14). recheck = prebuilt wheel/py≤3.13.
- **swebench:** `import resource` Unix-only → Windows native รันไม่ได้ → scorer ผ่าน WSL. py3.14 ไม่มี wheel `datasets`/`swebench` → puller ใช้ requests; scorer WSL pip.

## H. salvage state (paw build, deferred — primary = swe-probe ตอนนี้)

- repo `E:\portable-harness` (git). port-a-whip เก่า `~/.claude/port-a-whip` = source สำหรับ salvage write-path (patcher/healthcheck/install/runner/state).
- `paw sets list/show` ✓ (read-path lifted, 8 sets). write-path ยังไม่ port. `bundle/AGENTS.md` = canonical harness manual (link injection source).
- G5 locked: salvage portaw subtree staged (patcher = comment-preserving TOML + `_guard_unchanged` race-safe, lift verbatim ตอน MCP-set แรก; thin-rewrite REJECTED). MVP `link secure-agent` (0-MCP) = agents_md+runner+install+healthcheck+state+router-wiring.
- ติด `ECC adopt-all` (memory note 2026-06-24): ECC plugin = harness base, paw = residual overlay. ctx-mode compliance + prune/ROP/codex-migrate = pending ที่ note นั้น.
