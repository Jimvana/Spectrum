# Benchmark Improvement Checklist

Working list from the `itsdangerous-messy-20260511` run. Keep this file as the
place to tick off benchmark and retrieval quality follow-ups.

## Current Reference Run

- Repo: `https://github.com/pallets/itsdangerous.git`
- Demo output: `demo/runs/itsdangerous-messy-20260511/`
- Production output: `benchmarks/generated/itsdangerous_messy_20260511_prod/`
- Corpus: 30 files, 31 chunks, 77,545 raw chunk bytes
- Spectrum fidelity: true, 0 failures

## Latest Large-Corpus Reference

- Corpus: `C:\Users\james\Desktop\2rep`
- Docs: 72,601
- Raw bytes: 1,028,410,590
- Current serving-policy output:
  `benchmarks/generated/readme_rebench_20260511_current_policy_128k/`
- Profile: `spectrum_serving`, `accurate`, top-k 5, hydrate-limit 1,
  `auto` decode policy, 16 KiB auto-decode threshold
- Result: Hit@1 0.8500, MRR 0.8625, Recall@5 0.8750, avg query 3.43 ms,
  avg hydrate 1.35 ms, avg E2E 4.78 ms, P95 E2E 6.35 ms
- Previous hydrate-limit 5 reference:
  `benchmarks/generated/readme_rebench_20260511_fallback_fix/`, avg query
  3.75 ms, avg E2E 8.53 ms, P95 E2E 32.41 ms
- Note: zero-candidate fallback search is no longer the main latency issue.
  The 16 KiB policy deferred five selected `.spec` payloads in this query set;
  callers can use `--decode-policy exact` when they know full text is required.

## Checklist

- [x] Debug why `spectrum_spb_bm25` and `spectrum_serving_pipeline` quality
      diverge on the same generated query set.
      - Reference signal: `spectrum_spb_bm25` scored Hit@1 1.000 / Recall@5
        1.000, while `spectrum_serving_pipeline` scored Hit@1 0.667 /
        Recall@5 0.667.
      - Inspect candidate generation, result ID mapping, rerank depth, metadata
        loading, and title/path boosts in `rag/production_benchmark.py` and
        `rag/spectrum_serving.py`.

- [x] Add a small labelled messy-query benchmark format.
      - Support expected paths or document IDs for free-form human queries.
      - Report Hit@1, MRR, and Recall@5 separately from generated file/path
        queries.
      - Start with the five `itsdangerous` messy queries from the reference run.

- [x] Add query expansion or synonym aliases for common human phrasing.
      - Examples from the run:
        - `expire`, `expires`, `links expire` -> `timed`, `timestamp`,
          `max_age`, `age`.
        - `tampered`, `messed with`, `broken token` -> `bad signature`,
          `bad data`, `unsign`, `signature`.
        - `setup entry point`, `cli`, `command` -> `pyproject`,
          `project.scripts`, `entry_points`, `console_scripts`.

- [x] Reduce metadata/template noise for code-intent queries.
      - `.github/ISSUE_TEMPLATE`, PR templates, and workflow files ranked too
        highly for code-focused messy queries.
      - Consider lower path priors for `.github/`, issue templates, PR
        templates, and workflow automation unless the query has GitHub or CI
        intent.

- [x] Improve path and file-role priors.
      - Boost `src/` for implementation-intent queries.
      - Boost `tests/` for queries containing `test`, `broken`, `fails`,
        `regression`, or similar.
      - Boost project config files for packaging and entry-point queries.

- [x] Add per-query diagnostics to benchmark reports.
      - Include top results, scores, matched aliases, rerank contributions, and
        hydration timings for each query.
      - This should make misses explainable without reopening raw indexes.

- [x] Track search latency and hydration latency separately for all benchmark
      variants.
      - Search was fast in the reference run; Spectrum serving E2E was dominated
        by selected payload hydration.
      - Keep this visible so quality work does not hide decode regressions.

- [ ] Re-run the `itsdangerous` benchmark after each ranking change.
      - Keep the same repo, query set, top-k, and rerank profile for regression
        comparison.
      - Add at least two more small external repos before treating the signal as
        stable.

- [x] Fix large-corpus zero-candidate fallback latency.
      - Bounded path/title fallback now handles the previous slow fallback
        cases before the broad full-content BM25 path.
      - Large-corpus reference improved from avg query 14.79 ms / avg E2E
        18.60 ms / P95 E2E 92.08 ms to avg query 3.75 ms / avg E2E 8.53 ms /
        P95 E2E 32.41 ms.

- [ ] Reduce large-corpus hydration/decode tail latency.
      - The remaining P95 E2E cost is now selected-payload hydration/decode,
        especially for large files.
      - Benchmark hydrate-limit 0, hydrate-limit 1, top-k hydration, cached
        decode, native decode, RAM-backed payloads, and sidecar-only result
        list paths on the same 72,601-document corpus.
      - Keep search, hydrate, and E2E metrics separate so decode work does not
        obscure retrieval regressions.
      - Current serving mitigation is implemented: selected-result hydration is
        the default, native-or-fast selected decode is used, decoded payloads use
        a byte-bounded LRU cache, and oversized selected `.spec` payloads are
        deferred to snippet/metadata unless exact decode is forced.

- [x] Add hydration tail profiler output.
      - `rag/production_benchmark.py` now supports `--hydration-matrix` with
        comma-separated hydrate limits, records per-query hydrated bytes,
        selected payload path, cache hit, and decode milliseconds, and surfaces
        the slowest hydration outliers in Markdown.
      - Smoke verified on `benchmarks/generated/ram_hydrate_smoke` with
        `spectrum_serving` and `spectrum_fast` across hydrate limits 0, 1, and
        5.

- [x] Add size-aware selected decode policy.
      - `SpectrumServingRetriever` now uses a byte-bounded decoded-payload LRU
        cache and can defer exact selected decode for `.spec` payloads above
        `--max-auto-decode-spec-bytes`. The default threshold is 16 KiB.
      - The benchmark default is now `--hydrate-limit 1`, matching the
        production result-list path where top-k rows are snippets and only the
        selected item attempts exact payload decode.
      - The selected-result decode policy can be `none`, `auto`, or `exact`.
      - Smoke verified with `--max-auto-decode-spec-bytes 100`, which deferred
        selected decode and dropped hydration time to snippet-sidecar levels.
      - Large-corpus run with the default 16 KiB threshold preserved quality,
        reduced avg hydrated bytes from 17,447 to 3,719, and moved P95 E2E from
        32.41 ms to 6.35 ms versus the earlier hydrate-limit 5 reference.

## Useful Next Work

1. Stabilize the signal across more repos.
   - Add two small external labelled query sets before tuning ranking weights
     further.
   - Good targets are one Python library with tests/config and one non-Python
     repo with `src/`, tests, docs, and CI metadata.

2. Reduce Spectrum serving hydration/decode P95.
   - Large-corpus fallback search is fixed; current P95 E2E reference is
     32.41 ms.
   - Current labelled smoke quality is good, but serving E2E is still dominated
     by selected payload hydration/decode.
   - Compare `hydrate_limit=0`, `hydrate_limit=1`, cached decode, native decode,
     RAM-backed payloads, and smaller sidecar sizes with the same labelled query
     set.

3. Make alias and intent rules data-driven.
   - Move the hard-coded synonym groups and path-intent rules into a small
     profile/config object once the multi-repo runs show which rules generalize.

4. Tighten diagnostics output.
   - The JSON now contains detailed per-query diagnostics; the markdown report
     should surface misses and top rerank contributions compactly so failures
     are visible without opening the JSON.
