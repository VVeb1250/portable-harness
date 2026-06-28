# Wire decision matrix

> Goal: every bundle decision must answer **wireแล้วคุ้มไหม?** — not only
> "can this tool be installed?"

Paw's job is not to make every runtime look identical. Paw's job is to choose
the cheapest reliable wiring for each host while preserving quality.

## Runtime model

```text
Open portable foundation:
  AGENTS.md / host instructions
  MCP where a tool must be interactive
  CLI binaries where a tool can be zero-idle-token

Installed harness pack:
  ECC skills/rules/hooks/agents, when present and useful

Execution runtimes:
  Claude Code monthly seat
  Codex monthly seat
  Goose / API-metered runtime

Paw control plane:
  catalog → plan → apply → verify → remove
  global/project state
  token/quality tradeoff ledger
```

## Core question

For every `set × host`, classify the wiring:

| Policy | Meaning | Linker behavior |
| --- | --- | --- |
| `ready` | Evidence says benefit usually beats cost on this host. | plan/apply may proceed, still verify. |
| `conditional` | Benefit depends on workload, repo size, or session shape. | warn with condition; require explicit apply. |
| `detect-first` | Reuse existing foundation/install state before touching config. | block blind install; run detector/preflight first. |
| `manual` | Human choice needed because the tradeoff is not knowable from repo state. | show plan only; no mutation. |
| `skip` | Cost/overlap/risk beats benefit. | do not wire by default. |
| `deferred` | Candidate exists but not validated. | keep catalog evidence; no install choice. |

## Host tiers

| Host/runtime | Strength | Risk | Default bias |
| --- | --- | --- | --- |
| Claude Code monthly | Strong hooks, lazy MCP, ECC strongest here. | Claude-specific behavior does not prove portability. | Use ECC selectively; MCP can be richer when lazy-loaded. |
| Codex monthly | AGENTS.md + config/plugin surfaces; weaker hooks. | More instruction-based; load-all MCP tax matters. | Prefer CLI/AGENTS.md; keep MCP count low. |
| Goose / API-metered | Open/local-first runtime candidate for metered calls. | Needs separate adapter and measured MCP/extension behavior. | Prefer explicit CLI/MCP recipes; measure per call. |
| Gemini/Cursor/OpenCode/etc. | Useful portability checks. | Host-specific config/hook parity varies. | Adapter-by-adapter; no uniform claims. |

## Tradeoff gates

A set should be wired only when it clears these gates:

1. **Capability gate** — does it solve a real user task better than native host tools?
2. **Portability gate** — can the behavior be expressed through AGENTS.md, CLI, MCP,
   or a small host adapter?
3. **Token gate** — does it reduce total context/tool-output cost for the workload?
   - CLI/hook with no tool definition cost wins by default.
   - MCP is acceptable only when its idle/tool-schema tax is justified.
   - Load-all hosts get stricter MCP limits than lazy-load hosts.
4. **Quality gate** — does it improve pass rate, correctness, safety, or review
   quality in a measurable way?
5. **Operational gate** — can paw verify, unlink, and recover from drift?

If any gate is unknown, classify as `conditional` or `manual`, not `ready`.

## Current important decisions

| Area | Decision |
| --- | --- |
| ECC | Reuse as rich harness pack when detected; do not make it the philosophical portable base. |
| Open base | AGENTS.md + MCP + CLI + host adapters are paw's portable base. Goose is the main runtime candidate for API-metered execution. |
| Router | Thin nudge only. It must read linker state and never infer readiness from PATH alone. |
| MCP | Keep active MCP count low; host-condition anchors (`codegraph` vs `semble`) instead of stacking. |
| Per-project tools | Link with `paw plan|apply|verify|remove`; keep `.paw/state.json` as source of managed state. |
| Global tools | Detect existing install first; avoid stacking ECC/plugin/manual installs. |

## Examples

### `efficiency-starter`

```text
Claude Code:
  codegraph is acceptable because MCP is lazy-loaded and richer callers/impact matter.

Codex/load-all:
  prefer semble for lower idle tax; use codegraph only when callers/impact are explicit.

Goose/API:
  adapter needed; measure extension/tool-schema behavior before defaulting.
```

### `context-workbench`

```text
Big logs / many files / docs indexing:
  conditional positive.

Small prompts or read-to-edit work:
  negative; use native read/shell.
```

### ECC hooks/rules

```text
Claude Code:
  may be useful, but measure per-turn overhead and overlap.

Codex/Goose/API:
  do not port the hook bundle blindly. Convert useful behavior into CLI verify
  steps, AGENTS.md instructions, or small host-specific adapters.
```

## Linker output contract

Future linker plans should expose:

```json
{
  "wire_policy": "conditional",
  "reason": "load-all MCP idle tax; use only for caller/impact work",
  "host": "codex",
  "set": "efficiency-starter",
  "next_actions": ["paw verify efficiency-starter"]
}
```

This keeps tradeoffs reviewable and prevents future sessions from silently
turning every good tool into an always-on bundle.
