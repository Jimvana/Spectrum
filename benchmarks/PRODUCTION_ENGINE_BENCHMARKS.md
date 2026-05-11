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
- average and p95 hydration latency
- selected-payload decode outliers with path, payload size, cache hit, and
  decode time
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
| `spectrum_serving` | `spectrum_serving_pipeline` | standard Spectrum serving flow: snippets for top-k plus cached selected-result decode, with oversized selected payloads deferred by policy |
| `spectrum_serving_native` | `spectrum_serving_pipeline_native` | standard Spectrum serving flow that requires the optional Rust selected-payload decoder |
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
| `spectrum_serving` | You are modelling the production API/UI path. | Returns snippets for top-k, decodes only the selected payload, and can defer oversized exact decode. |
| `spectrum` | You are debugging or benchmarking full Spectrum hydration. | Decodes full payloads for returned results. |

For application developers, `spectrum_serving` is the default integration
target. `spectrum_snippet` is the fast discovery path inside that flow.
`spectrum` direct is retained as a diagnostic and benchmark baseline rather
than the recommended interactive serving mode.

The production benchmark now defaults to `--hydrate-limit 1`, matching the
serving shape used by an interactive UI or API: result lists hydrate from
snippet sidecars, and only the selected result attempts full `.spec` decode.
Spectrum serving also uses a byte-bounded decoded-payload LRU cache and
`--max-auto-decode-spec-bytes` to avoid letting very large selected files
dominate P95 latency. The default threshold is 16 KiB under the `auto` decode
policy. When a selected `.spec` payload exceeds that threshold, the serving row
returns snippet/metadata immediately and records the selected payload as
`deferred`; callers that need exact source can request exact decode.

To compare hydration policies in one report:

```bash
python rag/production_benchmark.py \
  --benchmark-dir benchmarks/generated/codebase_benchmark_self_files \
  --out-dir benchmarks/generated/hydration_tail_matrix \
  --engine spectrum_serving \
  --hydration-matrix \
  --matrix-hydrate-limits 0,1,5
```

Useful controls:

- `--decode-policy none` returns snippet/metadata only and never decodes the
  selected full payload during the benchmark.
- `--decode-policy auto` is the default: decode selected payloads under the
  auto-decode threshold and defer larger selected payloads.
- `--decode-policy exact` always decodes the selected full payload.
- `--hydrate-limit 0` measures search plus snippet-sidecar behavior only.
- `--hydrate-limit 1` models selected-result hydration and is the default.
- `--hydrate-limit -1` hydrates the returned top-k and is mainly for stress
  testing.
- `--max-auto-decode-spec-bytes -1` disables oversized-payload deferral.
- `--force-selected-decode` is a backwards-compatible alias for
  `--decode-policy exact`.
- `--decode-cache-bytes` sets the byte budget for the decoded-payload LRU.

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
when the wheel is installed and falls back to the Python fast decoder when it
is not. The explicit `*_native` benchmark engine is retained for runs that
should skip unless the native extension is available.

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
