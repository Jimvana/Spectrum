# Changelog

## 0.1.0-preview.5 - 2026-05-17

### Added

- Spectrum Hub guided workflows for building, appending, serving, and verifying
  portable project packs.
- Project pack runtime launchers and default `.spectrum/project.specpack`
  output for `spectrum project init`.
- Local API endpoints for manifest discovery, document list/upsert/delete, ops
  data, readiness checks, hydrate URLs, and server shutdown.
- ByteSpectrum static site source and project API workflow documentation.

## 0.1.0-preview.1 - 2026-05-14

Initial Spectrum Store developer preview.

### Added

- npm CLI package named `spectrumstore`, exposing `spectrum` and
  `spectrumstore` commands.
- Local-first `.specpack` workflows: `pack`, `index`, `search`, `verify`,
  `inspect`, and `unpack`.
- `spectrum doctor` install health checks for Python, bundled runtime files,
  package imports, the npm wrapper, and temporary write access.
- Bundled Python Spectrum core, index, CLI, and current codec runtime so npm
  users do not need to set `PYTHONPATH` or `SPECTRUM_REPO_ROOT`.
- 5-minute quickstart and tiny auth-service sample codebase.
- Packed tarball smoke-test script for release and CI validation.

### Preview Notes

- Requires Node.js 18+ and Python 3.10+ on `PATH`.
- The CLI is the supported first install surface. SDKs, server, dashboard,
  memory, connectors, and integrations remain active ecosystem packages.
- The public `.specpack` format should still be treated as preview-stage until
  the dictionary and compatibility policy are locked for a stable release.
