# Spectrum Retrieval Encoding Flow

## Purpose

Spectrum keeps two layers separate:

1. The `.spec` codec layer stores source text losslessly as dictionary token IDs
   plus fallback IDs. This layer must remain stable, reversible, and
   corpus-independent.
2. The retrieval layer decides how material is selected, chunked, indexed, and
   ranked so `.spec` stores work well for search and RAG.

The retrieval layer can evolve quickly. The `.spec` payload must remain
portable and byte-faithful.

## Retrieval-Ready Encode Pipeline

```text
source corpus
  -> corpus profile selection
  -> lossless text extraction or source streaming
  -> chunking and overlap strategy
  -> language/profile-aware .spec encoding
  -> retrieval sidecar extraction
  -> compact index build
  -> ranking parameter sweep
  -> profile manifest with chosen settings
```

The `.spec` file remains the canonical payload. Retrieval settings live beside
the payload in manifests, benchmark reports, and `.specpack` metadata.

## Corpus Profiles

Profiles record what the material is and how it should be indexed.

| Profile | Typical input | Main retrieval signals |
|---|---|---|
| `plain-text` | prose documents, notes, articles | headings, paragraphs, title, named entities |
| `code-python` | Python repositories | path, module, class/function names, imports, comments |
| `code-web` | HTML/CSS/JS/TS projects | path, tags, selectors, identifiers, text nodes |
| `code-mixed` | multi-language repositories | path, extension, filename, identifiers, declarations |
| `mixed-docs-code` | documentation sites and repos | path, headings, code blocks, prose, identifiers |

## What Encoding Should Optimize

- Select the right tokenizer and language ID for the source.
- Preserve enough metadata to recover fields such as title, path, heading, or
  symbol name.
- Chunk at useful boundaries where possible, then fall back to character/token
  windows.
- Store overlap policy, chunk size, source profile, dictionary version, and
  tokenizer profile in metadata.
- Build sidecar retrieval features from the same source material used for the
  `.spec` payload.
- Keep document/query normalization aligned and regression-tested.

## What Encoding Must Not Do

The encoder must not:

- Drop bytes from the `.spec` payload.
- Rewrite source text in the payload to make search easier.
- Bake one corpus' ranking settings into the core `.spec` header.
- Treat generated benchmark queries as enough proof of retrieval quality.
- Hide query expansion, token filtering, or boosts from diagnostics.

Lossless decode remains the first invariant. Retrieval wins are only valid when
round-trip fidelity still passes.

## Parameter Sweep Role

The sweep harness should test ranking settings per profile:

- BM25 `k1`
- BM25 `b`
- document-frequency filtering thresholds
- unique-query-term handling
- title, path, heading, function, and class boosts
- noisy-token downweighting
- phrase/proximity and query expansion weights

Each run should report storage size, quality, latency, decode cost, and the
profile/chunk settings used. A good result is profile-specific:

```text
profile=code-mixed, chunk_strategy=file, best_sparse_variant=k1=1.2,b=0.75,title_boost=1.0
```

## Manifest Direction

Future corpus manifests and `.specpack` bundles should include retrieval profile
metadata similar to:

```json
{
  "profile": "code-mixed",
  "dict_version": 12,
  "chunking": {
    "strategy": "file_or_window",
    "chunk_chars": 6000,
    "overlap_chars": 600
  },
  "retrieval": {
    "index": "spectrum-binary-bm25",
    "k1": 1.2,
    "b": 0.75,
    "title_boost": 1.0,
    "rerank_profile": "accurate"
  }
}
```

This keeps `.spec` portable while making retrieval behavior reproducible.
