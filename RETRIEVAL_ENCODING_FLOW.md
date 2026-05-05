# Spectrum Retrieval Encoding Flow

## Purpose

Spectrum has two layers that should stay clearly separated:

1. The `.spec` codec layer stores source text losslessly as dictionary token IDs
   plus fallback IDs. This layer must remain stable, reversible, and
   corpus-independent.
2. The retrieval encoding layer decides how source material is prepared,
   chunked, indexed, and ranked so `.spec` stores work well for search and RAG.

The parameter sweep harness should improve the second layer. It should not make
the binary `.spec` format Wikipedia-specific, and it should not discard source
bytes just to improve retrieval scores.

## Retrieval-Ready Encode Pipeline

For any corpus intended for retrieval, the target flow is:

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
the payload in manifests, benchmark reports, and future `.specpack` metadata.

## Corpus Profiles

A retrieval corpus should declare a profile before encoding. The profile records
what the material is and how it should be indexed.

Examples:

| Profile | Typical input | Main retrieval signals |
|---|---|---|
| `wiki-full-xml` | Wikimedia XML dumps | title, page text, redirects, headings, citations, years |
| `plain-text` | prose documents | headings, paragraphs, title, named entities |
| `code-python` | Python repositories | path, module, class/function names, imports, comments |
| `code-web` | HTML/CSS/JS/TS projects | path, tags, selectors, identifiers, text nodes |
| `mixed-docs-code` | documentation sites and repos | path, headings, code blocks, prose, identifiers |

Profiles should be data-driven. Wiki can be the first profile because the local
benchmark store already exists, but the harness output should be labelled as
`wiki-full-xml`, not treated as a universal Spectrum default.

## What Encoding Should Optimize

The encoding process should optimize for retrieval by making these choices
explicit:

- Select the right tokenizer and language ID for the source.
- Preserve enough structure to recover fields such as title, path, heading, or
  symbol name.
- Chunk at useful boundaries where possible, then fall back to character/token
  windows.
- Store overlap policy, chunk size, source profile, dictionary version, and
  tokenizer profile in metadata.
- Build sidecar retrieval features from the same token stream used in `.spec`.
- Keep document/query normalization aligned and regression-tested.

This means retrieval optimization belongs in the corpus build/index pipeline,
not in ad hoc query-time fixes alone.

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
- field boosts such as title, path, heading, function name, or class name
- noisy-token downweighting
- later, phrase/proximity and query expansion weights

Each run should report storage size, quality, latency, decode cost, and the
profile/chunk settings used. A good result is profile-specific:

```text
profile=wiki-full-xml, chunk_chars=6000, overlap_chars=600
best_sparse_variant=b=0.75, max_df_ratio=0.50
```

That result can become the default for that profile only after it survives a
labelled human-style query set and a larger corpus run.

The first labelled Wiki set lives at
`rag/labelled_queries/wiki_fullxml_sample_human.json`. It stores expected page
titles rather than fixed chunk IDs; evaluation tools resolve those titles
against each benchmark store, so the same queries work across chunk sizes.

## Manifest Direction

Future corpus manifests and `.specpack` bundles should include retrieval
profile metadata similar to:

```json
{
  "profile": "wiki-full-xml",
  "dict_version": 10,
  "language_id": 9,
  "chunking": {
    "strategy": "character_window",
    "chunk_chars": 6000,
    "overlap_chars": 600
  },
  "retrieval": {
    "index": "spectrum-binary-bm25",
    "k1": 1.5,
    "b": 0.75,
    "max_df_ratio": 0.5,
    "field_boosts": {
      "title": 0.0
    }
  }
}
```

This keeps `.spec` portable while making retrieval behavior reproducible.

## Next Implementation Steps

1. Use `rag/normalization_audit.py` to grow regression coverage for
   document/query tokenization mismatches.
2. Run `rag/parameter_sweep.py` against the existing 6k and 1.8k Wiki stores
   to identify profile-specific BM25 settings.
3. Expand the labelled Wiki query file with negative, ambiguous, and
   section-specific cases.
4. Promote the best Wiki settings into the Wiki benchmark profile only after
   generated and labelled queries both support them.
5. Add a second non-Wiki profile, preferably a mixed code/documentation corpus,
   before claiming general retrieval defaults.
6. Update manifests once profile-level retrieval settings are stable enough to
   reproduce.
