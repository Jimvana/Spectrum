# Custom Agent Instructions For Spectrum

These instructions are for any AI agent using Spectrum as local project context.
Spectrum stores a project as a compact, lossless, searchable `.specpack` and
serves it through a local HTTP API. Treat the served API as the preferred way to
discover context, search, and hydrate exact files before making assumptions.

## Operating Model

Use this flow by default:

```text
check server -> fetch project context -> search -> hydrate exact files -> act -> verify/update pack when needed
```

Important rules:

- Do not rely on snippets alone for implementation decisions. Search results are
  candidate pointers; hydrate the exact document or raw file before trusting it.
- Prefer the project context bundle first when the pack is served as `repo`:
  `GET /projects/repo/context`.
- Ask before using SSH, production deploy commands, secrets, destructive file
  operations, or commands that mutate a remote system.
- Never store raw secrets in project notes. Store references such as key aliases,
  vault item names, env file locations, or ssh-agent requirements.
- If you add, replace, or delete pack documents through the API, verify the pack
  and rebuild the embedded index unless the user explicitly wants a fast,
  temporary mutation.

## Installation And Health Checks

Requirements:

```text
Node.js 18+
Python 3.10+
```

Check the local install:

```bash
spectrum doctor
spectrum doctor --json
```

Find running Spectrum servers:

```bash
spectrum hub -v
spectrum hub -v --ports 7777,7778 --json
```

Probe a known server directly:

```bash
curl http://127.0.0.1:7777/health
curl http://127.0.0.1:7777/packs
```

Expected health response:

```json
{"status":"ok","version":"0.1.0"}
```

## Fast Start

Create and serve a pack in one guided workflow:

```bash
spectrum load
```

Non-interactive:

```bash
spectrum load ./my-repo ./my-repo.specpack --yes
```

Pack only, do not start the API:

```bash
spectrum load ./my-repo ./my-repo.specpack --yes --no-serve
```

Manual workflow:

```bash
spectrum pack ./my-repo ./my-repo.specpack --json
spectrum index ./my-repo.specpack --embed --json
spectrum verify ./my-repo.specpack --json
spectrum serve ./my-repo.specpack --port 7777
```

When `spectrum serve ./my-repo.specpack` is used, the positional pack is
registered as pack id `repo`.

## Project Packs

Use project packs when an agent needs durable context files, runbooks, deploy
notes, and cross-platform launchers.

Create a project pack:

```bash
spectrum project init ./my-project --name "My Project"
```

This creates a default pack at:

```text
./my-project/.spectrum/project.specpack
```

Serve it:

```bash
spectrum project serve ./my-project/.spectrum/project.specpack --port 7777
```

Restart a served project pack:

```bash
spectrum project restart ./my-project/.spectrum/project.specpack --port 7777
```

Stop an existing server without restarting:

```bash
spectrum project restart ./my-project/.spectrum/project.specpack --port 7777 --no-start
```

Append durable notes or source folders:

```bash
spectrum project add ./my-project/.spectrum/project.specpack ./new-notes --json
```

Replace existing source paths intentionally:

```bash
spectrum project add ./my-project/.spectrum/project.specpack ./new-notes --replace --json
```

Standard project context files are embedded under `.spectrum-project/`:

```text
project.md
status.md
agent-rules.md
architecture.md
deploy.md
server.md
ssh.md
secrets.refs.md
ops.json
runbook.md
decisions.md
```

Always fetch this bundle first:

```bash
curl http://127.0.0.1:7777/projects/repo/context
```

Useful project endpoints:

```text
GET /projects/repo/context
GET /projects/repo/ops
GET /projects/repo/readiness
GET /project
```

`/projects/repo/context` returns present context documents, a `missing` list,
readiness data, and convenience fields such as `project`, `status`, `rules`,
`architecture`, `deploy`, `server`, `ssh`, `secret_references`, `runbook`, and
`decisions`.

## Core CLI Commands

Encode and decode a single `.spec` file:

```bash
spectrum encode ./source.py ./source.py.spec --json
spectrum decode ./source.py.spec ./source.py --json
```

Create a `.specpack`:

```bash
spectrum pack ./docs ./docs.specpack --json
```

Include all non-`.spec` files, including assets and generated files:

```bash
spectrum pack ./site ./site.specpack --all --json
```

Append to an existing pack:

```bash
spectrum append ./docs.specpack ./project-notes --json
```

Replace existing packed paths:

```bash
spectrum append ./docs.specpack ./project-notes --replace --json
```

Inspect:

```bash
spectrum inspect ./docs.specpack --json
```

Verify lossless decode:

```bash
spectrum verify ./docs.specpack --json
```

Build an embedded search index:

```bash
spectrum index ./docs.specpack --embed --json
```

Search from the CLI:

```bash
spectrum search ./docs.specpack "authentication middleware bearer token" --top 5 --json
```

Restore all files:

```bash
spectrum unpack ./docs.specpack ./docs-restored --json
```

Serve the local API:

```bash
spectrum serve ./docs.specpack --port 7777
```

Serve multiple packs:

```bash
spectrum serve --pack docs=./docs.specpack --pack notes=./notes.specpack --port 7777
```

## HTTP API

Base URL:

```text
http://127.0.0.1:7777
```

General endpoints:

```text
GET  /health
GET  /project
GET  /dashboard
POST /shutdown
```

Pack registry:

```text
GET    /packs
POST   /packs
GET    /packs/{pack_id}
DELETE /packs/{pack_id}
```

Register a pack:

```bash
curl -X POST http://127.0.0.1:7777/packs \
  -H 'content-type: application/json' \
  -d '{"id":"docs","path":"./docs.specpack"}'
```

Search and hydrate:

```text
POST /packs/{pack_id}/search
GET  /packs/{pack_id}/documents/{source_path}
GET  /packs/{pack_id}/raw/{source_path}
```

Search request:

```bash
curl -X POST http://127.0.0.1:7777/packs/repo/search \
  -H 'content-type: application/json' \
  -d '{"query":"authentication middleware","top_k":5}'
```

Search options:

```json
{
  "query": "authentication middleware",
  "top_k": 5,
  "language": "txt",
  "index_path": null,
  "build_if_missing": true,
  "include_generated": false
}
```

Hydrate the selected result:

```bash
curl http://127.0.0.1:7777/packs/repo/documents/src/auth/middleware.py
```

Use `raw` for browser assets, binary files, and exact content types:

```bash
curl http://127.0.0.1:7777/packs/repo/raw/public/app.js
```

For paths with spaces or special characters, URL-encode the path.

Manifest and file listing:

```text
GET /packs/{pack_id}/manifest
GET /packs/{pack_id}/files
GET /packs/{pack_id}/documents
```

List files with filters:

```bash
curl 'http://127.0.0.1:7777/packs/repo/files?prefix=src&limit=100&cursor=0'
curl 'http://127.0.0.1:7777/packs/repo/files?include_generated=true'
```

By default, generated paths are filtered out of `/files` and search. Use
`include_generated=true` only when generated assets are relevant.

Pack maintenance:

```text
POST /packs/{pack_id}/verify
POST /packs/{pack_id}/index
POST /packs/{pack_id}/unpack
POST /packs/{pack_id}/export
```

Examples:

```bash
curl -X POST http://127.0.0.1:7777/packs/repo/verify

curl -X POST http://127.0.0.1:7777/packs/repo/index \
  -H 'content-type: application/json' \
  -d '{"embed":true}'

curl -X POST http://127.0.0.1:7777/packs/repo/unpack \
  -H 'content-type: application/json' \
  -d '{"output_dir":"./restored"}'

curl -X POST http://127.0.0.1:7777/packs/repo/export \
  -H 'content-type: application/json' \
  -d '{"parent_dir":"./exports","folder_name":"repo-restored"}'
```

Document mutation:

```text
POST   /packs/{pack_id}/documents
PUT    /packs/{pack_id}/documents
DELETE /packs/{pack_id}/documents/{source_path}
```

Add or replace a document:

```bash
curl -X POST http://127.0.0.1:7777/packs/repo/documents \
  -H 'content-type: application/json' \
  -d '{"source_path":".spectrum-project/status.md","content":"# Status\n\nUpdated notes.\n","replace":true,"rebuild_index":true}'
```

Delete a document:

```bash
curl -X DELETE http://127.0.0.1:7777/packs/repo/documents/.spectrum-project/status.md \
  -H 'content-type: application/json' \
  -d '{"reason":"superseded","rebuild_index":true}'
```

Deletes are archived into `.spectrum-trash/trash.jsonl` inside the pack.

## Served App Assets And Proxying

If a pack contains app files, the server can serve them directly.

App URLs:

```text
GET /apps/{pack_id}/
GET /apps/{pack_id}/{path}
```

For pack id `repo`, root paths also fall back to app assets:

```text
GET /
GET /app.js
GET /assets/logo.png
```

Default app entry candidates include:

```text
public/index.html
index.html
dist/index.html
build/index.html
```

An app manifest can be stored at one of:

```text
.spectrum-project/app.json
.spectrum/app.json
spectrum.app.json
```

Proxy backend API routes with:

```json
{
  "entry": "public/index.html",
  "backend": {
    "mode": "proxy",
    "target": "http://127.0.0.1:3000",
    "routes": ["/api/*"]
  }
}
```

When served as `repo`, matching `/api/*` requests are forwarded to the target.

## Encrypted Packs

Create an encrypted pack:

```bash
spectrum pack ./docs ./docs.specpack --encrypt --hint "non-secret hint" --json
```

Serve or operate on an encrypted pack:

```bash
spectrum serve ./docs.specpack --unlock --port 7777
spectrum search ./docs.specpack "deploy notes" --unlock --json
spectrum verify ./docs.specpack --unlock --json
```

`SPECTRUM_PASSPHRASE` is supported but should be used cautiously because
environment variables can leak through process listings, shells, or logs.

## Direct Python Server During Development

From this repository checkout, the server can be run without the npm wrapper:

```bash
PYTHONPATH="packages/core/src:packages/index/src:packages/server/src" \
python -m spectrum_server.main --pack repo=./docs.specpack --port 7777
```

On PowerShell:

```powershell
$env:PYTHONPATH="packages/core/src;packages/index/src;packages/server/src"
python -m spectrum_server.main --pack repo=./docs.specpack --port 7777
```

Server implementation files:

```text
packages/server/src/spectrum_server/main.py
packages/server/src/spectrum_server/app.py
```

The server uses `ThreadingHTTPServer` and keeps registered pack paths in an
in-memory `PackRegistry`. Restart or re-register if you need a clean registry.

## Troubleshooting

Port already in use:

```bash
spectrum hub -v --ports 7777 --json
spectrum project restart ./my-project/.spectrum/project.specpack --port 7777 --force
```

Unknown pack:

```bash
curl http://127.0.0.1:7777/packs
```

If `repo` is missing, serve the pack positionally or register it:

```bash
spectrum serve ./my-project.specpack --port 7777
```

or:

```bash
curl -X POST http://127.0.0.1:7777/packs \
  -H 'content-type: application/json' \
  -d '{"id":"repo","path":"./my-project.specpack"}'
```

Search looks stale after append:

```bash
spectrum index ./my-project.specpack --embed --json
```

or through HTTP:

```bash
curl -X POST http://127.0.0.1:7777/packs/repo/index \
  -H 'content-type: application/json' \
  -d '{"embed":true}'
```

Locked encrypted pack:

```bash
spectrum serve ./my-project.specpack --unlock --port 7777
```

Need exact files outside the API:

```bash
spectrum unpack ./my-project.specpack ./restored --json
```

## Best Agent Experience Checklist

At the beginning of a task:

1. Run or request `spectrum hub -v` to discover servers.
2. If a server is running, fetch `/health`, `/packs`, and `/projects/repo/context`.
3. Read `agent-rules.md`, `status.md`, `deploy.md`, `server.md`, `ssh.md`, and
   `secrets.refs.md` if present.
4. Search for task-specific terms with `/packs/repo/search`.
5. Hydrate each selected `hydrate_url` before making edits or recommendations.

During work:

1. Use `/packs/repo/files` to browse source paths without unpacking everything.
2. Use `/packs/repo/raw/...` for binary assets and app previews.
3. Keep generated files out of searches unless they are directly relevant.
4. Confirm before using ops data for SSH, deployment, production logs, or secret
   access.

After durable work:

1. Add or update notes in `.spectrum-project/status.md`, `runbook.md`, or
   `decisions.md` when the new context will matter later.
2. Verify the pack.
3. Rebuild the embedded index.
4. If a long-running server behaves unexpectedly after pack changes, restart it.
