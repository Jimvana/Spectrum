# Spectrum

Spectrum is a deterministic semantic encoding for compact, lossless, searchable
code and text stores. The CLI includes a bring-your-own-repo demo so you can
benchmark Spectrum against a conventional raw-code retrieval store on your own
machine.

The project converts source text into `.spec` files by mapping meaningful language tokens to stable integer IDs, run-length encoding repeated IDs, and compressing the resulting stream. Unlike a passive compressor, the stored representation keeps a searchable semantic-token layer: token IDs can be indexed directly, compared, and decoded back to the original source on demand.

## Why It Exists

Most retrieval systems store raw chunks and build a separate search index beside them. Spectrum tests a different idea:

> The compressed artifact and the retrieval representation can be the same thing.

The current proof path is local, explainable, compressed retrieval for code and structured text. The project is not trying to beat gzip, Brotli, or zstd as a pure byte compressor. Those tools are storage baselines. Spectrum's claim is that `.spec` can be compact, lossless, searchable, and explainable at the same time.

## Try The Demo

Install or update the local CLI from this checkout:

```powershell
cd "CLI Tool"
npm install -g . --force
```

Then run the guided demo:

```powershell
spectrum demo
```

For a repeatable third-party repo run:

```powershell
spectrum demo `
  --repo https://github.com/vladmandic/human `
  --max-files 0 `
  --query "face detection pipeline" `
  --query "model loading" `
  --clean
```

The demo clones or scans a repository, builds a conventional raw-code TF-IDF
store and a Spectrum `.spec` + SPB2 BM25 store, verifies byte-for-byte lossless
decode fidelity, and writes Markdown, JSON, and HTML reports under `demo/runs/`.

Use `spectrum` for the public CLI command. The older `spec` command remains
available as a backwards-compatible alias.

## Current Status

- `.spec` binary format proven with byte-for-byte round trips.
- Dictionary v10 covers Python, HTML, JavaScript, TypeScript, CSS, SQL, Rust, PHP, English text, and XML/Wiki syntax.
- Encoders, decoders, migration tooling, and version snapshots are included.
- Wikipedia/XML shard experiments verify large lossless corpora locally.
- RAG storage benchmarks compare conventional raw text plus TF-IDF against `.spec` chunks plus a compact Spectrum BM25 index. Current loaders support SPB1 fixed-width postings and prefer SPB2 varint/delta postings when `postings_v2.bin` exists.
- The standard Spectrum serving path now preloads `.spec` payload bytes into RAM, serves query-windowed snippet sidecars for result lists, and byte-prism decodes the selected full payload on demand.

Current 120-page Wikipedia sample signal with 6k-character chunks:

| Store | Total bytes | Payload bytes | Index/vector bytes | Hit@1 | MRR | Avg query time |
|---|---:|---:|---:|---:|---:|---:|
| Conventional raw+TF-IDF | 6,430,395 | 4,226,166 | 2,204,110 | 1.000 | 1.000 | 1.233 ms |
| Spectrum `.spec`+binary BM25 | 4,172,510 | 2,275,732 | 1,896,562 | 0.923 | 0.936 | 2.988 ms |

Current codebase self-test signal with 80 files from this repository:

| Store | Total bytes | Payload bytes | Index/vector bytes | Hit@1 | MRR | Avg query time |
|---|---:|---:|---:|---:|---:|---:|
| Conventional raw+TF-IDF | 2,772,764 | 2,395,479 | 377,135 | 0.217 | 0.359 | 0.446 ms |
| Spectrum `.spec`+binary BM25 | 1,027,896 | 746,406 | 281,110 | 0.333 | 0.457 | 0.052 ms |

The benchmark is still small and should not be treated as a production retrieval claim. It is a proof harness for measuring storage size, query quality, latency, decode cost, and lossless fidelity.

Current 25k generated-text store after converting the Spectrum BM25 postings
index from SPB1 to SPB2:

| Store | Total bytes | Total MiB | Notes |
|---|---:|---:|---|
| Raw TF-IDF baseline | 127,528,437 | 121.62 | raw chunks plus TF-IDF |
| Spectrum `.spec` + SPB1 | 132,005,046 | 125.89 | original fixed-width postings |
| Spectrum `.spec` + SPB2 | 85,213,790 | 81.27 | varint/delta postings, exact same top-5 and scores |

SPB2 reduced `postings.bin` equivalent storage from 62,550,276 bytes to
15,759,020 bytes on that corpus.

Current large Java ECB signal after rebuilding OpenJDK with SPB2 postings:

| Store | Total bytes | Payload bytes | Index/vector bytes | Hit@1 | MRR | Recall@5 | Avg query time |
|---|---:|---:|---:|---:|---:|---:|---:|
| Conventional raw+TF-IDF | 507,690,480 | 435,772,020 | 71,918,310 | 0.200 | 0.258 | 0.362 | 18.856 ms |
| Spectrum `.spec`+SPB2 BM25 | 185,950,831 | 144,726,790 | 41,223,626 | 0.325 | 0.439 | 0.637 | 15.347 ms |

The Java run covered 53,780 OpenJDK file-level chunks, including 52,532 Java
files, and verified lossless decoding with zero fidelity failures. SPB2 reduced
the previous OpenJDK Spectrum index by 61.94% while preserving the same
generated-query rankings.

Current Java production-serving signal on Apache Commons Lang:

| Engine | E2E ms | P95 E2E ms | Hit@1 | MRR | Recall@5 | CPU E2E ms | Stored bytes |
|---|---:|---:|---:|---:|---:|---:|---:|
| Spectrum snippets | 0.461 | 0.784 | 0.447 | 0.567 | 0.750 | 0.383 | 2,945,660 |
| Raw TF-IDF | 0.647 | 0.886 | 0.163 | 0.236 | 0.366 | 0.629 | n/a in production runner |
| Raw BM25 | 1.576 | 2.348 | 0.284 | 0.392 | 0.569 | 1.478 | n/a in production runner |
| Spectrum serving | 1.594 | 5.492 | 0.447 | 0.567 | 0.750 | 1.587 | 2,958,855 |
| Dense LSA | 14.048 | 15.125 | 0.166 | 0.231 | 0.349 | 13.381 | 1,169,408 |
| Hybrid Spectrum+LSA | 16.497 | 19.723 | 0.284 | 0.408 | 0.618 | 15.871 | 3,772,846 |

The Java production run used 571 files/chunks from Apache Commons Lang and 571
generated file/path queries. The storage builder reported 8,975,222 raw chunk
bytes, 10,496,085 bytes for conventional raw+TF-IDF, and 2,603,438 bytes for
Spectrum `.spec`+SPB2 BM25 before serving snippets. Optional FAISS, Chroma,
OpenSearch, Zoekt, and Lucene/Pyserini adapters were skipped on this machine
because their dependencies or services were not installed.

<img width="640" height="480" alt="latency_vs_quality_size" src="https://github.com/user-attachments/assets/09ee679a-ab72-462e-835d-b1aede977c19" />


## The `.spec` Format

Each `.spec` file has a 16-byte uncompressed header followed by a zlib-compressed token stream.

```text
Header:
  [0:4]   Magic:           b'SPEC'
  [4:6]   Dict version:    uint16 BE
  [6:8]   Flags:           uint16 BE
  [8:12]  Original length: uint32 BE
  [12:14] Language ID:     uint16 BE
  [14:16] Checksum:        uint16 BE

Body:
  zlib-compressed uint32 token IDs
```

Unknown characters fall back to ASCII or Unicode marker IDs, so decoding remains lossless. The header stores dictionary version, language ID, source length, flags, and a checksum for verification.

| Component | What it answers | Cost |
|---|---|---|
| Spectrum snippets | “What are the likely top results, and what preview text should I show?” | Very fast; tiny hydration cost because it reads short snippet sidecars instead of decoding full `.spec` payloads. |
| Spectrum serving | “Give me previews, and when the user or agent chooses a result, give me the exact full source text.” | Slightly slower because it uses snippets for the result list, then decodes one selected full `.spec` payload on demand and caches it. |


## Repository Layout

```text
encoder/             Original PNG/token encoder proof
decoder/             Original PNG/token decoder proof
spec_format/         Current .spec encoder, decoder, migrator, and frozen versions
tokenizers/          Language-specific tokenizers
rag/                 Retrieval and storage benchmark harnesses
tools/               Wikipedia verification, indexing, and read tools
versions/            Versioned snapshots of the encoding stack
Runtime/             Runtime planning and implementation notes
```

Large Wikipedia dumps, generated benchmark stores, `.spec` outputs, caches, and local artifacts are intentionally ignored by Git.

## Basic Usage

Encode and decode workflows are currently Python script based. The exact commands vary by experiment, but the active RAG proof harness is:

```powershell
python rag\storage_benchmark.py `
  --page-index wiki_enwiki_fullxml_sample\page_index.json `
  --out-dir benchmarks\generated\storage_benchmark_6k `
  --max-pages 120 `
  --chunk-chars 6000 `
  --overlap-chars 600 `
  --queries 40 `
  --top-k 5
```

The active codebase proof harness is:

```powershell
python rag\codebase_benchmark.py `
  --source-root . `
  --out-dir benchmarks\generated\codebase_benchmark_self_files `
  --max-files 80 `
  --queries 60
```

Use `--postings-format v2` or `--postings-format both` on the storage and
codebase benchmark builders to write SPB2 indexes. Existing stores can be
converted with `tools/convert_spectrum_postings_v2.py`, and SPB1/SPB2 equality
can be checked with `tools/benchmark_postings_formats.py`.

See `PROJECT_OUTLINE.md`, `RETRIEVAL_POSITIONING.md`, `RETRIEVAL_ENCODING_FLOW.md`, `RAG_STORAGE_BENCHMARK.md`, `RAG_RANKING_TODO.md`, and `BENCHMARK_LOG.md` for the detailed design notes and benchmark history.

For repeatable third-party repository tests, use the External Codebase
Benchmark workflow in `EXTERNAL_CODEBASE_BENCHMARK.md`. In future notes,
`ECB` means: clone a repo, convert supported source files into lossless `.spec`
chunks, build the Spectrum BM25 store, build the raw+TF-IDF baseline, verify
fidelity, and compare storage/retrieval/latency.

For comparisons against production-style retrieval engines, use
`rag/production_benchmark.py` against an existing codebase benchmark directory.
The runner supports local TF-IDF, raw BM25, Spectrum BM25, byte-prism Spectrum
decode, the standard `spectrum_serving` flow (query-windowed top-k snippets plus
RAM-backed cached on-demand full `.spec` decode), local dense LSA, hybrid reciprocal-rank fusion,
and dependency-gated adapters for FAISS, Chroma, OpenSearch, Zoekt, and
Lucene/Pyserini. Generated stores now live under `benchmarks/generated/`, and
tracked summaries live under `benchmarks/reports/`. See
`benchmarks/PRODUCTION_ENGINE_BENCHMARKS.md`.

## Roadmap

- Improve query normalization and ranking quality for Spectrum BM25.
- Formalize retrieval encoding profiles so `.spec` corpus builds carry chunking, normalization, indexing, and ranking settings without changing the lossless payload format.
- Complete stronger production adapters for Lucene, Zoekt, OpenSearch, Chroma,
  FAISS, neural embeddings, and hybrid retrieval.
- Expand non-Wiki profile testing with larger codebases and code-aware labelled queries.
- Package corpus shards, manifests, and dictionary libraries into a portable `.specpack` format.
- Decide whether library dependencies should remain manifest-level or move into a future header format.

## License

Spectrum Algo is released under the MIT License. See `LICENSE`.
