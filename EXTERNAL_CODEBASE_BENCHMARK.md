# External Codebase Benchmark (ECB)

## Purpose

An External Codebase Benchmark, or ECB, is the repeatable pipeline for testing
Spectrum against a third-party GitHub repository.

The goal is to compare:

1. A conventional raw-code RAG store:
   - raw chunk text in JSONL
   - TF-IDF sparse vector matrix
   - TF-IDF vocabulary

2. A Spectrum codebase RAG store:
   - cloned source files encoded into lossless `.spec` chunks
   - compact binary Spectrum BM25 postings index
   - retrieval-only aliases from paths, filenames, language names, and
     identifiers
   - no raw source text stored in the Spectrum store

The `.spec` payload must remain byte-for-byte lossless. Retrieval aliases are
sidecar index features only; they do not rewrite or simplify the payload.

## Trigger Phrases

If a future conversation asks for any of these, use this workflow:

- `ECB`
- `External Codebase Benchmark`
- `External Codebase RAG Benchmark`
- `Third-Party Repo Benchmark`
- `External Repo Smoke Test`

Typical user prompt:

```text
Run an ECB on https://github.com/owner/repo
```

## Pipeline

1. Clone the repository under `external_repos/<repo-name>`.
   - Use a shallow clone unless the user asks for history.
   - Record the checked-out commit SHA.
   - Keep `external_repos/` ignored by Git.

2. Inspect the repo shape.
   - Count supported source/doc files.
   - Summarize extension mix and approximate bytes.
   - Identify generated/vendor directories to exclude.

3. Run `rag/codebase_benchmark.py`.
   - The harness scans supported source files.
   - Each file is encoded into a language-aware `.spec` chunk by default.
   - Use `--chunk-chars 0` for one chunk per file unless testing chunking.
   - The Spectrum store builds `.spec` payloads plus `index.bin` when
     `--postings-format v2` is used, then packages the canonical Spectrum
     corpus as `spectrum.specpack`.
   - The conventional store builds raw `chunks.jsonl` plus TF-IDF artifacts.

4. Verify fidelity.
   - The run is not valid unless Spectrum lossless is `True`.
   - If fidelity fails, inspect the failing file/chunk.
   - The harness may fall back to character-token payloads for tokenizer edge
     cases, but the benchmark must still report lossless output.

5. Report the result.
   - Files and chunk count.
   - Extension mix.
   - Raw chunk bytes.
   - Total store bytes.
   - Payload bytes.
   - Index/vector bytes.
   - Build time.
   - Hit@1, MRR, Recall@5.
   - Average and p95 query latency.
   - Fidelity status.
   - Commit SHA and excluded directories.

6. State the caveat.
   - Current ECB query sets are generated from file paths and identifiers.
   - Treat this as a smoke test until labelled code queries are added.
   - Stronger future baselines should include Zoekt/Lucene/OpenSearch and
     embedding or hybrid retrieval.

## Command Template

```powershell
git clone --depth=1 https://github.com/owner/repo external_repos\repo

python rag\codebase_benchmark.py `
  --source-root external_repos\repo `
  --out-dir benchmarks\generated\codebase_benchmark_repo `
  --max-files 0 `
  --postings-format v2 `
  --queries 120 `
  --exclude-dir dist `
  --exclude-dir build `
  --exclude-dir coverage `
  --exclude-dir node_modules
```

Tune excludes for each repo. Common extra excludes:

```text
dist
build
coverage
node_modules
vendor
.next
.cache
typedoc
docs/generated
models
```

## What Counts As A Win

An ECB win should be framed carefully:

- Storage win: Spectrum total store bytes are smaller than raw+TF-IDF.
- Payload win: `.spec` payload bytes are smaller than raw JSONL payload bytes.
- Index win: Spectrum `spectrum.specpack` index and metadata are smaller than TF-IDF
  matrix plus vocabulary.
- Retrieval smoke-test win: Spectrum beats raw+TF-IDF on generated file/path
  queries.
- Latency win: Spectrum average query latency is lower.
- Fidelity win: all `.spec` chunks decode exactly.

Do not claim general code-search superiority from generated queries alone.

## Large Java Example

Repository/source tree:

```text
/Users/video/jdk
```

Command:

```powershell
python rag\codebase_benchmark.py `
  --source-root /Users/video/jdk `
  --out-dir benchmarks\generated\codebase_benchmark_openjdk_jdk_java_spb2 `
  --max-files 0 `
  --queries 80 `
  --postings-format v2
```

Result:

| Store | Bytes | Ratio vs raw chunks | Payload bytes | Index/vector bytes | Hit@1 | MRR | Recall@5 | Avg query ms | P95 query ms |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| Conventional raw+TF-IDF | 507,690,480 | 1.242x | 435,772,020 | 71,918,310 | 0.200 | 0.258 | 0.362 | 18.856 | 22.474 |
| Spectrum `.spec`+SPB2 BM25 | 185,950,831 | 0.455x | 144,726,790 | 41,223,626 | 0.325 | 0.439 | 0.637 | 15.347 | 28.328 |

Fidelity:

```text
53,780 / 53,780 file-level chunks lossless
```

This is the strongest current ECB storage signal: Spectrum is 63.37% smaller
than the conventional raw+TF-IDF store while retaining better generated-query
quality and lower average query latency. The tradeoffs are much slower Python
build time and slightly worse p95 query latency.

## Smaller External Example

Repository:

```text
https://github.com/vladmandic/human
```

Commit:

```text
d0c4c83
```

Command:

```powershell
python rag\codebase_benchmark.py `
  --source-root external_repos\human `
  --out-dir benchmarks\generated\codebase_benchmark_human `
  --max-files 0 `
  --queries 120 `
  --exclude-dir dist `
  --exclude-dir typedoc `
  --exclude-dir models `
  --exclude-dir build `
  --exclude-dir coverage
```

Result:

| Store | Bytes | Ratio vs raw chunks | Payload bytes | Index/vector bytes | Hit@1 | MRR | Recall@5 | Avg query ms |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| Conventional raw+TF-IDF | 2,912,945 | 1.326x | 2,279,391 | 633,403 | 0.242 | 0.326 | 0.525 | 0.440 |
| Spectrum `.spec`+binary BM25 | 1,230,156 | 0.560x | 897,993 | 331,782 | 0.317 | 0.390 | 0.542 | 0.079 |

Fidelity:

```text
172 / 172 file-level chunks lossless
```
