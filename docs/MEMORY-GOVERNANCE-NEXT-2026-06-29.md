# Memory governance — next-up backlog

Date: 2026-06-29
Status: follow-on to the loop-closure work (distrust / sessionlog / outcomes wired).
Owner note: the three primitives are *wired* but `record_miss` has no automatic
caller yet, and the ledgers have no CLI to view/reset. This file tracks that gap
so it does not get lost. Recorded as a file rather than ICM because ICM
`store`/`list` honesty is still unverified (see bottom).

## Context — what landed this session

Three overlay primitives ported from the `port-a-whip` prototype to `paw/memory/`,
each fail-safe and isolated by `tests/conftest.py`:

- `distrust.py` — miss-count overlay. `distrusted_ids()` is filtered in
  `recall.icm_recall` and `router_block._relevant_lessons`.
- `sessionlog.py` — per-session inject dedup. `paw_block` (session_id already
  flows from the hook) skips lessons already injected this session.
- `outcomes.py` — router feedback loop. `match_sets` demotes sets the user keeps
  ignoring and logs suggestions; `linker.apply_plan` logs conversions.
- `store.py` — atomic write + cross-process lock foundation shared by all three.

The loops are closed and tested at the boundaries (187 focused, 444 full suite).

## Backlog — NOT yet done

### 1. `record_miss` has no automatic caller
The distrust overlay is read everywhere but written nowhere on the hot path.
Today a miss can only be recorded manually (like `paw memory observe` records an
observation). To make distrust self-feeding, wire it into a Stop/capture path
that detects "this memory was recalled earlier in the session AND the same error
recurred" — i.e. a recall→fail→miss link.

**Blocker:** this needs trustworthy transcript-watermark delta capture (read the
session transcript since the last watermark, match recalled ids against re-fired
errors). That capture is itself a known verification gap — see AGENTS.md
"Resuming the memory system" and `docs/MEMORY-PLAN.md`. Do NOT build a second
ad-hoc transcript scanner; reuse the reflect/capture path once it is honest.

First slice (no transcript parsing): let an agent or hook call
`distrust.record_miss(mem_id)` explicitly when it observes a recalled lesson
failing — same posture as `paw memory observe` today. Bounded, manual, honest.

### 2. CLI subcommands for the three ledgers
The overlays are internal today. Add read/reset commands so an owner can inspect
and clear them without hand-editing jsonl:

- `paw memory distrust list` / `forget <id>` — show suppressed memory ids, reset one
- `paw memory outcomes list` / `forget <set>` — show suggest/use counts, un-demote a set
- `paw memory session reset <session_id>` — wipe one session's inject log (compact hook)

Keep these bounded (one-line renders by default) and never auto-write from a
read command.

### 3. Migrate `paw/memory_governance.py` (observations) to `store.py` primitives
The pre-existing `memory_governance.py` (observations → proposals) still uses
non-atomic `path.write_text`. It is a different concept from `distrust.py`
(rewrite-vs-retire proposals, not miss-suppression) but should share the same
atomic write + lock so a parallel hook can't corrupt it. Low-risk polish; do
after #1/#2.

## Known blocker — ICM `store` honesty (carried from HANDOFF doc)

Reproduced this session: `icm.exe store -t decisions -c "..."` prints
`Stored: <id>`, but `icm.exe list -t decisions` does NOT return that id. This is
the same false-success mismatch the curate honesty work (#1) defends against at
the paw layer. Until the ICM CLI contract is verified (or worked around with a
re-read-and-retry), durable decisions/mistakes are only trustworthy through the
paw curate path that verifies visibility — not through a raw `icm store`. That
is why this backlog is a markdown file and not an ICM `decisions` entry.
