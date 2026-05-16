# Spectrum

Spectrum is a local-first way to turn a codebase into a compact, lossless,
searchable `.specpack` that can be queried and restored byte-for-byte.

The developer preview ships first as an npm-installed CLI. The current preview
is `spectrumstore@0.1.0-preview.4`.

## Turn The Key

Install Spectrum, point it at a repo, and let the guided loader do the rest:

```powershell
npm install -g spectrumstore
spectrum load
```

`spectrum load` walks you through the complete local path: it checks the
install, packs your repo into a compact `.specpack`, then starts the local HTTP
API so an agent, app, or retrieval workflow can search and hydrate exact source.

Prefer copy/paste commands instead of prompts:

```powershell
spectrum load ./my-repo ./my-repo.specpack --yes
```

After it starts, your pack is available locally:

```text
http://127.0.0.1:7777
```

Useful checks:

```powershell
curl http://127.0.0.1:7777/health
curl http://127.0.0.1:7777/packs
```

Use it when you want local, exact, searchable codebase packs for agents, RAG
tools, and retrieval workflows without keeping raw chunks and a separate search
store as the only source of truth.

See the [5-minute quickstart](docs/quickstart.md), the
[comparison guide](docs/why-spectrum.md), and the
[release checklist](RELEASE_CHECKLIST.md).

## Spectrum Benchmark Demo

[![Watch the Spectrum benchmark demo](https://img.youtube.com/vi/vVIzw3rQUHI/maxresdefault.jpg)](https://youtu.be/vVIzw3rQUHI)

Watch Spectrum benchmarked against TF-IDF, Raw BM25, Dense Vector retrieval, and FAISS Flat, including live retrieval, decoding, and byte-for-byte fidelity verification.

## Why Spectrum Matters

Spectrum combines storage and retrieval into one deterministic representation.
Instead of keeping raw chunks, compressed archives, and separate search indexes,
Spectrum stores source material as compact `.specpack` data that can be searched,
retrieved, decoded, and verified back to the original bytes.

This makes it useful for:

- AI agent memory
- codebase retrieval
- local RAG systems
- compact searchable archives
- exact reconstruction of source context

## Spectrum Store Developer Preview

The first turnkey product surface is **Spectrum Store Developer Preview**: a
local-first command line tool for creating compact, lossless, searchable
`.specpack` stores from folders of code or text.

Install from npm:

```powershell
npm install -g spectrumstore
spectrum doctor
```

To pin the preview channel explicitly:

```powershell
npm install -g spectrumstore@preview
```

Install from a local checkout while developing Spectrum itself:

```powershell
npm install -g . --force
```

Then run the guided workflow:

```powershell
spectrum load ./docs ./docs.specpack --yes
```

Or run the core workflow manually:

```powershell
spectrum pack ./docs ./docs.specpack --json
spectrum serve ./docs.specpack --port 7777
```

As the project changes, append new continuity notes, deployment docs, or source
files without rebuilding the pack from scratch:

```powershell
spectrum append ./docs.specpack ./project-notes --json
```

If a source path already exists in the pack, append fails by default. Use
`--replace` when you intentionally want the newer file to replace the existing
packed document. Appending drops any embedded `index.bin` because it is derived
from the old manifest; rebuild it with `spectrum index ./docs.specpack --embed`
when you want embedded search again.

For a portable project pack with standard agent context files, use the project
workflow:

```powershell
spectrum project init ./my-project ./my-project.specpack --name "My Project"
spectrum project add ./my-project.specpack ./new-notes
spectrum project serve ./my-project.specpack --port 7777
```

This creates `.spectrum-project/` inside the project with files such as
`project.md`, `deploy.md`, `ssh.md`, and `secrets.refs.md`. When served, agents
can fetch the starter context bundle from:

```text
http://127.0.0.1:7777/projects/repo/context
```

Humans can use the built-in local dashboard:

```text
http://127.0.0.1:7777/project
```

Additional diagnostics:

```powershell
spectrum verify ./docs.specpack --json
spectrum index ./docs.specpack --embed --json
spectrum search ./docs.specpack "authentication middleware" --top 5 --json
spectrum unpack ./docs.specpack ./docs-restored --json
```

The package name is `spectrumstore`, and it exposes both `spectrum` and
`spectrumstore` commands. It requires Node.js 18+ and Python 3.10+ on `PATH`;
the preview npm package bundles the Python Spectrum CLI, index layer, core API,
and current codec runtime so users do not need to set `PYTHONPATH` or
`SPECTRUM_REPO_ROOT` manually.

## Spectrum Benchmark HUD

The repository includes a local **Spectrum CodeRAG Benchmark HUD** for visually
comparing repo-level code retrieval against common RAG baselines on real code
corpora. It streams live build, storage density, latency, context quality,
recall, MRR, deterministic reconstruction, and Spectrum debug events for:

* Spectrum CodeRAG,
* FAISS Flat,
* raw BM25,
* TF-IDF,
* Chroma when available,
* and hybrid sparse+dense retrieval.

Run it from the repository root on Windows:

```powershell
powershell -ExecutionPolicy Bypass -File .\benchmark_hud\launch-windows.ps1
```

Run it from the repository root on macOS:

```bash
chmod +x benchmark_hud/launch-mac.command
./benchmark_hud/launch-mac.command
```

Then open:

```text
http://127.0.0.1:8765
```

Use `Small`, `Medium`, or `Large` for built-in corpora, or choose `My own repo`
and enter a public GitHub repository as `owner/name` or
`https://github.com/owner/name`. Custom repo runs clone the repository into that
run's local artifact folder and benchmark it with the same engines. The HUD can
export a completed run as JSON, including the repository name, resolved CodeRAG
configuration, engine metrics, and Spectrum low-rank/miss debug trace. Generated
run artifacts are written under `benchmark_hud/runs/` and are ignored by Git.

The HUD currently uses `retrieval_mode: "coderag"` for Spectrum. The
`Fast`/`Balanced`/`Accurate` buttons switch the CodeRAG rerank depth and scoring
profile, not the generic Spectrum codec or index format.

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
* Shell / PowerShell
* JSON / YAML / TOML
* English text

Spectrum is not attempting to compete with gzip, Brotli, or zstd as a pure byte compressor. Those are storage baselines. The goal is different:

> compact + lossless + searchable + explainable retrieval.

---

# Current Production-Shaped Signal

Latest large-corpus benchmark using the `accurate` Spectrum serving profile on
the same 72,601-document Linux-scale repository corpus. Rebench run:
2026-05-11, 80 generated file/path queries, top-k 5, hydrate-limit 1,
`auto` decode policy, 16 KiB auto-decode threshold.

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
| Avg query time                          |                       3.43 ms |
| Avg hydrate time                        |                       1.35 ms |
| Avg end-to-end                          |                       4.78 ms |
| P95 end-to-end                          |                       6.35 ms |
| Avg CPU end-to-end                      |                       4.69 ms |
| CPU utilization                         |                        98.15% |
| Peak RSS memory                         |                       ~3.1 GB |

Key observations:

* Retrieval quality improved on the same 72k-document corpus after the latest ranking and serving changes.
* The accurate reranking stage itself remains sub-millisecond because reranking only evaluates the top candidate set rather than the entire corpus.
* Spectrum serving operates as a retrieval-aware storage layer:

  * compact `.spec` payloads remain lossless,
  * snippets are served without full hydration,
  * and only selected payloads are byte-prism decoded on demand.
* The current serving default hydrates only the selected result with the `auto`
  decode policy, which defers exact decode for selected `.spec` payloads above
  16 KiB. In the latest large-corpus run this preserved quality, reduced average
  hydrated bytes by about 79% versus the earlier hydrate-limit 5 run, and
  lowered P95 E2E from 32.41 ms to 6.35 ms.
* The current optimization frontier is selected-payload decode, sidecar
  footprint, and memory efficiency, not reranking throughput.

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

The full ecosystem plan is tracked in `docs/ecosystem_architecture.md`. The
developer manual for the SDKs, CLI, HTTP API, and RAG workflows is
`ECOSYSTEM_MANUAL.md`.

## Try The Legacy Benchmark Demo

The published `spectrumstore` preview focuses on `pack`, `search`, `verify`,
and `unpack`. The older guided benchmark demo still runs from the legacy CLI in
this checkout:

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
* selected-result hydration instead of top-k full hydration,
* optional size-aware full-decode deferral for oversized selected payloads,
* byte-bounded decoded-payload LRU caching,
* and native Rust byte-prism decoding when the extension is installed, with a
  Python fast-decoder fallback.

## Which Spectrum Mode To Use

For product integrations, use `spectrum_serving` as the default runtime shape.
It searches the Spectrum postings, returns fast snippet sidecars for the result
list, and decodes the selected full `.spec` payload only when a caller opens or
uses that result. The serving path keeps result-list hydration cheap by default:
top-k results use snippets, selected-result hydration is the benchmark default,
decoded payloads are held in a byte-bounded LRU cache, and very large selected
`.spec` payloads above the 16 KiB auto-decode threshold can be deferred so the
caller gets snippet/metadata immediately and requests exact full decode
explicitly when needed.

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
| `spectrum_serving` | production API/UI flow with on-demand exact payloads | Selected result only; oversized payloads can defer exact decode |
| `spectrum` | benchmark/debug full hydration behavior | Returned results |

Use `spectrum` for the public CLI command. The older `spec` command remains available as a backwards-compatible alias.

---

## Spectrum CodeRAG Mode

Spectrum CodeRAG is the repo-aware retrieval mode used by the Benchmark HUD for
code assistant tasks. It is deliberately separate from generic Spectrum
retrieval. CodeRAG adds ranking signals that make sense for repositories:

* exact filename and path-stem matches,
* source/config/doc path intent,
* dotfile and package/plugin manifest handling,
* environment disambiguation such as production vs staging and lite vs full,
* root config preference over nested config when the query does not ask for a
  nested app path,
* penalties for generic docs, benchmark files, advisory folders, and sibling
  files that match broad identifiers while missing the most specific query term,
* deterministic tie-breaks using exact filename/stem, path specificity, fewer
  extra filename terms, and shallower paths.

These are **not** global Spectrum retrieval defaults. Base Spectrum serving can
still use a neutral `CodeRerankProfile(mode="base")`, while CodeRAG uses
`coderag_rerank_profile(...)`. This keeps future document, memory, archive, or
general text retrieval tuning isolated from repo-specific CodeRAG heuristics.

User-facing switching is partial today:

* The Benchmark HUD switches CodeRAG quality profiles with
  `Fast` / `Balanced` / `Accurate`.
* The HUD does not yet expose a generic `base` vs `coderag` mode selector; it is
  intentionally a CodeRAG benchmark surface.
* Programmatic callers can choose the profile object they pass into
  `SpectrumServingRetriever`: neutral base profile or CodeRAG profile.

---

## CodeRAG Reranking Profiles

CodeRAG runs Spectrum BM25 first, then reranks a bounded candidate set with
repo-aware sidecar signals: path parts, filename parts, identifiers,
function/class/export/import names, environment/config/doc cues, and cheap
proximity matches.

The production benchmark currently exposes this with `--spectrum-rerank`:

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

Hydration-tail runs can compare snippet-only, selected-result, and top-k
hydration in one report:

```powershell
python rag\production_benchmark.py `
  --benchmark-dir benchmarks\generated\conventional_vs_spectrum_all_queries `
  --engine spectrum_serving `
  --hydration-matrix `
  --matrix-hydrate-limits 0,1,5
```

Use `--force-selected-decode` or `--max-auto-decode-spec-bytes -1` when a
benchmark needs exact full selected-payload decode even for oversized files.
Use `--decode-policy none` for snippet/metadata-only serving, `--decode-policy
auto` for threshold-aware selected decode, and `--decode-policy exact` when the
caller knows it needs full text immediately and accepts the latency cost.

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

