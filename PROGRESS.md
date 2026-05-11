# Spectrum Progress

## Current Status

Spectrum has a working lossless `.spec` codec, append-only dictionary snapshots,
retrieval indexing, codebase benchmark tooling, production-shaped serving, and
optional native decode acceleration.

Dictionary v12 currently covers Python, HTML, JavaScript, TypeScript, CSS, SQL,
Rust, PHP, XML-compatible payloads, Java, C, C++, Go, C#, shell, JSON, YAML,
TOML, and English text. The XML-compatible language path is retained for
backwards compatibility and dictionary coverage.

## Recently Stabilized

- `.spec` header/body format with dictionary version, flags, original byte
  length, language ID, checksum, RLE, zlib body, ASCII fallback, and Unicode
  fallback.
- Frozen dictionary snapshots for older-version decode compatibility.
- Compact binary postings formats, including SPB2 doc-gap/varint postings.
- Codebase benchmark and `.specpack` demo workflows.
- Serving retriever that returns snippets first and decodes selected payloads on
  demand.
- Code-aware reranking over bounded candidates with path, filename, identifier,
  structure, and proximity signals.
- Bounded path/title fallback for Spectrum serving zero-candidate queries. On
  the 72,601-document Linux-scale corpus, the latest `accurate` serving run
  reached Hit@1 0.8500, Recall@5 0.8750, avg query 3.75 ms, avg E2E 8.53 ms,
  and P95 E2E 32.41 ms.
- Hydration-tail controls for Spectrum serving: selected-result hydration is
  the benchmark default, decoded full payloads use a byte-bounded LRU cache,
  standard serving uses native decode when available with Python fallback, and
  selected decode is controlled by explicit policies: `none`, `auto`, and
  `exact`. The default `auto` policy defers selected `.spec` payloads above the
  16 KiB auto-decode threshold to the snippet/metadata path unless exact decode
  is requested. On the same 72,601-document corpus, the 16 KiB policy kept
  Hit@1 0.8500 and Recall@5 0.8750 while moving avg E2E from 8.53 ms to 4.78
  ms and P95 E2E from 32.41 ms to 6.35 ms versus the earlier hydrate-limit 5
  README run.

## Current Focus

- Expand the active dictionary before the public core format is treated as
  stable. Keep existing dictionary versions frozen for decode compatibility,
  avoid reordering shipped token IDs, and only lock the next dictionary once the
  broader token coverage has been tested.
- Prepare an npm-distributed bundled CLI package when the core CLI is ready.
  Target package name: `spectrumstore`, exposing `spectrum` and `spectrumstore`
  commands. Publish only after pack/decode-or-unpack/verify/inspect work from a
  bundled implementation, Python-missing errors are clear, and `npm pack` plus
  global tarball install have been tested locally.
- Mixed code/document retrieval quality.
- Human-labelled query sets.
- Stronger baseline comparisons.
- Re-run the large-corpus hydration matrix with the new selected-result,
  cache-bounded, size-aware serving policy. The fallback search regression is
  fixed; the next measurement should confirm how much of the remaining P95 E2E
  tail comes from exact decode versus intentionally deferred oversized payloads.
- Native acceleration where decode cost dominates.
- Keeping retrieval sidecars separate from the lossless `.spec` payload.

## Notes

Historical corpus-specific experiments have been removed from the active repo
surface. The remaining XML-compatible tokenizer/dictionary behavior is kept so
older payloads and language ID compatibility continue to work.
