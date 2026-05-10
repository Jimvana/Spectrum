# Spectrum Project Outline

## Goal

Spectrum is a deterministic retrieval-aware encoding layer for compact,
lossless, searchable code and text stores.

The central idea:

```text
source text
  -> stable token IDs
  -> compact .spec payload
  -> searchable postings/index sidecar
  -> selective decode back to exact source
```

The compressed artifact and retrieval representation are intentionally close
together. Spectrum is not trying to beat gzip, Brotli, or zstd as a passive byte
compressor; it is trying to combine compact storage, searchability,
explainability, and lossless hydration.

## Current Components

- `spec_format/spec_encoder.py`: writes `.spec` headers and compressed token ID
  bodies.
- `spec_format/spec_decoder.py`: decodes `.spec` files back to exact source.
- `dictionary.py` and `english_tokens.py`: stable token IDs and generated
  English word coverage.
- `tokenizers/`: language-aware tokenizers for code, text, XML-compatible
  payloads, and config formats.
- `rag/indexer.py`: builds compact retrieval indexes from `.spec` files.
- `rag/storage_benchmark.py`: compares Spectrum stores with conventional
  raw-text TF-IDF stores for JSONL/text corpora.
- `rag/codebase_benchmark.py`: builds and benchmarks repository/codebase
  stores.
- `rag/spectrum_serving.py`: production-shaped serving retriever for `.specpack`
  or `spectrum_spec` stores.
- `native/spectrum_native/`: optional Rust decoder acceleration.
- `CLI Tool/spectrum_cli/main.py`: public encode/archive/index/search/demo CLI.

## Format Invariants

- `.spec` payloads are lossless.
- Dictionary IDs are append-only across versions.
- Older dictionary snapshots remain available for decode compatibility.
- ASCII and Unicode fallback IDs preserve unknown characters.
- Retrieval metadata and ranking settings live beside the payload, not inside
  the core header.

## Active Proof Path

The active proof path is code and structured-text retrieval:

- compact `.spec` payloads,
- binary BM25 postings (`SPB1`/`SPB2`),
- snippet sidecars for result previews,
- bounded code-aware reranking,
- selective full-payload decode on open,
- optional native decode acceleration.

## Next Work

1. Broaden labelled code and mixed-document query sets.
2. Add stronger baselines: Lucene/OpenSearch BM25, Zoekt, Tree-sitter chunk
   BM25, vector stores, neural embeddings, and hybrid retrieval.
3. Keep tuning query normalization, field boosts, noisy-token handling, and
   phrase/proximity scoring.
4. Continue separating the correctness reference path from optional production
   acceleration paths.
