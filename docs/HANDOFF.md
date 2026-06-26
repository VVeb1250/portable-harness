# Handoff → Codex (memory system)

> Written by Claude (Opus 4.8) 2026-06-26, branch `docs/bundle-scout-vets`.
> Cross-host continuity also in the **ICM blackboard** (`paw blackboard read
> --project portable-harness --run-id memory-2026-06-26 --kind handoff`).
> Full spec: `docs/MEMORY-PLAN.md`. Per-pillar detail: `docs/STATUS.md`.

## What exists now (built + tested + live)

The behavioral memory loop is **code-complete and host-uniform** (CC + Codex):

```
session → [Stop] paw reflect --capture → ICM `pending`
                    (+ [--llm] DeepSeek silent-bug pass, opt-in)
        → [SessionStart] paw curate --surface → reconcile vs recall
                    → ADD new | BUMP recurrence(seen:N, escalate) → ICM wiki
        → [UserPromptSubmit] paw_block + paw recall → surface lessons
```

- **Capture** (`paw/reflection.py`): host-dispatched transcript parse. CC =
  `message.content[]` tool_use/tool_result(`is_error`). Codex = `response_item`
  payloads (function_call/custom_tool_call ↔ `*_output` by `call_id`; no
  is_error → derived from the output's `Exit code: N`). Noise filters:
  permission-denial / `nah`-guard / compact / meta dropped; misalignment =
  terse(≤240c) + strong marker. Incremental per-session watermark
  (`~/.paw/state/reflect/<sid>.json`) — Stop fires per turn, so only new lines
  are scanned. `pending` is excluded from `paw recall`.
- **Curate** (`paw/curate.py`): reconciles each pending vs `paw recall` top-K by
  Jaccard. ADD (new) / BUMP (≥0.5 → `seen:N`++ , escalate seen≥3→critical) /
  SKIP. Drains pending. UPDATE-merge + DELETE deferred (LLM judgement).
- **Hybrid** (`paw/reflect_llm.py`, `paw reflect --llm`): opt-in DeepSeek pass
  for the silent-bug class (success-with-failure) the heuristic is blind to.
  Local pre-filter → $0 when nothing suspicious; OFF on the live hooks.
- **Bench** (`bench/_reflection_ab.py`): heuristic vs DeepSeek. On the gold set
  both F1≈0.86 but pure-LLM not worth per-session cost → hybrid is the verdict.

Hooks wired (personal files, not in repo): CC `~/.claude/settings.json` and
Codex `~/.codex/hooks.json` Stop→`paw reflect --capture [--host codex]`,
SessionStart→`paw curate --surface`. 160 tests green.

## Your first task (it's literally yours to verify)

**Confirm Codex capture fires end-to-end.** The Codex Stop-hook *stdin* shape is
unverified — capture has a fallback that resolves your rollout under
`~/.codex/sessions` (by session-id in the filename, else newest), but no live
Codex Stop has been observed. So:

1. Work normally for a few turns (make a real shell error somewhere).
2. `icm.exe list -t pending --format json --no-embeddings --read-only` — your
   mistakes should appear with `type:` / `session:` keywords.
3. Check the watermark advanced: `~/.paw/state/reflect/<your-session>.json`.
4. If pending stays empty: inspect what the Stop hook receives on stdin
   (`paw reflect --capture --host codex` reads `{transcript_path, session_id}`),
   and confirm `newest_codex_transcript()` matched YOUR rollout (filename carries
   the session uuid). Fix the resolver or add the right stdin key.

Manual dry-run any time: `py -m paw reflect --capture --host codex --transcript
<rollout.jsonl> --dry-run`.

## Then (optimization, not core)

- **Phase 5 — graduate** (`docs/MEMORY-PLAN.md` row 5): suggest a candidate skill
  when a lesson recurs (`seen:N ≥ thr`) and is procedural-shaped. Human-gated —
  never auto-write a skill. Add `paw graduate` (suggest-only).
- **Bench hardening**: more fixtures + multi-run stability; add live-CC / live-Codex
  arms to `bench/_reflection_ab.py`.
- **Tune live pending**: watch real captures. Known candidate noise — pytest
  failures during TDD are expected red, not mistakes; consider filtering
  test-run exit codes in `paw/reflection.py` `_exec_candidates`.

## Guardrails (do not violate)

- `icm consolidate` **only with `--keep-originals --summarizer-provider <llm>`** —
  bare/`provider=none` joins the whole topic into one ` | ` blob and DELETES
  originals (data loss; recovered once already).
- `nah` guards hook *scripts* (e.g. `skill-router.py`). Hook *config* files
  (`settings.json`, `hooks.json`) are editable.
- Windows: `py` only; backslash paths; call `icm.exe` (not bare `icm`).
- Storage split, recall unified: experiential → ICM; conventions/ADR → AGENTS.md
  family. `pending` is never recalled into the wiki until curation promotes it.
