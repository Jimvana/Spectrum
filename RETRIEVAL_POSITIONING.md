# Spectrum Retrieval Positioning

## Core Focus

Spectrum should be discussed and evaluated as a **retrieval-ready storage format**, not as a general-purpose compression competitor.

The central claim:

> A `.spec` file is both a compact stored artifact and a directly searchable semantic-token representation.

That is the unusual part. In most RAG and code-search systems, storage and retrieval are separate layers: raw files or chunks are stored, then an index, vector store, trigram index, or AST/chunk representation is built beside them. Spectrum's stored form already contains meaningful token IDs that can be searched directly.

## What Spectrum Is Competing With

Focus comparisons on retrieval systems and retrieval-ready representations:

- Raw BM25 / Lucene-style inverted indexes
- Zoekt / Sourcegraph-style code search
- Tree-sitter chunking + BM25
- Embedding RAG
- Hybrid BM25 + embeddings
- Other explainable sparse retrieval methods

These are the meaningful baselines because they retrieve information.

## What Spectrum Is Not Competing With

Do not lead with comparisons against passive compression formats:

- gzip
- Brotli
- zstd
- zip

Those tools may be relevant as storage baselines, but they are not RAG or code-search systems. They compress bytes; they do not provide retrieval, semantic matching, token-level explainability, or decode-on-demand search workflows.

If they are mentioned, keep them clearly scoped:

> Passive compressors are storage tools, not search baselines.

For Wikipedia-scale data, keep the distinction sharp:

- `.bz2` is compressed source material. It is not directly useful to an LLM
  until decompressed and parsed.
- `.zim` is an offline reader/archive format. It is excellent for human browsing
  and can be fast when paired with its indexes, but the compressed clusters are
  not themselves semantically meaningful to an LLM.
- `.spec` is intended to be a retrieval-ready storage layer. Its advantage only
  appears once we build indexes over token IDs and decode selected hits on
  demand.

## Preferred Framing

Use this framing:

> Spectrum sits between raw BM25 and syntax-aware code retrieval: not as fast as raw BM25, not as top-rank accurate as Tree-sitter chunking in the current small test, but unusually balanced because the same `.spec` artifact is compact, explainable, searchable, and decodable on demand.

Shorter version:

> Raw BM25 is fastest. Tree-sitter is strongest for code structure. Spectrum is the compact, explainable, retrieval-ready middle ground.

## Current Local Benchmark Signal

Local benchmark context:

- Corpus: 14 files
- Queries: 8 labelled retrieval queries
- Spectrum index: `.spec` token ID BM25
- Raw BM25: lexical source-text BM25 proxy
- Tree-sitter: syntax chunking + BM25, aggregated back to files
- Dense result: local LSA proxy, not a neural embedding model
- Real Lucene, Zoekt, and neural embeddings were not run in this environment

Measured results:

| Method | Hit@1 | MRR | Recall@5 | Avg query time |
|---|---:|---:|---:|---:|
| Spectrum BM25 | 87.5% | 0.906 | 90.5% | 2.25 ms |
| Raw BM25 | 87.5% | 0.917 | 66.7% | 0.12 ms |
| Tree-sitter chunk BM25 | 100.0% | 1.000 | 71.4% | 7.12 ms |
| Dense LSA proxy | 62.5% | 0.792 | 85.7% | 11.87 ms |
| Hybrid BM25 + LSA | 75.0% | 0.875 | 85.7% | 11.18 ms |

Interpretation:

- Spectrum is slower than raw BM25 but still fast.
- Spectrum is faster than Tree-sitter chunk BM25 in this test.
- Spectrum has strong candidate recall.
- Tree-sitter had the best top-rank accuracy on this small benchmark.
- Raw BM25 remains a very strong speed baseline.
- The dense/embedding comparison is only a local proxy and should not be treated as a production embedding benchmark.

## Strongest Product Claim

The most defensible product direction is:

> Offline, explainable, compressed retrieval for code and structured text.

Spectrum is strongest when the user cares about:

- Local/offline retrieval
- Explainable matching
- Code and structured text
- Avoiding embedding API calls
- Keeping storage and retrieval representation close together
- Decode-on-demand access to original source
- A format that can be indexed without fully reconstructing every file

## Weaknesses To Be Honest About

Be explicit about these:

- Raw BM25 is much faster in the current local benchmark.
- Tree-sitter chunking is stronger for syntax-aware code relevance.
- Hybrid BM25 + embeddings is likely stronger for broad natural-language RAG.
- Spectrum's HTML query normalization needs work; the `html head body div class href` query underperformed.
- Current benchmark is small and not enough for production claims.
- Real Lucene, Zoekt, and neural embedding baselines still need to be run.

## Current RAG Storage Benchmark

The active proof harness is now `rag/storage_benchmark.py`.

It compares two stores built from identical chunks:

- Conventional local RAG: raw `chunks.jsonl` plus persisted TF-IDF vectors.
- Spectrum RAG: lossless `.spec` chunks plus compact binary Spectrum token BM25 postings/frequency index.

Current 120-page Wikipedia sample result with 6k-character chunks:

| Store | Total bytes | Payload bytes | Index/vector bytes | Hit@1 | MRR | Avg query time |
|---|---:|---:|---:|---:|---:|---:|
| Conventional raw+TF-IDF | 6,430,395 | 4,226,166 | 2,204,110 | 1.000 | 1.000 | 1.233 ms |
| Spectrum `.spec`+binary BM25 | 4,172,510 | 2,275,732 | 1,896,562 | 0.923 | 0.936 | 2.988 ms |

The most important signal is component-level:

- Spectrum payload is much smaller than raw text payload.
- Spectrum total store can be smaller than a conventional raw+vector store with realistic larger chunks.
- The compact binary BM25 index is now smaller than the conventional TF-IDF vector/index component on the 6k run.
- The next meaningful engineering win is better query/ranking quality against conventional TF-IDF and true embedding/hybrid baselines.

## Next Benchmark Plan

The next serious benchmark should compare Spectrum against real retrieval systems:

1. Build a larger corpus:
   - 10-50 repositories
   - mixed code and documentation
   - labelled query-to-file or query-to-chunk relevance

2. Run true baselines:
   - Lucene/OpenSearch BM25
   - Zoekt
   - Tree-sitter chunk BM25
   - Chroma or FAISS vector store
   - neural embeddings
   - hybrid BM25 + embeddings

3. Measure end to end:
   - index size
   - source/chunk/vector storage size
   - index build time
   - query latency
   - Hit@1
   - MRR
   - Recall@k
   - decode time
   - explainability of matches

Ranking/query-normalization tasks are tracked in `RAG_RANKING_TODO.md`. Use that
file as the running checklist and mark items complete when benchmarked.

## Next Build Plan: Wiki Reader / Indexer

The immediate task is to turn the v10 full-XML `.spec` shards into something an
LLM agent can use directly:

1. Build a manifest verifier that checks all shard lengths/checksums without
   writing decoded XML to disk.
2. Build a page-boundary scanner over token IDs: `<page>`, `<title>`, `<text`,
   `</text>`, `</page>`.
3. Build a title index: normalized title -> `(shard, token_start, token_end)`.
4. Build a token inverted index over page or chunk IDs.
5. Add a query tokenizer that converts user queries into Spectrum token IDs.
6. Add decode-on-demand for one page/chunk.
7. Benchmark against ZIM/Kiwix search, raw BM25 over extracted text, and
   embeddings/hybrid retrieval.

Success criteria:

- Exact title lookup returns the page without decoding unrelated shards.
- Token/BM25 search returns relevant pages with explainable token matches.
- The reader can decode only the selected result.
- End-to-end query latency is competitive with ordinary text indexes while
  retaining compact `.spec` storage.

## One-Sentence Carryover

If future conversations need a quick reset, use this:

> Keep Spectrum positioned as a retrieval-ready `.spec` artifact: the comparison is BM25, Zoekt, Tree-sitter chunking, embeddings, and hybrid RAG, not passive compressors like gzip or Brotli.
