# swe_probe — team(Claude+DeepSeek) vs solo, on SWE-bench-Lite

Answers the EXISTENTIAL gap (STATUS #1) and upgrades bench from proxy→objective (#2):

> Does **Claude-plan + DeepSeek-implement** hold resolution-rate vs **Claude-solo**,
> while burning far less scarce **Claude quota**?

Same-vendor (Opus+Sonnet) is the case literature says solo wins. The real edge is
**cross-vendor cost-arbitrage**: bulk implementation moves to a ~1-2 orders cheaper
meter (DeepSeek V4-flash, $0.14/$0.28 per M) while Claude only plans/reviews.

## Design (keeps it cheap + honest)

- **Oracle retrieval** — every arm gets exactly the files the gold patch edits.
  Measures *patch generation*, not retrieval. No repo-wide exploration = low Claude quota.
- **Single shot** — no agentic retry loop ("ไม่ต้องรันหลายรอบ").
- **3 arms:** `claude-solo` (you), `deepseek-solo` (trap baseline), `team` (you plan → DeepSeek impl → you review).
- **Objective scoring** — official swebench harness in Docker → `resolved: true/false`.
- **gold-validate gate** — score the gold patch first; if it doesn't resolve, the
  env/scorer is wrong → don't trust arm scores.

## Privacy

DeepSeek = PRC servers; code leaves the machine. Only public OSS instances here. Never
run proprietary code through the DeepSeek arms.

## One-time setup

DeepSeek key (already set this machine):
```powershell
$env:DEEPSEEK_API_KEY   # must be non-empty
```

swebench scorer needs Python ≤3.12 (no wheels on 3.14) — isolate with uv:
```powershell
uv python install 3.12
uv venv --python 3.12 bench\swe_probe\.swebench-venv
bench\swe_probe\.swebench-venv\Scripts\python -m pip install swebench
```
(or set `$env:SWEBENCH_PYTHON` to any 3.10–3.12 python with `swebench` installed.)

Docker Desktop must be running. Subset footprint ≈ 10–20 GB (not the 120 GB full-run
figure); `docker system prune -a` reclaims after.

## Run (per instance)

```powershell
# 0. lock 2 small instances + verify env
py -m bench.swe_probe.run instances --repo psf/requests      # pick 2 real ids
py -m bench.swe_probe.run pull <id>
py -m bench.swe_probe.run gold-validate <id>                 # MUST say PASS

# 1. DeepSeek-solo (automated)
py -m bench.swe_probe.run deepseek-solo <id>
py -m bench.swe_probe.run eval <id> deepseek-solo

# 2. team — Claude (you) plans into plan.md, DeepSeek implements, you review the .diff
#    ...write bench/swe_probe/plan.md (the plan), then:
py -m bench.swe_probe.run team-impl <id> --plan bench\swe_probe\plan.md
#    review/repair preds\<id>__team.diff if needed, then:
py -m bench.swe_probe.run eval <id> team

# 3. Claude-solo — you write the whole patch to a file, register + eval
py -m bench.swe_probe.run claude-patch <id> claude-solo --file my.diff
py -m bench.swe_probe.run eval <id> claude-solo

# 4. record Claude quota for the Claude-touching arms (ccusage delta before/after)
ccusage session    # snapshot input/output token delta for the arm
py -m bench.swe_probe.run claude-usage <id> claude-solo --in <N> --out <M>
py -m bench.swe_probe.run claude-usage <id> team        --in <N> --out <M>

# 5. read the scorecard
py -m bench.swe_probe.run report
```

## Reading the result

`win = team pass == claude-solo pass, AND team claude_tok << claude-solo claude_tok`

- team resolves what solo resolves → **quality holds at the handoff**.
- team Claude tokens (plan+review only) ≪ solo Claude tokens (full solve) → **quota saved**;
  DeepSeek $ is negligible.
- `deepseek-solo` is the trap: if it already resolves cheap tasks, the team overhead is pointless.

## Phases

- **A (here):** does quality hold + quota shift? (the load-bearing risk)
- **B (later, arithmetic):** project token split onto the real seat model
  (Claude flat-but-capped + DeepSeek meter) → "stretches my Max quota by X".
