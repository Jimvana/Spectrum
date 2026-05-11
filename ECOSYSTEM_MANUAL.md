# Spectrum SDK, CLI, And API Manual

This manual is for developers who want to use Spectrum as a local-first,
lossless, searchable store for RAG, code search, memory, archival, or transport
workflows.

Spectrum is pre-1.0. The current package layout and command/API names are usable
for development, demos, and early integrations, but the format and public API
should still be treated as a developer preview.

## What Spectrum Provides

Spectrum turns UTF-8 source files into compact `.spec` payloads and groups them
into `.specpack` archives. A `.specpack` can also contain a retrieval index
(`index.bin`) so the same artifact can be:

- stored compactly,
- searched without restoring every source file first,
- verified for byte-for-byte decode fidelity,
- unpacked back to exact source bytes,
- used as a RAG corpus or local knowledge store.

The short version for RAG is:

```text
source folder
  -> spectrum pack
  -> .specpack
  -> spectrum index --embed
  -> spectrum search
  -> hydrate selected source when needed
  -> send context to your model or agent
```

## Package Map

The ecosystem packages live under `packages/`.

| Package | Purpose |
|---|---|
| `packages/core` | Low-level `.spec` and `.specpack` encode/decode, inspect, pack, unpack, and verification APIs. |
| `packages/index` | Retrieval index creation and BM25 search over Spectrum packs. |
| `packages/cli` | Python CLI implementation for `pack`, `index`, `search`, `verify`, `inspect`, and `unpack`. |
| `packages/sdk-python` | Public Python SDK package, importable as `spectrum`. |
| `packages/sdk-js` | Public JavaScript SDK package, importable as `@spectrumstore/sdk`. |
| `packages/server` | Local HTTP API for pack registration, inspection, verification, indexing, search, document read, and unpack. |
| `packages/connectors` | Planned/import connector area for external sources. |
| `packages/integrations` | Planned LangChain, LlamaIndex, and framework adapters. |
| `packages/memory` | Planned source-linked memory layer on top of packs and indexes. |
| `packages/dashboard` | Planned local UI for browsing/searching packs. |
| `packages/cloud` | Reserved for optional hosted/team experiments. The local format does not depend on it. |

The root npm package, `spectrumstore`, is the current turnkey preview wrapper.
It exposes `spectrum` and `spectrumstore` commands and wires Node to the Python
package stack in this checkout.

## Core Concepts

### `.spec`

A `.spec` file is one encoded source file. It contains a Spectrum header,
compressed token IDs, source length, checksum metadata, dictionary version, and
language metadata. The decoder reconstructs the original source bytes and the
verification path checks length and checksum.

Use `.spec` directly when you need to encode or decode one file, inspect codec
metadata, or test low-level format behavior.

### `.specpack`

A `.specpack` file is a ZIP archive using Spectrum's pack manifest. It contains:

- `manifest.json`,
- one `.spec` member per source file under `files/`,
- optionally `index.bin`, the embedded retrieval index.

The manifest records source paths, encoded member paths, original sizes, and
encoded sizes. `spectrum_core.inspect_pack()` and `spectrum inspect` summarize
this metadata without unpacking the source.

### `index.bin`

`index.bin` is Spectrum's compact retrieval sidecar. It is built from `.spec`
payloads rather than restored source text. For `.specpack` files it can be:

- embedded inside the pack with `--embed`, which is easiest to distribute,
- written separately with `--output`, which is useful when the pack should stay
  immutable.

Search uses the index if it exists. If allowed, the CLI and SDK can build a
temporary index when no embedded or sidecar index is available.

### Verify Versus Inspect

`inspect` reads metadata and size information. It is fast and does not prove
that the payload can be decoded correctly.

`verify` decodes into a temporary directory and checks length/checksum fidelity.
Run it after creating packs and before relying on a pack as durable storage.

### Hydration

Hydration means decoding selected `.spec` payloads back to source text. In RAG
systems, search should produce a small ranked candidate set first; hydration
should happen only for the items you want to show, open, or send to a model.

The current SDK exposes whole-pack unpacking. The HTTP API also exposes a
document-read endpoint by source path. More selective SDK hydration APIs are
planned.

## Requirements

For the current preview:

- Python 3.10 or newer.
- Node.js 18 or newer for the npm CLI wrapper and JavaScript SDK tests.
- A Spectrum checkout containing `dictionary.py` and `spec_format/`.

Supported source extensions in the pack builder include:

```text
.py .html .htm .js .mjs .cjs .css .txt .md .ts .tsx .sql .rs .php
.phtml .xml .java .c .h .cpp .cc .cxx .hpp .hh .hxx .go .cs .sh
.bash .zsh .json .yaml .yml .toml
```

Folders named `.git`, `node_modules`, and `__pycache__` are skipped. Existing
`.spec` and `.specpack` files are skipped. Use `--all` or `include_all=True` to
include every non-Spectrum file, but only do that for UTF-8 text-like content.

## Quick Start With The CLI

From the repository root:

```powershell
npm install -g . --force
```

Create, verify, index, search, and unpack a store:

```powershell
spectrum pack ./docs ./docs.specpack --json
spectrum verify ./docs.specpack --json
spectrum index ./docs.specpack --embed --json
spectrum search ./docs.specpack "authentication middleware" --top 5 --json
spectrum unpack ./docs.specpack ./docs-restored --json
```

The root npm wrapper sets `PYTHONPATH` and `SPECTRUM_REPO_ROOT` for you. If the
command fails because Python is missing, install Python 3.10+ and make sure
`py`, `python`, or `python3` is available on `PATH`.

## Local Development Setup

Run all package tests from the repo root:

```powershell
python scripts/test.py
```

Run only Python package tests:

```powershell
python scripts/test.py --python-only
```

Run only JavaScript SDK tests:

```powershell
python scripts/test.py --js-only
```

For direct Python module execution from a checkout without editable installs:

```powershell
$env:PYTHONPATH = "packages/core/src;packages/index/src;packages/cli/src;packages/sdk-python;packages/server/src"
$env:SPECTRUM_REPO_ROOT = (Get-Location).Path
```

On bash-like shells:

```bash
export PYTHONPATH="packages/core/src:packages/index/src:packages/cli/src:packages/sdk-python:packages/server/src"
export SPECTRUM_REPO_ROOT="$PWD"
```

Editable installs are also supported for local package development:

```powershell
python -m pip install -e packages/core -e packages/index -e packages/cli -e packages/sdk-python -e packages/server
```

After that, `spectrum-core` and `spectrum-server` entry points should be
available in the active Python environment.

## CLI Manual

The recommended preview command is `spectrum`. The same root package also
exposes `spectrumstore`.

Show command help:

```powershell
spectrum --help
spectrum pack --help
spectrum search --help
```

### `pack`

Create a `.specpack` from a file or folder.

```powershell
spectrum pack <input> <output.specpack> [--all] [--language <name>] [--rle off|auto|force] [--zlib-level 1-9] [--json]
```

Examples:

```powershell
spectrum pack ./src ./src.specpack --json
spectrum pack ./notes ./notes.specpack --language text --json
spectrum pack ./mixed ./mixed.specpack --all --json
```

Use `--all` when you want to include text files whose extensions are not in the
default allowlist. Avoid binary files; Spectrum's current core path is for UTF-8
text and source files.

`--language` forces the tokenizer/language hint. In most folder workflows you
should omit it and let extension-based detection run.

`--rle` controls run-length encoding of token IDs:

| Value | Meaning |
|---|---|
| `off` | Default. Do not apply RLE. |
| `auto` | Apply RLE when the encoder judges it beneficial. |
| `force` | Force RLE. Useful for experiments, not always smaller. |

### `verify`

Verify a `.spec`, a directory of `.spec` files, or a `.specpack`.

```powershell
spectrum verify ./docs.specpack --json
```

JSON output shape:

```json
{
  "valid": true,
  "chunks_checked": 12,
  "decode_passed": 12,
  "decode_failed": 0,
  "failures": []
}
```

Use the process exit code in automation. A failed verification returns a nonzero
exit code.

### `inspect`

Inspect `.spec` or `.specpack` metadata.

```powershell
spectrum inspect ./docs.specpack --json
spectrum info ./docs.specpack --json
```

Pack output includes path, format, version, dictionary version, entry count,
original bytes, encoded bytes, pack bytes, compression ratio, and any missing
manifest entries.

### `index`

Build a retrieval index for a `.spec`, `.spec` directory, or `.specpack`.

```powershell
spectrum index <input> [-o <index-path>] [--embed] [--json]
```

Common pack workflow:

```powershell
spectrum index ./docs.specpack --embed --json
```

Sidecar workflow:

```powershell
spectrum index ./docs.specpack --output ./docs.index.bin --json
```

When `--embed` is used with a pack, the index is stored as `index.bin` inside
the `.specpack`.

### `search`

Search a `.specpack`.

```powershell
spectrum search <pack.specpack> <query> [--top <n>] [--language <name>] [--index <index-path>] [--no-build] [--json]
```

Examples:

```powershell
spectrum search ./docs.specpack "authentication bearer middleware" --top 5 --json
spectrum search ./docs.specpack "def validate_token" --language py --top 3 --json
spectrum search ./docs.specpack "invoice export" --index ./docs.index.bin --json
```

The default query language is `txt`, which is appropriate for natural-language
queries over mixed code/prose corpora. The current query engine accepts
language hints such as `py`, `js`, `css`, or `html` when the query itself is
code-heavy.

Result objects include:

```json
{
  "rank": 1,
  "doc_id": 0,
  "name": "auth.md.spec",
  "path": "files/auth.md.spec",
  "source_path": "auth.md",
  "language": "Text",
  "score": 1.2345,
  "token_count": 42,
  "orig_length": 128,
  "matched_tokens": ["authentication", "middleware"]
}
```

Use `source_path` as the human-facing document path. `path` is the internal
`.spec` member path.

`--no-build` makes search fail if no embedded or supplied index is available.
That is useful in production to avoid surprise indexing work on the request
path.

### `unpack`

Decode a `.specpack` to a folder.

```powershell
spectrum unpack ./docs.specpack ./docs-restored --json
spectrum decode-pack ./docs.specpack ./docs-restored --json
```

The decoded folder should match the original source bytes if verification
passes.

### `encode` And `decode`

Work with one `.spec` file.

```powershell
spectrum encode ./src/app.py ./out/app.py.spec --json
spectrum inspect ./out/app.py.spec --json
spectrum decode ./out/app.py.spec ./restored/app.py --json
```

Use these commands for low-level format testing. For RAG and application
storage, `.specpack` is usually the better unit.

### CLI RAG Workflow

For a local RAG corpus:

```powershell
spectrum pack ./knowledge ./knowledge.specpack --json
spectrum verify ./knowledge.specpack --json
spectrum index ./knowledge.specpack --embed --json
spectrum search ./knowledge.specpack "how do we rotate api keys" --top 8 --json
```

Then hydrate the selected source:

```powershell
spectrum unpack ./knowledge.specpack ./knowledge-hydrated --json
```

For small packs this is enough. For server-backed apps, register the pack with
the HTTP API and use the document endpoint for source-path reads.

### Legacy Demo, Benchmark, And GUI CLI

Some demo, benchmark, and GUI commands still live in the older `CLI Tool`
package while the ecosystem packages are being split out.

Install that CLI only when you need those commands:

```powershell
cd "CLI Tool"
npm install -g . --force
```

Useful legacy commands:

```powershell
spectrum demo
spectrum demo --repo https://github.com/vladmandic/human --max-files 0 --query "model loading" --clean
spectrum benchmark ./docs.specpack
spectrum gui --open
```

The modern root preview CLI is the one to use for package/API integration
documentation. The legacy CLI remains useful for demos and benchmarks until
those surfaces move under `packages/`.

## Python SDK Manual

The Python SDK package name is `spectrum-ai`. Its import name is `spectrum`.

```python
from spectrum import Document, SpectrumPack
```

### Create A Pack From A Folder

```python
from spectrum import SpectrumPack

pack = SpectrumPack.create(
    input_path="./docs",
    output_path="./docs.specpack",
)

print(pack.inspect())
print(pack.verify())
```

Options:

```python
pack = SpectrumPack.create(
    input_path="./docs",
    output_path="./docs.specpack",
    include_all=False,
    language=None,
    rle="off",
    zlib_level=9,
)
```

### Open An Existing Pack

```python
pack = SpectrumPack.open("./docs.specpack")
print(pack.entries)
```

`entries` returns dictionaries copied from the pack manifest. Each entry has:

- `source`: original source path inside the corpus,
- `spec`: internal `.spec` member path,
- `original_size`: original byte length,
- `spec_size`: encoded byte length.

### Create A Pack From In-Memory Documents

```python
from spectrum import Document, SpectrumPack

pack = SpectrumPack.from_documents(
    [
        Document(
            id="runbook",
            path="ops/api-key-rotation.md",
            content="Rotate API keys every 90 days.\n",
            metadata={"source": "internal-runbook"},
        ),
        Document(
            id="auth",
            path="code/auth.md",
            content=b"Authentication middleware validates bearer tokens.\n",
        ),
    ],
    "./knowledge.specpack",
)
```

Current behavior:

- `path` becomes the path stored in the pack.
- `content` can be `str` or `bytes`.
- `metadata` is accepted so callers can keep a stable document object shape,
  but arbitrary metadata is not yet persisted in the core manifest.
- Absolute paths and `..` path traversal are rejected.
- At least one document is required.

### Build An Index And Search

```python
pack = SpectrumPack.open("./knowledge.specpack")
index_summary = pack.build_index(embed=True)
results = pack.search("authentication bearer middleware", top_k=5)

for result in results:
    print(result["rank"], result["source_path"], result["score"])
```

`build_index()` options:

```python
pack.build_index(embed=True, output_path=None)
```

`search()` options:

```python
pack.search("query text", top_k=10, language="txt")
```

### Unpack And Read Content

```python
decoded = pack.unpack("./decoded")

for document in decoded:
    print(document.path)
    print(document.content)
```

Decoded documents contain:

- `path`: source path from the pack,
- `content`: UTF-8 text decoded with replacement for invalid bytes,
- `content_bytes`: exact bytes written by the decoder.

`extract_to(output_dir)` clears and recreates the target directory before
unpacking:

```python
pack.extract_to("./fresh-decoded-copy")
```

### Python RAG Example

This example keeps the flow explicit. It builds the pack, searches it, then
loads only the source paths that were selected by search.

```python
from pathlib import Path
from spectrum import Document, SpectrumPack

documents = [
    Document(
        id="auth",
        path="auth.md",
        content="Authentication middleware validates bearer tokens.\n",
    ),
    Document(
        id="billing",
        path="billing.md",
        content="Invoices and payment receipts are exported nightly.\n",
    ),
]

pack = SpectrumPack.from_documents(documents, "./app-memory.specpack")
pack.build_index(embed=True)

results = pack.search("how are bearer tokens validated", top_k=3)
selected_paths = {result["source_path"] for result in results}

decoded_dir = Path("./app-memory-decoded")
decoded = pack.unpack(decoded_dir)
context_blocks = [
    f"### {doc.path}\n{doc.content}"
    for doc in decoded
    if doc.path in selected_paths
]

rag_context = "\n\n".join(context_blocks)
print(rag_context)
```

For larger packs, prefer the HTTP API pattern so your application can keep the
pack registered and fetch source paths through a service boundary.

### Python SDK Errors

Common exceptions:

- `FileNotFoundError`: source pack or input path does not exist.
- `ValueError("at least one document is required")`: empty document iterable.
- `ValueError("unsafe document path")`: absolute or parent-traversing document
  path.
- `ValueError("decoded document failed verification")`: checksum or length
  mismatch during unpack.

## JavaScript SDK Manual

The JavaScript SDK package name is `@spectrumstore/sdk`.

```js
import { SpectrumPack } from "@spectrumstore/sdk";
```

The current JS SDK shells out to the Spectrum CLI/core command and parses JSON.
It is not a native JavaScript encoder yet. By default it runs `spectrum-core`,
which is the Python console script installed by `packages/cli`.

### Create, Verify, Index, Search, Unpack

```js
import { SpectrumPack } from "@spectrumstore/sdk";

const pack = await SpectrumPack.create({
  inputPath: "./docs",
  outputPath: "./docs.specpack",
});

console.log(await pack.inspect());
console.log(await pack.verify());

await pack.buildIndex({ embed: true });
const results = await pack.search("authentication middleware", { topK: 5 });
console.log(results);

await pack.unpack("./decoded");
```

### Local Checkout Command Override

When developing from this repository without installing the Python console
script, pass an SDK command override:

```js
import { delimiter, join } from "node:path";
import { SpectrumPack } from "@spectrumstore/sdk";

const repoRoot = process.cwd();

const sdkOptions = {
  command: "python",
  baseArgs: ["-m", "spectrum_cli.main"],
  env: {
    ...process.env,
    PYTHONPATH: [
      join(repoRoot, "packages/core/src"),
      join(repoRoot, "packages/index/src"),
      join(repoRoot, "packages/cli/src"),
    ].join(delimiter),
    SPECTRUM_REPO_ROOT: repoRoot,
  },
};

const pack = await SpectrumPack.create(
  { inputPath: "./docs", outputPath: "./docs.specpack" },
  sdkOptions,
);
```

You can also set `SPECTRUM_COMMAND` in the environment to change the command
used by default.

### JS API Reference

Constructor and open:

```js
const pack = new SpectrumPack("./docs.specpack", sdkOptions);
const samePack = SpectrumPack.open("./docs.specpack", sdkOptions);
```

Create:

```js
await SpectrumPack.create({
  inputPath: "./docs",
  outputPath: "./docs.specpack",
  includeAll: false,
  language: undefined,
  rle: "off",
  zlibLevel: 9,
}, sdkOptions);
```

Methods:

```js
await pack.inspect();
await pack.verify();
await pack.buildIndex({ embed: true, outputPath: undefined });
await pack.search("query", {
  topK: 10,
  language: "txt",
  indexPath: undefined,
  buildIfMissing: true,
});
await pack.unpack("./decoded");
```

### JS RAG Example

```js
import { readFile } from "node:fs/promises";
import { join } from "node:path";
import { SpectrumPack } from "@spectrumstore/sdk";

const pack = SpectrumPack.open("./knowledge.specpack");
await pack.buildIndex({ embed: true });

const results = await pack.search("where is api key rotation documented", {
  topK: 4,
  language: "txt",
});

await pack.unpack("./knowledge-decoded");

const context = [];
for (const result of results) {
  const sourcePath = result.source_path;
  const text = await readFile(join("./knowledge-decoded", sourcePath), "utf8");
  context.push(`### ${sourcePath}\n${text}`);
}

console.log(context.join("\n\n"));
```

For a server application, avoid unpacking per request. Build and verify the pack
ahead of time, register it with `spectrum-server`, then call the HTTP search and
document endpoints from Node.

## Core Python API

Use `spectrum_core` when you want direct access to the format and pack layer
without the higher-level SDK wrapper.

```python
from spectrum_core import (
    SpectrumPack,
    decode_file,
    encode_file,
    inspect_pack,
    inspect_spec,
    pack,
    unpack,
    verify_pack,
    verify_path,
    verify_spec,
)
```

### Encode And Decode One File

```python
encoded = encode_file(
    "./src/app.py",
    "./encoded/app.py.spec",
    language=None,
    rle="off",
    zlib_level=9,
)

info = inspect_spec("./encoded/app.py.spec")
decoded = decode_file("./encoded/app.py.spec", "./restored/app.py")

assert decoded.ok
```

`EncodeResult` fields:

- `source_path`
- `output_path`
- `original_size`
- `spec_size`
- `token_count`
- `ratio`
- `dict_version`
- `rle_mode`

`DecodeResult` fields:

- `spec_path`
- `output_path`
- `dict_version`
- `original_length`
- `decoded_length`
- `token_count`
- `length_ok`
- `checksum_ok`
- `ok` property

`SpecInfo` fields:

- `path`
- `bytes`
- `dict_version`
- `language_id`
- `language`
- `original_bytes`
- `checksum`
- `rle`
- `ratio`

### Pack And Unpack

```python
summary = pack("./docs", "./docs.specpack", include_all=False)
print(summary["entries"])

report = verify_pack("./docs.specpack")
assert report.valid

results = unpack("./docs.specpack", "./decoded")
assert all(result.ok for result in results)
```

`pack()` options:

```python
pack(
    input_path,
    output_path,
    include_all=False,
    language=None,
    rle="off",
    zlib_level=9,
    verbose=False,
)
```

`inspect_pack()` returns a dictionary containing:

- `path`
- `format`
- `version`
- `dict_version`
- `source_root`
- `entries`
- `original_size`
- `spec_size`
- `pack_size`
- `ratio`
- `missing_entries`

### Read A Pack Manifest And Specs

```python
from spectrum_core import SpectrumPack

with SpectrumPack.open("./docs.specpack") as opened:
    for entry in opened.entries:
        print(entry.source, entry.spec, entry.original_size, entry.spec_size)
        raw_spec = opened.read_spec(entry)
```

`SpectrumPack.extract_specs(output_dir)` extracts encoded `.spec` members, not
decoded source files. Use `unpack()` when you need source text.

### Validation API

```python
from spectrum_core import verify_path

report = verify_path("./docs.specpack")
print(report.to_dict())
```

`verify_path()` dispatches based on input:

- `.specpack` -> verify every entry in the pack,
- directory -> verify all `*.spec` files under the directory,
- file -> verify one `.spec`.

## Index Python API

Use `spectrum_index` when you want retrieval without going through the SDK.

```python
from spectrum_index import (
    build_index,
    build_pack_index,
    load_index,
    search_index,
    search_pack,
)
```

### Build And Search A Pack

```python
summary = build_pack_index("./docs.specpack", embed=True)
results = search_pack("./docs.specpack", "authentication middleware", top_k=5)
```

### Build A Sidecar Index

```python
summary = build_pack_index(
    "./docs.specpack",
    output_path="./docs.index.bin",
    embed=False,
)

results = search_pack(
    "./docs.specpack",
    "authentication middleware",
    index_path="./docs.index.bin",
    top_k=5,
)
```

### Search A Loaded Index

```python
index = load_index("./docs.index.bin")
results = search_index(index, "authentication middleware", top_k=5)
```

### Index Function Reference

```python
build_index(target, output_path=None, embed=False, verbose=False)
build_pack_index(pack_path, output_path=None, embed=False, verbose=False)
load_index(path)
search_index(index_or_path, query, top_k=10, language="txt")
search_pack(pack_path, query, top_k=10, language="txt", index_path=None, build_if_missing=True)
```

`build_index()` accepts a `.spec`, a directory of `.spec` files, or a
`.specpack`. `search_pack()` uses an explicitly supplied index first, then an
embedded `index.bin`, then a temporary index if `build_if_missing=True`.

## HTTP API Manual

The HTTP API is implemented by `packages/server`. It is intended for local
applications that want a stable process boundary around Spectrum packs.

It currently uses Python's standard-library `ThreadingHTTPServer`, keeps pack
registrations in memory, and has no authentication layer. Bind it to
`127.0.0.1` unless you have added your own network and auth controls.

### Start The Server

From a local checkout:

```powershell
$env:PYTHONPATH = "packages/core/src;packages/index/src;packages/server/src"
$env:SPECTRUM_REPO_ROOT = (Get-Location).Path
python -m spectrum_server.main --pack docs=./docs.specpack --port 7777
```

After editable install:

```powershell
spectrum-server --pack docs=./docs.specpack --port 7777
```

Options:

```text
--host 127.0.0.1
--port 7777
--pack id=path
--pack path
--quiet
```

If `--pack` is passed without `id=`, the server assigns IDs like `pack-1`.

### Endpoint Reference

| Method | Path | Body | Purpose |
|---|---|---|---|
| `GET` | `/health` | none | Health and server version. |
| `GET` | `/packs` | none | List registered packs. |
| `POST` | `/packs` | `{"id":"docs","path":"./docs.specpack"}` | Register a local pack. |
| `GET` | `/packs/{pack_id}` | none | Inspect a registered pack. |
| `DELETE` | `/packs/{pack_id}` | none | Remove a pack from the in-memory registry. |
| `POST` | `/packs/{pack_id}/verify` | none | Verify pack decode fidelity. |
| `POST` | `/packs/{pack_id}/index` | `{"embed":true,"output_path":null}` | Build an index. |
| `POST` | `/packs/{pack_id}/search` | `{"query":"...","top_k":5}` | Search a pack. |
| `GET` | `/packs/{pack_id}/documents/{source_path}` | none | Read one decoded document by source path. |
| `POST` | `/packs/{pack_id}/unpack` | `{"output_dir":"./decoded"}` | Decode all documents to a folder. |

### Request Examples

Health:

```powershell
Invoke-RestMethod http://127.0.0.1:7777/health
```

Register a pack:

```powershell
Invoke-RestMethod `
  -Method Post `
  -Uri http://127.0.0.1:7777/packs `
  -ContentType "application/json" `
  -Body '{"id":"docs","path":"./docs.specpack"}'
```

Inspect:

```powershell
Invoke-RestMethod http://127.0.0.1:7777/packs/docs
```

Verify:

```powershell
Invoke-RestMethod `
  -Method Post `
  -Uri http://127.0.0.1:7777/packs/docs/verify
```

Build an embedded index:

```powershell
Invoke-RestMethod `
  -Method Post `
  -Uri http://127.0.0.1:7777/packs/docs/index `
  -ContentType "application/json" `
  -Body '{"embed":true}'
```

Search:

```powershell
Invoke-RestMethod `
  -Method Post `
  -Uri http://127.0.0.1:7777/packs/docs/search `
  -ContentType "application/json" `
  -Body '{"query":"authentication bearer middleware","top_k":5,"language":"txt"}'
```

Read a decoded document:

```powershell
Invoke-RestMethod http://127.0.0.1:7777/packs/docs/documents/auth.md
```

For nested paths, URL-encode path separators or use a client that preserves the
path segment you intend to send:

```text
GET /packs/docs/documents/src%2Fauth%2Fmiddleware.py
```

Unpack all documents:

```powershell
Invoke-RestMethod `
  -Method Post `
  -Uri http://127.0.0.1:7777/packs/docs/unpack `
  -ContentType "application/json" `
  -Body '{"output_dir":"./decoded"}'
```

### HTTP Response Shapes

Errors return JSON:

```json
{
  "error": "unknown pack: docs"
}
```

Search returns:

```json
{
  "results": [
    {
      "rank": 1,
      "doc_id": 0,
      "name": "auth.md.spec",
      "path": "files/auth.md.spec",
      "source_path": "auth.md",
      "language": "Text",
      "score": 1.2345,
      "token_count": 42,
      "orig_length": 128,
      "matched_tokens": ["authentication", "middleware"]
    }
  ]
}
```

Document reads return:

```json
{
  "path": "auth.md",
  "content": "Authentication middleware validates bearer tokens.\n",
  "content_bytes": [65, 117, 116, 104]
}
```

`content` is decoded as UTF-8 with replacement for invalid bytes. Use
`content_bytes` when exact byte handling matters.

## RAG Playbooks

### Playbook 1: Local Knowledge Base

Use this when you have Markdown, text, source files, or configuration files and
want a local retrieval store.

1. Put the corpus in one folder.
2. Create a pack:

   ```powershell
   spectrum pack ./knowledge ./knowledge.specpack --json
   ```

3. Verify lossless decode:

   ```powershell
   spectrum verify ./knowledge.specpack --json
   ```

4. Embed the retrieval index:

   ```powershell
   spectrum index ./knowledge.specpack --embed --json
   ```

5. Search:

   ```powershell
   spectrum search ./knowledge.specpack "deployment rollback procedure" --top 8 --json
   ```

6. Hydrate only the chosen documents for the model context.

### Playbook 2: Application-Embedded Python RAG

Use the SDK when your app is Python-native and can call Spectrum in-process.

```python
from spectrum import SpectrumPack

pack = SpectrumPack.open("./knowledge.specpack")
pack.build_index(embed=True)

def retrieve_context(query: str, top_k: int = 5) -> str:
    results = pack.search(query, top_k=top_k)
    wanted = {result["source_path"] for result in results}
    decoded = pack.unpack("./_decoded_cache")
    blocks = [
        f"### {doc.path}\n{doc.content}"
        for doc in decoded
        if doc.path in wanted
    ]
    return "\n\n".join(blocks)
```

For production-sized packs, build the pack and index offline, then use the HTTP
API or add an application-level decoded-document cache.

### Playbook 3: Node Or Web Service RAG

Use the JS SDK for build-time pack management, or use the HTTP server for
runtime search.

Build once:

```js
const pack = await SpectrumPack.create({
  inputPath: "./knowledge",
  outputPath: "./knowledge.specpack",
});
await pack.verify();
await pack.buildIndex({ embed: true });
```

Serve runtime search:

```powershell
spectrum-server --pack knowledge=./knowledge.specpack --port 7777
```

Then call:

```text
POST /packs/knowledge/search
GET  /packs/knowledge/documents/{source_path}
```

### Playbook 4: Code Search

For source repositories, use natural-language queries first and code-language
hints when the query is itself code.

```powershell
spectrum pack ./repo ./repo.specpack --json
spectrum index ./repo.specpack --embed --json
spectrum search ./repo.specpack "where websocket messages are parsed" --top 10 --json
spectrum search ./repo.specpack "function parseMessage" --language js --top 10 --json
```

Search results include matched tokens and source paths, so UIs can show why a
file matched before hydrating it.

### Playbook 5: Lossless Archive Or Transport

If search is secondary and storage/transport is primary:

```powershell
spectrum pack ./project ./project.specpack --json
spectrum verify ./project.specpack --json
```

Only build an index when you need retrieval:

```powershell
spectrum index ./project.specpack --embed --json
```

Restore:

```powershell
spectrum unpack ./project.specpack ./project-restored --json
```

## Integration Guidance

### Choosing A Surface

| Need | Use |
|---|---|
| Shell scripts, CI, local tools | `spectrum` CLI |
| Python application | `spectrum` Python SDK |
| JavaScript build/runtime tool | `@spectrumstore/sdk` |
| Service boundary for apps or agents | `spectrum-server` HTTP API |
| Format-level control | `spectrum_core` |
| Retrieval-only control | `spectrum_index` |
| Demo, benchmark, GUI exploration | Legacy `CLI Tool` package |

### Index Strategy

Embed `index.bin` when the pack is your deployable artifact. This gives you one
file to copy, cache, upload, or mount.

Use a sidecar index when:

- the pack must remain immutable,
- different deployments need different index profiles,
- you want to rebuild indexes independently of pack creation.

Use `--no-build` or `build_if_missing=False` on request paths where indexing
latency would be unacceptable.

### Update Strategy

The current pack builder is full-rebuild oriented. For changing corpora:

1. Rebuild the pack in a temporary output path.
2. Verify it.
3. Build or embed the index.
4. Atomically switch your application or server registry to the new path.

Incremental document updates are planned for the memory/connectors layer.

### Prompt Construction

For RAG, treat Spectrum search results as candidate selection. Construct model
context from decoded source only after ranking.

A typical prompt block should include source path and content:

```text
### docs/auth.md
Authentication middleware validates bearer tokens.

### src/auth/session.py
def validate_session(...):
    ...
```

Keep source paths in the prompt so downstream answers can cite or act on the
right file.

### Encoding And File Types

The current core path reads source bytes and decodes as UTF-8 with replacement
inside the encoder. It is designed for source code, markup, config, Markdown,
and prose. Do not use it as a binary asset archive.

Line endings are preserved on decode because the decoder writes bytes rather
than using platform newline translation.

## Troubleshooting

### `spectrum` Is Not Recognized

Install the root preview package:

```powershell
npm install -g . --force
```

Then check command resolution:

```powershell
where.exe spectrum
where.exe spectrumstore
node --version
```

### Python Cannot Be Found

The npm wrapper tries `py -3`, `python`, and `python3` on Windows, and
`python3`, `python`, and `py -3` elsewhere. Install Python 3.10+ and make sure
one of those commands is on `PATH`.

### `ModuleNotFoundError`

If running Python modules directly from the checkout, set `PYTHONPATH`:

```powershell
$env:PYTHONPATH = "packages/core/src;packages/index/src;packages/cli/src;packages/sdk-python;packages/server/src"
```

Or install packages in editable mode.

### `Could not locate the Spectrum repository root`

Set `SPECTRUM_REPO_ROOT` to the checkout containing `dictionary.py` and
`spec_format/`:

```powershell
$env:SPECTRUM_REPO_ROOT = "C:\Users\james\Documents\GitHub\Spectrum"
```

The root npm `spectrum` wrapper sets this automatically.

### `no encodable files found`

The input folder may only contain unsupported extensions or skipped directories.
Use `--all` for UTF-8 text-like files with custom extensions:

```powershell
spectrum pack ./corpus ./corpus.specpack --all --json
```

### Search Is Empty

Check:

- the pack has documents: `spectrum inspect ./pack.specpack --json`,
- the index exists: `spectrum index ./pack.specpack --embed --json`,
- the query language is sensible: start with `--language txt`,
- the query terms exist in the corpus,
- `--no-build` is not blocking index creation during development.

### Server Returns `unknown pack`

Register the pack first:

```powershell
Invoke-RestMethod `
  -Method Post `
  -Uri http://127.0.0.1:7777/packs `
  -ContentType "application/json" `
  -Body '{"id":"docs","path":"./docs.specpack"}'
```

Pack registrations are in memory and are lost when the server process exits.
Use `--pack docs=./docs.specpack` on startup for repeatable local runs.

### Document Endpoint Cannot Find Nested Paths

URL-encode nested source paths:

```text
/packs/docs/documents/src%2Fauth%2Fmiddleware.py
```

### JSON Automation

Use `--json` for CLI automation. Commands return nonzero status on decode,
verify, file, value, and OS errors.

## Current Gaps And Stability Notes

- Spectrum is still pre-1.0. Treat public APIs as developer-preview APIs.
- The dictionary and tokenization coverage should be expanded before making
  format/API stability claims.
- The JavaScript SDK shells out to the Python CLI/core command; it is not a
  native JS codec.
- The Python SDK accepts document metadata but does not yet persist arbitrary
  metadata into the core pack manifest.
- The server has no authentication and should be kept local unless wrapped by
  another trusted service layer.
- Server pack registration is in memory.
- SDK-level selective hydration is still limited. Current simple SDK examples
  may unpack a whole pack and filter selected documents.
- Connector, memory, dashboard, cloud, LangChain, and LlamaIndex packages are
  currently package boundaries or placeholders rather than full integrations.
- Demo, benchmark, and GUI commands still live in the legacy `CLI Tool`
  package.

## Minimal End-To-End Checklist

For a developer getting started with Spectrum:

1. Install Python 3.10+ and Node.js 18+.
2. From the repo root, run `npm install -g . --force`.
3. Run `spectrum pack ./docs ./docs.specpack --json`.
4. Run `spectrum verify ./docs.specpack --json`.
5. Run `spectrum index ./docs.specpack --embed --json`.
6. Run `spectrum search ./docs.specpack "your query" --top 5 --json`.
7. Use Python SDK, JS SDK, or HTTP API depending on your application boundary.
8. Decode only the selected documents you need for display, model context, or
   downstream processing.
