/**
 * Spectrum Algo — JS Decoder Round-Trip Test
 *
 * Usage:
 *   node test-decoder.mjs <path-to-spec-file> <path-to-original-file>
 *
 * Example:
 *   node test-decoder.mjs /tmp/test_decode.spec ../spec_format/spec_decoder.py
 *
 * What it does:
 *   1. Loads spectrum-tokens.json from the same directory as this file
 *   2. Reads the .spec file
 *   3. Decodes it with spectrum-decoder.js
 *   4. Compares output to the original file byte-for-byte
 *   5. Reports pass / fail with details
 */

import { readFile } from "fs/promises";
import { resolve, dirname } from "path";
import { fileURLToPath } from "url";
import { decodeSpec, loadTokenTable } from "./spectrum-decoder.js";

const __dir = dirname(fileURLToPath(import.meta.url));

// ── Args ─────────────────────────────────────────────────────────────────────

const [,, specArg, origArg] = process.argv;

if (!specArg || !origArg) {
  console.error("Usage: node test-decoder.mjs <spec-file> <original-file>");
  process.exit(1);
}

const specPath = resolve(specArg);
const origPath = resolve(origArg);
const tokenTablePath = resolve(__dir, "spectrum-tokens.json");

// ── Helpers ──────────────────────────────────────────────────────────────────

function pass(msg)  { console.log(`  ✓  ${msg}`); }
function fail(msg)  { console.error(`  ✗  ${msg}`); }
function info(msg)  { console.log(`     ${msg}`); }

// ── Main ─────────────────────────────────────────────────────────────────────

async function main() {
  console.log("\nSpectrum Algo — JS Decoder Round-Trip Test");
  console.log("═".repeat(50));

  // 1. Load token table
  process.stdout.write("Loading token table … ");
  let tokenTable;
  try {
    // Use readFile + JSON.parse (no fetch needed in Node test)
    const raw = await readFile(tokenTablePath, "utf8");
    tokenTable = JSON.parse(raw);
    console.log(`${tokenTable.length.toLocaleString()} tokens`);
  } catch (e) {
    console.log("FAILED");
    fail(`Could not load ${tokenTablePath}: ${e.message}`);
    process.exit(1);
  }

  // 2. Read .spec file
  process.stdout.write("Reading .spec file    … ");
  let specBuffer;
  try {
    specBuffer = (await readFile(specPath)).buffer;
    console.log(`${(specBuffer.byteLength / 1024).toFixed(1)} KB`);
  } catch (e) {
    console.log("FAILED");
    fail(`Could not read ${specPath}: ${e.message}`);
    process.exit(1);
  }

  // 3. Decode
  process.stdout.write("Decoding              … ");
  let result;
  const t0 = performance.now();
  try {
    result = await decodeSpec(specBuffer, tokenTable);
    const ms = (performance.now() - t0).toFixed(1);
    console.log(`${result.tokenCount.toLocaleString()} tokens → ${result.source.length.toLocaleString()} chars  (${ms} ms)`);
  } catch (e) {
    console.log("FAILED");
    fail(`decodeSpec threw: ${e.message}`);
    process.exit(1);
  }

  // 4. Read original file
  let original;
  try {
    original = await readFile(origPath, "utf8");
  } catch (e) {
    fail(`Could not read original file ${origPath}: ${e.message}`);
    process.exit(1);
  }

  // 5. Compare
  console.log("\nResults");
  console.log("─".repeat(50));
  info(`Dict version  : ${result.meta.dictVersion}`);
  info(`Language ID   : ${result.meta.languageId}`);
  info(`Orig length   : ${result.meta.origLength.toLocaleString()} bytes`);
  info(`Decoded length: ${new TextEncoder().encode(result.source).length.toLocaleString()} bytes`);
  info(`Checksum      : ${result.checksumOk ? "✓ match" : "✗ MISMATCH"}`);

  console.log("\nFidelity checks");
  console.log("─".repeat(50));

  let allPassed = true;

  // Checksum
  if (result.checksumOk) {
    pass("Checksum matches");
  } else {
    fail("Checksum MISMATCH");
    allPassed = false;
  }

  // Length match
  const decodedBytes = new TextEncoder().encode(result.source).length;
  if (decodedBytes === result.meta.origLength) {
    pass(`Decoded length matches (${decodedBytes.toLocaleString()} bytes)`);
  } else {
    fail(`Length mismatch: decoded ${decodedBytes} vs expected ${result.meta.origLength}`);
    allPassed = false;
  }

  // Content match
  if (result.source === original) {
    pass("Content matches original byte-for-byte");
  } else {
    fail("Content MISMATCH");
    allPassed = false;
    // Show first diff
    for (let i = 0; i < Math.min(result.source.length, original.length); i++) {
      if (result.source[i] !== original[i]) {
        const ctx = 40;
        const start = Math.max(0, i - 10);
        info(`First diff at char ${i}`);
        info(`  decoded : ${JSON.stringify(result.source.slice(start, start + ctx))}`);
        info(`  original: ${JSON.stringify(original.slice(start, start + ctx))}`);
        break;
      }
    }
    if (result.source.length !== original.length) {
      info(`  decoded length: ${result.source.length}, original length: ${original.length}`);
    }
  }

  console.log("\n" + "═".repeat(50));
  if (allPassed) {
    console.log("  PASS — JS decoder round-trip verified ✓");
  } else {
    console.log("  FAIL — see above for details ✗");
  }
  console.log("═".repeat(50) + "\n");

  process.exit(allPassed ? 0 : 1);
}

main().catch(e => {
  console.error("Unexpected error:", e);
  process.exit(1);
});
