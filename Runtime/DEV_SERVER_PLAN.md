# Spectrum Algo — Dev Server Plan (Phase 4)

## Read This First

This document is a self-contained brief for building `spectrum-serve`, the
Spectrum Algo local development server. Read it fully before writing any code.

The Runtime project context lives in `Runtime/PROGRESS.md` and
`Runtime/RUNTIME_PROJECT.md`. The short version: Spectrum Algo encodes source
files as `.spec` binaries. The Service Worker runtime (`spectrum-sw.js`)
intercepts browser fetch requests and decodes `.spec` files transparently — but
it can't intercept the very first page load, because the SW doesn't exist yet
when the browser requests the entry point HTML. The dev server solves that.

---

## The Problem Being Solved

After a web project is encoded, disk looks like this:

```
my-project/
  index.html.spec     ← entry point, encoded
  app.js.spec
  styles.css.spec
  logo.png            ← binary, not encoded (not supported yet)
```

If you just run `python3 -m http.server` and navigate to `localhost:8080/`,
the browser requests `index.html`, gets a 404 (only `index.html.spec` exists),
and the page fails to load. The Service Worker never gets a chance to register.

The dev server fixes this by handling the bootstrap:

1. Requests for a file that doesn't exist are checked for a `.spec` equivalent
2. If found, the file is decoded server-side and returned
3. If the decoded file is HTML, a SW registration snippet is injected
4. On subsequent requests the active SW takes over — the server is just a fallback

---

## Architecture

```
Browser                     Dev Server                       Disk
───────                     ──────────                       ────
GET /                   →   finds index.html.spec        →   decodes it
                            injects <script>register SW</script>
                        ←   returns HTML

SW registers and activates (takes ~200ms on first load)

GET /app.js             →   SW intercepts                →   fetches app.js.spec
                            decodes, returns JS              (server not involved)

GET /styles.css         →   SW intercepts                →   fetches styles.css.spec
                            decodes, returns CSS             (server not involved)
```

The server handles the entry point. The SW handles everything after that.
The server also serves the SW infrastructure files (`spectrum-sw.js`,
`spectrum-decoder.js`, `spectrum-tokens.bin`) from the Runtime directory.

---

## Deliverable

**`Runtime/spectrum-serve.mjs`** — a single-file Node.js CLI server.

```
node Runtime/spectrum-serve.mjs [project-dir] [--port 8080] [--open]
```

- `project-dir` defaults to the current working directory
- `--port` / `-p` — port number (default: 8080)
- `--open` — open the browser automatically after starting

---

## Request Handling Logic

For every incoming GET request, the server checks in this order:

```
1. Is the path one of the Runtime infrastructure files?
   (spectrum-sw.js, spectrum-decoder.js, spectrum-tokens.bin)
   → serve from the Runtime/ directory

2. Does the exact file exist in the project directory?
   → serve it directly (static file)

3. Does <path>.spec exist in the project directory?
   → decode it, determine MIME type from original extension
   → if HTML: inject the SW registration snippet
   → serve the decoded content

4. Is it a directory request?
   → try index.html, then index.html.spec (applying rule 2 or 3)

5. None of the above → 404
```

Non-GET requests (POST, etc.) always pass through unchanged.

---

## SW Registration Snippet

Injected into every HTML response (decoded or plain), inserted right after the
opening `<head>` tag (case-insensitive match). If no `<head>` tag is found,
prepend to the response body.

```html
<script>/* injected by spectrum-serve */
if ('serviceWorker' in navigator) {
  navigator.serviceWorker.register('/spectrum-sw.js', { type: 'module' })
    .then(r => console.log('[spectrum] SW registered, scope:', r.scope))
    .catch(e => console.error('[spectrum] SW registration failed:', e));
}
</script>
```

Note: the SW path is always `/spectrum-sw.js` (root-relative), so the SW scope
covers the whole origin regardless of what subdirectory the project is in.

---

## Using the Existing JS Decoder

`Runtime/spectrum-decoder.js` already works in Node.js 18+ (confirmed by
`Runtime/test-decoder.mjs`). Use it directly — no need to re-implement decode
logic in the server.

The token table should be loaded once at server startup (not on every request).
Use the `.json` file for the server-side load (simpler than the `.bin` file in
Node since `JSON.parse` is fast enough for a one-time server startup cost):

```js
import { readFile } from 'fs/promises';
import { decodeSpec } from './spectrum-decoder.js';

const tokenTable = JSON.parse(
  await readFile(new URL('./spectrum-tokens.json', import.meta.url), 'utf8')
);
```

Then on each `.spec` request:
```js
const buffer = await readFile(specPath);
const result = await decodeSpec(buffer.buffer, tokenTable);
// result.source is the decoded text
```

---

## MIME Type Handling

Same map as in `spectrum-sw.js`. Use the *original* extension (before `.spec`)
to determine Content-Type. Copy the map from the SW for consistency:

```js
const MIME_TYPES = {
  '.js':   'application/javascript; charset=utf-8',
  '.mjs':  'application/javascript; charset=utf-8',
  '.css':  'text/css; charset=utf-8',
  '.html': 'text/html; charset=utf-8',
  '.htm':  'text/html; charset=utf-8',
  '.json': 'application/json; charset=utf-8',
  '.txt':  'text/plain; charset=utf-8',
  '.py':   'text/x-python; charset=utf-8',
  '.ts':   'application/javascript; charset=utf-8',
  '.sql':  'text/x-sql; charset=utf-8',
  '.rs':   'text/plain; charset=utf-8',
  '.svg':  'image/svg+xml; charset=utf-8',
  '.xml':  'application/xml; charset=utf-8',
  '.md':   'text/markdown; charset=utf-8',
};
```

For static files without a `.spec`, use Node's built-in lookup or a simple map.

---

## Serving Runtime Infrastructure Files

The server needs to serve these three files regardless of what project directory
is being served:

| URL path                   | Serves from                        |
|----------------------------|------------------------------------|
| `/spectrum-sw.js`          | `Runtime/spectrum-sw.js`           |
| `/spectrum-decoder.js`     | `Runtime/spectrum-decoder.js`      |
| `/spectrum-tokens.bin`     | `Runtime/spectrum-tokens.bin`      |

Detect the Runtime directory as the directory containing `spectrum-serve.mjs`
(i.e. `new URL('.', import.meta.url).pathname`).

---

## Startup Output

```
Spectrum Algo Dev Server
  Project : /Users/james/my-project
  Runtime : /Users/james/.../Spectrum Algo/Runtime
  URL     : http://localhost:8080
  Dict    : v9  (234,893 tokens)

Ready. SW will activate on first page load.
Press Ctrl+C to stop.
```

---

## Error Handling

- Corrupted `.spec` file → return 500 with a plain text error message
  (mirrors what the SW does so behaviour is consistent)
- File not found (no original, no `.spec`) → 404
- Decode error → log to server console with the file path + error

---

## Test: Encoded Project Round-Trip

A good acceptance test after building the server:

1. Encode the `test-web/` project files to `.spec` (already done — `app.js.spec`
   and `styles.css.spec` exist, `index.html` is plain)
2. Run `node Runtime/spectrum-serve.mjs Runtime/test-web`
3. Open `http://localhost:8080/` — should load the dark-themed test page
4. All diagnostic checks should go green (same as current SW-based test)

For a fuller test, encode `index.html` itself to `index.html.spec` and remove
the original — the server should decode it, inject the SW snippet, and serve it.
This is the real first-load scenario the server exists to solve.

---

## Files to Read Before Starting

- `Runtime/spectrum-decoder.js` — the decoder you'll import
- `Runtime/spectrum-sw.js` — copy the MIME map and skip-list from here
- `Runtime/test-decoder.mjs` — shows how to load the token table in Node
- `Runtime/test-web/` — the test project you'll use for acceptance testing

## Files to Create

- `Runtime/spectrum-serve.mjs` — the whole thing, single file

---

## Out of Scope for This Phase

- HTTPS / self-signed certs
- Hot reload / file watching
- WebSocket proxying
- Binary file (image/font) encoding — current `.spec` format is text only;
  binary files should be served as-is from disk (rule 2 catches these)
- `npm`-style package / global install — just run it directly with `node`
