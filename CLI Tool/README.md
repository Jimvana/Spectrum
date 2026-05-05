# Spectrum CLI

Experimental command line wrapper for Spectrum `.spec` files.

## Install Or Update

From the repository checkout:

```powershell
cd "C:\Users\james\Documents\GitHub\Spectrum\CLI Tool"
npm install -g . --force
```

`--force` lets npm replace an older global `spec` shim when updating from a
previous local install.

Verify the install:

```powershell
spectrum --version
spectrum demo --help
```

On Windows, if command resolution is confusing, inspect the real executable
paths with:

```powershell
where.exe spectrum
where.exe spec
where.exe py
where.exe python
```

Use `spectrum` for new docs and demos. `spec` remains available as a
backwards-compatible alias.

## Commands

```bash
spectrum demo
spectrum encode ./docs -a
spectrum encode ./docs -a --index
spectrum decode ./docs.specpack
spectrum index ./docs.specpack
spectrum search "query" ./docs.specpack
spectrum benchmark ./docs.specpack
spectrum gui
```

`.specpack` archives store their search index inside the pack by default. If a
pack has no embedded index yet, `spec search "query" ./docs.specpack` builds and
embeds one automatically. Loose `.spec` files and `.specdir` folders use sidecar
indexes.

Search uses a universal retrieval layer over the encoded files: it indexes
words, simple English aliases, identifiers, strings, comments, and path terms
across code and prose instead of making users choose a code-vs-text mode.

`spec benchmark` compares Spectrum against a raw text + BM25 baseline and writes
`report.md`, `report.json`, `queries.json`, and the raw baseline store.

`spectrum demo` (also available as `spec demo`) starts a guided bring-your-own
repo flow. It asks for a Git URL or local path, chooses a local workspace and
report directory, runs the codebase benchmark, verifies lossless Spectrum
decoding, and optionally previews free-form searches against the built Spectrum
store.

Scriptable demo runs are supported too:

```powershell
spectrum demo `
  --repo https://github.com/vladmandic/human `
  --max-files 0 `
  --query "face detection pipeline" `
  --query "model loading" `
  --clean
```

`spec gui` starts a local browser UI for loading a folder or `.specpack`,
running side-by-side Spectrum vs raw BM25 vs embedding/vector searches, and
launching the same generated-query benchmark from a page instead of the
terminal.

For benchmark folders that contain `spectrum_spec/postings_v2.bin`, the GUI
uses SPB2 automatically and falls back to `postings.bin` for older stores. The
Spectrum Pack size card reports the effective loaded store size: `.spec`
payloads plus docs/metadata plus the selected postings file.

Convenience scripts are available for the local GUI server:

```bash
"CLI Tool/gui/start_server.sh"
"CLI Tool/gui/stop_server.sh"
```

The start script opens `http://127.0.0.1:8765`, writes `.server.pid`, and logs
to `CLI Tool/gui/server.log`. The stop script stops the recorded process and any
server listening on the configured GUI port.

The current package is a thin Node executable that calls the Python Spectrum
engine in this repository. It is intended as the CLI surface for the project
before the codec is packaged as a standalone runtime.
