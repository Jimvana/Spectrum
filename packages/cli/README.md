# Spectrum CLI

CLI owns developer-facing commands such as `pack`, `search`, `decode`, `verify`, `bench`, `demo`, `inspect`, `server`, and `dashboard`.

The first ecosystem CLI package wraps `spectrum_core` for local format workflows:

- `encode` - encode one file to `.spec`.
- `decode` - decode one `.spec` file.
- `pack` - create a `.specpack` from a file or folder.
- `unpack` - decode a `.specpack`.
- `inspect` - inspect `.spec` or `.specpack` metadata.
- `verify` - verify `.spec`, `.spec` directory, or `.specpack` fidelity.

Example:

```powershell
$env:PYTHONPATH="packages/core/src;packages/cli/src"
python -m spectrum_cli.main pack ./docs ./docs.specpack --json
python -m spectrum_cli.main verify ./docs.specpack --json
```

Search, benchmark, server, and dashboard commands remain in the legacy CLI until
the corresponding ecosystem packages are moved under `packages/`.
