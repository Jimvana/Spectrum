# Spectrum Server

Server owns the local-first HTTP API for pack management, ingestion, search, decode, verification, benchmarking, and memory endpoints.

The first server package is dependency-light and uses Python's standard library
HTTP server over `spectrum_core`.

Run locally:

```powershell
$env:PYTHONPATH="packages/core/src;packages/server/src"
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

Document ingestion, memory, and benchmark endpoints will be added after the
remaining packages are split out.
