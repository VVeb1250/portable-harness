# No-Daemon Baseline Backlog

Purpose: keep future sessions focused. The current plan is still
no-daemon / CLI-first until the baseline is usable. Optional sidecar, Memoir
graphing, and marketplace integrations are later experiments, not the next
default work.

## Priority -1 — Stop AI Wandering / Bundle Coherence

This outranks the feature backlog. The bundle is currently too easy for resumed
agents to misread: historical drafts look actionable, root context files contain
large generated capability blocks, and live capabilities such as Context7 and
context-mode are wired but not reliably routed.

1. Freeze bundle churn until the source-of-truth chain is clean.
   - Do not add new sets, sidecars, Memoir flows, or marketplace imports while
     the entrypoint docs and managed blocks disagree.
   - Done when: `CLAUDE.md`, `AGENTS.md`, `bundle/AGENTS.md`, `docs/README.md`,
     and `docs/STATUS.md` all point to the same next-work queue.

2. Reconcile generated capability blocks.
   - Current symptom: root AI context files can accumulate large paw capability
     blocks and stale commands, making every resumed session expensive and
     confusing.
   - Work: define which file is the generator source, which files are active
     bridges, and which blocks are managed vs hand-written. Then remove or
     regenerate stale blocks deliberately.
   - Done when: no agent has to infer whether a block is source, generated
     output, or historical residue.

3. Add a routing contract for live knowledge tools.
   - Current symptom: Context7 and context-mode are healthy but unused unless
     the agent remembers them manually.
   - Work: encode trigger rules:
     - library / SDK / CLI / API docs -> Context7 first when available;
     - bulky output / many files / logs / JSON with embeddings / diff summaries
       -> context-mode first;
     - exact edit text / short fixed output / filesystem mutations -> normal
       shell/read/apply_patch.
   - Done when: the route is visible in docs and enforced by review/telemetry,
     even if not yet automatic.

4. Add a preflight "what should I read?" command or checklist.
   - Current symptom: resumed agents choose their own docs and often follow old
     TODOs.
   - Work: one command/checklist that prints current truth, backlog P-1/P0,
     active tools, and parked experiments.
   - Done when: a fresh AI can answer "what is the next correct thing?" without
     reading every markdown file.

## Priority 0 — Make Paw Feel Helpful, Not Noisy

1. Reduce router false positives.
   - Current symptom: unrelated skill/set nudges still appear.
   - Work: thresholds, cooldowns, negative rules, and minimal telemetry.
   - Done when: irrelevant suggestions are rare and explainable.

2. Fix `paw route` over-routing.
   - Current symptom: small/simple work can still choose a team route.
   - Work: make simple + low/medium risk default to solo/local unless strong
     complexity signals exist.
   - Done when: small bug fixes do not invoke a team by default.

3. Make pending curation safe and useful.
   - Current symptom: `pending` is noisy and can promote command noise.
   - Work: dry-run-first workflow, better classification, safer topic routing,
     and stronger skip rules.
   - Done when: useful user corrections are promoted and command noise is
     skipped or quarantined.

4. Audit memory hook coverage.
   - Current symptom: hooks register/poll, but capture coverage is not fully
     proven, especially Codex Stop payload/transcript shape.
   - Work: smoke SessionStart, UserPromptSubmit, Stop, capture, poll, and
     heartbeat on Claude and Codex.
   - Done when: each event has evidence and known gaps are explicit.

5. Add real `paw init` / `paw doctor` commands.
   - Current symptom: status requires several manual commands.
   - First slice live: `python -m paw init|doctor` now checks default core
     binaries, emits missing-tool install hints, reads linker ledger state, and
     reports hosts that need restart/reload after paw-owned MCP/PATH wiring.
   - Work: verify the default core (`local-memory`, `efficiency-min`,
     `secure-agent`, `doc-data-min`), report missing tools with per-OS install
     hints, report ICM topics, pending count, hook config, mesh members, stale
     sessions, linker state, router state, and which host sessions need restart
     after config/env changes.
   - Remaining: add ICM topic/pending count, hook config, mesh stale-session
     summary, and richer linker drift state into the same report.
   - Done when: one command answers "is paw basically working, what is missing,
     and do Claude/Codex/Gemini need restart?"

## Priority 1 — Reduce Manual Prompt Tax

6. Define recall/store/poll trigger policy.
   - Current symptom: agent/user must remember when to recall, store, poll, and
     curate.
   - Work: short policy and wrappers for task start, decision capture,
     fail-fix capture, session end, and multi-session polling.

7. Exercise mesh beyond presence.
   - Current symptom: live mesh shows members, but not real handoff workflow.
   - Work: examples and shortcuts for post, poll, promote, and lock.

8. Fix output hygiene.
   - Current symptom: raw ICM JSON can include embeddings and blow context.
   - Work: summary-only wrappers and docs that prefer human/toon/no-embedding
     output.

9. Add router/nudge telemetry.
   - Current symptom: false-positive rate is anecdotal.
   - Work: log suggestion, reason, context, and accepted/ignored heuristic.

## Priority 2 — Bundle Full-Performance Work

10. Build the code-intelligence shootout.
    - Compare CodeGraph, codebase-memory-mcp, Serena, grepai, and the
      `rg`/`ast-grep` baseline.
    - Tasks: find callers, trace route to handler, impact analysis, config
      tracing, architecture query, and "what changes if symbol X changes?"
    - Metrics: correctness, file reads/tool calls, input/output tokens, wall
      time, setup/index time, cleanup/unlink behavior, privacy/network behavior,
      MCP/tool-schema tax, and Windows/macOS/Linux friction.
    - Done when: `code-intelligence` has a measured default, measured
      fallbacks, and explicit cases where plain `rg`/`ast-grep` still wins.

11. Add a Windows-safe wrapper for `codebase-memory-mcp`.
    - Current symptom: local bench passed, but JSON argv/PowerShell quoting is
      fragile.
    - First slice live: `python -m paw codebase-memory project-name|index|search`
      builds JSON in Python and invokes `codebase-memory-mcp` through argv,
      bypassing PowerShell JSON quoting. Local smoke indexed `tests/` and
      searched `DoctorTests` successfully.
    - Work: expose a paw command or wrapper that invokes the binary with argv
      directly, avoids shell JSON quoting, and returns bounded output suitable
      for agents.
    - Remaining: add output shaping/limits for agent use and wire this wrapper
      into the code-intelligence shootout runner.
    - Done when: index/search smoke works from PowerShell without hand-escaped
      JSON and can be used in the shootout.

12. Bench grepai only after local embeddings are intentionally installed.
    - Current symptom: grepai is promising but blocked by missing Ollama/local
      embeddings.
    - Work: install or document a small local embedding setup only when the user
      explicitly chooses that benchmark path; then compare it against
      CodeGraph/codebase-memory and `rg`/`ast-grep`.
    - Done when: grepai is either promoted into `code-intelligence`/developer
      profile with evidence, or kept deferred with a clear reason.

13. Bench repo-pack: Repomix vs code2prompt.
    - Compare scoped directory packing, git diff/log packing, remote repo
      support, token-count accuracy, output quality for agents, install story,
      and cross-OS behavior.
    - Add a scope guard before any promotion: broad repo packing must require
      include/exclude scope, split output, metadata-only mode, or an explicit
      override.
    - Done when: `repo-pack` has a measured primary tool and cannot accidentally
      dump an oversized whole-repo artifact into an agent context.

14. Add cross-OS CI smoke for the default foundation sets.
    - Cover `efficiency-min`, `secure-agent`, and `doc-data-min` on Windows,
      macOS, and Linux.
    - Smoke only the deterministic core: binary detection, help/version probes,
      one tiny functional command per tool, and compact failure output.
    - Done when: default-init claims are backed by CI rather than local Windows
      evidence only.

15. Cleanup `efficiency-starter` only after migration is proven safe.
    - Current posture: `efficiency-starter` is a legacy compatibility alias for
      `efficiency-min` plus project-linked `code-intelligence`.
    - Work: verify existing managed blocks, router hints, host configs, and
      docs no longer depend on the old set name before removing or shrinking
      the alias.
    - Done when: old installs keep working, new installs prefer the split sets,
      and removing stale docs cannot strand existing users.

## Priority 3 — Linker, ECC, and Release Hardening

16. Add real ECC detector for `harness-foundation`.
    - Surface `present`, `absent`, and `conflict`.

17. Decide canonical ECC install state.
    - Resolve plugin vs manual/profile state before wiring more behavior.

18. Keep `harness-foundation` out of blind batch installs.
    - It stays detect-first until the detector exists.

19. Apply host tradeoff policy before promoting ECC hooks/rules.
    - Wrap/select only; do not copy the ECC hook bundle wholesale.

20. Add broader Linux/macOS CI.
    - Cover router, blackboard, Team Kernel, and non-foundation bundle smoke
      after the default foundation CI is in place.

21. Write release/no-daemon quickstart.
    - One page for memory, router, mesh, curation, and known limitations.

22. Run a new dated bench cohort.
    - Re-measure team economics with mutate -> verify on another fixture/repo.
    - Never append to the frozen N=8 cohort.

## Deferred Experiments

23. Optional local sidecar.
    - Only revisit after the no-daemon baseline is usable.
    - Must measurably reduce manual prompts, missed captures, hook complexity,
      or coordination lag while staying local-only, CLI-compatible,
      no-MCP-required, and graceful when absent.

24. ICM Memoir pilot.
    - Do not use Memoir as a pending drain.
    - Later safe pilot: one `portable-harness` memoir distilled only from
      curated `decisions` and `lessons`, then export/search the graph.

25. `skills.sh` / `npx skills` bundle.
    - Treat as external `SKILL.md` package distribution only.
    - Do not activate hooks, commands, MCP config, credentials, or host settings
      through skill import.
    - Paw/ECC linker verifies runtime dependencies separately.

## Explicit Non-Goals For Now

- Mandatory daemon.
- Memoir from raw `pending`.
- Building a skill marketplace.
- Copying ECC hooks wholesale.
- Claiming uniform automatic behavior across hosts.
