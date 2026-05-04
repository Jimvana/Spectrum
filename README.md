# Spectrum CLI

`spec` is the public command line interface for Spectrum `.spec` files and `.specpack` archives. It can encode source trees, decode them back to files, embed a searchable sparse retrieval index, and run a local benchmark against raw text plus BM25.

The package currently ships as a small Node executable that launches the Python Spectrum engine vendored in this repository. Node is used for npm distribution; Python performs the codec, indexing, search, and benchmark work.

## Install

```bash
npm install -g @jimvana/spectrum
spec --help
```

For local development:

```bash
git clone https://github.com/Jimvana/Spectrum.git
cd Spectrum
npm install
npm test
npm link
spec --version
```

## Requirements

- Node.js 18 or newer
- Python 3.10 or newer available as `python3` or `python`

There are no npm runtime dependencies.

## Usage

```bash
spec encode ./docs -a --index
spec info ./docs.specpack
spec search "oauth callback handler" ./docs.specpack
spec decode ./docs.specpack -o ./docs-restored
spec verify ./docs.specpack
spec benchmark ./docs.specpack
```

### Commands

| Command | Purpose |
| --- | --- |
| `encode` | Encode one file, a directory, or a `.specpack` archive. |
| `decode` | Restore `.spec`, `.specdir`, or `.specpack` content back to source files. |
| `index` | Build a search index. Archives embed the index by default; loose files use sidecar indexes. |
| `search` | Search an existing index or a `.specpack`; missing or stale pack indexes are rebuilt automatically. |
| `info` | Inspect metadata, sizes, language, checksum, and index state. |
| `verify` | Decode into a temporary location and validate length/checksum fidelity. |
| `benchmark` | Compare Spectrum archive plus BM25 against raw text plus BM25. |

## Examples

Encode a project as one searchable archive:

```bash
spec encode ./project -a --index -o project.specpack
spec search "database migration rollback" project.specpack
```

Encode all files, not only recognised source/text extensions:

```bash
spec encode ./notes -a --all --index
```

Build or rebuild an index later:

```bash
spec index project.specpack
```

Write benchmark artifacts:

```bash
spec benchmark ./project --clean -o ./spec-benchmark
```

The benchmark writes `report.md`, `report.json`, `queries.json`, and a raw BM25 baseline store.

## Development

```bash
npm test
node ./bin/spec.js --help
```

The smoke tests exercise the npm executable, encode/decode fidelity, packed indexing, and search.

## Language Tokens

Spec can compress any text corpus, while keeping specific languages defined by their own tokens.

Right now in dictionary v12, Spectrum covers:

Python,
HTML,
JavaScript,
CSS,
Plain text / Markdown,
TypeScript / TSX,
SQL,
Rust,
PHP,
XML / Wiki-style markup,
Java,
C,
C++,
Go,
C#,
Shell scripts,
JSON,
YAML,
TOML,
English word tokens,

## Repository Layout

```text
bin/spec.js              Node executable shim
spectrum_cli/main.py     CLI command implementation
vendor/spectrum_algo/    Vendored Spectrum codec, tokenizers, spec format, and retrieval code
tests/                   Node smoke tests for the public package
```

## Release Checklist

1. Update `VERSION` in `spectrum_cli/main.py`.
2. Update `version` in `package.json`.
3. Run `npm test`.
4. Run `npm pack --dry-run` and inspect the file list.
5. Publish with `npm publish --access public`.

## License

Spectrum is available under the PolyForm Noncommercial License 1.0.0.
Commercial use requires a separate commercial license.

See [LICENSE](LICENSE) and [NOTICE](NOTICE).

## Status

This is the public CLI surface for Spectrum while the codec runtime is still packaged inside the repo. The public API is the `spec` command; internal Python module paths should be treated as implementation details.
