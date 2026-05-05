"""MCP server exposing Spectrum .spec readers to ChatGPT and other MCP clients."""

from __future__ import annotations

import argparse
import os
from typing import Any

from mcp.server.fastmcp import FastMCP

from . import core


mcp = FastMCP(
    "Spectrum Spec Reader",
    instructions=(
        "Read and inspect Spectrum Algo .spec and .specpack files. "
        "Use these tools when the user asks about encoded Spectrum files, "
        "compressed source archives, or .spec format contents."
    ),
    host=os.environ.get("SPECTRUM_MCP_HOST", "127.0.0.1"),
    port=int(os.environ.get("SPECTRUM_MCP_PORT", "8000")),
    streamable_http_path=os.environ.get("SPECTRUM_MCP_PATH", "/mcp"),
)


@mcp.tool()
def list_spec_files(root: str | None = None, limit: int = 500) -> dict[str, Any]:
    """List .spec and .specpack files under an allowed root."""
    return core.list_spec_files(root=root, limit=limit)


@mcp.tool()
def inspect_spec(path: str) -> dict[str, Any]:
    """Read only the header metadata for a .spec file."""
    return core.inspect_spec(path)


@mcp.tool()
def read_spec(path: str, max_chars: int = 200_000) -> dict[str, Any]:
    """Decode a .spec file to UTF-8 text plus fidelity metadata."""
    return core.read_spec(path, max_chars=max_chars)


@mcp.tool()
def inspect_specpack(path: str) -> dict[str, Any]:
    """Inspect a .specpack archive manifest and high-level size metadata."""
    return core.inspect_specpack(path)


@mcp.tool()
def read_specpack_member(path: str, source: str, max_chars: int = 200_000) -> dict[str, Any]:
    """Decode one source member from a .specpack archive."""
    return core.read_specpack_member(path, source=source, max_chars=max_chars)


@mcp.tool()
def search_specs(
    query: str,
    root: str | None = None,
    limit: int = 20,
    max_file_bytes: int = 5_000_000,
) -> dict[str, Any]:
    """Search decoded .spec and .specpack contents for a plain-text query."""
    return core.search_specs(query=query, root=root, limit=limit, max_file_bytes=max_file_bytes)


def main() -> None:
    parser = argparse.ArgumentParser(description="Spectrum .spec MCP server")
    parser.add_argument(
        "--transport",
        choices=("stdio", "sse", "streamable-http"),
        default="stdio",
        help="MCP transport to run. Use streamable-http or sse behind HTTPS for ChatGPT.",
    )
    args = parser.parse_args()
    mcp.run(transport=args.transport)


if __name__ == "__main__":
    main()
