# Spectrum RAG Ranking / Query Normalization TODO

This is the standing checklist for improving Spectrum retrieval quality after
the compact binary postings index work.

Status legend:

- [ ] Not started
- [~] In progress
- [x] Done

## Current Baseline

Latest local signal focuses on code and mixed structured-text stores:

- Spectrum `.spec` payloads remain lossless.
- Binary postings keep the retrieval index compact.
- Code-aware serving reranking improves generated path/identifier query quality.
- Bounded path/title fallback fixed the previous zero-candidate serving
  fallback regression on the 72,601-document Linux-scale corpus: Hit@1 0.8500,
  MRR 0.8625, Recall@5 0.8750, avg query 3.75 ms, avg E2E 8.53 ms, P95 E2E
  32.41 ms.
- Serving now has hydration-tail controls: result-list hydration stays on
  snippet sidecars, selected-result hydration is the benchmark default, decoded
  payloads use a byte-bounded LRU cache, native decode is used when available,
  and selected-result decode can run as `none`, `auto`, or `exact`.
- Main next target: re-run the large-corpus hydration matrix and decide whether
  the remaining tail requires a lower defer threshold, larger sidecars, or more
  native decode work.
- 2026-05-11 16 KiB policy run: Hit@1 0.8500, MRR 0.8625, Recall@5 0.8750,
  avg hydrate 1.35 ms, avg E2E 4.78 ms, P95 E2E 6.35 ms. The threshold
  deferred five selected documentation payloads; `exact` decode remains
  available when callers know full text is required.

## Checklist

- [x] Document retrieval encoding profile direction.
  - Keep the `.spec` codec layer lossless and corpus-independent.
  - Put retrieval optimization in corpus profiles, chunking/index manifests,
    parameter sweeps, and diagnostics.

- [x] Build a ranking evaluation harness.
  - Run multiple Spectrum ranking variants against the same query set.
  - Report Hit@1, MRR, Recall@5, avg query latency, p95 latency, and decode
    latency.
  - Save outputs in repeatable JSON/Markdown reports.

- [~] Make document and query normalization identical.
  - Audit `.spec` chunk tokenization vs `encode_query()`.
  - Align casing, punctuation, apostrophes, symbols, markup, and fallback-token
    handling.
  - Add regression queries for cases where document/query tokenization diverges.
  - Keep retrieval aliases profile-gated until labelled query sets support them.

- [x] Add query diagnostics.
  - Show query text, emitted Spectrum token IDs, human-readable token names,
    dropped tokens, and high-frequency/noisy tokens.
  - Include diagnostics in benchmark output for failed or low-ranking queries.

- [~] Downweight or filter noisy tokens.
  - Identify ultra-common words, syntax tokens, markup tokens, and boilerplate
    tokens.
  - Test BM25-only IDF vs explicit stop-token filtering vs soft downweighting.
  - Track quality impact separately for prose, code, HTML, CSS, and structured
    text.

- [~] Add field-aware ranking boosts.
  - Boost filename, path, headings, function/class names, and title-like fields.
  - Benchmark boost weights rather than hard-coding guesses.
  - Current serving defaults keep these knobs configurable by profile.

- [ ] Tune BM25 parameters for Spectrum token streams.
  - Grid-search `k1`, `b`, title/path boosts, noisy-token weight, and query
    expansion weight.
  - Keep separate best settings for prose vs code/structured text if needed.

- [ ] Add phrase/proximity scoring.
  - Store enough positional information, or compact token windows, to reward
    query terms that occur near each other.
  - Compare size impact against ranking improvement.

- [~] Add code-aware candidate reranking.
  - Run fast Spectrum BM25 over compact postings to get a bounded candidate set.
  - Rerank candidates with path, filename, identifier, structural declaration,
    import, and proximity signals.
  - Keep the reranker sidecar separate from the lossless `.spec` payload.
  - Current runtime profiles: `off`, `fast`, `balanced`, and
    `accurate`/`quality`.

- [x] Bound zero-candidate serving fallback.
  - Prefer path/title fallback candidates before broad full-content BM25.
  - Keep full BM25 fallback only as a last resort when bounded sidecar lookup
    finds nothing.
  - 2026-05-11 result on the 72,601-document Linux-scale corpus:
    avg query 3.75 ms, avg E2E 8.53 ms, P95 E2E 32.41 ms, Hit@1 0.8500.

- [~] Reduce selected-payload hydration/decode P95.
  - Profile the remaining P95 E2E tail after fallback search was fixed.
  - Compare hydrate-limit 0/1/top-k, cached decode, native decode, RAM-backed
    payloads, and smaller/full sidecar window strategies on the same corpus.
  - Track large-file selected decode outliers separately from search latency.
  - Current mitigation: `spectrum_serving` defaults to selected-result
    hydration with `auto` decode policy, uses native-or-fast selected decode,
    caches decoded payloads with a byte-bounded LRU, and defers exact decode for
    selected `.spec` payloads above the 16 KiB auto-decode size threshold unless
    `exact` decode is requested.
  - Target: keep average search near current levels while reducing P95 E2E below
    the current 32.41 ms reference.

- [ ] Create human-style labelled query sets.
  - Include natural questions and keyword queries, not only generated path or
    content queries.
  - Mark expected file/chunk IDs.
  - Include negative and ambiguous queries.

- [ ] Add lightweight query expansion.
  - Start with rule-based expansions for code, HTML, CSS, and common aliases.
  - Examples: `href -> link/url/anchor`, `function -> def/return`,
    `class -> selector/attribute`.
  - Keep expansion explainable and visible in diagnostics.

- [ ] Add stronger baselines.
  - Chroma or FAISS vector store.
  - Neural embeddings where practical.
  - Hybrid sparse+dense retrieval.
  - Lucene/OpenSearch BM25 and Zoekt/code-search baselines.

- [ ] Run larger-corpus benchmarks.
  - Add mixed code/documentation repositories.
  - Track index size, build time, query quality, query latency, decode latency,
    and explainability.

## Update Rule

When one of these tasks is completed, mark it `[x]`, add a short note with the
date/result, and update the relevant benchmark report if numbers changed.
