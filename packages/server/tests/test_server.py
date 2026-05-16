from __future__ import annotations

import json
import threading
from http.client import HTTPConnection
from pathlib import Path

from spectrum_core import pack
from spectrum_server.app import PackRegistry, SpectrumServer, create_handler


def request(port: int, method: str, path: str, body: dict | None = None) -> tuple[int, dict]:
    connection = HTTPConnection("127.0.0.1", port, timeout=5)
    payload = json.dumps(body).encode("utf-8") if body is not None else None
    headers = {"content-type": "application/json"} if body is not None else {}
    connection.request(method, path, body=payload, headers=headers)
    response = connection.getresponse()
    data = json.loads(response.read().decode("utf-8"))
    connection.close()
    return response.status, data


def text_request(port: int, method: str, path: str) -> tuple[int, str, str]:
    connection = HTTPConnection("127.0.0.1", port, timeout=5)
    connection.request(method, path)
    response = connection.getresponse()
    content_type = response.getheader("content-type", "")
    data = response.read().decode("utf-8")
    connection.close()
    return response.status, content_type, data


def test_server_pack_lifecycle(tmp_path: Path) -> None:
    docs = tmp_path / "docs"
    docs.mkdir()
    (docs / "note.md").write_bytes(b"# Server\r\n\r\nHTTP round trip.\r\n")
    pack_path = tmp_path / "docs.specpack"
    pack(docs, pack_path)

    registry = PackRegistry()
    server = SpectrumServer(("127.0.0.1", 0), create_handler(registry), quiet=True)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    port = server.server_address[1]

    try:
        status, health = request(port, "GET", "/health")
        assert status == 200
        assert health["status"] == "ok"

        status, registered = request(port, "POST", "/packs", {"id": "docs", "path": str(pack_path)})
        assert status == 200
        assert registered["id"] == "docs"

        status, inspected = request(port, "GET", "/packs/docs")
        assert status == 200
        assert inspected["entries"] == 1

        status, verified = request(port, "POST", "/packs/docs/verify")
        assert status == 200
        assert verified["valid"]

        status, indexed = request(port, "POST", "/packs/docs/index", {"embed": True})
        assert status == 200
        assert indexed["embedded"]

        status, searched = request(port, "POST", "/packs/docs/search", {"query": "server http round trip", "top_k": 1})
        assert status == 200
        assert searched["results"][0]["path"].endswith("note.md.spec")
        assert searched["results"][0]["source_path"] == "note.md"

        decoded = tmp_path / "decoded"
        status, unpacked = request(port, "POST", "/packs/docs/unpack", {"output_dir": str(decoded)})
        assert status == 200
        assert unpacked["results"][0]["checksum_ok"]
        assert (decoded / "note.md").read_bytes() == (docs / "note.md").read_bytes()

        status, packs = request(port, "GET", "/packs")
        assert status == 200
        assert packs["packs"][0]["id"] == "docs"

        status, document = request(port, "GET", "/packs/docs/documents/note.md")
        assert status == 200
        assert document["path"] == "note.md"
        assert document["checksum_ok"]
        assert document["content"] == "# Server\r\n\r\nHTTP round trip.\r\n"
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


def test_server_reads_nested_document_without_full_unpack(tmp_path: Path) -> None:
    docs = tmp_path / "docs"
    nested = docs / "notes"
    nested.mkdir(parents=True)
    (nested / "memory.md").write_bytes(b"Nested document lookup.\n")
    pack_path = tmp_path / "docs.specpack"
    pack(docs, pack_path)

    registry = PackRegistry()
    server = SpectrumServer(("127.0.0.1", 0), create_handler(registry), quiet=True)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    port = server.server_address[1]

    try:
        assert request(port, "POST", "/packs", {"id": "docs", "path": str(pack_path)})[0] == 200
        status, document = request(port, "GET", "/packs/docs/documents/notes/memory.md")
        assert status == 200
        assert document["path"] == "notes/memory.md"
        assert document["content"] == "Nested document lookup.\n"
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


def test_server_builds_project_context_bundle(tmp_path: Path) -> None:
    docs = tmp_path / "project"
    context = docs / ".spectrum-project"
    context.mkdir(parents=True)
    (context / "project.md").write_text("# Project\n\nByteSpectrum site.\n", encoding="utf-8")
    (context / "deploy.md").write_text("# Deploy\n\nRun the production deploy check.\n", encoding="utf-8")
    (context / "secrets.refs.md").write_text("# Secret References\n\nUse ssh-agent.\n", encoding="utf-8")
    pack_path = tmp_path / "project.specpack"
    pack(docs, pack_path)

    registry = PackRegistry()
    server = SpectrumServer(("127.0.0.1", 0), create_handler(registry), quiet=True)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    port = server.server_address[1]

    try:
        assert request(port, "POST", "/packs", {"id": "repo", "path": str(pack_path)})[0] == 200
        status, context_bundle = request(port, "GET", "/projects/repo/context")
        assert status == 200
        assert context_bundle["id"] == "repo"
        assert "ByteSpectrum site" in context_bundle["project"]
        assert "production deploy" in context_bundle["deploy"]
        assert "ssh-agent" in context_bundle["secret_references"]
        assert "status.md" in context_bundle["missing"]
        assert context_bundle["documents"][0]["path"] == ".spectrum-project/project.md"
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


def test_server_serves_project_dashboard(tmp_path: Path) -> None:
    docs = tmp_path / "project"
    context = docs / ".spectrum-project"
    context.mkdir(parents=True)
    (context / "project.md").write_text("# Project\n\nDashboard test.\n", encoding="utf-8")
    pack_path = tmp_path / "project.specpack"
    pack(docs, pack_path)

    registry = PackRegistry()
    registry.add("repo", pack_path)
    server = SpectrumServer(("127.0.0.1", 0), create_handler(registry), quiet=True)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    port = server.server_address[1]

    try:
        status, content_type, html = text_request(port, "GET", "/project")
        assert status == 200
        assert "text/html" in content_type
        assert "Spectrum Project" in html
        assert "/projects/${packId}/context" in html
        assert "/packs/${packId}/search" in html
        assert "Verify Pack" in html
        assert "Rebuild Search" in html
        assert "copy-endpoint" in html
        assert "expectedContextFiles" in html
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)
