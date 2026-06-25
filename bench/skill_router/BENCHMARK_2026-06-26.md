# Multilingual Skill Router Benchmark — 2026-06-26

## Outcome

On the 180-query development cohort, bounded graph routing retained 83.3% of
required skill groups in its top three cards while using 151.6 mean context
tokens. Loading metadata for all 175 skills cost 8,976 tokens.

That is a 98.3% context reduction relative to load-all metadata. Graph routing
also improved over semantic retrieval alone:

| Arm | Recall@3 | Full coverage | Precision@3 | Silence | Mean context tokens |
| --- | ---: | ---: | ---: | ---: | ---: |
| Load all metadata | 100.0% availability | 100.0% availability | 0.8% | 0.0% | 8,976.0 |
| Metadata lexical | 12.9% | 14.2% | 36.7% | 90.0% | 87.5 |
| Semantic top-3 | 56.1% | 52.5% | 35.1% | 93.3% | 169.1 |
| Graph top-3 | **83.3%** | **81.7%** | **55.3%** | **100.0%** | **151.6** |
| Oracle | 100.0% | 100.0% | 100.0% | 100.0% | 29.7 |

`load_all` is an availability ceiling, not a skill-selection score: every skill
is present, so recall is trivially perfect while precision and silence are poor.

## Language results

Graph Recall@3:

| Language | Semantic | Graph | Delta |
| --- | ---: | ---: | ---: |
| English | 81.8% | 100.0% | +18.2 pp |
| Arabic | 81.8% | 100.0% | +18.2 pp |
| Turkish | 63.6% | 100.0% | +36.4 pp |
| Chinese | 90.9% | 100.0% | +9.1 pp |
| Spanish | 72.7% | 90.9% | +18.2 pp |
| Finnish | 45.5% | 90.9% | +45.5 pp |
| Hindi | 36.4% | 90.9% | +54.5 pp |
| Japanese | 63.6% | 90.9% | +27.3 pp |
| Thai | 54.5% | 90.9% | +36.4 pp |
| Amharic | 36.4% | 54.5% | +18.2 pp |
| Igbo | 45.5% | 54.5% | +9.1 pp |
| Swahili | 0.0% | 36.4% | +36.4 pp |

Silence accuracy was 100% for graph routing in every language.

The weakest languages were Swahili, Igbo, and Amharic. This may reflect model
coverage, synthetic translation quality, or both; the current data cannot
separate those causes.

## Intent-level findings

- `docker-compose` and `investor-deck` reached full coverage in all languages.
- `secure-auth-tests`, browser E2E, and database migration reached 91.7%.
- `test-driven-feature` remained the weakest intent at 41.7%.
- Swahili accounted for failures across most technical intents.

## Development loop

The first run exposed missing graph coverage and an overly strict exact-label
grader:

| Graph arm | Recall@3 | Full coverage | Precision@3 | Silence | Mean tokens |
| --- | ---: | ---: | ---: | ---: | ---: |
| v1 | 65.9% | 62.5% | 33.3% | 100.0% | 178.5 |
| v2 | 83.3% | 81.7% | 55.3% | 100.0% | 151.6 |

v2 added generic intent nodes for uncovered domains and allowed explicitly
declared compatible substitutes such as `tdd`/`tdd-workflow`. It did not enlarge
the three-card output budget.

Because v1 failures informed these changes, v2 is a development-set result. A
new held-out cohort is required before claiming generalization.

## Relationship to prior work

- [SkillRet](https://arxiv.org/html/2605.05726v1) isolates skill retrieval over
  17,810 skills and 4,997 evaluation queries.
- [R3-Skill](https://arxiv.org/html/2606.03565v2) shows that skill compatibility
  and rejection labels matter in addition to pairwise relevance.
- [SkillsBench](https://arxiv.org/html/2602.12670v4) evaluates downstream task
  outcomes and finds focused skill bundles outperform exhaustive bundles.
- [RAG-MCP](https://arxiv.org/abs/2505.03275) and
  [JSPLIT](https://arxiv.org/html/2510.14537v1) evaluate retrieval/taxonomy
  approaches to prompt bloat.
- [MLCL](https://arxiv.org/html/2601.05366v1) demonstrates that multilingual
  tool-use failures require separate language-aware evaluation.

The paw benchmark combines a live personal skill catalog, multilingual
retrieval, silence cases, compatibility labels, and explicit context-token
accounting. It remains smaller and less reviewed than the public benchmarks
above.

## Limitations and next gate

1. Prompts are synthetic and not yet native-speaker reviewed.
2. v2 was tuned on the same intents used for evaluation.
3. Context tokens measure the delivery payload, not total model-session usage.
4. Local latency excludes model loading and corpus-index construction from each
   individual query, but reports them separately in `results.json`.
5. No downstream agent executes the selected skill, so this is not task pass
   rate.

Before an external performance claim:

- freeze a held-out paraphrase and code-switch cohort;
- obtain native review for at least Thai, Swahili, Igbo, and Amharic;
- run a matched end-to-end arm: no skill, load-all metadata, graph-routed skill,
  and oracle skill;
- report task success and total session tokens alongside retrieval metrics.
