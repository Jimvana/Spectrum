from __future__ import annotations

import json
import threading
from http.client import HTTPConnection
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from spectrum_core import pack
import spectrum_server.app as app_module
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


def bytes_request(port: int, method: str, path: str) -> tuple[int, str, bytes]:
    connection = HTTPConnection("127.0.0.1", port, timeout=5)
    connection.request(method, path)
    response = connection.getresponse()
    content_type = response.getheader("content-type", "")
    data = response.read()
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
        assert searched["results"][0]["hydrate_url"] == "/packs/docs/documents/note.md"

        status, manifest = request(port, "GET", "/packs/docs/manifest")
        assert status == 200
        assert manifest["id"] == "docs"
        assert manifest["documents"][0]["source_path"] == "note.md"
        assert manifest["documents"][0]["hydrate_url"] == "/packs/docs/documents/note.md"
        assert manifest["external_entries"] == []

        status, documents = request(port, "GET", "/packs/docs/documents")
        assert status == 200
        assert documents["documents"][0]["source_path"] == "note.md"

        decoded = tmp_path / "decoded"
        status, unpacked = request(port, "POST", "/packs/docs/unpack", {"output_dir": str(decoded)})
        assert status == 200
        assert unpacked["results"][0]["checksum_ok"]
        assert (decoded / "note.md").read_bytes() == (docs / "note.md").read_bytes()

        exports = tmp_path / "exports"
        exports.mkdir()
        status, exported = request(port, "POST", "/packs/docs/export", {"parent_dir": str(exports)})
        assert status == 200
        assert exported["valid"]
        assert Path(exported["output_dir"]).name == "docs"
        assert (Path(exported["output_dir"]) / "note.md").read_bytes() == (docs / "note.md").read_bytes()

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


def test_server_serves_raw_pack_files_and_app_assets(tmp_path: Path) -> None:
    docs = tmp_path / "site"
    public = docs / "public"
    assets = public / "assets"
    assets.mkdir(parents=True)
    (public / "index.html").write_text('<script src="app.js"></script><img src="assets/logo.png">', encoding="utf-8")
    (public / "app.js").write_text("window.siteLoaded = true;\n", encoding="utf-8")
    png = b"\x89PNG\r\n\x1a\n" + bytes(range(32))
    (assets / "logo.png").write_bytes(png)
    pack_path = tmp_path / "site.specpack"
    pack(docs, pack_path, include_all=True)

    registry = PackRegistry()
    registry.add("repo", pack_path)
    server = SpectrumServer(("127.0.0.1", 0), create_handler(registry), quiet=True)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    port = server.server_address[1]

    try:
        status, content_type, html = text_request(port, "GET", "/apps/repo/")
        assert status == 200
        assert "text/html" in content_type
        assert "app.js" in html

        status, content_type, script = text_request(port, "GET", "/apps/repo/app.js")
        assert status == 200
        assert "javascript" in content_type
        assert "siteLoaded" in script

        status, content_type, root_script = text_request(port, "GET", "/app.js")
        assert status == 200
        assert "javascript" in content_type
        assert "siteLoaded" in root_script

        status, api_error = request(port, "GET", "/api/snapshot")
        assert status == 404
        assert api_error["error"] == "route not found"

        status, content_type, image = bytes_request(port, "GET", "/apps/repo/assets/logo.png")
        assert status == 200
        assert content_type == "image/png"
        assert image == png

        status, content_type, raw_html = text_request(port, "GET", "/packs/repo/raw/public/index.html")
        assert status == 200
        assert "text/html" in content_type
        assert "assets/logo.png" in raw_html
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


def test_server_files_endpoint_filters_generated_paths(tmp_path: Path) -> None:
    docs = tmp_path / "repo"
    (docs / "src").mkdir(parents=True)
    (docs / "dist").mkdir()
    (docs / "src" / "app.py").write_text("print('source')\n", encoding="utf-8")
    (docs / "dist" / "bundle.js").write_text("console.log('generated')\n", encoding="utf-8")
    image = b"\x89PNG\r\n\x1a\n" + bytes(range(8))
    (docs / "src" / "logo.png").write_bytes(image)
    pack_path = tmp_path / "repo.specpack"
    pack(docs, pack_path, include_all=True)

    registry = PackRegistry()
    registry.add("repo", pack_path)
    server = SpectrumServer(("127.0.0.1", 0), create_handler(registry), quiet=True)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    port = server.server_address[1]

    try:
        status, files = request(port, "GET", "/packs/repo/files")
        assert status == 200
        assert {item["source_path"] for item in files["files"]} == {"src/app.py", "src/logo.png"}
        assert files["files"][0]["raw_url"].startswith("/packs/repo/raw/")
        by_path = {item["source_path"]: item for item in files["files"]}
        assert by_path["src/app.py"]["storage_kind"] == "encoded"
        assert by_path["src/logo.png"]["storage_kind"] == "external_blob"
        assert by_path["src/logo.png"]["external_reason"] == "media_extension"

        status, all_files = request(port, "GET", "/packs/repo/files?include_generated=true")
        assert status == 200
        assert {item["source_path"] for item in all_files["files"]} == {
            "dist/bundle.js",
            "src/app.py",
            "src/logo.png",
        }
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


def test_server_caches_decoded_raw_files(tmp_path: Path, monkeypatch) -> None:
    docs = tmp_path / "docs"
    docs.mkdir()
    (docs / "note.md").write_text("Cached raw document.\n", encoding="utf-8")
    pack_path = tmp_path / "docs.specpack"
    pack(docs, pack_path)
    calls = 0
    original_decode_member = app_module.decode_member
    app_module._DECODE_CACHE.invalidate()

    def counting_decode_member(*args, **kwargs):
        nonlocal calls
        calls += 1
        return original_decode_member(*args, **kwargs)

    monkeypatch.setattr(app_module, "decode_member", counting_decode_member)

    registry = PackRegistry()
    registry.add("repo", pack_path)
    server = SpectrumServer(("127.0.0.1", 0), create_handler(registry), quiet=True)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    port = server.server_address[1]

    try:
        first = text_request(port, "GET", "/packs/repo/raw/note.md")
        second = text_request(port, "GET", "/packs/repo/raw/note.md")
        assert first == second
        assert calls == 1
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)
        app_module._DECODE_CACHE.invalidate()


def test_server_proxies_configured_app_backend_routes(tmp_path: Path) -> None:
    class BackendHandler(BaseHTTPRequestHandler):
        def log_message(self, format: str, *args) -> None:  # noqa: A002
            return

        def do_GET(self) -> None:
            if self.path != "/api/snapshot":
                self.send_response(404)
                self.end_headers()
                return
            body = json.dumps({"from_backend": True}).encode("utf-8")
            self.send_response(200)
            self.send_header("content-type", "application/json; charset=utf-8")
            self.send_header("content-length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

    backend = ThreadingHTTPServer(("127.0.0.1", 0), BackendHandler)
    backend_thread = threading.Thread(target=backend.serve_forever, daemon=True)
    backend_thread.start()
    backend_url = f"http://127.0.0.1:{backend.server_address[1]}"

    docs = tmp_path / "site"
    public = docs / "public"
    config_dir = docs / ".spectrum-project"
    public.mkdir(parents=True)
    config_dir.mkdir(parents=True)
    (public / "index.html").write_text("app", encoding="utf-8")
    (config_dir / "app.json").write_text(
        json.dumps({"backend": {"mode": "proxy", "target": backend_url, "routes": ["/api/*"]}}),
        encoding="utf-8",
    )
    pack_path = tmp_path / "site.specpack"
    pack(docs, pack_path, include_all=True)

    registry = PackRegistry()
    registry.add("repo", pack_path)
    server = SpectrumServer(("127.0.0.1", 0), create_handler(registry), quiet=True)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    port = server.server_address[1]

    try:
        status, proxied = request(port, "GET", "/api/snapshot")
        assert status == 200
        assert proxied == {"from_backend": True}

        status, manifest = request(port, "GET", "/packs/repo/manifest")
        assert status == 200
        assert manifest["app"]["backend"]["target"] == backend_url
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)
        backend.shutdown()
        backend.server_close()
        backend_thread.join(timeout=5)


def test_server_builds_project_context_bundle(tmp_path: Path) -> None:
    docs = tmp_path / "project"
    context = docs / ".spectrum-project"
    context.mkdir(parents=True)
    (context / "project.md").write_text("# Project\n\nByteSpectrum site.\n", encoding="utf-8")
    (context / "deploy.md").write_text("# Deploy\n\nRun the production deploy check.\n", encoding="utf-8")
    (context / "secrets.refs.md").write_text("# Secret References\n\nUse ssh-agent.\n", encoding="utf-8")
    (context / "ops.json").write_text(
        json.dumps(
            {
                "sites": [
                    {
                        "name": "example-site",
                        "domains": ["example.com"],
                        "ssh": {
                            "host": "203.0.113.10",
                            "user": "deploy",
                            "identity_file": "C:\\Users\\example\\.ssh\\spectrum_example_ed25519",
                        },
                        "deploy": {"remote_path": "/var/www/spectrum"},
                    }
                ],
                "policy": {"ssh_requires_confirmation": True, "deploy_requires_confirmation": True},
            }
        ),
        encoding="utf-8",
    )
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
        assert context_bundle["ops"]["data"]["sites"][0]["name"] == "example-site"
        assert context_bundle["readiness"]["ssh"]["ready"]

        status, ops = request(port, "GET", "/projects/repo/ops")
        assert status == 200
        assert ops["path"] == ".spectrum-project/ops.json"
        assert ops["data"]["sites"][0]["ssh"]["user"] == "deploy"

        status, readiness = request(port, "GET", "/projects/repo/readiness")
        assert status == 200
        assert readiness["deploy"]["ready"]
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


def test_server_upserts_document_into_served_pack(tmp_path: Path) -> None:
    docs = tmp_path / "project"
    docs.mkdir()
    (docs / "project.md").write_text("# Project\n\nServed pack update.\n", encoding="utf-8")
    pack_path = tmp_path / "project.specpack"
    pack(docs, pack_path)

    registry = PackRegistry()
    registry.add("repo", pack_path)
    server = SpectrumServer(("127.0.0.1", 0), create_handler(registry), quiet=True)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    port = server.server_address[1]

    ops = {
        "sites": [
            {
                "name": "example-site",
                "ssh": {
                    "host": "203.0.113.10",
                    "user": "deploy",
                    "identity_file": "C:\\Users\\example\\.ssh\\spectrum_example_ed25519",
                },
                "deploy": {"remote_path": "/var/www/spectrum"},
            }
        ],
        "policy": {"ssh_requires_confirmation": True, "deploy_requires_confirmation": True},
    }

    try:
        status, updated = request(
            port,
            "POST",
            "/packs/repo/documents",
            {
                "source_path": ".spectrum-project/ops.json",
                "content": json.dumps(ops),
                "replace": True,
                "rebuild_index": False,
            },
        )
        assert status == 200
        assert updated["verify"]["valid"]
        assert updated["document"]["path"] == ".spectrum-project/ops.json"
        assert updated["file"]["storage_kind"] == "encoded"

        status, hydrated = request(port, "GET", "/packs/repo/documents/.spectrum-project/ops.json")
        assert status == 200
        assert json.loads(hydrated["content"])["sites"][0]["name"] == "example-site"

        status, live_ops = request(port, "GET", "/projects/repo/ops")
        assert status == 200
        assert live_ops["missing"] is False
        assert live_ops["data"]["sites"][0]["ssh"]["user"] == "deploy"

        status, readiness = request(port, "GET", "/projects/repo/readiness")
        assert status == 200
        assert readiness["ssh"]["ready"]
        assert readiness["deploy"]["ready"]

        status, deleted = request(
            port,
            "DELETE",
            "/packs/repo/documents/.spectrum-project/ops.json",
            {"rebuild_index": False},
        )
        assert status == 200
        assert deleted["removed"]
        assert deleted["archived_to"] == ".spectrum-trash/trash.jsonl"
        assert deleted["verify"]["valid"]

        status, deleted_ops = request(port, "GET", "/projects/repo/ops")
        assert status == 200
        assert deleted_ops["missing"] is True

        status, trash = request(port, "GET", "/packs/repo/documents/.spectrum-trash/trash.jsonl")
        assert status == 200
        records = [json.loads(line) for line in trash["content"].splitlines() if line]
        assert records[-1]["source_path"] == ".spectrum-project/ops.json"
        assert json.loads(records[-1]["content"])["sites"][0]["name"] == "example-site"
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


def test_server_batch_upserts_documents_verifies_changed_and_indexes_once(tmp_path: Path, monkeypatch) -> None:
    docs = tmp_path / "project"
    docs.mkdir()
    (docs / "README.md").write_text("# Project\n\nOriginal pack.\n", encoding="utf-8")
    pack_path = tmp_path / "project.specpack"
    pack(docs, pack_path)

    def fail_full_verify(*args, **kwargs):
        raise AssertionError("full verify should not run for verify=changed")

    monkeypatch.setattr(app_module, "verify_pack", fail_full_verify)

    registry = PackRegistry()
    registry.add("repo", pack_path)
    server = SpectrumServer(("127.0.0.1", 0), create_handler(registry), quiet=True)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    port = server.server_address[1]

    image = b"\x89PNG\r\n\x1a\n" + bytes(range(24))
    try:
        status, updated = request(
            port,
            "POST",
            "/packs/repo/documents/batch",
            {
                "replace": True,
                "verify": "changed",
                "rebuild_index": True,
                "documents": [
                    {"source_path": "README.md", "content": "# Project\n\nUpdated batch text.\n"},
                    {"source_path": "notes/agent.md", "content": "Batch searchable marker.\n"},
                    {"source_path": "assets/logo.png", "content_bytes": list(image)},
                ],
            },
        )
        assert status == 200
        assert updated["append"]["appended_entries"] == 3
        assert updated["verify"]["valid"]
        assert updated["verify"]["chunks_checked"] == 3
        assert updated["index"]["embedded"]
        by_path = {item["source_path"]: item for item in updated["files"]}
        assert by_path["README.md"]["storage_kind"] == "encoded"
        assert by_path["notes/agent.md"]["storage_kind"] == "encoded"
        assert by_path["assets/logo.png"]["storage_kind"] == "external_blob"

        status, searched = request(port, "POST", "/packs/repo/search", {"query": "batch searchable marker", "top_k": 1})
        assert status == 200
        assert searched["results"][0]["source_path"] == "notes/agent.md"

        status, manifest = request(port, "GET", "/packs/repo/manifest")
        assert status == 200
        assert {entry["source_path"] for entry in manifest["external_entries"]} == {"assets/logo.png"}

        status, documents = request(port, "GET", "/packs/repo/documents")
        assert status == 200
        assert {entry["source_path"] for entry in documents["documents"]} == {"README.md", "notes/agent.md"}

        status, _content_type, raw_image = bytes_request(port, "GET", "/packs/repo/raw/assets/logo.png")
        assert status == 200
        assert raw_image == image
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


def test_server_shutdown_endpoint_stops_server(tmp_path: Path) -> None:
    docs = tmp_path / "docs"
    docs.mkdir()
    (docs / "note.md").write_text("Shutdown test.\n", encoding="utf-8")
    pack_path = tmp_path / "docs.specpack"
    pack(docs, pack_path)

    registry = PackRegistry()
    registry.add("repo", pack_path)
    server = SpectrumServer(("127.0.0.1", 0), create_handler(registry), quiet=True)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    port = server.server_address[1]

    try:
        status, shutdown = request(port, "POST", "/shutdown")
        assert status == 200
        assert shutdown["status"] == "shutting_down"
        thread.join(timeout=5)
        assert not thread.is_alive()
    finally:
        server.server_close()


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
