# Decode vs Standard RAG Hydration

## Current benchmark paths

Standard RAG hydration in this benchmark is intentionally best-case: each engine builds `docs_by_id`, then hydration returns existing raw strings from memory.

Spectrum hydration does more work for each returned top-k document:

1. read the `.spec` file from disk
2. parse the 16-byte header
3. zlib-decompress the body
4. unpack the decompressed byte stream into uint32 token IDs
5. expand RLE / ASCII / Unicode / dictionary IDs into token strings
6. reconstruct or join text
7. trim to the stored original byte length

## Mean E2E Result

| Engine | Mean search ms | Mean hydrate ms | Mean E2E ms |
|---|---:|---:|---:|
| Raw TF-IDF | 0.903 | 0.001 | 0.904 |
| Raw BM25 | 2.456 | 0.001 | 2.457 |
| FAISS vector | 4.077 | 0.004 | 4.082 |
| Chroma vector DB | 4.680 | 0.003 | 4.683 |
| Spectrum native | 0.414 | 13.432 | 13.846 |
| Hybrid Spectrum+vector | 7.474 | 29.500 | 36.974 |

## Why Standard RAG Is Faster Today

Standard RAG stores raw text in a ready-to-return form. Once the index has found document IDs, returning the payload is basically a lookup.

Spectrum stores compact `.spec` payloads. That saves storage and preserves lossless source, but the current Python hydration path decodes full returned payloads synchronously. The benchmark shows Spectrum's search is fast; decode is the end-to-end bottleneck.

## Practical Fixes To Test Next

- Decode only the final selected chunk instead of all top-k candidates.
- Cache decoded hot chunks between queries.
- Add small raw/snippet sidecars for preview results, decode full payload only on open.
- Optimize `decode_code_spec_bytes` to avoid large intermediate Python lists where possible.
- Move decode to a native/vectorized path if `.spec` remains the serving payload.
