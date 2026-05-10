# Spectrum RAG Storage Benchmark

## Purpose

This benchmark compares a conventional local RAG store against a Spectrum RAG
store built from the same chunks.

It measures:

- total disk size
- payload size
- index/vector size
- build time
- build CPU time
- build throughput
- query latency
- query CPU time
- retrieval quality
- decode latency
- decode CPU time
- decoded `.spec` bytes read per query
- lossless round-trip fidelity

The retrieval encoding direction is documented in
`RETRIEVAL_ENCODING_FLOW.md`. The short version: `.spec` remains a lossless,
portable payload format, while retrieval optimization lives in corpus profiles,
chunking/index metadata, ranking sweeps, and diagnostics.

## Harness

Use a JSONL corpus:

```powershell
python rag\storage_benchmark.py `
  --corpus-jsonl data\corpus.jsonl `
  --out-dir benchmarks\generated\storage_benchmark `
  --max-records 200 `
  --chunk-chars 6000 `
  --overlap-chars 600 `
  --queries 40 `
  --top-k 5
```

Each JSONL row should contain `text` or `content`, plus optional `title` or
`path`.

Or use a directory of UTF-8 text files:

```powershell
python rag\storage_benchmark.py `
  --text-dir test_sources `
  --out-dir benchmarks\generated\storage_benchmark_text `
  --max-records 200 `
  --chunk-chars 6000 `
  --overlap-chars 600 `
  --queries 40 `
  --top-k 5
```

To append a cumulative benchmark entry with the reason for the run:

```powershell
python rag\storage_benchmark.py `
  --corpus-jsonl data\corpus.jsonl `
  --out-dir benchmarks\generated\storage_benchmark `
  --append-log `
  --change-note "Describe what changed since the previous run"
```

## What The Script Builds

1. Conventional local RAG baseline:
   - `chunks.jsonl` with raw chunk text
   - persisted TF-IDF sparse vector matrix
   - TF-IDF vocabulary

2. Spectrum RAG store:
   - one `.spec` file per chunk
   - compact binary Spectrum token BM25 postings/frequency index
   - no raw chunk text stored in the Spectrum store

Current baseline uses scikit-learn TF-IDF because Chroma/FAISS are not
installed locally. Chroma, FAISS, neural embeddings, and hybrid baselines can be
added as later comparisons.

## Binary Postings Formats

Spectrum benchmark stores support two binary BM25 postings formats:

| File | Magic | Status | Encoding |
|---|---|---|---|
| `postings.bin` | `SPB1` | compatibility/default build output | fixed-width `(doc_id uint32, term_frequency uint32)` rows |
| `index.bin` | `SPB2` | preferred current format | sorted doc IDs stored as unsigned LEB128 doc-id gaps plus unsigned LEB128 term frequencies |

Build a code store with SPB2 directly:

```bash
python rag/codebase_benchmark.py \
  --source-root . \
  --out-dir benchmarks/generated/codebase_spb2 \
  --postings-format v2
```

Or write both formats for comparison:

```bash
python rag/codebase_benchmark.py \
  --source-root . \
  --out-dir benchmarks/generated/codebase_both \
  --postings-format both
```

Convert an existing Spectrum benchmark store without re-encoding `.spec`
payloads:

```bash
python tools/convert_spectrum_postings_v2.py \
  --store "benchmarks/generated/example/spectrum_spec"
```

Compare SPB1 and SPB2:

```bash
python tools/benchmark_postings_formats.py \
  --store "benchmarks/generated/example/spectrum_spec"
```

## Codebase Harness

`rag/codebase_benchmark.py` scans a source tree, writes language-aware `.spec`
chunks, adds retrieval-only aliases from paths and identifiers, and compares
the result with the same raw+TF-IDF baseline. The aliases are index sidecars
only; the `.spec` payload remains lossless.

The repeatable third-party repo workflow is documented in
`EXTERNAL_CODEBASE_BENCHMARK.md`. Short name: `ECB`.

Example:

```powershell
python rag\codebase_benchmark.py `
  --source-root . `
  --out-dir benchmarks\generated\codebase_self_files `
  --max-files 80 `
  --queries 60
```

## Honest Takeaway

Spectrum is not proven as a universal replacement yet.

What is proven locally:

- `.spec` chunks are lossless.
- `.spec` payloads can be substantially smaller than raw text chunks.
- Spectrum token retrieval can be fast and explainable.
- Decode-on-demand works.
- The binary index fixes the largest storage bottleneck from the early JSON
  index path.

Next proof steps:

1. Add Chroma/FAISS/neural embedding baselines.
2. Run larger mixed code/documentation corpora.
3. Add labelled human queries, not only generated path/content queries.
4. Improve query normalization and ranking against conventional TF-IDF and real
   retrieval baselines.

The working checklist for ranking/query-normalization work lives in
`RAG_RANKING_TODO.md`.
