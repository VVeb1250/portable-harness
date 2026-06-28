# Shared BRAIN (L0 Substrate)

> สถานะ: **ICM-direct + blackboard v1 implemented** · **UPDATED 2026-06-25**.
> เจ้าของ: supimol.web@gmail.com · mindset: [../CLAUDE.md](../CLAUDE.md) · คู่กับ: [ARCHITECTURE.md](./ARCHITECTURE.md)
> ขอบเขต = **Layer 0 (shared brain) เท่านั้น**. cockpit = L1, team = L2.

---

## 0. สรุป (บรรทัดเดียว)

**Shared BRAIN = `ICM` (memory) + `RTK` (token-cut, tool layer) + curated tool bundle + `AGENTS.md` (instructions).**
**`ICM` ยืนเองได้ ไม่ต้องพึ่ง portaw** — `icm init` เสียบเข้าทุก host เอง. portaw (โปรเจกต์ตัวเอง, **archived**) = optional overlay ใช้ opportunistically, **อย่า hinge**.

> ไม่ใช่ "seamless model-access" (vendor บล็อก + คนอื่นทำแล้ว) — แต่ "seamless substrate ใต้ agent" = ToS-immune, policy-immune, ของเรา.

**Parallel-memory v0:** L0 now has a small explicit coordination plane via
`python -m paw memory ...`. If Claude, Codex, Gemini, DeepSeek, and other
sessions are open at once, they can register/heartbeat, post to shared or
per-member private lanes, promote private notes to shared memory, poll from a
cursor, and claim TTL write-intent locks. This is **poll-based coordination**,
not full orchestration: no hidden agent spawn, no true push notification, and
no cross-machine transport yet.

---

## 1. Foundation = ICM (standalone)

[rtk-ai/icm](https://github.com/rtk-ai/icm) — "Permanent memory for AI agents. Single binary, zero deps, MCP-native." (ตระกูลเดียวกับ RTK)

- **multi-host เอง:** `icm init` default = **`standard` = cli + skill + hook, NO MCP** → inject CLAUDE.md/AGENTS.md instructions + slash-cmd + hook ต่อ host (MCP opt-in `--mode mcp/all`). **→ ICM ผ่าน CLI = 0 tool-def tax** (N1-safe). **ไม่ต้องมี portaw.** ⚠️ v0.10.53: host auto-detect อาจ miss ("not detected") → fallback = CLI bridge ผ่าน CLAUDE.md instruction (STATUS §C).
- **store เดียว ใช้ร่วม:** SQLite local เดียว (`%APPDATA%\Roaming\icm\icm\data\memories.db`); CLI + (opt) MCP เข้าตัวเดียวกัน → host เขียน → host อื่นอ่านเจอ. นี่คือ durable shared persistence; `paw memory` เพิ่ม near-live coordination plane ข้าง ๆ.
- **CLI:** `icm store -t <topic> -c "<content>" -i <critical|high|medium|low> -k "<kw>"` · `icm recall "<q>"` · `icm forget <id>` · `icm consolidate` · `icm topics`.
- **governance ในตัว:** decay by importance (critical=ไม่ลบ), dedup >85% similar = update ไม่ซ้ำ.
- **privacy win:** local-only, ไม่มี network write → code/memory ไม่ออกนอกเครื่อง. (คนละเรื่องกับ model-routing ไป GLM = risk ที่ L1)
- สถานะเครื่องนี้: **LIVE v0.10.57** (store/recall + isolated blackboard round-trip verified). ⚠️ PowerShell เรียก `icm.exe` (`icm`=Invoke-Command alias).

### Shared blackboard v1

paw owns only the protocol glue; ICM owns persistence/search/dedup.

- namespace: `<project>/blackboard/<run-id>`
- entry kinds: `plan`, `handoff`, `observation`, `review`, `decision`, `result`, `blocker`
- payload: versioned JSON (`paw-blackboard/v1`) with role, kind, content, and optional artifact reference
- writes are explicit; no transcript/tool-output dumping
- reads are bounded (`limit <= 50`) and keyword-oriented
- secret-like content is rejected before invoking ICM
- `--db` supports isolated CI/tests without touching the user's configured memory
- for near-live multi-session work, pair this with `paw memory poll`: blackboard
  is durable handoff; memory mesh is peer registry, cursor, lanes, and locks

### Parallel memory mesh v0

`paw memory` is the live coordination layer for multiple local AI sessions.

```powershell
python -m paw memory register --project portable-harness --run-id demo `
  --member codex-1 --host codex --role planner
python -m paw memory post --project portable-harness --run-id demo `
  --member codex-1 --lane private --kind observation --content "scratch finding"
python -m paw memory promote --project portable-harness --run-id demo `
  --member codex-1 --seq 2
python -m paw memory poll --project portable-harness --run-id demo `
  --member claude-1 --since 0
python -m paw memory lock-acquire --project portable-harness --run-id demo `
  --name files-paw --owner codex-1 --purpose "editing paw memory code"
```

State is local and explicit under `~/.paw/state/memory-mesh` by default. Use
`--state-dir` for tests or isolated experiments. The mesh never stores
secret-like content and uses short-lived locks so a dead session does not block
the run forever.

### Hook shim

The reliability layer is `paw memory hook`: a tiny host-agnostic shim that
registers/heartbeats the current session, polls new mesh events since the
member's cursor, and injects only a short summary when something changed.

```powershell
python -m paw memory install-hooks --host all
```

Installs add-only hooks for:
- Claude Code: `~/.claude/settings.json`
- Codex: `~/.codex/hooks.json`

Events wired:
- `SessionStart` → register + poll
- `UserPromptSubmit` → heartbeat + poll
- `Stop` → heartbeat only

The hook does not dump transcripts, does not spawn agents, and does not write to
ICM. It only uses the local memory mesh state and returns an additional-context
block when there are new shared/private events or relevant locks.

```powershell
python -m paw blackboard write --project portable-harness --run-id demo `
  --role planner --kind plan --content "Inspect parser.py and add regression tests"
python -m paw blackboard read --project portable-harness --run-id demo `
  --query "regression tests" --limit 5
```

## 2. portaw = optional overlay (archived — salvage, ห้าม depend)

- คำสั่ง portaw **รันได้จริง** (probe ผ่าน: `install`/`sets`/`mem`/`doctor`) แต่ **โปรเจกต์ archived** (เจ้าของว่า "ทรงไม่ค่อยเวิค", ยังไม่ทำต่อ) → **brain ต้องไม่ขึ้นกับมัน**.
- ค่าที่ portaw เพิ่ม (ถ้าเลือกใช้):

  | portaw feature | ทำอะไร | แทนได้ด้วย (จาก candidate-backlog เอง) |
  |---|---|---|
  | `mem` | governance overlay (distrust-on-miss) เหนือ ICM | ICM decay/dedup ในตัว (พอสำหรับ v1) |
  | `sets` + `install --host` | curated bundle + patch (cc/codex/gemini) | hand-curated `mcp.json` · `rulesync` |
  | `agents-md` | AGENTS.md @import bridge | `openai/agents.md` + `rulesync` |
  | `bench` | token-delta | `ccusage --offline` ตรงๆ |

- **ท่ามาตรฐาน:** ใช้ ICM เป็นแกน. ถ้าวันใด revive portaw ค่อยเสริม governance/sets ทับ.

---

## 3. The stack (ICM center, portaw optional)

```
        ┌──────── hosts (first-party CLIs) ────────┐
        │  Claude Code · Codex · Gemini (+GLM via CC)
        └───────┬───────────┬───────────┬──────────┘
                │ MCP        │ MCP       │ MCP      ← icm init เสียบเอง
        ┌───────▼───────────▼───────────▼──────────┐
   MEM  │  ICM  (serve/CLI, 1 SQLite, local-only)   │  ← foundation
        │     · · · · (optional) portaw mem overlay │
        ├───────────────────────────────────────────┤
  TOOLS │  curated mcp.json  (or portaw sets)        │
        ├───────────────────────────────────────────┤
  INSTR │  AGENTS.md  (agents.md/rulesync; or portaw)│
        ├───────────────────────────────────────────┤
 TOKEN  │  RTK tool-layer: hook(Gemini/Copilot✓)/pipe│
        └───────────────────────────────────────────┘
```

---

## 4. Wire-up recipe = L0 ทั้งหมด

```powershell
# --- CORE (ไม่ต้องมี portaw) ---
irm https://raw.githubusercontent.com/rtk-ai/icm/main/install.ps1 | iex   # 1) ติดตั้ง (SHA256-verified); restart terminal ให้ PATH ติด
icm.exe init                                                              # 2) standard (cli+skill+hook); host miss ได้ → CLI bridge fallback
icm.exe store -t test -c "brain online" -i high -k "smoke"               # 3) acceptance (⚠️ icm.exe: PS 'icm'=Invoke-Command alias)
icm.exe recall "brain online"                                            #    เขียน host นึง → อ่านอีก host เห็น

# --- TOOL BUNDLE (เลือกทาง) ---
#   a) hand-curated: เขียน mcp.json (codegraph/context7/fetch/desktop-commander) แล้ว patch แต่ละ host
#   b) opportunistic portaw: portaw install efficiency-starter --host claude-code -y   (+ codex, gemini)

# --- INSTRUCTIONS ---  AGENTS.md (agents.md/rulesync)  หรือ  portaw agents-md --link

# --- TOKEN-CUT (RTK tool layer) ---  wire `rtk hook` ต่อ host (ดู §5)
#   ⚠️ rtk hook = claude/cursor/gemini/copilot เท่านั้น (ยืนยันแล้ว ไม่มี codex) → Codex: PATH-shim/`rtk pipe`
#   + พิจารณา Headroom layer-2 (long-tail compress, reversible) — ดู BENCH.md §2a stack-marginal
```

## 5. Token-cut (RTK, tool layer)

ตรวจแล้ว: RTK **ไม่มี** `serve` daemon, แต่มี `hook` (รองรับ **Gemini CLI, Copilot**), `pipe` (filter stdin สากล), `rewrite` (engine).

| Host | วิธี | สถานะ |
|---|---|---|
| Claude Code | hook เดิม (+ bypass กัน double) | ✓ |
| Gemini | `rtk hook` | wire |
| Codex | `rtk hook` ถ้าครอบ; ไม่งั้น PATH-shim (`git→rtk git`) / `rtk pipe` | **ยืนยัน coverage** |

วัด: `rtk gain` / `rtk cc-economics` / `ccusage`. **ไม่มี code ใหม่** นอกจาก glue.

---

## 6. Acceptance

1. blackboard protocol: isolated ICM SQLite write→recall→typed parse passes.
2. cross-host memory: `icm store` (Codex ctx) → `icm recall` (CC) เห็น + กลับกัน.
3. shared tools: cc/codex/gemini เห็น bundle เดียวกัน.
4. token-cut: non-CC รัน `git status` → output ย่อ; ตัวเลขขึ้น.
5. no-clobber: `icm init` / patch ทำ backup; config user ไม่หาย.

## 7. Risks

| Risk | Mitigation |
|---|---|
| hinge บน portaw (archived) | **ICM-direct**; portaw = optional overlay เท่านั้น |
| ICM ยังไม่ติดตั้ง = brain ตาย | step 1-2 recipe; CLAUDE.md mistakes ก็รอ ICM เหมือนกัน |
| tool-def กิน token ทุก host | คัด server น้อย-คม; CLI > MCP บน load-all; ≤2-3 MCP/set |
| Codex ไม่อยู่ใน `rtk hook` | PATH-shim / `rtk pipe` fallback |
| privacy (memory) | ICM local-only — ไม่รั่ว |
| paw/personal contents | ship schema/empty เท่านั้น |

## 8. Open questions

1. tool bundle: hand-curated `mcp.json` หรือ revive `portaw sets`? (เริ่ม hand-curated = พึ่งตัวเองน้อยสุด)
2. governance: ICM decay/dedup พอ หรือต้อง paw overlay (distrust-on-miss)?
3. Codex อยู่ใน `rtk hook` coverage ไหม?
4. instructions: `agents.md`+`rulesync` หรือ `portaw agents-md`?
