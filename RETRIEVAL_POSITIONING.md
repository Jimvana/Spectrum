# Spectrum Retrieval Positioning

## Core Focus

Spectrum should be discussed and evaluated as a retrieval-ready storage format,
not as a general-purpose compression competitor.

The central claim:

> A `.spec` file is both a compact stored artifact and a directly searchable
> token representation.

In most RAG and code-search systems, storage and retrieval are separate layers:
raw files or chunks are stored, then an index, vector store, trigram index, or
syntax-aware chunk representation is built beside them. Spectrum keeps the
stored form and searchable token representation close together.

## Meaningful Comparisons

Focus comparisons on retrieval systems and retrieval-ready representations:

- Raw BM25 / Lucene-style inverted indexes
- Zoekt / Sourcegraph-style code search
- Tree-sitter chunking plus BM25
- Embedding RAG
- Hybrid BM25 plus embeddings
- Other explainable sparse retrieval methods

Passive compressors such as gzip, Brotli, zstd, and zip are storage baselines,
not search baselines. They compress bytes; they do not provide retrieval,
token-level explainability, or decode-on-demand workflows.

## Preferred Framing

Use this framing:

> Raw BM25 is fastest. Syntax-aware indexing is strongest for code structure.
> Spectrum is the compact, explainable, retrieval-ready middle ground.

Spectrum is strongest when the user cares about:

- Local/offline retrieval
- Explainable matching
- Code and structured text
- Avoiding embedding API calls
- Keeping storage and retrieval representation close together
- Decode-on-demand access to original source
- A format that can be indexed without fully reconstructing every file

## Active Proof Path

The active proof path is code and structured-text retrieval:

- `rag/codebase_benchmark.py` scans repositories and compares raw TF-IDF with
  Spectrum `.spec` plus binary BM25 postings.
- `rag/spectrum_serving.py` loads `.specpack` or `spectrum_spec` stores, serves
  snippet sidecars, reranks bounded candidate sets, and decodes selected
  payloads on demand.
- `benchmarks/reports/final_serving/` and related benchmark reports track the
  current production-shaped serving signal.

## Weaknesses To Keep Visible

- Raw BM25 remains a strong speed baseline.
- Syntax-aware code retrieval can be stronger for structured relevance.
- Hybrid sparse plus embedding retrieval is likely stronger for broad natural
  language RAG.
- Spectrum query normalization and ranking still need profile-specific tuning.
- Generated queries are useful smoke tests, but labelled human queries are
  needed for production claims.

## Next Benchmark Plan

1. Build larger mixed code/documentation corpora.
2. Add labelled query-to-file or query-to-chunk relevance.
3. Run true baselines: Lucene/OpenSearch BM25, Zoekt, Tree-sitter chunk BM25,
   Chroma or FAISS, neural embeddings, and hybrid retrieval.
4. Measure index size, source/chunk/vector storage size, build time, query
   latency, Hit@1, MRR, Recall@k, decode time, and explainability.

## One-Sentence Carryover

Keep Spectrum positioned as a retrieval-ready `.spec` artifact: the comparison
is BM25, Zoekt, Tree-sitter chunking, embeddings, and hybrid RAG, not passive
compressors.
