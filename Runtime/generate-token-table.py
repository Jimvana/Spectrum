"""
Generate spectrum-tokens.json from the Spectrum Algo dictionary.

Exports SPEC_TOKENS as a plain JSON array where index == token ID.
The JS decoder loads this file once to build its ID→token lookup.

Usage:
    python generate-token-table.py

Output:
    Runtime/spectrum-tokens.json   (~1.5 MB, generated — do not edit by hand)
"""

import sys
import json
from pathlib import Path

# Make sure we can import from the project root
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import dictionary as D

OUT_BIN  = Path(__file__).resolve().parent / "spectrum-tokens.bin"  # null-delimited UTF-8 (fast SW parse)
OUT_JSON = Path(__file__).resolve().parent / "spectrum-tokens.json" # JSON (kept for Node test)

tokens = D.SPEC_TOKENS   # ordered list, index == ID

print(f"[gen] SPEC_TOKENS count : {len(tokens):,}")
print(f"[gen] ASCII_BASE        : {D.SPEC_ID_ASCII_BASE:,}")
print(f"[gen] Dict version      : {D.DICT_VERSION}")

# Sanity-check: no token must contain a null byte (that's our delimiter)
bad = [t for t in tokens if '\x00' in t]
if bad:
    raise ValueError(f"{len(bad)} tokens contain null bytes — cannot use .bin format: {bad[:5]}")

# ── .bin: tokens joined by \x00 ──────────────────────────────────────────────
# In the SW: fetch → arrayBuffer → TextDecoder.decode → split('\x00')
# Much faster than JSON.parse for 234k strings.
print(f"[gen] Writing → {OUT_BIN.name} (null-delimited UTF-8) ...")
OUT_BIN.write_bytes('\x00'.join(tokens).encode('utf-8'))
size_kb = OUT_BIN.stat().st_size / 1024
print(f"[gen] Done. {size_kb:,.1f} KB")

# ── .json: kept so test-decoder.mjs still works without changes ──────────────
print(f"[gen] Writing → {OUT_JSON.name} (JSON, for Node tooling) ...")
OUT_JSON.write_text(json.dumps(tokens, ensure_ascii=False, separators=(',', ':')), encoding="utf-8")
size_kb = OUT_JSON.stat().st_size / 1024
print(f"[gen] Done. {size_kb:,.1f} KB")
