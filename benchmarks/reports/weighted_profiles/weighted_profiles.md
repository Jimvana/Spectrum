# Workload-Weighted Benchmark Profiles

These tables use the measured final benchmark data, then weight Spectrum by expected full-decode/open rate:

`weighted Spectrum = snippet_only * (1 - open_rate) + selected_full_decode * open_rate`

- Measured Spectrum snippet-only path: `0.373 ms`
- Measured Spectrum selected full-decode path: `5.759 ms`

## Standard RAG Snippets Profile

Assumes 90% snippet-only candidate serving and 10% selected full .spec decode.

| Rank | Engine | Weighted E2E ms | Recall@5 | MRR |
|---:|---|---:|---:|---:|
| 1 | Raw TF-IDF | 0.873 | 0.562 | 0.328 |
| 2 | Spectrum serving | 0.911 | 0.506 | 0.329 |
| 3 | Raw BM25 | 2.474 | 0.826 | 0.574 |
| 4 | FAISS vector | 4.685 | 0.542 | 0.335 |
| 5 | Chroma vector DB | 5.578 | 0.487 | 0.296 |

## Code Assistant Profile

Assumes 65% snippet/candidate serving and 35% selected full .spec decode.

| Rank | Engine | Weighted E2E ms | Recall@5 | MRR |
|---:|---|---:|---:|---:|
| 1 | Raw TF-IDF | 0.873 | 0.562 | 0.328 |
| 2 | Spectrum serving | 2.258 | 0.506 | 0.329 |
| 3 | Raw BM25 | 2.474 | 0.826 | 0.574 |
| 4 | FAISS vector | 4.685 | 0.542 | 0.335 |
| 5 | Chroma vector DB | 5.578 | 0.487 | 0.296 |

## Spectrum Sensitivity

| Full decode/open rate | Expected Spectrum E2E ms |
|---:|---:|
| 0% | 0.373 |
| 5% | 0.642 |
| 10% | 0.911 |
| 15% | 1.181 |
| 20% | 1.450 |
| 35% | 2.258 |
| 50% | 3.066 |
| 100% | 5.759 |
