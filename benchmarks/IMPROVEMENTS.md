# Benchmark Improvement Checklist

Working list from the `itsdangerous-messy-20260511` run. Keep this file as the
place to tick off benchmark and retrieval quality follow-ups.

## Current Reference Run

- Repo: `https://github.com/pallets/itsdangerous.git`
- Demo output: `demo/runs/itsdangerous-messy-20260511/`
- Production output: `benchmarks/generated/itsdangerous_messy_20260511_prod/`
- Corpus: 30 files, 31 chunks, 77,545 raw chunk bytes
- Spectrum fidelity: true, 0 failures

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

## Useful Next Work

1. Stabilize the signal across more repos.
   - Add two small external labelled query sets before tuning ranking weights
     further.
   - Good targets are one Python library with tests/config and one non-Python
     repo with `src/`, tests, docs, and CI metadata.

2. Reduce Spectrum serving E2E latency.
   - Current labelled smoke quality is good, but serving E2E is still dominated
     by selected payload hydration/decode.
   - Compare `hydrate_limit=0`, `hydrate_limit=1`, cached decode, native decode,
     and smaller sidecar sizes with the same labelled query set.

3. Make alias and intent rules data-driven.
   - Move the hard-coded synonym groups and path-intent rules into a small
     profile/config object once the multi-repo runs show which rules generalize.

4. Tighten diagnostics output.
   - The JSON now contains detailed per-query diagnostics; the markdown report
     should surface misses and top rerank contributions compactly so failures
     are visible without opening the JSON.
