# Spectrum

Spectrum is a deterministic retrieval-aware encoding layer for compact, lossless, searchable code and text stores.

The project explores a simple idea:

> The compressed artifact and the retrieval representation can be the same thing.

Instead of storing raw chunks beside a separate retrieval index, Spectrum converts source text into a compact `.spec` representation that remains:

* lossless,
* directly searchable,
* explainable,
* and hydratable back into the original source on demand.

The current implementation maps meaningful language tokens into stable integer IDs, applies run-length and postings compression, and stores a retrieval-aware token layer alongside the compressed payload. Unlike a passive archive format, the encoded representation itself participates in retrieval.

Current dictionary support includes:

* Python
* JavaScript / TypeScript
* HTML / CSS
* SQL
* Rust
* PHP
* XML-compatible payloads
* Java
* C / C++
* Go
* C#
* shell
* JSON / YAML / TOML
* English text

Spectrum is not attempting to compete with gzip, Brotli, or zstd as a pure byte compressor. Those are storage baselines. The goal is different:

> compact + lossless + searchable + explainable retrieval.

---

# Current Production-Shaped Signal

Latest large-corpus benchmark using the `accurate` Spectrum serving profile on
the same 72,601-document Linux-scale repository corpus. Rebench run:
2026-05-11, 80 generated file/path queries, top-k 5, hydrate-limit 5.

| Metric                                  | Spectrum serving (`accurate`) |
| --------------------------------------- | ----------------------------: |
| Corpus documents                        |                        72,601 |
| Raw corpus bytes                        |                 1,028,410,590 |
| Compact `.spec` store bytes             |                   368,706,401 |
| Compact `.spec` ratio                   |              0.3585x raw size |
| Serving store + snippet sidecar bytes   |                   502,080,081 |
| Serving footprint ratio                 |              0.4882x raw size |
| Lossless decode                         |                           Yes |
| Hit@1                                   |                        0.8500 |
| MRR                                     |                        0.8625 |
| Recall@5                                |                        0.8750 |
| Avg query time                          |                       3.75 ms |
| Avg hydrate time                        |                       4.78 ms |
| Avg end-to-end                          |                       8.53 ms |
| P95 end-to-end                          |                      32.41 ms |
| Avg CPU end-to-end                      |                       8.01 ms |
| CPU utilization                         |                        93.89% |
| Peak RSS memory                         |                       ~3.1 GB |

Key observations:

* Retrieval quality improved on the same 72k-document corpus after the latest ranking and serving changes.
* The accurate reranking stage itself remains sub-millisecond because reranking only evaluates the top candidate set rather than the entire corpus.
* Spectrum serving operates as a retrieval-aware storage layer:

  * compact `.spec` payloads remain lossless,
  * snippets are served without full hydration,
  * and only selected payloads are byte-prism decoded on demand.
* The current optimization frontier is candidate generation, fallback-query latency, sidecar footprint, and memory efficiency, not reranking throughput.

---

# Why It Exists

Most retrieval systems store raw chunks and build a separate search index beside them.

Spectrum tests a different architecture:

```text
source code
  -> prism encoding
  -> compact searchable representation
  -> selective hydration back into exact source
```

The long-term goal is a compact intermediate representation that can sit between:

* storage,
* retrieval,
* transport,
* and source reconstruction,

while preserving exact byte-level fidelity.

The project currently focuses on:

* local explainable retrieval,
* lossless code storage,
* compact postings/index structures,
* retrieval-aware compression,
* and production-shaped benchmark pipelines for large code corpora.

## Ecosystem Layout

New ecosystem work lives under `packages/`, with each element in its own subdirectory:

* `packages/core` for the open format, encode/decode, pack IO, and validation.
* `packages/cli` for command line workflows.
* `packages/sdk-js` and `packages/sdk-python` for official SDKs.
* `packages/server` and `packages/dashboard` for the local API and UI.
* `packages/memory` and `packages/index` for agent memory and retrieval.
* `packages/connectors` and `packages/integrations` for data imports and framework adapters.
* `packages/cloud` for optional hosted/team experiments.

The full ecosystem plan is tracked in `docs/ecosystem_architecture.md`.

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

For a repeatable third-party repository benchmark run:

```powershell
spectrum demo `
  --repo https://github.com/vladmandic/human `
  --max-files 0 `
  --query "face detection pipeline" `
  --query "model loading" `
  --clean
```

The demo clones or scans a repository, builds:

* a conventional raw-code TF-IDF retrieval store,
* and a Spectrum `.specpack` BM25 retrieval store,

then:

* verifies byte-for-byte lossless decode fidelity,
* benchmarks retrieval quality and latency,
* measures storage footprint,
* writes the canonical Spectrum corpus as `spectrum.specpack`,
* stores the Spectrum retrieval index inside the pack as `index.bin`,
* and writes Markdown, JSON, and HTML reports under:

```text
demo/runs/
```

The current serving pipeline supports:

* RAM-backed `.spec` payload serving,
* query-windowed snippet sidecars,
* bounded reranking profiles (`fast`, `balanced`, `accurate`),
* selective full-payload hydration,
* and optional native Rust byte-prism decoding.

## Which Spectrum Mode To Use

For product integrations, use `spectrum_serving` as the default runtime shape.
It searches the Spectrum postings, returns fast snippet sidecars for the result
list, and decodes the selected full `.spec` payload only when a caller opens or
uses that result.

Use `spectrum_snippet` when the task only needs ranked previews, search result
lists, autocomplete, or a lightweight RAG candidate set. It avoids full payload
decode and is usually the fastest path.

Use `spectrum` / Spectrum direct mainly for diagnostics and benchmarks. It
searches the Spectrum index and decodes full payloads for returned results, so
it is useful for measuring exact hydration cost and validating `.spec` fidelity,
but it should not be the normal interactive serving path.

| Mode | Best use | Full `.spec` decode |
|---|---|---|
| `spectrum_snippet` | result lists, previews, lightweight retrieval | No |
| `spectrum_serving` | production API/UI flow with on-demand exact payloads | Selected result only |
| `spectrum` | benchmark/debug full hydration behavior | Returned results |

Use `spectrum` for the public CLI command. The older `spec` command remains available as a backwards-compatible alias.

---

## Code Reranking Profiles

Code search can run Spectrum BM25 first, then rerank a bounded candidate set
with code-aware sidecar signals: path parts, filename parts, identifiers,
function/class/export/import names, and cheap proximity matches.

The production benchmark exposes this with `--spectrum-rerank`:

| Profile | Candidate rerank depth | Intended use |
|---|---:|---|
| `off` | 0 | Lowest retrieval work; BM25 only. |
| `fast` | 10 | Latency-sensitive searches where some quality loss is acceptable. |
| `balanced` | 25 | Middle ground for interactive search. |
| `accurate` | 50 | Highest quality default. |
| `quality` | 50 | Backwards-compatible alias for `accurate`. |

You can override the profile depth directly:

```powershell
python rag\production_benchmark.py `
  --benchmark-dir benchmarks\generated\conventional_vs_spectrum_all_queries `
  --engine spectrum_serving `
  --spectrum-rerank accurate `
  --spectrum-rerank-candidates 35 `
  --hydrate-limit 1
```

Recent local code-search signal:

| Corpus | Profile | Hit@1 | MRR | Recall@5 | Avg E2E ms |
|---|---|---:|---:|---:|---:|
| Apache Commons Lang | `accurate` / top-50 | 0.828 | 0.876 | 0.937 | 4.401 |
| Apache Commons Lang | `balanced` / top-25 | 0.820 | 0.866 | 0.925 | 4.118 |
| Self-files | `accurate` / top-50 | 0.868 | 0.898 | 0.936 | 3.477 |
| Self-files | `balanced` / top-25 | 0.807 | 0.831 | 0.861 | 2.482 |

All timings are milliseconds. These runs used small generated-query code
benchmarks, so treat them as a profile tuning signal rather than a large-scale
production claim.

