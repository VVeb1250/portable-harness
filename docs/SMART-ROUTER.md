# paw Smart Router

> Working design draft — zero-AI, just-in-time capability routing.

## Purpose

Smart Router watches what an agent is about to do and surfaces the smallest
useful piece of help at the right moment:

- a skill whose workflow fits the task;
- an MCP or tool capability worth using;
- a relevant mistake memory that prevents a known failure.

It is not an agent/team orchestrator. It does not choose a planner,
implementer, or reviewer. The existing team-routing experiment is a separate
concern and should eventually use a different name.

The core promise is:

> Before the agent acts, retrieve the capability or correction most likely to
> help now — otherwise remain silent.

## Scope vs project concept (build vs rent)

The detailed design below specifies a full retrieval + ranking + feedback engine
for all three lanes. That is the north-star reference, not the v0 build target.
A prior analysis (per `docs/ARCHITECTURE.md` §11.4) concluded that two of the
three lanes should be *rented* from native host mechanisms, and only the mistake
lane is genuine net-new value worth building now.

| Lane | Verdict | Mechanism to rent | Why |
| --- | --- | --- | --- |
| Skill | RENT native | Native Skill discovery (name+description menu → `Skill` tool, progressive load) + the existing `~/.claude/hooks/skill-router.py` hook | A zero-AI lexical skill router already exists (TF-IDF cosine + curated intent-phrase boost from `skill-graph.json` + cooldown + outcome-demotion + a tier-2 MiniLM ONNX fallback for Thai/CJK). Rebuilding it as FTS5 is a reimplementation of retrieval that already ships. |
| MCP / capability | RENT discovery + FOLD metadata into the bundle catalog | Native Tool Search for runtime PULL (deferred tools show name only at 0 schema tokens/turn; the agent forms a query — `keyword`, `select:Name`, `+require` — to load schemas on demand, including still-connecting servers). Host/availability/cost metadata lives in `paw/registry/sets.json` as curation, not a runtime ranking engine. | Tool Search is agent-PULL, matching locked decision A-15 (capability lane = PULL, not push). It removes the discovery-tax; loaded schemas still cost tokens per turn, so delivery-tax A-08 is only half-solved — but a custom router would not solve that either. The registry's job is curation, not retrieval. |
| Mistake | BUILD now | None — no native equivalent | `before_tool` exact tool+operation+project match → `icm recall <command>` → `warn`, delivered via a PreToolUse hook. Fully deterministic (no Thai/lexical risk), and the project's locked durable value (A-16, `docs/ARCHITECTURE.md` §11.2 / §11.4 value (b)). |

### Why rent

The smart-ceiling of any zero-AI lexical router is the same low class regardless
of implementation: FTS5/BM25 == TF-IDF == Tool Search's lexical retrieval. The
FTS5/BM25 skill+capability ranking proposed below would be a fourth
reimplementation of retrieval that already exists in `~/.claude/hooks/skill-router.py`
and native Tool Search. The genuine intelligence in capability routing is the
**agent + explicit PULL query**, not the router — which is exactly why
`docs/ARCHITECTURE.md` §11.4 scopes it as rent: "router/search = commodity,
platform absorbing — Tool Search / skills / memory-tool. VALUE = curation ·
action-keyed mistake-layer · cross-host. build these 3; rent the rest."

A push-style skill-suggester already exists and measures ~8% real-world uptake
(suggestions ignored 92% of the time). Pushing a skill from a free-text
`task_received` description is the exact failure mode of the archived `portaw`
blind-push — locked decision A-15 — where an all-Thai prompt yielded TF-IDF=0
and then a spurious tier-2 semantic match. The mistake lane has none of this
risk because it matches on exact structured fields, never on prose.

## Design constraints

1. No generative AI in the routing path.
2. No embedding model in the first implementation.
3. No network request required to make a routing decision.
4. Silence is better than a weak suggestion.
5. Suggestions must explain why they appeared.
6. The normal result is zero to two suggestions.
7. A suggestion does not install, enable, or execute anything automatically.
8. Security policy may warn or block; ordinary recommendations may not.
9. The same router contract must work across Codex, Claude Code, Gemini, and
   hosts with weaker event support.
10. Every routing decision must be reproducible from the event, registry,
    memories, and policy version.

## High-level flow

```text
Host event
  → normalize event context
  → decide whether this event is worth routing
  → retrieve lexical candidates from three lanes
  → apply metadata and policy filters
  → score and deduplicate
  → pass confidence and cooldown gates
  → return 0–2 explainable suggestions
```

The three retrieval lanes are:

```text
Skills catalog ─┐
MCP/tool catalog ├─→ one shared ranking and policy layer
Mistake memory ─┘
```

## Event model

The router should not run on every message or tool call. It should receive a
small set of meaningful lifecycle events.

### Initial events

| Event | Purpose |
| --- | --- |
| `task_received` | Suggest a workflow skill or capability at the start |
| `before_tool` | Prevent a known misuse or suggest a better capability |
| `after_error` | Retrieve a correction or recovery workflow |

### Possible later events

| Event | Purpose |
| --- | --- |
| `before_plan` | Suggest planning/research workflows for complex work |
| `before_write` | Surface file/config-specific safeguards |
| `before_external_action` | Surface publishing, deployment, or credential policy |
| `task_complete` | Record feedback and confirmed reusable lessons |

### Minimal event contract

```json
{
  "schema": "paw-router-event/v1",
  "event": "before_tool",
  "project": "portable-harness",
  "host": "codex",
  "task": "Inspect the code dependency graph",
  "action": {
    "tool": "codegraph",
    "operation": "init",
    "target": "E:/portable-harness"
  },
  "signals": {
    "files": [],
    "error_codes": [],
    "attempt": 1
  }
}
```

Only fields available on a host need to be populated. Missing context should
lower confidence rather than cause the router to invent context.

## Candidate sources

### Skill lane

Each skill needs routing metadata separate from its full instructions:

```yaml
id: diagnose
kind: skill
events:
  - task_received
  - after_error
task_kinds:
  - debugging
triggers:
  - intermittent failure
  - regression
  - reproduce
  - root cause
file_patterns: []
requires:
  - shell
cost: medium
overlaps:
  - debug-by-logging
```

The router retrieves metadata only. The host loads the full skill after the
agent or policy accepts the suggestion.

### MCP/tool lane

The router should recommend a capability, then name the best available
delivery mechanism.

```yaml
id: current-library-docs
kind: capability
events:
  - task_received
  - before_tool
triggers:
  - latest API
  - current documentation
  - version-specific behavior
providers:
  - id: context7
    type: mcp
    hosts: [codex, claude-code, gemini]
  - id: official-web-docs
    type: native
    hosts: ["*"]
prefer:
  - already_available
  - native
  - cli
  - mcp
```

This prevents the catalog from treating an MCP server as the product. The
product is the capability; MCP is one possible transport.

The lane must filter candidates by:

- host support;
- current availability;
- permissions and network requirements;
- secrets or environment requirements;
- overlap with native/CLI capabilities;
- active MCP count and context cost;
- project policy.

The first version only recommends already available capabilities. It does not
install or enable an MCP automatically.

### Mistake-memory lane

Mistakes should be stored as structured corrections rather than raw
conversation memories:

```yaml
id: codegraph-never-init
kind: mistake
scope:
  projects:
    - portable-harness
events:
  - before_tool
match:
  tools:
    - codegraph
  operations:
    - init
summary: Do not initialize CodeGraph in this repository.
fix: Use rg and context-mode; retain CodeGraph as an external augment only.
importance: high
confidence: 1.0
evidence: docs/BUNDLE.md
```

Useful mistake fields:

- project, host, language, or global scope;
- matching tools, commands, operations, files, and error codes;
- concise trigger;
- confirmed correction;
- importance;
- confidence;
- evidence;
- expiry or recheck trigger;
- number of confirmed recurrences.

The router must never inject the full memory record. It returns only the
smallest correction needed for the current event.

## Retrieval

> Reference north-star. This full lexical design applies only IF a custom router
> is ever justified. For v0 the skill and capability lanes ride native Tool
> Search plus the existing `~/.claude/hooks/skill-router.py` hook, so this
> machinery is built only for the mistake lane's exact-match path initially.

The initial router uses lexical retrieval only:

- structured exact matching;
- normalized trigger matching;
- SQLite FTS5/BM25 for free text;
- aliases and curated synonyms;
- file, tool, command, host, and event indexes.

No vector database or model is required.

### Query construction

Construct a bounded search document from:

```text
task
event
tool and operation
target file/path
error code and short error summary
host and project
```

Do not index or query with:

- secrets;
- full source files;
- full command logs;
- full transcripts;
- generated model reasoning.

### Exact-match fast path

Structured matches should take priority over free-text retrieval.

Examples:

```text
tool=codegraph + operation=init + project=portable-harness
  → exact mistake match

event=after_error + error_code=ModuleNotFoundError
  → error-specific recovery candidates

file=package.json + task contains dependency audit
  → security/dependency skill candidates
```

FTS5 is primarily for natural-language task descriptions and error summaries,
not for facts already represented as fields.

## Ranking

> Reference north-star, as with *Retrieval* above. For v0 only the mistake
> lane's exact-match path is built; skill/capability ranking is rented from
> native Tool Search and the existing hook until a frozen eval proves a gap.

Use a deterministic score whose components are visible in diagnostics.

```text
score =
    exact_match
  + lexical_relevance
  + event_fit
  + scope_fit
  + impact
  + confidence
  + prior_helpfulness
  + availability
  - overlap
  - interruption_cost
  - context_cost
  - cooldown
```

Suggested ordering of importance:

1. exact tool/operation/error match;
2. project and host scope;
3. event timing;
4. lexical relevance;
5. importance and confidence;
6. availability;
7. historical feedback;
8. cost and overlap penalties.

Weights should be tuned from an evaluation set, not intuition alone.

### Cross-lane priority

Default priority:

```text
direct high-confidence mistake
  > required security/policy guard
  > strongly matched skill
  > already-available capability
  > optional MCP suggestion
```

This is not a permanent hard-coded ordering. It expresses the principle that
preventing a known failure is usually more valuable than adding another
capability.

## Silence policy

Silence is a first-class output:

```json
{
  "schema": "paw-router-result/v1",
  "status": "success",
  "suggestions": [],
  "reason": "no_candidate_passed_threshold"
}
```

The router should remain silent when:

- no candidate passes the lane threshold;
- the top candidates are too close and neither is necessary;
- the suggestion was recently shown for the same task;
- the capability is already being used;
- the candidate is unavailable and installation was not requested;
- the match depends only on a common word;
- the event contains too little context;
- the likely interruption cost exceeds the expected benefit.

It should not call AI to break a tie. An ambiguous result means the router does
not know enough and should stay quiet.

## Suggestion actions

The output vocabulary should remain small:

| Action | Meaning |
| --- | --- |
| `offer` | Relevant option; agent may ignore it |
| `recommend` | Strong expected benefit |
| `warn` | Known mistake or important risk; must be visible |
| `block` | Deterministic security/policy violation only |

Skills and MCPs normally produce `offer` or `recommend`.

Mistakes normally produce `warn`.

Only a separate, explicit policy rule may produce `block`. A retrieved memory
alone must never block an action.

## Result contract

```json
{
  "schema": "paw-router-result/v1",
  "status": "success",
  "event": "before_tool",
  "suggestions": [
    {
      "id": "codegraph-never-init",
      "kind": "mistake",
      "action": "warn",
      "summary": "Do not initialize CodeGraph in this repository.",
      "reason": "Exact project, tool, and operation match.",
      "score": 0.97,
      "confidence": 1.0,
      "source": "mistake-memory",
      "next_action": "Use rg or context-mode for this repository."
    }
  ],
  "diagnostics": {
    "router_version": "v0",
    "policy_version": "v0",
    "candidates_considered": 4
  }
}
```

Human output should be shorter:

```text
Warning: do not initialize CodeGraph in portable-harness.
Use rg or context-mode; this repo deliberately keeps CodeGraph external.
```

## Cooldown and deduplication

Without state, even accurate suggestions become annoying.

Track:

- suggestion ID;
- task or run ID;
- event type;
- first and last shown time;
- accepted, ignored, dismissed, or helped outcome;
- number of repeats;
- relevant action fingerprint.

Initial rules:

- do not repeat an `offer` within the same task;
- repeat a `warn` only if the risky action is attempted again;
- suppress a skill once the skill is active;
- merge candidates that recommend the same capability;
- choose one winner from strongly overlapping skills;
- cap output at two suggestions per event;
- cap each lane at one suggestion unless a policy warning is present.

## Feedback

Feedback improves deterministic ranking without training a model.

Useful outcomes:

```text
accepted
dismissed
helped
irrelevant
already_known
mistake_prevented
mistake_repeated
```

Feedback should adjust bounded metadata such as:

- helpfulness count;
- false-positive count;
- per-project threshold;
- cooldown duration;
- trigger aliases;
- confidence of a mistake;
- deprecation or expiry state.

Do not mutate core policy weights online after every event. Review accumulated
feedback and update a versioned configuration so decisions remain reproducible.

## Host delivery

The router core returns the same result everywhere. Host adapters determine
when events are available and how suggestions appear.

| Host capability | Delivery |
| --- | --- |
| lifecycle hooks | route automatically at supported events |
| prompt/session hook only | route at task start and major transitions |
| no hooks | explicit `paw suggest` or wrapper integration |
| native skill discovery | return skill ID for native loading |
| no native skill loading | show the skill path or usage instruction |

Host adapters must not change ranking logic. They only translate events and
deliver results.

## Relationship to existing paw components

### `paw sets`

The current set registry becomes one source of capability metadata. It needs
more event, trigger, overlap, availability, and cost fields before it can
support precise routing.

### Current `paw route`

The current command routes tasks to agent roles. It should not define the
meaning of Smart Router.

Possible future naming:

```text
paw suggest             # Smart Router diagnostic/manual entrypoint
paw team plan            # existing agent/team route decision
paw team run             # future Team Kernel execution
```

The Smart Router will normally run through host events rather than requiring
the user to invoke `paw suggest`.

### ICM

ICM remains the durable memory backend. Smart Router should query a
mistake-specific, structured lane rather than perform broad recall over all
memories.

If ICM cannot expose the required filters efficiently, paw may maintain a
small local routing index containing references to ICM records. ICM remains
the source of truth; the routing index is disposable.

## MVP

Per *Scope vs project concept* above, the MVP collapses to the **mistake lane
only** (vertical slice #1 plus the silence slice #4). The skill and capability
lanes defer to rented native mechanisms — native Tool Search and the existing
`~/.claude/hooks/skill-router.py` hook — until a frozen evaluation proves native
recall is insufficient. The fuller list below remains the north-star target.

The first useful version should be intentionally narrow.

### Inputs

- three events: `task_received`, `before_tool`, `after_error`;
- skill metadata from locally available skills;
- MCP/tool metadata from the paw registry and host inventory;
- structured mistake memories from ICM;
- project and host context.

### Routing

- exact structured matches;
- SQLite FTS5/BM25;
- deterministic filters and scoring;
- threshold and silence policy;
- cooldown and deduplication;
- no AI, embeddings, network, installation, or automatic execution.

### Outputs

- zero to two suggestions;
- `offer`, `recommend`, or `warn`;
- concise reason;
- stable JSON contract;
- optional diagnostics explaining the score.

### First vertical slices

1. `before_tool` retrieves an exact project-specific mistake.
2. `task_received` recommends one strongly matching skill — *deferred — rented
   via native Tool Search / existing `skill-router.py` hook; revisit only if eval
   shows a gap.*
3. `after_error` retrieves a confirmed correction or recovery skill — *deferred —
   rented via native Tool Search / existing `skill-router.py` hook; revisit only
   if eval shows a gap.*
4. An unrelated event returns no suggestions.
5. A repeated suggestion is suppressed by cooldown.

## Evaluation

Build a frozen event corpus before tuning weights.

Each event should label:

- expected suggestions;
- suggestions that would be acceptable but unnecessary;
- suggestions that are wrong;
- whether silence is the desired result;
- whether a warning is required;
- available host capabilities.

Primary metrics:

| Metric | Why it matters |
| --- | --- |
| Precision@1 | The first suggestion must usually be right |
| Precision@2 | Measures the complete visible recommendation set |
| Silence accuracy | Prevents notification spam |
| Required-warning recall | Known mistakes must not be missed |
| Duplicate rate | Measures cooldown quality |
| Unavailable suggestion rate | Router should not recommend unusable tools |
| Mean output size | Protects context budget |
| Decision latency | Router must remain cheap enough for hooks |

Initial quality bias:

```text
optimize precision and silence first;
accept lower recall until evidence supports broader triggers.
```

A router that surfaces five plausible ideas is not high quality. A router that
usually stays quiet and catches the one expensive mistake is.

## When to consider semantic retrieval

Do not add embeddings because they sound more intelligent.

Consider a local semantic layer only if the frozen evaluation shows a material
lexical failure, such as:

- Thai and English descriptions frequently miss each other;
- paraphrased tasks miss the correct skill despite curated aliases;
- mistake recall requires too many brittle trigger phrases;
- lexical recall remains poor after metadata and synonym improvements.

Even then:

1. keep exact matching and FTS5;
2. add semantic retrieval as another candidate source;
3. fuse results deterministically;
4. preserve the same thresholds and silence policy;
5. require a measured quality gain large enough to justify model size,
   startup time, packaging, and cross-host complexity.

Generative AI is not part of the fallback path. Ambiguity still resolves to
silence.

## Alternative: AI-lite hybrid router

The zero-AI router is the default recommendation, but a second design is worth
keeping as an experimental arm. Its goal is to spend a very small amount of AI
only where lexical routing has already demonstrated uncertainty.

The AI does not search the full catalog, generate suggestions, or override
policy. It receives a tiny, pre-filtered candidate set and performs one bounded
classification:

```text
host event
  → exact matching + FTS5/BM25
  → deterministic filters and scoring
  → confidence gate
      ├─ clear winner → return without AI
      ├─ no useful candidate → remain silent
      └─ narrow ambiguity → AI adjudicates 2–3 candidates
  → deterministic policy and output limits
```

### What AI is allowed to do

Given the event and at most three candidates, return:

```json
{
  "choice": "diagnose",
  "relevant": true,
  "reason_code": "repeated_failure_needs_structured_diagnosis"
}
```

It may:

- choose one candidate;
- reject all candidates;
- map paraphrased intent to a fixed reason code.

It may not:

- invent a skill, MCP, memory, command, or policy;
- retrieve additional context;
- install or execute anything;
- produce user-facing prose;
- lower a deterministic security restriction;
- turn an `offer` into a `warn` or `block`;
- see secrets, source files, transcripts, or full logs.

### When AI may run

All conditions must hold:

1. no exact structured match exists;
2. the top lexical candidates pass a minimum relevance threshold;
3. their scores are too close for a reliable deterministic choice;
4. selecting the wrong candidate has meaningful interruption cost;
5. the event is not on a latency-critical path;
6. the per-session AI-routing budget is not exhausted.

Example gate:

```text
top score ≥ candidate threshold
score(top1) - score(top2) < ambiguity margin
candidate count ∈ [2, 3]
event ∈ {task_received, after_error}
```

`before_tool` mistake and security routing should normally remain fully
deterministic because exact tool, operation, project, and policy fields are
more trustworthy than model judgment.

### Cost controls

- use a small local model or cheapest approved structured-output model;
- one short classification call, no conversation history;
- cap input to the event summary plus candidate metadata;
- cap output to a tiny enum-based schema;
- cache by normalized event and candidate fingerprints;
- allow no retries unless the response is schema-invalid;
- enforce a hard call budget per task/session;
- disable the AI arm completely when offline.

Target:

```text
at least 95% of events use no AI
at most 5% reach adjudication
zero AI calls for clear matches and desired-silence events
```

The percentages are hypotheses, not acceptance criteria. The frozen evaluation
must determine whether the adjudicator is useful enough to keep.

### Failure behavior

If the AI call times out, fails validation, exceeds budget, or returns low
confidence:

```text
remain silent
```

Do not fall back to the highest ambiguous candidate merely because the model
failed. This preserves the router's precision-first contract.

### Evaluation against zero-AI

The AI-lite arm must run against the same frozen corpus as the zero-AI router.

Compare:

- Precision@1 and Precision@2;
- silence accuracy;
- required-warning recall;
- false interruptions;
- incremental decision latency;
- calls per 100 events;
- token/API cost per 100 events;
- availability and offline degradation;
- cases improved and cases made worse.

Adopt AI-lite only if it produces a material precision or recall gain on
previously ambiguous events without weakening silence accuracy.

Suggested experiment:

```text
Arm A: exact fields + FTS5/BM25 + deterministic scoring
Arm B: Arm A + bounded adjudication on ambiguous candidates
```

Keep Arm A as the permanent fallback and control group. AI-lite is an optional
precision layer, not a dependency of Smart Router.

### AI-lite recommendation

Do not implement this arm before the zero-AI event corpus and baseline exist.
First collect the lexical router's real ambiguity set. Then test whether a
small adjudicator resolves those specific cases better than aliases, metadata,
or score calibration.

## Open design questions

1. Should skill metadata live beside each `SKILL.md`, in the paw registry, or
   in a generated index?
2. What structured fields can ICM support without duplicating memory state?
3. Should host availability be observed on every event or cached per session?
4. What is the correct identity for cooldown: task, run, thread, or action?
5. Which mistakes are project-scoped versus globally reusable?
6. Should a user dismissal reduce ranking globally or only in that project?
7. How should mutually exclusive or overlapping skills declare precedence?
8. Which policy rules are allowed to block, and where are they administered?
9. Should MCP context cost be a static registry value or measured per host?
10. What minimum evaluation score is required before enabling automatic hook
    delivery?

## Working recommendation

Build Smart Router v0 as:

```text
structured metadata
+ SQLite FTS5/BM25
+ exact field matching
+ deterministic policy scoring
+ cooldown state
+ ICM mistake references
+ host event adapters
```

No LLM. No embeddings. No vector database. No autonomous installation.

The router earns complexity only after a frozen evaluation demonstrates a
specific failure that simpler metadata and lexical retrieval cannot fix.
