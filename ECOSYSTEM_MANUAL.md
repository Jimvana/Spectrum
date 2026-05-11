# Spectrum Ecosystem Manual

This manual covers the current ecosystem packages under `packages/`.

The implementation is still pre-1.0. The public API shape is taking form, but
the dictionary should be expanded before the core format is treated as stable.

## Package Map

- `packages/core` - `.spec` encode/decode, `.specpack` pack/unpack, inspection, verification.
- `packages/cli` - command line wrapper over `spectrum_core`.
- `packages/index` - retrieval indexes and BM25 search over Spectrum packs.
- `packages/sdk-python` - Python SDK for app developers.
- `packages/sdk-js` - JavaScript SDK backed by the CLI/core command.
- `packages/server` - local HTTP API over Spectrum packs.

## Local Development Setup

From the repo root:

```powershell
python scripts/test.py
```

Run only Python tests:

```powershell
python scripts/test.py --python-only
```

Run only JavaScript SDK tests:

```powershell
python scripts/test.py --js-only
```

The root `pyproject.toml` also configures package paths for pytest, so
`python -m pytest` works from the repo root without manually setting
`PYTHONPATH`.

## Core API

Import:

```python
from spectrum_core import (
    encode_file,
    decode_file,
    inspect_spec,
    pack,
    unpack,
    inspect_pack,
    verify_spec,
    verify_pack,
    verify_path,
    SpectrumPack,
)
```

Example:

```python
pack("./docs", "./docs.specpack")
print(inspect_pack("./docs.specpack"))
print(verify_pack("./docs.specpack").to_dict())
unpack("./docs.specpack", "./decoded")
```

Core preserves UTF-8 source bytes, including CRLF line endings.

## CLI

Run locally:

```powershell
python -m spectrum_cli.main pack ./docs ./docs.specpack --json
python -m spectrum_cli.main inspect ./docs.specpack --json
python -m spectrum_cli.main verify ./docs.specpack --json
python -m spectrum_cli.main index ./docs.specpack --embed --json
python -m spectrum_cli.main search ./docs.specpack "authentication middleware" --json
python -m spectrum_cli.main unpack ./docs.specpack ./decoded --json
```

Current commands:

- `encode <input> <output>`
- `decode <input> <output>`
- `pack <input> <output>`
- `unpack <input> <output>`
- `inspect <input>`
- `verify <input>`
- `index <input>`
- `search <pack> <query>`

Planned npm package name: `spectrumstore`, exposing `spectrum` and
`spectrumstore` commands once the bundled CLI is ready.

## Python SDK

Import:

```python
from spectrum import Document, SpectrumPack
```

Create from a folder:

```python
pack = SpectrumPack.create(
    input_path="./docs",
    output_path="./docs.specpack",
)

print(pack.inspect())
print(pack.verify())
pack.build_index()
print(pack.search("authentication middleware", top_k=5))
```

Create from in-memory documents:

```python
pack = SpectrumPack.from_documents(
    [
        Document(
            id="doc-1",
            path="notes/memory.md",
            content="Spectrum should stay local-first.\n",
        )
    ],
    "./memory.specpack",
)
```

Decode:

```python
decoded = pack.unpack("./decoded")
print(decoded[0].content)
```

## JavaScript SDK

Import:

```js
import { SpectrumPack } from "@spectrumstore/sdk";
```

Example:

```js
const pack = await SpectrumPack.create({
  inputPath: "./docs",
  outputPath: "./docs.specpack",
});

console.log(await pack.inspect());
console.log(await pack.verify());
await pack.buildIndex();
console.log(await pack.search("authentication middleware", { topK: 5 }));
await pack.unpack("./decoded");
```

During local development, point it at the Python CLI:

```js
const sdkOptions = {
  command: "python",
  baseArgs: ["-m", "spectrum_cli.main"],
  env: {
    ...process.env,
    PYTHONPATH: "packages/core/src;packages/cli/src;packages/index/src",
  },
};
```

## Server

Run:

```powershell
python -m spectrum_server.main --pack docs=./docs.specpack --port 7777
```

Endpoints:

- `GET /health`
- `GET /packs`
- `POST /packs` with `{"id": "docs", "path": "./docs.specpack"}`
- `GET /packs/{pack_id}`
- `DELETE /packs/{pack_id}`
- `POST /packs/{pack_id}/verify`
- `POST /packs/{pack_id}/index` with `{"embed": true}`
- `POST /packs/{pack_id}/search` with `{"query": "authentication middleware", "top_k": 5}`
- `POST /packs/{pack_id}/unpack` with `{"output_dir": "./decoded"}`

Example:

```powershell
Invoke-RestMethod http://127.0.0.1:7777/health
Invoke-RestMethod http://127.0.0.1:7777/packs/docs
```

## Current Gaps

- Dictionary expansion should happen before format/API stability claims.
- Benchmark commands remain in the legacy CLI for now.
- JS SDK currently shells out to the CLI/core command; it is not a native JS
  encoder.
- Server currently covers pack lifecycle, inspection, verify, index, search, and
  unpack. Ingestion, memory, and benchmark endpoints come later.
