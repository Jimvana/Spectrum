# Spectrum Benchmark Log

Cumulative benchmark history. Each entry records what changed between runs so storage, speed, and ranking movement has context.

## 2026-05-03 - OpenJDK Java ECB with SPB2 postings

**Change note:** Reran the large OpenJDK Java External Codebase Benchmark after updating the Spectrum benchmark builders to write SPB2 varint/delta postings directly.

**Run:** `/Users/video/jdk`, output=`rag/codebase_benchmark_openjdk_jdk_java_spb2`, files=53,780, chunks=53,780, Java files=52,532, raw=408,883,555 bytes, queries=80, top_k=5, postings_format=`v2`, verification enabled.

| Metric | Conventional raw+TF-IDF | Spectrum `.spec`+SPB2 BM25 |
|---|---:|---:|
| Total store bytes | 507,690,480 | 185,950,831 |
| Ratio vs raw chunks | 1.242x | 0.455x |
| Payload bytes | 435,772,020 | 144,726,790 |
| Index/vector bytes | 71,918,310 | 41,223,626 |
| Build seconds | 19.665 | 596.901 |
| Hit@1 | 0.200 | 0.325 |
| MRR | 0.258 | 0.439 |
| Recall@5 | 0.362 | 0.637 |
| Avg query ms | 18.856 | 15.347 |
| P95 query ms | 22.474 | 28.328 |
| Spectrum lossless | n/a | True |
| Fidelity failures | n/a | 0 |

Compared with the previous OpenJDK SPB1 run, SPB2 reduced the Spectrum index
bytes from 108,316,597 to 41,223,626 bytes, a 61.94% index reduction, and
reduced the full Spectrum store from 253,045,262 to 185,950,831 bytes, a 26.51%
store reduction. Retrieval quality was unchanged because SPB2 changes only the
on-disk postings representation. Against the raw+TF-IDF baseline in this run,
Spectrum was 63.37% smaller overall, had higher generated-query quality, and
kept lower average query latency, with the tradeoff of much slower Python build
time and higher p95 query latency.

## 2026-05-02 - BM25 parameter sweep harness

**Change note:** Added `rag/parameter_sweep.py` and ran profile-labelled BM25 sweeps over the current verified Wiki 6k and 1.8k benchmark stores. Each run swept 800 combinations across `k1`, `b`, document-frequency filtering, title boost, and unique-query-term handling.

**6k run:** `rag/parameter_sweep_6k/parameter_sweep.md`, profile=`wiki-full-xml-6k`, queries=32, top_k=5

| Variant | Hit@1 | MRR | Recall@5 | Avg query ms | P95 query ms |
|---|---:|---:|---:|---:|---:|
| Conventional TF-IDF | 0.938 | 0.953 | 0.969 | 0.852 | 0.911 |
| Best Spectrum sweep result (`k1=1.8`, `b=0`, DF none, title boost 0.5) | 0.938 | 0.944 | 0.969 | 1.415 | 2.140 |
| Fast Spectrum DF50 result (`k1=1.5`, `b=0.75`, title boost 0) | 0.938 | 0.938 | 0.938 | 0.168 | 0.296 |

**1.8k run:** `rag/parameter_sweep_1800/parameter_sweep.md`, profile=`wiki-full-xml-1800`, queries=32, top_k=5

| Variant | Hit@1 | MRR | Recall@5 | Avg query ms | P95 query ms |
|---|---:|---:|---:|---:|---:|
| Conventional TF-IDF | 1.000 | 1.000 | 1.000 | 0.991 | 1.254 |
| Best Spectrum sweep result (`k1=1.5`, `b=0.5`, DF50, title boost 1, unique terms) | 1.000 | 1.000 | 1.000 | 0.799 | 1.163 |

**Decision made:** Treat these as Wiki profile results only. The 1.8k result is strong on generated queries, but it still needs a labelled human-style query set before becoming a profile default.

## 2026-05-02 - Normalization audit

**Change note:** Added `rag/normalization.py` and `rag/normalization_audit.py` to compare base document/query token overlap with retrieval-only normalized aliases. Also fixed generated query creation so `--queries N` keeps scanning after duplicate titles instead of returning fewer queries than requested.

**Audit run:** `rag/normalization_audit_latest/normalization_audit.md`, cases=10

| Result | Count |
|---|---:|
| Improved cases | 4 |
| Still zero-overlap cases | 0 |

Targeted improvements:

- `AfghanistanPeople` vs `Afghanistan people` now shares `people` instead of zero dictionary-token overlap.
- `don't`, `don’t`, and `dont` variants now share `dont`.
- Hyphen, slash, year-suffix, possessive, and HTML-entity cases were already partially overlapping under the base tokenizer.

**Generated-query benchmark check:** Retrieval aliases are useful diagnostically but are not a default yet. On the fixed 32-query Wiki generated set, opt-in aliases increased build/index cost and did not improve generated-query ranking overall without retuning. Keep `--retrieval-normalization` as an experimental profile option until labelled human-style queries show whether the aliases help real search behavior.

## 2026-05-02 - Human-style labelled Wiki queries

**Change note:** Added `rag/labelled_queries/wiki_fullxml_sample_human.json`, a 50-query starter set with natural, keyword, alias, exact-title, and CamelCase-style queries. `rag/ranking_eval.py` and `rag/parameter_sweep.py` now resolve labelled `title` fields to benchmark-specific chunk IDs, so the same query file can run against 6k and 1.8k stores.

**Labelled sweep results:**

| Store/profile | Conventional Hit@1 | Conventional MRR | Conventional Recall@5 | Best Spectrum Hit@1 | Best Spectrum MRR | Best Spectrum Recall@5 | Best Spectrum setting |
|---|---:|---:|---:|---:|---:|---:|---|
| 6k, base | 0.820 | 0.850 | 0.900 | 0.680 | 0.733 | 0.800 | `k1=2.1`, `b=1`, DF50 |
| 1.8k, base | 0.800 | 0.832 | 0.880 | 0.700 | 0.742 | 0.800 | `k1=2.1`, `b=1`, DF50 |
| 6k, retrieval normalization | 0.820 | 0.850 | 0.900 | 0.760 | 0.825 | 0.920 | `k1=2.1`, `b=1`, DF50, title boost 1 |
| 1.8k, retrieval normalization | 0.800 | 0.832 | 0.880 | 0.780 | 0.833 | 0.920 | `k1=2.1`, `b=1`, DF50, title boost 0.5 |

**Decision made:** The labelled set is already more useful than generated title/content queries. It exposes a real quality gap for base Spectrum ranking, and it shows that opt-in retrieval normalization helps human-style queries enough to keep developing it as a profile feature.

## 2026-05-01 - 6k chunks current baseline

**Change note:** Spectrum storage benchmark after replacing the Spectrum JSON BM25 index with compact binary postings/frequency storage.

**Run:** `wiki_enwiki_fullxml_sample/page_index.json`, pages=120, chunks=782, raw=4,120,949 bytes, chunk_chars=6,000, overlap=600, queries=26, top_k=5

| Metric | Conventional raw+TF-IDF | Spectrum `.spec`+binary BM25 |
|---|---:|---:|
| Total store bytes | 6,430,395 | 4,172,510 |
| Ratio vs raw chunks | 1.560x | 1.013x |
| Payload bytes | 4,226,166 | 2,275,732 |
| Index/vector bytes | 2,204,110 | 1,896,562 |
| Build seconds | 0.657 | 5.947 |
| Hit@1 | 1.000 | 0.923 |
| MRR | 1.000 | 0.936 |
| Recall@5 | 1.000 | 0.962 |
| Avg query ms | 1.233 | 2.988 |
| Avg decode ms | 0.000 | 2.932 |
| Spectrum lossless | n/a | True |
| Fidelity failures | n/a | 0 |

## 2026-05-03T22:11:00+01:00

**Change note:** Added SPB2 varint/delta-encoded Spectrum postings sidecar and converted the 25k generated-text benchmark store without rebuilding `.spec` payloads.

**Run:** `test data/gpt55_thinking_max_distill_god_seed_25k/spectrum_spec`, docs=25,000, queries=6, top_k=5, repeats=5.

| Metric | SPB1 | SPB2 |
|---|---:|---:|
| Postings file bytes | 62,550,276 | 15,759,020 |
| Full Spectrum store bytes | 132,005,046 | 85,213,790 |
| Full Spectrum store MiB | 125.89 | 81.27 |
| Load ms | 1,100.471 | 3,407.621 |
| Avg query ms | 6.850 | 6.736 |
| P95 query ms | 11.718 | 11.412 |
| Top-5 equality | n/a | true |
| Max score absolute difference | n/a | 0.0 |

SPB2 reduced the postings file by 74.81% and the full Spectrum store by
35.45%. Compared with the raw TF-IDF store at 127,528,437 bytes, the effective
Spectrum+SPB2 store is 42,314,647 bytes smaller.

## 2026-05-01 - 1.8k chunks current baseline

**Change note:** Same binary Spectrum BM25 storage path as the 6k run, tested with smaller chunks.

**Run:** `wiki_enwiki_fullxml_sample/page_index.json`, pages=120, chunks=2,377, raw=4,130,031 bytes, chunk_chars=1,800, overlap=180, queries=28, top_k=5

| Metric | Conventional raw+TF-IDF | Spectrum `.spec`+binary BM25 |
|---|---:|---:|
| Total store bytes | 7,234,684 | 5,913,788 |
| Ratio vs raw chunks | 1.752x | 1.432x |
| Payload bytes | 4,374,718 | 2,868,949 |
| Index/vector bytes | 2,859,846 | 3,044,622 |
| Build seconds | 0.722 | 6.234 |
| Hit@1 | 0.964 | 0.929 |
| MRR | 0.964 | 0.941 |
| Recall@5 | 0.964 | 0.964 |
| Avg query ms | 1.394 | 8.014 |
| Avg decode ms | 0.000 | 1.697 |
| Spectrum lossless | n/a | True |
| Fidelity failures | n/a | 0 |

## 2026-05-01 - Core RAG index persistence

**Change note:** Core `rag.indexer`, `rag.query`, and `rag.benchmark` now default to compact binary `rag/index.bin` instead of JSON `rag/index.json`. This is the small local code/spec index, separate from the Wikipedia storage benchmark above.

| Metric | JSON index | Binary index |
|---|---:|---:|
| Index bytes | 298,203 | 117,492 |
| Size reduction | n/a | 60.6% |

## 2026-05-01 - Ranking harness, no query expansion

**Change note:** Added `rag/ranking_eval.py` to compare Spectrum ranking variants and diagnose failures without adding query expansion.

**6k chunk run:** `rag/ranking_eval_6k/ranking_eval.md`, queries=26, top_k=5

| Variant | Hit@1 | MRR | Recall@5 | Avg query ms | P95 query ms |
|---|---:|---:|---:|---:|---:|
| Conventional TF-IDF | 1.000 | 1.000 | 1.000 | 0.822 | 0.909 |
| Spectrum BM25 | 0.923 | 0.936 | 0.962 | 2.281 | 2.766 |
| Spectrum unique query | 0.923 | 0.936 | 0.962 | 2.269 | 2.742 |
| Spectrum DF90 | 0.923 | 0.936 | 0.962 | 0.920 | 1.498 |
| Spectrum DF75 | 0.923 | 0.936 | 0.962 | 0.454 | 0.766 |
| Spectrum title boost 1 | 0.923 | 0.942 | 0.962 | 2.496 | 3.002 |
| Spectrum title boost 2 | 0.846 | 0.885 | 0.923 | 2.504 | 2.998 |

**1.8k chunk run:** `rag/ranking_eval_1800/ranking_eval.md`, queries=28, top_k=5

| Variant | Hit@1 | MRR | Recall@5 | Avg query ms | P95 query ms |
|---|---:|---:|---:|---:|---:|
| Conventional TF-IDF | 0.964 | 0.964 | 0.964 | 0.961 | 1.105 |
| Spectrum BM25 | 0.929 | 0.941 | 0.964 | 6.427 | 12.541 |
| Spectrum unique query | 0.929 | 0.946 | 0.964 | 6.414 | 12.898 |
| Spectrum DF90 | 0.929 | 0.941 | 0.964 | 2.261 | 6.969 |
| Spectrum DF75 | 0.893 | 0.911 | 0.929 | 1.416 | 2.722 |
| Spectrum title boost 1 | 0.929 | 0.929 | 0.929 | 7.056 | 12.957 |
| Spectrum title boost 2 | 0.893 | 0.902 | 0.929 | 7.058 | 13.110 |

**Diagnostic takeaway:** Failures are mostly not synonym problems. The weak spots are CamelCase/title fallback drops, high-frequency control tokens, common words/numbers, and wiki redirect/citation boilerplate.

## 2026-05-01 - Ranking tuning variants

**Change note:** Added repeatable tuned variants to `rag/ranking_eval.py`: `df50`, `b025_title_boost_025`, and `b1_df90`.

**6k chunk run:** `rag/ranking_eval_6k_latest/ranking_eval.md`, queries=26, top_k=5

| Variant | Hit@1 | MRR | Recall@5 | Avg query ms | P95 query ms |
|---|---:|---:|---:|---:|---:|
| Conventional TF-IDF | 1.000 | 1.000 | 1.000 | 0.826 | 1.038 |
| Spectrum BM25 baseline | 0.923 | 0.936 | 0.962 | 2.333 | 2.782 |
| Spectrum DF50 | 0.923 | 0.936 | 0.962 | 0.293 | 0.537 |
| Spectrum b=0.25 + title boost 0.25 | 0.962 | 0.962 | 0.962 | 2.577 | 3.031 |

**1.8k chunk run:** `rag/ranking_eval_1800_latest/ranking_eval.md`, queries=28, top_k=5

| Variant | Hit@1 | MRR | Recall@5 | Avg query ms | P95 query ms |
|---|---:|---:|---:|---:|---:|
| Conventional TF-IDF | 0.964 | 0.964 | 0.964 | 1.053 | 1.301 |
| Spectrum BM25 baseline | 0.929 | 0.941 | 0.964 | 7.217 | 13.636 |
| Spectrum DF50 | 0.929 | 0.929 | 0.929 | 0.847 | 1.481 |
| Spectrum b=1.0 + DF90 | 0.964 | 0.964 | 0.964 | 2.500 | 7.500 |

**Diagnostic takeaway:** Ranking can be improved without query expansion, but the best setting differs by chunk profile. The next step is a fuller parameter sweep plus labelled queries before changing production defaults.
## 2026-05-01T19:49:21+00:00

**Change note:** Post ranking-harness and binary postings loader fix; no query expansion or ranking algorithm change.

**Run:** `wiki_enwiki_fullxml_sample\page_index.json`, pages=120, chunks=782, raw=4,120,949 bytes, chunk_chars=6,000, overlap=600, queries=32, top_k=5

| Metric | Conventional raw+TF-IDF | Spectrum `.spec`+binary BM25 |
|---|---:|---:|
| Total store bytes | 6,430,395 | 4,172,510 |
| Ratio vs raw chunks | 1.560x | 1.013x |
| Payload bytes | 4,226,166 | 2,275,732 |
| Index/vector bytes | 2,204,110 | 1,896,562 |
| Build seconds | 0.685 | 6.196 |
| Hit@1 | 0.938 | 0.938 |
| MRR | 0.953 | 0.938 |
| Recall@5 | 0.969 | 0.938 |
| Avg query ms | 1.200 | 2.819 |
| Avg decode ms | 0.000 | 3.449 |
| Spectrum lossless | n/a | True |
| Fidelity failures | n/a | 0 |

## 2026-05-01T20:50:32+00:00

**Change note:** Added CPU and decode-byte cost metrics to storage benchmark; 6k chunk profile.

**Run:** `wiki_enwiki_fullxml_sample\page_index.json`, pages=120, chunks=782, raw=4,120,949 bytes, chunk_chars=6,000, overlap=600, queries=32, top_k=5

| Metric | Conventional raw+TF-IDF | Spectrum `.spec`+binary BM25 |
|---|---:|---:|
| Total store bytes | 6,430,427 | 4,172,542 |
| Ratio vs raw chunks | 1.560x | 1.013x |
| Payload bytes | 4,226,166 | 2,275,732 |
| Index/vector bytes | 2,204,110 | 1,896,562 |
| Build seconds | 0.686 | 6.034 |
| Build CPU seconds | 0.656 | 5.953 |
| Build MiB/CPU second | 5.989 | 0.660 |
| Hit@1 | 0.938 | 0.938 |
| MRR | 0.953 | 0.938 |
| Recall@5 | 0.969 | 0.938 |
| Avg query ms | 1.204 | 2.823 |
| Avg query CPU ms | 0.488 | 3.906 |
| Avg decode ms | 0.000 | 3.023 |
| Avg decode CPU ms | 0.000 | 1.953 |
| Avg decode input bytes | 0 | 3,013.6 |
| Spectrum lossless | n/a | True |
| Fidelity failures | n/a | 0 |

## 2026-05-01T20:50:33+00:00

**Change note:** Added CPU and decode-byte cost metrics to storage benchmark; 1.8k chunk profile.

**Run:** `wiki_enwiki_fullxml_sample\page_index.json`, pages=120, chunks=2,377, raw=4,130,031 bytes, chunk_chars=1,800, overlap=180, queries=32, top_k=5

| Metric | Conventional raw+TF-IDF | Spectrum `.spec`+binary BM25 |
|---|---:|---:|
| Total store bytes | 7,234,715 | 5,913,820 |
| Ratio vs raw chunks | 1.752x | 1.432x |
| Payload bytes | 4,374,718 | 2,868,949 |
| Index/vector bytes | 2,859,846 | 3,044,622 |
| Build seconds | 0.709 | 6.534 |
| Build CPU seconds | 0.703 | 6.344 |
| Build MiB/CPU second | 5.602 | 0.621 |
| Hit@1 | 1.000 | 0.969 |
| MRR | 1.000 | 0.984 |
| Recall@5 | 1.000 | 1.000 |
| Avg query ms | 1.487 | 7.977 |
| Avg query CPU ms | 0.977 | 8.301 |
| Avg decode ms | 0.000 | 3.774 |
| Avg decode CPU ms | 0.000 | 1.465 |
| Avg decode input bytes | 0 | 1,211.0 |
| Spectrum lossless | n/a | True |
| Fidelity failures | n/a | 0 |

## 2026-05-01T21:06:33+00:00

**Change note:** Production-style optimized 6k run: optimized token-to-id/query scoring, skipped build-time verification, Spectrum DF50 query filter.

**Run:** `wiki_enwiki_fullxml_sample\page_index.json`, pages=120, chunks=782, raw=4,120,949 bytes, chunk_chars=6,000, overlap=600, queries=32, top_k=5, spectrum_k1=1.5, spectrum_b=0.75, spectrum_max_df_ratio=0.5, skip_verify=True

| Metric | Conventional raw+TF-IDF | Spectrum `.spec`+binary BM25 |
|---|---:|---:|
| Total store bytes | 6,430,426 | 4,172,573 |
| Ratio vs raw chunks | 1.560x | 1.013x |
| Payload bytes | 4,226,166 | 2,275,732 |
| Index/vector bytes | 2,204,110 | 1,896,562 |
| Build seconds | 0.664 | 4.069 |
| Build CPU seconds | 0.625 | 3.906 |
| Build MiB/CPU second | 6.288 | 1.006 |
| Hit@1 | 0.938 | 0.938 |
| MRR | 0.953 | 0.938 |
| Recall@5 | 0.969 | 0.938 |
| Avg query ms | 1.160 | 0.306 |
| Avg query CPU ms | 0.488 | 0.488 |
| Avg decode ms | 0.000 | 2.982 |
| Avg decode CPU ms | 0.000 | 2.441 |
| Avg decode input bytes | 0 | 3,013.6 |
| Spectrum fidelity verified | n/a | False |
| Spectrum lossless | n/a | None |
| Fidelity failures | n/a | not checked |

## 2026-05-01T21:06:33+00:00

**Change note:** Production-style optimized 1.8k run: optimized token-to-id/query scoring, skipped build-time verification, Spectrum b=1.0 with DF90 query filter.

**Run:** `wiki_enwiki_fullxml_sample\page_index.json`, pages=120, chunks=2,377, raw=4,130,031 bytes, chunk_chars=1,800, overlap=180, queries=32, top_k=5, spectrum_k1=1.5, spectrum_b=1.0, spectrum_max_df_ratio=0.9, skip_verify=True

| Metric | Conventional raw+TF-IDF | Spectrum `.spec`+binary BM25 |
|---|---:|---:|
| Total store bytes | 7,234,716 | 5,913,851 |
| Ratio vs raw chunks | 1.752x | 1.432x |
| Payload bytes | 4,374,718 | 2,868,949 |
| Index/vector bytes | 2,859,846 | 3,044,622 |
| Build seconds | 0.707 | 4.377 |
| Build CPU seconds | 0.703 | 4.266 |
| Build MiB/CPU second | 5.602 | 0.923 |
| Hit@1 | 1.000 | 0.969 |
| MRR | 1.000 | 0.984 |
| Recall@5 | 1.000 | 1.000 |
| Avg query ms | 1.478 | 1.700 |
| Avg query CPU ms | 1.465 | 0.488 |
| Avg decode ms | 0.000 | 2.022 |
| Avg decode CPU ms | 0.000 | 0.977 |
| Avg decode input bytes | 0 | 1,209.6 |
| Spectrum fidelity verified | n/a | False |
| Spectrum lossless | n/a | None |
| Fidelity failures | n/a | not checked |

## 2026-05-01T21:07:40+00:00

**Change note:** Production-style optimized 6k quality run: optimized token-to-id/query scoring, skipped build-time verification, Spectrum b=0.25 with title boost 0.25.

**Run:** `wiki_enwiki_fullxml_sample\page_index.json`, pages=120, chunks=782, raw=4,120,949 bytes, chunk_chars=6,000, overlap=600, queries=32, top_k=5, spectrum_k1=1.5, spectrum_b=0.25, spectrum_max_df_ratio=None, spectrum_title_boost=0.25, skip_verify=True

| Metric | Conventional raw+TF-IDF | Spectrum `.spec`+binary BM25 |
|---|---:|---:|
| Total store bytes | 6,430,426 | 4,172,572 |
| Ratio vs raw chunks | 1.560x | 1.013x |
| Payload bytes | 4,226,166 | 2,275,732 |
| Index/vector bytes | 2,204,110 | 1,896,562 |
| Build seconds | 0.655 | 4.049 |
| Build CPU seconds | 0.625 | 3.875 |
| Build MiB/CPU second | 6.288 | 1.014 |
| Hit@1 | 0.938 | 0.938 |
| MRR | 0.953 | 0.938 |
| Recall@5 | 0.969 | 0.938 |
| Avg query ms | 1.072 | 1.886 |
| Avg query CPU ms | 0.488 | 1.953 |
| Avg decode ms | 0.000 | 2.867 |
| Avg decode CPU ms | 0.000 | 2.441 |
| Avg decode input bytes | 0 | 3,008.8 |
| Spectrum fidelity verified | n/a | False |
| Spectrum lossless | n/a | None |
| Fidelity failures | n/a | not checked |

## 2026-05-01T21:08:12+00:00

**Change note:** Verified optimized 6k run after token-to-id/query scoring changes; fidelity verification enabled with Spectrum DF50 query filter.

**Run:** `wiki_enwiki_fullxml_sample\page_index.json`, pages=120, chunks=782, raw=4,120,949 bytes, chunk_chars=6,000, overlap=600, queries=32, top_k=5, spectrum_k1=1.5, spectrum_b=0.75, spectrum_max_df_ratio=0.5, spectrum_title_boost=0.0, skip_verify=False

| Metric | Conventional raw+TF-IDF | Spectrum `.spec`+binary BM25 |
|---|---:|---:|
| Total store bytes | 6,430,426 | 4,172,572 |
| Ratio vs raw chunks | 1.560x | 1.013x |
| Payload bytes | 4,226,166 | 2,275,732 |
| Index/vector bytes | 2,204,110 | 1,896,562 |
| Build seconds | 0.708 | 5.584 |
| Build CPU seconds | 0.672 | 5.391 |
| Build MiB/CPU second | 5.849 | 0.729 |
| Hit@1 | 0.938 | 0.938 |
| MRR | 0.953 | 0.938 |
| Recall@5 | 0.969 | 0.938 |
| Avg query ms | 1.102 | 0.286 |
| Avg query CPU ms | 0.000 | 0.488 |
| Avg decode ms | 0.000 | 2.815 |
| Avg decode CPU ms | 0.000 | 1.465 |
| Avg decode input bytes | 0 | 3,013.6 |
| Spectrum fidelity verified | n/a | True |
| Spectrum lossless | n/a | True |
| Fidelity failures | n/a | 0 |

## 2026-05-01T21:10:58+00:00

**Change note:** Full verified current benchmark vs conventional raw+TF-IDF; 6k chunks with optimized Spectrum DF50 query filter.

**Run:** `wiki_enwiki_fullxml_sample\page_index.json`, pages=120, chunks=782, raw=4,120,949 bytes, chunk_chars=6,000, overlap=600, queries=32, top_k=5, spectrum_k1=1.5, spectrum_b=0.75, spectrum_max_df_ratio=0.5, spectrum_title_boost=0.0, skip_verify=False

| Metric | Conventional raw+TF-IDF | Spectrum `.spec`+binary BM25 |
|---|---:|---:|
| Total store bytes | 6,430,427 | 4,172,571 |
| Ratio vs raw chunks | 1.560x | 1.013x |
| Payload bytes | 4,226,166 | 2,275,732 |
| Index/vector bytes | 2,204,110 | 1,896,562 |
| Build seconds | 0.666 | 5.452 |
| Build CPU seconds | 0.672 | 5.406 |
| Build MiB/CPU second | 5.849 | 0.727 |
| Hit@1 | 0.938 | 0.938 |
| MRR | 0.953 | 0.938 |
| Recall@5 | 0.969 | 0.938 |
| Avg query ms | 1.120 | 0.287 |
| Avg query CPU ms | 0.488 | 0.977 |
| Avg decode ms | 0.000 | 3.212 |
| Avg decode CPU ms | 0.000 | 2.930 |
| Avg decode input bytes | 0 | 3,013.6 |
| Spectrum fidelity verified | n/a | True |
| Spectrum lossless | n/a | True |
| Fidelity failures | n/a | 0 |

## 2026-05-01T21:10:58+00:00

**Change note:** Full verified current benchmark vs conventional raw+TF-IDF; 1.8k chunks with optimized Spectrum b=1.0 DF90 query filter.

**Run:** `wiki_enwiki_fullxml_sample\page_index.json`, pages=120, chunks=2,377, raw=4,130,031 bytes, chunk_chars=1,800, overlap=180, queries=32, top_k=5, spectrum_k1=1.5, spectrum_b=1.0, spectrum_max_df_ratio=0.9, spectrum_title_boost=0.0, skip_verify=False

| Metric | Conventional raw+TF-IDF | Spectrum `.spec`+binary BM25 |
|---|---:|---:|
| Total store bytes | 7,234,716 | 5,913,850 |
| Ratio vs raw chunks | 1.752x | 1.432x |
| Payload bytes | 4,374,718 | 2,868,949 |
| Index/vector bytes | 2,859,846 | 3,044,622 |
| Build seconds | 0.681 | 5.921 |
| Build CPU seconds | 0.688 | 5.844 |
| Build MiB/CPU second | 5.729 | 0.674 |
| Hit@1 | 1.000 | 0.969 |
| MRR | 1.000 | 0.984 |
| Recall@5 | 1.000 | 1.000 |
| Avg query ms | 1.493 | 1.694 |
| Avg query CPU ms | 0.000 | 0.977 |
| Avg decode ms | 0.000 | 2.250 |
| Avg decode CPU ms | 0.000 | 1.465 |
| Avg decode input bytes | 0 | 1,209.6 |
| Spectrum fidelity verified | n/a | True |
| Spectrum lossless | n/a | True |
| Fidelity failures | n/a | 0 |

## 2026-05-02T09:13:30+00:00

**Change note:** Normalization audit pass: shared retrieval aliases for text queries and document indexing, 1.8k b=1.0 DF90.

**Run:** `wiki_enwiki_fullxml_sample\page_index.json`, pages=120, chunks=2,377, raw=4,130,031 bytes, chunk_chars=1,800, overlap=180, queries=28, top_k=5, spectrum_k1=1.5, spectrum_b=1.0, spectrum_max_df_ratio=0.9, spectrum_title_boost=0.0, skip_verify=False

| Metric | Conventional raw+TF-IDF | Spectrum `.spec`+binary BM25 |
|---|---:|---:|
| Total store bytes | 7,234,716 | 5,936,422 |
| Ratio vs raw chunks | 1.752x | 1.437x |
| Payload bytes | 4,374,718 | 2,868,949 |
| Index/vector bytes | 2,859,846 | 3,067,192 |
| Build seconds | 0.982 | 23.415 |
| Build CPU seconds | 0.969 | 22.703 |
| Build MiB/CPU second | 4.066 | 0.173 |
| Hit@1 | 0.964 | 0.929 |
| MRR | 0.964 | 0.929 |
| Recall@5 | 0.964 | 0.929 |
| Avg query ms | 1.854 | 2.659 |
| Avg query CPU ms | 0.558 | 3.906 |
| Avg decode ms | 0.000 | 6.837 |
| Avg decode CPU ms | 0.000 | 1.116 |
| Avg decode input bytes | 0 | 1,070.4 |
| Spectrum fidelity verified | n/a | True |
| Spectrum lossless | n/a | True |
| Fidelity failures | n/a | 0 |

## 2026-05-02T09:13:31+00:00

**Change note:** Normalization audit pass: shared retrieval aliases for text queries and document indexing, 6k DF50.

**Run:** `wiki_enwiki_fullxml_sample\page_index.json`, pages=120, chunks=782, raw=4,120,949 bytes, chunk_chars=6,000, overlap=600, queries=26, top_k=5, spectrum_k1=1.5, spectrum_b=0.75, spectrum_max_df_ratio=0.5, spectrum_title_boost=0.0, skip_verify=False

| Metric | Conventional raw+TF-IDF | Spectrum `.spec`+binary BM25 |
|---|---:|---:|
| Total store bytes | 6,430,427 | 4,190,494 |
| Ratio vs raw chunks | 1.560x | 1.017x |
| Payload bytes | 4,226,166 | 2,275,732 |
| Index/vector bytes | 2,204,110 | 1,914,482 |
| Build seconds | 0.963 | 23.899 |
| Build CPU seconds | 0.891 | 23.047 |
| Build MiB/CPU second | 4.413 | 0.171 |
| Hit@1 | 1.000 | 0.885 |
| MRR | 1.000 | 0.923 |
| Recall@5 | 1.000 | 1.000 |
| Avg query ms | 1.764 | 0.548 |
| Avg query CPU ms | 1.803 | 0.000 |
| Avg decode ms | 0.000 | 8.269 |
| Avg decode CPU ms | 0.000 | 3.005 |
| Avg decode input bytes | 0 | 2,857.7 |
| Spectrum fidelity verified | n/a | True |
| Spectrum lossless | n/a | True |
| Fidelity failures | n/a | 0 |

## 2026-05-02T09:14:36+00:00

**Change note:** Normalization audit pass v2: targeted retrieval aliases only, 6k DF50.

**Run:** `wiki_enwiki_fullxml_sample\page_index.json`, pages=120, chunks=782, raw=4,120,949 bytes, chunk_chars=6,000, overlap=600, queries=26, top_k=5, spectrum_k1=1.5, spectrum_b=0.75, spectrum_max_df_ratio=0.5, spectrum_title_boost=0.0, skip_verify=False

| Metric | Conventional raw+TF-IDF | Spectrum `.spec`+binary BM25 |
|---|---:|---:|
| Total store bytes | 6,430,427 | 4,183,430 |
| Ratio vs raw chunks | 1.560x | 1.015x |
| Payload bytes | 4,226,166 | 2,275,732 |
| Index/vector bytes | 2,204,110 | 1,907,418 |
| Build seconds | 0.900 | 11.954 |
| Build CPU seconds | 0.844 | 11.812 |
| Build MiB/CPU second | 4.658 | 0.333 |
| Hit@1 | 1.000 | 0.885 |
| MRR | 1.000 | 0.923 |
| Recall@5 | 1.000 | 1.000 |
| Avg query ms | 1.498 | 0.628 |
| Avg query CPU ms | 1.803 | 0.601 |
| Avg decode ms | 0.000 | 3.643 |
| Avg decode CPU ms | 0.000 | 3.005 |
| Avg decode input bytes | 0 | 2,857.7 |
| Spectrum fidelity verified | n/a | True |
| Spectrum lossless | n/a | True |
| Fidelity failures | n/a | 0 |

## 2026-05-02T09:14:37+00:00

**Change note:** Normalization audit pass v2: targeted retrieval aliases only, 1.8k b=1.0 DF90.

**Run:** `wiki_enwiki_fullxml_sample\page_index.json`, pages=120, chunks=2,377, raw=4,130,031 bytes, chunk_chars=1,800, overlap=180, queries=28, top_k=5, spectrum_k1=1.5, spectrum_b=1.0, spectrum_max_df_ratio=0.9, spectrum_title_boost=0.0, skip_verify=False

| Metric | Conventional raw+TF-IDF | Spectrum `.spec`+binary BM25 |
|---|---:|---:|
| Total store bytes | 7,234,715 | 5,927,553 |
| Ratio vs raw chunks | 1.752x | 1.435x |
| Payload bytes | 4,374,718 | 2,868,949 |
| Index/vector bytes | 2,859,846 | 3,058,323 |
| Build seconds | 0.889 | 12.634 |
| Build CPU seconds | 0.875 | 12.359 |
| Build MiB/CPU second | 4.501 | 0.319 |
| Hit@1 | 0.964 | 0.929 |
| MRR | 0.964 | 0.929 |
| Recall@5 | 0.964 | 0.929 |
| Avg query ms | 1.687 | 2.286 |
| Avg query CPU ms | 1.116 | 2.790 |
| Avg decode ms | 0.000 | 2.409 |
| Avg decode CPU ms | 0.000 | 1.116 |
| Avg decode input bytes | 0 | 1,080.0 |
| Spectrum fidelity verified | n/a | True |
| Spectrum lossless | n/a | True |
| Fidelity failures | n/a | 0 |

## 2026-05-02T09:17:06+00:00

**Change note:** Normalization audit pass v3: targeted aliases and fixed generated query count, 6k DF50.

**Run:** `wiki_enwiki_fullxml_sample\page_index.json`, pages=120, chunks=782, raw=4,120,949 bytes, chunk_chars=6,000, overlap=600, queries=32, top_k=5, spectrum_k1=1.5, spectrum_b=0.75, spectrum_max_df_ratio=0.5, spectrum_title_boost=0.0, skip_verify=False

| Metric | Conventional raw+TF-IDF | Spectrum `.spec`+binary BM25 |
|---|---:|---:|
| Total store bytes | 6,430,427 | 4,183,429 |
| Ratio vs raw chunks | 1.560x | 1.015x |
| Payload bytes | 4,226,166 | 2,275,732 |
| Index/vector bytes | 2,204,110 | 1,907,418 |
| Build seconds | 0.972 | 12.031 |
| Build CPU seconds | 0.953 | 11.797 |
| Build MiB/CPU second | 4.123 | 0.333 |
| Hit@1 | 1.000 | 0.844 |
| MRR | 1.000 | 0.885 |
| Recall@5 | 1.000 | 0.969 |
| Avg query ms | 1.535 | 0.672 |
| Avg query CPU ms | 1.465 | 0.488 |
| Avg decode ms | 0.000 | 4.066 |
| Avg decode CPU ms | 0.000 | 3.418 |
| Avg decode input bytes | 0 | 2,460.2 |
| Spectrum fidelity verified | n/a | True |
| Spectrum lossless | n/a | True |
| Fidelity failures | n/a | 0 |

## 2026-05-02T09:17:07+00:00

**Change note:** Normalization audit pass v3: targeted aliases and fixed generated query count, 1.8k b=1.0 DF90.

**Run:** `wiki_enwiki_fullxml_sample\page_index.json`, pages=120, chunks=2,377, raw=4,130,031 bytes, chunk_chars=1,800, overlap=180, queries=32, top_k=5, spectrum_k1=1.5, spectrum_b=1.0, spectrum_max_df_ratio=0.9, spectrum_title_boost=0.0, skip_verify=False

| Metric | Conventional raw+TF-IDF | Spectrum `.spec`+binary BM25 |
|---|---:|---:|
| Total store bytes | 7,234,713 | 5,927,549 |
| Ratio vs raw chunks | 1.752x | 1.435x |
| Payload bytes | 4,374,718 | 2,868,949 |
| Index/vector bytes | 2,859,846 | 3,058,323 |
| Build seconds | 0.997 | 12.716 |
| Build CPU seconds | 1.000 | 12.500 |
| Build MiB/CPU second | 3.939 | 0.315 |
| Hit@1 | 0.969 | 0.875 |
| MRR | 0.969 | 0.901 |
| Recall@5 | 0.969 | 0.938 |
| Avg query ms | 1.694 | 2.286 |
| Avg query CPU ms | 0.977 | 1.953 |
| Avg decode ms | 0.000 | 2.545 |
| Avg decode CPU ms | 0.000 | 1.465 |
| Avg decode input bytes | 0 | 993.2 |
| Spectrum fidelity verified | n/a | True |
| Spectrum lossless | n/a | True |
| Fidelity failures | n/a | 0 |

