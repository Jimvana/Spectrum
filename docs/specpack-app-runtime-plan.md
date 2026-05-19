# Specpack App Runtime Plan

## Goal

Make a `.specpack` usable as a portable project filesystem that can be served, edited by agents, tested, and eventually unpacked for deployment.

The current experiment has proved the first part: Spectrum can serve app files directly from a `.specpack` plus its adjacent `.media` sidecar without unpacking the whole repository first.

## Current State

Spectrum can now serve static project files from a pack:

- HTML, CSS, JavaScript, images, and other browser assets can be read from the `.specpack`.
- Externalized media/model files are streamed from the sibling `.media` folder.
- The server does not unpack the whole repo to disk before serving.
- Routes like `/apps/{pack_id}/` can map to `public/index.html` or `index.html`.
- Root asset requests like `/app.js` and `/styles.css` can be resolved from the default pack.

The known limitation is backend routes. If a packed frontend calls `/api/snapshot`, the browser sends that request to the Spectrum server origin. Unless Spectrum knows how to proxy or run the app backend, it returns `route not found`.

## Design Principles

- The `.specpack` remains the source of truth.
- Agents should read and write through Spectrum APIs, not loose files, when a server is running.
- Serving should avoid full unpack where possible.
- Large binaries, media, models, and databases should remain sidecar-managed with stable relative references.
- Unpack should be treated as an export/deploy step, not the normal edit loop.
- The system should degrade clearly: static apps can run from the pack; dynamic apps need a runtime or proxy.

## Phase 1: Static App Serving

Status: mostly proven.

Deliverables:

- Serve exact raw files from the pack with `GET /packs/{pack_id}/raw/{source_path}`.
- Serve app entrypoints with `GET /apps/{pack_id}/`.
- Support common entrypoint candidates:
  - `public/index.html`
  - `index.html`
  - `dist/index.html`
  - `build/index.html`
- Serve browser assets with correct content types.
- Stream external sidecar files without copying them into temp folders.
- Keep Spectrum API paths isolated so `/api/...` is not accidentally treated as static HTML.

Validation:

- Pack a real frontend project.
- Serve it from a non-default test port.
- Verify HTML, CSS, JS, images, fonts, and media load from the pack.
- Verify unknown API routes return JSON errors, not static fallback HTML.

## Phase 2: Pack-Aware App Manifest

Add a small manifest layer that describes how an app inside a pack should be served or run.

Possible file names:

- `.spectrum-project/app.json`
- `.spectrum/app.json`
- `spectrum.app.json`

Example:

```json
{
  "entry": "public/index.html",
  "asset_roots": ["public", "dist", "assets"],
  "backend": {
    "mode": "proxy",
    "target": "http://127.0.0.1:3000",
    "routes": ["/api/*"]
  },
  "dev": {
    "command": "npm run dev",
    "port": 3000,
    "working_directory": "."
  }
}
```

Deliverables:

- Detect app metadata from the pack manifest.
- Expose it in `GET /packs/{pack_id}/manifest`.
- Show app/runtime state in the Hub GUI.
- Let users pick a serving mode:
  - static only
  - proxy backend
  - unpack-and-run

## Phase 3: Backend Route Support

Dynamic web apps need more than static file serving. Spectrum should support backend routes through explicit runtime modes.

### Option A: Proxy Existing Backend

Spectrum serves packed frontend files and proxies configured backend routes to an already-running dev server.

Example:

- Spectrum app origin: `http://127.0.0.1:7788`
- Backend origin: `http://127.0.0.1:3000`
- `/api/*` requests on Spectrum are proxied to port `3000`.

Pros:

- Simple.
- Keeps the current no-unpack static serving model.
- Useful while developing with an existing local backend.

Cons:

- Requires the user or agent to start the backend separately.
- The app is not fully portable unless the backend runtime is also handled.

### Option B: Unpack-And-Run Backend

Spectrum creates a temporary working directory, restores the project there, installs dependencies if needed, starts the dev command, then proxies app traffic.

Pros:

- Works with ordinary Node, Python, or other app runtimes.
- Keeps compatibility with existing projects.

Cons:

- More moving parts.
- Dependency install can be slow or unsafe without confirmation.
- Temp workspaces must be cleaned up carefully.

### Option C: Spectrum-Native Runtime

Spectrum handles a constrained subset of app behavior directly, such as static APIs backed by documents or pack data.

Pros:

- Very portable.
- Strongly aligned with the specpack-as-source-of-truth model.

Cons:

- Not enough for arbitrary existing apps.
- Better as a later layer, not the first full-runtime solution.

Recommendation:

Implement proxy mode first, then unpack-and-run. Keep Spectrum-native APIs as a future capability.

## Phase 4: Editable Virtual Filesystem

Agents should be able to work directly inside the `.specpack` without requiring a full repo checkout.

Deliverables:

- List files from the pack as a virtual tree.
- Read a file by source path.
- Write or replace a file by source path.
- Add files.
- Soft-delete files into Spectrum trash.
- Rename or move files.
- Rebuild search/index state after edits.
- Track modified files in pack metadata.

Useful APIs:

- `GET /packs/{pack_id}/files`
- `GET /packs/{pack_id}/raw/{source_path}`
- `PUT /packs/{pack_id}/raw/{source_path}`
- `POST /packs/{pack_id}/files/move`
- `DELETE /packs/{pack_id}/documents/{source_path}`

Important behavior:

- Text/code edits should update the `.specpack`.
- Media/model replacements should update the `.media` sidecar and manifest references.
- The server should expose enough metadata for agents to avoid accidentally editing generated or external files.

## Phase 5: Agent Coding Workflow

Build a coding loop where an agent can safely modify the project inside the pack.

Workflow:

1. Agent reads project context from Spectrum API.
2. Agent lists relevant files from the pack.
3. Agent edits files through write APIs.
4. Spectrum updates the pack and rebuilds indexes.
5. App server hot reloads or refreshes from the changed pack.
6. Agent runs tests through the configured runtime.
7. User can inspect the live app from the Spectrum app URL.

Deliverables:

- Pack-aware file editing tools.
- Change summaries from pack metadata.
- Diff views for pending edits.
- Optional checkpoints/snapshots before risky edits.
- Rollback to previous pack revision.

## Phase 6: Testing And Verification

Spectrum needs to know how to verify a packed project.

Deliverables:

- Static asset verification:
  - all referenced local assets resolve
  - content types are correct
  - sidecar hashes match
- Runtime verification:
  - configured backend starts
  - health checks pass
  - app entrypoint loads
  - selected API routes respond
- Browser smoke tests:
  - app page loads
  - no missing static assets
  - no unexpected HTML responses for API calls

Suggested manifest fields:

```json
{
  "checks": {
    "health": "/health",
    "app": "/",
    "api": ["/api/snapshot"]
  }
}
```

## Phase 7: Export And Deploy

When the user is ready, Spectrum can restore the project back to normal files.

Deliverables:

- Restore `.specpack` contents to a selected folder.
- Restore `.media` sidecar files to their original relative paths.
- Use `restore_media.json` to recreate original folders where appropriate.
- Preserve executable bits or platform metadata where feasible.
- Generate a deployment summary:
  - restored files
  - external media restored
  - skipped files
  - dependency/runtime notes

This keeps the normal deployment model simple: work portably in Spectrum, then unpack to deploy.

## Open Questions

- Should app runtime metadata live inside `.spectrum-project/app.json`, or should it be part of the pack manifest only?
- Should Spectrum support multiple apps inside one pack?
- How should secrets and `.env` files be handled during unpack-and-run?
- Should dependency install commands require explicit user confirmation every time?
- How should generated folders like `node_modules`, `.next`, `dist`, and `build` be classified?
- Should external sidecar files be mutable in place, or versioned like pack documents?

## Suggested Next Implementation Steps

1. Formalize the static serving routes and tests already proven by the experiment.
2. Add app manifest discovery.
3. Add proxy support for configured backend route prefixes like `/api/*`.
4. Add Hub controls for app serving mode and proxy target.
5. Add virtual file write APIs for raw text/code files.
6. Add a simple diff/checkpoint model before agent edits.
7. Add unpack-and-run support behind explicit confirmation.

## Success Criteria

- A static frontend can be served directly from a `.specpack` and `.media` sidecar.
- A dynamic frontend can use proxied backend routes without changing its source code.
- An agent can edit source files inside the specpack without unpacking the repo.
- The user can preview the app from Spectrum after edits.
- The project can be unpacked to a normal folder and deployed with expected files restored.
