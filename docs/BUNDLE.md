# BUNDLE — L0 curated tools

> v2 · 2026-06-21 · เจ้าของ: supimol.web@gmail.com · คู่กับ [SHARED-BRAIN](./SHARED-BRAIN.md) · [BENCH](./BENCH.md) · [STATUS](./STATUS.md)
> **2 layer แยกกัน:** *mental model* ยุบ lean (เกือบทุกตัว 0-tax CLI stack อิสระ) · *install UX* เก็บ **named-set แบบ portaw** (`install <set> --host` = ลงทีเดียว+wire+verify) เพราะ = ความสะดวกผู้ใช้ (North Star #2).

---

## กฎเดียว (mental model)

**0-tax core (always) + sets ลงตามต้องการ (named, on-demand) + MCP = zone เดียวที่ tax/N1 กัด.**
ลำดับเลือก: native host > CLI/hook (0-tax) > MCP (taxed, ≤2-3/host). วัด [`bench/mcp_tax.py`](../bench/mcp_tax.py).

## 1. Core — always-on, 0-tax (ทุก host)

| layer | tool | mode | สถานะ |
|---|---|---|---|
| token-cut (tool-output) | **RTK** 0.42 | hook (claude/cursor/gemini/copilot) · Codex=shim/pipe | ✓ installed |
| token-cut (assistant-output) | **caveman** | hook (SessionStart/UserPromptSubmit) | ✓ active |
| memory | **ICM** 0.10.53 `standard` | CLI+skill+hook (NO MCP) | ✓ installed |
| structural search/rewrite | **ast-grep** 0.43 | CLI | salvage — bench +69% precision/+76-97% codemod |
| instructions | **AGENTS.md / CLAUDE.md** | @import per host | ใช้อยู่ |

triad ครบ: lexical (grep native) / **struct (ast-grep)** / graph (codegraph). 0 tool-def tax.

## 2. MCP — zone เดียวที่ต้อง curate (tax + N1 ceiling)

| server | tools | tax eager | rule |
|---|---|---|---|
| **codegraph** | 8 | 1,653 | code-intel บน **CC** (lazy=idle 0, richer: callers/impact) |
| **semble** | 2 | ~509 | code-intel บน **load-all host** (Codex/Gemini) แทน codegraph — eager leaner, search-only |
| **fetch** | 1 | 290 | host-conditional: ข้ามถ้ามี WebFetch native (CC); ใส่ Codex/Gemini |

- **code-intel = codegraph XOR semble ต่อ host** (ห้ามโหลดคู่). CC=codegraph · Codex/Gemini=semble.
- **≤2-3 eager MCP/host.** **ตัด eager:** Desktop_Commander (11.5k, ซ้ำ native Read/Write/Bash) · context7 (→ on-demand) · plugin_*/chrome.

## 3. Installable sets — install UX แบบ portaw (named, ลงทีเดียว+wire+verify)

> ผู้ใช้เลือก **set** ไม่ใช่ tool ทีละตัว. `<harness> install <set> --host <host>` → ลง+patch config+verify-gate ในคำสั่งเดียว.
> **salvage portaw ทั้ง machinery:** `sets.json` (registry) **+ `install`/`sets list|show`/`verify`** (installer/wirer) — ไม่ใช่แค่ data. ส่วนใหญ่ 0-tax CLI → stack อิสระใต้ N1, install ตอนต้องใช้ (YAGNI).

| set | คือ | tools | tax | vet |
|---|---|---|---|---|
| **efficiency-starter** | coding (= core เรา) | codegraph/semble · rtk · ast-grep | host-cond | ✓ tested |
| **secure-agent** | permissions/supply-chain | nah(hook) · gitleaks · osv-scanner · infisical | **0 MCP** | ✓ tested PASS |
| **data-query** | query CSV/Parquet/SQLite/JSON | duckdb · jq | **0 MCP** | ✓ +99.96% vs Read |
| **doc-extract** | docx/xlsx/pptx → md | markitdown ⚠️`[docx,xlsx,pptx,pdf]` ไม่ใช่`[all]` | **0 MCP** | ✓ tested |
| **design-quality** | anti-slop UI | impeccable(skill) · figtree | **0 MCP** | ✓ slop-catch |
| **context-quality** | anti-halluc lib docs | context7 (2t) | 927/0 | ✓ idle-calc |
| **web-research** | research | fetch · ladder: scrapling→searxng→exa→firecrawl | 259/0 | ◐ CC: WebFetch พอ |
| **browser-automation** | browser driving | browser-harness (CDP skill) | **0 MCP** | ◐ ไม่ install-test · high-priv |

**อย่าใช้ MCP-wrap** (portaw rejected, idle-tax เปล่า): ast-grep-mcp · duckdb-mcp · playwright-mcp(47t) · **scrapling-mcp (15,859 tok 🐋)** · firecrawl-mcp. CLI form เสมอ.

## 4. Compat — tested 2026-06-21 (LIVE, secure-agent ลงครบบนเครื่องนี้)

- ✅ **rtk × CLI sets ไม่ชน** (rtk rewrite: git/ls→rewritten; ast-grep/duckdb/jq/markitdown/gitleaks/osv→**passthrough**).
- ✅ **rtk + nah PROVEN LIVE** — `settings.json` PreToolUse(Bash) = **rtk→nah**; รันทั้ง session ผ่าน 2 hook ไม่ชน (`nah log` ยืนยัน). nah guard จริง: `curl\|bash`→**BLOCK**(RCE) · `rm -rf ~`→ASK · `git status`→ALLOW.
- ⚠️ **FRICTION (intra-bundle) — RESOLVED don't-loosen (2026-06-22):** nah classify = `unknown→ASK` สำหรับ ast-grep/duckdb/rtk (jq=ALLOW อยู่แล้ว). **planned glue (classify→allow) = REJECTED = security hole:** `nah classify` match command-**prefix** + tools **dual-use** (พิสูจน์ `nah test`: `ast-grep -U`=rewrite · `rtk rm -rf`/`rtk sh -c 'curl|bash'`=wrapper bypass · `duckdb DROP/ATTACH/INSTALL`) → blanket-allow = silent-mutate / nah-bypass / RCE (A-12). nah `unknown→ASK` = **ถูกต้อง**. fix: accept ASK (ASK→proceed ไม่ block) หรือ nah **LLM-classifier** opt-in (`nah key`, content-aware). secure-agent ship ตามเดิม.
- ✅ **complement ไม่ทับ:** codegraph(code)/context7(lib docs)/web-research(remote)/data-query(local files)/doc-extract(binary) = 5 surface แยก.
- ⚠️ **MCP eager tradeoff** (codegraph XOR semble · ≤2-3). CLI sets ไม่มี tradeoff (นอกจาก nah-classify glue ข้างบน).

## 5. Host matrix

| host | core | MCP eager | token-cut | enforce tier (A-13) |
|---|---|---|---|---|
| Claude Code | RTK hook · ICM · caveman · ast-grep | codegraph (fetch ซ้ำ WebFetch→skip) | `rtk hook claude` ✓ | **A** auto-hook — token-cut + nah hard-BLOCK guaranteed |
| Gemini | RTK init · ICM · ast-grep | semble + fetch | `rtk init --gemini` ✓ | **B** init + some-hook |
| Codex | RTK by AGENTS.md instr · ICM(`icm.exe`) · ast-grep | semble + fetch | manual instr (rtk init ไม่มี `--codex`) | **C** instruction + `nah codex setup` + sandbox (no-hook) |

> ⚠️ **enforcement ไม่เท่ากันทุก host (smoke 2026-06-22, A-13):** shared brain (ICM memory + AGENTS.md) = portable จริง; แต่ **automatic guarantee (hook token-cut + nah hard-BLOCK) = Claude-only strong**, degrade → Gemini(medium) → Codex(instruction+sandbox, softer). **secure-agent บน Codex = `nah codex setup` (config approval-mode + `~/.codex/rules/nah-authority.rules` + sandbox) ไม่ใช่ hard-block** — โฆษณา guarantee ให้ตรง tier.

```powershell
# install UX (target — reuse/port portaw installer):
#   harness install secure-agent --host claude-code   # ลง+wire+verify ทีเดียว
#   harness sets list                                  # ดู catalog
# verify:
py bench/mcp_tax.py --all      # eager MCP เล็ก
icm.exe recall "smoke" ; rtk gain
```

## 6. Recheck (decay triggers)

- **Headroom** Windows install — ✓ **RESOLVED 2026-06-22:** pkg = `headroom-ai` 0.24.0 (≠ `headroom` squat), deps win-wheels ครบ, sdist pure-Python no-compiler. portaw 06-09 "no wheel" **disproven**. (A-09)
- **nah-classify** — ✓ **RESOLVED: ไม่ loosen** (prefix-match + dual-use = security hole, A-12). dual-use ASK = by-design. ปิด friction → nah LLM-classifier opt-in (`nah key`), ห้าม prefix-allow.
- **installer salvage** — portaw `install`/`verify` archived; ตัดสิน reuse-as-is vs port-thin (decision ค้าง).
- portaw vet 06-05..15 (~2wk) → re-confirm tool version ตอน activate แต่ละ set.
