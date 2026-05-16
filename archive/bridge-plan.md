# Spectrum Adoption Bridge Plan

Spectrum is already published on npm as `spectrumstore`, so the bridge is not
about proving that installation works. The remaining work is to turn the
published CLI into a complete, low-risk path for developers who want to use
Spectrum as a local agent/code-retrieval layer.

## Goal

Make this workflow boring and copy-pasteable:

```powershell
npm install -g spectrumstore
spectrum doctor
spectrum pack ./my-repo ./my-repo.specpack --json
spectrum serve ./my-repo.specpack --port 7777
```

Then let an agent, app, or framework retrieve and hydrate source through a small
stable local API.

## Current Position

- `npm install -g spectrumstore` works.
- The published package exposes both `spectrum` and `spectrumstore`.
- The CLI supports `doctor`, `pack`, `search`, `verify`, `inspect`, `index`,
  `unpack`, and the new local API command `serve`.
- `packages/server` already contains a dependency-light local HTTP API.
- The published npm package currently includes core, index, CLI, docs, demo
  sample code, and vendored runtime files.
- The repo package manifest now includes `packages/server/src/**/*.py` for the
  next packed/published npm release.
- Integration directories for LangChain and LlamaIndex currently exist mostly as
  placeholders.

## Biggest Remaining Blocker

Developers need switching confidence.

They need one blessed path that says:

```text
install Spectrum
pack a repo
serve the pack locally
connect an agent/retriever
search
hydrate exact source
verify fidelity
```

The core technology is far enough along. The bridge work is packaging,
contracts, examples, and one real integration path.

## Implementation Plan

### 1. Add a Blessed Local Server Command

Add a top-level CLI command that runs the existing local HTTP API without manual
`PYTHONPATH` setup.

Preferred command shape:

```powershell
spectrum serve ./my-repo.specpack --port 7777
```

Implementation notes:

- Reuse `packages/server/src/spectrum_server/main.py` and `app.py`.
- Make `serve` the single blessed command shape in docs and examples.
- Register a single positional `.specpack` as pack id `repo`.
- Preserve the existing multi-pack form using repeated `--pack id=path`.
- Return clear errors for missing packs, invalid suffixes, and occupied ports.
- Keep host defaulted to `127.0.0.1`.

### 2. Ship the Server in the npm Package

Update root `package.json` so npm installs the server package source.

Add:

```json
"packages/server/src/**/*.py"
```

Then verify:

```powershell
npm pack --dry-run
npm run smoke:packed
```

The smoke test should confirm that `spectrum serve --help` works from a packed
install, and ideally that a small `.specpack` can be registered by the server.

### 3. Declare the Preview Agent API Contract

Document a small stable HTTP contract for preview integrations.

Initial endpoints:

```text
GET  /health
GET  /packs
POST /packs
GET  /packs/{pack_id}
POST /packs/{pack_id}/index
POST /packs/{pack_id}/search
GET  /packs/{pack_id}/documents/{path}
POST /packs/{pack_id}/verify
```

For the bridge, the most important flow is:

```text
search query -> ranked results -> hydrate selected document -> exact content
```

The contract should specify:

- Request bodies.
- Response shapes.
- Error response shape.
- Path encoding expectations for document hydration.
- Whether index building is automatic or explicit.
- Preview stability policy.

### 4. Build One Real Integration First

Implement one usable integration before filling out more placeholders.

Recommended first target: LangChain.

Minimal Python shape:

```python
retriever = SpectrumRetriever("http://127.0.0.1:7777", pack_id="repo")
docs = retriever.invoke("authentication middleware")
```

The retriever should:

- Call `POST /packs/{pack_id}/search`.
- Map results into LangChain `Document` objects.
- Hydrate selected documents through `GET /packs/{pack_id}/documents/{path}`
  when full content is needed.
- Preserve source path, score, rank, and Spectrum metadata.

Keep the first integration thin. It should prove that Spectrum can be dropped
into a familiar agent/retrieval workflow.

### 5. Add an Agent Quickstart

Create a short doc, likely `docs/agent-quickstart.md`.

It should show:

```powershell
npm install -g spectrumstore
spectrum doctor
spectrum pack ./my-repo ./my-repo.specpack --json
spectrum serve ./my-repo.specpack --port 7777
```

Then include one 20-line example that:

- Sends a search request.
- Prints ranked paths/snippets.
- Hydrates one selected file.
- Passes the exact content into an agent or model prompt.

This doc should be the adoption bridge's main landing point from the README.

### 6. Decide SDK Positioning

The repo already has JS and Python SDKs, but the preview story should be
unambiguous.

Choose one:

1. Publish `@spectrumstore/sdk` and/or `spectrum-ai`, then document them as
   supported preview surfaces.
2. Explicitly defer SDK publishing and say the supported preview integration
   path is `spectrum` CLI plus the local HTTP server.

Do not leave this implied. Ambiguity makes developers hesitate.

### 7. Add a Practical Migration Benchmark

Add a small guide or script that compares a user's current retrieval setup
against Spectrum on their own repo.

Compare:

- Build time.
- Store size.
- Index/sidecar size.
- Query latency.
- Top-k relevance on a small user-provided query list.
- Exact restore verification.

This does not need to be a huge benchmark suite. It should help developers
answer: "Is Spectrum better enough for my workflow?"

## Suggested Preview Release Target

Target the bridge work at the next preview release, for example:

```text
spectrumstore@0.1.0-preview.3
```

Minimum release criteria:

- `spectrum serve` works from a global npm install.
- Server source is included in the npm package.
- Packed smoke test covers the server command.
- README links to the agent quickstart.
- Agent quickstart demonstrates search plus hydration.
- One integration path exists, preferably LangChain.
- HTTP preview contract is documented.

## Shortest Path

```text
package server
add spectrum serve
document HTTP contract
build one LangChain/OpenAI example
publish preview.3
```

That is the practical adoption bridge.
