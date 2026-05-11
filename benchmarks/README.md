# Benchmarks

This directory is the standard home for Spectrum benchmark outputs and reports.

## Layout

- `generated/` contains raw benchmark stores, matrices, `.spec` chunks, vector
  indexes, and run outputs. This directory is ignored by Git because benchmark
  stores can be hundreds of MiB.
- `reports/` contains compact, tracked summaries and charts that are useful for
  review and comparison.
- `PRODUCTION_ENGINE_BENCHMARKS.md` documents the production-engine benchmark
  workflow.
- `IMPROVEMENTS.md` tracks benchmark and retrieval quality follow-ups found
  during local runs.

## Current Tracked Reports

- `reports/final_league/`: latest competitor league table for speed, quality,
  and measured persisted size.
- `reports/final_serving/`: final standard-serving benchmark using top-k
  snippets plus selected full `.spec` decode.
- `reports/prism/`: byte-prism decode benchmark.
- `reports/serving_modes/`: full decode, cached decode, final-result-only, and
  snippet-sidecar serving-mode comparison.
- `reports/decode_explainer/`: visual explanation of standard RAG hydration vs
  Spectrum decode.

## Output Convention

Use `benchmarks/generated/<run-name>` for new benchmark runs:

```bash
python rag/codebase_benchmark.py \
  --source-root . \
  --out-dir benchmarks/generated/codebase_benchmark_self_files

python rag/production_benchmark.py \
  --benchmark-dir benchmarks/generated/codebase_benchmark_self_files \
  --out-dir benchmarks/generated/production_benchmark_self \
  --engine spectrum_serving \
  --engine raw_bm25
```
