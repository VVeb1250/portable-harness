# GateGuard — Problem Statement

> Draft. Problems only — solution/redesign to be refined separately.
> Evidence base: a full working session (issue-triage bot build on
> `coe-workshop.github.io`, ~12 file writes/edits + several destructive
> git ops) where the fact-forcing gate fired ~10 times.

## What GateGuard currently does

Before the first `Bash`, before every `Write`/`Edit`, and before
destructive commands, the gate **denies the call** and requires the agent
to emit a "facts" block first:

- list importers/callers of the file
- confirm no existing file serves the same purpose
- data schema (if it touches data)
- one-line rollback (destructive)
- quote the user's verbatim instruction

The agent restates these, then retries the identical call.

## Core design flaw: it forces a *report*, not *grounded truth*

The gate compels the agent to **state** facts, but never verifies the
statements are real. The facts are generated from the agent's own context
— the exact place a hallucination lives. So:

- A confused agent satisfies the gate by **confidently writing wrong
  facts** ("nothing imports this") and proceeds anyway.
- Self-report is not verification. The ritual assumes "if you slow down
  and articulate, you'll catch yourself" — sometimes true, but it trusts
  the agent's own claims as evidence.

The gate raises *friction*, not *correctness*. Those are not the same axis.

## Empirical result this session: cost >> benefit

- **Caught: nothing.** ~10 gates, all passed by restating facts already
  known. Zero clobbered files, zero rollbacks used, zero unknown
  duplicates surfaced.
- **The one genuinely risky moment** (force-push rewriting a shared `dev`)
  was stopped by the **branch ruleset**, not GateGuard.
- **Live irony:** the gate even fired on the creation of THIS problem doc
  — a markdown file with no importers, no API, no schema — forcing
  degenerate boilerplate to write a critique of that very behavior.
- **Measurable overhead:**
  - token bloat — verbose prose facts per gate; contributed to hitting
    ~81% context budget
  - cost — session ran to $70+, gate ceremony a non-trivial slice
  - latency — every gated action is a double round-trip (deny → facts →
    retry)

## Failure mode: template doesn't fit non-code artifacts

The required facts ("who imports this", "affected functions", "data
schema") assume a file with a **call graph**. For standalone artifacts —
GitHub Actions YAML, config, docs — the answers are **degenerate**:

> "Nothing imports it; it's a workflow triggered by an event."

The agent is forced to emit boilerplate noise to satisfy a check that has
no signal for that file type. Most of this session's writes were workflow
YAML → almost all gate output was degenerate.

## Failure mode: doesn't compose with team / multi-agent

- Each agent pays the output tax independently.
- Self-reported facts **don't transfer between agents** — there's no
  shared ground truth. Agent A's impact claim and Agent B's can disagree,
  so the gate gives an *illusion* of rigor while agents still risk
  clobbering the same symbol.
- The gate is a per-agent ritual, not a shared substrate. A team harness
  needs the latter.

## Failure mode: friction is uniform, risk is not

Every write is gated identically — a one-line comment tweak in an
untracked YAML pays the same ceremony as deleting a shared data file. The
gate has no notion of **blast radius**, so it taxes the safe 95% to
maybe-help the risky 5%.

## Secondary: the recovery hatch undercuts the gate

The denial message advertises `ECC_GATEGUARD=off` /
`ECC_DISABLED_HOOKS=...`. An agent optimizing for throughput is nudged
toward disabling the gate rather than engaging with it — so the gate is
both heavy *and* easy to switch off wholesale (all-or-nothing, no
middle).

## Summary of problems

1. Forces self-report, not verification → ungrounded; can rubber-stamp
   hallucinations.
2. Net negative cost/benefit on this session (caught nothing, taxed
   everything).
3. Fact template has no signal for non-code files (YAML/config/docs) →
   degenerate boilerplate.
4. Doesn't compose across agents — no shared truth, illusion of rigor.
5. Uniform friction, blast-radius-blind.
6. All-or-nothing kill switch invites bypass over engagement.

## Open questions (for the refinement pass)

- Should the gate's required evidence come from a **ground-truth index**
  (e.g. CodeGraph `callers`/`impact`) instead of agent prose?
- Should it **auto-skip** files not covered by that index?
- Keep a thin destructive-op gate (rollback line) for things the index
  can't cover (git/data)?
- Scope by blast radius / directory instead of uniform firing?
