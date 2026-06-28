# paw — Agent Operating Manual

> Future linker source, not the current session truth. For current state and
> next work, read `docs/README.md`, `docs/STATUS.md`, and
> `docs/NO-DAEMON-BASELINE-BACKLOG.md` first. If this file conflicts with those
> docs, treat this file as stale and update it before re-linking.

> Future managed-block source for the **port-a-whip (paw)** harness brain. The
> current CLI uses `python -m paw plan|apply|verify|remove <set>`. A future
> linker may inject relevant slices of this file into host context files inside
> a managed `<!-- paw:start -->`…`<!-- paw:end -->` block. **Do not hand-edit
> generated blocks** — edit this source and re-link/re-apply.

paw is a **curated, cross-host agent harness**: one install wires a vetted bundle of tools plus a
shared memory brain into whatever coding agent you run (Claude Code / Codex / Gemini / …). The moat
is **curation + token-cut + shared memory across heterogeneous agents** — not any single tool.

---

## L0 Brain — the always-on layer

| Component | Role | Surface | Token cost |
|---|---|---|---|
| **ICM** | Shared memory (mistakes, lessons, project facts) across every host | CLI (`icm`) + optional hook | **0 tool-defs** (CLI) |
| **RTK** | Shell-output token-cut (compresses git/cargo/pytest/build output before context) | PreToolUse hook / proxy | **0 tool-defs** (hook) |
| **nah** | Deterministic action-guard (blocks dangerous shell, no LLM in path) | PreToolUse hook | **0 tool-defs** (hook) |
| **curated sets** | On-demand tool bundles, vetted to be quality *and* compatible together | CLI + ≤1 MCP/host | see set table |

Everything in L0 is CLI/hook-first → **zero per-session schema tax**. MCP servers are the exception,
not the rule (see Token discipline).

---

## Memory protocol (ICM) — do this every session

Single source of truth = **ICM**. The old `portaw memory` path is retired; route through ICM and
`python -m paw ...`.

- **Recall before acting** on anything non-trivial: `icm.exe recall "<question>"` on Windows
  (`icm recall "<question>"` elsewhere).
- **Store a mistake the moment it bites:** `icm.exe store -t mistakes -c "trigger -> fix" -i high -k "<term>"`
  (`-i critical` for an always-on env-level lesson). Don't wait for end of session.
- **Curate carefully:** `python -m paw curate --dry-run --limit 10` before applying. Do not drain
  noisy `pending` entries blindly.
- **PowerShell gotcha:** call `icm.exe` — bare `icm` is an alias for `Invoke-Command`.
- Health check today is manual: `icm.exe topics`, `python -m paw sets list`, and
  `python -m paw memory members --project portable-harness --run-id live`. A one-shot
  `paw doctor` is backlog work.

A `[HIGH]`/`[critical]` lesson that matches the current action → **surface it to the user before proceeding.**

---

## Token discipline

Tool definitions cost tokens **every session** and again on compaction (~550–1,400 tok/tool). The
metric that decides a tool is **net = (runtime cut − static def tax)**, never compression % alone.

- **CLI/hook beats MCP** on any load-all host (0 def tax). Prefer it.
- **N1 ceiling: ≤ 2–3 active MCP servers per host.** Adding a 3rd needs an explicit check.
- Claude Code lazy-loads MCP defs (idle ≈ 0); **Codex and Gemini load all defs at startup** — there
  the def tax is always-on, so the host-conditional anchor matters (e.g. codegraph on CC, the leaner
  semble on Codex/Gemini).
- Measure before locking. `portaw bench` / `ccusage` kill vibes — don't guess token deltas.

---

## Security

`secure-agent` set = four non-overlapping CLI/hook guards (0 MCP def):

- **nah** — action guard. Blocks `curl … | bash`, asks on `rm -rf ~`, allows `git status`.
  **Dual-use commands resolve to ASK by design** (a wrapper that could mutate/exfiltrate is not auto-allowed).
  That friction is correct — do **not** loosen it via prefix-allow. Never pair nah with
  `--dangerously-skip-permissions` / auto-mode (bypasses the guard).
- **gitleaks** — secret egress guard. Pipe staged content before commit: `cat <file> | gitleaks -v stdin`.
- **osv-scanner** — dependency ingress guard. Scan before `npm i` / `pip install`: `osv-scanner scan source -r .`.
- **infisical** — secret exposure guard. Run secret-needing commands without the raw key in context:
  `infisical run -- <cmd>`. **Never hardcode secrets**; env/`.env`/secret-manager only.

Source code must not leave the machine unintentionally. Treat ToS/privacy as a hard constraint — it
can block a task.

---

## Curated sets

Install or inspect a set with `python -m paw plan|apply|verify|remove <set>` and
`python -m paw sets show <name>`. Each set is vetted for quality **and** mutual
compatibility; sets stack without host-surface collision unless noted.

| Set | Axis | What it buys | Active MCP |
|---|---|---|---|
| **efficiency-starter** | ↓token | Code-graph navigation (codegraph/semble) + ast-grep structural search/codemod + RTK output-cut | 1 (codegraph **XOR** semble, host-conditional) |
| **secure-agent** | permissions | nah + gitleaks + osv-scanner + infisical (4 guards) | 0 |
| **context-quality** | ↑quality | Context7 — live, version-correct library docs (kills API hallucination) | 1 |
| **design-quality** | ↑quality | impeccable anti-AI-slop audit + figtree Figma-token extract | 0 |
| **web-research** | ↓token | fetch + clean content extraction (markdown, not raw HTML) | 1 |
| **browser-automation** | capability | Lean browser-driving for agents that must use a real site | 0 |
| **data-query** | ↓token | Query CSV/Parquet/JSON/SQLite (duckdb) — bounded answers, not full dumps | 0 |
| **doc-extract** | capability | MarkItDown — one CLI call converts docx/pdf/… to markdown | 0 |

N1 check when stacking on a load-all host: efficiency-starter + context-quality = 2 active MCP (within
ceiling); a 3rd MCP set needs review.

---

## Cross-host enforcement — honest tiers (not uniform)

Portability is real, but **guarantees are not equal across hosts.** Do not advertise uniform-automatic
enforcement.

| Host | Memory (ICM) | RTK / nah guards | Context file |
|---|---|---|---|
| **Claude Code** | CLI bridge ✓ | **strong** — real PreToolUse hooks | `CLAUDE.md` (+ `AGENTS.md`) |
| **Gemini** | CLI bridge ✓ | **medium** — `rtk init --gemini`; nah = roadmap | `GEMINI.md` / settings |
| **Codex** | CLI bridge ✓ | **softer** — no hooks; instruction + `sandbox_mode` | `AGENTS.md` only |

ICM is portable everywhere via the CLI bridge. RTK/nah degrade from hook → instruction/sandbox as you
move off Claude Code, so a `secure-agent` guarantee on Codex is weaker than on CC — say so.

---

## Operating ethos

1. **Reuse, don't rebuild.** Search GitHub / registries / docs before writing anything new. Adopt,
   port, or wrap something that solves 80%+; write only the thin glue that's missing.
2. **Challenge everything**, including this file. Stale or wrong → fix it (edit the source, re-link).
3. **Landscape shifts daily.** Re-search for better tools; mark assumptions that can decay (ToS,
   subscriptions, vendor benches) and recheck them rather than building on a frozen guess.
4. **Substance over stars.** Vet by commits/releases/tests/recency/architecture, not popularity.
5. **Empirical over vibes.** Measure token deltas before locking a tool.
6. **Give a recommendation, not a survey** — choose, with the reason and the tradeoff.

> **Assumption ledger (recheck triggers):** "best" picks (RTK token-cut, ICM memory quality) are
> **not yet head-to-head benched** vs challengers (Headroom, MemPalace) — treat as current-best,
> replaceable. Per-host enforcement tiers depend on each host's hook support, which vendors change.
