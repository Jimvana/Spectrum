"""
Spectrum Algo — Decoder v1
Converts a Spectrum PNG image back into source code.

The decoder:
  1. Reads the header row to verify the image format and extract metadata
     (dictionary version, original file byte length).
  2. Iterates over data pixels row by row, left to right.
  3. For each pixel:
     - If it's in RGB_TO_TOKEN  → use the mapped token string
     - If it's the PAD pixel    → skip (padding, not real data)
     - Otherwise               → treat as fallback-encoded character
  4. Joins all tokens into a single string.
  5. Truncates to the original byte length recorded in the header.

Usage:
    python decoder.py <spectrum.png> [--out output.py]
"""

import sys
import os
import struct
from pathlib import Path
from PIL import Image

# Allow imports from parent directory (where dictionary.py lives)
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import dictionary as D

# ---------------------------------------------------------------------------
# Header parsing
# ---------------------------------------------------------------------------

class SpectrumHeaderError(Exception):
    pass


def parse_header_row(pixels: list[tuple[int, int, int]],
                     width: int) -> dict:
    """
    Parse the header row and return metadata dict.

    Expected layout (see encoder.py for full spec):
      Pixel 0: (0,0,0)           — HEADER_MARKER
      Pixel 1: (v_hi, v_lo, 0)  — dict version
      Pixel 2: (B3, B2, B1)     — high 3 bytes of original length
      Pixel 3: (B0, 0, 0)       — low byte of original length
    """
    if len(pixels) < 4:
        raise SpectrumHeaderError("Header row is too short.")

    # Pixel 0 — verify marker
    if pixels[0] != D.SPECIAL["__HEADER__"]:
        raise SpectrumHeaderError(
            f"Invalid header marker: expected {D.SPECIAL['__HEADER__']}, "
            f"got {pixels[0]}. Is this a Spectrum PNG?")

    # Pixel 1 — dict version
    v_hi, v_lo, _ = pixels[1]
    dict_version = (v_hi << 8) | v_lo

    # Pixels 2–3 — original file length (32-bit)
    b3, b2, b1 = pixels[2]
    b0, _, _ = pixels[3]
    original_length = struct.unpack(">I", bytes([b3, b2, b1, b0]))[0]

    return {
        "dict_version":    dict_version,
        "original_length": original_length,
    }


# ---------------------------------------------------------------------------
# Pixel decoder
# ---------------------------------------------------------------------------

PAD_PIXEL = D.SPECIAL["__PAD__"]


def pixels_to_tokens(data_pixels: list[tuple[int, int, int]]) -> list[str]:
    """
    Convert a flat list of data pixels (from rows 1+) into string tokens.

    Rules:
      - PAD pixel (1,1,1)      → skip
      - RLE marker (R=253)     → repeat the previous token N more times
      - In RGB_TO_TOKEN        → use mapped token
      - Otherwise              → fallback decode as Unicode character
    """
    tokens = []
    last_token: str | None = None

    for px in data_pixels:
        # Skip padding
        if px == PAD_PIXEL:
            continue

        # RLE marker — repeat the previous token N more times
        if D.is_rle_pixel(px):
            if last_token is not None:
                count = D.rle_pixel_count(px)
                tokens.extend([last_token] * count)
            continue

        # Normal token lookup
        token = D.RGB_TO_TOKEN.get(px)
        if token is not None:
            # Skip only the specific internal meta-tokens, not real dunders
            if token in ("__HEADER__", "__PAD__"):
                continue
            tokens.append(token)
            last_token = token
        else:
            # Fallback: decode as Unicode code point
            char = D.fallback_rgb_to_char(px)
            tokens.append(char)
            last_token = char

    return tokens


# ---------------------------------------------------------------------------
# Top-level decode function
# ---------------------------------------------------------------------------

def decode_file(image_path: str, output_path: str) -> dict:
    """
    Decode a Spectrum PNG back to source code.

    Returns a dict with stats:
      image_path, output_path, original_length, decoded_length, match
    """
    image_path = Path(image_path)
    output_path = Path(output_path)

    if not image_path.exists():
        raise FileNotFoundError(f"Image not found: {image_path}")

    # Load image
    img = Image.open(str(image_path)).convert("RGB")
    width, height = img.size
    all_pixels = list(img.get_flattened_data() if hasattr(img, "get_flattened_data") else img.getdata())

    print(f"[decoder] Loaded {image_path.name}  ({width}×{height}px, "
          f"{len(all_pixels)} pixels total)")

    # Parse header row (row 0)
    header_pixels = all_pixels[:width]
    try:
        metadata = parse_header_row(header_pixels, width)
    except SpectrumHeaderError as e:
        print(f"[decoder] ERROR: {e}", file=sys.stderr)
        sys.exit(1)

    dict_version = metadata["dict_version"]
    original_length = metadata["original_length"]

    print(f"[decoder] Header: dict_version={dict_version}, "
          f"original_length={original_length} bytes")

    if dict_version != D.DICT_VERSION:
        print(f"[decoder] WARNING: image was encoded with dict v{dict_version}, "
              f"but we have v{D.DICT_VERSION}. Results may differ.",
              file=sys.stderr)

    # Data pixels start after the header row(s)
    data_pixels = all_pixels[width:]

    # Decode pixels → tokens → source string
    tokens = pixels_to_tokens(data_pixels)
    source = "".join(tokens)

    # Truncate to original byte length (removes any padding artefacts)
    source_bytes = source.encode("utf-8")
    if len(source_bytes) > original_length:
        # Truncate carefully at a character boundary
        source = source_bytes[:original_length].decode("utf-8", errors="replace")
    decoded_length = len(source.encode("utf-8"))

    print(f"[decoder] Decoded {len(tokens)} tokens → {decoded_length} bytes")

    # Write output
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(source, encoding="utf-8")

    # Fidelity indicator
    match = (decoded_length == original_length)
    print(f"[decoder] Saved {output_path.name}  "
          f"({'✓ length matches' if match else '✗ length mismatch'})")

    return {
        "image_path":      str(image_path),
        "output_path":     str(output_path),
        "original_length": original_length,
        "decoded_length":  decoded_length,
        "token_count":     len(tokens),
        "match":           match,
    }


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    import argparse
    parser = argparse.ArgumentParser(
        description="Spectrum Algo Decoder — PNG → source code")
    parser.add_argument("image", help="Path to Spectrum PNG file")
    parser.add_argument("--out", default=None,
                        help="Output file path (default: results/<image_stem>_decoded.py)")
    args = parser.parse_args()

    image_path = Path(args.image)
    if not image_path.exists():
        print(f"Error: image not found: {image_path}", file=sys.stderr)
        sys.exit(1)

    if args.out:
        out_path = Path(args.out)
    else:
        out_dir = Path(__file__).resolve().parent.parent / "results"
        out_path = out_dir / (image_path.stem + "_decoded.py")

    decode_file(str(image_path), str(out_path))


if __name__ == "__main__":
    main()
