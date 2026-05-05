# Spectrum Benchmark

- Target: `/Users/video/Desktop/babel-main.specpack`
- Files: 18267
- Queries: 80

## Storage

| Store | Bytes | Ratio vs raw | Payload bytes | Index bytes | Build sec |
|---|---:|---:|---:|---:|---:|
| Raw text + BM25 | 36,734,161 | 1.590x | 27,100,427 | 9,633,734 | 20.849 |
| Spectrum `.specpack` + BM25 | 15,782,429 | 0.683x | 9,174,317 | 9,379,784 | 50.314 |

## Retrieval

| Store | Hit@1 | MRR | Recall@5 | Avg ms | P95 ms |
|---|---:|---:|---:|---:|---:|
| Raw text + BM25 | 0.150 | 0.313 | 0.525 | 12.698 | 16.920 |
| Spectrum `.specpack` + BM25 | 0.287 | 0.386 | 0.550 | 16.816 | 23.630 |

## Fidelity

- Spectrum verified: `True`

This is a local sparse-retrieval benchmark against raw text + BM25. It is not an embedding/vector database benchmark.
