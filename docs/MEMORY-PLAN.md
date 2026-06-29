# Memory plan — cross-host shared brain (CC + Codex)

> Locked 2026-06-26. Supersedes the half-done portaw→ICM migration. Driving
> concern (owner): the agent writes/reads memory **at the wrong moment** —
> misses real lessons, stores noise, forgets to recall, blackboard goes stale.
> That is a **behavioral/policy** problem, not a storage-backend problem.

## Current complaint — parallel agents now have v0 support

Owner complaint: memory still does not work well when several AI tools/vendors
and several sessions are open at the same time. That complaint was correct; the
first fix is now a small explicit coordination plane, not a full orchestrator.

What exists today:
- one local ICM store shared by hosts;
- explicit `paw blackboard write/read` for run-scoped handoff;
- heuristic capture/curate/recall plumbing for single-session continuity.
- `paw memory register|heartbeat|members` for peer identity and stale detection;
- `paw memory post|poll` for cursor-based shared/private lanes;
- `paw memory promote` for private→shared promotion;
- `paw memory lock-acquire|lock-release` for TTL write-intent locks.
- `paw memory hook` + `paw memory install-hooks` for Claude/Codex hook-assisted
  auto-register/heartbeat/poll, so agents do not need to remember the mesh
  manually on every turn.

What does **not** exist yet:
- automatic live capture across several concurrent vendors/sessions;
- push/subscription so one agent sees another agent's new memory without polling;
- automatic merge of conflicting semantic wiki updates;
- cross-machine transport;
- automatic agent spawn/barrier orchestration.

So the honest label is: **ICM-backed durable memory + local poll-based
parallel-memory mesh v0 + thin hook shim.** It supports several local live
sessions coordinating through one CLI, with Claude/Codex hooks preventing common
"agent forgot to poll" failures, but it is not yet autonomous multi-agent
teamwork.

## Verdict on backend — keep ICM

ICM is the right **struct** (verified): `topic·scope·importance·weight·access_count·
summary·raw_excerpt·keywords·embedding·related_ids`. Primitives map cleanly onto
the Mem0 model (ADD=`store`, UPDATE=`update`, DELETE=`forget`, NOOP=skip,
merge=`consolidate`). Semantic out-of-box (MiniLM), CLI = 0 def-tax, cross-host
via one SQLite + `icm.exe` on both hosts.

**agentmemory (rohitg00 / `@agentmemory/agentmemory`)** — strongest challenger
seen. Higher ceiling (95.2% R@5 LongMemEval-S), built-in 12-hook auto-capture +
LLM-compress, 1423 tests, 24k★. **Not adopted**: daemon-centric (iii-engine +
ports 3111/3113/49134, no one-shot CLI recall) conflicts with the lean/portable/
stateless thesis. The one thing it buys — auto-capture — is cheaply rebuildable
on ICM. *Recheck trigger:* shift to **multi-agent team** (concurrent shared live
memory) → its server model wins; or ICM rebuild proves low-quality; or we want
its observability (session replay/OTel/viewer). The old ledger note
("bm25-only") is **stale** — it now ships local MiniLM + hybrid RRF.

### Daemon posture

Current focus stays **no-daemon / CLI-first** until the memory stack is usable
enough to evaluate honestly. The concern is real: no-daemon can push work back
onto the user and agent, increasing prompt/token cost through manual
`recall`/`poll`/`store` reminders, and can lose memory unless hooks are made
heavier.

Decision for now:

- do not add a mandatory daemon before the CLI/hook path is working end to end;
- keep the durable contract portable through ICM CLI + committed docs + host
  hooks where available;
- revisit an **optional local sidecar** after the no-daemon baseline is usable.

Future sidecar gate: it must reduce manual prompts, missed captures, hook
complexity, or coordination lag in measured use, while staying local-only,
CLI-compatible, no-MCP-required, and graceful when absent. In short: "no
mandatory daemon" is the durable principle; optional daemon remains a later
benchmark candidate.

## Memory-type model (CoALA) + consolidation pathway

```
EPISODIC ──reflection(distill)──► SEMANTIC ──recurrence, human-gated──► PROCEDURAL
buffer / blackboard               ICM (experiential)                    skills (router)
                                  AGENTS.md family (committed)
```
- **Episodic** (raw: pending candidates, coordination) — transient.
- **Semantic** (distilled lessons/facts) = the **wiki**. Split:
  - experiential / cross-project / decay-prone → **ICM**
  - convention / ADR / architecture (repo-worthy, reviewable) → **CLAUDE.md /
    AGENTS.md / GEMINI.md** (linker injects all three)
- **Procedural** (runbook/recipe) = **skills** — already cross-host (router scans
  `.claude`+`.codex`+`.agents`). Recurring lessons *graduate* here (human-gated).

### Memoir posture

ICM's `memoir` layer is not in use yet (`icm memoir list` currently returns no
memoirs). Keep it that way until curation is cleaner. Memoir is the permanent
concept/graph layer, not a raw capture inbox: do not distill `pending` into a
memoir. The first safe pilot is one `portable-harness` memoir distilled only
from curated `decisions` and `lessons`, then searched/exported as a graph. This
is a later visual/knowledge-graph experiment, not part of the current
no-daemon baseline.

## Locked decisions

1. **ICM = the only true cross-host store** — semantic wiki + `pending` topic
   (never recalled into wiki) + blackboard coordination/continuity.

   <!-- paw:decision:icm-only-store:start -->
   ICM is the only true cross-host store. Do not propose daemon-centric
   alternatives (e.g. agentmemory) as a cross-host store — they clash with the
   no-daemon thesis. Markdown (CLAUDE.md / AGENTS.md) is for committed, git-
   reviewed facts; ICM is for semantic recall + structured facts + blackboard.
   <!-- paw:decision:icm-only-store:end -->
2. **Scope narrow** — experiential→ICM; committed→AGENTS.md family. **Storage
   split, recall unified** (recall reads ICM **and** greps the host context file).
3. **Continuity → ICM blackboard handoff** (retire CC-file's cross-host role;
   resume works on any host). CC file-memory = optional CC-only scratch, *outside*
   this design.
4. **Graduation = suggest** (human-gated; only procedural-shaped lessons; never
   auto-write a skill from an unvalidated lesson — skills are higher authority).
5. **Cross-link = defer traversal, populate `related_ids`** opportunistically
   during curation (data ready if graph is added later; flat recall is the 80%).
6. **Reflection engine — heuristic default, LLM as an optional silent-bug pass
   (hybrid).** *Updated by Phase-4 bench (`bench/_reflection_ab.py`), superseding
   the original "host-uniform dedicated DeepSeek" call.* On the gold set both
   arms scored F1≈0.86, but the heuristic is free/instant (0.16ms, $0) while
   DeepSeek costs ~2.1s + ~$0.00025/session and only **shifts** the error profile
   (catches silent bugs the `is_error` heuristic is blind to, but drops terse user
   corrections). So: keep the heuristic as the always-on capture, add a dedicated
   LLM (DeepSeek, host-uniform — avoids the nested-`claude` footgun) ONLY as a
   second pass for the silent-bug class. Re-bench with more fixtures before lock.
7. **CLI floor before hook** — `paw recall` / `paw reflect` work on any host
   (pull); push (UserPromptSubmit) + capture (Stop) hooks are enhancements on
   hook-capable hosts (CC, Codex). Other (API-call) hosts: deferred, CLI-only.

   <!-- paw:decision:cli-floor-before-hook:start -->
   The CLI is the floor; hooks are the ceiling. `paw recall` / `paw reflect` /
   `paw curate` / `paw memory status` MUST work on every host via plain CLI
   (pull model), because ZCode and other API-call hosts have no hook surface.
   Hooks (UserPromptSubmit injection, Stop capture) are ENHANCEMENTS on hook-
   capable hosts only — never a dependency. Do not move load-bearing memory
   logic into a hook such that a non-hook host loses the capability. When in
   doubt, ship the CLI command first and the hook wiring second.
   <!-- paw:decision:cli-floor-before-hook:end -->
8. **Memoir later, not now** — Memoirs are for curated stable concepts and graph
   visualization after the ordinary pending→wiki flow is trustworthy. Do not
   use Memoir as a pending drain or automatic transcript distiller.

   <!-- paw:decision:memoir-deferred:start -->
   Memoir (ICM knowledge graph) is deferred, not used. Do not wire Memoir as a
   pending drain or automatic transcript distiller — it is reserved for curated
   stable concepts AFTER the pending→wiki flow is trustworthy. Treat any Memoir
   proposal as premature until the ordinary memory loop is honest end-to-end.
   <!-- paw:decision:memoir-deferred:end -->

## Wiki entry schema (ICM)

```
topic:       mistakes | lessons | facts
importance:  low|medium|high|critical   (escalates on recurrence)
keywords:    [terms…, seen:N, type:execution|silent-bug|misalignment]
summary:     distilled trigger→fix / lesson (atomic, retrieval-phrased)
related_ids: [linked lessons/mistakes]   scope: project|global
```

### Mistake taxonomy (drives multi-signal capture)
| type | capture signal | reliability |
|---|---|---|
| **execution / AI oversight** | tool `is_error`, error→success sequence | heuristic ✓ |
| **silent bug (no error)** | none in-session; later test-fail/revert, or explicit | cross-session / explicit only |
| **user↔AI misalignment** | user correction/rework markers, dissatisfaction | heuristic partial |

Capture emits **coarse candidates + provisional type**; the reflection step
classifies + extracts the real lesson + discards false positives.

## Honest host tiers (degrade gracefully)

| host | capture (Stop) | recall push | recall pull (CLI) | reflect | committed |
|---|---|---|---|---|---|
| Claude Code | hook ✓ (`transcript_path`, JSONL) | paw_block ✓ | `paw recall` | dedicated/live | CLAUDE.md |
| Codex | hook ✓ (rollout adapter ✓; Stop-stdin TBV) | paw_block ✓ | `paw recall` | dedicated | AGENTS.md |
| Gemini/Cursor/API | deferred | — | `paw recall` | dedicated | GEMINI.md/— |

## Phase 0 findings (verified 2026-06-26)

- CC Stop stdin carries `transcript_path`; transcript = JSONL, assistant entries
  hold `message.content[].type==tool_use`, tool results ride user entries with
  `is_error` → fail→fix is parseable.
- CC events present: UserPromptSubmit, Stop, SessionStart, PostToolUse,
  PreToolUse, PostToolUseFailure.
- Codex events present: same set. **But Codex Stop→`portaw memory capture-hook`
  and SessionStart→`portaw memory session-hook` are DEAD (portaw)** — same
  migration gap as CC's mistake-learning stop-hook.
- **Residual risk:** Codex Stop stdin payload + transcript schema unverified
  (Codex mirrors the Claude hook contract, but the transcript JSONL shape must be
  confirmed before the capture adapter is trusted on Codex).

## Phases & sequencing

`0 verify → 1 recall-floor → 6 cleanup(migrate+retire) → 2 capture → 3 curate →
4 bench → 5 graduate`

| # | work | nah-blocked hook? |
|---|---|---|
| 0 | verify hook contracts (DONE for CC; Codex transcript TBV) | — |
| 1 | `paw recall <prompt>` CLI (wrap `router_block`) + read ICM + grep host committed file | — |
| 6 | migrate 46 `~/.paw/.../lessons.jsonl` → ICM (filter recurrence>1, drop raw-cmd noise); retire `~/.paw` overlay + dead mistake-learning stop-hook; fix CLAUDE.md single-source claim | hook = manual |
| 2 | **DONE (code+CLI; Stop-hook shim pending)** `paw/reflection.py` + `paw reflect --capture [--transcript] [--dry-run]` (reads Stop-hook stdin `{transcript_path,session_id}` else). Multi-signal scan → ICM `pending` topic + `type:` guess. **Noise control (owner's worry) — structural filters:** skip `is_error` that is permission-denial / `nah` guard (`_NON_ERROR`); skip `isCompactSummary`/`isMeta` turns; misalignment requires terse turn (≤240c) + strong marker only. Real-transcript validation: 5 raw → 1 after filters (4 FPs killed). `pending` excluded from `paw recall`. **Incremental capture:** CC Stop fires once per turn, so capture resumes from a per-session watermark (`~/.paw/state/reflect/<sid>.json`) — only new lines scanned, no cross-turn dup flood (`--full` forces rescan; dry-run never advances). Live-proven: run1 stores 1, run2 stores 0. | Stop-hook shim = manual |
| 3 | **DONE (engine+CLI; SessionStart shim pending)** `paw/curate.py` + `paw curate [--surface][--dry-run][--limit]`. Reconciles each pending vs `paw recall` top-K by Jaccard over summaries: **ADD** (no near-dup → store `mistakes`, seen:1, drops signal:/session:) · **BUMP** (Jaccard≥0.5 → increment existing `seen:N`, escalate seen≥3→critical, never downgrade) · **SKIP** (apply error). Drains pending (forget) on success. UPDATE-merge + DELETE deferred to Phase-4 LLM (heuristic text-rewrite = unsafe); `related_ids` deferred (no CLI flag). `--surface` = quiet-when-empty preview for SessionStart. Live-proven on canaries: j=0.90 bump (seen→2, medium→high) + add, pending drained, ICM restored. 16 curate tests, 138 total green. | SessionStart shim = manual |
| 4 | **DONE (scaffold + first signal; needs more fixtures)** `bench/_reflection_ab.py` — heuristic vs DeepSeek arms on a synthetic gold transcript (paraphrase-fair natural markers; 3 explicit mistakes + 1 silent-bug + 4 distractors). Result: both F1≈0.86 P=1.0 R=0.75, but heuristic 0.16ms/$0 vs DeepSeek 2141ms/$0.00025 and a **different miss** (heuristic blind to silent-bug; DeepSeek drops terse user correction). Verdict → decision #6 updated: heuristic default + LLM silent-bug pass (hybrid); pure-LLM not worth per-session cost. **Hybrid BUILT** (`paw/reflect_llm.py` + `paw reflect --llm`): local regex pre-filter keeps only suspicious *successful* results (→ $0 when none), one batched DeepSeek call confirms genuine silent bugs → `type:silent-bug` candidates. Opt-in (off on hooks). Live-proven: heuristic blind to an exit-0 `test_flow_timeout FAILED`, `--llm` caught it. 6 bench + 10 reflect_llm tests. Multi-fixture stability + live-CC/Codex arms = TODO. | — |
| 5 | suggest-graduate (`seen:N≥thr` + procedural-shape → flag candidate skill); periodic `icm consolidate` **⚠️ only with `--keep-originals` AND `--summarizer-provider <llm>`** (bare/provider=none JOINS the whole topic into one ' \| ' blob and DELETES originals — lossy, not summarization) | — |

## Open risks
- Codex Stop payload/transcript schema (Phase 0 residual) → gates Codex capture.
- DeepSeek API $ for reflection → bench before lock.
- Bench gold set needs hand-labeled transcripts.
