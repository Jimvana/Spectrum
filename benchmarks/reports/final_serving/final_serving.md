# Final Standard Serving Benchmark

Averages across self_files, human, and Babel corpuses. `Spectrum serving` is the standardized flow: Spectrum token search, top-k snippets, byte-prism decode of the selected result, and decoded-payload cache.

## Speed League

| Rank | Engine | Mean E2E ms | Search ms | Hydrate ms | P95 E2E ms |
|---:|---|---:|---:|---:|---:|
| 1 | Raw TF-IDF | 0.873 | 0.871 | 0.002 | 1.082 |
| 2 | Raw BM25 | 2.474 | 2.472 | 0.001 | 3.695 |
| 3 | FAISS vector | 4.685 | 4.680 | 0.005 | 6.894 |
| 4 | Chroma vector DB | 5.578 | 5.574 | 0.004 | 6.331 |
| 5 | Spectrum serving | 5.759 | 0.411 | 5.349 | 31.089 |

## Quality League

| Rank | Engine | Recall@5 | MRR | Hit@1 |
|---:|---|---:|---:|---:|
| 1 | Raw BM25 | 0.826 | 0.574 | 0.438 |
| 2 | Raw TF-IDF | 0.562 | 0.328 | 0.203 |
| 3 | FAISS vector | 0.542 | 0.335 | 0.224 |
| 4 | Spectrum serving | 0.506 | 0.329 | 0.232 |
| 5 | Chroma vector DB | 0.487 | 0.296 | 0.194 |

## Size League

Raw TF-IDF and raw BM25 are in-process baselines in this runner, so their persisted byte size is not recorded here.

| Rank | Engine | Mean bytes | Mean MiB |
|---:|---|---:|---:|
| 1 | Spectrum serving | 9,172,653 | 8.75 |
| 2 | FAISS vector | 12,563,509 | 11.98 |
| 3 | Chroma vector DB | 50,194,464 | 47.87 |
