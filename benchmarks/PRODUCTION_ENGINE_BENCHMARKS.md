# Production Engine Benchmarks

This workflow compares an existing Spectrum codebase benchmark against
production-style retrieval engines and hybrid search variants.

The runner is intentionally dependency-gated. Local baselines run with the
repo's normal Python dependencies. FAISS, Chroma, OpenSearch, Zoekt, and Lucene
adapters report `skipped` until their dependency or service is available.

## What It Measures

Inputs come from `rag/codebase_benchmark.py`:

- raw chunks from `conventional_tfidf/chunks.jsonl`
- Spectrum BM25 postings from `spectrum_spec/`
- fixed queries from `queries.json`

Every engine receives the same corpus and the same query labels. The report
captures:

- Hit@1
- MRR
- Recall@K
- average query latency
- p95 query latency
- build time
- index size where the adapter can measure it

## First Local Run

Build or reuse a codebase benchmark:

```bash
python rag/codebase_benchmark.py \
  --source-root . \
  --out-dir benchmarks/generated/codebase_benchmark_self_files \
  --max-files 80 \
  --queries 60 \
  --postings-format v2
```

Run the production benchmark harness:

```bash
python rag/production_benchmark.py \
  --benchmark-dir benchmarks/generated/codebase_benchmark_self_files \
  --out-dir benchmarks/generated/production_benchmark_self
```

Default engines:

- `raw_tfidf_sklearn`
- `raw_bm25_python`
- `spectrum_spb_bm25`
- `spectrum_spb_bm25_fast`
- `spectrum_snippet_sidecar`
- `spectrum_serving_pipeline`
- `dense_lsa_numpy`
- `hybrid_spectrum_dense_rrf`

Output files:

- `benchmarks/generated/production_benchmark_self/production_benchmark.json`
- `benchmarks/generated/production_benchmark_self/production_benchmark.md`

## Engine Selection

Use repeatable `--engine` flags to pick a subset:

```bash
python rag/production_benchmark.py \
  --benchmark-dir benchmarks/generated/codebase_benchmark_self_files \
  --out-dir benchmarks/generated/production_benchmark_optional \
  --engine spectrum_serving \
  --engine spectrum_fast \
  --engine faiss \
  --engine chroma \
  --engine opensearch \
  --engine zoekt \
  --engine lucene
```

Supported engine keys:

| Key | Report name | Status |
|---|---|---|
| `tfidf` | `raw_tfidf_sklearn` | local baseline |
| `raw_bm25` | `raw_bm25_python` | local lexical baseline |
| `spectrum` | `spectrum_spb_bm25` | Spectrum SPB1/SPB2 BM25 |
| `spectrum_fast` | `spectrum_spb_bm25_fast` | byte-prism Spectrum decode for code-like chunks |
| `spectrum_fast_cached` | `spectrum_spb_bm25_fast_cached` | byte-prism Spectrum decode with hot payload cache |
| `spectrum_snippet` | `spectrum_snippet_sidecar` | Spectrum search with tracked snippet sidecar hydration |
| `spectrum_serving` | `spectrum_serving_pipeline` | standard Spectrum serving flow: snippets for top-k plus cached full decode for selected result |
| `dense_lsa` | `dense_lsa_numpy` | local dense retrieval proxy |
| `hybrid` | `hybrid_spectrum_dense_rrf` | Spectrum BM25 + dense LSA via reciprocal-rank fusion |
| `faiss` | `faiss_lsa_flat` | optional FAISS flat inner-product index over local LSA vectors |
| `chroma` | `chroma_lsa` | optional Chroma persistent collection over local LSA vectors |
| `opensearch` | `opensearch_bm25_http` | optional OpenSearch HTTP BM25 adapter |
| `zoekt` | `zoekt_cli` | optional Zoekt CLI adapter |
| `lucene` | `lucene_pyserini_bm25` | placeholder for Pyserini/Lucene wiring |

## Optional Adapter Setup

FAISS:

```bash
python -m pip install faiss-cpu
```

Chroma:

```bash
python -m pip install chromadb
```

OpenSearch:

```bash
export OPENSEARCH_URL=http://localhost:9200
# Optional when auth is enabled:
export OPENSEARCH_AUTH=user:password
export OPENSEARCH_INDEX=spectrum-prod-bench
```

Zoekt:

```bash
go install github.com/sourcegraph/zoekt/cmd/zoekt-index@latest
go install github.com/sourcegraph/zoekt/cmd/zoekt-query@latest
```

Lucene:

The current Lucene row is a placeholder for Pyserini-backed BM25. It skips
cleanly until the index build path is implemented.

## Interpretation Rules

Do not treat generated file/path queries as a final production retrieval claim.
They are useful for regression testing and engine plumbing, but stronger
benchmarks need labelled human queries.

For vector runs, `dense_lsa_numpy`, `faiss_lsa_flat`, and `chroma_lsa` use the
same local TF-IDF + SVD vectors. That isolates vector-index behavior, but it is
not equivalent to testing a modern neural embedding model. A later benchmark
should add a fixed embedding model and cache embeddings to disk so FAISS,
Chroma, and hybrid search can be compared fairly.

For production engine runs, report both quality and operating cost:

- index build time
- index bytes
- query latency distribution
- dependency/service version
- corpus size
- query source
- whether the engine stored raw text, vectors, Spectrum payloads, or sidecar
  indexes

## Standard Spectrum Serving Flow

`spectrum_serving` is the default serving shape to benchmark for interactive
RAG and search:

1. Search Spectrum token postings.
2. Return path/title/snippet sidecars for the top-k results.
3. Decode the selected full `.spec` payload on demand with the byte-prism
   decoder.
4. Cache decoded payloads for repeat access.

This separates fast candidate serving from exact full-source hydration.
