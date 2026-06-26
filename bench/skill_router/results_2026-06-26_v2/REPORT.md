# Multilingual Skill Router Benchmark

- Cases: 180
- Skills: 175
- Load-all metadata tokens: 8976

| Arm | Recall@K | Full coverage | Precision@K | Silence | Mean ctx tok | Mean ms |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| load_all | 100.0% | 100.0% | 0.8% | 0.0% | 8976.0 | 0.00 |
| metadata_lexical | 12.9% | 14.2% | 36.7% | 90.0% | 87.5 | 62.67 |
| semantic_top3 | 56.1% | 52.5% | 35.1% | 93.3% | 169.1 | 65.25 |
| graph_top3 | 83.3% | 81.7% | 55.3% | 100.0% | 151.6 | 2.95 |
| oracle | 100.0% | 100.0% | 100.0% | 100.0% | 29.7 | 0.00 |

## Notes

- `load_all` exposes every skill metadata record, so recall is an availability ceiling, not autonomous selection accuracy.
- `oracle` exposes only labeled required skills and is the context-efficiency ceiling.
- This run measures retrieval, silence, compatibility coverage, context tokens, and local latency—not end-to-end task completion.
