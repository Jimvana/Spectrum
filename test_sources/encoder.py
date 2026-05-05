"""
Spectrum Algo — Encoder v1
Converts a source code file into a Spectrum PNG image.

Pixel layout:
  Row 0 (header row):
    Pixel 0: (0,0,0) — HEADER_MARKER, signals this is a Spectrum image
    Pixel 1: (dict_version >> 8, dict_version & 0xFF, 0) — dictionary version
    Pixel 2: (B3, B2, B1) — original file length, high 3 bytes
    Pixel 3: (B0, 0, 0)   — original file length, low byte
    Pixel 4+: (0,0,0) — padding to fill the header row to IMAGE_WIDTH

  Rows 1+: token pixels, left-to-right, top-to-bottom.
    Each token pixel is either:
      - A dictionary lookup pixel: direct colour from TOKEN_TO_RGB
      - A fallback pixel: encodes a single Unicode character by code point

Usage:
    python encoder.py <source_file> [--width 64] [--out output.png]
"""

import sys
import os
import tokenize
import io
import struct
from pathlib import Path
from PIL import Image

# Allow imports from parent directory (where dictionary.py lives)
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import dictionary as D

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
IMAGE_WIDTH = 64          # pixels per row (power of 2 recommended)
HEADER_ROW_COUNT = 1      # how many rows the header occupies


# ---------------------------------------------------------------------------
# Tokeniser
# ---------------------------------------------------------------------------

def tokenise_source(source: str) -> list[str]:
    """
    Tokenise Python source into a flat list of string tokens.

    Strategy:
      1. Use the stdlib `tokenize` module to get Python-aware tokens.
      2. For each token, try to match sub-tokens against the dictionary
         (e.g. the tokeniser gives us '==' as one token — great).
      3. Anything not in the dictionary is emitted character-by-character
         so the fallback encoder handles it.

    We also re-inject whitespace between tokens by comparing source positions,
    so the round-trip reconstruction is exact.
    """
    tokens: list[str] = []
    readline = io.StringIO(source).readline

    try:
        token_list = list(tokenize.generate_tokens(readline))
    except tokenize.TokenError as e:
        print(f"[encoder] tokenize error: {e} — falling back to char-by-char", file=sys.stderr)
        return list(source)  # worst case: every char is a separate token

    prev_end_row = 1
    prev_end_col = 0
    source_lines = source.splitlines(keepends=True)

    for tok in token_list:
        tok_type, tok_string, tok_start, tok_end, _ = tok

        # Skip ENCODING and ENDMARKER pseudo-tokens
        if tok_type in (tokenize.ENCODING, tokenize.ENDMARKER):
            continue

        # Reconstruct exact whitespace gap between previous token and this one
        gap = _extract_gap(source_lines, prev_end_row, prev_end_col,
                           tok_start[0], tok_start[1])
        for ch in gap:
            tokens.append(ch)

        # Emit the token itself
        if tok_type == tokenize.NEWLINE or tok_type == tokenize.NL:
            tokens.append("\n")
        elif tok_type == tokenize.INDENT:
            for ch in tok_string:
                tokens.append(ch)
        elif tok_type == tokenize.DEDENT:
            pass  # DEDENT has no characters — skip
        elif tok_type == tokenize.COMMENT:
            # Emit '#' then the rest char-by-char (comments aren't in dict)
            tokens.append("#")
            for ch in tok_string[1:]:
                tokens.append(ch)
        elif tok_type == tokenize.STRING:
            # Emit the whole string literal char-by-char
            for ch in tok_string:
                tokens.append(ch)
        else:
            # For OP and NAME tokens, try to match against the dictionary first
            _emit_token_or_chars(tok_string, tokens)

        prev_end_row, prev_end_col = tok_end

    return tokens


def _extract_gap(lines: list[str], r1: int, c1: int, r2: int, c2: int) -> str:
    """Extract the source text between (r1,c1) and (r2,c2) (1-indexed rows)."""
    if r1 == r2:
        line = lines[r1 - 1] if r1 <= len(lines) else ""
        return line[c1:c2]
    result = []
    # rest of first line
    if r1 <= len(lines):
        result.append(lines[r1 - 1][c1:])
    # full middle lines
    for r in range(r1 + 1, r2):
        if r <= len(lines):
            result.append(lines[r - 1])
    # start of last line
    if r2 <= len(lines):
        result.append(lines[r2 - 1][:c2])
    return "".join(result)


def _emit_token_or_chars(tok_string: str, tokens: list[str]) -> None:
    """
    Try to emit tok_string as a single dictionary token.
    If not in the dictionary, emit it character-by-character.
    """
    if tok_string in D.TOKEN_TO_RGB:
        tokens.append(tok_string)
    else:
        for ch in tok_string:
            tokens.append(ch)


# ---------------------------------------------------------------------------
# Pixel encoder
# ---------------------------------------------------------------------------

def tokens_to_pixels(tokens: list[str]) -> list[tuple[int, int, int]]:
    """Convert a list of string tokens to a list of RGB pixels."""
    pixels = []
    for tok in tokens:
        if tok in D.TOKEN_TO_RGB:
            pixels.append(D.TOKEN_TO_RGB[tok])
        else:
            # Fallback: encode character by code point
            pixels.append(D.char_to_fallback_rgb(tok))
    return pixels


def apply_rle(pixels: list[tuple[int, int, int]]) -> list[tuple[int, int, int]]:
    """
    Compress runs of identical pixels using RLE marker pixels.

    For a run of N identical pixels (N >= 3):
      Emit the pixel once, then emit make_rle_pixel(N-1).
      Result: 2 pixels instead of N  →  saves N-2 pixels.

    For a run of exactly 2: no saving, just emit both normally.
    For a run of 1: emit normally.

    The RLE marker pixel uses R=253 (reserved), so it can never collide
    with any real token colour.
    """
    result = []
    i = 0
    n = len(pixels)
    while i < n:
        px = pixels[i]
        run = 1
        while i + run < n and pixels[i + run] == px:
            run += 1
        result.append(px)
        if run >= 3:
            result.append(D.make_rle_pixel(run - 1))
        elif run == 2:
            result.append(px)   # just emit it twice, no saving at run=2
        i += run
    return result


# ---------------------------------------------------------------------------
# Header encoding
# ---------------------------------------------------------------------------

def build_header_row(dict_version: int, original_length: int,
                     width: int) -> list[tuple[int, int, int]]:
    """
    Build the header row pixels.

    Pixel 0: HEADER_MARKER (0,0,0)
    Pixel 1: dict version  (v_hi, v_lo, 0)
    Pixel 2: file length   (B3, B2, B1)   — high 3 bytes
    Pixel 3: file length   (B0,  0,  0)   — low byte
    Pixel 4+: PAD
    """
    row = []
    # Pixel 0 — header marker
    row.append(D.SPECIAL["__HEADER__"])
    # Pixel 1 — dictionary version (up to 65535)
    row.append(((dict_version >> 8) & 0xFF, dict_version & 0xFF, 0))
    # Pixels 2–3 — original file length (32-bit big-endian across two pixels)
    length_bytes = struct.pack(">I", original_length)  # 4 bytes
    row.append((length_bytes[0], length_bytes[1], length_bytes[2]))
    row.append((length_bytes[3], 0, 0))
    # Pad remainder
    pad = D.SPECIAL["__PAD__"]
    while len(row) < width:
        row.append(pad)
    return row


# ---------------------------------------------------------------------------
# Image assembly
# ---------------------------------------------------------------------------

def pixels_to_image(data_pixels: list[tuple[int, int, int]],
                    header_row: list[tuple[int, int, int]],
                    width: int) -> Image.Image:
    """
    Pack header + data pixels into a PIL Image.

    Rows: [header_row] + [data rows...]
    Data rows are padded with __PAD__ pixels to fill the last row.
    """
    pad_pixel = D.SPECIAL["__PAD__"]

    # Pad data to a full number of rows
    remainder = len(data_pixels) % width
    if remainder != 0:
        data_pixels = data_pixels + [pad_pixel] * (width - remainder)

    total_data_rows = len(data_pixels) // width
    total_rows = HEADER_ROW_COUNT + total_data_rows
    if total_data_rows == 0:
        total_rows = HEADER_ROW_COUNT + 1  # at least one data row

    img = Image.new("RGB", (width, total_rows))
    all_pixels = header_row[:]

    # Fill remaining header rows if HEADER_ROW_COUNT > 1 (future use)
    for _ in range(HEADER_ROW_COUNT - 1):
        all_pixels.extend([pad_pixel] * width)

    all_pixels.extend(data_pixels)

    # Pad to total size (shouldn't be needed, but defensive)
    expected = width * total_rows
    while len(all_pixels) < expected:
        all_pixels.append(pad_pixel)

    img.putdata(all_pixels)
    return img


# ---------------------------------------------------------------------------
# Top-level encode function
# ---------------------------------------------------------------------------

def encode_file(source_path: str, output_path: str,
                width: int = IMAGE_WIDTH, use_rle: bool = False) -> dict:
    """
    Encode a source file to a Spectrum PNG.

    Returns a dict with stats:
      source_path, output_path, original_size, png_size, token_count, image_size
    """
    source_path = Path(source_path)
    output_path = Path(output_path)

    # Read source
    source = source_path.read_text(encoding="utf-8")
    original_size = len(source.encode("utf-8"))

    # Tokenise
    tokens = tokenise_source(source)
    print(f"[encoder] {len(tokens)} tokens from {source_path.name}")

    # Convert to pixels
    raw_pixels = tokens_to_pixels(tokens)

    # RLE compression (off by default for PNG — PNG's DEFLATE handles runs
    # better than our marker-pixel approach; RLE is more useful for raw output)
    if use_rle:
        data_pixels = apply_rle(raw_pixels)
        rle_saving = len(raw_pixels) - len(data_pixels)
        print(f"[encoder] RLE: {len(raw_pixels)} → {len(data_pixels)} pixels "
              f"(saved {rle_saving} pixels, "
              f"{100 * rle_saving / max(len(raw_pixels), 1):.1f}%)")
    else:
        data_pixels = raw_pixels
        rle_saving = 0

    # Build header
    header_row = build_header_row(D.DICT_VERSION, original_size, width)

    # Assemble image
    img = pixels_to_image(data_pixels, header_row, width)

    # Save as lossless PNG
    output_path.parent.mkdir(parents=True, exist_ok=True)
    img.save(str(output_path), format="PNG")

    png_size = output_path.stat().st_size

    stats = {
        "source_path":   str(source_path),
        "output_path":   str(output_path),
        "original_size": original_size,
        "png_size":      png_size,
        "token_count":   len(tokens),
        "raw_pixels":    len(raw_pixels),
        "rle_pixels":    len(data_pixels),
        "rle_saving":    rle_saving,
        "image_size":    img.size,
        "ratio":         round(png_size / original_size, 3),
    }

    print(f"[encoder] Saved {output_path.name}  "
          f"({original_size} bytes → {png_size} bytes, "
          f"ratio {stats['ratio']}x, "
          f"image {img.size[0]}×{img.size[1]}px)")

    return stats


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    import argparse
    parser = argparse.ArgumentParser(
        description="Spectrum Algo Encoder — source code → PNG")
    parser.add_argument("source", help="Path to source file")
    parser.add_argument("--width", type=int, default=IMAGE_WIDTH,
                        help=f"Image width in pixels (default: {IMAGE_WIDTH})")
    parser.add_argument("--out", default=None,
                        help="Output PNG path (default: output_images/<source>.png)")
    parser.add_argument("--rle", action="store_true", default=False,
                        help="Enable pixel-level RLE compression (experimental; "
                             "hurts PNG output due to DEFLATE interaction, "
                             "useful for future raw binary output)")
    args = parser.parse_args()

    source_path = Path(args.source)
    if not source_path.exists():
        print(f"Error: source file not found: {source_path}", file=sys.stderr)
        sys.exit(1)

    if args.out:
        out_path = Path(args.out)
    else:
        out_dir = Path(__file__).resolve().parent.parent / "output_images"
        out_path = out_dir / (source_path.stem + ".png")

    encode_file(str(source_path), str(out_path), width=args.width, use_rle=args.rle)


if __name__ == "__main__":
    main()
