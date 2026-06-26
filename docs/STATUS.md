# STATUS — session state (compact-survival)

> อัพเดท: 2026-06-26 · state ก้อนเดียวให้ session หลัง-compact resume ได้ครบ. **resume: อ่าน §0 (current truth) → §F (next) ก่อน.**
> Doc map: [CLAUDE.md](../CLAUDE.md) mindset+routing · [ARCHITECTURE.md](./ARCHITECTURE.md) blueprint · [SHARED-BRAIN.md](./SHARED-BRAIN.md) L0 · [BENCH.md](./BENCH.md) bench detail · **STATUS.md (นี่)** = current truth.
> ⚠️ ประวัติ handoff ละเอียด §1-16 (pre-pivot harness framing → ECC collision → fork → context-mode adopt → swe-probe round 1) = **condensed ลงนี่แล้ว**; กู้เต็มได้ที่ git ก่อน commit `71a2815`.

---

## 0. CURRENT TRUTH — authoritative

- **economics gate ผ่าน:** frozen SymPy N=8 = `team3 5/8 > codex-solo 4/8 > claude-solo 2/6 ≈ deepseek-solo 2/8`. Canonical manifest: `bench/swe_probe/FROZEN_N8_2026-06-25.json`; verify with `python bench/swe_probe/verify_freeze.py`.
- **router live:** `python -m paw route` — deterministic complexity/risk/privacy/budget/fallback policy + JSON contract; 14 tests, 91.3% statement coverage.
- **shared blackboard live:** `python -m paw blackboard write/read` — ICM topic `<project>/blackboard/<run-id>`, versioned/bounded/secret-safe; real isolated ICM SQLite round-trip passes.
- **Team Kernel v0 runtime + CLI live:** `paw.team_kernel.TeamKernel` executes RouteDecision-shaped Planner → Implementer → optional Mutator → Reviewer → evaluator/stop loops with bounded retries and blackboard handoffs. `python -m paw team run ... --mock --db <isolated.db>` proves real ICM write/read transport plus mock patch-artifact handoff. `--adapters codex-deepseek` wires Codex read-only plan/review + DeepSeek implementer handoff; it is explicit, route-guarded, and blocked for `--sensitivity restricted`.
- **portable claim:** decision + data protocol portable; execution and enforcement remain host-tiered. Do not claim uniform hooks/security.
- **release posture:** alpha/internal-beta only. README quickstart exists, but full public release still needs real patch/search-replace applier policy, cross-platform CI, and release docs.
- **next:** wire a real mutation runner for patch/search-replace artifacts and a focused verification runner; the kernel loop already feeds evaluator failures back into the next planner/implementer context without importing the frozen benchmark cohort.
- **benchmark is frozen:** do not append to the N=8 cohort. New repo/model/N requires a new dated cohort and manifest.

---

## A. IDENTITY — paw คืออะไร (locked 2026-06-22, §12 เดิม)

> **paw = personal, cross-host, shared-brain agent-team substrate** — ไม่ใช่ "harness แข่ง ECC".

- **#1 personal** → ride seat *ตัวเอง* interactive = defensible. **ห้าม ship/resell/OSS-arbitrage.** personal-tool, อย่า over-engineer เป็น product.
- **#2 coordination = B (shared-state/blackboard) + heterogeneous members** — แต่ละตัวมี brain+specialty เอง (Opus reason · DeepSeek/GLM bulk · Codex/Gemini ฯลฯ) แชร์ ICM blackboard. two-tier memory (shared + per-member private).
- **coordination ladder:** A task-handoff = table-stakes (ฟรี) · **B shared-state = moat (build)** · C mesh/role-protocol = commodity (LangGraph/AutoGen/ECC → rent, อย่าสร้าง = portaw รอบ 4).
- **L0 scope = thin + team-shaped:** สร้างเฉพาะ shared-brain(ICM) + cross-host wiring + seat-router. general-harness breadth (skills/instincts) = ECC ทำแล้ว → wrap/ปล่อย.
- **moat:** distro ตาย (ECC ทำแล้ว). moat จริง = personal cost/quota economics (ride seat) + agentic + shared-brain glue ที่ Fusion/ECC ไม่มี. L2-team value = **cost/quota ไม่ใช่ quality** (literature: solo ≥ team on quality compute-controlled).

## A2. HISTORICAL SCORECARD — superseded by §0

> Historical pre-benchmark snapshot retained for decision history. It is no longer current: heterogeneous team economics, router v0, and ICM blackboard v1 now exist.

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
| ③ team kernel | build the proven team3 contract first; evaluate Agyn/MASAI/AgentPool only from observed gaps |
| ④ wrap/interop | **ECC** (member รัน ECC เป็น L0; paw bridge บนนั้น) |
| ⑤ reference only | agentmemory(mem ceiling) · MoA(ensemble ref) · SWE-bench-Lite(task data) |

→ no framework fork yet. Build a small vertical slice first; rent/fork only when a concrete missing capability appears.

## C. LIVE env + components (what actually runs)

- **ICM 0.10.57** (`%LOCALAPPDATA%\icm\bin\icm.exe`) — semantic memory + paw blackboard backend, CLI=0-tax. ⚠️ PowerShell `icm`=Invoke-Command alias → เรียก `icm.exe`/full path.
- **rtk** — token-cut Bash-hook (global). บีบ git ดี แต่ workload นี้ rtk-able แค่ ~0.8% (Read 62% ครอง).
- **nah 0.9.1** — security guard PreToolUse (BLOCK curl|bash · ASK dual-use/rm-rf · ALLOW git_safe). dual-use→ASK ห้าม loosen.
- **context-mode MCP** (project-scoped `.mcp.json`, ELv2 local-first) — ctx_* 11 tools, +7.9k tok/session repo นี้. routing nudge block ใน CLAUDE.md. **gate = folded (§D).**
- **paw router + blackboard + team kernel** — route decision, shared-state, Team Kernel mock-smoke, and explicit Codex/DeepSeek adapter profile live. External adapter privacy guard blocks restricted/mismatched routes. Contract tests: 35 across router/blackboard/kernel/adapters.
- **swe-probe** `bench/swe_probe/` — frozen SymPy N=8 evidence; verifier runs without paid arms.
- WSL Ubuntu + swebench + Docker Desktop (flask env-image cached, eval ~1-2min). `$env:DEEPSEEK_API_KEY` set. ccusage 20.0.14 · tiktoken 0.13.0 · iii.exe PATH.
- **ECC plugin hooks** = 24 hooks (node-spawn ทุก tool-call, CC-locked). **DECISION 2026-06-25: `ECC_HOOK_PROFILE=minimal`** set ใน `~/.claude/settings.json` `env` (มีผล session หน้า). minimal = ตัด tier `standard` (gateguard fact-force, ecc-context-monitor cost-warning, quality-gate, console/design/doc warnings, suggest-compact) เก็บเฉพาะ minimal-tier (observe/metrics/cost-tracker/session-end = เงียบ, feed ICM). knob อื่น: `ECC_DISABLED_HOOKS=id,id` (surgical) · `ECC_GATEGUARD=off` (gate ตัวเดียว).

### ECC hook → harness mapping (ไม่ port — ส่วนใหญ่ harness มี cross-host แล้ว)

> เหตุผล: ECC hook = node-spawn/tool-call (per-turn tax, ขัด #7) + CC-locked (ขัด #8). ~80% ซ้ำของเดิม. **author-once-per-host idiom (rtk/nah/ICM pattern) > copy ECC bundle.**

| ECC hook | harness equivalent (cross-host) | verdict |
|---|---|---|
| config-protection · governance-capture | **nah** (BLOCK/ASK) + secure-agent (gitleaks/osv) | harness แข็งกว่า → skip |
| quality-gate · format-typecheck (Biome/tsc) | **ruff/mypy CLI** (0-tax, python) | skip (node→CLI) |
| cost-tracker · ecc-context-monitor | **ccusage + bench/** | skip (ECC cost=CC-only) |
| observe · evaluate-session · metrics-bridge | **ICM** (18-host learning, adopt-all bridge LIVE) | **keep ECC ON** (minimal เก็บไว้) = bridge เดียวที่ net-positive |
| session-start/end ctx | ICM session-hook + context-mode SessionStart | skip |
| console-warn · design-quality-check · doc-file-warning · desktop-notify | — (JS/frontend/macOS, irrelevant repo python) | skip |

**Residual (harness ยังไม่มี, gate ก่อนทำ):** (1) gateguard "investigate-before-mutate" — overlap mindset #9, low ROI; ถ้าเอา = gate เฉพาะ code-file load-bearing (ข้าม md/memory), opt-in. (2) scope-creep/tool-loop detector — signal มีค่าแต่ threshold+cross-host ยาก. **ทำเป็น per-host thin-hook ตาม enforce-tier (A=CC hook · B=Gemini init · C=Codex AGENTS.md) เท่านั้น ห้าม copy ECC node-bundle.** A2 gate: พิสูจน์ว่าขาดจริงก่อน polish.

## D. HISTORICAL BENCH LOG — frozen; canonical truth is §0 + manifest

> The log below records how the conclusion evolved. Do not resume its intermediate TODOs or append runs to this cohort.

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
- **cost axis: rig BUILT, team-side วัดแล้ว, solo-side ยัง.** agentic loop เสร็จ (`team-loop`: DeepSeek implement→eval→ป้อน test-fail feedback→retry, max-iter, per-attempt run_id ดอจ swebench cache). **ไม่ใช้ paid API** — Claude=seat นี้ (sub, $0 marginal), วัด quota ด้วย **tiktoken** (o200k, proxy symmetric → delta valid; `tokens.py`). first data flask-5063: team Claude quota = **8295 tok FIXED** (plan once in=7983/out=312, ไม่โตตาม iter) + DeepSeek $0.003/2-iter (iter1 fail→feedback→iter2 resolved ✓ = loop ได้ผลจริง). **เหลือ: claude-solo agentic by-hand** (loop seat: read+patch ทุก iter → claude_tok โตตาม iter) เทียบกับ team 8295-fixed = ตอบ EXISTENTIAL. accounting: `claude-tokens --in-file --out-file` (tiktoken นับ content จริงที่ผ่าน seat).
- N=2 เล็ก + flask public (contaminated) → absolute optimistic; **delta** อ่านได้.
- **whole-file ไม่ scale → FIXED ด้วย SEARCH/REPLACE blocks** (Aider-style, commit pending). โมเดลคืนเฉพาะ region ที่แก้ → apply locally (exact + trailing-ws flex + new-file) → diff locally (confound-kill เดิมคงอยู่). proof บน flask-5063 (cli.py 1050L ที่เคย stall): output **2457 tok vs 10626 whole-file = -77%**, 0 miss, fresh eval **resolved=True**. miss-tracking ใน ledger (`edit_misses`). ICM `01KVTVC8...` = closed.

**ctx-mode gate = FOLDED (not killed):**
- replay compliance = **8%** (20 ctx_/219 bulky). user: 8% = habit confound (Claude reflex Bash/Read) ไม่ใช่ tool อ่อน.
- hook-B booster = **rejected** — category Read 62%/Bash-other 17%/Web 12%/Grep 6%; hook บีบได้แค่ Bash ~17% < 30% gate; Read บีบ hook ไม่ได้ (read-to-edit verbatim). machinery ช่วยไม่ได้; ไม่มี portable hard-enforce (ชน #8).
- **decision: fold เข้า swe-work** (Read/log/diff-heavy = ctx-mode best case). route ctx_ ด้วยมือ 3-5 swe session → replay+ccusage → **terminal keep/kill** (best-case fail=kill เด็ดขาด · clear=keep). tax 7.9k/session bleed = ราคาของ clean read.

## E. HISTORICAL cross-host verdict — superseded by §0

**Historical pre-router statement:** runtime enforcement was CC-first. Current truth: router/blackboard protocol is portable, while execution/enforcement remains tiered.
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

**Current ordered next work:**

1. ~~Team Kernel v0 contract~~ **DONE 2026-06-26** — `paw.team_kernel.TeamKernel` runs Planner → Implementer → Reviewer → evaluator/stop with bounded retries, review-gated evaluation, explicit stop reasons, and blackboard handoffs. Adapter-injected only; no real agent launcher yet.
2. ~~Team Kernel CLI + isolated ICM smoke~~ **DONE 2026-06-26** — `python -m paw team run <task> --project <p> --run-id <r> --mock --db <isolated.db> --json` writes/reads real `<project>/blackboard/<run-id>` entries.
3. ~~Lift Codex/DeepSeek adapter contracts from `swe_probe`~~ **DONE 2026-06-26** — `paw.team_adapters` has Codex read-only CLI planner/reviewer (`codex exec --json -o`) and DeepSeek Anthropic-compatible implementer (`/v1/messages`, `$DEEPSEEK_API_KEY`). Claude is intentionally not in the default runtime path; keep it as optional benchmark/comparison only.
4. ~~Privacy guard + alpha quickstart~~ **DONE 2026-06-26** — `codex-deepseek` is blocked for restricted work and route mismatch before adapter construction; README documents mock smoke, real adapter env, and host-tiered caveats.
5. ~~Mutation/evaluation layer v0~~ **DONE 2026-06-26** — Team Kernel supports an injected `mutation_runner` after implementer handoff, records mutator artifacts in the blackboard/result, runs focused verification via evaluator, and feeds evaluator failures into the next planner/implementer context. Mock CLI emits a deterministic patch artifact; real patch/search-replace applier remains next.
6. Add Linux/macOS CI for router + blackboard + Team Kernel; Windows is already live.
7. Implement `paw link/verify/unlink` after the Team Kernel contract settles.
8. Optional later benchmark work must use a new dated cohort.

> Everything below in §F is a historical backlog retained for provenance; do not resume it over the ordered list above.

1. ~~search/replace blocks~~ **DONE** (§D) — SR แทน whole-file, -77% output บนไฟล์ใหญ่, resolved hold. พร้อมขยาย N.
2. **N=5-10 quality axis** — flask Lite หมด (เหลือ 4045 messy) → repo hermetic อื่น (pylint/sqlfluff/sympy/sphinx), gold-validate ก่อน. ดู team≥solo & team>deepseek-solo hold.
3. **cost axis = agentic mode** — rig DONE + team-side วัดแล้ว (§D, no paid API/tiktoken). **เหลือ claude-solo agentic by-hand**: loop seat (read oracle+เขียน patch→eval→อ่าน `feedback`→แก้ ทุก iter, per-attempt arm `claude-solo__a<k>`) → `claude-tokens` นับ in/out จริง → เทียบ team 8295-fixed. ถ้า solo claude_tok >> team & resolved ≈ → team ชนะ quota = ตอบ EXISTENTIAL.
4. **🟢 BENCH v2 (Codex = member จริงตัวที่ 2, sub-seat verified §G) — codex-solo SHIPPED + first data.** `codex.py` adapter BUILT (`codex.generate_patch`→stage oracle repo→`codex exec`→git diff→real usage+turns), `codex-solo` arm wired (`run codex-solo <id>`→`eval <id> codex-solo`), report ยกเครื่องเป็น cost-axis cols (**out_tok + turns**, iterate present arms). **first measurement codex-solo flask-5063 = resolved ✓** (out 4469 / reason 1073 / **17 turns** / in 510k cacheable; deepseek-solo ✗ ตรงนี้ → codex = solo member เก่งจริง). **cost signal:** team ✓ (claude plan 2769 out, **2 turns**, deepseek $0.003) ชนะ codex-solo ✓ (4469 out, 17 turns) บน premium-seat burn ทั้งๆที่ resolved เท่ากัน — heterogeneous team ผ่อง agentic-loop ออกจาก premium seat ไป metered DeepSeek = signal EXISTENTIAL ครั้งแรกกับ member จริง (ไม่ใช่ 2 Claude-arms). **💵 MONEY AXIS เพิ่มแล้ว (user challenge: out-tok อย่างเดียว=rate-limit axis ไม่ใช่เงิน):** report มี `api_usd` col = ทุก member's **in+out+reasoning × API list-rate** (สกุลเดียว; sub seat ตีที่ opportunity-cost ไม่ใช่ $0 marginal — ไม่งั้น seat=$0 แล้ว team ที่บวก DeepSeek cents ดูแพงกว่า solo "ฟรี" หลอก). `config.PRICING`+`config.usd()`; rate verified §G. **flask-5063 (ทั้งคู่ ✓): team $0.0497 vs codex-solo $0.6929 = ~14× ถูกกว่า** — money axis เปิดโปงว่า codex **input 510k agentic-read × $1.25 = $0.64 ครองต้นทุน** (out-tok ซ่อนไว้; user ถูก). claude-solo = **n/a** (unmeasured by-hand → โชว์ n/a ไม่ใช่ $0 หลอก). ⚠️ caveat credibility: N=1 + flask public · claude $=**floor** (tiktoken ไม่นับ thinking) · codex input ไม่หัก cache (=upper bound, จริง ~$0.45) · turns ไม่ apple-to-apple (codex=shell-cmd+explore vs team=eval-iter) · rate=list snapshot (codex อาจ 5.2/5.3 $1.75/$14 → ยิ่งเสริม). **direction robust, magnitude นุ่ม + claude-solo gap เปิด. เหลือ:** generalize `team-loop` → `--planner {claude,codex}` `--implementer {deepseek,codex,claude}` (codex-plan→deepseek · claude-plan→codex) + **hard instances** (sympy/sphinx/pylint, gold-validate; flask ง่าย=inconclusive) + claude-solo by-hand out-tok (§F.3).
   - **codex.py recipe (IMPLEMENTED 2026-06-24, `bench/swe_probe/codex.py`):** temp dir → เขียน oracle_files → `git init+commit` (base) → `codex exec -C <dir> -s workspace-write --skip-git-repo-check --json -` → patch = `git diff -- <gold paths>` (restrict กัน codex scratch files) → **usage = event สุดท้าย `turn.completed.usage`** (output_tokens = scarce-axis) → turns = นับ `item.completed` ที่ `item.type==command_execution` (flask-5063 = 17). ⚠️ **Windows gotchas (แก้แล้ว):** (1) npm `codex` = ไม่มี ext → `subprocess([... ])` bare = **WinError 2** (CreateProcess ไม่ apply PATHEXT) → ต้อง `shell=True` ให้ cmd.exe หา `codex.cmd`. (2) prompt ส่งผ่าน **stdin (`-`)** ไม่ใช่ argv → กัน cmdline-length/quoting + ให้ interpolate แค่ temp-dir path. exit 0 ✓ diff ✓ usage ✓ resolved ✓ บน flask-5063.
4b. **🟢 team3 (real 3-role team) SHIPPED — RESUME RUN-PLAN (post-compact, user: medium N=5-6).** code commit `3b29deb`: `team3` arm = Planner→Implementer→Reviewer loop + blackboard (Planner+Reviewer=**Codex** read-only `codex exec -o`, Implementer=**DeepSeek**); reviewer GATES ก่อน eval (REVISE→re-impl no-eval, PASS→eval, eval-fail→feed test+review back). แก้ critique เดิม: `team` เก่า=handoff บางๆ ไม่ใช่ teamwork → ลำเอียง. + `codex.generate_plan/review`, `codex-impl` cmd (claude-plan-codex), matrix arms, pull retry+cache. **6 sympy instances pulled+committed** (13031/13177/13437/13647/13895/13915); gold-validate รันค้าง background log `bench/swe_probe/_goldval.log`. **รัน (post-compact):** (1) `tail _goldval.log` → เก็บเฉพาะ instance ที่ PASS (env trustworthy), ทิ้ง FAIL. (2) shell loop ต่อ instance ที่ผ่าน: `deepseek-solo <id>`+`eval <id> deepseek-solo` · `codex-solo <id>`+`eval <id> codex-solo` · `team3 <id>` (self-eval ใน loop). (3) **claude-solo baseline (ผม=seat, BLIND — อ่านแค่ problem+oracle_files ห้ามแตะ gold_patch):** author patch→`claude-patch <id> claude-solo --file p.diff`→`claude-tokens <id> claude-solo --in-file ... --out-file p.diff`→`eval <id> claude-solo`. (4) `report` → resolution + api_usd ข้าม arm × N. ⚠️ codex รอบ plan+review+impl = แพง $/instance; ดู team3 vs codex-solo vs claude-solo บน resolution & api_usd.
4c. **🟢🟢 N=8 sympy bench DONE (2026-06-25) — thesis ผ่าน, team3 ชนะจริง.** gold-validate: 13031/13437/13647/13895/13915 PASS (13177 FAIL→ทิ้ง) + ขยาย 11400/11870/11897. arms ครบ (claude-solo by-hand BLIND, deepseek/codex/team3 automated). **resolved: team3 5/8 ≥ codex-solo 4/7 > claude-solo 2/5 ≈ deepseek-solo 2/8.** (1) **team3 ≥ best solo** — decider 11400 (codex-solo เอา diff ไม่ออก/tooling-fail, team3 ✓⚠️asterisk). (2) **ยก deepseek อ่อน 3 ครั้ง** (13031/13915/11400 deepseek✗→team3✓). (3) **cost พลิกเข้าข้าง team3 บน hard** — codex-solo agentic-impl เผา turns (13915=24t→$.85·11870=13t→$1.84) vs team3 codex แค่ plan+review(read-only สั้น)+deepseek impl ถูก → 13915 team3 $.78<codex$.85 · 11870 $.85<$1.84. (N=5 ที่ว่า "team แพงกว่า" = easy-instance artifact, แก้แล้ว). (4) team3 ไม่กิน premium Claude seat เลย. (5) 13437/11870/11897 = hard จริง ไม่มีใครแก้. **→ heterogeneous team (codex-brain+deepseek-hands) ≥ best solo บน resolution + cost ≈/ดีกว่า + premium-seat-free.** caveat: N=8/1-repo/single-shot · claude$=floor · codex input ไม่หัก cache · 11400 codex asterisk. ผล: `bench/swe_probe/_report.txt`. **เหลือ:** backfill 11400 codex-solo (clean head-to-head) · ขยาย N/repo อื่น (sphinx/pylint) · `powercfg /change standby-timeout-dc 30` (revert sleep-disable). ⚠️ Docker stale-socket recovery on hard-poweroff → memory [[docker-stale-socket-recovery]].
4d. **🟢🟢🟢 11400 head-to-head backfilled (2026-06-25) — asterisk หาย, thesis แข็งขึ้น.** codex-solo 11400 rerun = patch ออกจริง 624B/22 turns (empty-diff รอบเก่า = transient ไม่ใช่ขีดจำกัด) → **codex-solo ✗ แบบ fair** (ไม่ใช่ tooling-fail). claude-solo 11400 author BLIND = ✗ เช่นกัน. **ทั้ง codex-solo + claude-solo พลาดเหมือนกัน**: blind single-shot ใส่แค่ `_print_sinc`, ไม่ใส่ `_print_Relational` → cond `Ne(x,0)` พิมพ์ผิด (ต้อง `x != 0`) → fail `test_ccode_Relational`+`test_ccode_sinc`. **team3 ✓** เพราะ revise loop (3 iters, codex review จับ Ne→`!=`) เพิ่ม `_print_Relational` ที่ทั้งสอง solo มองไม่เห็น single-shot. **decider 11400 = team-iteration ชนะของจริง**: strong solo สองตัวล้ม 1-shot, team แก้ผ่าน feedback loop — + ถูกกว่าด้วย (team3 $0.968 < codex $1.014). **corrected sympy tally: team3 5/8 > codex-solo 4/8 > claude-solo 2/6 ≈ deepseek-solo 2/8** (11400 codex เป็น fair ✗ → codex 4/7→4/8). ผล: `bench/swe_probe/_report.txt` (uncommitted). **เหลือจริง:** ขยาย N/repo (sphinx/pylint) เมื่อต้องการ N ใหญ่ · `powercfg /change standby-timeout-dc 30` (revert).
5. **ctx-mode compliance** หลัง 3-5 swe session → replay+ccusage → keep/kill.
5. **(parked)** H3 `paw link` skill/CLI (delivery undecided) · DeepSeek+harness runtime wiring · fork ③ เลือก Agyn/MASAI (รอ economics) · per-seat billing test (user-driven) · docs reframe ARCHITECTURE L0→L2.

## G. ASSUMPTION LEDGER (decay → recheck trigger)

- **ToS (load-bearing):** Anthropic billing whiplash (agent→credit paused June-16, "จะ revise"). programmatic บน **Claude** sub = ban-risk → interactive-only. DeepSeek/GLM metered = safe.
- **Codex ToS = VERIFIED PERMITTED (2026-06-24, flip จากเดิม)** — เดิมเหมา Anthropic-policy ใส่ Codex ผิด. OpenAI ship `codex exec` เพื่อ CI/scripting โดยตรง (automation = intended); ChatGPT-sub auth ใช้ automate ได้ (docs discouraged→แนะนำ API key, "treat auth.json like password", "อย่าใช้ public-repo CI" = กัน secret รั่ว ไม่ใช่ห้าม). **ไม่มี clause ห้าม programmatic.** local/personal (auth.json ไม่รั่ว) = ผ่าน. usage กิน plan agentic limit (5h+weekly) = scarce-axis ที่จะวัด. recheck on OpenAI policy change. [src: developers.openai.com/codex/noninteractive · help.openai.com/articles/11369540]
- **DeepSeek:** `deepseek-chat/reasoner` deprecate **2026-07-24** → ใช้ `deepseek-v4-flash` ($0.14/$0.28 per M). Anthropic-compat endpoint `/anthropic` live. recheck price/endpoint.
- **API-equiv pricing (cost-axis $, load-bearing, verified 2026-06-24):** `config.PRICING` per-1M = Claude Opus 4.8 std **$5/$25** · gpt-5-codex **$1.25/$10** · DeepSeek v4-flash **$0.14/$0.28**. ใช้ตี opportunity-cost ของ sub seat (marginal จริง=$0) ให้สกุลเดียว. ⚠️ codex model version ไม่ชัด (5.2/5.3 = $1.75/$14 → codex แพงขึ้น) · cached-input ไม่หักส่วนลด (upper bound) · Claude tiktoken = floor. recheck on price/model-version change. [src: platform.claude.com/docs pricing · help.openai.com/articles/20001106 codex rate-card]
- **context-mode ELv2:** ใช้/fork personal ฟรี; ห้าม hosted-service คู่แข่ง; license-key clause ยังไม่ active → recheck on version bump. bus-factor 1 (solo) → mitigant fork free-state.
- **ECC:** affaan-m/ECC ทำ harness layer 90% overlap (mature, user รันอยู่) → paw redundant as standalone harness; defensible = semantic-mem + measurement + team-axis. recheck if ECC adds vector memory.
- **agentmemory (rohitg00 / `@agentmemory/agentmemory`):** RE-VETTED 2026-06-26 — old "bm25-only" note STALE. now ships local MiniLM + hybrid BM25+vector+graph RRF, built-in 12-hook auto-capture+LLM-compress, 1423 tests, 24k★, v0.9.27. ceiling 95.2% R@5. **NOT adopted — durable reason = daemon-centric** (iii-engine + ports 3111/3113/49134, no one-shot CLI recall) ชน lean/stateless/portable thesis. its one win (auto-capture) rebuildable on ICM cheaper. recheck → multi-agent team (concurrent shared live mem) flips it. full plan: [[docs/MEMORY-PLAN.md]].
- **MEMORY PLAN locked 2026-06-26** → `docs/MEMORY-PLAN.md`. keep ICM (struct verified, maps to Mem0 ADD/UPDATE/DELETE/NOOP). behavioral layer = the real work: reflection-pass (episodic→semantic distill, host-uniform dedicated model TBB), push+pull recall (`paw recall` CLI floor + paw_block push, LIVE), Stop-capture→`pending`→SessionStart-curate, suggest-graduate to skills. **Phase 0 done:** CC Stop has `transcript_path` (JSONL parseable); **Codex Stop/SessionStart ALSO dead portaw** (`portaw memory capture/session-hook`) — migration gap both hosts; Codex transcript schema TBV. seq: 0→1→6(migrate 46 stranded lessons+retire ~/.paw+fix CLAUDE.md lie)→2→3→4(bench)→5.
- **headroom-ai 0.27.0:** §BENCH 2a CLOSED. Windows ยัง BLOCKED เพราะไม่มี
  wheel (Python 3.12/3.14 ต่าง fallback maturin → `link.exe` fail); Linux Docker
  รันได้. SmartCrusher JSON -41.9% ที่ 11–26ms/semantic sentinels held.
  Full proxy เพิ่ม RTK อีก -23.2% บน saved mix แต่ latency 0.3–1.8s/fixture
  (build-log 11.9s) + config/MCP/memory overlap → **optional JSON L2 only,
  ไม่ wrap/proxy default**. recheck = upstream Windows wheel + latency release.
- **swebench:** `import resource` Unix-only → Windows native รันไม่ได้ → scorer ผ่าน WSL. py3.14 ไม่มี wheel `datasets`/`swebench` → puller ใช้ requests; scorer WSL pip.

## H. implementation state

- repo `E:\portable-harness` (git). port-a-whip เก่า `~/.claude/port-a-whip` = source สำหรับ salvage write-path (patcher/healthcheck/install/runner/state).
- `paw sets list/show` ✓ (**14 sets**) · `paw route` ✓ · `paw blackboard write/read` ✓.
- **write-path LANDED (slice-0, 2026-06-26):** `paw plan|apply|verify|remove <set>` ✓ end-to-end for **10 CLI-only sets** (secure-agent · design-quality · browser-automation · data-query · doc-extract · harness-foundation · repo-pack · test-affected · quality-gate · api-quality). drift-guard + backup + `.paw/state.json` ledger + reversible remove, all live-proven (`paw apply repo-pack`→inject+backup, verify=healthy, remove→original). **binary resolution = PATH → vendored `bin/` → MISSING+OS-install-cmd** (`resolve_binary`/`install_command`); vendored `bin/code2prompt.exe` 4.2.0 resolves healthy. injected block carries usage+install lines. 63 tests green.
- **slice-1 LANDED (MCP merge, JSON hosts, 2026-06-26):** all **14 sets plan OK on claude-code**. MCP wiring merges into project-local `.mcp.json` (CC) / `.gemini/settings.json` (Gemini) via stdlib json — `merge_mcp_servers`/`remove_mcp_servers` (idempotent, preserves sibling servers, ledger `mcp_wiring.prior` for precise reverse). **host_anchor honored** (efficiency-starter → codegraph on CC, semble on gemini; XOR enforced, only wired tool's binary detected). **N1 ceiling warn** when union >3. live-proven: context-quality merge context7 beside `keep-me` → verify healthy → remove restores. binary detection now covers MCP tools (codegraph/uvx/context-mode). 77 tests green.
- **slice-1b LANDED (Codex TOML MCP, 2026-06-26):** MCP sets wire on `--host codex` now. Comment-preserving merge into `.codex/config.toml` `[mcp_servers.<name>]` via **tomlkit** (`_merge_mcp_toml`/`_remove_mcp_toml`); format-aware dispatch by suffix (`mcpServers` JSON ⇄ `mcp_servers` TOML). live-proven: context-quality → `[mcp_servers.context7]`+nested `.env` added, **header+inline comments + github stub preserved**, verify healthy, remove restores. semble anchor picked on codex (XOR). N1 excludes `enabled=false` stubs. TOML never unlinks file (holds user state). guard: tomlkit absent → BLOCK "install port-a-whip[cli]". 82 tests green. **linker MCP now complete on all 3 hosts (CC/gemini JSON + codex TOML).**
- **router cross-host FIXED (2026-06-26, env wiring not repo):** Codex `~/.codex/config.toml` UserPromptSubmit hook repointed from dead `portaw router run --host codex` → `py "~/.claude/hooks/skill-router.py"` (same paw.skill_router engine as CC; script already scans `~/.codex/skills`+ECC). Codex re-trusted new hash. **both hosts now run one router engine.** memory/sets surfacing bridge REBUILT in repo: **`paw/router_block.py`** `paw_block(prompt,cwd,session_id)` — (1) curated-set match by trigger_terms (lexical, 0 subprocess, floor 2.0, `· paw apply <set>` verb), (2) ICM mistake recall gated by **keyword-overlap + importance∈{high,critical}** (ICM has no score cutoff → local post-filter kills noise; verified stays silent on non-overlapping lessons). fail-silent → '' (hook never breaks). 9 tests. **⚠️ MANUAL STEP (nah blocks me editing hooks):** change `~/.claude/hooks/skill-router.py` line ~151 import `portaw.adapters.router` → `paw.router_block`. paw importable under bare `py` (editable). one script shared by CC+Codex → fixes both. After edit: 🐾 sets + 🧠 memory auto-surface live again on both hosts.
- **PATH wiring (2026-06-26):** `apply` of a set with a vendored `bin/` binary prepends `bin/` to PATH in machine-local `.claude/settings.local.json` (gitignored → repo stays portable; CC `env` is literal/no-expand so a full PATH snapshot is written), reversible via ledger. lets vendored tools run by bare name in CC Bash subprocesses. ⚠️ snapshot can age (new tool dirs added later not seen) — local + reversible, acceptable.
- router: 14 tests / 91.3% statement coverage. blackboard: real isolated ICM integration; full suite 23 tests.
- G5 locked: salvage portaw subtree staged (patcher = comment-preserving TOML + `_guard_unchanged` race-safe, lift verbatim ตอน MCP-set แรก; thin-rewrite REJECTED). MVP `link secure-agent` (0-MCP) = agents_md+runner+install+healthcheck+state+router-wiring.
- ติด `ECC adopt-all` (memory note 2026-06-24): ECC plugin = harness base, paw = residual overlay. ctx-mode compliance + prune/ROP/codex-migrate = pending ที่ note นั้น.
