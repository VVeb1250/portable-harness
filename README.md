# port-a-whip 🐾

**`paw`** — a curated cross-host AI-agent harness: **token-cut + shared-brain + one-command bundle linker**, portable across Claude Code / Codex / Gemini.

> **Status:** early build. Design complete; installer **read-path** runs. Successor to the archived `port-a-whip` (salvaging its installer core). Not yet released.

## Try

```
py -m paw sets list
py -m paw sets show secure-agent
```

## Layout

- `docs/` — design (start at [STATUS.md](docs/STATUS.md) to resume a session):
  - [ARCHITECTURE.md](docs/ARCHITECTURE.md) — layered L0/L1/L2, assumption ledger, **§11 locked design**
  - [SHARED-BRAIN.md](docs/SHARED-BRAIN.md) · [BUNDLE.md](docs/BUNDLE.md) · [BENCH.md](docs/BENCH.md)
- `paw/` — Python package: curated-set registry + loader (installer write-path WIP)
- `bench/` — token-tax measurement (`mcp_tax.py`)
- `bundle/` — curated MCP config

## The brain — 3 event-keyed recall lanes (no paid LLM)

| lane | trigger | mechanism | always-on tax |
|---|---|---|---|
| **capability** | agent hits a need | read/search a curated index (pull, not push) | ~0 |
| **memory** | task / file context | ICM local search (`icm recall`) | ~0 |
| **mistakes** | about to run an action | PreToolUse lookup keyed to the command | ~0 |

Delivery = **bundle-linker**: one command wires a whole bundle into a host (codegraph-link-style — verify → patch → managed block → unlink). Guarantees are **host-tiered** (A-13): hooks are strong on Claude, instruction+sandbox on Codex.

## Principles

See [CLAUDE.md](CLAUDE.md): reuse-don't-rebuild · token-budget-real (CLI > MCP) · cross-host · anti-vibes/empirical · challenge-everything.

## License

MIT.
