"""
Spectrum Algo — .spec Encoder v1
Converts a source file into a compact binary .spec file.

.spec file structure
─────────────────────────────────────────────────────────────────────────────
Header (16 bytes, uncompressed):
  [0:4]   Magic:           b'SPEC'
  [4:6]   Dict version:    uint16 BE
  [6:8]   Flags:           uint16 BE
                             bit 0 = RLE enabled
  [8:12]  Original length: uint32 BE  (bytes in original UTF-8 source)
  [12:14] Language ID:     uint16 BE  (0=Python, 1=HTML, 2=JS — future use)
  [14:16] Checksum:        uint16 BE  (sum of all original bytes mod 65536)

Body (zlib-compressed, level 9):
  Sequence of uint32 LE token IDs.
  (Upgraded from uint16 in v7 to accommodate the 234K+ English word dictionary.)

  Token ID scheme:
    0  …  N-1              dictionary token (N = len(SPEC_TOKENS))
    N  …  N+127            ASCII fallback char  (ID = N + ord(char))
    0xFFFFFFFD (4294967293) RLE marker — followed by one more uint32 = repeat count
                            (repeat count = how many MORE times to emit previous token)
    0xFFFFFFFE (4294967294) Unicode fallback (char > 127) — followed by one more
                            uint32 = the full Unicode code point
    0xFFFFFFFF              reserved

RLE threshold: runs of 3+ identical token IDs.
  A run of N → emit ID once, then emit SPEC_ID_RLE, then emit (N-1) as uint16.
  Run of 1 or 2 → emit normally (no saving at run=2, no overhead at run=1).

Why 2 bytes per token beats 3 bytes (RGB pixel)?
  • Smaller raw stream before compression
  • RLE operates on meaningful token IDs — common patterns (indent runs,
    keyword clusters) compress harder than RGB triples with DEFLATE
  • No PNG row-filter overhead / image container
─────────────────────────────────────────────────────────────────────────────
"""

import sys
import struct
import zlib
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import dictionary as D
from encoder.encoder import tokenise_source
from tokenizers.html_tokenizer import tokenise_html
from tokenizers.js_tokenizer import tokenise_js
from tokenizers.css_tokenizer import tokenise_css
from tokenizers.text_tokenizer import tokenize_text
from tokenizers.ts_tokenizer import tokenise_ts
from tokenizers.sql_tokenizer import tokenise_sql
from tokenizers.rust_tokenizer import tokenise_rust
from tokenizers.php_tokenizer import tokenise_php

# ─────────────────────────────────────────────────────────────────────────────
# Constants
# ─────────────────────────────────────────────────────────────────────────────
MAGIC      = b'SPEC'
LANGUAGE_PYTHON = 0
LANGUAGE_HTML   = 1
LANGUAGE_JS     = 2
LANGUAGE_CSS    = 3
LANGUAGE_TEXT   = 4
LANGUAGE_TS     = 5
LANGUAGE_SQL    = 6
LANGUAGE_RUST   = 7
LANGUAGE_PHP    = 8

FLAG_RLE = 0b0000_0001

# Extension → language ID
_EXT_TO_LANG = {
    ".py":   LANGUAGE_PYTHON,
    ".html": LANGUAGE_HTML,
    ".htm":  LANGUAGE_HTML,
    ".js":   LANGUAGE_JS,
    ".mjs":  LANGUAGE_JS,
    ".cjs":  LANGUAGE_JS,
    ".css":  LANGUAGE_CSS,
    ".txt":  LANGUAGE_TEXT,
    ".md":   LANGUAGE_TEXT,
    ".ts":   LANGUAGE_TS,
    ".tsx":  LANGUAGE_TS,
    ".sql":  LANGUAGE_SQL,
    ".rs":   LANGUAGE_RUST,
    ".php":  LANGUAGE_PHP,
    ".phtml":LANGUAGE_PHP,
}

_LANG_NAMES = {
    LANGUAGE_PYTHON: "Python",
    LANGUAGE_HTML:   "HTML",
    LANGUAGE_JS:     "JS",
    LANGUAGE_CSS:    "CSS",
    LANGUAGE_TEXT:   "Text",
    LANGUAGE_TS:     "TypeScript",
    LANGUAGE_SQL:    "SQL",
    LANGUAGE_RUST:   "Rust",
    LANGUAGE_PHP:    "PHP",
}


# ─────────────────────────────────────────────────────────────────────────────
# Token → ID
# ─────────────────────────────────────────────────────────────────────────────

def token_to_spec_id(tok: str) -> list[int]:
    """
    Convert a single token string to one or more uint16 IDs.

    Dictionary tokens    → [id]
    Single ASCII char    → [ascii_base + ord]
    Single Unicode char  → [SPEC_ID_UNICODE, hi_word, lo_word]
    Multi-char fallback  → each character encoded individually (recursive)
    """
    if tok in D.TOKEN_TO_SPEC_ID:
        return [D.TOKEN_TO_SPEC_ID[tok]]

    # Multi-char fallback: split and encode each character
    if len(tok) > 1:
        ids: list[int] = []
        for ch in tok:
            ids.extend(token_to_spec_id(ch))
        return ids

    # Single character fallback
    cp = ord(tok)
    if cp <= 127:
        return [D.SPEC_ID_ASCII_BASE + cp]
    else:
        return [D.SPEC_ID_UNICODE, cp]


def tokens_to_ids(tokens: list[str]) -> list[int]:
    """Convert a token list to a flat list of uint16 IDs."""
    ids = []
    for tok in tokens:
        ids.extend(token_to_spec_id(tok))
    return ids


# ─────────────────────────────────────────────────────────────────────────────
# RLE on the ID stream
# ─────────────────────────────────────────────────────────────────────────────

def apply_rle_ids(ids: list[int]) -> list[int]:
    """
    Compress runs of identical IDs using the SPEC_ID_RLE marker.

    Only applied to simple single-ID tokens (not multi-ID fallback sequences).
    Run of N identical IDs (N ≥ 3):  ID, SPEC_ID_RLE, (N-1)
      → 3 uint16s instead of N  (saves N-3 values for N ≥ 4; break-even at 3)
    """
    result = []
    i = 0
    n = len(ids)
    while i < n:
        val = ids[i]
        # Don't RLE-compress special marker IDs themselves
        if val in (D.SPEC_ID_RLE, D.SPEC_ID_UNICODE):
            result.append(val)
            i += 1
            continue
        run = 1
        while i + run < n and ids[i + run] == val:
            run += 1
        result.append(val)
        if run >= 3:
            result.append(D.SPEC_ID_RLE)
            result.append(min(run - 1, 0xFFFFFFFF))  # cap at uint32 max
        elif run == 2:
            result.append(val)
        i += run
    return result


# ─────────────────────────────────────────────────────────────────────────────
# Header
# ─────────────────────────────────────────────────────────────────────────────

def build_header(dict_version: int, original_length: int, checksum: int,
                 flags: int, language_id: int = LANGUAGE_PYTHON) -> bytes:
    return (
        MAGIC
        + struct.pack(">H", dict_version)
        + struct.pack(">H", flags)
        + struct.pack(">I", original_length)
        + struct.pack(">H", language_id)
        + struct.pack(">H", checksum)
    )


# ─────────────────────────────────────────────────────────────────────────────
# Top-level encode
# ─────────────────────────────────────────────────────────────────────────────

def encode_file(source_path: str, output_path: str,
                use_rle: bool = True,
                language_id: int = LANGUAGE_PYTHON,
                zlib_level: int = 9) -> dict:
    """
    Encode a source file to a .spec binary.

    Returns a stats dict with sizes and compression ratios.
    """
    source_path  = Path(source_path)
    output_path  = Path(output_path)

    source        = source_path.read_text(encoding="utf-8", errors="replace")
    source_bytes  = source.encode("utf-8")
    original_size = len(source_bytes)
    checksum      = sum(source_bytes) & 0xFFFF

    # Auto-detect language from extension if not specified
    if language_id == LANGUAGE_PYTHON:
        ext = source_path.suffix.lower()
        language_id = _EXT_TO_LANG.get(ext, LANGUAGE_PYTHON)

    lang_name = _LANG_NAMES.get(language_id, f"lang{language_id}")

    # Tokenise using the appropriate tokenizer
    if language_id == LANGUAGE_HTML:
        tokens = tokenise_html(source)
    elif language_id == LANGUAGE_JS:
        tokens = tokenise_js(source)
    elif language_id == LANGUAGE_CSS:
        tokens = tokenise_css(source)
    elif language_id == LANGUAGE_TEXT:
        tokens = tokenize_text(source)
    elif language_id == LANGUAGE_TS:
        tokens = tokenise_ts(source)
    elif language_id == LANGUAGE_SQL:
        tokens = tokenise_sql(source)
    elif language_id == LANGUAGE_RUST:
        tokens = tokenise_rust(source)
    elif language_id == LANGUAGE_PHP:
        tokens = tokenise_php(source)
    else:
        tokens = tokenise_source(source)

    print(f"[spec_enc] {len(tokens):,} tokens from {source_path.name} [{lang_name}]")

    # Token → ID stream
    ids = tokens_to_ids(tokens)
    raw_id_count = len(ids)

    # RLE on ID stream
    flags = 0
    if use_rle:
        ids = apply_rle_ids(ids)
        flags |= FLAG_RLE
        rle_saved = raw_id_count - len(ids)
        print(f"[spec_enc] RLE: {raw_id_count:,} → {len(ids):,} IDs "
              f"(saved {rle_saved:,}, {100*rle_saved/max(raw_id_count,1):.1f}%)")

    # Pack as uint32 LE (upgraded from uint16 in v7)
    raw_stream = struct.pack(f"<{len(ids)}I", *ids)

    # Compress
    compressed = zlib.compress(raw_stream, level=zlib_level)

    # Build file
    header = build_header(D.DICT_VERSION, original_size, checksum,
                          flags, language_id)
    output_bytes = header + compressed

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_bytes(output_bytes)

    spec_size = len(output_bytes)
    stats = {
        "source_path":   str(source_path),
        "output_path":   str(output_path),
        "original_size": original_size,
        "spec_size":     spec_size,
        "token_count":   len(tokens),
        "raw_stream_bytes": len(raw_stream),
        "compressed_bytes": len(compressed),
        "ratio":         round(spec_size / original_size, 4),
        "use_rle":       use_rle,
    }

    print(f"[spec_enc] Saved {output_path.name}  "
          f"({original_size:,} B → {spec_size:,} B, "
          f"ratio {stats['ratio']:.4f}x)")

    return stats


# ─────────────────────────────────────────────────────────────────────────────
# CLI
# ─────────────────────────────────────────────────────────────────────────────

def main():
    import argparse
    parser = argparse.ArgumentParser(
        description="Spectrum Algo .spec Encoder — source → binary")
    parser.add_argument("source", help="Path to source file")
    parser.add_argument("--out", default=None,
                        help="Output .spec path (default: spec_format/output/<stem>.spec)")
    parser.add_argument("--no-rle", action="store_true",
                        help="Disable RLE compression")
    parser.add_argument("--zlib-level", type=int, default=9,
                        help="zlib compression level 1–9 (default: 9)")
    parser.add_argument("--lang",
                        choices=["py", "html", "js", "css", "txt", "ts", "sql", "rs", "php"],
                        default=None,
                        help="Force language (default: auto-detect from extension)")
    args = parser.parse_args()

    src = Path(args.source)
    if not src.exists():
        print(f"Error: {src} not found", file=sys.stderr)
        sys.exit(1)

    if args.out:
        out = Path(args.out)
    else:
        out_dir = Path(__file__).resolve().parent / "output"
        out = out_dir / (src.stem + ".spec")

    lang_map = {
        "py":   LANGUAGE_PYTHON,
        "html": LANGUAGE_HTML,
        "js":   LANGUAGE_JS,
        "css":  LANGUAGE_CSS,
        "txt":  LANGUAGE_TEXT,
        "ts":   LANGUAGE_TS,
        "sql":  LANGUAGE_SQL,
        "rs":   LANGUAGE_RUST,
        "php":  LANGUAGE_PHP,
    }
    lang_id  = lang_map[args.lang] if args.lang else LANGUAGE_PYTHON

    encode_file(str(src), str(out), use_rle=not args.no_rle,
                language_id=lang_id, zlib_level=args.zlib_level)


if __name__ == "__main__":
    main()
