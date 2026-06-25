# port-a-whip 🐾

**`paw`** — a curated cross-host AI-agent harness: **token-cut + shared-brain + one-command bundle linker**, portable across Claude Code / Codex / Gemini.

> **Status:** early runtime. Curated-set read path, deterministic router, and
> ICM shared blackboard run today; installer write path and Team Kernel are next.

## Try

```
python -m paw sets list
python -m paw sets show secure-agent
python -m paw route "Refactor the parser across several files" --json
python -m paw blackboard write --project portable-harness --run-id demo --role planner --kind plan --content "Inspect parser.py and add regression tests"
python -m paw blackboard read --project portable-harness --run-id demo --query "regression tests"
```

## Layout

- `docs/` — design (start at [STATUS.md](docs/STATUS.md) to resume a session):
  - [ARCHITECTURE.md](docs/ARCHITECTURE.md) — layered L0/L1/L2, assumption ledger, **§11 locked design**
  - [SHARED-BRAIN.md](docs/SHARED-BRAIN.md) · [BUNDLE.md](docs/BUNDLE.md) · [BENCH.md](docs/BENCH.md)
- `paw/` — curated-set registry, explainable router, and ICM blackboard adapter
- `bench/` — token/cost measurement; SymPy N=8 team benchmark is frozen under `bench/swe_probe/`
- `bundle/` — curated MCP config

## The brain — 3 event-keyed recall lanes (no paid LLM)

| lane | trigger | mechanism | always-on tax |
|---|---|---|---|
| **capability** | agent hits a need | read/search a curated index (pull, not push) | ~0 |
| **memory** | task / file context | ICM local search (`icm recall`) | ~0 |
| **mistakes** | about to run an action | PreToolUse lookup keyed to the command | ~0 |

Team state uses an explicit ICM blackboard namespace:
`<project>/blackboard/<run-id>`. Entries are bounded, versioned, and
secret-checked; artifacts remain files and memory stores references/summaries.

Delivery target = **bundle-linker**: verify → patch → managed block → unlink.
Guarantees are **host-tiered**: hooks are strong on Claude,
instruction+sandbox on Codex.

## Principles

See [CLAUDE.md](CLAUDE.md): reuse-don't-rebuild · token-budget-real (CLI > MCP) · cross-host · anti-vibes/empirical · challenge-everything.

## License

MIT.
