# Spectrum Agent Brief

Use this brief to orient an agent that has not seen the Spectrum repository before.

## One-Sentence Definition

Spectrum is a deterministic, lossless, searchable encoding format for code and structured text: it turns source files into compact `.spec` payloads whose token stream can also be indexed and searched directly.

## What Spectrum Is

Spectrum is not just a compressor and not just a search index. It is an experiment in making the stored artifact and the retrieval representation overlap.

Traditional retrieval stacks usually keep two things:

- raw text chunks, stored so the system can hydrate results later
- a separate index or vector store, built from those chunks so the system can search them

Spectrum tests a different shape:

- encode the source into stable semantic token IDs
- compress that token stream into `.spec` files
- build compact postings over those same token IDs
- return snippets quickly from sidecars
- decode exact full source only when a result is selected

The important claim is:

> A retrieval corpus can be compact, lossless, searchable, and explainable without treating compression and search as totally separate layers.

## Why Spectrum Exists

Spectrum exists because RAG and code-search systems often duplicate storage:

- raw chunks are stored for hydration
- lexical indexes are stored for search
- vector indexes are stored for semantic retrieval
- snippets, previews, and metadata may be stored again for serving

That duplication can make local search and agent memory expensive, opaque, and hard to reason about.

Spectrum explores whether a source corpus can be represented in a more compact form that still supports:

- exact reconstruction of the original bytes/text
- fast lexical or token search
- lightweight snippet serving
- bounded full-payload decode only when needed
- deterministic, inspectable behavior

The project is especially aimed at local, explainable retrieval for codebases and structured text. It is not trying to beat gzip, Brotli, or zstd as a pure byte compressor. Those are storage baselines. Spectrum is trying to combine storage, retrieval, and lossless hydration into one coherent representation.

## Core Concepts

### `.spec` Payloads

A `.spec` file stores encoded source text.

Current format shape:

- 16-byte uncompressed header
- dictionary version
- flags
- original length
- language ID
- checksum
- zlib-compressed stream of integer token IDs

Unknown characters fall back to marker IDs, so the decoder can reconstruct the original source losslessly.

### Dictionary

Spectrum uses a stable dictionary of meaningful language tokens. Current dictionary coverage includes Python, HTML, JavaScript, TypeScript, CSS, SQL, Rust, PHP, XML-compatible payloads, Java, C, C++, Go, C#, shell, JSON, YAML, TOML, and English text.

The dictionary gives Spectrum a semantic-token layer instead of compressing only arbitrary bytes.

### SPB2 Postings

Spectrum retrieval uses compact BM25-style postings over token IDs. The current preferred postings format is SPB2, which uses varint/delta encoding to reduce index size while preserving rankings.

### Snippet Sidecars

For result lists, Spectrum can serve path/title/snippet sidecars without decoding full `.spec` payloads. This keeps candidate serving fast.

### Byte-Prism Decode

When an agent or user selects a result, Spectrum decodes the selected full `.spec` payload on demand. The runtime can use a native Rust decoder when installed, with a Python reference decoder as fallback.

## Standard Serving Flow

The standard `spectrum_serving` path is:

1. Search Spectrum token postings.
2. Return path/title/snippet sidecars for top-k results.
3. Decode the selected full `.spec` payload on demand.
4. Cache decoded payloads for repeated access.

This separates fast candidate serving from exact full-source hydration.

## Why This Matters For Agents

Agents need search systems that are cheap to keep local, fast enough for interactive use, and exact when code must be read or edited.

Spectrum is useful to an agent because it can:

- search a codebase without keeping a large raw-text retrieval store
- show snippets quickly
- hydrate exact source only for the files or chunks that matter
- preserve byte-for-byte fidelity for edits and audits
- expose deterministic token/postings behavior instead of opaque embedding-only retrieval

The long-term idea is an agent memory and code-search substrate that is compact, local-first, inspectable, and lossless.

## What Spectrum Is Not

Spectrum is not a neural embedding model.

Spectrum is not a vector database.

Spectrum is not only a compression algorithm.

Spectrum is not claiming final production search superiority from generated-query benchmarks alone.

The current benchmarks are best read as engineering signals about storage size, latency, decode cost, fidelity, and ranking-profile behavior. Stronger product claims need labelled human-query evaluation.

## Current Benchmark Signal

Latest production-scale run found in:

`benchmarks/prod_spectrum_accurate_weighted_standard/`

Headline results:

- corpus: 72,601 docs
- raw corpus size: 980.77 MB
- Spectrum storage: 351.63 MB
- Spectrum ratio vs raw: 35.85%
- lossless decode: true
- queries: 80
- Hit@1: 0.7375
- MRR: 0.7438
- Recall@5: 0.7500
- search latency: 3.0698 ms
- hydrate latency: 3.1299 ms
- end-to-end latency: 6.1997 ms
- P95 end-to-end latency: 7.4901 ms

Recent comparative ranking-profile signal:

`benchmarks/reports/ranking_profiles_vs_competition/`

Notable Spectrum rows:

- Java accurate snippet sidecar: Hit@1 0.8266, MRR 0.8746, Recall@5 0.9370, E2E 2.336 ms, size 2,945,660 bytes
- Self accurate serving pipeline: Hit@1 0.8679, MRR 0.8979, Recall@5 0.9357, E2E 3.369 ms, size 1,696,839 bytes
- Self accurate snippet sidecar: Hit@1 0.7857, MRR 0.8396, Recall@5 0.9179, E2E 0.720 ms, size 1,688,693 bytes

## Mental Model

Think of Spectrum as a source-aware storage and retrieval format:

```text
source file
  -> language tokenizer
  -> stable semantic token IDs
  -> .spec compressed payload
  -> compact token postings
  -> snippet sidecars for result lists
  -> selected full decode when exact source is needed
```

The compressed object is still useful for retrieval because the encoded token layer remains indexable.

## Repository Areas To Inspect

- `README.md`: main project overview, current status, benchmark snapshots
- `spec_format/`: `.spec` encoder, decoder, migrator, and format snapshots
- `tokenizers/`: language-specific tokenization
- `rag/`: retrieval, storage, and production benchmark harnesses
- `native/`: optional Rust/PyO3 decoder acceleration
- `benchmarks/`: generated runs and tracked reports
- `CLI Tool/`: public `spectrum` CLI demo

## Useful Framing

If explaining Spectrum to someone else, lead with this:

Spectrum asks whether the thing you store for retrieval can also be the thing you search. It encodes code and text into compact, lossless `.spec` payloads, indexes the semantic token stream, serves snippets cheaply, and decodes exact source only when needed.

That is why it exists: to reduce duplicated RAG storage while keeping retrieval local, explainable, fast, and lossless.
