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
  [12:14] Language ID:     uint16 BE  (0=Python, 1=HTML, 2=JS, 3=CSS,
                                       4=Text, 5=TS, 6=SQL, 7=Rust, 8=PHP,
                                       9=XML-compatible, 10=Java, 11=C, 12=C++,
                                       13=Go, 14=C#, 15=Shell, 16=JSON,
                                       17=YAML, 18=TOML)
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
  A run of N → emit ID once, then emit SPEC_ID_RLE, then emit (N-1) as uint32.
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
from spec_format.extension_tokens import extension_token_to_id
from tokenizers.html_tokenizer import tokenise_html
from tokenizers.js_tokenizer import tokenise_js
from tokenizers.css_tokenizer import tokenise_css
from tokenizers.text_tokenizer import tokenize_text
from tokenizers.xml_tokenizer import tokenize_xml_compatible_source
from tokenizers.ts_tokenizer import tokenise_ts
from tokenizers.sql_tokenizer import tokenise_sql
from tokenizers.rust_tokenizer import tokenise_rust
from tokenizers.php_tokenizer import tokenise_php
from tokenizers.java_tokenizer import tokenise_java
from tokenizers.c_tokenizer import tokenise_c
from tokenizers.cpp_tokenizer import tokenise_cpp
from tokenizers.go_tokenizer import tokenise_go
from tokenizers.csharp_tokenizer import tokenise_csharp
from tokenizers.shell_tokenizer import tokenise_shell
from tokenizers.config_tokenizer import tokenise_config

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
LANGUAGE_XML    = 9
LANGUAGE_JAVA   = 10
LANGUAGE_C      = 11
LANGUAGE_CPP    = 12
LANGUAGE_GO     = 13
LANGUAGE_CSHARP = 14
LANGUAGE_SHELL  = 15
LANGUAGE_JSON   = 16
LANGUAGE_YAML   = 17
LANGUAGE_TOML   = 18

FLAG_RLE = 0b0000_0001
RLE_MODE_OFF = "off"
RLE_MODE_AUTO = "auto"
RLE_MODE_FORCE = "force"
RLE_MODES = (RLE_MODE_OFF, RLE_MODE_AUTO, RLE_MODE_FORCE)
DEFAULT_RLE_MIN_SAVINGS = 0.02
DEFAULT_RLE_BLOCK_SIZE = 65_536

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
    ".xml":  LANGUAGE_XML,
    ".java": LANGUAGE_JAVA,
    ".c":    LANGUAGE_C,
    ".h":    LANGUAGE_C,
    ".cpp":  LANGUAGE_CPP,
    ".cc":   LANGUAGE_CPP,
    ".cxx":  LANGUAGE_CPP,
    ".hpp":  LANGUAGE_CPP,
    ".hh":   LANGUAGE_CPP,
    ".hxx":  LANGUAGE_CPP,
    ".go":   LANGUAGE_GO,
    ".cs":   LANGUAGE_CSHARP,
    ".sh":   LANGUAGE_SHELL,
    ".bash": LANGUAGE_SHELL,
    ".zsh":  LANGUAGE_SHELL,
    ".json": LANGUAGE_JSON,
    ".yaml": LANGUAGE_YAML,
    ".yml":  LANGUAGE_YAML,
    ".toml": LANGUAGE_TOML,
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
    LANGUAGE_XML:    "XML-compatible",
    LANGUAGE_JAVA:   "Java",
    LANGUAGE_C:      "C",
    LANGUAGE_CPP:    "C++",
    LANGUAGE_GO:     "Go",
    LANGUAGE_CSHARP: "C#",
    LANGUAGE_SHELL:  "Shell",
    LANGUAGE_JSON:   "JSON",
    LANGUAGE_YAML:   "YAML",
    LANGUAGE_TOML:   "TOML",
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

    extension_id = extension_token_to_id(tok)
    if extension_id is not None:
        return [extension_id]

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
    token_map = D.TOKEN_TO_SPEC_ID
    ascii_base = D.SPEC_ID_ASCII_BASE
    unicode_marker = D.SPEC_ID_UNICODE
    ext_lookup = extension_token_to_id
    ids = []
    append = ids.append
    extend = ids.extend
    for tok in tokens:
        token_id = token_map.get(tok)
        if token_id is not None:
            append(token_id)
            continue

        extension_id = ext_lookup(tok)
        if extension_id is not None:
            append(extension_id)
            continue

        if len(tok) == 1:
            cp = ord(tok)
            if cp <= 127:
                append(ascii_base + cp)
            else:
                append(unicode_marker)
                append(cp)
            continue

        for ch in tok:
            token_id = token_map.get(ch)
            if token_id is not None:
                append(token_id)
                continue
            cp = ord(ch)
            if cp <= 127:
                append(ascii_base + cp)
            else:
                extend((unicode_marker, cp))
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


def normalize_rle_mode(use_rle: bool | str) -> str:
    """Accept the old bool API and the newer explicit mode strings."""
    if isinstance(use_rle, bool):
        return RLE_MODE_FORCE if use_rle else RLE_MODE_OFF
    mode = use_rle.lower()
    if mode not in RLE_MODES:
        raise ValueError(f"unknown RLE mode {use_rle!r}; expected one of {', '.join(RLE_MODES)}")
    return mode


def apply_rle_ids_auto(
    ids: list[int],
    min_savings: float = DEFAULT_RLE_MIN_SAVINGS,
    block_size: int = DEFAULT_RLE_BLOCK_SIZE,
    zlib_level: int = 9,
) -> tuple[list[int], int, int]:
    """
    Sample RLE after packing and zlib first. If the sample wins, apply RLE
    independently per block and keep blocks with enough raw ID savings.
    """
    if block_size <= 0:
        raise ValueError("rle_block_size must be greater than zero")
    if not ids:
        return ids, 0, 0

    sample = ids[:block_size]
    encoded_sample = apply_rle_ids(sample)
    raw_sample = struct.pack(f"<{len(sample)}I", *sample)
    rle_sample = struct.pack(f"<{len(encoded_sample)}I", *encoded_sample)
    raw_sample_size = len(zlib.compress(raw_sample, level=zlib_level))
    rle_sample_size = len(zlib.compress(rle_sample, level=zlib_level))
    sampled_savings = (raw_sample_size - rle_sample_size) / max(raw_sample_size, 1)
    if sampled_savings < min_savings:
        return ids, 0, 0

    result: list[int] = []
    encoded_blocks = 0
    total_blocks = 0
    for start in range(0, len(ids), block_size):
        block = ids[start:start + block_size]
        encoded = apply_rle_ids(block)
        total_blocks += 1
        saved = len(block) - len(encoded)
        if saved > 0 and saved / max(len(block), 1) >= min_savings:
            result.extend(encoded)
            encoded_blocks += 1
        else:
            result.extend(block)
    return result, encoded_blocks, total_blocks


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
                use_rle: bool | str = RLE_MODE_OFF,
                language_id: int = LANGUAGE_PYTHON,
                zlib_level: int = 9,
                rle_min_savings: float = DEFAULT_RLE_MIN_SAVINGS,
                rle_block_size: int = DEFAULT_RLE_BLOCK_SIZE) -> dict:
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
    elif language_id == LANGUAGE_XML:
        tokens = tokenize_xml_compatible_source(source)
    elif language_id == LANGUAGE_JAVA:
        tokens = tokenise_java(source)
    elif language_id == LANGUAGE_C:
        tokens = tokenise_c(source)
    elif language_id == LANGUAGE_CPP:
        tokens = tokenise_cpp(source)
    elif language_id == LANGUAGE_GO:
        tokens = tokenise_go(source)
    elif language_id == LANGUAGE_CSHARP:
        tokens = tokenise_csharp(source)
    elif language_id == LANGUAGE_SHELL:
        tokens = tokenise_shell(source)
    elif language_id in (LANGUAGE_JSON, LANGUAGE_YAML, LANGUAGE_TOML):
        tokens = tokenise_config(source)
    else:
        tokens = tokenise_source(source)

    print(f"[spec_enc] {len(tokens):,} tokens from {source_path.name} [{lang_name}]")

    # Token → ID stream
    ids = tokens_to_ids(tokens)
    raw_id_count = len(ids)

    # RLE on ID stream
    flags = 0
    rle_mode = normalize_rle_mode(use_rle)
    rle_blocks_encoded = 0
    rle_blocks_total = 0
    if rle_mode == RLE_MODE_FORCE:
        ids = apply_rle_ids(ids)
        flags |= FLAG_RLE
        rle_saved = raw_id_count - len(ids)
        print(f"[spec_enc] RLE: {raw_id_count:,} → {len(ids):,} IDs "
              f"(saved {rle_saved:,}, {100*rle_saved/max(raw_id_count,1):.1f}%)")

    elif rle_mode == RLE_MODE_AUTO:
        ids, rle_blocks_encoded, rle_blocks_total = apply_rle_ids_auto(
            ids,
            min_savings=rle_min_savings,
            block_size=rle_block_size,
            zlib_level=zlib_level,
        )
        if rle_blocks_encoded:
            flags |= FLAG_RLE
        rle_saved = raw_id_count - len(ids)
        print(
            f"[spec_enc] RLE auto: {raw_id_count:,} -> {len(ids):,} IDs "
            f"(saved {rle_saved:,}, {100*rle_saved/max(raw_id_count,1):.1f}%; "
            f"{rle_blocks_encoded}/{rle_blocks_total} blocks kept)"
        )

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
        "ratio":         round(spec_size / original_size, 4) if original_size else 0.0,
        "use_rle":       rle_mode != RLE_MODE_OFF,
        "rle_mode":      rle_mode,
        "rle_min_savings": rle_min_savings,
        "rle_blocks_encoded": rle_blocks_encoded,
        "rle_blocks_total": rle_blocks_total,
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
                        help="Deprecated alias for --rle=off")
    parser.add_argument("--rle", choices=RLE_MODES, default=RLE_MODE_OFF,
                        help="RLE mode: off (default), auto, or force")
    parser.add_argument("--rle-min-savings", type=float,
                        default=DEFAULT_RLE_MIN_SAVINGS,
                        help="Minimum per-block ID savings ratio for --rle=auto (default: 0.02)")
    parser.add_argument("--rle-block-size", type=int,
                        default=DEFAULT_RLE_BLOCK_SIZE,
                        help="ID block size for --rle=auto (default: 65536)")
    parser.add_argument("--zlib-level", type=int, default=9,
                        help="zlib compression level 1–9 (default: 9)")
    parser.add_argument("--lang",
                        choices=[
                            "py", "html", "js", "css", "txt", "ts", "sql",
                            "rs", "php", "xml", "java", "c", "cpp", "go",
                            "cs", "sh", "json", "yaml", "toml",
                        ],
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
        "xml":  LANGUAGE_XML,
        "java": LANGUAGE_JAVA,
        "c":    LANGUAGE_C,
        "cpp":  LANGUAGE_CPP,
        "go":   LANGUAGE_GO,
        "cs":   LANGUAGE_CSHARP,
        "sh":   LANGUAGE_SHELL,
        "json": LANGUAGE_JSON,
        "yaml": LANGUAGE_YAML,
        "toml": LANGUAGE_TOML,
    }
    lang_id  = lang_map[args.lang] if args.lang else LANGUAGE_PYTHON

    rle_mode = RLE_MODE_OFF if args.no_rle else args.rle
    encode_file(
        str(src),
        str(out),
        use_rle=rle_mode,
        language_id=lang_id,
        zlib_level=args.zlib_level,
        rle_min_savings=args.rle_min_savings,
        rle_block_size=args.rle_block_size,
    )


if __name__ == "__main__":
    main()
