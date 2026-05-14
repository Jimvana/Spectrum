# Why Spectrum

Spectrum is for local, lossless, searchable codebase packs. It is not trying to
replace every search or compression tool.

## When Spectrum Fits

Use Spectrum when you need:

- a compact artifact that can be searched and restored exactly,
- local codebase retrieval for agents or RAG tools,
- explainable retrieval over source paths and code/text tokens,
- a single portable `.specpack` instead of raw chunks plus separate indexes,
- byte-for-byte verification before trusting restored context.

## Compared With Common Options

| Tooling | Good At | Tradeoff Spectrum Targets |
| --- | --- | --- |
| `ripgrep` | Fast exact text search over files already on disk. | It does not create a compact portable store or retrieval artifact. |
| BM25 / TF-IDF | Lightweight lexical retrieval. | The index usually sits beside raw chunks rather than inside a lossless pack. |
| Vector DBs | Semantic recall across large corpora. | They normally require embeddings, sidecar storage, and separate source reconstruction. |
| gzip / zstd / archives | General compression and transport. | They are not directly retrieval-aware. |

Spectrum's design goal is the overlap: compact storage, searchable retrieval,
and exact reconstruction from the same developer-facing artifact.

## Current Benchmark Signal

On the current large-codebase benchmark reported in the README, Spectrum serving
uses compact `.spec` payloads, snippet-first search, and selective hydration. The
latest recorded run preserved byte-level lossless decode and reached high
repo-level retrieval quality with millisecond-scale end-to-end search on the
tested corpus.

Treat those numbers as preview evidence, not a universal guarantee. The useful
developer test is simple: pack your own repo, search for things you actually
need, and verify the restored files.

## What To Install First

Install the CLI first:

```powershell
npm install -g spectrumstore
spectrum doctor
```

The SDKs and server are useful for embedding Spectrum later, but the CLI is the
supported first contact for the developer preview.
