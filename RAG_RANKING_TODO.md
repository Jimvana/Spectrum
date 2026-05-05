# Spectrum RAG Ranking / Query Normalization TODO

This is the standing checklist for improving Spectrum retrieval quality after
the compact binary postings index work.

Future conversations should reference this file, update item statuses when work
lands, and add benchmark notes under the relevant task.

Status legend:

- [ ] Not started
- [~] In progress
- [x] Done

## Current Baseline

Latest local benchmark signal:

- 6k chunks: Spectrum `.spec`+binary BM25 is smaller than conventional raw+TF-IDF, but ranks slightly behind.
- 1.8k chunks: Spectrum wins total storage and matches Recall@5, but still trails Hit@1/MRR and query latency.
- Main next target: improve query normalization and ranking quality without giving up the storage win.

## Checklist

- [x] Document retrieval encoding profile direction.
  - Keep the `.spec` codec layer lossless and corpus-independent.
  - Put retrieval optimization in corpus profiles, chunking/index manifests, parameter sweeps, and diagnostics.
  - 2026-05-02: Added `RETRIEVAL_ENCODING_FLOW.md` to define how corpus builds should optimize `.spec` stores for retrieval without making the binary format or core encoder Wikipedia-specific.

- [x] Build a ranking evaluation harness.
  - Run multiple Spectrum ranking variants against the same query set.
  - Report Hit@1, MRR, Recall@5, avg query latency, p95 latency, and decode latency.
  - Save outputs in a repeatable JSON/Markdown report.
  - 2026-05-01: Added `rag/ranking_eval.py`. It compares conventional TF-IDF, baseline Spectrum BM25, unique-query BM25, DF-filtered BM25, and title-boost variants without query expansion.

- [~] Make document and query normalization identical.
  - Audit `.spec` chunk tokenization vs `encode_query()`.
  - Align casing, punctuation, apostrophes, symbols, markup, and fallback-token handling.
  - Add regression queries for cases where document/query tokenization diverges.
  - 2026-05-01: Ranking diagnostics show CamelCase/title-heavy queries drop many fallback tokens, especially redirect pages such as `AfghanistanPeople`.
  - 2026-05-02: Added shared retrieval normalization in `rag/normalization.py` and `rag/normalization_audit.py` for regression cases. The audit improves 4/10 tricky cases and removes zero-overlap cases for CamelCase and apostrophe variants.
  - 2026-05-02: Retrieval aliases are opt-in via `--retrieval-normalization`. Generated Wiki queries did not justify making them default yet: they improve targeted diagnostics but add build/index cost and can hurt generated-query ranking unless retuned.
  - 2026-05-02: Human-labelled queries show the opposite signal from generated queries: retrieval normalization improves best-profile quality and recall on 6k and 1.8k stores. Keep it profile-gated, but continue tuning it against labelled sets.

- [x] Add query diagnostics.
  - Show query text, emitted Spectrum token IDs, human-readable token names, dropped tokens, and high-frequency/noisy tokens.
  - Include diagnostics in benchmark output for failed or low-ranking queries.
  - 2026-05-01: `rag/ranking_eval.py` writes failed/weak query diagnostics to `ranking_eval.json` and `ranking_eval.md`.

- [~] Downweight or filter noisy tokens.
  - Identify ultra-common words, syntax tokens, markup tokens, and boilerplate tokens.
  - Test BM25-only IDF vs explicit stop-token filtering vs soft downweighting.
  - Track quality impact separately for prose, code, HTML, CSS, and wiki text.
  - 2026-05-01: Preliminary DF filtering (`df90`, `df75`) improves query latency on the 6k run without hurting quality; `df75` hurts quality on 1.8k chunks, so this needs threshold tuning.
  - 2026-05-01: Added repeatable `df50` and `b1_df90` ranking variants. `df50` preserved 6k quality while cutting avg query time to 0.293 ms; `b1_df90` matched conventional Hit@1/MRR/Recall@5 on the 1.8k run and cut avg query time from 7.217 ms to 2.500 ms.

- [~] Add field-aware ranking boosts.
  - Boost title matches in the storage benchmark.
  - Later boost filename, path, headings, function/class names, and page titles for code/document corpora.
  - Benchmark boost weights rather than hard-coding guesses.
  - 2026-05-01: Preliminary title boost variants are in the ranking harness. Light boost improves 6k MRR only; stronger boost hurts both runs.
  - 2026-05-01: Added `spectrum_bm25_b025_title_boost_025`. On 6k chunks it improved Spectrum Hit@1/MRR from 0.923/0.936 to 0.962/0.962, but it hurt 1.8k quality, so title boost should remain corpus/chunk-profile tuned for now.

- [ ] Tune BM25 parameters for Spectrum token streams.
  - Grid-search `k1`, `b`, title boost, noisy-token weight, and query expansion weight.
  - Keep separate best settings for prose vs code/structured text if needed.
  - 2026-05-01: Initial grid found different winners by chunk size: 6k prefers lower length normalization (`b=0.25`) with a small title boost, while 1.8k prefers full length normalization (`b=1.0`) plus `df90` filtering. Promote this to a fuller parameter sweep before hard-coding defaults.
  - 2026-05-02: Treat sweep results as profile-specific retrieval settings. Wiki runs can define a `wiki-full-xml` profile default only after generated and labelled query sets agree.
  - 2026-05-02: Added `rag/parameter_sweep.py` to sweep profile-labelled BM25 settings over existing benchmark stores and compare them with the conventional TF-IDF baseline.
  - 2026-05-02: Ran 800-variant sweeps on the current verified Wiki stores. On 6k chunks, the best quality variant matched conventional Hit@1/Recall@5 but still trailed MRR (`k1=1.8`, `b=0`, no DF filter, title boost `0.5`). On 1.8k chunks, multiple DF50/title-boost variants matched conventional Hit@1/MRR/Recall@5 and were slightly faster than conventional TF-IDF.
  - 2026-05-02: Fixed generated query creation so `--queries N` continues past duplicate page titles and returns the requested count when enough unique titles exist.
  - 2026-05-02: Labelled human-query sweeps prefer `k1=2.1`, `b=1`, and DF50. This differs from the generated-query winners and confirms that generated queries should not set profile defaults alone.

- [ ] Add phrase/proximity scoring.
  - Store enough positional information, or compact token windows, to reward query terms that occur near each other.
  - Compare size impact against ranking improvement.

- [ ] Create a human-style labelled query set.
  - Include natural questions and keyword queries, not only generated title/content queries.
  - Mark expected page/chunk IDs.
  - Include negative and ambiguous queries.
  - 2026-05-02: Added `rag/labelled_queries/wiki_fullxml_sample_human.json` with 50 starter Wiki queries. The evaluators now resolve labelled `title` fields to benchmark-specific chunk IDs, so the same set can run against 6k and 1.8k stores.
  - 2026-05-02: Ran labelled sweeps. Base Spectrum trails conventional on human-style queries, but opt-in retrieval normalization improves the best 1.8k profile to Hit@1/MRR/Recall@5 `0.780/0.833/0.920` vs conventional `0.800/0.832/0.880`.

- [ ] Add lightweight query expansion.
  - Start with rule-based expansions for code, HTML, CSS, wiki/text, and common aliases.
  - Examples: `href -> link/url/anchor`, `function -> def/return`, `class -> selector/attribute`.
  - Keep expansion explainable and visible in diagnostics.
  - Do this after core normalization/noise/title/BM25 tuning and labelled-query evaluation, so expansion does not mask Spectrum-native weaknesses.

- [ ] Add stronger baselines.
  - Chroma or FAISS vector store.
  - Neural embeddings where practical.
  - Hybrid sparse+dense retrieval.
  - Later: Lucene/OpenSearch BM25 and Zoekt/code-search baselines.

- [ ] Run larger-corpus benchmarks.
  - Re-run on `wiki_enwiki_fullxml_1hr`.
  - Add mixed code/documentation repositories.
  - Track index size, build time, query quality, query latency, decode latency, and explainability.
  - 2026-05-02: Added `rag/codebase_benchmark.py` as the first non-Wiki source harness. On 80 file-level chunks from this repo, Spectrum was lossless and smaller than raw+TF-IDF while scoring higher on generated file/path queries. This needs a larger external codebase and labelled code queries before it becomes a serious profile result.
  - 2026-05-02: Ran the codebase harness on `vladmandic/human` at `d0c4c83`: 172 file-level chunks, Spectrum lossless, total store `1,230,156` bytes vs raw+TF-IDF `2,912,945`, and generated file/path-query Hit@1/MRR `0.317/0.390` vs conventional `0.242/0.326`.

## Update Rule

When one of these tasks is completed, mark it `[x]`, add a short note with the
date/result, and update the relevant benchmark report if numbers changed.
