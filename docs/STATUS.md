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
- **cost axis: rig BUILT, team-side วัดแล้ว, solo-side ยัง.** agentic loop เสร็จ (`team-loop`: DeepSeek implement→eval→ป้อน test-fail feedback→retry, max-iter, per-attempt run_id ดอจ swebench cache). **ไม่ใช้ paid API** — Claude=seat นี้ (sub, $0 marginal), วัด quota ด้วย **tiktoken** (o200k, proxy symmetric → delta valid; `tokens.py`). first data flask-5063: team Claude quota = **8295 tok FIXED** (plan once in=7983/out=312, ไม่โตตาม iter) + DeepSeek $0.003/2-iter (iter1 fail→feedback→iter2 resolved ✓ = loop ได้ผลจริง). **เหลือ: claude-solo agentic by-hand** (loop seat: read+patch ทุก iter → claude_tok โตตาม iter) เทียบกับ team 8295-fixed = ตอบ EXISTENTIAL. accounting: `claude-tokens --in-file --out-file` (tiktoken นับ content จริงที่ผ่าน seat).
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
3. **cost axis = agentic mode** — rig DONE + team-side วัดแล้ว (§D, no paid API/tiktoken). **เหลือ claude-solo agentic by-hand**: loop seat (read oracle+เขียน patch→eval→อ่าน `feedback`→แก้ ทุก iter, per-attempt arm `claude-solo__a<k>`) → `claude-tokens` นับ in/out จริง → เทียบ team 8295-fixed. ถ้า solo claude_tok >> team & resolved ≈ → team ชนะ quota = ตอบ EXISTENTIAL.
4. **🟢 BENCH v2 (Codex = member จริงตัวที่ 2, sub-seat verified §G) — codex-solo SHIPPED + first data.** `codex.py` adapter BUILT (`codex.generate_patch`→stage oracle repo→`codex exec`→git diff→real usage+turns), `codex-solo` arm wired (`run codex-solo <id>`→`eval <id> codex-solo`), report ยกเครื่องเป็น cost-axis cols (**out_tok + turns**, iterate present arms). **first measurement codex-solo flask-5063 = resolved ✓** (out 4469 / reason 1073 / **17 turns** / in 510k cacheable; deepseek-solo ✗ ตรงนี้ → codex = solo member เก่งจริง). **cost signal:** team ✓ (claude plan 2769 out, **2 turns**, deepseek $0.003) ชนะ codex-solo ✓ (4469 out, 17 turns) บน premium-seat burn ทั้งๆที่ resolved เท่ากัน — heterogeneous team ผ่อง agentic-loop ออกจาก premium seat ไป metered DeepSeek = signal EXISTENTIAL ครั้งแรกกับ member จริง (ไม่ใช่ 2 Claude-arms). **💵 MONEY AXIS เพิ่มแล้ว (user challenge: out-tok อย่างเดียว=rate-limit axis ไม่ใช่เงิน):** report มี `api_usd` col = ทุก member's **in+out+reasoning × API list-rate** (สกุลเดียว; sub seat ตีที่ opportunity-cost ไม่ใช่ $0 marginal — ไม่งั้น seat=$0 แล้ว team ที่บวก DeepSeek cents ดูแพงกว่า solo "ฟรี" หลอก). `config.PRICING`+`config.usd()`; rate verified §G. **flask-5063 (ทั้งคู่ ✓): team $0.0497 vs codex-solo $0.6929 = ~14× ถูกกว่า** — money axis เปิดโปงว่า codex **input 510k agentic-read × $1.25 = $0.64 ครองต้นทุน** (out-tok ซ่อนไว้; user ถูก). claude-solo = **n/a** (unmeasured by-hand → โชว์ n/a ไม่ใช่ $0 หลอก). ⚠️ caveat credibility: N=1 + flask public · claude $=**floor** (tiktoken ไม่นับ thinking) · codex input ไม่หัก cache (=upper bound, จริง ~$0.45) · turns ไม่ apple-to-apple (codex=shell-cmd+explore vs team=eval-iter) · rate=list snapshot (codex อาจ 5.2/5.3 $1.75/$14 → ยิ่งเสริม). **direction robust, magnitude นุ่ม + claude-solo gap เปิด. เหลือ:** generalize `team-loop` → `--planner {claude,codex}` `--implementer {deepseek,codex,claude}` (codex-plan→deepseek · claude-plan→codex) + **hard instances** (sympy/sphinx/pylint, gold-validate; flask ง่าย=inconclusive) + claude-solo by-hand out-tok (§F.3).
   - **codex.py recipe (IMPLEMENTED 2026-06-24, `bench/swe_probe/codex.py`):** temp dir → เขียน oracle_files → `git init+commit` (base) → `codex exec -C <dir> -s workspace-write --skip-git-repo-check --json -` → patch = `git diff -- <gold paths>` (restrict กัน codex scratch files) → **usage = event สุดท้าย `turn.completed.usage`** (output_tokens = scarce-axis) → turns = นับ `item.completed` ที่ `item.type==command_execution` (flask-5063 = 17). ⚠️ **Windows gotchas (แก้แล้ว):** (1) npm `codex` = ไม่มี ext → `subprocess([... ])` bare = **WinError 2** (CreateProcess ไม่ apply PATHEXT) → ต้อง `shell=True` ให้ cmd.exe หา `codex.cmd`. (2) prompt ส่งผ่าน **stdin (`-`)** ไม่ใช่ argv → กัน cmdline-length/quoting + ให้ interpolate แค่ temp-dir path. exit 0 ✓ diff ✓ usage ✓ resolved ✓ บน flask-5063.
5. **ctx-mode compliance** หลัง 3-5 swe session → replay+ccusage → keep/kill.
5. **(parked)** H3 `paw link` skill/CLI (delivery undecided) · DeepSeek+harness runtime wiring · fork ③ เลือก Agyn/MASAI (รอ economics) · per-seat billing test (user-driven) · docs reframe ARCHITECTURE L0→L2.

## G. ASSUMPTION LEDGER (decay → recheck trigger)

- **ToS (load-bearing):** Anthropic billing whiplash (agent→credit paused June-16, "จะ revise"). programmatic บน **Claude** sub = ban-risk → interactive-only. DeepSeek/GLM metered = safe.
- **Codex ToS = VERIFIED PERMITTED (2026-06-24, flip จากเดิม)** — เดิมเหมา Anthropic-policy ใส่ Codex ผิด. OpenAI ship `codex exec` เพื่อ CI/scripting โดยตรง (automation = intended); ChatGPT-sub auth ใช้ automate ได้ (docs discouraged→แนะนำ API key, "treat auth.json like password", "อย่าใช้ public-repo CI" = กัน secret รั่ว ไม่ใช่ห้าม). **ไม่มี clause ห้าม programmatic.** local/personal (auth.json ไม่รั่ว) = ผ่าน. usage กิน plan agentic limit (5h+weekly) = scarce-axis ที่จะวัด. recheck on OpenAI policy change. [src: developers.openai.com/codex/noninteractive · help.openai.com/articles/11369540]
- **DeepSeek:** `deepseek-chat/reasoner` deprecate **2026-07-24** → ใช้ `deepseek-v4-flash` ($0.14/$0.28 per M). Anthropic-compat endpoint `/anthropic` live. recheck price/endpoint.
- **API-equiv pricing (cost-axis $, load-bearing, verified 2026-06-24):** `config.PRICING` per-1M = Claude Opus 4.8 std **$5/$25** · gpt-5-codex **$1.25/$10** · DeepSeek v4-flash **$0.14/$0.28**. ใช้ตี opportunity-cost ของ sub seat (marginal จริง=$0) ให้สกุลเดียว. ⚠️ codex model version ไม่ชัด (5.2/5.3 = $1.75/$14 → codex แพงขึ้น) · cached-input ไม่หักส่วนลด (upper bound) · Claude tiktoken = floor. recheck on price/model-version change. [src: platform.claude.com/docs pricing · help.openai.com/articles/20001106 codex rate-card]
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
