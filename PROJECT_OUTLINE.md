# Spectrum Algo — Project Outline

## Concept

Spectrum Algo is a semantic compression and encoding system that converts source code and structured text into a compact binary format — the `.spec` file — by mapping meaningful language tokens to a shared integer dictionary, then compressing the resulting ID stream.

The core idea: instead of treating source code as a flat stream of bytes (which general-purpose compressors like gzip see as opaque), Spectrum understands the *language structure* of the content. Python keywords, HTML tags, JS operators, CSS properties, and English words each map to a fixed numeric token ID. The resulting ID stream is semantically grouped, RLE-compressed, and then zlib'd — producing a file that is within 15–20% of gzip on raw size, but with one crucial difference: **the token IDs carry meaning**.

This has two major implications:

1. **Compression** — .spec files are 15–85% of original size across Python, HTML, JS, CSS, and plain text, with perfect lossless round-trip fidelity verified by checksum.

2. **Semantic retrieval** — because .spec token IDs represent actual language constructs, the token frequency distribution of a .spec file is a natural semantic fingerprint. Two files that share many token IDs are genuinely similar in structure and content. This opens the door to retrieval without neural embeddings.

The longer-term vision: Spectrum is a foundation for a new kind of data layer — one where compression and semantic understanding are the same operation, not separate steps.

---

## Origin

The original spark was a thought experiment: *what if processors could read weight or tone rather than just binary 1s and 0s?* Colour was the first practical software-layer proof of that idea — encoding tokens as RGB pixel values in a PNG. That approach proved round-trip fidelity worked, but PNG was holding the format back. The `.spec` binary format keeps the semantic dictionary idea and drops the image container entirely, achieving 2–3x better compression than the PNG approach.

---

## Goals

### Phase 1 — Completed ✅
1. Prove round-trip fidelity — encode source → .spec → decode back to source, byte-for-byte identical, checksum verified
2. Build a stable, versioned token dictionary covering Python, HTML, JS, CSS, and plain English
3. Achieve meaningful compression — within striking distance of gzip, across multiple languages
4. Establish the .spec binary format as the canonical Spectrum output

### Phase 2 — Semantic Retrieval (Current Focus)
5. Prove that .spec token ID distributions can act as a retrieval-ready storage layer
6. Build a prototype Spectrum RAG system — store .spec chunks, retrieve by token similarity, decode on demand
7. Benchmark storage size, retrieval quality, query speed, decode speed, and fidelity against conventional RAG stores
8. Publish the project openly under a non-commercial licence

---

## The .spec Format

A `.spec` file is a self-contained, versioned binary with a 16-byte header and a zlib-compressed body.

```
Header (16 bytes, uncompressed):
  [0:4]   Magic:           b'SPEC'
  [4:6]   Dict version:    uint16 BE
  [6:8]   Flags:           uint16 BE  (bit 0 = RLE enabled)
  [8:12]  Original length: uint32 BE  (bytes in original UTF-8 source)
  [12:14] Language ID:     uint16 BE  (0=Python, 1=HTML, 2=JS, 3=CSS, 4=Text,
                                       5=TypeScript, 6=SQL, 7=Rust, 8=PHP,
                                       9=XML/Wiki, 10=Java, 11=C, 12=C++,
                                       13=Go, 14=C#, 15=Shell, 16=JSON,
                                       17=YAML, 18=TOML)
  [14:16] Checksum:        uint16 BE  (sum of original bytes mod 65536)

Body (zlib level 9, compressed):
  Stream of uint32 LE token IDs.
  RLE runs of 3+ identical IDs are collapsed: ID, RLE_MARKER, count
  Unknown chars fall back to ASCII (ID = ASCII_BASE + ord) or Unicode (UNICODE_MARKER + codepoint)
```

This format is language-aware, versioned, and fully self-describing. A decoder that receives any `.spec` file knows the language, dictionary version, original size, and has a checksum to verify fidelity — without needing any external metadata.

---

## Extension Libraries

The current core dictionary is intentionally stable, but large corpora need
domain-specific "chapters" rather than one ever-growing universal dictionary.
Spectrum now treats those chapters as extension libraries declared in a shard
manifest.

For example, a cleaned Wikipedia corpus declares:

```
spectrum-core@10
english-text@1
wikimedia-clean-text@1
```

A lossless full-XML Wikimedia sample now declares:

```
spectrum-core@10
english-text@1
wikimedia-xml@1
```

This makes `.spec` portable without forcing every decoder to ship every domain
dictionary. The file or shard manifest says which libraries are required; the
decoder can load them, verify their hashes, and then interpret the token stream.

Design rules:

- Library names and versions are explicit.
- Each library has a stable hash so decoding is reproducible.
- Token IDs must remain unambiguous. Spectrum's first extension model uses
  reserved global ranges inside the existing uint32 ID stream.
- Missing libraries should fail clearly instead of silently producing bad text.
- `.specpack` is the likely future bundle format: data shards plus required
  libraries and manifests in one portable package.

Current implementation status:

- `spec_format/libraries.py` defines the manifest schema and built-in library
  declarations.
- Dictionary v10 appends 64 XML/MediaWiki source tokens directly to the core
  dictionary.
- `tokenizers/wiki_tokenizer.py` promotes repeated XML/MediaWiki syntax markers
  to those v10 core tokens in raw-wikitext and full-XML modes.
- `tools/wiki_dump_to_spec.py --mode full-xml` streams decompressed Wikimedia
  XML directly into `.spec` shards, preserving XML structure and metadata.
- The 16-byte `.spec` binary header has not yet been changed, so dependency
  loading is manifest-level rather than embedded in each individual shard.

---

## Compression Results (Phase 1)

| File | Lang | Original | gzip | .spec | .spec ratio | .spec vs gzip |
|------|------|----------|------|-------|-------------|---------------|
| bootstrap.css | CSS | 233 KB | 31 KB | 36 KB | 0.157× | 1.19× |
| bulma.min.css | CSS | 207 KB | 27 KB | 32 KB | 0.153× | 1.15× |
| bootstrap.js | JS | 226 KB | 46 KB | 55 KB | 0.243× | 1.20× |
| socat.html | HTML | 235 KB | 47 KB | 57 KB | 0.242× | 1.21× |
| mega_stdlib.py | Python | 1,124 KB | 254 KB | 294 KB | 0.268× | 1.16× |
| jquery.js | JS | 282 KB | 83 KB | 99 KB | 0.350× | 1.19× |
| moby dick.txt | Text | 1.3 MB | — | (tested) | — | — |

**.spec consistently achieves 15–85% of original size, within 15–21% of gzip, across all supported languages. All files decode with perfect byte-for-byte fidelity.**

The gap vs gzip (~15–21%) is the cost of the semantic token layer. It's not a bug — it's the feature. Gzip output is meaningless compressed bytes. .spec output is structured semantic token IDs you can reason about.

---

## Project Structure

```
/Spectrum Algo
  /encoder            # encoder.py — source → PNG (original approach, still works)
  /decoder            # decoder.py — PNG → source (original approach)
  /spec_format        # spec_encoder.py, spec_decoder.py — .spec binary format
    /_frozen          # frozen dictionary snapshots (one integer per version)
      v7.py           # SPEC_TOKEN_COUNT = 234,702
      v8.py           # SPEC_TOKEN_COUNT = 234,830
      v9.py           # SPEC_TOKEN_COUNT = 234,893  ← current
    /output           # encoded .spec files and their decoded counterparts
    spec_migrate.py   # upgrades old .spec files to the current dictionary version
  /tokenizers         # language-specific tokenisers (9 languages)
    python_tokenizer  # via encoder.py (Python stdlib tokenize)
    html_tokenizer.py
    js_tokenizer.py
    css_tokenizer.py
    text_tokenizer.py
    ts_tokenizer.py
    sql_tokenizer.py
    rust_tokenizer.py
    php_tokenizer.py
  /versions           # versioned snapshots of core logic (one subdirectory per release)
    /v8               # complete snapshot of encoding stack as of dictionary v8
    /v9               # complete snapshot of encoding stack as of dictionary v9
    /v10              # complete snapshot of encoding stack as of dictionary v10
    /v11              # complete snapshot of encoding stack as of dictionary v11
    /v12              # complete snapshot of encoding stack as of dictionary v12
  /test_sources       # source files used for benchmarking
  /output_images      # PNG outputs (legacy, kept for comparison)
  /results            # decoded outputs from PNG pipeline (legacy)
  /Runtime            # JS decoder, service worker runtime, and dev server prototype
  dictionary.py       # Shared token dictionary (v12, 235,021 SPEC tokens)
  english_tokens.py   # English word token list (234,248 words, generated)
  make_snapshot.py    # captures a versioned snapshot into versions/vN/
  benchmark_results.json
  PROJECT_OUTLINE.md
  PROGRESS.md
```

### Version Snapshot Workflow

Each time the dictionary is bumped to a new version, a snapshot of the core encoding logic is captured in `versions/vN/`. This makes it possible to audit exactly what code produced any historical `.spec` file and to verify the append-only ID guarantee between versions.

**The correct order is critical:**

1. **Before** incrementing `DICT_VERSION` in `dictionary.py`, run:
   ```
   python make_snapshot.py
   ```
   This captures the current version's code. Running it after bumping the version captures the new code instead, which requires manual patching of the snapshot.

2. Add the new language tokens to `dictionary.py` and increment `DICT_VERSION`.

3. Add a frozen count file `spec_format/_frozen/vN.py`:
   ```python
   SPEC_TOKEN_COUNT: int = <len(D.SPEC_TOKENS) after adding new tokens>
   ```

4. Register it in `spec_format/_frozen/__init__.py` — one import and one dict entry.

5. Run `python dictionary.py` to confirm zero RGB collisions.

6. Migrate any existing `.spec` files with `python spec_format/spec_migrate.py <dir>`.

**What is snapshotted** (by `make_snapshot.py`): `dictionary.py`, all `tokenizers/`, `spec_format/` (including `_frozen/`), `encoder/`, `decoder/`.

**What is NOT snapshotted**: `english_tokens.py` (234K-line generated file, identical across all versions), test data, browser/runtime proof tools, and RAG.

---

## Tech Stack

- **Language:** Python 3
- **Compression:** zlib (level 9), RLE on token ID stream
- **Dictionary:** v10 — 234,957 tokens across Python, HTML, JavaScript, TypeScript, CSS, SQL, Rust, PHP, English plain text, and XML/Wiki source syntax
- **Backwards compatibility:** all `.spec` files from v7 onwards are decodable; frozen snapshot system stores one integer per historical version
- **No external ML dependencies** — Spectrum is self-contained

---

## Phase 2 — Semantic Retrieval: The Plan

This is where Spectrum gets genuinely interesting.

### The Problem with Traditional RAG

A standard RAG (Retrieval-Augmented Generation) system stores data twice: once as raw text, and once as a vector of ~1536 floats generated by an external embedding model. Those floats cost money to generate, take space to store, require an internet connection, and are completely opaque — you can't look at them and understand why two chunks matched.

### The Spectrum Approach

The token IDs inside a `.spec` file are already a semantic representation. Python files that do similar things use similar tokens. CSS files for similar UIs share the same property tokens. We don't need a neural network to tell us that — the token overlap is the signal.

**Three retrieval strategies to explore:**

1. **Token Frequency (TF-IDF style)** — build a sparse vector of token ID frequencies per .spec chunk. Cosine similarity on sparse integer vectors. No neural net, no floats. Mathematically equivalent to BM25 but operating on Spectrum tokens instead of raw words.

2. **Token Sequence (n-gram matching)** — look at sequences of token IDs, not just frequencies. Two code files that share patterns like `def → name → ( → args → )` are structurally similar in a way frequency alone can't capture.

3. **MinHash fingerprinting** — use the set of unique token IDs as a MinHash signature. Ultra-fast approximate similarity with no floating point at all. Scales to millions of .spec files.

### What Phase 2 Looks Like

- Build a minimal Spectrum RAG prototype: index a corpus of .spec files, accept a query, return the most similar chunks, decode and return the text
- Benchmark total storage, retrieval quality, query latency, decode latency, and lossless fidelity against a conventional RAG store on the same chunks
- The key question: *for code and structured text, is token-ID similarity good enough to replace vector embeddings?* The hypothesis is yes — and if it is, Spectrum RAG is faster, smaller, cheaper, offline-capable, and fully explainable.

### Current RAG Storage Benchmark

The active proof harness is `rag/storage_benchmark.py`.

It builds two stores from the same Wikipedia-derived text chunks:

1. Conventional local RAG baseline:
   - raw `chunks.jsonl`
   - persisted TF-IDF sparse vector matrix
   - TF-IDF vocabulary

2. Spectrum RAG:
   - lossless `.spec` chunks
   - compact binary Spectrum token BM25 postings/frequency index
   - no raw text stored in the Spectrum store

Current 6k-character chunk result on 120 Wikipedia pages:

| Store | Total bytes | Payload bytes | Index/vector bytes | Hit@1 | MRR | Avg query |
|---|---:|---:|---:|---:|---:|---:|
| Conventional raw+TF-IDF | 6,430,395 | 4,226,166 | 2,204,110 | 1.000 | 1.000 | 1.233 ms |
| Spectrum `.spec`+binary BM25 | 4,172,510 | 2,275,732 | 1,896,562 | 0.923 | 0.936 | 2.988 ms |

Spectrum round-tripped every chunk losslessly with zero fidelity failures.

Interpretation:

- Spectrum payload size is already substantially smaller than raw chunk text.
- With larger RAG chunks, total Spectrum store size is close to raw chunk size while still retrieval-ready.
- With smaller chunks, the compact binary index keeps Spectrum ahead of the conventional raw+TF-IDF store on total size.
- The next engineering target is ranking/query normalization and stronger retrieval baselines.

See `RAG_STORAGE_BENCHMARK.md` for the current benchmark method and results.
Use `RAG_RANKING_TODO.md` as the standing checklist for ranking/query-normalization work and mark items complete there in future sessions.

### LLM Data Layer Comparison: BZ2 vs ZIM vs SPEC

For large datasets such as Wikipedia, there are three different kinds of
artifact:

| Format | What it is | Good for | Weakness for LLM/agent use |
|---|---|---|---|
| `.bz2` Wikimedia dump | Compressed XML source material | Archival source, rebuild pipelines | Must decompress and parse XML/wikitext before use |
| `.zim` / Kiwix | Offline rendered article archive | Human offline browsing, mature reader/search tooling | Content is packaged for readers; compressed clusters are opaque without ZIM tooling/indexes |
| `.spec` + libraries | Lossless tokenized XML/source representation | LLM-native retrieval, token search, explainable matching, decode-on-demand | Needs Spectrum indexer/reader tooling to realise the advantage |

Current conclusion:

- For humans, `.zim` is the most immediately useful artifact.
- For raw archival fidelity, `.bz2` is the upstream source.
- For LLMs and agents, `.spec` is potentially the most intuitive format because
  its stored form contains meaningful token IDs: XML boundaries, titles, text
  fields, MediaWiki syntax, words, punctuation, and fallback Unicode.

The important distinction is that `.spec` should not be positioned as simply
"smaller than compression". On the 2 GiB full-XML test, `.spec` was larger than
gzip and bzip2 on identical bytes. The value is that the compressed artifact is
also structured and indexable.

### Next Build Tasks: Spectrum Wiki Reader / Indexer

To make `.spec` genuinely better for LLM use, build the tooling around the
format:

1. **Shard verifier**
   - Verify every `.spec` shard in a manifest without writing decoded XML to disk.
   - Emit pass/fail counts, checksum status, total decoded bytes, and timing.

2. **Page boundary index**
   - Scan full-XML `.spec` shards for `<page>`, `<title>`, `<text`, and `</page>` token IDs.
   - Store page offsets as `(shard, token_start, token_end, title)`.
   - Allow direct decode of one page without decoding a whole shard.

3. **Title index**
   - Map normalized title to page boundary.
   - Support exact title lookup and prefix/fuzzy lookup.

4. **Token inverted index**
   - Map token ID to posting lists of pages/chunks.
   - Start with BM25-style scoring on Spectrum token IDs.
   - Keep postings explainable: show which token IDs matched and what they mean.

5. **Query tokenizer**
   - Convert user queries into Spectrum token IDs using the same libraries.
   - Support title queries, natural-language queries, and MediaWiki-aware queries.

6. **Decode-on-demand reader**
   - Decode only the selected page/chunk from `.spec`.
   - Optionally render wikitext to plain text or HTML after retrieval.

7. **Benchmark harness**
   - Compare `.spec` index search against:
     - raw XML + gzip/bzip2 storage
     - ZIM/Kiwix search where available
     - BM25 over extracted article text
     - embeddings/hybrid retrieval
   - Measure storage size, index size, build time, query latency, decode latency,
     Hit@k, MRR, and explainability.

### Why This Matters Beyond RAG

If token-ID distributions are a valid semantic fingerprint, Spectrum becomes more than a compression format. It becomes an **indexable, queryable, compressed representation of knowledge** — one that any system can read without a GPU, an API key, or a 10GB model weight file.

That's a fundamentally different architecture for how AI systems store and retrieve information.

---

## Licence

Spectrum Algo is intended to be released under a **non-commercial open licence**. Free to use, fork, and build on — but not to sell or monetise without permission. The goal is to make this as useful as possible to developers, researchers, and AI systems, not to lock it behind a paywall.

---

## Future Possibilities

- Extend dictionary to JSON, Markdown, and other structured formats
- Dictionary version negotiation between encoder and decoder (like a codec handshake)
- Streaming .spec encoder for large files and live data
- `.spec` as a transmission protocol — compact payloads for code sharing between AI agents
- Explore whether .spec token distributions could be used to detect code plagiarism, find similar bugs across codebases, or cluster codebases by style
- RGBA pixel mode for the PNG pipeline (retained for visual/educational use)
