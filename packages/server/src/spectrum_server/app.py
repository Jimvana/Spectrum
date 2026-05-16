from __future__ import annotations

import json
import tempfile
from dataclasses import asdict, dataclass, is_dataclass
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import unquote, urlparse

from spectrum_core import SpectrumPack, decode_member, inspect_pack, unpack, verify_pack
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
    "runbook.md",
    "decisions.md",
]
PROJECT_CONTEXT_DIR = ".spectrum-project"
PROJECT_FIELD_NAMES = {
    "project.md": "project",
    "status.md": "status",
    "agent-rules.md": "rules",
    "architecture.md": "architecture",
    "deploy.md": "deploy",
    "server.md": "server",
    "ssh.md": "ssh",
    "secrets.refs.md": "secret_references",
    "runbook.md": "runbook",
    "decisions.md": "decisions",
}


@dataclass(frozen=True)
class HtmlResponse:
    body: str
    status: HTTPStatus = HTTPStatus.OK


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


def _decode_document(pack_path: Path, source_path: str) -> dict:
    with tempfile.TemporaryDirectory(prefix="spectrum-server-doc-") as tmp_name:
        tmp = Path(tmp_name)
        output = tmp / "document"
        with SpectrumPack.open(pack_path) as opened:
            entry = opened.find_entry(source_path)
            if entry is None:
                raise ApiError(HTTPStatus.NOT_FOUND, f"document not found: {source_path}")
        result = decode_member(pack_path, source_path, output)
        data = output.read_bytes()
        return {
            "path": entry.source,
            "id": entry.source_id,
            "metadata": entry.metadata or {},
            "content": data.decode("utf-8", errors="replace"),
            "content_bytes": list(data),
            "checksum_ok": result.checksum_ok,
            "length_ok": result.length_ok,
        }


def _build_project_context(pack_path: Path, pack_id: str) -> dict:
    documents = []
    missing = []
    fields: dict[str, str] = {}

    with SpectrumPack.open(pack_path) as opened:
        available = {entry.source for entry in opened.entries}

    for filename in PROJECT_CONTEXT_FILES:
        candidates = [f"{PROJECT_CONTEXT_DIR}/{filename}", filename]
        source_path = next((candidate for candidate in candidates if candidate in available), None)
        if source_path is None:
            missing.append(filename)
            continue
        decoded = _decode_document(pack_path, source_path)
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

    return {
        "id": pack_id,
        "pack_path": str(pack_path),
        "context_dir": PROJECT_CONTEXT_DIR,
        "documents": documents,
        "missing": missing,
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

        def do_DELETE(self) -> None:
            self._handle("DELETE")

        def _handle(self, method: str) -> None:
            try:
                payload = self._route(method)
                if isinstance(payload, HtmlResponse):
                    self._send_html(payload.body, status=payload.status)
                else:
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

            if method == "GET" and parts in ([], ["project"], ["dashboard"]):
                return HtmlResponse(_project_dashboard_html())

            if method == "GET" and parts == ["health"]:
                return {"status": "ok", "version": SERVER_VERSION}

            if len(parts) == 3 and parts[0] in {"projects", "packs"} and parts[2] == "context" and method == "GET":
                pack_id = parts[1]
                return _build_project_context(registry.get(pack_id), pack_id)

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

            if len(parts) >= 4 and parts[0] == "packs" and parts[2] == "documents" and method == "GET":
                pack_id = parts[1]
                document_path = "/".join(parts[3:])
                return _decode_document(registry.get(pack_id), document_path)

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

        def _send_html(self, payload: str, status: HTTPStatus = HTTPStatus.OK) -> None:
            body = payload.encode("utf-8")
            self.send_response(status.value)
            self.send_header("content-type", "text/html; charset=utf-8")
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
