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
| `spectrum_native` | `spectrum_spb_bm25_native` | optional Rust byte-prism Spectrum decode |
| `spectrum_fast_cached` | `spectrum_spb_bm25_fast_cached` | byte-prism Spectrum decode with hot payload cache |
| `spectrum_native_cached` | `spectrum_spb_bm25_native_cached` | optional Rust byte-prism Spectrum decode with hot payload cache |
| `spectrum_snippet` | `spectrum_snippet_sidecar` | Spectrum search with tracked snippet sidecar hydration |
| `spectrum_serving` | `spectrum_serving_pipeline` | standard Spectrum serving flow: snippets for top-k plus cached full decode for selected result |
| `spectrum_serving_native` | `spectrum_serving_pipeline_native` | standard Spectrum serving flow with optional Rust selected-payload decode |
| `dense_lsa` | `dense_lsa_numpy` | local dense retrieval proxy |
| `hybrid` | `hybrid_spectrum_dense_rrf` | Spectrum BM25 + dense LSA via reciprocal-rank fusion |
| `faiss` | `faiss_lsa_flat` | optional FAISS flat inner-product index over local LSA vectors |
| `chroma` | `chroma_lsa` | optional Chroma persistent collection over local LSA vectors |
| `opensearch` | `opensearch_bm25_http` | optional OpenSearch HTTP BM25 adapter |
| `zoekt` | `zoekt_cli` | optional Zoekt CLI adapter |
| `lucene` | `lucene_pyserini_bm25` | placeholder for Pyserini/Lucene wiring |

### Spectrum Mode Guidance

Use these Spectrum engines for different jobs:

| Engine key | Use this when | Hydration behavior |
|---|---|---|
| `spectrum_snippet` | You need ranked previews, result lists, autocomplete, or lightweight RAG candidates. | No full `.spec` decode; returns snippet sidecars. |
| `spectrum_serving` | You are modelling the production API/UI path. | Returns snippets for top-k and decodes only the selected full payload. |
| `spectrum` | You are debugging or benchmarking full Spectrum hydration. | Decodes full payloads for returned results. |

For application developers, `spectrum_serving` is the default integration
target. `spectrum_snippet` is the fast discovery path inside that flow.
`spectrum` direct is retained as a diagnostic and benchmark baseline rather
than the recommended interactive serving mode.

## Optional Adapter Setup

FAISS:

```bash
python -m pip install faiss-cpu
```

Chroma:

```bash
python -m pip install chromadb
```

Native Spectrum decoder:

```bash
python -m pip install maturin
python -m maturin build --release --manifest-path native/spectrum_native/Cargo.toml
python -m pip install native/spectrum_native/target/wheels/spectrum_native-*.whl
```

Then compare the Python and native byte-prism paths:

```bash
python rag/production_benchmark.py \
  --benchmark-dir benchmarks/generated/java_corpus_commons_lang \
  --out-dir benchmarks/generated/java_corpus_commons_lang_native_decoder_prod \
  --engine spectrum_fast \
  --engine spectrum_native \
  --engine spectrum_serving \
  --engine spectrum_serving_native \
  --hydrate-limit 1
```

If the extension is unavailable, native engines report `skipped` rather than
silently falling back to Python.

The standard `spectrum_serving` runtime uses native selected-payload decode
when the wheel is installed and falls back to the Python reference decoder when
it is not. The explicit `*_native` benchmark engines are retained so Python and
native paths can be compared side by side.

Current Apache Commons Lang signal with `--hydrate-limit 1`:

| Engine | Hydrate ms | E2E ms | P95 E2E ms | Hit@1 | MRR | Recall@5 |
|---|---:|---:|---:|---:|---:|---:|
| `spectrum_spb_bm25_fast` | 1.8571 | 2.2920 | 7.6569 | 0.4466 | 0.5670 | 0.7496 |
| `spectrum_spb_bm25_native` | 0.3486 | 0.8055 | 1.1057 | 0.4466 | 0.5670 | 0.7496 |
| `spectrum_serving_pipeline` | 1.0625 | 1.5007 | 5.2002 | 0.4466 | 0.5670 | 0.7496 |
| `spectrum_serving_pipeline_native` | 0.0838 | 0.5445 | 0.8897 | 0.4466 | 0.5670 | 0.7496 |

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
