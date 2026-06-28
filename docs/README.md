# Documentation Map

This file is the navigation layer for humans and AI agents. It exists to stop
future sessions from following stale historical notes or rebuilding parked
ideas.

## Read Order For New Sessions

1. [`../CLAUDE.md`](../CLAUDE.md) — owner mindset and global decision rules.
2. [`../AGENTS.md`](../AGENTS.md) — Codex-specific operating guide.
3. [`STATUS.md`](STATUS.md) — current truth. Read section 0 first.
4. [`PAW-NORTH-STAR.md`](PAW-NORTH-STAR.md) — product concept and anti-wander rules.
5. [`NO-DAEMON-BASELINE-BACKLOG.md`](NO-DAEMON-BASELINE-BACKLOG.md) — next work.
6. Task-specific file from the map below.

When in doubt, `STATUS.md` section 0 and
`NO-DAEMON-BASELINE-BACKLOG.md` override older draft notes.

## Current Source Of Truth

| File | Purpose | Status |
| --- | --- | --- |
| [`STATUS.md`](STATUS.md) | Compact current state, assumptions, and active next work | authoritative |
| [`PAW-NORTH-STAR.md`](PAW-NORTH-STAR.md) | Product north star: portable harness curator/linker/launcher, global-first policy, and anti-wander rules | authoritative for product concept |
| [`BUNDLE-INIT-STRATEGY.md`](BUNDLE-INIT-STRATEGY.md) | What `paw init` should install/verify, which capabilities stay project-linked, and candidate research gates | authoritative for bundle/init strategy |
| [`NO-DAEMON-BASELINE-BACKLOG.md`](NO-DAEMON-BASELINE-BACKLOG.md) | Canonical backlog for making the no-daemon baseline usable | authoritative for next work |
| [`MEMORY-PLAN.md`](MEMORY-PLAN.md) | ICM, pending, curate, Memoir posture, and daemon posture | authoritative for memory |
| [`ECC-INTEGRATION-LEDGER.md`](ECC-INTEGRATION-LEDGER.md) | What paw reuses from ECC vs owns itself | authoritative for ECC overlap |
| [`WIRE-DECISION-MATRIX.md`](WIRE-DECISION-MATRIX.md) | Host/token/quality gates before wiring capabilities | authoritative for host tradeoffs |
| [`SHARED-BRAIN.md`](SHARED-BRAIN.md) | L0 brain architecture and ICM/RTK/paw relationship | current but secondary |
| [`ARCHITECTURE.md`](ARCHITECTURE.md) | Layered design and assumption ledger | current but broad |

## Research And Historical Context

These files are useful evidence, but do not resume their TODOs unless
`STATUS.md` or the backlog explicitly says to.

| File | Use |
| --- | --- |
| [`BENCH.md`](BENCH.md) | Bench summary and cost/quality reasoning |
| [`BUNDLE.md`](BUNDLE.md) | Catalog vetting history and set rationale |
| [`CATALOG-DEEP-VET-2026-06-25.md`](CATALOG-DEEP-VET-2026-06-25.md) | Deep vet notes for candidate tools |
| [`CODING-HARNESS-CANDIDATES-2026-06-28.md`](CODING-HARNESS-CANDIDATES-2026-06-28.md) | Coding-focused harness/tool gap scan and candidate bench backlog |
| [`BUNDLE-COVERAGE-GAPS-2026-06-28.md`](BUNDLE-COVERAGE-GAPS-2026-06-28.md) | Six-bundle coverage check, missing `observe-eval` bundle, and gap-driven candidate list |
| [`RECIPE-BUNDLE-RESEARCH-2026-06-28.md`](RECIPE-BUNDLE-RESEARCH-2026-06-28.md) | Persona-first recipe taxonomy and candidate tools/MCPs by user type |
| [`OPTIONAL-FOUNDATION-GAP-FILL-2026-06-28.md`](OPTIONAL-FOUNDATION-GAP-FILL-2026-06-28.md) | Targeted gap-fill for memory, skill format, agent safety, workspace, data/BI, and automation optional foundations |
| [`FOUNDATION-BENCH-2026-06-28.md`](FOUNDATION-BENCH-2026-06-28.md) | Local Foundation/Core + dev Optional Foundation benchmark after tool updates |
| [`RESEARCH-RADAR.md`](RESEARCH-RADAR.md) | Research watchlist |
| [`SKILL-ROUTER-RESEARCH.md`](SKILL-ROUTER-RESEARCH.md) | Skill-router research notes |
| [`SMART-ROUTER.md`](SMART-ROUTER.md) | Router design draft; v0 scope is narrower |
| [`PUSH-PULL-SKILL-ROUTER-DRAFT.md`](PUSH-PULL-SKILL-ROUTER-DRAFT.md) | Historical draft |
| [`PAW-CLI-WORKFLOW-DRAFT.md`](PAW-CLI-WORKFLOW-DRAFT.md) | Historical draft |
| [`GATEGUARD-PROBLEMS.md`](GATEGUARD-PROBLEMS.md) | Specific hook/gating concerns |
| [`CLAUDES-SKILL-USAGE-PROBLEM.md`](CLAUDES-SKILL-USAGE-PROBLEM.md) | Observed skill-use failures |

## Parked Until Later

- Mandatory daemon: parked. Continue CLI kernel first.
- Optional sidecar: allowed only after CLI + thin hooks expose a real ergonomic
  gap; it must remain optional.
- ICM Memoir graph: later pilot from curated `decisions` + `lessons` only.
- `skills.sh` integration: future external `SKILL.md` package channel only.
- ECC hook bundle clone: non-goal. Reuse or wrap selected parts only.

## Quick Commands

```powershell
git status --short --branch
icm.exe recall "portable-harness current task"
python -m paw sets list
python -m paw memory members --project portable-harness --run-id live
python -m paw curate --dry-run --limit 10
```
