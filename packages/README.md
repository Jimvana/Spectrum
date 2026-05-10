# Spectrum Packages

This directory is the home for the Spectrum ecosystem packages.

Each ecosystem element has its own subdirectory so implementation can grow without mixing concerns:

- `core/` - format, encoder, decoder, pack IO, validation.
- `cli/` - command line workflows and report generation.
- `sdk-js/` - TypeScript/JavaScript SDK.
- `sdk-python/` - Python SDK.
- `server/` - local-first HTTP API.
- `dashboard/` - local dashboard UI.
- `memory/` - source-linked agent memory layer.
- `index/` - retrieval/indexing layer.
- `connectors/` - data import connectors.
- `integrations/` - framework adapters.
- `cloud/` - optional hosted/team service experiments.

Existing prototype code remains in the current top-level folders until it is intentionally migrated.
