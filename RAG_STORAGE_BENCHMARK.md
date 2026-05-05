# Spectrum RAG Storage Benchmark

## Purpose

This is now the main proof path for Spectrum.

The goal is to compare a conventional local RAG store against a Spectrum RAG
store built from the same chunks, measuring:

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

This is a better proof than trying to perfectly render Wikipedia in Chrome.
Wikipedia is useful as a large text corpus, but the real claim is
retrieval-ready storage.

The retrieval encoding direction is documented in
`RETRIEVAL_ENCODING_FLOW.md`. The short version: `.spec` remains a lossless,
portable payload format, while retrieval optimization lives in corpus profiles,
chunking/index metadata, ranking sweeps, and diagnostics.

## Harness

Run:

```powershell
python rag\storage_benchmark.py `
  --page-index wiki_enwiki_fullxml_sample\page_index.json `
  --out-dir rag\storage_benchmark_6k `
  --max-pages 120 `
  --chunk-chars 6000 `
  --overlap-chars 600 `
  --queries 40 `
  --top-k 5
```

To append a cumulative benchmark entry with the reason for the run:

```powershell
python rag\storage_benchmark.py `
  --page-index wiki_enwiki_fullxml_sample\page_index.json `
  --out-dir rag\storage_benchmark_6k `
  --max-pages 120 `
  --chunk-chars 6000 `
  --overlap-chars 600 `
  --queries 40 `
  --top-k 5 `
  --append-log `
  --change-note "Describe what changed since the previous run"
```

The cumulative score history lives in `BENCHMARK_LOG.md`.

Cost metrics now include both wall-clock time and Python process CPU time.
CPU time is a rough local proxy for compute and power cost; it is not a direct
energy measurement. On multi-threaded library calls, process CPU can exceed wall
time because it accumulates CPU used across worker threads.

The script builds:

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

Spectrum benchmark stores now support two binary BM25 postings formats:

| File | Magic | Status | Encoding |
|---|---|---|---|
| `postings.bin` | `SPB1` | compatibility/default build output | fixed-width `(doc_id uint32, term_frequency uint32)` rows |
| `postings_v2.bin` | `SPB2` | compressed sidecar, preferred by loaders when present | sorted doc IDs stored as unsigned LEB128 doc-id gaps plus unsigned LEB128 term frequencies |

SPB2 preserves the same in-memory `BinarySpectrumBM25` postings shape as SPB1,
so scoring and ranking semantics are unchanged. It only changes the on-disk
representation. Loaders prefer `postings_v2.bin` when it exists and fall back to
`postings.bin` for old benchmark stores.

Build a store with SPB2 directly:

```bash
python rag/codebase_benchmark.py \
  --source-root . \
  --out-dir rag/codebase_benchmark_spb2 \
  --postings-format v2
```

Or write both formats for comparison:

```bash
python rag/codebase_benchmark.py \
  --source-root . \
  --out-dir rag/codebase_benchmark_both \
  --postings-format both
```

Convert an existing Spectrum benchmark store without re-encoding `.spec`
payloads:

```bash
python tools/convert_spectrum_postings_v2.py \
  --store "test data/gpt55_thinking_max_distill_god_seed_25k/spectrum_spec"
```

Compare SPB1 and SPB2:

```bash
python tools/benchmark_postings_formats.py \
  --store "test data/gpt55_thinking_max_distill_god_seed_25k/spectrum_spec"
```

Current 25k HF/generated-text store result:

| Metric | SPB1 | SPB2 |
|---|---:|---:|
| Postings file | 62,550,276 B | 15,759,020 B |
| Full Spectrum store | 132,005,046 B | 85,213,790 B |
| Load time | 1,100.471 ms | 3,407.621 ms |
| Avg query latency | 6.850 ms | 6.736 ms |
| P95 query latency | 11.718 ms | 11.412 ms |
| Top-5 equality | n/a | true |
| Max score difference | n/a | 0.0 |

The SPB2 postings file is 74.81% smaller than SPB1, and the full Spectrum store
is 35.45% smaller. Against the raw TF-IDF baseline for the same 25k corpus,
Spectrum+SPB2 is 42,314,647 bytes smaller, or 33.18% smaller overall. The
expected tradeoff is slower load time because SPB2 currently decodes all
postings eagerly into the same Python structures as SPB1; query latency stays
flat because the search path is unchanged after loading.

Current large Java codebase result:

```bash
python rag/codebase_benchmark.py \
  --source-root /Users/video/jdk \
  --out-dir rag/codebase_benchmark_openjdk_jdk_java_spb2 \
  --max-files 0 \
  --queries 80 \
  --postings-format v2
```

| Store | Bytes | Ratio vs raw chunks | Payload bytes | Index/vector bytes | Hit@1 | MRR | Recall@5 | Avg query ms | P95 query ms |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| Conventional raw+TF-IDF | 507,690,480 | 1.242x | 435,772,020 | 71,918,310 | 0.200 | 0.258 | 0.362 | 18.856 | 22.474 |
| Spectrum `.spec`+SPB2 BM25 | 185,950,831 | 0.455x | 144,726,790 | 41,223,626 | 0.325 | 0.439 | 0.637 | 15.347 | 28.328 |

This run covered 53,780 file-level chunks from OpenJDK, including 52,532 Java
files, and verified byte-for-byte lossless decoding with zero fidelity
failures. Against the previous OpenJDK SPB1 result, SPB2 reduced the Spectrum
index by 61.94% and the full Spectrum store by 26.51% while preserving the same
rankings. Against the raw+TF-IDF baseline, Spectrum was 63.37% smaller overall
and better on generated path/identifier queries, with slower build time and a
higher p95 query latency.

## Codebase Harness

The first non-Wiki comparison lives in `rag/codebase_benchmark.py`. It scans a
source tree, writes language-aware `.spec` chunks, adds retrieval-only aliases
from paths and identifiers, and compares the result with the same raw+TF-IDF
baseline. The aliases are index sidecars only; the `.spec` payload remains
lossless.

The repeatable third-party repo workflow is documented in
`EXTERNAL_CODEBASE_BENCHMARK.md`. Short name: `ECB`.

Run:

```powershell
python rag\codebase_benchmark.py `
  --source-root . `
  --out-dir rag\codebase_benchmark_self_files `
  --max-files 80 `
  --queries 60
```

Current self-codebase signal:

| Store | Bytes | Ratio vs raw chunks | Payload bytes | Index/vector bytes | Hit@1 | MRR | Recall@5 | Avg query ms |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| Conventional raw+TF-IDF | 2,772,764 | 1.218x | 2,395,479 | 377,135 | 0.217 | 0.359 | 0.600 | 0.446 |
| Spectrum `.spec`+binary BM25 | 1,027,896 | 0.452x | 746,406 | 281,110 | 0.333 | 0.457 | 0.683 | 0.052 |

Fidelity passed on all 80 file-level chunks. This query set is generated from
file paths and identifiers, so it is a smoke test rather than a final code
retrieval benchmark. The next step is a larger external codebase with labelled
queries such as "where is binary postings written?" or "decode spec header".

External codebase smoke test:

```powershell
git clone --depth=1 https://github.com/vladmandic/human external_repos\human

python rag\codebase_benchmark.py `
  --source-root external_repos\human `
  --out-dir rag\codebase_benchmark_human `
  --max-files 0 `
  --queries 120 `
  --exclude-dir dist `
  --exclude-dir typedoc `
  --exclude-dir models `
  --exclude-dir build `
  --exclude-dir coverage
```

Source revision: `d0c4c83`.

| Store | Bytes | Ratio vs raw chunks | Payload bytes | Index/vector bytes | Hit@1 | MRR | Recall@5 | Avg query ms |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| Conventional raw+TF-IDF | 2,912,945 | 1.326x | 2,279,391 | 633,403 | 0.242 | 0.326 | 0.525 | 0.440 |
| Spectrum `.spec`+binary BM25 | 1,230,156 | 0.560x | 897,993 | 331,782 | 0.317 | 0.390 | 0.542 | 0.079 |

Fidelity passed on all 172 file-level chunks across TypeScript, JavaScript,
HTML, CSS, and Markdown.

## Current Result: 6k Character Chunks

Source:

- `wiki_enwiki_fullxml_sample/page_index.json`
- 120 pages
- 782 chunks
- 4,120,949 raw chunk bytes

Storage:

| Store | Bytes | Ratio vs raw chunks | Build seconds |
|---|---:|---:|---:|
| Conventional raw+TF-IDF | 6,430,395 | 1.560x | 0.657 |
| Spectrum `.spec`+binary BM25 | 4,172,510 | 1.013x | 5.947 |

Components:

| Store | Payload bytes | Index/vector bytes | Metadata bytes |
|---|---:|---:|---:|
| Conventional raw+TF-IDF | 4,226,166 | 2,204,110 | 119 |
| Spectrum `.spec`+binary BM25 | 2,275,732 | 1,896,562 | 216 |

Retrieval:

| Store | Hit@1 | MRR | Recall@5 | Avg query ms | Avg decode ms |
|---|---:|---:|---:|---:|---:|
| Conventional raw+TF-IDF | 1.000 | 1.000 | 1.000 | 1.233 | 0.000 |
| Spectrum `.spec`+binary BM25 | 0.923 | 0.936 | 0.962 | 2.988 | 2.932 |

Latest cost run:

| Store | Build CPU sec | MiB/CPU sec | Avg query CPU ms | Avg decode CPU ms | Avg decode input bytes |
|---|---:|---:|---:|---:|---:|
| Conventional raw+TF-IDF | 0.672 | 5.849 | 0.000 | 0.000 | 0.0 |
| Spectrum `.spec`+binary BM25, verified, DF50 | 5.391 | 0.729 | 0.488 | 1.465 | 3,013.6 |
| Spectrum `.spec`+binary BM25, production DF50 | 3.906 | 1.006 | 0.488 | 2.441 | 3,013.6 |

Fidelity:

- Spectrum lossless round-trip: true
- Fidelity failures: 0

## Current Result: 1.8k Character Chunks

Source:

- 120 pages
- 2,377 chunks
- 4,130,031 raw chunk bytes

Storage:

| Store | Bytes | Ratio vs raw chunks |
|---|---:|---:|
| Conventional raw+TF-IDF | 7,234,684 | 1.752x |
| Spectrum `.spec`+binary BM25 | 5,913,788 | 1.432x |

Components:

| Store | Payload bytes | Index/vector bytes |
|---|---:|---:|
| Conventional raw+TF-IDF | 4,374,718 | 2,859,846 |
| Spectrum `.spec`+binary BM25 | 2,868,949 | 3,044,622 |

Latest cost run:

| Store | Build CPU sec | MiB/CPU sec | Avg query CPU ms | Avg decode CPU ms | Avg decode input bytes |
|---|---:|---:|---:|---:|---:|
| Conventional raw+TF-IDF | 0.703 | 5.602 | 1.465 | 0.000 | 0.0 |
| Spectrum `.spec`+binary BM25, production b=1.0 DF90 | 4.266 | 0.923 | 0.488 | 0.977 | 1,209.6 |

Interpretation:

- Spectrum payload is much smaller than raw chunk text.
- The compact binary BM25 index removes the previous JSON-index bottleneck.
- Spectrum now wins total store size on both tested chunk profiles.
- With larger chunks, Spectrum is close to raw payload size while remaining
  retrieval-ready.
- The next engineering target is retrieval quality and larger, more realistic
  labelled query sets.

## Honest Takeaway

Spectrum is not proven as a universal replacement yet.

What is proven locally:

- `.spec` chunks are lossless.
- `.spec` payloads are substantially smaller than raw text chunks.
- Spectrum token retrieval can reach similar Hit@1 on this generated query set.
- Decode-on-demand works.
- The binary index fixes the largest storage bottleneck, though conventional
  TF-IDF remains faster on these runs.

Next proof step:

1. Add a Chroma/FAISS/neural embedding baseline.
2. Run the same benchmark on the larger `wiki_enwiki_fullxml_1hr` page index.
3. Add labelled human queries, not only generated title/content queries.
4. Improve query normalization and ranking against conventional TF-IDF.

The working checklist for ranking/query-normalization work lives in
`RAG_RANKING_TODO.md`. Future sessions should mark items off there as they are
implemented and re-tested.
