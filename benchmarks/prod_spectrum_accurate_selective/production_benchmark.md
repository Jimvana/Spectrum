# Production Engine Benchmark

- Benchmark dir: `C:\Users\james\Desktop\2rep`
- Docs: 72,601
- Queries: 80
- Hydrate limit: 5

## Results

| Engine | Status | Hit@1 | MRR | Recall@5 | Search ms | Hydrate ms | E2E ms | P95 E2E ms | CPU E2E ms | CPU util % | Build sec | Build CPU sec | Index bytes | Notes |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|
| spectrum_serving_pipeline | ok | 0.5875 | 0.5938 | 0.6 | 1.8165 | 2.34 | 4.1565 | 4.3291 | 4.1016 | 98.68 | 61.2374 | 60.0469 | 413915926 |  |

## Notes

- `dense_lsa_numpy`, `faiss_lsa_flat`, and `chroma_lsa` use the same local LSA vectors so they measure vector-index plumbing, not frontier embedding quality.
- `Search ms` is retrieval only; `E2E ms` is retrieval plus hydration of the returned top-k payloads.
- Standard RAG engines hydrate from raw text already held in memory. Spectrum serving preloads `.spec` payload bytes into RAM, then byte-prism decodes selected payloads on demand.
- `opensearch_bm25_http`, `zoekt_cli`, and `lucene_pyserini_bm25` are dependency-gated production adapters.
- Use labelled human queries before treating these numbers as product-level retrieval claims.
