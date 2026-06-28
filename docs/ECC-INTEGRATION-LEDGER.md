# ECC integration ledger

> Current decision: open portable foundation = AGENTS.md + MCP/CLI + host
> adapters. ECC is the richest installed harness pack to detect and reuse when
> present. Paw is the portable bundle/linker/state overlay. Do not rebuild broad
> ECC harness features inside paw unless this ledger says `paw owns` or
> `build gap`.

## Why this exists

Claude already flagged the uncomfortable truth: ECC covers most of the generic
agent-harness surface that paw originally explored. If this is left implicit,
future sessions drift back into rebuilding skills, hooks, commands, or agents
that ECC already ships.

So the rule is simple:

```text
Before paw builds or wires harness behavior:
  1. detect ECC
  2. classify the capability
  3. reuse / wrap / own / avoid
  4. record the exception when paw builds anyway
```

## Current ECC evidence

Local evidence checked from
`C:\Users\VVeb1250\.claude\plugins\cache\ecc\ecc\2.0.0`:

- ECC version: `2.0.0`
- Surface present: `skills/`, `commands/`, `agents/`, `hooks/`, `rules/`,
  `manifests/`, `mcp-configs/`, `plugins/`
- Approximate local inventory:
  - skills: 441 files
  - commands: 92 files
  - agents: 67 files
  - hooks: 4 files
  - rules: 114 files
  - manifests: `install-components.json`, `install-modules.json`,
    `install-profiles.json`
  - package scripts include `harness:audit`, `observability:ready`, `test`

This is enough evidence to treat ECC as a real reusable harness pack, not just
a candidate. It is not enough to treat ECC as the whole portable foundation,
because its strongest hooks/rules are Claude-shaped and must be re-expressed
per host when Codex, Goose, Gemini, or API-metered runtimes are in scope.

## Capability ledger

| Capability | ECC status | paw decision | Notes |
| --- | --- | --- | --- |
| Skills / workflow playbooks | Strong | reuse ECC | paw should discover and suggest ECC skills, not create a parallel skill library. |
| Commands / slash compatibility | Strong, host-shaped | reuse or ignore | Prefer skills where ECC says skills are canonical; do not clone command shims. |
| Agents / role prompts | Strong | reuse when host supports it | paw Team Kernel should not copy ECC agents; it may choose existing roles later. |
| Hooks | Strong in Claude, uneven cross-host | wrap selectively | Do not port hook bundles wholesale. Keep host-tiered behavior explicit. |
| Rules / coding guidance | Strong | reuse selected rules | Avoid dumping large rule packs into every host/session. |
| Install profiles / manifests | Strong | detect-first | paw linker should detect profile/plugin/manual state before applying anything. |
| MCP baseline | Useful but token-sensitive | wrap with N1 gate | paw owns token economics and active-MCP ceiling; do not blindly adopt all ECC MCPs. |
| Security workflows | Strong | reuse/wrap | Use ECC skills/rules where they fit; paw still keeps deterministic tools like `nah`, `gitleaks`, `osv-scanner`, `infisical`. |
| Quality workflows | Strong | reuse/wrap | paw owns curated deterministic CLI sets (`quality-gate`, `api-quality`) and verify/remove behavior. |
| Memory / learning | Partial / host-shaped | paw owns for now | ICM + mistake memory + blackboard remain paw-owned unless ECC gains equivalent cross-host shared memory. |
| Bundle catalog | Not ECC's job | paw owns | paw curates portable tool sets by token-cut, quality gain, host support, and readiness. |
| Link / verify / remove / rollback | Not covered as paw needs it | paw owns | This is paw's core control-plane responsibility. |
| Global vs per-project bundle state | Not covered as paw needs it | paw owns | Global foundation can reuse ECC; project-local tool setup stays paw linker territory. |
| Token economics / N1 ceiling | Partial | paw owns | ECC breadth is a feature; paw decides what is cheap enough to keep active. |
| Router / behavioral nudges | Partial | thin paw overlay | Not a core layer. Router only suggests after linker state is known; it must not replace apply/verify. |

## Ownership model

```text
Open foundation = portable agent substrate
  AGENTS.md, MCP, CLI tools, and host adapters

ECC = rich installed harness pack
  skills, commands, agents, hooks, rules, install profiles, harness ergonomics

paw = portable bundle control plane
  catalog, global/project link state, apply/verify/remove, token economics,
  shared memory, blackboard, and thin just-in-time nudges
```

## Global vs project policy

### External skill marketplaces

`skills.sh` / `npx skills` is an interesting future bundle source, but treat it
as a skill-package channel rather than a harness installer.

Policy:

- use it to find/install/update external `SKILL.md` packages;
- allow skill-local support files such as references, scripts, templates, and
  assets only after inspection;
- do not treat hooks, slash commands, MCP config, credentials, or host settings
  as activated by a skill import;
- let paw/ECC linker own any hook/command/MCP/config wiring separately;
- record skill presence separately from runtime readiness, because a skill may
  reference binaries, CLIs, credentials, or services that still need
  `paw verify`.

Possible future set names: `external-skills`, `skill-marketplace`, or
`skills-sh`.

### Global foundation

Use ECC as the first thing to detect, not the first thing to reinstall.

Global paw behavior:

- detect Claude/Codex ECC plugin or manual install state;
- refuse to stack plugin + full/manual/profile installs without explicit user
  intent;
- prefer ECC skills/rules/hooks when they already satisfy the need;
- keep heavy extras opt-in.

### Per-project bundles

Project-local paw behavior:

- use `paw plan|apply|verify|remove <set>`;
- write only managed paw blocks/config sections;
- maintain `.paw/state.json` ledger;
- verify managed block/MCP/binary health before router use;
- preserve user config and unrelated host state.

## Linker implications

`harness-foundation` is `detect-first`, not a normal installable set.

Expected linker behavior:

1. detect ECC presence and install shape;
2. report `present`, `absent`, or `conflict`;
3. if absent, offer the managed ECC install path for the target host;
4. if present, reuse it and wire only paw-owned gaps;
5. if conflicting/stacked, warn before doing any mutation.

## Router implications

Router is not a core runtime layer. It is a thin behavioral nudge.

Allowed:

- suggest `paw apply <set>` when a matching set is absent;
- suggest `paw verify <set>` when the set is degraded or drifted;
- suggest concrete tool usage only when linker state is healthy.

Not allowed:

- infer readiness from PATH alone;
- recommend deferred tools as live defaults;
- use AI to decide bundle readiness;
- duplicate ECC skill-router behavior except as a small bridge.

## Build rules for future sessions

When adding a capability:

1. Search ECC first.
2. If ECC covers it, add a pointer or wrapper; do not rebuild.
3. If ECC is host-specific, write an adapter note and keep the host tier clear.
4. If paw owns it, add tests and update this ledger.
5. If the decision is uncertain, mark it `unknown` here instead of letting it
   vanish into chat history.

## Current open gaps

- Add a real ECC detector to `paw plan harness-foundation` / future preflight.
- Teach linker to surface `present/absent/conflict` for ECC install shapes.
- Decide which ECC install state file(s) are canonical across plugin vs manual
  profile installs.
- Keep `harness-foundation` out of blind batch installs until the detector
  exists.
- Apply the host tradeoff policy in
  [`WIRE-DECISION-MATRIX.md`](./WIRE-DECISION-MATRIX.md) before promoting any
  ECC hook/rule/profile from reuse candidate to default wiring.
- Re-run this ledger when ECC changes major version or adds cross-host shared
  memory.
