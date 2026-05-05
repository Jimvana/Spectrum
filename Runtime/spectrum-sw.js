/**
 * Spectrum Algo — Service Worker Runtime
 *
 * Intercepts fetch requests and transparently decodes .spec files on the fly.
 *
 * When a request for `foo.js` returns a 404 (or fails to fetch), the SW
 * automatically checks for `foo.js.spec`, decodes it using the Spectrum Algo
 * decoder, and returns the decoded content with the correct Content-Type.
 * The page never knows the difference.
 *
 * Registration (add to your HTML, ideally in a <script> near the top of <body>):
 *
 *   <script>
 *     if ('serviceWorker' in navigator) {
 *       navigator.serviceWorker.register('/spectrum-sw.js', { type: 'module' })
 *         .then(reg => console.log('[spectrum] SW registered', reg.scope))
 *         .catch(err => console.error('[spectrum] SW registration failed', err));
 *     }
 *   </script>
 *
 * Note — first HTML load:
 *   The SW cannot intercept the very first page load (it isn't active yet).
 *   Resources referenced in <script>/<link> tags in the initial HTML load
 *   before the SW takes control. Two workarounds:
 *     1. Use the spectrum-serve dev server (Phase 4) — it injects SW
 *        registration and handles the entry-point decode server-side.
 *     2. Load resources dynamically after SW activation (see test-web/index.html).
 */

import { decodeSpec, SpecFormatError } from './spectrum-decoder.js';

// ─────────────────────────────────────────────────────────────────────────────
// Config
// ─────────────────────────────────────────────────────────────────────────────

// Path to the token table, relative to the SW's location.
// .bin format: tokens joined by \x00 — far faster to parse than JSON
// (TextDecoder.decode + split vs JSON.parse for 234k strings).
const TOKEN_TABLE_URL = new URL('./spectrum-tokens.bin', self.location.href).href;

// MIME types keyed on the *original* (non-.spec) file extension
const MIME_TYPES = new Map([
  ['.js',   'application/javascript; charset=utf-8'],
  ['.mjs',  'application/javascript; charset=utf-8'],
  ['.ts',   'application/javascript; charset=utf-8'],  // browsers run transpiled TS
  ['.css',  'text/css; charset=utf-8'],
  ['.html', 'text/html; charset=utf-8'],
  ['.htm',  'text/html; charset=utf-8'],
  ['.json', 'application/json; charset=utf-8'],
  ['.txt',  'text/plain; charset=utf-8'],
  ['.py',   'text/x-python; charset=utf-8'],
  ['.sql',  'text/x-sql; charset=utf-8'],
  ['.rs',   'text/x-rust; charset=utf-8'],
  ['.php',  'text/x-php; charset=utf-8'],
  ['.xml',  'application/xml; charset=utf-8'],
  ['.svg',  'image/svg+xml; charset=utf-8'],
  ['.md',   'text/markdown; charset=utf-8'],
]);

// ─────────────────────────────────────────────────────────────────────────────
// Token table — loaded once per SW lifetime, held in memory
// No Cache API — it caused hanging in Chrome when stale cache entries existed.
// For a local dev tool, a direct fetch on each SW start is instant.
// ─────────────────────────────────────────────────────────────────────────────

// Singleton promise — concurrent fetch events share one load, not N parallel fetches
let _tokenTablePromise = null;

function getTokenTable() {
  if (_tokenTablePromise) return _tokenTablePromise;

  _tokenTablePromise = (async () => {
    const t0 = Date.now();
    console.log('[spectrum-sw] Loading token table …');

    const resp = await fetch(TOKEN_TABLE_URL);
    if (!resp.ok) {
      throw new Error(`Token table fetch failed: HTTP ${resp.status} for ${TOKEN_TABLE_URL}`);
    }

    const buf   = await resp.arrayBuffer();
    const text  = new TextDecoder().decode(buf);
    const table = text.split('\x00');

    console.log(`[spectrum-sw] Token table ready — ${table.length.toLocaleString()} tokens in ${Date.now() - t0}ms`);
    return table;
  })().catch(err => {
    _tokenTablePromise = null; // reset so next call retries
    throw err;
  });

  return _tokenTablePromise;
}


// ─────────────────────────────────────────────────────────────────────────────
// MIME type helper
// ─────────────────────────────────────────────────────────────────────────────

function getMimeType(pathname) {
  // pathname is the original URL path (without .spec), e.g. "/app.js"
  const lower = pathname.toLowerCase();
  for (const [ext, mime] of MIME_TYPES) {
    if (lower.endsWith(ext)) return mime;
  }
  return 'text/plain; charset=utf-8';
}


// ─────────────────────────────────────────────────────────────────────────────
// Lifecycle events
// ─────────────────────────────────────────────────────────────────────────────

self.addEventListener('install', event => {
  console.log('[spectrum-sw] Installing …');
  // skipWaiting() unconditionally — don't block activation on the token table
  // fetch. The token table loads lazily on the first decode instead.
  // Gating skipWaiting() on a network fetch caused the SW to stay stuck in
  // "waiting" state if the fetch was slow or failed.
  event.waitUntil(self.skipWaiting());
});

self.addEventListener('activate', event => {
  console.log('[spectrum-sw] Activated — claiming clients');
  event.waitUntil(self.clients.claim()); // take control of already-open pages
});

// Allow pages to kick a claim() on demand.
// Needed when the SW is already active (from a previous session) but didn't
// claim the current page — clients.claim() only runs in activate, which
// doesn't re-run for an already-active SW. The page posts { type: 'CLAIM' }
// and this handler forces a new claim cycle.
self.addEventListener('message', event => {
  if (event.data?.type === 'CLAIM') {
    console.log('[spectrum-sw] Got CLAIM message — claiming clients');
    event.waitUntil(self.clients.claim());
  }
});


// ─────────────────────────────────────────────────────────────────────────────
// Fetch intercept — the core of the runtime
// ─────────────────────────────────────────────────────────────────────────────

self.addEventListener('fetch', event => {
  // Only intercept GET requests for same-origin URLs
  const url = new URL(event.request.url);
  if (event.request.method !== 'GET') return;
  if (url.origin !== self.location.origin) return;

  // Don't intercept requests for SW infrastructure files themselves
  const path = url.pathname;
  if (
    path.endsWith('spectrum-sw.js') ||
    path.endsWith('spectrum-decoder.js') ||
    path.endsWith('spectrum-tokens.bin') ||
    path.endsWith('spectrum-tokens.json')
  ) return;

  event.respondWith(handleFetch(event.request, url));
});

async function handleFetch(request, url) {
  // ── 1. Try the original request ──────────────────────────────────────────
  let originalResp;
  try {
    originalResp = await fetch(request);
    // If it succeeded (and isn't a 404), return it as-is
    if (originalResp.ok) return originalResp;
    // Any non-404 error: pass through unchanged (let the browser handle it)
    if (originalResp.status !== 404) return originalResp;
  } catch (_) {
    // Network error — fall through and try .spec
  }

  // ── 2. Try the .spec equivalent ──────────────────────────────────────────
  // Use origin + pathname only — strip query strings so that
  // "styles.css?cb=123" maps to "styles.css.spec", not "styles.css?cb=123.spec"
  const specUrl = url.origin + url.pathname + '.spec';
  let specResp;
  try {
    specResp = await fetch(specUrl);
    if (!specResp.ok) {
      // No .spec either — return the original 404 (or rethrow network error)
      return originalResp || new Response('Not found', { status: 404 });
    }
  } catch (_) {
    return originalResp || new Response('Not found', { status: 404 });
  }

  // ── 3. Decode the .spec file ─────────────────────────────────────────────
  try {
    const table  = await getTokenTable();
    const buffer = await specResp.arrayBuffer();
    const result = await decodeSpec(buffer, table);

    if (!result.checksumOk) {
      console.warn(`[spectrum-sw] Checksum mismatch for ${url.pathname} — serving anyway`);
    }

    const mimeType = getMimeType(url.pathname);
    console.log(`[spectrum-sw] Decoded ${url.pathname} → ${result.source.length.toLocaleString()} chars (${mimeType.split(';')[0]})`);

    return new Response(result.source, {
      status: 200,
      headers: {
        'Content-Type': mimeType,
        'X-Spectrum-Decoded': 'true',
        'X-Spectrum-Tokens': String(result.tokenCount),
      },
    });

  } catch (err) {
    // Always return an error Response — never re-throw. A rejected respondWith()
    // promise causes a silent network error in Chrome that doesn't reliably
    // trigger script.onerror or link.onerror, making failures invisible.
    const msg = err instanceof SpecFormatError
      ? `Spectrum format error: ${err.message}`
      : `Spectrum internal error: ${err.name}: ${err.message}`;
    console.error(`[spectrum-sw] Failed to decode ${url.pathname}:`, err);
    return new Response(msg, {
      status: 500,
      headers: { 'Content-Type': 'text/plain' },
    });
  }
}
