# Spectrum Algo Runtime — Build Progress

## Status: Phases 1–3 Complete ✅

The browser runtime is working end-to-end. A web project where all source files
have been encoded to `.spec` runs correctly in Chrome via Service Worker, with
zero changes to the source HTML.

---

## What Was Built

### `spectrum-decoder.js`
ES module decoder. Takes a `.spec` file as an `ArrayBuffer` and returns the
decoded source text. Works in browsers, Service Workers, and Node.js 18+.

Pipeline: header parse → zlib decompress → uint32 LE unpack → ID→token lookup
→ RLE/Unicode handling → language-specific reconstruct → checksum verify.

```js
import { loadTokenTable, decodeSpec } from './spectrum-decoder.js';
const table  = await loadTokenTable('./spectrum-tokens.bin');
const result = await decodeSpec(arrayBuffer, table);
console.log(result.source);      // decoded source text
console.log(result.checksumOk);  // fidelity check
```

### `spectrum-tokens.bin`
The token lookup table: 234,893 tokens joined by null bytes (`\x00`), UTF-8
encoded. Parsed in the SW as `TextDecoder.decode(buf).split('\x00')` — much
faster than `JSON.parse` for this many strings.

Regenerate after any dictionary update:
```
python3 Runtime/generate-token-table.py
```

### `spectrum-sw.js`
Service Worker. Intercepts every same-origin GET fetch:

```
page requests: fetch('app.js')
  → SW tries app.js  → 404
  → SW tries app.js.spec  → 200
  → decodes .spec → returns JS with Content-Type: application/javascript
```

The page never knows. No source changes required.

Register it in your HTML:
```html
<script>
  navigator.serviceWorker.register('/spectrum-sw.js', { type: 'module' });
</script>
```

### `test-web/`
Minimal end-to-end test. `app.js` and `styles.css` exist only as `.spec` files
on disk. `index.html` registers the SW, waits for control, then dynamically
loads both resources. All green in Chrome.

### `test-decoder.mjs`
Node.js round-trip test harness:
```
node Runtime/test-decoder.mjs path/to/file.spec path/to/original
```

---

## Gotchas Discovered

**DecompressionStream deadlock in Chrome SW**
`await writer.close()` blocks until the readable side is consumed, but we
hadn't started reading yet — deadlock. Fix: use `Blob.stream().pipeThrough()`
which handles backpressure automatically. Node's implementation doesn't deadlock
so the Node tests passed while Chrome hung.

**Chrome Cache API hanging**
Using the Cache API to cache the token table caused 15s+ hangs when stale
entries existed. Removed entirely. Token table is loaded fresh each SW start via
a singleton promise (fast on localhost, acceptable cost).

**Hard reload bypasses the SW permanently**
Ctrl+Shift+R sets a "bypass SW" flag on the page. `clients.claim()` cannot
reclaim it — `controllerchange` never fires. Fix: detect the state
(`reg.active` non-null but `controller` null) and do an automatic normal reload.
The sessionStorage flag prevents an infinite loop.

**`skipWaiting()` must be unconditional**
Gating `skipWaiting()` on the token table network fetch meant the new SW could
get stuck in "waiting" state if the fetch was slow. Moved to fire immediately.

**Query strings corrupt `.spec` filenames**
`request.url + '.spec'` turns `styles.css?cb=123` into `styles.css?cb=123.spec`.
Fix: use `url.origin + url.pathname + '.spec'` — always strip query params.

---

## Remaining Phases

**Phase 4 — Dev server (`spectrum-serve`)**
The current workaround (dynamic resource loading after SW activation) breaks
normal `<script>`/`<link>` tags in the initial HTML. A lightweight Node server
that decodes `index.html.spec` server-side and injects the SW registration
script would solve the first-load problem properly.

**Phase 5 — Node.js module loader hook**
`--experimental-loader` hook so `.spec`-encoded Node projects run directly:
`node --experimental-loader spectrum-node.js app.js`

**Phase 6 — Hardening**
Binary files, large files, MIME edge cases, error UX, performance profiling.
