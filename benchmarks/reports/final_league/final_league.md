# Final Competitor League Table

Averages across self_files, human, and Babel corpuses. E2E = search + hydration of top-k payloads. Spectrum snippet sidecar returns snippets/previews, not full decoded `.spec` payloads.

## Speed League

| Rank | Engine | Mean E2E ms | Search ms | Hydrate ms | P95 E2E ms |
|---:|---|---:|---:|---:|---:|
| 1 | Spectrum snippet sidecar | 0.373 | 0.372 | 0.001 | 0.702 |
| 2 | Raw TF-IDF | 0.839 | 0.838 | 0.001 | 1.023 |
| 3 | Raw BM25 | 2.298 | 2.296 | 0.001 | 3.625 |
| 4 | FAISS vector | 4.398 | 4.394 | 0.004 | 6.813 |
| 5 | Chroma vector DB | 5.541 | 5.537 | 0.004 | 6.596 |
| 6 | Spectrum byte-prism cached | 9.756 | 0.393 | 9.363 | 59.279 |
| 7 | Spectrum byte-prism | 53.851 | 0.441 | 53.411 | 146.350 |

## Quality League

| Rank | Engine | Recall@5 | MRR | Hit@1 |
|---:|---|---:|---:|---:|
| 1 | Raw BM25 | 0.826 | 0.574 | 0.438 |
| 2 | Raw TF-IDF | 0.562 | 0.328 | 0.203 |
| 3 | FAISS vector | 0.542 | 0.335 | 0.224 |
| 4 | Spectrum byte-prism | 0.506 | 0.329 | 0.232 |
| 5 | Spectrum byte-prism cached | 0.506 | 0.329 | 0.232 |
| 6 | Spectrum snippet sidecar | 0.506 | 0.329 | 0.232 |
| 7 | Chroma vector DB | 0.492 | 0.297 | 0.194 |

## Size League

Measured persisted index/store bytes where available. Raw TF-IDF and raw BM25 are in-process baselines in this runner, so their byte size is not recorded here.

| Rank | Engine | Mean bytes | Mean MiB |
|---:|---|---:|---:|
| 1 | Spectrum byte-prism | 7,475,236 | 7.13 |
| 2 | Spectrum byte-prism cached | 7,475,236 | 7.13 |
| 3 | Spectrum snippet sidecar | 9,040,476 | 8.62 |
| 4 | FAISS vector | 12,563,509 | 11.98 |
| 5 | Chroma vector DB | 50,229,963 | 47.90 |
