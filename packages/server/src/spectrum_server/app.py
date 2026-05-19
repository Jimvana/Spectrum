from __future__ import annotations

import json
import mimetypes
import shutil
import tempfile
import threading
import zipfile
from collections import OrderedDict
from dataclasses import asdict, dataclass, is_dataclass
from datetime import datetime, timezone
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, quote, unquote, urljoin, urlparse
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from spectrum_core import (
    EncryptOptions,
    LockedPackError,
    SpectrumPack,
    append_to_pack,
    decode_member,
    encode_file,
    encrypt_pack_bytes,
    export_distributable,
    inspect_pack,
    inspect_encrypted_header,
    is_encrypted_pack,
    is_generated_path,
    unpack,
    verify_pack,
)
from spectrum_index import build_pack_index, search_pack

SERVER_VERSION = "0.1.0"
PROJECT_CONTEXT_FILES = [
    "project.md",
    "status.md",
    "agent-rules.md",
    "architecture.md",
    "deploy.md",
    "server.md",
    "ssh.md",
    "secrets.refs.md",
    "ops.json",
    "runbook.md",
    "decisions.md",
]
PROJECT_CONTEXT_DIR = ".spectrum-project"
TRASH_SOURCE_PATH = ".spectrum-trash/trash.jsonl"
PROJECT_FIELD_NAMES = {
    "project.md": "project",
    "status.md": "status",
    "agent-rules.md": "rules",
    "architecture.md": "architecture",
    "deploy.md": "deploy",
    "server.md": "server",
    "ssh.md": "ssh",
    "secrets.refs.md": "secret_references",
    "ops.json": "ops_json",
    "runbook.md": "runbook",
    "decisions.md": "decisions",
}


@dataclass(frozen=True)
class HtmlResponse:
    body: str
    status: HTTPStatus = HTTPStatus.OK


@dataclass(frozen=True)
class RawResponse:
    body: bytes
    content_type: str
    status: HTTPStatus = HTTPStatus.OK


@dataclass(frozen=True)
class RawFileResponse:
    path: Path
    content_type: str
    status: HTTPStatus = HTTPStatus.OK


@dataclass(frozen=True)
class ProxyResponse:
    body: bytes
    status: int
    headers: dict[str, str]


class DecodedFileCache:
    def __init__(self, *, max_entries: int = 256, max_bytes: int = 64 * 1024 * 1024) -> None:
        self.max_entries = max_entries
        self.max_bytes = max_bytes
        self._raw: OrderedDict[tuple[str, int, int, str], bytes] = OrderedDict()
        self._documents: OrderedDict[tuple[str, int, int, str], dict[str, Any]] = OrderedDict()
        self._bytes = 0
        self._lock = threading.RLock()

    def _key(self, pack_path: Path, source_path: str) -> tuple[str, int, int, str]:
        stat = pack_path.stat()
        return (str(pack_path.resolve()), stat.st_mtime_ns, stat.st_size, source_path)

    def get_raw(self, pack_path: Path, source_path: str) -> bytes | None:
        key = self._key(pack_path, source_path)
        with self._lock:
            value = self._raw.get(key)
            if value is None:
                return None
            self._raw.move_to_end(key)
            return value

    def set_raw(self, pack_path: Path, source_path: str, value: bytes) -> None:
        key = self._key(pack_path, source_path)
        with self._lock:
            previous = self._raw.pop(key, None)
            if previous is not None:
                self._bytes -= len(previous)
            self._raw[key] = value
            self._bytes += len(value)
            self._trim()

    def get_document(self, pack_path: Path, source_path: str) -> dict[str, Any] | None:
        key = self._key(pack_path, source_path)
        with self._lock:
            value = self._documents.get(key)
            if value is None:
                return None
            self._documents.move_to_end(key)
            return dict(value)

    def set_document(self, pack_path: Path, source_path: str, value: dict[str, Any]) -> None:
        key = self._key(pack_path, source_path)
        with self._lock:
            self._documents[key] = dict(value)
            self._trim()

    def invalidate(self, pack_path: Path | None = None) -> None:
        with self._lock:
            if pack_path is None:
                self._raw.clear()
                self._documents.clear()
                self._bytes = 0
                return
            prefix = str(pack_path.resolve())
            for key in list(self._raw):
                if key[0] == prefix:
                    self._bytes -= len(self._raw.pop(key))
            for key in list(self._documents):
                if key[0] == prefix:
                    self._documents.pop(key)

    def _trim(self) -> None:
        while len(self._raw) + len(self._documents) > self.max_entries or self._bytes > self.max_bytes:
            if self._raw:
                _key, value = self._raw.popitem(last=False)
                self._bytes -= len(value)
            elif self._documents:
                self._documents.popitem(last=False)
            else:
                break


_DECODE_CACHE = DecodedFileCache()


def _json_default(value: Any):
    if isinstance(value, Path):
        return str(value)
    if is_dataclass(value):
        return asdict(value)
    raise TypeError(f"Object of type {type(value).__name__} is not JSON serializable")


def _truthy(value: Any) -> bool:
    if isinstance(value, str):
        return value.lower() in {"1", "true", "yes", "on"}
    return bool(value)


class ApiError(Exception):
    def __init__(self, status: HTTPStatus, message: str):
        super().__init__(message)
        self.status = status
        self.message = message


class PackRegistry:
    """In-memory registry of local `.specpack` paths."""

    def __init__(self) -> None:
        self._packs: dict[str, Path] = {}
        self._passphrases: dict[str, str] = {}
        self._app_proxy_overrides: dict[str, dict[str, Any]] = {}
        self.lock = threading.RLock()

    def add(self, pack_id: str, path: str | Path, *, passphrase: str | None = None) -> dict:
        if not pack_id:
            raise ApiError(HTTPStatus.BAD_REQUEST, "pack id is required")
        pack_path = Path(path).expanduser().resolve()
        if not pack_path.exists():
            raise ApiError(HTTPStatus.NOT_FOUND, f"pack not found: {pack_path}")
        if pack_path.suffix.lower() != ".specpack":
            raise ApiError(HTTPStatus.BAD_REQUEST, "pack path must end with .specpack")
        with SpectrumPack.open(pack_path, passphrase=passphrase):
            pass
        self._packs[pack_id] = pack_path
        if passphrase is not None:
            self._passphrases[pack_id] = passphrase
        _DECODE_CACHE.invalidate(pack_path)
        info = inspect_pack(pack_path, passphrase=passphrase)
        return {"id": pack_id, "path": str(pack_path), "encrypted": info.get("encrypted", False), "locked": False}

    def get(self, pack_id: str) -> Path:
        try:
            return self._packs[pack_id]
        except KeyError as exc:
            raise ApiError(HTTPStatus.NOT_FOUND, f"unknown pack: {pack_id}") from exc

    def has(self, pack_id: str) -> bool:
        return pack_id in self._packs

    def passphrase(self, pack_id: str) -> str | None:
        self.get(pack_id)
        return self._passphrases.get(pack_id)

    def set_app_proxy(self, pack_id: str, target: str, *, routes: list[str] | None = None) -> None:
        self.get(pack_id)
        parsed = urlparse(target)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            raise ApiError(HTTPStatus.BAD_REQUEST, "proxy target must be an http(s) URL")
        self._app_proxy_overrides[pack_id] = {
            "backend": {
                "mode": "proxy",
                "target": target.rstrip("/"),
                "routes": routes or ["/api/*"],
            }
        }

    def app_proxy_override(self, pack_id: str) -> dict[str, Any] | None:
        self.get(pack_id)
        return self._app_proxy_overrides.get(pack_id)

    def remove(self, pack_id: str) -> dict:
        path = self.get(pack_id)
        del self._packs[pack_id]
        _DECODE_CACHE.invalidate(path)
        return {"id": pack_id, "path": str(path), "removed": True}

    def list(self) -> list[dict]:
        rows = []
        for pack_id, path in sorted(self._packs.items()):
            encrypted = is_encrypted_pack(path)
            rows.append({
                "id": pack_id,
                "path": str(path),
                "encrypted": encrypted,
                "locked": encrypted and pack_id not in self._passphrases,
                "hint": inspect_pack(path).get("hint") if encrypted else None,
            })
        return rows


def _decode_document(pack_path: Path, source_path: str, *, passphrase: str | None = None) -> dict:
    source_path = _safe_source_path(source_path)
    cached = _DECODE_CACHE.get_document(pack_path, source_path)
    if cached is not None:
        return cached
    with tempfile.TemporaryDirectory(prefix="spectrum-server-doc-") as tmp_name:
        tmp = Path(tmp_name)
        output = tmp / "document"
        with SpectrumPack.open(pack_path, passphrase=passphrase) as opened:
            entry = opened.find_entry(source_path)
            if entry is None:
                raise ApiError(HTTPStatus.NOT_FOUND, f"document not found: {source_path}")
        result = decode_member(pack_path, source_path, output, passphrase=passphrase)
        data = output.read_bytes()
        document = {
            "path": entry.source,
            "id": entry.source_id,
            "metadata": entry.metadata or {},
            "content": data.decode("utf-8", errors="replace"),
            "content_bytes": list(data),
            "checksum_ok": result.checksum_ok,
            "length_ok": result.length_ok,
        }
        _DECODE_CACHE.set_raw(pack_path, source_path, data)
        _DECODE_CACHE.set_document(pack_path, source_path, document)
        return document


def _decode_json_document(pack_path: Path, candidates: list[str], *, passphrase: str | None = None) -> dict[str, Any] | None:
    with SpectrumPack.open(pack_path, passphrase=passphrase) as opened:
        available = {entry.source for entry in opened.entries}
    source_path = next((candidate for candidate in candidates if candidate in available), None)
    if source_path is None:
        return None
    decoded = _decode_document(pack_path, source_path, passphrase=passphrase)
    try:
        data = json.loads(decoded["content"])
    except json.JSONDecodeError as exc:
        raise ApiError(HTTPStatus.BAD_REQUEST, f"invalid app manifest JSON in {source_path}: {exc.msg}") from exc
    if not isinstance(data, dict):
        raise ApiError(HTTPStatus.BAD_REQUEST, f"app manifest must be a JSON object: {source_path}")
    data["_source_path"] = source_path
    return data


def _pack_app_config(
    pack_path: Path,
    *,
    passphrase: str | None = None,
    override: dict[str, Any] | None = None,
) -> dict[str, Any]:
    config = _decode_json_document(
        pack_path,
        [f"{PROJECT_CONTEXT_DIR}/app.json", ".spectrum/app.json", "spectrum.app.json"],
        passphrase=passphrase,
    ) or {}
    if override:
        merged = dict(config)
        for key, value in override.items():
            if isinstance(value, dict) and isinstance(merged.get(key), dict):
                merged[key] = {**merged[key], **value}
            else:
                merged[key] = value
        config = merged
    config.setdefault("entry", "public/index.html")
    return config


def _route_matches(pattern: str, request_path: str) -> bool:
    pattern = "/" + pattern.strip("/")
    path = "/" + request_path.strip("/")
    if pattern.endswith("/*"):
        return path == pattern[:-2] or path.startswith(pattern[:-1])
    return path == pattern


def _proxy_config_for_request(app_config: dict[str, Any], request_path: str) -> dict[str, Any] | None:
    backend = app_config.get("backend")
    if not isinstance(backend, dict) or backend.get("mode") != "proxy":
        return None
    target = str(backend.get("target") or "").strip()
    if not target:
        return None
    routes = backend.get("routes") or ["/api/*"]
    if not isinstance(routes, list):
        return None
    if any(_route_matches(str(route), request_path) for route in routes):
        return {"target": target.rstrip("/"), "routes": routes}
    return None


def _proxy_request(method: str, request_path: str, query: str, body: bytes, headers: dict[str, str], target: str) -> ProxyResponse:
    url = urljoin(f"{target}/", request_path.lstrip("/"))
    if query:
        url = f"{url}?{query}"
    forwarded_headers = {
        key: value
        for key, value in headers.items()
        if key.lower() not in {"host", "content-length", "connection", "accept-encoding"}
    }
    request = Request(url, data=body if body else None, headers=forwarded_headers, method=method)
    try:
        with urlopen(request, timeout=20) as response:
            response_headers = {
                key: value
                for key, value in response.headers.items()
                if key.lower() not in {"connection", "transfer-encoding", "content-encoding"}
            }
            return ProxyResponse(response.read(), response.status, response_headers)
    except HTTPError as exc:
        response_headers = {
            key: value
            for key, value in exc.headers.items()
            if key.lower() not in {"connection", "transfer-encoding", "content-encoding"}
        }
        return ProxyResponse(exc.read(), exc.code, response_headers)
    except Exception as exc:
        raise ApiError(HTTPStatus.BAD_GATEWAY, f"app backend proxy failed: {exc}") from exc


def _content_type(source_path: str) -> str:
    guessed, _encoding = mimetypes.guess_type(source_path)
    if guessed:
        if guessed.startswith("text/") or guessed in {"application/javascript", "application/json"}:
            return f"{guessed}; charset=utf-8"
        return guessed
    return "application/octet-stream"


def _raw_pack_file(pack_path: Path, source_path: str, *, passphrase: str | None = None) -> RawResponse | RawFileResponse:
    source = _safe_source_path(source_path)
    cached = _DECODE_CACHE.get_raw(pack_path, source)
    if cached is not None:
        return RawResponse(cached, _content_type(source))
    with SpectrumPack.open(pack_path, passphrase=passphrase) as opened:
        entry = opened.find_entry(source)
        if entry is not None:
            with tempfile.TemporaryDirectory(prefix="spectrum-server-raw-") as tmp_name:
                output = Path(tmp_name) / "raw"
                decode_member(pack_path, source, output, passphrase=passphrase)
                data = output.read_bytes()
                _DECODE_CACHE.set_raw(pack_path, source, data)
                return RawResponse(data, _content_type(source))
        external = next((candidate for candidate in opened.external_entries if candidate.source == source), None)
        if external is not None:
            blob = opened.external_blob_path(external)
            if not blob.exists():
                raise ApiError(HTTPStatus.NOT_FOUND, f"external media sidecar missing: {source}")
            return RawFileResponse(blob, _content_type(source))
    raise ApiError(HTTPStatus.NOT_FOUND, f"raw file not found: {source}")


def _app_source_candidates(path: str) -> list[str]:
    source = path.strip("/")
    if not source:
        return ["public/index.html", "index.html", "dist/index.html", "build/index.html"]
    if source.endswith("/"):
        source = f"{source}index.html"
    candidates = []
    if not source.startswith("public/"):
        candidates.append(f"public/{source}")
    if not source.startswith("dist/"):
        candidates.append(f"dist/{source}")
    if not source.startswith("build/"):
        candidates.append(f"build/{source}")
    candidates.append(source)
    if "." not in Path(source).name:
        candidates.extend(["public/index.html", "index.html", "dist/index.html", "build/index.html"])
    return candidates


def _raw_app_file(pack_path: Path, app_path: str, *, passphrase: str | None = None) -> RawResponse | RawFileResponse:
    last_error: ApiError | None = None
    for source in _app_source_candidates(app_path):
        try:
            return _raw_pack_file(pack_path, source, passphrase=passphrase)
        except ApiError as exc:
            if exc.status != HTTPStatus.NOT_FOUND:
                raise
            last_error = exc
    raise last_error or ApiError(HTTPStatus.NOT_FOUND, f"app file not found: {app_path}")


def _safe_source_path(value: str) -> str:
    path = Path(value.replace("\\", "/"))
    if not value or path.is_absolute() or ".." in path.parts:
        raise ApiError(HTTPStatus.BAD_REQUEST, f"unsafe document path: {value!r}")
    if any(part in {"", ".", ".."} for part in path.parts):
        raise ApiError(HTTPStatus.BAD_REQUEST, f"unsafe document path: {value!r}")
    return path.as_posix()


def _upsert_pack_document(pack_path: Path, source_path: str, body: dict, *, passphrase: str | None = None) -> dict:
    source = _safe_source_path(source_path)
    if "content_bytes" in body:
        raw_bytes = bytes(int(value) for value in body["content_bytes"])
    elif "content" in body:
        raw_bytes = str(body["content"]).encode("utf-8")
    else:
        raise ApiError(HTTPStatus.BAD_REQUEST, "content or content_bytes is required")

    replace = bool(body.get("replace", True))
    rebuild_index = bool(body.get("rebuild_index", True))
    with tempfile.TemporaryDirectory(prefix="spectrum-server-upsert-") as tmp_name:
        tmp = Path(tmp_name)
        target = tmp / source
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(raw_bytes)
        append_summary = append_to_pack(pack_path, tmp, replace=replace, include_all=True, passphrase=passphrase)
    _DECODE_CACHE.invalidate(pack_path)

    verify_report = verify_pack(pack_path, passphrase=passphrase).to_dict()
    index_summary = None
    if rebuild_index:
        result = build_pack_index(pack_path, embed=True, passphrase=passphrase)
        index_summary = {key: value for key, value in result.items() if key != "index"}
    document = _decode_document(pack_path, source, passphrase=passphrase)
    return {
        "path": str(pack_path),
        "source_path": source,
        "append": append_summary,
        "verify": verify_report,
        "index": index_summary,
        "document": {
            key: value
            for key, value in document.items()
            if key != "content_bytes"
        },
    }


def _delete_pack_document(pack_path: Path, source_path: str, body: dict | None = None, *, passphrase: str | None = None) -> dict:
    source = _safe_source_path(source_path)
    body = body or {}
    rebuild_index = bool(body.get("rebuild_index", True))
    reason = str(body.get("reason") or "")
    with SpectrumPack.open(pack_path, passphrase=passphrase) as opened:
        entry = opened.find_entry(source)
        if entry is None:
            raise ApiError(HTTPStatus.NOT_FOUND, f"document not found: {source}")
        manifest = dict(opened.manifest)
        entries = [
            raw
            for raw in manifest.get("entries", [])
            if str(raw.get("source", "")) not in {source, TRASH_SOURCE_PATH}
        ]
        removed_spec = entry.spec

    with tempfile.TemporaryDirectory(prefix="spectrum-server-delete-") as tmp_name:
        tmp = Path(tmp_name)
        removed_output = tmp / "removed"
        result = decode_member(pack_path, source, removed_output, passphrase=passphrase)
        removed_content = removed_output.read_text(encoding="utf-8", errors="replace")
        trash_existing = ""
        with SpectrumPack.open(pack_path, passphrase=passphrase) as opened:
            if opened.find_entry(TRASH_SOURCE_PATH) is not None:
                trash_output = tmp / "existing-trash.jsonl"
                decode_member(pack_path, TRASH_SOURCE_PATH, trash_output, passphrase=passphrase)
                trash_existing = trash_output.read_text(encoding="utf-8", errors="replace")

        trash_record = {
            "deleted_at": datetime.now(timezone.utc).isoformat(),
            "source_path": source,
            "reason": reason,
            "checksum_ok": result.checksum_ok,
            "length_ok": result.length_ok,
            "content": removed_content,
        }
        trash_content = trash_existing + json.dumps(trash_record, ensure_ascii=False) + "\n"
        trash_source = tmp / TRASH_SOURCE_PATH
        trash_source.parent.mkdir(parents=True, exist_ok=True)
        trash_source.write_text(trash_content, encoding="utf-8")
        trash_spec = tmp / "trash.spec"
        encode_result = encode_file(trash_source, trash_spec)
        trash_entry = {
            "source": TRASH_SOURCE_PATH,
            "spec": f"files/{TRASH_SOURCE_PATH}.spec",
            "original_size": encode_result.original_size,
            "spec_size": encode_result.spec_size,
            "metadata": {"system": True, "role": "trash"},
        }
        entries.append(trash_entry)
        manifest["entries"] = entries

        tmp_zip = Path(tmp_name) / pack_path.name
        with SpectrumPack.open(pack_path, passphrase=passphrase) as opened, zipfile.ZipFile(
            tmp_zip, "w", compression=zipfile.ZIP_STORED
        ) as target_zip:
            source_zip = opened._zip
            for item in source_zip.infolist():
                if item.filename in {"manifest.json", removed_spec, "index.bin", trash_entry["spec"]}:
                    continue
                target_zip.writestr(item, source_zip.read(item.filename))
            target_zip.writestr("manifest.json", json.dumps(manifest, indent=2))
            target_zip.write(trash_spec, trash_entry["spec"])
        if is_encrypted_pack(pack_path):
            if passphrase is None:
                raise ApiError(HTTPStatus.LOCKED, "encrypted Spectrum pack is locked")
            encrypted_info = inspect_encrypted_header(pack_path)
            pack_path.write_bytes(
                encrypt_pack_bytes(
                    tmp_zip.read_bytes(),
                    passphrase,
                    options=EncryptOptions(
                        encrypted_info.kdf_profile or "interactive",
                        encrypted_info.hint,
                    ),
                )
            )
        else:
            shutil.move(str(tmp_zip), pack_path)

    _DECODE_CACHE.invalidate(pack_path)
    verify_report = verify_pack(pack_path, passphrase=passphrase).to_dict()
    index_summary = None
    if rebuild_index:
        result = build_pack_index(pack_path, embed=True, passphrase=passphrase)
        index_summary = {key: value for key, value in result.items() if key != "index"}
    return {
        "path": str(pack_path),
        "source_path": source,
        "removed": True,
        "archived_to": TRASH_SOURCE_PATH,
        "verify": verify_report,
        "index": index_summary,
    }


def _hydrate_url(pack_id: str, source_path: str) -> str:
    return f"/packs/{quote(pack_id, safe='')}/documents/{quote(source_path, safe='')}"


def _document_summary(pack_id: str, entry) -> dict:
    return {
        "source_path": entry.source,
        "path": entry.spec,
        "id": entry.source_id,
        "metadata": entry.metadata or {},
        "original_size": entry.original_size,
        "spec_size": entry.spec_size,
        "hydrate_url": _hydrate_url(pack_id, entry.source),
    }


def _pack_manifest(pack_path: Path, pack_id: str, *, passphrase: str | None = None) -> dict:
    with SpectrumPack.open(pack_path, passphrase=passphrase) as opened:
        documents = [_document_summary(pack_id, entry) for entry in opened.entries]
        return {
            "id": pack_id,
            "pack_path": str(pack_path),
            "format": opened.manifest.get("format"),
            "version": opened.manifest.get("version"),
            "dict_version": opened.manifest.get("dict_version"),
            "source_root": opened.manifest.get("source_root"),
            "app": _pack_app_config(pack_path, passphrase=passphrase),
            "documents": documents,
        }


def _raw_url(pack_id: str, source_path: str) -> str:
    return f"/packs/{quote(pack_id, safe='')}/raw/{quote(source_path, safe='')}"


def _pack_files(
    pack_path: Path,
    pack_id: str,
    *,
    prefix: str = "",
    limit: int = 500,
    cursor: int = 0,
    include_generated: bool = False,
    passphrase: str | None = None,
) -> dict:
    prefix = prefix.strip("/")
    prefix_match = f"{prefix}/" if prefix else ""
    limit = max(1, min(limit, 2000))
    cursor = max(0, cursor)
    with SpectrumPack.open(pack_path, passphrase=passphrase) as opened:
        rows = []
        for entry in opened.entries:
            if prefix and entry.source != prefix and not entry.source.startswith(prefix_match):
                continue
            generated = is_generated_path(entry.source)
            if generated and not include_generated:
                continue
            rows.append(
                {
                    "source_path": entry.source,
                    "kind": "encoded",
                    "generated": generated,
                    "original_size": entry.original_size,
                    "spec_size": entry.spec_size,
                    "metadata": entry.metadata or {},
                    "hydrate_url": _hydrate_url(pack_id, entry.source),
                    "raw_url": _raw_url(pack_id, entry.source),
                }
            )
        for entry in opened.external_entries:
            if prefix and entry.source != prefix and not entry.source.startswith(prefix_match):
                continue
            generated = is_generated_path(entry.source)
            if generated and not include_generated:
                continue
            rows.append(
                {
                    "source_path": entry.source,
                    "kind": entry.kind,
                    "generated": generated,
                    "original_size": entry.size_bytes,
                    "spec_size": 0,
                    "sidecar_path": entry.sidecar_path,
                    "sha256": entry.sha256,
                    "raw_url": _raw_url(pack_id, entry.source),
                }
            )
        rows.sort(key=lambda row: str(row["source_path"]).lower())
        page = rows[cursor : cursor + limit]
        next_cursor = cursor + limit if cursor + limit < len(rows) else None
        return {
            "id": pack_id,
            "pack_path": str(pack_path),
            "source_root": opened.manifest.get("source_root"),
            "prefix": prefix,
            "limit": limit,
            "cursor": cursor,
            "next_cursor": next_cursor,
            "include_generated": include_generated,
            "total": len(rows),
            "files": page,
        }


def _decode_project_ops(pack_path: Path, *, passphrase: str | None = None) -> dict:
    candidates = [f"{PROJECT_CONTEXT_DIR}/ops.json", "ops.json"]
    with SpectrumPack.open(pack_path, passphrase=passphrase) as opened:
        source_path = next((candidate for candidate in candidates if opened.find_entry(candidate)), None)
    if source_path is None:
        return {
            "missing": True,
            "path": None,
            "data": None,
            "error": None,
        }

    decoded = _decode_document(pack_path, source_path, passphrase=passphrase)
    try:
        data = json.loads(decoded["content"])
    except json.JSONDecodeError as exc:
        return {
            "missing": False,
            "path": decoded["path"],
            "data": None,
            "error": f"invalid JSON: {exc.msg}",
            "checksum_ok": decoded["checksum_ok"],
            "length_ok": decoded["length_ok"],
        }
    return {
        "missing": False,
        "path": decoded["path"],
        "data": data,
        "error": None,
        "checksum_ok": decoded["checksum_ok"],
        "length_ok": decoded["length_ok"],
    }


def _first_site(ops: dict) -> dict:
    sites = ((ops.get("data") or {}).get("sites") or []) if not ops.get("missing") else []
    return sites[0] if sites and isinstance(sites[0], dict) else {}


def _ops_readiness(ops: dict) -> dict:
    site = _first_site(ops)
    ssh = site.get("ssh") if isinstance(site.get("ssh"), dict) else {}
    deploy = site.get("deploy") if isinstance(site.get("deploy"), dict) else {}
    policy = (ops.get("data") or {}).get("policy") or {}

    ssh_required = ["host", "user", "identity_file"]
    deploy_required = ["remote_path"]
    ssh_missing = [field for field in ssh_required if not ssh.get(field)]
    deploy_missing = [field for field in deploy_required if not deploy.get(field)]

    return {
        "ops": {
            "ready": not ops.get("missing") and ops.get("error") is None,
            "missing": bool(ops.get("missing")),
            "path": ops.get("path"),
            "error": ops.get("error"),
        },
        "ssh": {
            "ready": not ssh_missing and not ops.get("missing") and ops.get("error") is None,
            "missing": ssh_missing,
            "requires_confirmation": bool(policy.get("ssh_requires_confirmation", True)),
        },
        "deploy": {
            "ready": not deploy_missing and not ops.get("missing") and ops.get("error") is None,
            "missing": deploy_missing,
            "requires_confirmation": bool(policy.get("deploy_requires_confirmation", True)),
        },
    }


def _build_project_context(pack_path: Path, pack_id: str, *, passphrase: str | None = None) -> dict:
    documents = []
    missing = []
    fields: dict[str, str] = {}

    with SpectrumPack.open(pack_path, passphrase=passphrase) as opened:
        available = {entry.source for entry in opened.entries}

    for filename in PROJECT_CONTEXT_FILES:
        candidates = [f"{PROJECT_CONTEXT_DIR}/{filename}", filename]
        source_path = next((candidate for candidate in candidates if candidate in available), None)
        if source_path is None:
            missing.append(filename)
            continue
        decoded = _decode_document(pack_path, source_path, passphrase=passphrase)
        document = {
            "path": decoded["path"],
            "id": decoded["id"],
            "metadata": decoded["metadata"],
            "content": decoded["content"],
            "checksum_ok": decoded["checksum_ok"],
            "length_ok": decoded["length_ok"],
        }
        documents.append(document)
        fields[PROJECT_FIELD_NAMES[filename]] = decoded["content"]

    ops = _decode_project_ops(pack_path, passphrase=passphrase)
    return {
        "id": pack_id,
        "pack_path": str(pack_path),
        "context_dir": PROJECT_CONTEXT_DIR,
        "documents": documents,
        "missing": missing,
        "ops": ops,
        "readiness": _ops_readiness(ops),
        **fields,
    }


def _project_dashboard_html() -> str:
    return """<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Spectrum Project</title>
  <style>
    :root {
      color-scheme: light;
      --bg: #f6f7f9;
      --ink: #17202a;
      --muted: #627084;
      --line: #d8dee8;
      --panel: #ffffff;
      --accent: #0f766e;
      --accent-soft: #e6f4f1;
      --warn: #a16207;
      --warn-soft: #fef3c7;
      --bad: #b91c1c;
      --bad-soft: #fee2e2;
      --code: #eef2f7;
    }
    * { box-sizing: border-box; }
    body {
      margin: 0;
      font-family: Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
      color: var(--ink);
      background: var(--bg);
    }
    header {
      padding: 24px clamp(16px, 4vw, 40px) 16px;
      border-bottom: 1px solid var(--line);
      background: var(--panel);
    }
    h1, h2, h3 { margin: 0; font-weight: 650; letter-spacing: 0; }
    h1 { font-size: 24px; line-height: 1.2; }
    h2 { font-size: 16px; margin-bottom: 10px; }
    h3 { font-size: 14px; margin-bottom: 8px; }
    main {
      display: grid;
      grid-template-columns: minmax(280px, 360px) minmax(0, 1fr);
      gap: 18px;
      padding: 18px clamp(16px, 4vw, 40px) 36px;
    }
    section, aside {
      background: var(--panel);
      border: 1px solid var(--line);
      border-radius: 8px;
      padding: 16px;
      min-width: 0;
    }
    .stack { display: grid; gap: 14px; }
    .status {
      display: flex;
      align-items: center;
      gap: 8px;
      color: var(--muted);
      margin-top: 8px;
      font-size: 14px;
    }
    .dot {
      width: 10px;
      height: 10px;
      border-radius: 999px;
      background: var(--warn);
      flex: 0 0 auto;
    }
    .dot.ok { background: var(--accent); }
    .dot.bad { background: var(--bad); }
    .grid {
      display: grid;
      grid-template-columns: repeat(2, minmax(0, 1fr));
      gap: 12px;
    }
    .metric {
      border-top: 1px solid var(--line);
      padding-top: 10px;
    }
    .label {
      color: var(--muted);
      font-size: 12px;
      margin-bottom: 4px;
    }
    .value {
      font-size: 14px;
      overflow-wrap: anywhere;
    }
    code {
      background: var(--code);
      border: 1px solid var(--line);
      border-radius: 6px;
      padding: 1px 5px;
      font-family: ui-monospace, SFMono-Regular, Consolas, "Liberation Mono", monospace;
      font-size: 0.92em;
    }
    button, input {
      font: inherit;
      border-radius: 7px;
      border: 1px solid var(--line);
    }
    input {
      width: 100%;
      padding: 10px 11px;
      background: white;
      color: var(--ink);
    }
    button {
      padding: 10px 12px;
      cursor: pointer;
      color: white;
      background: var(--accent);
      border-color: var(--accent);
      white-space: nowrap;
    }
    button.secondary {
      color: var(--ink);
      background: white;
      border-color: var(--line);
    }
    button:disabled {
      cursor: wait;
      opacity: 0.68;
    }
    .actions {
      display: grid;
      grid-template-columns: repeat(2, minmax(0, 1fr));
      gap: 8px;
    }
    .endpoint-row {
      display: grid;
      grid-template-columns: minmax(0, 1fr) auto;
      gap: 8px;
      align-items: center;
    }
    .search {
      display: grid;
      grid-template-columns: minmax(0, 1fr) auto;
      gap: 10px;
    }
    .list {
      display: grid;
      gap: 8px;
      margin-top: 12px;
    }
    .item {
      width: 100%;
      text-align: left;
      color: var(--ink);
      background: white;
      border: 1px solid var(--line);
    }
    .item strong, .item span {
      display: block;
      overflow-wrap: anywhere;
    }
    .item span {
      color: var(--muted);
      font-size: 12px;
      margin-top: 3px;
    }
    pre {
      margin: 0;
      padding: 14px;
      min-height: 240px;
      max-height: 560px;
      overflow: auto;
      white-space: pre-wrap;
      overflow-wrap: anywhere;
      background: #111827;
      color: #e5e7eb;
      border-radius: 8px;
      font-family: ui-monospace, SFMono-Regular, Consolas, "Liberation Mono", monospace;
      font-size: 13px;
      line-height: 1.5;
    }
    .docs {
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
      gap: 8px;
    }
    .doc-button {
      color: var(--ink);
      background: white;
      border-color: var(--line);
      text-align: left;
      overflow-wrap: anywhere;
    }
    .checklist {
      display: grid;
      gap: 6px;
    }
    .check {
      display: grid;
      grid-template-columns: auto minmax(0, 1fr);
      gap: 8px;
      align-items: center;
      min-height: 26px;
      color: var(--muted);
      font-size: 13px;
    }
    .check .mark {
      display: grid;
      place-items: center;
      width: 18px;
      height: 18px;
      border-radius: 999px;
      background: var(--warn-soft);
      color: var(--warn);
      font-size: 12px;
      font-weight: 700;
    }
    .check.ok {
      color: var(--ink);
    }
    .check.ok .mark {
      background: var(--accent-soft);
      color: var(--accent);
    }
    .notice {
      border: 1px solid var(--line);
      border-radius: 8px;
      padding: 10px 12px;
      background: white;
      color: var(--muted);
      font-size: 13px;
      line-height: 1.45;
    }
    .notice.ok {
      border-color: #99d8cf;
      background: var(--accent-soft);
      color: #14534d;
    }
    .notice.bad {
      border-color: #fecaca;
      background: var(--bad-soft);
      color: var(--bad);
    }
    @media (max-width: 860px) {
      main { grid-template-columns: 1fr; }
      .grid { grid-template-columns: 1fr; }
      .search { grid-template-columns: 1fr; }
      .actions, .endpoint-row { grid-template-columns: 1fr; }
    }
  </style>
</head>
<body>
  <header>
    <h1>Spectrum Project</h1>
    <div class="status"><span id="status-dot" class="dot"></span><span id="status-text">Connecting</span></div>
  </header>
  <main>
    <aside class="stack">
      <section>
        <h2>Project</h2>
        <div class="grid">
          <div class="metric"><div class="label">Pack</div><div id="pack-id" class="value">repo</div></div>
          <div class="metric"><div class="label">Documents</div><div id="doc-count" class="value">0</div></div>
          <div class="metric"><div class="label">Missing</div><div id="missing-count" class="value">0</div></div>
          <div class="metric"><div class="label">Verify</div><div id="verify-state" class="value">Not run</div></div>
        </div>
      </section>
      <section>
        <h2>Actions</h2>
        <div class="actions">
          <button id="verify-button" type="button">Verify Pack</button>
          <button id="index-button" type="button">Rebuild Search</button>
        </div>
        <div id="action-result" class="notice">Pack maintenance actions run locally against the registered pack.</div>
      </section>
      <section>
        <h2>Agent Endpoint</h2>
        <div class="endpoint-row">
          <code id="endpoint-url">/projects/repo/context</code>
          <button id="copy-endpoint" class="secondary" type="button">Copy</button>
        </div>
      </section>
      <section>
        <h2>Readiness</h2>
        <div id="checklist" class="checklist"></div>
      </section>
      <section>
        <h2>Context Files</h2>
        <div id="docs" class="docs"></div>
      </section>
      <section>
        <h2>Search</h2>
        <div class="search">
          <input id="query" value="deploy nginx ssh" aria-label="Search query">
          <button id="search-button" type="button">Search</button>
        </div>
        <div id="results" class="list"></div>
      </section>
    </aside>
    <section class="stack">
      <div>
        <h2 id="viewer-title">Context</h2>
        <pre id="viewer">Loading project context...</pre>
      </div>
    </section>
  </main>
  <script>
    const packId = "repo";
    const statusDot = document.getElementById("status-dot");
    const statusText = document.getElementById("status-text");
    const viewer = document.getElementById("viewer");
    const viewerTitle = document.getElementById("viewer-title");
    const docsEl = document.getElementById("docs");
    const resultsEl = document.getElementById("results");
    const checklistEl = document.getElementById("checklist");
    const actionResult = document.getElementById("action-result");
    const verifyButton = document.getElementById("verify-button");
    const indexButton = document.getElementById("index-button");
    const endpointUrl = document.getElementById("endpoint-url");
    const expectedContextFiles = [
      "project.md",
      "status.md",
      "agent-rules.md",
      "architecture.md",
      "deploy.md",
      "server.md",
      "ssh.md",
      "secrets.refs.md",
      "runbook.md",
      "decisions.md"
    ];

    function setStatus(kind, text) {
      statusDot.className = "dot " + kind;
      statusText.textContent = text;
    }

    function setActionResult(kind, text) {
      actionResult.className = "notice " + kind;
      actionResult.textContent = text;
    }

    async function jsonFetch(url, options = {}) {
      const res = await fetch(url, options);
      if (!res.ok) {
        let message = `${res.status} ${res.statusText}`;
        try {
          const payload = await res.json();
          if (payload.error) message = payload.error;
        } catch (_) {
          // Keep the HTTP status fallback when the response is not JSON.
        }
        throw new Error(message);
      }
      return res.json();
    }

    function showDocument(doc) {
      viewerTitle.textContent = doc.path;
      viewer.textContent = doc.content || "";
    }

    async function hydrate(path) {
      const doc = await jsonFetch(`/packs/${packId}/documents/${encodeURIComponent(path)}`);
      showDocument(doc);
    }

    function renderDocs(context) {
      docsEl.textContent = "";
      for (const doc of context.documents || []) {
        const btn = document.createElement("button");
        btn.type = "button";
        btn.className = "doc-button";
        btn.textContent = doc.path;
        btn.addEventListener("click", () => showDocument(doc));
        docsEl.appendChild(btn);
      }
    }

    function renderChecklist(context) {
      checklistEl.textContent = "";
      const present = new Set((context.documents || []).map(doc => doc.path.split("/").pop()));
      for (const file of expectedContextFiles) {
        const row = document.createElement("div");
        const ok = present.has(file);
        row.className = "check " + (ok ? "ok" : "");
        row.innerHTML = `<span class="mark">${ok ? "OK" : "!"}</span><span>${file}</span>`;
        checklistEl.appendChild(row);
      }
    }

    function renderResults(results) {
      resultsEl.textContent = "";
      if (!results.length) {
        resultsEl.textContent = "No results";
        return;
      }
      for (const result of results) {
        const btn = document.createElement("button");
        btn.type = "button";
        btn.className = "item";
        btn.innerHTML = `<strong>${result.source_path || result.path}</strong><span>score ${result.score}</span>`;
        btn.addEventListener("click", () => hydrate(result.source_path));
        resultsEl.appendChild(btn);
      }
    }

    async function loadContext() {
      const [packs, context] = await Promise.all([
        jsonFetch("/packs"),
        jsonFetch(`/projects/${packId}/context`)
      ]);
      document.getElementById("pack-id").textContent = packs.packs?.[0]?.path || packId;
      document.getElementById("doc-count").textContent = String(context.documents?.length || 0);
      document.getElementById("missing-count").textContent = String(context.missing?.length || 0);
      endpointUrl.textContent = `${window.location.origin}/projects/${packId}/context`;
      renderDocs(context);
      renderChecklist(context);
      viewerTitle.textContent = "Project Context";
      viewer.textContent = [
        context.project || "",
        context.status || "",
        context.rules || "",
        context.deploy || "",
        context.server || "",
        context.ssh || "",
        context.secret_references || ""
      ].filter(Boolean).join("\\n\\n---\\n\\n");
      setStatus("ok", "Project loaded. Agent context available.");
    }

    async function runVerify() {
      verifyButton.disabled = true;
      setActionResult("", "Verifying pack...");
      try {
        const result = await jsonFetch(`/packs/${packId}/verify`, { method: "POST" });
        const summary = `${result.decode_passed}/${result.chunks_checked} chunks passed`;
        document.getElementById("verify-state").textContent = result.valid ? "Passed" : "Failed";
        setActionResult(result.valid ? "ok" : "bad", result.valid ? `Pack verified. ${summary}.` : `Pack verification failed. ${summary}.`);
      } finally {
        verifyButton.disabled = false;
      }
    }

    async function rebuildSearch() {
      indexButton.disabled = true;
      setActionResult("", "Rebuilding embedded search index...");
      try {
        const result = await jsonFetch(`/packs/${packId}/index`, {
          method: "POST",
          headers: { "content-type": "application/json" },
          body: JSON.stringify({ embed: true })
        });
        setActionResult("ok", `Search index rebuilt for ${result.documents} documents.`);
      } finally {
        indexButton.disabled = false;
      }
    }

    async function copyEndpoint() {
      const value = endpointUrl.textContent || "";
      if (navigator.clipboard?.writeText) {
        await navigator.clipboard.writeText(value);
        setActionResult("ok", "Agent endpoint copied.");
      } else {
        setActionResult("", value);
      }
    }

    async function runSearch() {
      const query = document.getElementById("query").value.trim();
      if (!query) return;
      const payload = await jsonFetch(`/packs/${packId}/search`, {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({ query, top_k: 6 })
      });
      renderResults(payload.results || []);
    }

    document.getElementById("search-button").addEventListener("click", runSearch);
    verifyButton.addEventListener("click", () => {
      runVerify().catch(error => setActionResult("bad", error.message));
    });
    indexButton.addEventListener("click", () => {
      rebuildSearch().catch(error => setActionResult("bad", error.message));
    });
    document.getElementById("copy-endpoint").addEventListener("click", () => {
      copyEndpoint().catch(error => setActionResult("bad", error.message));
    });
    document.getElementById("query").addEventListener("keydown", event => {
      if (event.key === "Enter") runSearch();
    });

    loadContext().catch(error => {
      setStatus("bad", error.message);
      viewer.textContent = String(error.stack || error);
    });
  </script>
</body>
</html>"""


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

        def do_PUT(self) -> None:
            self._handle("PUT")

        def do_DELETE(self) -> None:
            self._handle("DELETE")

        def _handle(self, method: str) -> None:
            try:
                with registry.lock:
                    payload = self._route(method)
                if isinstance(payload, HtmlResponse):
                    self._send_html(payload.body, status=payload.status)
                elif isinstance(payload, RawResponse):
                    self._send_raw(payload.body, payload.content_type, status=payload.status)
                elif isinstance(payload, RawFileResponse):
                    self._send_file(payload.path, payload.content_type, status=payload.status)
                elif isinstance(payload, ProxyResponse):
                    self._send_proxy(payload)
                else:
                    self._send_json(payload)
            except ApiError as exc:
                self._send_json({"error": exc.message}, status=exc.status)
            except LockedPackError as exc:
                self._send_json({"error": str(exc)}, status=HTTPStatus.LOCKED)
            except json.JSONDecodeError:
                self._send_json({"error": "invalid JSON body"}, status=HTTPStatus.BAD_REQUEST)
            except Exception as exc:  # pragma: no cover - defensive HTTP boundary.
                self._send_json({"error": str(exc)}, status=HTTPStatus.INTERNAL_SERVER_ERROR)

        def _route(self, method: str) -> Any:
            parsed = urlparse(self.path)
            parts = [unquote(part) for part in parsed.path.strip("/").split("/") if part]
            request_path = parsed.path or "/"

            if method == "GET" and parts in ([], ["project"], ["dashboard"]):
                return HtmlResponse(_project_dashboard_html())

            if method == "GET" and parts == ["health"]:
                return {"status": "ok", "version": SERVER_VERSION}

            if len(parts) >= 2 and parts[0] == "apps" and method == "GET":
                pack_id = parts[1]
                app_path = "/".join(parts[2:])
                return _raw_app_file(registry.get(pack_id), app_path, passphrase=registry.passphrase(pack_id))

            if parts and parts[0] == "api" and registry.has("repo"):
                app_config = _pack_app_config(
                    registry.get("repo"),
                    passphrase=registry.passphrase("repo"),
                    override=registry.app_proxy_override("repo"),
                )
                proxy = _proxy_config_for_request(app_config, request_path)
                if proxy is not None:
                    return _proxy_request(
                        method,
                        request_path,
                        parsed.query,
                        self._read_body(),
                        dict(self.headers.items()),
                        proxy["target"],
                    )

            if method == "POST" and parts == ["shutdown"]:
                threading.Thread(target=self.server.shutdown, daemon=True).start()
                return {"status": "shutting_down"}

            if len(parts) == 3 and parts[0] in {"projects", "packs"} and parts[2] == "context" and method == "GET":
                pack_id = parts[1]
                return _build_project_context(registry.get(pack_id), pack_id, passphrase=registry.passphrase(pack_id))

            if len(parts) == 3 and parts[0] in {"projects", "packs"} and parts[2] == "ops" and method == "GET":
                pack_id = parts[1]
                return _decode_project_ops(registry.get(pack_id), passphrase=registry.passphrase(pack_id))

            if len(parts) == 3 and parts[0] in {"projects", "packs"} and parts[2] == "readiness" and method == "GET":
                pack_id = parts[1]
                return _ops_readiness(_decode_project_ops(registry.get(pack_id), passphrase=registry.passphrase(pack_id)))

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
                    return {"id": pack_id, **inspect_pack(registry.get(pack_id), passphrase=registry.passphrase(pack_id))}
                if method == "DELETE":
                    return registry.remove(pack_id)

            if len(parts) == 3 and parts[0] == "packs" and parts[2] == "manifest" and method == "GET":
                return _pack_manifest(registry.get(parts[1]), parts[1], passphrase=registry.passphrase(parts[1]))

            if len(parts) == 3 and parts[0] == "packs" and parts[2] == "files" and method == "GET":
                query = parse_qs(parsed.query)
                include_generated = _truthy((query.get("include_generated") or ["false"])[0])
                return _pack_files(
                    registry.get(parts[1]),
                    parts[1],
                    prefix=str((query.get("prefix") or [""])[0]),
                    limit=int((query.get("limit") or ["500"])[0]),
                    cursor=int((query.get("cursor") or ["0"])[0]),
                    include_generated=include_generated,
                    passphrase=registry.passphrase(parts[1]),
                )

            if len(parts) == 3 and parts[0] == "packs" and parts[2] == "documents" and method == "GET":
                return {"documents": _pack_manifest(registry.get(parts[1]), parts[1], passphrase=registry.passphrase(parts[1]))["documents"]}

            if len(parts) == 3 and parts[0] == "packs" and parts[2] == "documents" and method in {"POST", "PUT"}:
                body = self._read_json()
                source_path = str(body.get("source_path") or body.get("path") or "")
                if not source_path:
                    raise ApiError(HTTPStatus.BAD_REQUEST, "source_path is required")
                return _upsert_pack_document(registry.get(parts[1]), source_path, body, passphrase=registry.passphrase(parts[1]))

            if len(parts) == 3 and parts[0] == "packs" and parts[2] == "verify" and method == "POST":
                return verify_pack(registry.get(parts[1]), passphrase=registry.passphrase(parts[1])).to_dict()

            if len(parts) == 3 and parts[0] == "packs" and parts[2] == "index" and method == "POST":
                body = self._read_json()
                result = build_pack_index(
                    registry.get(parts[1]),
                    output_path=body.get("output_path"),
                    embed=bool(body.get("embed", True)),
                    passphrase=registry.passphrase(parts[1]),
                )
                return {key: value for key, value in result.items() if key != "index"}

            if len(parts) == 3 and parts[0] == "packs" and parts[2] == "search" and method == "POST":
                body = self._read_json()
                query = str(body.get("query") or "")
                if not query:
                    raise ApiError(HTTPStatus.BAD_REQUEST, "query is required")
                results = search_pack(
                    registry.get(parts[1]),
                    query,
                    top_k=int(body.get("top_k", 10)),
                    language=body.get("language", "txt"),
                    index_path=body.get("index_path"),
                    build_if_missing=bool(body.get("build_if_missing", True)),
                    passphrase=registry.passphrase(parts[1]),
                    include_generated=_truthy(body.get("include_generated", False)),
                )
                for result in results:
                    source_path = result.get("source_path")
                    if source_path:
                        result["hydrate_url"] = _hydrate_url(parts[1], source_path)
                return {"results": results}

            if len(parts) == 3 and parts[0] == "packs" and parts[2] == "unpack" and method == "POST":
                body = self._read_json()
                output = body.get("output_dir")
                if not output:
                    raise ApiError(HTTPStatus.BAD_REQUEST, "output_dir is required")
                results = unpack(registry.get(parts[1]), output, passphrase=registry.passphrase(parts[1]))
                return {"results": results}

            if len(parts) == 3 and parts[0] == "packs" and parts[2] == "export" and method == "POST":
                body = self._read_json()
                parent = body.get("parent_dir") or body.get("output_parent")
                if not parent:
                    raise ApiError(HTTPStatus.BAD_REQUEST, "parent_dir is required")
                return export_distributable(
                    registry.get(parts[1]),
                    parent,
                    folder_name=body.get("folder_name"),
                    passphrase=registry.passphrase(parts[1]),
                )

            if len(parts) >= 4 and parts[0] == "packs" and parts[2] == "documents" and method == "GET":
                pack_id = parts[1]
                document_path = "/".join(parts[3:])
                return _decode_document(registry.get(pack_id), document_path, passphrase=registry.passphrase(pack_id))

            if len(parts) >= 4 and parts[0] == "packs" and parts[2] == "raw" and method == "GET":
                pack_id = parts[1]
                raw_path = "/".join(parts[3:])
                return _raw_pack_file(registry.get(pack_id), raw_path, passphrase=registry.passphrase(pack_id))

            if len(parts) >= 4 and parts[0] == "packs" and parts[2] == "documents" and method == "DELETE":
                pack_id = parts[1]
                document_path = "/".join(parts[3:])
                return _delete_pack_document(registry.get(pack_id), document_path, self._read_json(), passphrase=registry.passphrase(pack_id))

            if method == "GET" and parts and parts[0] != "api":
                try:
                    return _raw_app_file(registry.get("repo"), "/".join(parts), passphrase=registry.passphrase("repo"))
                except ApiError as exc:
                    if exc.status != HTTPStatus.NOT_FOUND:
                        raise

            raise ApiError(HTTPStatus.NOT_FOUND, "route not found")

        def _read_json(self) -> dict:
            body = self._read_body()
            if not body:
                return {}
            return json.loads(body.decode("utf-8"))

        def _read_body(self) -> bytes:
            length = int(self.headers.get("content-length", "0") or "0")
            if length <= 0:
                return b""
            return self.rfile.read(length)

        def _send_json(self, payload: Any, status: HTTPStatus = HTTPStatus.OK) -> None:
            body = json.dumps(payload, default=_json_default, indent=2).encode("utf-8")
            self.send_response(status.value)
            self.send_header("content-type", "application/json; charset=utf-8")
            self.send_header("content-length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def _send_html(self, payload: str, status: HTTPStatus = HTTPStatus.OK) -> None:
            body = payload.encode("utf-8")
            self.send_response(status.value)
            self.send_header("content-type", "text/html; charset=utf-8")
            self.send_header("content-length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def _send_raw(self, body: bytes, content_type: str, status: HTTPStatus = HTTPStatus.OK) -> None:
            self.send_response(status.value)
            self.send_header("content-type", content_type)
            self.send_header("content-length", str(len(body)))
            self.send_header("cache-control", "no-store")
            self.end_headers()
            self.wfile.write(body)

        def _send_file(self, path: Path, content_type: str, status: HTTPStatus = HTTPStatus.OK) -> None:
            self.send_response(status.value)
            self.send_header("content-type", content_type)
            self.send_header("content-length", str(path.stat().st_size))
            self.send_header("cache-control", "no-store")
            self.end_headers()
            with path.open("rb") as handle:
                shutil.copyfileobj(handle, self.wfile, length=1024 * 1024)

        def _send_proxy(self, payload: ProxyResponse) -> None:
            self.send_response(payload.status)
            sent_length = False
            for key, value in payload.headers.items():
                if key.lower() in {"connection", "transfer-encoding"}:
                    continue
                if key.lower() == "content-length":
                    sent_length = True
                self.send_header(key, value)
            if not sent_length:
                self.send_header("content-length", str(len(payload.body)))
            self.end_headers()
            self.wfile.write(payload.body)

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
