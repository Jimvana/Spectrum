# Spectrum Algo — Runtime Project

## Purpose of This Document

This file is a self-contained brief for building the Spectrum Algo runtime. Read this fully before writing any code. It covers the problem being solved, the chosen approach, the architecture, open questions, and the phased build plan.

---

## Background: The File Reference Problem

Spectrum Algo encodes source files as pixel images, saving them with a `.spec` extension. For example:

- `1.js` → `1.js.spec`
- `styles.css` → `styles.css.spec`
- `index.html` → `index.html.spec`

This breaks internal file references. If `index.html` contains `<script src="1.js">`, that reference now points to a file that no longer exists. The original file has been replaced by `1.js.spec`.

---

## Chosen Solution: Runtime Interception

Rather than rewriting references inside files (which requires per-format parsers and is brittle), the solution is a **runtime shim** that intercepts file requests transparently.

When something requests `1.js`, the runtime:
1. Checks whether `1.js` exists — if yes, serves it normally
2. If not, checks whether `1.js.spec` exists
3. If found, decodes the `.spec` file on the fly using the Spectrum Algo decoder
4. Returns the decoded content as if `1.js` had been there all along

The source code never needs to change. References stay intact. The runtime is the translation layer.

---

## Why Not Other Approaches

**Reference rewriting** — Scan each file and update references to point at `.spec` versions. Rejected because it requires format-aware parsers for HTML, CSS, JS (imports, require, url(), src, href...), and is fragile against dynamic references.

**Keep original filenames** — Store spec data inside files named with original extensions. Rejected because it inflates file size and confuses any tool that tries to parse the file normally.

**OS-level filesystem virtualisation** — Mount a virtual filesystem so all apps transparently see decoded files. Technically possible (FUSE on Linux/Mac, Dokan on Windows) but requires OS-specific implementations, elevated permissions, and significant complexity. Overkill.

---

## Target Platform: Web (Phase 1)

The first runtime target is **web projects** served via a local development server or browser. This is the highest-value target because:
- Web projects are the most common use case for `.spec` encoded files
- The browser already has a built-in interception mechanism: **Service Workers**
- A Service Worker can intercept every `fetch` request the page makes, check for a `.spec` equivalent, decode it, and return the result — all transparently, without touching the source

### How a Service Worker Runtime Works

```
Page requests: fetch('1.js')
  ↓
Service Worker intercepts the request
  ↓
Checks: does 1.js exist?
  → Yes: pass through normally
  → No: check for 1.js.spec
      → Found: decode .spec → return JS content
      → Not found: return 404 as normal
```

The page never knows the difference. The source HTML never changes.

---

## Spectrum Algo Decoder (Existing)

The decoder already exists in the main Spectrum Algo project at:

```
/Users/video/Desktop/Spectrum Algo/decoder/
```

The runtime needs to either:
- **Port** the decode logic to JavaScript (for use inside a Service Worker), or
- **Call** the existing Python decoder via a local server endpoint

For a pure browser Service Worker approach, the decode logic needs to be in JavaScript. Porting it is the cleaner long-term solution. A local server bridge is a valid stepping stone for Phase 1.

Key things to understand about the decoder before porting:
- How `.spec` files are structured (pixel layout, colour mapping, header/metadata)
- What the decode function takes as input and returns as output
- Whether there are any dependencies that would need to be replicated in JS

Read the existing decoder source before starting any port work.

---

## Architecture Overview

```
[Web Project]
  index.html
  style.css          ← these are all .spec files on disk
  app.js
  utils.js

[Browser]
  Loads index.html.spec → decoded by runtime → browser sees index.html content
  Page requests app.js  → Service Worker intercepts
                        → fetches app.js.spec
                        → decodes on the fly
                        → returns JS to page
  All references work as if original files exist
```

---

## Phase Plan

### Phase 1 — JavaScript Decoder
Port the Spectrum Algo decode logic from Python to JavaScript. This is the foundation everything else depends on.

Deliverable: `spectrum-decoder.js` — a standalone JS module that takes a `.spec` file (as ArrayBuffer or Blob) and returns the decoded file content (as text or ArrayBuffer).

Acceptance criteria: round-trip test — encode a known file with the existing Python encoder, decode with the new JS decoder, confirm output matches original byte-for-byte.

### Phase 2 — Service Worker Skeleton
Build a basic Service Worker that:
- Registers and activates correctly
- Intercepts all fetch requests
- Passes non-.spec requests through untouched
- Stubs the decode step (returns placeholder) for a matching .spec request

Deliverable: `spectrum-sw.js` — a working Service Worker with intercept logic in place.

### Phase 3 — Wire Decoder into Service Worker
Connect the Phase 1 decoder to the Phase 2 Service Worker. When a `.spec` file is found, decode it and return real content.

Deliverable: end-to-end test — a minimal web project with `.spec` encoded files that runs correctly in the browser via the Service Worker runtime.

### Phase 4 — Dev Server Integration
Build a lightweight local dev server (Node.js) that:
- Serves a web project directory
- Automatically injects the Service Worker registration into HTML responses
- Handles the initial `.spec` decode for the HTML entry point itself (since the Service Worker isn't registered yet when the first page load happens)

Deliverable: `spectrum-serve` CLI command — run it in a project directory and the project loads in the browser as if all files were unencoded.

### Phase 5 — Node.js Runtime (Separate Track)
For non-browser JS projects, implement a Node.js module loader hook that intercepts `require()` / `import` calls and decodes `.spec` files on the fly.

Deliverable: `spectrum-node.js` — a loader that can be passed via `--experimental-loader` or `--require` to run a `.spec`-encoded Node project.

### Phase 6 — Hardening
- Edge cases: binary files, large files, nested references
- Error handling: corrupted `.spec` files, missing files
- Performance: caching decoded files in memory to avoid repeated decode on every request
- Cross-browser testing

---

## Open Questions to Resolve Early

**Decoder port complexity** — How much of the Python decoder logic is straightforward to port vs. tricky? Read the decoder source first and flag anything unusual.

**First HTML load problem** — The Service Worker can only intercept requests *after* it has been registered. But the entry point (`index.html.spec`) needs to be decoded *before* the Service Worker exists. The dev server (Phase 4) solves this, but Phase 1–3 need a workaround — likely a thin HTML stub that registers the SW then redirects.

**Binary files** — Does the current `.spec` format handle binary files (images, fonts) as well as text? The runtime needs to handle both, returning the correct MIME type.

**MIME types** — The Service Worker must return responses with the correct `Content-Type` header based on the original file extension (`.js` → `application/javascript`, `.css` → `text/css`, etc.), not the `.spec` extension.

**Cache invalidation** — If a `.spec` file changes on disk, the Service Worker's in-memory cache of the decoded version needs to be invalidated.

---

## Files to Read Before Starting

- `/Users/video/Desktop/Spectrum Algo/decoder/` — existing Python decoder, understand structure and logic
- `/Users/video/Desktop/Spectrum Algo/encoder/` — existing encoder, understand the .spec format from both ends
- `/Users/video/Desktop/Spectrum Algo/spec_format/` — any format specification documents
- `/Users/video/Desktop/Spectrum Algo/PROGRESS.md` — overall project status and decisions already made

---

## Definition of Done (Phase 1 Complete)

A developer can take a web project where all source files have been encoded to `.spec`, drop `spectrum-sw.js` into the project root, add a single `<script>` tag to register the Service Worker, and have the project run correctly in the browser with no other changes.
