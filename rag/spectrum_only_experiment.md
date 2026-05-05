# Spectrum-Only Retrieval Experiment

Purpose: isolate whether the `.spec` representation carries retrieval signal without BM25 keyword weighting.

Implementation:

- `raw_text_bm25`: raw source/chunk text BM25 baseline.
- `spectrum_bm25`: current Spectrum token BM25 path.
- `spectrum_only_binary_cosine`: direct `.spec` token similarity using binary cosine over unique Spectrum token IDs.
- Spectrum-only intentionally removes BM25, IDF, length-normalized term frequency, and title boosts.

## Human-Labelled Wiki Queries

These are the most useful results for retrieval behavior because the queries are natural/human-style rather than generated from chunk text.

### 6k chunks

Report: `rag/ranking_eval_spectrum_only_6k_human/ranking_eval.md`

| Variant | Hit@1 | MRR | Recall@5 | Avg ms | P95 ms |
|---|---:|---:|---:|---:|---:|
| Raw text BM25 | 0.760 | 0.807 | 0.880 | 0.158 | 0.593 |
| Spectrum BM25 | 0.580 | 0.633 | 0.720 | 0.125 | 0.438 |
| Spectrum only | 0.600 | 0.692 | 0.820 | 0.079 | 0.236 |

### 1.8k chunks

Report: `rag/ranking_eval_spectrum_only_1800_human/ranking_eval.md`

| Variant | Hit@1 | MRR | Recall@5 | Avg ms | P95 ms |
|---|---:|---:|---:|---:|---:|
| Raw text BM25 | 0.780 | 0.827 | 0.880 | 0.275 | 1.314 |
| Spectrum BM25 | 0.600 | 0.669 | 0.780 | 0.230 | 1.154 |
| Spectrum only | 0.700 | 0.742 | 0.800 | 0.156 | 0.690 |

## Generated Wiki Queries

Generated queries are easier because they are derived from source chunk text. They are still useful as a consistency check.

### 6k chunks

Report: `rag/ranking_eval_spectrum_only_6k/ranking_eval.md`

| Variant | Hit@1 | MRR | Recall@5 | Avg ms | P95 ms |
|---|---:|---:|---:|---:|---:|
| Raw text BM25 | 1.000 | 1.000 | 1.000 | 0.766 | 1.189 |
| Spectrum BM25 | 0.923 | 0.936 | 0.962 | 0.649 | 1.044 |
| Spectrum only | 0.808 | 0.833 | 0.885 | 0.308 | 0.438 |

### 1.8k chunks

Report: `rag/ranking_eval_spectrum_only_1800/ranking_eval.md`

| Variant | Hit@1 | MRR | Recall@5 | Avg ms | P95 ms |
|---|---:|---:|---:|---:|---:|
| Raw text BM25 | 1.000 | 1.000 | 1.000 | 1.748 | 2.864 |
| Spectrum BM25 | 0.969 | 0.984 | 1.000 | 1.619 | 2.817 |
| Spectrum only | 0.875 | 0.932 | 1.000 | 0.771 | 1.108 |

## Ranking Behavior

- Spectrum-only changes the top result often: 38/50 human queries on 6k chunks and 34/50 human queries on 1.8k chunks.
- On human-labelled queries, Spectrum-only improves over current Spectrum BM25 despite using a much simpler scorer.
- The biggest improvements are title/entity-like queries where direct Spectrum token overlap can pull the exact redirect/title page to rank 1, for example `Atlas Shrugged characters list`, `ASCII art page`, `academy award best picture`, `American football sport`, and `Anna Kournikova tennis`.
- Spectrum-only also produces some clear misses on noisy or broad queries because it has no IDF/downweighting for common tokens.

## Latency

Spectrum-only is faster than Spectrum BM25 in every run because it only counts unique token overlap and avoids BM25 scoring math:

- 6k human: 0.079 ms avg vs 0.125 ms avg.
- 1.8k human: 0.156 ms avg vs 0.230 ms avg.
- 6k generated: 0.308 ms avg vs 0.649 ms avg.
- 1.8k generated: 0.771 ms avg vs 1.619 ms avg.

## Takeaway

The `.spec` representation does carry independent retrieval signal. The strongest evidence is the human-labelled set: Spectrum-only beats the current Spectrum BM25 baseline on both chunk sizes while running faster. It is not a replacement yet, but it is enough signal to justify further experiments with Spectrum-native similarity and hybrid scoring.

## Follow-Up Benchmark Suite

Additional run: `rag/spectrum_only_benchmark_suite/benchmark_suite.md`

This repeats the test across:

- two messy natural-language corpora,
- a mixed-language/file-type corpus,
- raw BM25,
- local LSA dense vectors as an embedding proxy,
- Spectrum BM25,
- Spectrum-only binary cosine,
- validation and holdout query sets with duplicate-query and lexical-overlap checks.

### Messy natural-language results

The first operational-notes corpus is easy for all methods, but the noisier forum corpus separates the variants:

| Corpus/query set | Raw BM25 Hit@1 | Embedding proxy Hit@1 | Spectrum BM25 Hit@1 | Spectrum-only Hit@1 |
|---|---:|---:|---:|---:|
| Operational notes / validation | 1.000 | 1.000 | 1.000 | 1.000 |
| Operational notes / holdout | 1.000 | 1.000 | 1.000 | 1.000 |
| Noisy forum / validation | 1.000 | 1.000 | 0.800 | 0.800 |
| Noisy forum / holdout | 0.900 | 0.900 | 0.900 | 0.900 |

Query validation checks found no duplicate queries and low relevant-doc lexical overlap:

- Operational holdout average Jaccard: 0.132.
- Noisy forum holdout average Jaccard: 0.098.

### Mixed language/file-type stress

The stress corpus covers Python, JavaScript, TypeScript, CSS, HTML, SQL, Rust, Java, PHP, and Markdown.

| Query set | Raw BM25 Hit@1 | Embedding proxy Hit@1 | Spectrum BM25 Hit@1 | Spectrum-only Hit@1 |
|---|---:|---:|---:|---:|
| Validation | 0.800 | 0.800 | 1.000 | 1.000 |
| Holdout | 0.900 | 0.900 | 0.700 | 0.700 |

Spectrum-only remains faster than Spectrum BM25 in the benchmark-suite stress runs, but the mixed-language holdout shows a real weakness: both Spectrum variants trail raw BM25 and the embedding proxy on paraphrased file-intent queries. That points to alias/query normalization and cross-language token coverage as the next areas to improve.
