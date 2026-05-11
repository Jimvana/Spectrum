# Spectrum Store CLI

CLI owns the developer-facing Spectrum Store preview commands: `pack`,
`search`, `decode`, `verify`, `inspect`, `index`, and `unpack`.

The first ecosystem CLI package wraps `spectrum_core` for local format workflows:

- `encode` - encode one file to `.spec`.
- `decode` - decode one `.spec` file.
- `pack` - create a `.specpack` from a file or folder.
- `unpack` - decode a `.specpack`.
- `inspect` - inspect `.spec` or `.specpack` metadata.
- `verify` - verify `.spec`, `.spec` directory, or `.specpack` fidelity.
- `index` - build a retrieval index.
- `search` - search a `.specpack`.

Example:

```powershell
npm install -g . --force
spectrum pack ./docs ./docs.specpack --json
spectrum verify ./docs.specpack --json
spectrum index ./docs.specpack --embed --json
spectrum search ./docs.specpack "authentication middleware" --json
```

Benchmark, server, and dashboard commands remain in the legacy CLI until the
corresponding ecosystem packages are moved under `packages/`.
