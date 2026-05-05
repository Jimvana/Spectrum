/**
 * Spectrum Algo — JS Decoder
 *
 * Decodes a .spec binary file back to source text.
 * Works in browsers, Service Workers, and Node.js 18+.
 *
 * Usage (ES module):
 *
 *   import { loadTokenTable, decodeSpec } from './spectrum-decoder.js';
 *
 *   const tokenTable = await loadTokenTable('./spectrum-tokens.json');
 *   const result     = await decodeSpec(arrayBuffer, tokenTable);
 *   console.log(result.source);
 *
 * The token table only needs to be loaded once; cache it across calls.
 */

// ─────────────────────────────────────────────────────────────────────────────
// Constants — must match spec_encoder.py / spec_decoder.py
// ─────────────────────────────────────────────────────────────────────────────

const MAGIC        = [0x53, 0x50, 0x45, 0x43]; // "SPEC"
const HEADER_SIZE  = 16;
const FLAG_RLE     = 0b00000001;

// Special sentinel IDs in the uint32 stream
const SPEC_ID_RLE     = 0xFFFFFFFD; // followed by: uint32 repeat count
const SPEC_ID_UNICODE = 0xFFFFFFFE; // followed by: uint32 Unicode code point

// Language IDs (matches spec_encoder.py LANGUAGE_* constants)
const LANGUAGE_TEXT = 4;

// CTRL tokens used by the English text reconstructor
const T_CAP_FIRST  = "CTRL:CAP_FIRST";
const T_CAP_ALL    = "CTRL:CAP_ALL";
const T_BEGIN_WORD = "CTRL:BEGIN_WORD";
const T_END_WORD   = "CTRL:END_WORD";
const T_NUM_SEP    = "CTRL:NUM_SEP";


// ─────────────────────────────────────────────────────────────────────────────
// Header parsing
// ─────────────────────────────────────────────────────────────────────────────

function parseHeader(view) {
  if (view.byteLength < HEADER_SIZE) {
    throw new SpecFormatError("File too short to contain a valid header.");
  }

  for (let i = 0; i < 4; i++) {
    if (view.getUint8(i) !== MAGIC[i]) {
      throw new SpecFormatError(
        `Bad magic bytes: expected "SPEC", got "${String.fromCharCode(
          view.getUint8(0), view.getUint8(1), view.getUint8(2), view.getUint8(3)
        )}". Is this a .spec file?`
      );
    }
  }

  const dictVersion = view.getUint16(4,  false); // big-endian
  const flags       = view.getUint16(6,  false);
  const origLength  = view.getUint32(8,  false);
  const languageId  = view.getUint16(12, false);
  const checksum    = view.getUint16(14, false);

  return {
    dictVersion,
    flags,
    origLength,
    languageId,
    checksum,
    rleEnabled: !!(flags & FLAG_RLE),
  };
}


// ─────────────────────────────────────────────────────────────────────────────
// zlib decompression  (uses native DecompressionStream — no dependencies)
// DecompressionStream('deflate') handles RFC 1950 / zlib format, which is
// exactly what Python's zlib.compress() produces.
//
// Uses pipeThrough — avoids the writer/reader deadlock that occurs in Chrome's
// SW context when await writer.close() blocks until the readable is fully
// consumed (but we haven't started reading yet). pipeThrough handles
// backpressure automatically.
// ─────────────────────────────────────────────────────────────────────────────

async function zlibDecompress(compressed) {
  const stream = new Blob([compressed])
    .stream()
    .pipeThrough(new DecompressionStream('deflate'));
  return new Uint8Array(await new Response(stream).arrayBuffer());
}


// ─────────────────────────────────────────────────────────────────────────────
// ID stream → token strings
// ─────────────────────────────────────────────────────────────────────────────

/**
 * Decode a uint32 ID stream back to token strings.
 *
 * @param {Uint32Array} ids        - Decoded uint32 LE stream from the .spec body
 * @param {string[]}    tokenTable - SPEC_TOKENS array (index == ID)
 * @returns {string[]}
 */
function idsToTokens(ids, tokenTable) {
  const asciiBase = tokenTable.length; // IDs [asciiBase … asciiBase+127] = ASCII chars
  const tokens    = [];
  let   lastTok   = null;

  for (let i = 0; i < ids.length; i++) {
    const val = ids[i];

    // ── RLE marker: next ID is the repeat count ───────────────────────────
    if (val === SPEC_ID_RLE) {
      const count = ids[++i];
      if (lastTok !== null) {
        for (let j = 0; j < count; j++) tokens.push(lastTok);
      }
      continue;
    }

    // ── Unicode fallback (code points > 127): next ID is the code point ──
    if (val === SPEC_ID_UNICODE) {
      const cp  = ids[++i];
      const tok = String.fromCodePoint(cp);
      tokens.push(tok);
      lastTok = tok;
      continue;
    }

    // ── ASCII fallback (IDs asciiBase … asciiBase+127) ────────────────────
    if (val >= asciiBase && val < asciiBase + 128) {
      const tok = String.fromCharCode(val - asciiBase);
      tokens.push(tok);
      lastTok = tok;
      continue;
    }

    // ── Dictionary token ──────────────────────────────────────────────────
    const tok = tokenTable[val];
    if (tok === undefined) {
      throw new SpecFormatError(
        `Unknown token ID ${val} at stream position ${i}. ` +
        `The file may have been encoded with a newer dictionary version. ` +
        `Upgrade spectrum-tokens.json.`
      );
    }
    tokens.push(tok);
    lastTok = tok;
  }

  return tokens;
}


// ─────────────────────────────────────────────────────────────────────────────
// English text reconstructor
// Mirrors tokenizers/text_tokenizer.py :: reconstruct_text()
// ─────────────────────────────────────────────────────────────────────────────

function applyCap(word, capMode) {
  if (!word || capMode === null) return word;
  if (capMode === "first") return word[0].toUpperCase() + word.slice(1);
  if (capMode === "all")   return word.toUpperCase();
  return word;
}

function reconstructText(tokens) {
  const result      = [];
  let   capMode     = null;
  let   spelling    = [];
  let   inSpelled   = false;

  for (const tok of tokens) {
    if (tok === T_CAP_FIRST) { capMode = "first"; continue; }
    if (tok === T_CAP_ALL)   { capMode = "all";   continue; }

    if (tok === T_BEGIN_WORD) {
      inSpelled = true;
      spelling  = [];
      continue;
    }

    if (tok === T_END_WORD) {
      result.push(applyCap(spelling.join(""), capMode));
      capMode   = null;
      inSpelled = false;
      spelling  = [];
      continue;
    }

    if (tok === T_NUM_SEP) continue; // no-op on decode

    if (inSpelled) {
      spelling.push(tok);
      continue;
    }

    result.push(applyCap(tok, capMode));
    capMode = null;
  }

  return result.join("");
}


// ─────────────────────────────────────────────────────────────────────────────
// Custom error class
// ─────────────────────────────────────────────────────────────────────────────

class SpecFormatError extends Error {
  constructor(message) {
    super(message);
    this.name = "SpecFormatError";
  }
}


// ─────────────────────────────────────────────────────────────────────────────
// Main decode function
// ─────────────────────────────────────────────────────────────────────────────

/**
 * Decode a .spec file buffer back to source text.
 *
 * @param {ArrayBuffer|Uint8Array} buffer     - Raw .spec file bytes
 * @param {string[]}               tokenTable - SPEC_TOKENS array from loadTokenTable()
 *
 * @returns {Promise<{
 *   source:     string,   // decoded source text
 *   meta:       object,   // parsed header fields
 *   checksumOk: boolean,  // whether the decoded checksum matches the header
 *   tokenCount: number,   // number of tokens decoded
 * }>}
 */
export async function decodeSpec(buffer, tokenTable) {
  // Normalise input to ArrayBuffer
  let ab;
  if (buffer instanceof ArrayBuffer) {
    ab = buffer;
  } else if (ArrayBuffer.isView(buffer)) {
    ab = buffer.buffer.slice(buffer.byteOffset, buffer.byteOffset + buffer.byteLength);
  } else {
    throw new TypeError("buffer must be an ArrayBuffer or TypedArray");
  }

  const view  = new DataView(ab);
  const bytes = new Uint8Array(ab);

  // 1. Parse header
  const meta = parseHeader(view);

  // 2. Decompress the body (everything after the 16-byte header)
  const body      = bytes.slice(HEADER_SIZE);
  const rawStream = await zlibDecompress(body);

  // 3. Unpack uint32 LE stream
  const count      = Math.floor(rawStream.length / 4);
  const streamView = new DataView(rawStream.buffer, rawStream.byteOffset, rawStream.byteLength);
  const ids        = new Uint32Array(count);
  for (let i = 0; i < count; i++) {
    ids[i] = streamView.getUint32(i * 4, true); // true = little-endian
  }

  // 4. Decode IDs → token strings
  const tokens = idsToTokens(ids, tokenTable);

  // 5. Reconstruct source (language-specific)
  let source;
  if (meta.languageId === LANGUAGE_TEXT) {
    source = reconstructText(tokens);
  } else {
    source = tokens.join("");
  }

  // 6. Truncate to original byte length (encoder guarantees this is exact)
  const te = new TextEncoder();
  const td = new TextDecoder();
  let sourceBytes = te.encode(source);
  if (sourceBytes.length > meta.origLength) {
    sourceBytes = sourceBytes.slice(0, meta.origLength);
    source      = td.decode(sourceBytes);
  }

  // 7. Verify checksum (sum of source bytes, mod 2^16)
  let sum = 0;
  for (let i = 0; i < sourceBytes.length; i++) sum += sourceBytes[i];
  const checksumOk = (sum & 0xFFFF) === meta.checksum;

  return { source, meta, checksumOk, tokenCount: tokens.length };
}


// ─────────────────────────────────────────────────────────────────────────────
// Token table loader
// ─────────────────────────────────────────────────────────────────────────────

/**
 * Fetch and parse the SPEC_TOKENS JSON array.
 * Call once at startup; pass the result to every decodeSpec() call.
 *
 * @param {string} url  - URL or file:// path to spectrum-tokens.json
 * @returns {Promise<string[]>}
 */
export async function loadTokenTable(url) {
  const resp = await fetch(url);
  if (!resp.ok) {
    throw new Error(`Failed to load token table from "${url}": HTTP ${resp.status}`);
  }
  return resp.json();
}


// ─────────────────────────────────────────────────────────────────────────────
// Named exports (also available as default for convenience)
// ─────────────────────────────────────────────────────────────────────────────

export { SpecFormatError };
export default { decodeSpec, loadTokenTable, SpecFormatError };
