# Multilingual Skill Router Benchmark

This benchmark compares skill-catalog delivery and retrieval strategies over the
live local skill inventory.

## Run

```powershell
python -m bench.skill_router.runner `
  --cohort bench/skill_router/cohort_2026-06-26.json `
  --output bench/skill_router/results_2026-06-26_v2
```

The runner is local-only. It uses the installed multilingual ONNX encoder and
does not call a paid API.

## Cohort

- 10 positive intents and 5 silence intents;
- 12 languages: English, Thai, Chinese, Japanese, Spanish, Arabic, Hindi,
  Turkish, Finnish, Swahili, Igbo, and Amharic;
- 180 total queries;
- compatible substitutes may share one accepted label group, for example
  `tdd-workflow` and `tdd`.

The translations are synthetic diagnostic prompts. Native-speaker review is
required before making publication-grade cross-language claims.

## Arms

- `load_all`: expose all skill metadata. This measures availability and context
  tax, not autonomous model selection.
- `metadata_lexical`: lexical routing over skill metadata.
- `semantic_top3`: multilingual embedding retrieval, capped at three cards.
- `graph_top3`: semantic anchors plus one-hop graph traversal, substitute
  collapse, complement expansion, and three-card output.
- `oracle`: expose only the labeled required skills.

## Metrics

- required-group Recall@K;
- full required-skill coverage;
- Precision@K;
- MRR;
- silence accuracy;
- context tokens using `o200k_base`;
- local routing latency.

This benchmark does not measure whether an agent successfully completes the
downstream task after loading a skill. That requires a separate matched
execution benchmark.

## Integrity warning

`results_2026-06-26_v2` is a development-set result. The v1 failures informed
graph coverage additions before v2 was run on the same cohort. Treat v2 as
evidence that the graph mechanism can improve this catalog, not as a held-out
generalization claim.
