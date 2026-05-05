#!/usr/bin/env node
/**
 * Spectrum Algo — Dev Server  (Phase 4)
 *
 * Handles the "first HTML load" bootstrap problem: the Service Worker can't
 * intercept a page before it exists, so this server decodes .spec files
 * server-side and injects the SW registration snippet into every HTML response.
 * After the first load the SW takes over; the server is just a fallback.
 *
 * Usage:
 *   node Runtime/spectrum-serve.mjs [project-dir] [--port 8080] [--open]
 *
 *   project-dir   Directory to serve (default: cwd)
 *   --port / -p   Port number (default: 8080)
 *   --open        Open the browser automatically after starting
 */

import { createServer }            from 'http';
import { readFile, access, stat }  from 'fs/promises';
import { resolve, join, extname, dirname, basename } from 'path';
import { fileURLToPath }           from 'url';
import { exec }                    from 'child_process';

import { decodeSpec } from './spectrum-decoder.js';


// ─────────────────────────────────────────────────────────────────────────────
// Paths
// ─────────────────────────────────────────────────────────────────────────────

const RUNTIME_DIR = dirname(fileURLToPath(import.meta.url));

// Infrastructure files served from Runtime/ regardless of project-dir
const INFRA = {
  '/spectrum-sw.js':      join(RUNTIME_DIR, 'spectrum-sw.js'),
  '/spectrum-decoder.js': join(RUNTIME_DIR, 'spectrum-decoder.js'),
  '/spectrum-tokens.bin': join(RUNTIME_DIR, 'spectrum-tokens.bin'),
};


// ─────────────────────────────────────────────────────────────────────────────
// MIME types — mirrored from spectrum-sw.js for consistency
// ─────────────────────────────────────────────────────────────────────────────

const MIME_TYPES = {
  '.js':   'application/javascript; charset=utf-8',
  '.mjs':  'application/javascript; charset=utf-8',
  '.ts':   'application/javascript; charset=utf-8',
  '.css':  'text/css; charset=utf-8',
  '.html': 'text/html; charset=utf-8',
  '.htm':  'text/html; charset=utf-8',
  '.json': 'application/json; charset=utf-8',
  '.txt':  'text/plain; charset=utf-8',
  '.py':   'text/x-python; charset=utf-8',
  '.sql':  'text/x-sql; charset=utf-8',
  '.rs':   'text/x-rust; charset=utf-8',
  '.php':  'text/x-php; charset=utf-8',
  '.xml':  'application/xml; charset=utf-8',
  '.svg':  'image/svg+xml; charset=utf-8',
  '.md':   'text/markdown; charset=utf-8',
  // common static assets
  '.ico':  'image/x-icon',
  '.png':  'image/png',
  '.jpg':  'image/jpeg',
  '.jpeg': 'image/jpeg',
  '.gif':  'image/gif',
  '.webp': 'image/webp',
  '.woff': 'font/woff',
  '.woff2':'font/woff2',
};

function getMimeType(filePath) {
  const ext = extname(filePath).toLowerCase();
  return MIME_TYPES[ext] ?? 'application/octet-stream';
}

function isHtml(filePath) {
  const ext = extname(filePath).toLowerCase();
  return ext === '.html' || ext === '.htm';
}


// ─────────────────────────────────────────────────────────────────────────────
// SW registration snippet — injected into every HTML response
// ─────────────────────────────────────────────────────────────────────────────

const SW_SNIPPET = `<script>/* injected by spectrum-serve */
if ('serviceWorker' in navigator) {
  navigator.serviceWorker.register('/spectrum-sw.js', { type: 'module' })
    .then(r => console.log('[spectrum] SW registered, scope:', r.scope))
    .catch(e => console.error('[spectrum] SW registration failed:', e));
}
</script>`;

/**
 * Inject the SW registration snippet right after the opening <head> tag.
 * Falls back to prepending to the body if no <head> is found.
 */
function injectSwSnippet(html) {
  const match = html.match(/<head[^>]*>/i);
  if (match) {
    const idx = match.index + match[0].length;
    return html.slice(0, idx) + '\n' + SW_SNIPPET + '\n' + html.slice(idx);
  }
  return SW_SNIPPET + '\n' + html;
}


// ─────────────────────────────────────────────────────────────────────────────
// File system helpers
// ─────────────────────────────────────────────────────────────────────────────

async function fileExists(p) {
  try { await access(p); return true; } catch { return false; }
}

async function isDirectory(p) {
  try { return (await stat(p)).isDirectory(); } catch { return false; }
}


// ─────────────────────────────────────────────────────────────────────────────
// Response helpers
// ─────────────────────────────────────────────────────────────────────────────

function send(res, status, body, headers = {}) {
  const buf = typeof body === 'string' ? Buffer.from(body, 'utf8') : body;
  res.writeHead(status, {
    'Content-Length': buf.length,
    ...headers,
  });
  res.end(buf);
}

function send404(res, urlPath) {
  send(res, 404, `404 Not Found: ${urlPath}`, { 'Content-Type': 'text/plain; charset=utf-8' });
}

function send500(res, urlPath, err) {
  const msg = `500 Internal Server Error decoding ${urlPath}:\n${err.message}`;
  send(res, 500, msg, { 'Content-Type': 'text/plain; charset=utf-8' });
}


// ─────────────────────────────────────────────────────────────────────────────
// Core request handler
// ─────────────────────────────────────────────────────────────────────────────

async function handleRequest(req, res, projectDir, tokenTable) {
  // Only handle GET; everything else gets a 405
  if (req.method !== 'GET') {
    send(res, 405, 'Method Not Allowed', { 'Content-Type': 'text/plain' });
    return;
  }

  // Strip query string from the URL path
  const urlPath = new URL(req.url, 'http://localhost').pathname;

  // ── Rule 1: Infrastructure files → serve from Runtime/ ───────────────────
  if (INFRA[urlPath]) {
    const infraPath = INFRA[urlPath];
    if (await fileExists(infraPath)) {
      const data = await readFile(infraPath);
      const mime = getMimeType(infraPath);
      send(res, 200, data, { 'Content-Type': mime });
      console.log(`  [infra] ${urlPath}`);
      return;
    }
    // Infrastructure file missing — this is a setup problem
    send(res, 500, `Infrastructure file missing: ${infraPath}`, { 'Content-Type': 'text/plain' });
    console.error(`  [error] Missing infrastructure file: ${infraPath}`);
    return;
  }

  // Resolve to an absolute path in the project directory
  // Prevent path traversal by checking the resolved path stays inside projectDir
  const rel = urlPath.replace(/^\//, '');
  const absPath = resolve(join(projectDir, rel));
  if (!absPath.startsWith(projectDir)) {
    send(res, 403, 'Forbidden', { 'Content-Type': 'text/plain' });
    return;
  }

  // ── Rule 4 (check first): Directory request? ─────────────────────────────
  if (await isDirectory(absPath)) {
    return handleIndex(res, absPath, urlPath, tokenTable);
  }

  // ── Rule 2: Exact file exists? → serve it directly ───────────────────────
  if (await fileExists(absPath)) {
    const data = await readFile(absPath);
    const mime = getMimeType(absPath);
    let body = data;

    // Still inject SW snippet into plain HTML files served directly
    if (isHtml(absPath)) {
      const html = injectSwSnippet(data.toString('utf8'));
      body = Buffer.from(html, 'utf8');
      console.log(`  [html]  ${urlPath}  (injected SW snippet)`);
    } else {
      console.log(`  [file]  ${urlPath}`);
    }

    send(res, 200, body, { 'Content-Type': mime });
    return;
  }

  // ── Rule 3: <path>.spec exists? → decode and serve ───────────────────────
  const specPath = absPath + '.spec';
  if (await fileExists(specPath)) {
    return serveDecoded(res, specPath, urlPath, absPath, tokenTable);
  }

  // ── Rule 5: Nothing found → 404 ──────────────────────────────────────────
  send404(res, urlPath);
  console.log(`  [404]   ${urlPath}`);
}


// ─────────────────────────────────────────────────────────────────────────────
// Directory index: try index.html, then index.html.spec
// ─────────────────────────────────────────────────────────────────────────────

async function handleIndex(res, dirPath, urlPath, tokenTable) {
  const htmlPath = join(dirPath, 'index.html');
  const specPath = join(dirPath, 'index.html.spec');

  if (await fileExists(htmlPath)) {
    const data = await readFile(htmlPath);
    const html = injectSwSnippet(data.toString('utf8'));
    const body = Buffer.from(html, 'utf8');
    send(res, 200, body, { 'Content-Type': 'text/html; charset=utf-8' });
    console.log(`  [html]  ${urlPath}index.html  (injected SW snippet)`);
    return;
  }

  if (await fileExists(specPath)) {
    return serveDecoded(res, specPath, urlPath + 'index.html', htmlPath, tokenTable);
  }

  send404(res, urlPath);
  console.log(`  [404]   ${urlPath}  (no index.html or index.html.spec)`);
}


// ─────────────────────────────────────────────────────────────────────────────
// Decode a .spec file and serve the result
// ─────────────────────────────────────────────────────────────────────────────

async function serveDecoded(res, specPath, urlPath, originalPath, tokenTable) {
  try {
    const raw    = await readFile(specPath);
    const result = await decodeSpec(raw, tokenTable);

    if (!result.checksumOk) {
      console.warn(`  [warn]  Checksum mismatch for ${urlPath} — serving anyway`);
    }

    const mime = getMimeType(originalPath);
    let body;

    if (isHtml(originalPath)) {
      const html = injectSwSnippet(result.source);
      body = Buffer.from(html, 'utf8');
      console.log(`  [spec]  ${urlPath}  →  ${result.source.length.toLocaleString()} chars  (html+SW snippet)`);
    } else {
      body = Buffer.from(result.source, 'utf8');
      console.log(`  [spec]  ${urlPath}  →  ${result.source.length.toLocaleString()} chars  (${mime.split(';')[0]})`);
    }

    send(res, 200, body, {
      'Content-Type':         mime,
      'X-Spectrum-Decoded':   'true',
      'X-Spectrum-Tokens':    String(result.tokenCount),
    });

  } catch (err) {
    console.error(`  [error] Failed to decode ${urlPath}:`, err.message);
    send500(res, urlPath, err);
  }
}


// ─────────────────────────────────────────────────────────────────────────────
// CLI argument parser
// ─────────────────────────────────────────────────────────────────────────────

function parseArgs(argv) {
  let projectDir = null;
  let port       = 8080;
  let openBrowser = false;

  for (let i = 0; i < argv.length; i++) {
    const arg = argv[i];
    if (arg === '--port' || arg === '-p') {
      const n = parseInt(argv[++i], 10);
      if (isNaN(n) || n < 1 || n > 65535) {
        console.error(`Invalid port: ${argv[i]}`);
        process.exit(1);
      }
      port = n;
    } else if (arg.startsWith('--port=') || arg.startsWith('-p=')) {
      const n = parseInt(arg.split('=')[1], 10);
      if (isNaN(n) || n < 1 || n > 65535) {
        console.error(`Invalid port: ${arg}`);
        process.exit(1);
      }
      port = n;
    } else if (arg === '--open') {
      openBrowser = true;
    } else if (!arg.startsWith('-')) {
      projectDir = resolve(arg);
    } else {
      console.error(`Unknown argument: ${arg}`);
      process.exit(1);
    }
  }

  if (projectDir === null) {
    projectDir = resolve(process.cwd());
  }

  return { projectDir, port, openBrowser };
}


// ─────────────────────────────────────────────────────────────────────────────
// Open browser
// ─────────────────────────────────────────────────────────────────────────────

function launchBrowser(url) {
  const cmd = process.platform === 'win32'  ? `start "${url}"`
            : process.platform === 'darwin' ? `open "${url}"`
            : `xdg-open "${url}"`;
  exec(cmd, err => {
    if (err) console.warn(`[spectrum-serve] Could not open browser: ${err.message}`);
  });
}


// ─────────────────────────────────────────────────────────────────────────────
// Main
// ─────────────────────────────────────────────────────────────────────────────

async function main() {
  const { projectDir, port, openBrowser } = parseArgs(process.argv.slice(2));

  // Verify project directory exists
  if (!(await fileExists(projectDir))) {
    console.error(`Project directory not found: ${projectDir}`);
    process.exit(1);
  }
  if (!(await isDirectory(projectDir))) {
    console.error(`Not a directory: ${projectDir}`);
    process.exit(1);
  }

  // Load token table once at startup
  const tokenTablePath = join(RUNTIME_DIR, 'spectrum-tokens.json');
  let tokenTable;
  try {
    const raw  = await readFile(tokenTablePath, 'utf8');
    tokenTable = JSON.parse(raw);
  } catch (err) {
    console.error(`Failed to load token table from ${tokenTablePath}:`);
    console.error(err.message);
    process.exit(1);
  }

  const url = `http://localhost:${port}`;

  console.log('');
  console.log('Spectrum Algo Dev Server');
  console.log(`  Project : ${projectDir}`);
  console.log(`  Runtime : ${RUNTIME_DIR}`);
  console.log(`  URL     : ${url}`);
  console.log(`  Dict    : ${tokenTable.length.toLocaleString()} tokens`);
  console.log('');

  const server = createServer((req, res) => {
    handleRequest(req, res, projectDir, tokenTable).catch(err => {
      console.error('[spectrum-serve] Unhandled error:', err);
      try {
        res.writeHead(500);
        res.end('Internal Server Error');
      } catch { /* already sent */ }
    });
  });

  server.listen(port, '127.0.0.1', () => {
    console.log('Ready. SW will activate on first page load.');
    console.log('Press Ctrl+C to stop.');
    console.log('');
    if (openBrowser) launchBrowser(url);
  });

  server.on('error', err => {
    if (err.code === 'EADDRINUSE') {
      console.error(`Port ${port} is already in use. Try --port <number>.`);
    } else {
      console.error('Server error:', err.message);
    }
    process.exit(1);
  });
}

main().catch(err => {
  console.error('Fatal error:', err);
  process.exit(1);
});
