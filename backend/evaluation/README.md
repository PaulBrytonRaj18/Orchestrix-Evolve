# Ranking evaluation

`data/eval_set.json.gz` is a frozen benchmark: 23 research topics, 2,068 candidate
papers (what Orchestrix's own discovery returned for each topic) and 210 relevance
labels. A candidate is **relevant** when one of the topic's three most relevant,
highly cited OpenAlex *reviews* cites it — expert-chosen papers, no hand labelling.

```bash
python -m evaluation.run                                   # TF-IDF + default model
python -m evaluation.run --tune --variants "BAAI/bge-small-en-v1.5@600,nomic-ai/nomic-embed-text-v1.5-Q@600"
python -m evaluation.build_dataset                         # rebuild (network, ~3 min)
```

Tuned weights are reported with 2-fold cross-validation (chosen on half the topics,
scored on the other half).

## Results (2026-11-27, 4-CPU container)

| Strategy | nDCG@20 | Recall@20 | MRR |
|---|---|---|---|
| random order | 0.147 | 0.198 | 0.219 |
| TF-IDF hybrid (ranker before Phase 2) | 0.394 | 0.460 | 0.547 |
| bge-small@600, dense similarity only | 0.268 | 0.346 | 0.379 |
| bge-small@600, hybrid, CV-tuned (grid) | 0.508 | 0.548 | 0.688 |
| **bge-small@600, semantic 0.3 + citations 0.6 (production)** | **0.549** | **0.578** | **0.728** |
| arctic-embed-s@1000, hybrid, CV-tuned | 0.494 | 0.537 | 0.695 |
| nomic-embed-v1.5-Q@600, hybrid, CV-tuned | 0.480 | 0.538 | 0.708 |
| citations only | 0.567 | 0.586 | 0.793 |

Embedding cost for one 90-paper pool: 300 chars 1.1 s · 600 chars 2.1 s · 1,000 chars
3.8 s (bge-small); Nomic is ~1.5× slower with no quality gain here.

**Caveat.** Reviews cite influential work, so this ground truth rewards citation
count; pure citation ranking scores highest. Production deliberately keeps a 0.3
semantic weight: it costs ~3% nDCG on this benchmark but keeps results on-topic and
keeps new, rarely cited papers visible (14% of the top 20 are from 2024+ vs 13% for
citations only). Re-check this trade-off with user feedback signals when available.
