from __future__ import annotations

import json
import tempfile
from dataclasses import asdict, is_dataclass
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import unquote, urlparse

from spectrum_core import SpectrumPack, inspect_pack, unpack, verify_pack
from spectrum_index import build_pack_index, search_pack

SERVER_VERSION = "0.1.0"


def _json_default(value: Any):
    if isinstance(value, Path):
        return str(value)
    if is_dataclass(value):
        return asdict(value)
    raise TypeError(f"Object of type {type(value).__name__} is not JSON serializable")


class ApiError(Exception):
    def __init__(self, status: HTTPStatus, message: str):
        super().__init__(message)
        self.status = status
        self.message = message


class PackRegistry:
    """In-memory registry of local `.specpack` paths."""

    def __init__(self) -> None:
        self._packs: dict[str, Path] = {}

    def add(self, pack_id: str, path: str | Path) -> dict:
        if not pack_id:
            raise ApiError(HTTPStatus.BAD_REQUEST, "pack id is required")
        pack_path = Path(path).expanduser().resolve()
        if not pack_path.exists():
            raise ApiError(HTTPStatus.NOT_FOUND, f"pack not found: {pack_path}")
        if pack_path.suffix.lower() != ".specpack":
            raise ApiError(HTTPStatus.BAD_REQUEST, "pack path must end with .specpack")
        with SpectrumPack.open(pack_path):
            pass
        self._packs[pack_id] = pack_path
        return {"id": pack_id, "path": str(pack_path)}

    def get(self, pack_id: str) -> Path:
        try:
            return self._packs[pack_id]
        except KeyError as exc:
            raise ApiError(HTTPStatus.NOT_FOUND, f"unknown pack: {pack_id}") from exc

    def remove(self, pack_id: str) -> dict:
        path = self.get(pack_id)
        del self._packs[pack_id]
        return {"id": pack_id, "path": str(path), "removed": True}

    def list(self) -> list[dict]:
        return [{"id": pack_id, "path": str(path)} for pack_id, path in sorted(self._packs.items())]


def create_handler(registry: PackRegistry | None = None):
    registry = registry or PackRegistry()

    class SpectrumHandler(BaseHTTPRequestHandler):
        server_version = f"SpectrumServer/{SERVER_VERSION}"

        def log_message(self, format: str, *args) -> None:  # noqa: A002
            if getattr(self.server, "quiet", False):
                return
            super().log_message(format, *args)

        def do_GET(self) -> None:
            self._handle("GET")

        def do_POST(self) -> None:
            self._handle("POST")

        def do_DELETE(self) -> None:
            self._handle("DELETE")

        def _handle(self, method: str) -> None:
            try:
                payload = self._route(method)
                self._send_json(payload)
            except ApiError as exc:
                self._send_json({"error": exc.message}, status=exc.status)
            except json.JSONDecodeError:
                self._send_json({"error": "invalid JSON body"}, status=HTTPStatus.BAD_REQUEST)
            except Exception as exc:  # pragma: no cover - defensive HTTP boundary.
                self._send_json({"error": str(exc)}, status=HTTPStatus.INTERNAL_SERVER_ERROR)

        def _route(self, method: str) -> Any:
            parsed = urlparse(self.path)
            parts = [unquote(part) for part in parsed.path.strip("/").split("/") if part]

            if method == "GET" and parts == ["health"]:
                return {"status": "ok", "version": SERVER_VERSION}

            if parts == ["packs"]:
                if method == "GET":
                    return {"packs": registry.list()}
                if method == "POST":
                    body = self._read_json()
                    pack_id = str(body.get("id") or body.get("name") or "")
                    path = body.get("path")
                    if not path:
                        raise ApiError(HTTPStatus.BAD_REQUEST, "path is required")
                    return registry.add(pack_id, path)

            if len(parts) == 2 and parts[0] == "packs":
                pack_id = parts[1]
                if method == "GET":
                    return {"id": pack_id, **inspect_pack(registry.get(pack_id))}
                if method == "DELETE":
                    return registry.remove(pack_id)

            if len(parts) == 3 and parts[0] == "packs" and parts[2] == "verify" and method == "POST":
                return verify_pack(registry.get(parts[1])).to_dict()

            if len(parts) == 3 and parts[0] == "packs" and parts[2] == "index" and method == "POST":
                body = self._read_json()
                result = build_pack_index(
                    registry.get(parts[1]),
                    output_path=body.get("output_path"),
                    embed=bool(body.get("embed", True)),
                )
                return {key: value for key, value in result.items() if key != "index"}

            if len(parts) == 3 and parts[0] == "packs" and parts[2] == "search" and method == "POST":
                body = self._read_json()
                query = str(body.get("query") or "")
                if not query:
                    raise ApiError(HTTPStatus.BAD_REQUEST, "query is required")
                return {
                    "results": search_pack(
                        registry.get(parts[1]),
                        query,
                        top_k=int(body.get("top_k", 10)),
                        language=body.get("language", "txt"),
                        index_path=body.get("index_path"),
                        build_if_missing=bool(body.get("build_if_missing", True)),
                    )
                }

            if len(parts) == 3 and parts[0] == "packs" and parts[2] == "unpack" and method == "POST":
                body = self._read_json()
                output = body.get("output_dir")
                if not output:
                    raise ApiError(HTTPStatus.BAD_REQUEST, "output_dir is required")
                results = unpack(registry.get(parts[1]), output)
                return {"results": results}

            if len(parts) == 4 and parts[0] == "packs" and parts[2] == "documents" and method == "GET":
                pack_id = parts[1]
                document_path = parts[3]
                with tempfile.TemporaryDirectory(prefix="spectrum-server-doc-") as tmp_name:
                    tmp = Path(tmp_name)
                    results = unpack(registry.get(pack_id), tmp)
                    for result in results:
                        rel = Path(result.output_path).relative_to(tmp).as_posix()
                        if rel == document_path:
                            data = Path(result.output_path).read_bytes()
                            return {
                                "path": rel,
                                "content": data.decode("utf-8", errors="replace"),
                                "content_bytes": list(data),
                            }
                raise ApiError(HTTPStatus.NOT_FOUND, f"document not found: {document_path}")

            raise ApiError(HTTPStatus.NOT_FOUND, "route not found")

        def _read_json(self) -> dict:
            length = int(self.headers.get("content-length", "0") or "0")
            if length <= 0:
                return {}
            return json.loads(self.rfile.read(length).decode("utf-8"))

        def _send_json(self, payload: Any, status: HTTPStatus = HTTPStatus.OK) -> None:
            body = json.dumps(payload, default=_json_default, indent=2).encode("utf-8")
            self.send_response(status.value)
            self.send_header("content-type", "application/json; charset=utf-8")
            self.send_header("content-length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

    return SpectrumHandler


class SpectrumServer(ThreadingHTTPServer):
    def __init__(self, server_address, RequestHandlerClass, *, quiet: bool = False):
        super().__init__(server_address, RequestHandlerClass)
        self.quiet = quiet


def run_server(
    *,
    host: str = "127.0.0.1",
    port: int = 7777,
    registry: PackRegistry | None = None,
    quiet: bool = False,
) -> SpectrumServer:
    server = SpectrumServer((host, port), create_handler(registry), quiet=quiet)
    server.serve_forever()
    return server
