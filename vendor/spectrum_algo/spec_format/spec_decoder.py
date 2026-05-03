"""
Spectrum Algo — .spec Decoder v1
Converts a .spec binary file back into source code.

See spec_encoder.py for the full format specification.
"""

import sys
import struct
import zlib
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import dictionary as D
from spec_format.extension_tokens import extension_id_to_literal
from tokenizers.text_tokenizer import reconstruct_text
from spec_format._frozen import (
    get_id_to_token_for_version,
    get_ascii_base_for_version,
    MIN_SUPPORTED_VERSION,
)

LANGUAGE_TEXT = 4
LANGUAGE_XML = 9

# ─────────────────────────────────────────────────────────────────────────────
# Constants (must match encoder)
# ─────────────────────────────────────────────────────────────────────────────
MAGIC    = b'SPEC'
FLAG_RLE = 0b0000_0001
HEADER_SIZE = 16


class SpecFormatError(Exception):
    pass


# ─────────────────────────────────────────────────────────────────────────────
# Header parsing
# ─────────────────────────────────────────────────────────────────────────────

def parse_header(data: bytes) -> dict:
    if len(data) < HEADER_SIZE:
        raise SpecFormatError("File too short to contain a valid header.")
    if data[:4] != MAGIC:
        raise SpecFormatError(
            f"Bad magic bytes: expected {MAGIC!r}, got {data[:4]!r}. "
            "Is this a .spec file?")

    dict_version,  = struct.unpack_from(">H", data, 4)
    flags,         = struct.unpack_from(">H", data, 6)
    orig_length,   = struct.unpack_from(">I", data, 8)
    language_id,   = struct.unpack_from(">H", data, 12)
    checksum,      = struct.unpack_from(">H", data, 14)

    return {
        "dict_version": dict_version,
        "flags":        flags,
        "orig_length":  orig_length,
        "language_id":  language_id,
        "checksum":     checksum,
        "rle_enabled":  bool(flags & FLAG_RLE),
    }


# ─────────────────────────────────────────────────────────────────────────────
# ID stream → tokens
# ─────────────────────────────────────────────────────────────────────────────

def ids_to_tokens(
    ids: list[int],
    id_to_token: dict[int, str] | None = None,
    ascii_base: int | None = None,
) -> list[str]:
    """
    Decode a uint32 ID stream (with optional RLE markers) back to token strings.

    id_to_token  — version-specific ID→token map; defaults to current dict.
    ascii_base   — version-specific ASCII fallback base ID; defaults to current.

    ID scheme:
      0 … N-1                  → dictionary token
      N … N+127                → ASCII char (ord = ID - N)
      SPEC_ID_RLE  (0xFFFFFFFD) → repeat previous token (next ID = count)
      SPEC_ID_UNICODE (0xFFFFFFFE) → Unicode char > 127 (next ID = code point)
    """
    if id_to_token is None:
        id_to_token = D.SPEC_ID_TO_TOKEN
    if ascii_base is None:
        ascii_base = D.SPEC_ID_ASCII_BASE

    tokens: list[str] = []
    last_tok: str | None = None
    i = 0
    n = len(ids)

    while i < n:
        val = ids[i]

        # RLE marker
        if val == D.SPEC_ID_RLE:
            if i + 1 >= n:
                raise SpecFormatError(f"RLE marker at position {i} has no count.")
            count = ids[i + 1]
            if last_tok is not None:
                tokens.extend([last_tok] * count)
            i += 2
            continue

        # Unicode fallback (> 127)
        if val == D.SPEC_ID_UNICODE:
            if i + 1 >= n:
                raise SpecFormatError(f"Unicode escape at {i} is truncated.")
            cp = ids[i + 1]
            tok = chr(cp)
            tokens.append(tok)
            last_tok = tok
            i += 2
            continue

        # ASCII fallback (IDs ascii_base … ascii_base+127)
        if ascii_base <= val < ascii_base + 128:
            tok = chr(val - ascii_base)
            tokens.append(tok)
            last_tok = tok
            i += 1
            continue

        # Extension-library token ranges
        extension_literal = extension_id_to_literal(val)
        if extension_literal is not None:
            tokens.append(extension_literal)
            last_tok = extension_literal
            i += 1
            continue

        # Dictionary token
        tok = id_to_token.get(val)
        if tok is None:
            raise SpecFormatError(
                f"Unknown token ID {val} at stream position {i}. "
                f"The file may have been encoded with a newer dictionary version "
                f"than available. Try upgrading Spectrum Algo.")
        tokens.append(tok)
        last_tok = tok
        i += 1

    return tokens


# ─────────────────────────────────────────────────────────────────────────────
# Top-level decode
# ─────────────────────────────────────────────────────────────────────────────

def decode_file(spec_path: str, output_path: str) -> dict:
    """
    Decode a .spec file back to source code.

    Returns a stats dict including fidelity information.
    """
    spec_path   = Path(spec_path)
    output_path = Path(output_path)

    raw = spec_path.read_bytes()
    print(f"[spec_dec] Loaded {spec_path.name}  ({len(raw):,} bytes)")

    # Parse header
    meta = parse_header(raw)
    dict_version = meta["dict_version"]
    orig_length  = meta["orig_length"]
    expected_cksum = meta["checksum"]

    print(f"[spec_dec] Header: dict_v={dict_version}, "
          f"orig={orig_length:,} B, "
          f"rle={meta['rle_enabled']}, "
          f"lang={meta['language_id']}")

    # ── Version compatibility check ──────────────────────────────────────────
    if dict_version < MIN_SUPPORTED_VERSION:
        raise SpecFormatError(
            f"Dict version {dict_version} is below the minimum supported "
            f"version ({MIN_SUPPORTED_VERSION}). Re-encode from original source."
        )

    if dict_version == D.DICT_VERSION:
        # Current version — use live dict directly (fastest path)
        id_to_token = D.SPEC_ID_TO_TOKEN
        ascii_base  = D.SPEC_ID_ASCII_BASE
        compat_note = ""
    elif dict_version < D.DICT_VERSION:
        # Older file — load the frozen snapshot for that version
        id_to_token = get_id_to_token_for_version(dict_version)
        ascii_base  = get_ascii_base_for_version(dict_version)
        compat_note = (f" [backwards-compat: encoded with v{dict_version}, "
                       f"decoded via frozen snapshot]")
        print(f"[spec_dec] Backwards compatibility: using frozen v{dict_version} "
              f"token table ({len(id_to_token):,} tokens).")
    else:
        # Newer file than our dict — warn and try current dict
        import warnings
        warnings.warn(
            f"File was encoded with dict v{dict_version} but current dict is "
            f"v{D.DICT_VERSION}. Tokens added in v{dict_version} may fail to "
            f"decode. Upgrade Spectrum Algo to the latest version.",
            UserWarning,
        )
        id_to_token = D.SPEC_ID_TO_TOKEN
        ascii_base  = D.SPEC_ID_ASCII_BASE
        compat_note = f" [WARNING: encoded with newer v{dict_version}]"

    # Decompress body
    body = raw[HEADER_SIZE:]
    try:
        raw_stream = zlib.decompress(body)
    except zlib.error as e:
        raise SpecFormatError(f"zlib decompression failed: {e}")

    # Unpack uint32 LE stream (upgraded from uint16 in v7)
    count = len(raw_stream) // 4
    ids = list(struct.unpack(f"<{count}I", raw_stream[:count * 4]))

    # Decode to tokens (using version-appropriate ID table)
    tokens = ids_to_tokens(ids, id_to_token=id_to_token, ascii_base=ascii_base)

    # Reconstruct source — text files need the state-machine reconstructor
    # to interpret CTRL:* control tokens; all other languages just join.
    if meta["language_id"] in (LANGUAGE_TEXT, LANGUAGE_XML):
        source = reconstruct_text(tokens)
    else:
        source = "".join(tokens)

    # Truncate to original byte length
    source_bytes = source.encode("utf-8")
    if len(source_bytes) > orig_length:
        source = source_bytes[:orig_length].decode("utf-8", errors="replace")

    decoded_length = len(source.encode("utf-8"))

    # Verify checksum
    actual_cksum = sum(source.encode("utf-8")) & 0xFFFF
    cksum_ok = (actual_cksum == expected_cksum)

    # Write output
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(source, encoding="utf-8")

    length_ok = (decoded_length == orig_length)
    fidelity  = "✓ perfect" if (length_ok and cksum_ok) else "✗ mismatch"

    print(f"[spec_dec] Decoded {len(tokens):,} tokens → {decoded_length:,} bytes  "
          f"checksum {'✓' if cksum_ok else '✗'}  [{fidelity}]{compat_note}")
    print(f"[spec_dec] Saved → {output_path.name}")

    return {
        "spec_path":       str(spec_path),
        "output_path":     str(output_path),
        "dict_version":    dict_version,
        "orig_length":     orig_length,
        "decoded_length":  decoded_length,
        "token_count":     len(tokens),
        "length_ok":       length_ok,
        "checksum_ok":     cksum_ok,
        "fidelity":        fidelity,
    }


# ─────────────────────────────────────────────────────────────────────────────
# CLI
# ─────────────────────────────────────────────────────────────────────────────

def main():
    import argparse
    parser = argparse.ArgumentParser(
        description="Spectrum Algo .spec Decoder — binary → source")
    parser.add_argument("spec_file", help="Path to .spec file")
    parser.add_argument("--out", default=None,
                        help="Output file path (default: spec_format/output/<stem>_decoded.py)")
    args = parser.parse_args()

    spec = Path(args.spec_file)
    if not spec.exists():
        print(f"Error: {spec} not found", file=sys.stderr)
        sys.exit(1)

    if args.out:
        out = Path(args.out)
    else:
        out_dir = Path(__file__).resolve().parent / "output"
        out = out_dir / (spec.stem + "_decoded.py")

    result = decode_file(str(spec), str(out))
    if not (result["length_ok"] and result["checksum_ok"]):
        sys.exit(1)


if __name__ == "__main__":
    main()
