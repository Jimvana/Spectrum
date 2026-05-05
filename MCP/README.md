# Spectrum Spec MCP

MCP server for letting ChatGPT and other MCP clients inspect and decode Spectrum Algo `.spec` and `.specpack` files.

This server does not make `.spec` a native ChatGPT upload type. It exposes tools that ChatGPT can call. The tools decode `.spec` files with the Spectrum decoder in this repository, then return plain text and structured metadata.

## Tools

- `list_spec_files`: find `.spec` and `.specpack` files under an allowed root.
- `inspect_spec`: read `.spec` header metadata without decoding the full body.
- `read_spec`: decode one `.spec` file to text.
- `inspect_specpack`: read a `.specpack` manifest.
- `read_specpack_member`: decode one source file inside a `.specpack`.
- `search_specs`: plain-text search across decoded `.spec` and `.specpack` contents.

## Local Setup

From this folder:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e .
```

By default, the server only allows access to the parent Spectrum Algo repository. To expose a different folder, set `SPECTRUM_SPEC_ROOTS` to one or more absolute paths separated by your OS path separator:

```bash
export SPECTRUM_SPEC_ROOTS="/path/to/spec/files"
```

## Run For Local MCP Clients

```bash
spectrum-spec-mcp
```

That runs stdio transport, which is what most local MCP clients expect.

Equivalent:

```bash
python -m spectrum_spec_mcp.server --transport stdio
```

## Run For ChatGPT Connector Testing

ChatGPT needs a publicly reachable HTTPS MCP endpoint. For local development, run a streamable HTTP server and expose it with a tunnel such as ngrok or Cloudflare Tunnel.

```bash
SPECTRUM_MCP_HOST=127.0.0.1 SPECTRUM_MCP_PORT=8000 \
  python -m spectrum_spec_mcp.server --transport streamable-http
```

Then create a ChatGPT connector in developer mode using the public `/mcp` endpoint from your tunnel.

HTTP settings are controlled with environment variables:

- `SPECTRUM_MCP_HOST`, default `127.0.0.1`
- `SPECTRUM_MCP_PORT`, default `8000`
- `SPECTRUM_MCP_PATH`, default `/mcp`

## Quick Functional Test

After installing dependencies, run:

```bash
python - <<'PY'
from spectrum_spec_mcp.core import list_spec_files, read_spec

files = list_spec_files(limit=5)["files"]
print(files)
if files:
    print(read_spec(files[0], max_chars=500)["metadata"])
PY
```

## Notes For Lexi

- This package imports the decoder from the parent Spectrum Algo repo. Keep the `MCP` folder inside this repo, or set `PYTHONPATH` so Python can import `dictionary.py`, `spec_format`, and `tokenizers`.
- `read_spec` returns decoded text and fidelity metadata: `length_ok`, `checksum_ok`, `token_count`, dictionary version, language, and compression ratio.
- `search_specs` decodes files on demand. For very large archives, prefer `inspect_specpack` first, then call `read_specpack_member` for specific files.
