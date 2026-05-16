# Spectrum Store CLI

CLI owns the developer-facing Spectrum Store preview commands: `doctor`,
`pack`, `append`, `project`, `search`, `decode`, `verify`, `inspect`, `index`,
`serve`, and `unpack`.

The first ecosystem CLI package wraps `spectrum_core` for local format workflows:

- `encode` - encode one file to `.spec`.
- `decode` - decode one `.spec` file.
- `pack` - create a `.specpack` from a file or folder.
- `append` - add files or a folder to an existing `.specpack`.
- `project` - initialize, append to, and serve portable project packs.
- `unpack` - decode a `.specpack`.
- `inspect` - inspect `.spec` or `.specpack` metadata.
- `verify` - verify `.spec`, `.spec` directory, or `.specpack` fidelity.
- `index` - build a retrieval index.
- `search` - search a `.specpack`.
- `serve` - run the local HTTP API for a `.specpack`.
- `doctor` - check the local install, Python runtime, imports, bundled runtime,
  and temporary write access.

Example:

```powershell
npm install -g spectrumstore
spectrum doctor
spectrum pack ./docs ./docs.specpack --json
spectrum append ./docs.specpack ./project-notes --json
spectrum verify ./docs.specpack --json
spectrum index ./docs.specpack --embed --json
spectrum search ./docs.specpack "authentication middleware" --json
```

Portable project workflow:

```powershell
spectrum project init ./my-project ./my-project.specpack --name "My Project"
spectrum project add ./my-project.specpack ./new-notes
spectrum project serve ./my-project.specpack --port 7777
```

If an appended source path already exists, `append` fails unless `--replace` is
passed. Appending removes embedded `index.bin` so searches do not silently use a
stale index; rebuild it with `spectrum index ./docs.specpack --embed`.

Benchmark and dashboard commands remain in the legacy CLI until the
corresponding ecosystem packages are moved under `packages/`.
