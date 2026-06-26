# port-a-whip 🐾

**`paw`** — a curated cross-host AI-agent harness: **token-cut + shared-brain + one-command bundle linker**, portable across Claude Code / Codex / Gemini.

> **Status:** alpha runtime. Curated sets, deterministic routing, ICM shared
> blackboard, host linker, and Team Kernel handoffs run today. External
> Codex/DeepSeek adapters are explicit opt-in; mutation/evaluation automation is
> still the next layer.

## Try

```
python -m paw sets list
python -m paw sets show secure-agent
python -m paw route "Refactor the parser across several files" --json
python -m paw blackboard write --project portable-harness --run-id demo --role planner --kind plan --content "Inspect parser.py and add regression tests"
python -m paw blackboard read --project portable-harness --run-id demo --query "regression tests"
```

Smoke the Team Kernel without calling external models. The mock path writes the
planner, implementer, mutator, reviewer, and evaluator handoffs to the shared
blackboard, including a deterministic patch artifact reference:

```
python -m paw team run "Refactor the parser safely" --project portable-harness --run-id demo-team --complexity complex --risk medium --sensitivity public --mock --json
```

Run the explicit Codex/DeepSeek team profile after setting `DEEPSEEK_API_KEY`
in your shell:

```
python -m paw team run "Plan and implement a small refactor" --project portable-harness --run-id real-team-1 --complexity complex --risk medium --sensitivity public --adapters codex-deepseek --json
```

`codex-deepseek` uses Codex read-only planning/review (`codex exec`) and a
DeepSeek implementer call. It is blocked for `--sensitivity restricted`, and it
only runs when the router selects the matching
`planner=codex, implementer=deepseek, reviewer=codex` team route. Use `--mock`
for transport smoke tests or private/restricted work until a local codex-only
adapter exists.

Useful environment:

- `DEEPSEEK_API_KEY` — required for `--adapters codex-deepseek`.
- `CODEX_BIN` — override the Codex CLI binary; defaults to `codex`.
- `CODEX_TIMEOUT` — Codex CLI timeout in seconds; defaults to `900`.

## Layout

- `docs/` — design (start at [STATUS.md](docs/STATUS.md) to resume a session):
  - [ARCHITECTURE.md](docs/ARCHITECTURE.md) — layered L0/L1/L2, assumption ledger, **§11 locked design**
  - [SHARED-BRAIN.md](docs/SHARED-BRAIN.md) · [BUNDLE.md](docs/BUNDLE.md) · [BENCH.md](docs/BENCH.md)
- `paw/` — curated-set registry, explainable router, ICM blackboard adapter,
  Team Kernel, and explicit role adapters
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

Delivery targets:

- **bundle-linker:** verify -> patch -> managed block -> unlink.
- **Team Kernel:** route -> plan -> implement -> review -> evaluate/stop, with
  blackboard handoffs between roles.

Guarantees are **host-tiered**: hooks are strong on Claude, instruction+sandbox
on Codex. Do not claim uniform hook/security parity across hosts.

## Principles

See [CLAUDE.md](CLAUDE.md): reuse-don't-rebuild · token-budget-real (CLI > MCP) · cross-host · anti-vibes/empirical · challenge-everything.

## License

MIT.
