# Spectrum Algo — Progress Log

## Status: Phase 1 Complete - Dictionary v12. .spec format proven across Python, HTML, JS, TS, CSS, SQL, Rust, PHP, XML/Wiki, Java, C, C++, Go, C#, shell, JSON, YAML, TOML, and English text. Backwards compatibility, version snapshots, migration tooling, and the RAG/demo proof path are in place.

---

## Log

### Session 24 - Native Rust Decoder Path
**Date:** May 2026
**What we did:**
- Added `native/spectrum_native`, a Rust/PyO3 extension that accelerates the byte-prism decoder hot loop for code-like `.spec` chunks.
- Added `rag/native_decoder.py` as the optional native wrapper. Python still owns dictionary/version table packing and remains the reference fallback.
- Updated standard Spectrum serving so selected full-payload hydration uses native Rust decode when the wheel is installed, and falls back to Python when native decode is unavailable or the chunk uses the plain-text reconstruction profile.
- Added production benchmark engine keys for `spectrum_native`, `spectrum_native_cached`, and `spectrum_serving_native`.
- Documented the source-build path with `maturin` and the intended end-user packaging model: prebuilt wheels should include the compiled decoder, so users do not need Rust installed.

**Verification:**
- Built and installed the Windows CPython 3.11 wheel locally with `maturin build --release`.
- Verified decode parity across the Apache Commons Lang Java benchmark corpus: 571/571 docs matched the Python reference decoder, with 536 chunks decoded natively and 35 text-profile chunks using the Python fallback.
- Re-ran `rag/production_benchmark.py` on `benchmarks/generated/java_corpus_commons_lang` with `--hydrate-limit 1`.

**Current serving signal:**
- `spectrum_serving_pipeline`: E2E 1.5007 ms, P95 E2E 5.2002 ms, hydrate 1.0625 ms.
- `spectrum_serving_pipeline_native`: E2E 0.5445 ms, P95 E2E 0.8897 ms, hydrate 0.0838 ms.
- Search quality was unchanged: Hit@1 0.4466, MRR 0.5670, Recall@5 0.7496 on both serving paths.

**Decision made:**
- Treat Rust as the default runtime acceleration path when installed, not as a `.spec` format fork or hard dependency.
- Keep Python as the compatibility/reference decoder so `.spec` remains portable on platforms without a prebuilt native wheel.

### Session 13 — Extension Library Manifests
**Date:** April 2026
**What we did:**
- Added `spec_format/libraries.py` as the first implementation of Spectrum extension library declarations.
- Defined manifest-level libraries for `spectrum-core`, `english-text`, `wikimedia-clean-text`, `wikimedia-raw-wikitext`, and planned `wikimedia-xml`.
- Wired Wikipedia shard manifests to declare the libraries required to interpret the corpus.
- Backfilled the completed `wiki_enwiki_dump/manifest.json` and `manifest.partial.json` with library metadata.
- Added Option A reserved global extension token ranges in `spec_format/extension_tokens.py`.
- Added initial Wikimedia/XML and MediaWiki extension tokens:
  - `1,000,000-1,099,999` reserved for `wikimedia-xml`
  - `1,100,000-1,199,999` reserved for `mediawiki`
- Added `tokenizers/wiki_tokenizer.py` so raw-wikitext mode can emit extension tokens for repeated XML/wiki syntax markers.
- Updated the core encoder/decoder to recognise extension token IDs while preserving backwards compatibility for normal `.spec` files.

**Decision made:**
- Keep the current 16-byte `.spec` header unchanged for now. Library dependencies live in shard manifests until a future `.specpack` or header-v2 format can embed/bundle them properly.
- Treat extension libraries as domain "chapters": Wikipedia can request Wikimedia/XML/MediaWiki libraries, while another large corpus can request its own domain library without bloating the core dictionary.
- Use reserved global ranges first, because the `.spec` body is already uint32 and can carry extension IDs without a stream-format change.

**Next step:**
- Design a true lossless Wikimedia profile using XML and MediaWiki syntax token libraries instead of the current cleaned-text extraction profile.

### Session 14 — Dictionary v10: XML / MediaWiki Core Tokens
**Date:** April 2026
**What we did:**
- Bumped `DICT_VERSION` to 10.
- Added 64 append-only core dictionary tokens for XML and MediaWiki source syntax.
- Added frozen snapshot `spec_format/_frozen/v10.py` with `SPEC_TOKEN_COUNT = 234,957`.
- Registered language id `9` as `XML/Wiki`.
- Updated `tokenizers/wiki_tokenizer.py` to emit v10 core dictionary literals instead of extension-internal token names.
- Added `tools/wiki_dump_to_spec.py --mode full-xml`, which streams the decompressed Wikimedia XML directly into `.spec` chunks instead of parsing article records out.
- Captured `versions/v10/` snapshot.

**Verification:**
- Synthetic XML/Wiki sample round-tripped exactly with dictionary v10.
- Real enwiki full-XML 16 MiB sample encoded to 7,196,157 bytes (`0.4289x`) and all four sample shards decoded with perfect checksums.
- Sample shards showed thousands of XML core-token hits and tens of thousands of MediaWiki core-token hits per chunk.

**Decision made:**
- XML/MediaWiki is now part of the core dictionary for the immediate lossless-Wikipedia experiment. The manifest library model remains useful for declaring corpus profiles, but full XML no longer depends on reserved extension ID ranges.

### Session 15 — LLM Data Layer Positioning
**Date:** April 2026
**What we did:**
- Clarified the difference between Wikimedia `.bz2`, Kiwix/ZIM, and Spectrum `.spec` for LLM/agent use.
- Documented that `.bz2` is compressed source material, `.zim` is a human offline-reader archive, and `.spec` is intended to become an LLM-native tokenized retrieval layer.
- Added the concrete build plan for a Spectrum Wiki reader/indexer:
  - shard verifier
  - page-boundary index
  - title index
  - token inverted index
  - query tokenizer
  - decode-on-demand reader
  - benchmark harness against ZIM, raw BM25, and embedding/hybrid retrieval

**Decision made:**
- Do not position Spectrum as a pure compression competitor. On identical bytes, gzip/bzip2 still compress smaller. Position Spectrum as compact, lossless, semantic-token storage that can become faster and more intuitive for LLM retrieval once indexed.

### Session 16 - RAG Storage Benchmark Proof Path
**Date:** May 2026
**What we did:**
- Updated the legacy browser extension decoder to current dictionary v10 and XML/Wiki language id support. The extension was later removed during project cleanup.
- Built `tools/wiki_verify_manifest.py` to verify full-XML shard manifests without writing decoded XML to disk.
- Verified `wiki_enwiki_fullxml_1hr`: 32 shards, 2,147,483,648 original XML bytes, checksum pass.
- Built `tools/wiki_page_index.py` for page/title boundaries over full-XML `.spec` shards.
- Built `tools/wiki_read_page.py` for decode-on-demand page extraction by id/title.
- Built `wiki_enwiki_fullxml_1hr/page_index.json`: 69,942 page records, 1,611,897,232 tokens scanned, no malformed events.
- Added a Chrome Wiki Reader proof page for searchable `page_index.json` browsing and raw/rendered article display.
- Reframed the main proof away from perfect Wikipedia rendering and toward a RAG storage benchmark.
- Added `rag/storage_benchmark.py`, which builds two stores from the same chunks:
  - conventional local RAG: raw `chunks.jsonl` + TF-IDF vector matrix
  - Spectrum RAG: lossless `.spec` chunks + Spectrum token BM25 index
- Added `RAG_STORAGE_BENCHMARK.md` with benchmark method and results.

**Current benchmark signal:**
- On 120 Wikipedia pages with 6k-character chunks:
  - conventional raw+TF-IDF store: 6,430,395 bytes
  - Spectrum `.spec`+BM25 store: 5,230,494 bytes
  - Spectrum payload alone: 2,275,732 bytes vs 4,226,166 raw JSONL payload bytes
  - both stores reached 93.8% Hit@1 on generated title/content queries
  - Spectrum round-tripped losslessly with zero fidelity failures
- On smaller 1.8k-character chunks, Spectrum payload still won, but the naive JSON BM25 index made total storage larger than the conventional baseline.

**Decision made:**
- The main project proof should be "retrieval-ready storage" rather than browser-perfect Wikipedia rendering.
- Current bottleneck is no longer `.spec` payload size; it is the JSON index size and Python BM25 query speed.

**Next step:**
- Replace the JSON Spectrum BM25 index with a compact binary index and rerun the storage benchmark against a Chroma/FAISS/neural embedding baseline.

### Session 17 - Binary RAG Index and Ranking TODO
**Date:** May 2026
**What we did:**
- Replaced the storage benchmark's Spectrum JSON BM25 index with a compact binary postings/frequency index:
  - `postings.bin` for token postings and term frequencies
  - `docs.json` for lightweight document metadata
  - no raw text stored in the Spectrum store
- Re-ran the 120-page Wikipedia storage benchmark at 6k and 1.8k chunk sizes.
- Added `RAG_RANKING_TODO.md` as the standing checklist for ranking/query-normalization work.
- Cross-referenced the checklist from `RAG_STORAGE_BENCHMARK.md` and `RETRIEVAL_POSITIONING.md`.

**Current benchmark signal:**
- On 6k-character chunks:
  - conventional raw+TF-IDF store: 6,430,395 bytes
  - Spectrum `.spec`+binary BM25 store: 4,172,510 bytes
  - Spectrum index/vector component: 1,896,562 bytes vs 2,204,110 conventional
  - Spectrum Hit@1/MRR/Recall@5: 0.923 / 0.936 / 0.962
  - conventional Hit@1/MRR/Recall@5: 1.000 / 1.000 / 1.000
- On 1.8k-character chunks:
  - conventional raw+TF-IDF store: 7,234,684 bytes
  - Spectrum `.spec`+binary BM25 store: 5,913,788 bytes
  - Spectrum Recall@5 matched conventional at 0.964, but Hit@1/MRR still trailed.

**Decision made:**
- The JSON index bottleneck is solved enough for now; Spectrum now wins total storage size in both tested chunk profiles.
- The next bottleneck is ranking quality and query normalization.
- Future conversations should use `RAG_RANKING_TODO.md` as the task list and mark items off there as work lands.

**Next step:**
- Start with the ranking evaluation harness and query diagnostics from `RAG_RANKING_TODO.md`.

### Session 18 - Core RAG Binary Index Default
**Date:** May 2026
**What we did:**
- Moved the core `rag.indexer` persistence path off JSON by default:
  - `python -m rag.indexer ...` now writes `rag/index.bin`
  - `rag.query` and `rag.benchmark` default to `rag/index.bin`
  - `.json` indexes still load and save for backwards compatibility
- The binary index stores document metadata and sparse token frequency vectors, then rebuilds the inverted index at load time to avoid duplicate on-disk data.
- Replaced the query CLI result table with ASCII-safe output for Windows PowerShell.

**Verification:**
- Built `rag/index.bin` from `spec_format/output`: 117,492 bytes vs existing `rag/index.json`: 298,203 bytes.
- Verified binary save/load round-trip preserves document count, frequency rows, and BM25 score parity against the in-memory index.
- Verified `python -m rag.query "for loop range append list" --index rag/index.bin --top 3 --lang py` works in PowerShell.

**Decision made:**
- Use compact binary for the core RAG index path by default, while keeping legacy JSON as an explicit compatibility format.

### Session 19 - Benchmark Log
**Date:** May 2026
**What we did:**
- Added `BENCHMARK_LOG.md` as the cumulative score history for RAG/storage benchmark runs.
- Seeded it with the current 6k chunk, 1.8k chunk, and core RAG binary-index results.
- Added `--append-log`, `--benchmark-log`, and `--change-note` to `rag/storage_benchmark.py` so future benchmark runs can append scores and note what changed.
- Updated `RAG_STORAGE_BENCHMARK.md` with the logging command pattern.

**Decision made:**
- Every meaningful benchmark run should include a short change note explaining what changed since the previous run.

### Session 20 - Ranking Harness and Diagnostics
**Date:** May 2026
**What we did:**
- Added `rag/ranking_eval.py`, a ranking evaluation harness for existing storage benchmark outputs.
- The harness compares conventional TF-IDF with Spectrum BM25 variants without query expansion:
  - baseline BM25
  - unique query terms
  - document-frequency filtering
  - title boost variants
- Added failed-query diagnostics with query tokens, token IDs, readable token names, document frequency ratios, IDF, and fallback-token counts.
- Fixed `load_binary_postings()` compatibility for existing `postings.bin` files by correcting the binary header offset handling.
- Ran the harness on the current 6k and 1.8k benchmark stores.

**Current ranking signal:**
- 6k chunks:
  - baseline Spectrum BM25: Hit@1 0.923, MRR 0.936, Recall@5 0.962
  - DF75 filtering preserved quality and cut avg query time from 2.281 ms to 0.454 ms
  - title boost 1 improved MRR to 0.942 but did not improve Hit@1
- 1.8k chunks:
  - baseline Spectrum BM25: Hit@1 0.929, MRR 0.941, Recall@5 0.964
  - unique query terms improved MRR slightly to 0.946
  - DF75 and title boosts hurt quality

**Decision made:**
- Query expansion should stay later. Current diagnostics show core issues first: CamelCase/title fallback drops, high-frequency control tokens, common words, numbers, and wiki citation/redirect boilerplate.

### Session 21 - Ranking Tuning Variants
**Date:** May 2026
**What we did:**
- Added repeatable tuned variants to `rag/ranking_eval.py`:
  - `spectrum_bm25_df50`
  - `spectrum_bm25_b025_title_boost_025`
  - `spectrum_bm25_b1_df90`
- Re-ran the ranking harness on the 6k and 1.8k Wikipedia benchmark stores.
- Updated `RAG_RANKING_TODO.md` and `BENCHMARK_LOG.md` with the new results.

**Current ranking signal:**
- 6k chunks:
  - baseline Spectrum BM25: Hit@1 0.923, MRR 0.936, Recall@5 0.962
  - `b=0.25 + title boost 0.25`: Hit@1 0.962, MRR 0.962, Recall@5 0.962
  - `df50`: same quality as baseline, avg query time cut to 0.293 ms
- 1.8k chunks:
  - baseline Spectrum BM25: Hit@1 0.929, MRR 0.941, Recall@5 0.964
  - `b=1.0 + df90`: Hit@1 0.964, MRR 0.964, Recall@5 0.964, matching conventional TF-IDF on this query set

**Decision made:**
- Do not hard-code one global ranking default yet. The best setting differs by chunk size/profile, so the next step is a fuller parameter sweep and labelled human-style query set.

### Session 22 - Storage Benchmark Cost Metrics
**Date:** May 2026
**What we did:**
- Extended `rag/storage_benchmark.py` with CPU and I/O cost metrics:
  - build CPU seconds
  - build MiB per CPU second
  - query CPU milliseconds
  - decode CPU milliseconds
  - average `.spec` bytes read for decoded top result
- Re-ran the 6k and 1.8k chunk storage benchmarks into:
  - `rag/storage_benchmark_6k_cost/`
  - `rag/storage_benchmark_1800_cost/`
- Appended both runs to `BENCHMARK_LOG.md`.

**Current cost signal:**
- 6k chunks:
  - conventional build CPU: 0.656s; Spectrum build CPU: 5.953s
  - conventional query CPU: 0.488 ms; Spectrum query CPU: 3.906 ms
  - Spectrum decode CPU: 1.953 ms, reading 3,013.6 `.spec` bytes on average
- 1.8k chunks:
  - conventional build CPU: 0.703s; Spectrum build CPU: 6.344s
  - conventional query CPU: 0.977 ms; Spectrum query CPU: 8.301 ms
  - Spectrum decode CPU: 1.465 ms, reading 1,211.0 `.spec` bytes on average

**Decision made:**
- `.spec` currently trades lower storage for materially higher ingest/build CPU and baseline query CPU. The next optimization target is query-path CPU, then encode throughput.

### Session 23 - First CPU Optimization Pass
**Date:** May 2026
**What we did:**
- Optimized the token-to-ID hot path by checking core dictionary tokens before extension-token lookup and reducing per-token function calls.
- Applied small plain-text tokenizer hot-path cleanup by caching local append/extend and dictionary lookups.
- Optimized `BinarySpectrumBM25.search()` with cached IDF/DF ratios, cached BM25 length norms, `heapq.nlargest()`, and query-time DF filtering.
- Added production-style benchmark options:
  - `--skip-verify`
  - `--spectrum-k1`
  - `--spectrum-b`
  - `--spectrum-max-df-ratio`
  - `--spectrum-unique-query-terms`
  - `--spectrum-title-boost`
- Ran optimized production and verified benchmark profiles.

**Current optimization signal:**
- 6k verified DF50 run:
  - Spectrum build CPU improved from 5.953s to 5.391s.
  - Spectrum query wall time improved from 2.823 ms to 0.286 ms.
  - Fidelity verification passed with zero failures.
- 6k production DF50 run:
  - Spectrum build CPU improved to 3.906s with build-time verification skipped.
  - Spectrum query wall time was 0.306 ms vs conventional 1.160 ms.
- 1.8k production `b=1.0 + df90` run:
  - Spectrum build CPU improved from 6.344s to 4.266s.
  - Spectrum query wall time improved from 7.977 ms to 1.700 ms.
  - Spectrum Recall@5 matched conventional at 1.000, with Hit@1 0.969 and MRR 0.984.

**Decision made:**
- Query CPU is now much less of a blocker when using DF-filtered tuned profiles. The remaining major cost is encode/build throughput, especially if full verification is required during ingest.

### Session 1
**Date:** April 2026
**What we did:**
- Defined the concept and goals
- Agreed on approach: pre-built Python keyword dictionary, PNG output, WSL2/Python stack
- Chose first test source: a Python fibonacci script (mix of keywords, symbols, strings, numbers)
- Created folder structure
- Created PROJECT_OUTLINE.md and PROGRESS.md

**Decisions made:**
- Pre-built dictionary (not dynamic) for v1 — simpler, more predictable
- Fallback to character-by-character for tokens not in dictionary
- PNG only (lossless) — lossy formats like JPEG would corrupt colour values
- Fixed image width, variable height

---

### Session 2
**Date:** April 2026
**What we did:**
- Built `dictionary.py` — 94 unique RGB↔token mappings (36 keywords, 42 symbols, 10 digits, 4 whitespace, 2 special)
- Confirmed zero colour collisions across all 94 entries
- Wrote `test_sources/fibonacci.py` — rich mix of keywords, operators, strings, digits, comments, whitespace
- Built `encoder/encoder.py` — tokenises Python source using stdlib `tokenize`, maps to RGB pixels, writes lossless PNG with header row
- Built `decoder/decoder.py` — reads header, decodes pixels back to tokens, reconstructs source, truncates to original byte length
- **Ran first round-trip test: PERFECT FIDELITY ✓**

**Round-trip result:**
- Source: `fibonacci.py` → 2,201 bytes
- Encoded: `fibonacci.png` → 2,365 bytes (64×34px, 2,055 tokens)
- Decoded: `fibonacci_decoded.py` → 2,201 bytes
- `diff fibonacci.py fibonacci_decoded.py` → zero differences

**Decisions made:**
- Header row: pixel 0 = marker (0,0,0), pixel 1 = dict version, pixels 2–3 = original byte length (32-bit)
- Fallback encoding: any char not in the dictionary is stored as its Unicode code point split across R, G, B channels
- PAD pixel (1,1,1) fills the last row and is silently skipped on decode
- Image width: 64px (can be overridden via `--width` flag)

---

### Session 3
**Date:** April 2026
**What we did:**
- Expanded dictionary to v2 — added 74 built-in functions/types (len, range, str, int, list, dict, etc.), total 168 tokens
- Built and tested RLE (Run-Length Encoding) — marker pixel (R=253, G=count_hi, B=count_lo) after any run of 3+ identical tokens
- Discovered RLE is **counterproductive for PNG output** — important finding (see below)
- Confirmed all 5 files decode with perfect byte-for-byte fidelity
- Dictionary bumped to v3 (RLE marker infrastructure added); RLE defaults to OFF for PNG

**Key finding — RLE vs PNG DEFLATE:**
PNG's built-in DEFLATE compression already handles runs of identical pixels better than our marker-pixel RLE. RLE saves 19.1% of pixels on mega_stdlib but each remaining pixel becomes harder for DEFLATE to compress — the unique marker pixels break up the uniform runs that DEFLATE exploits with a single LZ77 back-reference. Net result: +76KB worse on the 1MB file.

| Approach | Pixels | Bytes/pixel | PNG size |
|---|---|---|---|
| No RLE (default) | 1,074,862 | 0.541 | 581,102 bytes |
| With RLE | 869,590 | 0.756 | 657,718 bytes |

RLE kept as `--rle` flag for future raw/binary output format where it would genuinely help.

---

### Session 4
**Date:** April 2026
**What we did:**
- Ran frequency analysis on mega_stdlib.py to find top char-by-char token offenders
- Built dictionary v4 (291 tokens) adding: 24 core identifiers (self, cls, args, kwargs, etc.), 24 dunders (__init__, __name__, etc.), 24 exception types, 34 common methods (append, join, split, etc.), 20 stdlib module names
- Fixed a decoder bug: meta-token skip was using `startswith("__")`, silently eating all dunders — changed to explicit `("__HEADER__", "__PAD__")` check
- Re-ran all 5 files; perfect fidelity on all ✅

**Key finding — dictionary expansion vs PNG:**
Adding 123 new tokens removed 41,468 pixels from mega_stdlib but only saved 1,052 bytes of PNG. DEFLATE was already compressing fallback char-pixels at ~99.2% efficiency. Char-by-char encoding of `self` as (s,e,l,f) = 4 repeated-pattern pixels compresses almost as well as a single dictionary pixel — DEFLATE back-references them for near-free.

**Conclusion so far — two truths about Spectrum + PNG:**
- RLE at pixel level hurts (breaks up runs that DEFLATE exploits)
- Rich dictionary helps pixel count but not PNG ratio (DEFLATE handles repetitive chars already)
- PNG is doing a lot of heavy lifting. For a raw/non-compressed Spectrum format, both RLE and dictionary would give dramatic gains.
- The ~0.52x ratio on 1MB Python may be close to the ceiling for PNG-wrapped Spectrum

**Current best results:**
| File | v3 Ratio | v4 Ratio |
|---|---|---|
| fibonacci.py  | 1.075x | 1.000x |
| encoder.py    | 0.84x  | 0.772x |
| decoder.py    | 0.897x | 0.849x |
| dictionary.py | 0.782x | 0.675x |
| mega_stdlib.py| 0.517x | 0.516x |

---

### Session 5
**Date:** April 2026
**What we did:**
- Designed and built the `.spec` binary format — Spectrum's native format, no image wrapper
- Added stable TOKEN_TO_SPEC_ID / SPEC_ID_TO_TOKEN mappings to dictionary.py
- Built `spec_format/spec_encoder.py` — tokenises source, encodes as uint16 token ID stream, RLE on the ID stream, zlib level 9
- Built `spec_format/spec_decoder.py` — zlib decompress, uint16 stream → tokens → source, checksum verification
- All 5 test files decode with **perfect fidelity + checksum pass** ✅

**Four-way comparison (original / gzip / PNG / .spec):**

| File | Original | gzip | PNG | **.spec** |
|---|---|---|---|---|
| fibonacci.py | 2,201 B | 885 B (0.40x) | 2,202 B (1.00x) | **1,077 B (0.49x)** |
| encoder.py | 12,888 B | 4,187 B (0.33x) | 9,947 B (0.77x) | **4,954 B (0.38x)** |
| decoder.py | 7,653 B | 2,689 B (0.35x) | 6,500 B (0.85x) | **3,199 B (0.42x)** |
| dictionary.py | 22,047 B | 6,591 B (0.30x) | 14,096 B (0.64x) | **7,730 B (0.35x)** |
| mega_stdlib.py | 1,123,961 B | 259,670 B (0.23x) | 580,050 B (0.52x) | **300,943 B (0.27x)** |

**.spec beats PNG** on every single file (2x–3x better on large files).
**.spec is within striking distance of gzip** and on small files like fibonacci.py actually beats gzip (0.49x vs 0.40x — wait, gzip wins there). On large files gzip still leads but .spec is ~116% of gzip size.

**Key finding:** The semantic token layer (Spectrum dictionary + RLE on a structured ID stream) contributes real compression beyond what raw-text gzip achieves. At 1MB, .spec is 300KB vs gzip's 260KB — within 15% of gzip, which has no semantic awareness at all. This gap will narrow as the dictionary grows (HTML/JS adds more tokens).

---

### Session 6  — Phase 3: HTML + JavaScript
**Date:** April 2026
**What we did:**
- Dictionary v5 (403 tokens): added HTML tags (43), HTML attributes (20), JS keywords (19), JS operators (7), JS identifiers (24) — zero collisions
- Built `tokenizers/html_tokenizer.py` — regex + state-machine, handles tags/attrs/text/comments, ✓ round-trip verified
- Built `tokenizers/js_tokenizer.py` — single-pass regex scanner, handles all JS token types, ✓ round-trip verified
- Updated `spec_encoder.py` — auto-detects language from file extension (.py/.html/.htm/.js), `--lang` override flag
- Tested: jQuery (288KB), Bootstrap (231KB), underscore docs HTML (173KB), socat HTML (240KB)
- **All 4 new files: perfect checksum fidelity ✅**

**Full comparison — all languages:**

| File | Lang | Original | gzip | .spec | gzip ratio | .spec ratio | .spec vs gzip |
|---|---|---|---|---|---|---|---|
| mega_stdlib.py | Python | 1,124 KB | 254 KB | 294 KB | 0.231x | 0.268x | 1.16x |
| jquery.js | JS | 282 KB | 83 KB | 99 KB | 0.294x | 0.350x | 1.19x |
| bootstrap.js | JS | 226 KB | 46 KB | 55 KB | 0.203x | 0.243x | 1.20x |
| underscore.html | HTML | 169 KB | 39 KB | 46 KB | 0.233x | 0.273x | 1.17x |
| socat.html | HTML | 235 KB | 47 KB | 57 KB | 0.200x | 0.242x | 1.21x |

**.spec consistently beats gzip by a margin of ~16–21%** (i.e., gzip is ~16–21% smaller) — this gap is the "semantic overhead cost" of our fixed dictionary. Spectrum is paying for a shared, queryable token layer.

**Key insight:** .spec is within 20% of gzip across all three languages with the same codebase. The gap is stable — around 1.17–1.21x gzip — which means it's not getting worse as we add languages. Bootstrap.js gets 0.243x ratio which is genuinely impressive for a format with human-readable semantics.

**Next steps:**
- [x] Add CSS support (Phase 4) ← done
- [ ] Investigate closing the gzip gap further (more aggressive dictionary coverage)
- [ ] Consider RGBA mode for PNG output
- [ ] Formal protocol spec draft

---

### Session 7 — Phase 4: CSS
**Date:** April 2026
**What we did:**
- Dictionary v6 (473 tokens): added CSS_AT_RULES (10), CSS_PROPERTIES (40), CSS_VALUE_KEYWORDS (20) — zero collisions
- CSS at-rules stored as full `@keyword` strings (e.g. `@media`, `@keyframes`) for single-token encoding
- CSS hyphenated properties stored as single tokens (`font-size`, `background-color`, `margin-top` etc.)
- Built `tokenizers/css_tokenizer.py` — single-pass regex scanner, round-trip verified ✓
- Updated `spec_encoder.py` — LANGUAGE_CSS = 3, auto-detects `.css` extension, `--lang css` CLI flag
- Tested on 3 CSS files: bootstrap.css (233KB), normalize.css (6KB), bulma.min.css (207KB)
- **All 3 files: perfect checksum fidelity ✅**

**CSS results — four-way comparison:**

| File | Original | gzip | .spec | gzip ratio | .spec ratio | .spec/gzip |
|---|---|---|---|---|---|---|
| bootstrap.css | 232,948 B | 30,772 B | 36,487 B | 0.132x | 0.157x | 1.186x |
| normalize.css | 6,138 B | 1,751 B | 2,056 B | 0.285x | 0.335x | 1.174x |
| bulma.min.css | 207,302 B | 27,452 B | 31,608 B | 0.152x | 0.153x | 1.151x |

**Key finding — CSS is Spectrum's best language so far:**
Bootstrap CSS compresses to 0.157x (6.4× reduction), beating every previous language result. The .spec/gzip gap narrows to 1.15–1.19x — closer to gzip than Python (1.16x), HTML (1.17–1.21x), or JS (1.19–1.20x). This is because CSS has extreme property-name repetition (the same 40 properties repeat thousands of times across a large stylesheet), and the Spectrum dictionary eliminates that repetition efficiently before zlib even sees the stream.

**Tokenizer dict hit rate:**
- bootstrap.css (minified): 33.9% dict hits — impressive given minification strips most whitespace
- normalize.css (formatted): higher hit rate expected on formatted CSS

**Complete 4-language picture (large files):**

| File | Lang | Original | gzip | .spec | gzip ratio | .spec ratio | .spec/gzip |
|---|---|---|---|---|---|---|---|
| mega_stdlib.py | Python | 1,124 KB | 254 KB | 294 KB | 0.231x | 0.268x | 1.16x |
| jquery.js | JS | 282 KB | 83 KB | 99 KB | 0.294x | 0.350x | 1.19x |
| bootstrap.js | JS | 226 KB | 46 KB | 55 KB | 0.203x | 0.243x | 1.20x |
| underscore.html | HTML | 169 KB | 39 KB | 46 KB | 0.233x | 0.273x | 1.17x |
| socat.html | HTML | 235 KB | 47 KB | 57 KB | 0.200x | 0.242x | 1.21x |
| bootstrap.css | CSS | 233 KB | 31 KB | 36 KB | 0.132x | 0.157x | **1.19x** |
| bulma.min.css | CSS | 207 KB | 27 KB | 32 KB | 0.132x | 0.153x | **1.15x** |

**.spec gap vs gzip is stable at 1.15–1.21x across all four languages.**

---

### Session 9 — Dictionary v7: English Plain Text
**Date:** April 2026
**What we did:**
- Added English plain-text support: 234,248 English words mapped to sequential RGB values starting at (3,0,0)
- Added 5 control tokens (CTRL:CAP_FIRST, CTRL:CAP_ALL, CTRL:BEGIN_WORD, CTRL:END_WORD, CTRL:NUM_SEP) for capitalisation and letter-by-letter word reconstruction
- Built `tokenizers/text_tokenizer.py` — handles capitalisation, punctuation, unknown words character-by-character
- Dictionary v7: 234,702 tokens total — zero collisions ✓
- Round-trip fidelity verified on plain English prose ✅

---

### Session 10 — Dictionary v8: TypeScript, SQL, Rust
**Date:** April 2026
**What we did:**
- Added TypeScript support: 16 TS-specific keywords (steel-blue family R=244, B=90) — placed after ENGLISH_WORDS so TS keywords override same-spelling English words
- Added SQL support: 69 DML/DDL keywords (deep-plum R=241, B=110) + 43 aggregate functions (R=242, B=110). SQL tokenizer emits uppercase keywords as dict tokens, lowercase falls back char-by-char to guarantee round-trip
- Added Rust support: 20 keywords (forest-sage R=243, B=70) including `::` path separator and lifetime annotations
- Built `tokenizers/ts_tokenizer.py`, `tokenizers/sql_tokenizer.py`, `tokenizers/rust_tokenizer.py`
- Updated `spec_encoder.py`: LANGUAGE_TS=5, LANGUAGE_SQL=6, LANGUAGE_RUST=7; auto-detects .ts/.tsx/.sql/.rs
- Dictionary v8: 234,830 tokens — zero collisions ✓
- All three new languages: perfect round-trip fidelity ✅

---

### Session 11 — Dictionary v9: PHP + Backwards Compatibility + Version Snapshots
**Date:** April 2026
**What we did:**
- Added PHP support: 24 PHP-specific keywords (warm-sand R=245, B=80) + 53 built-in functions (R=245, B=100/104/108)
- Built `tokenizers/php_tokenizer.py` — handles PHP open/close tags, `#` line comments, heredoc/nowdoc (opaque passthrough), `$varName` variables (emits `$` char then identifier), `?->` nullsafe operator
- Updated `spec_encoder.py`: LANGUAGE_PHP=8; auto-detects .php/.phtml
- Dictionary v9: 234,893 tokens — zero collisions ✓

**Backwards Compatibility System:**
- Proved the append-only ID guarantee: token IDs are strictly stable between versions (zero mismatches across v7→v8→v9)
- Built `spec_format/_frozen/` package — stores just one integer (SPEC_TOKEN_COUNT) per historical version; the decoder reconstructs any old ID table as `SPEC_TOKENS[:count]`
- `spec_format/spec_decoder.py` updated to be version-aware: loads the correct frozen snapshot for any v7+ file, warns on unknown future versions, rejects pre-v7 (different binary format)
- Built `spec_format/spec_migrate.py` — upgrades any `.spec` file or directory from an older dict version to the current one; supports `--dry-run`, `--backup`, `--recursive`

**Version Snapshot System:**
- Built `make_snapshot.py` — captures a complete snapshot of the core encoding stack (dictionary, tokenizers, spec_format, encoder, decoder) into `versions/vN/` at the project root
- `versions/v8/` — snapshot of encoding logic as of dictionary v8 (Python, HTML, JS, TS, CSS, SQL, Rust, English)
- `versions/v9/` — snapshot of encoding logic as of dictionary v9 (adds PHP) ← current
- **Important workflow rule:** run `python make_snapshot.py` BEFORE bumping `DICT_VERSION` — the snapshot must capture the old version's code. See PROJECT_OUTLINE.md for the full step-by-step workflow.
- `make_snapshot.py --list` shows all snapshots with token count, date, and languages covered

**PHP round-trip results:**
- PHP encode → decode: checksum ✓ perfect on all test files including class/namespace/nullsafe/heredoc cases
- Compression ratio on a 944B PHP controller: 0.69x (better than gzip on small files)

---

## Round-Trip Test Results

| Test | Source File | Original Size | PNG Size | Ratio | Saving | Fidelity |
|------|-------------|---------------|----------|-------|--------|----------|
| 1    | fibonacci.py    | 2,201 bytes    | 2,365 bytes  | 1.075× | −164 B    | ✅ Perfect |
| 2    | encoder.py      | 10,954 bytes   | 8,466 bytes  | 0.773× | +2,488 B  | ✅ Perfect |
| 3    | decoder.py      | 7,113 bytes    | 6,227 bytes  | 0.875× | +886 B    | ✅ Perfect |
| 4    | dictionary.py   | 9,325 bytes    | 7,393 bytes  | 0.793× | +1,932 B  | ✅ Perfect |
| 5    | mega_stdlib.py  | 1,123,961 bytes | 581,102 bytes | **0.517×** | +542,859 B | ✅ Perfect |

**Observations:**
- fibonacci.py (2 KB) is slightly larger as a PNG — PNG's own overhead dominates at small sizes.
- All files 7 KB+ are smaller as PNGs. The encoding wins from ~3–4 KB upward.
- At 1 MB, Spectrum encodes to **less than half the original size** (48.3% reduction).
- Encode time: 0.9s. Decode time: 0.5s. For a 1.07 MB file. Fast.
- Dictionary v2 (168 tokens) improved compression significantly over v1 by covering 74 built-in functions/types.
- 5/5 round-trips show perfect byte-for-byte fidelity.

---

---

### Session 8 — Phase 2 Planning
**Date:** April 2026
**What we discussed:**
- Recognised that the `.spec` format's token IDs are not just compression artefacts — they're a semantic fingerprint
- Traditional RAG stores data twice: raw text + float embedding vectors (1536 floats × 4 bytes = 6KB per chunk). .spec stores it once, compressed, with meaning already baked in
- Identified that two files sharing many token IDs are genuinely similar in structure and content — no neural network needed to determine this
- Identified three candidate retrieval strategies for Phase 2 (see PROJECT_OUTLINE.md for detail): TF-IDF on token frequencies, n-gram sequence matching, MinHash fingerprinting
- Key question to answer: *is token-ID similarity good enough to replace vector embeddings for retrieval, at least for code and structured text?*

**Phase 2 goals:**
- [ ] Build a minimal Spectrum RAG prototype — index .spec files, query by token similarity, decode and return results
- [ ] Benchmark retrieval quality vs standard embedding-based RAG on the same corpus
- [ ] Determine which retrieval strategy (frequency / sequence / MinHash) performs best
- [ ] Prepare the project for public release under a non-commercial open licence

**Why this matters:**
If token-ID distributions are a valid semantic fingerprint, Spectrum becomes more than a compression format — it becomes an indexable, queryable, compressed knowledge representation that works offline, requires no API calls, has no GPU dependency, and is fully explainable. That's a genuinely different architecture for how AI systems store and retrieve information.

---

## Notes & Ideas

- PNG pipeline is retained as the visual/educational output — useful for demos and explaining the concept
- PNG overhead makes small files slightly larger than source — expected and understood
- Original concept root: what if processors read weight/tone instead of binary? The .spec format is the practical realisation of that idea — colour was the proof of concept, token IDs are the real thing
- Future: RGBA pixel mode for PNG pipeline (4.2 billion symbols per pixel vs 16.7M for RGB)
- Future: explore whether image CDN infrastructure could be repurposed for Spectrum payloads
- Future: dictionary versioning/negotiation between encoder and decoder (codec handshake)
- Future: `.spec` as a transmission protocol for code sharing between AI agents
- Future: detect code similarity/plagiarism or cluster codebases by style using token distributions
