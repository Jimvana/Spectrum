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

        decoded = tmp_path / "decoded"
        status, unpacked = request(port, "POST", "/packs/docs/unpack", {"output_dir": str(decoded)})
        assert status == 200
        assert unpacked["results"][0]["checksum_ok"]
        assert (decoded / "note.md").read_bytes() == (docs / "note.md").read_bytes()

        status, packs = request(port, "GET", "/packs")
        assert status == 200
        assert packs["packs"][0]["id"] == "docs"
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)
