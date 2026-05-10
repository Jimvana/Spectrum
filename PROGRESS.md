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

## Current Focus

- Mixed code/document retrieval quality.
- Human-labelled query sets.
- Stronger baseline comparisons.
- Native acceleration where decode cost dominates.
- Keeping retrieval sidecars separate from the lossless `.spec` payload.

## Notes

Historical corpus-specific experiments have been removed from the active repo
surface. The remaining XML-compatible tokenizer/dictionary behavior is kept so
older payloads and language ID compatibility continue to work.
