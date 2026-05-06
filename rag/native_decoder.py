"""
Optional native byte-prism decoder.

Python remains the reference implementation and owns dictionary/version table
selection. The native extension owns only the hot loop: inflate the uint32 ID
stream and expand IDs through packed UTF-8 token tables.
"""

from __future__ import annotations

import os
from array import array
from dataclasses import dataclass
from functools import lru_cache

import dictionary as D
from spec_format._frozen import get_ascii_base_for_version, get_id_to_token_for_version
from spec_format.extension_tokens import EXTENSION_ID_TO_LITERAL
from spec_format.spec_decoder import parse_header
from spec_format.spec_encoder import LANGUAGE_TEXT

try:  # pragma: no cover - depends on optional compiled extension
    import _spectrum_native
except Exception:  # pragma: no cover
    _spectrum_native = None


class NativeDecoderUnavailable(RuntimeError):
    pass


@dataclass(frozen=True)
class NativeDecodeTables:
    token_blob: bytes
    token_offsets: bytes
    token_lengths: bytes
    extension_ids: bytes
    extension_blob: bytes
    extension_offsets: bytes
    extension_lengths: bytes


def native_decoder_available() -> bool:
    return _spectrum_native is not None and os.environ.get("SPECTRUM_NATIVE_DECODER") != "0"


def _u32_bytes(values: list[int]) -> bytes:
    arr = array("I", values)
    if arr.itemsize != 4:
        raise RuntimeError("Expected native unsigned int arrays to be 4 bytes")
    return arr.tobytes()


def _id_to_token_for_version(dict_version: int) -> tuple[dict[int, str], int]:
    if dict_version == D.DICT_VERSION:
        return D.SPEC_ID_TO_TOKEN, D.SPEC_ID_ASCII_BASE
    return get_id_to_token_for_version(dict_version), get_ascii_base_for_version(dict_version)


@lru_cache(maxsize=8)
def _tables_for_version(dict_version: int) -> NativeDecodeTables:
    id_to_token, ascii_base = _id_to_token_for_version(dict_version)
    prism = {
        token_id: token.encode("utf-8")
        for token_id, token in id_to_token.items()
    }
    for offset in range(128):
        prism[ascii_base + offset] = bytes((offset,))

    max_token_id = max(prism) if prism else 0
    token_offsets = [0] * (max_token_id + 1)
    token_lengths = [0xFFFF_FFFF] * (max_token_id + 1)
    token_blob = bytearray()
    for token_id, piece in sorted(prism.items()):
        token_offsets[token_id] = len(token_blob)
        token_lengths[token_id] = len(piece)
        token_blob.extend(piece)

    extension_ids: list[int] = []
    extension_offsets: list[int] = []
    extension_lengths: list[int] = []
    extension_blob = bytearray()
    for token_id, literal in sorted(EXTENSION_ID_TO_LITERAL.items()):
        piece = literal.encode("utf-8")
        extension_ids.append(token_id)
        extension_offsets.append(len(extension_blob))
        extension_lengths.append(len(piece))
        extension_blob.extend(piece)

    return NativeDecodeTables(
        token_blob=bytes(token_blob),
        token_offsets=_u32_bytes(token_offsets),
        token_lengths=_u32_bytes(token_lengths),
        extension_ids=_u32_bytes(extension_ids),
        extension_blob=bytes(extension_blob),
        extension_offsets=_u32_bytes(extension_offsets),
        extension_lengths=_u32_bytes(extension_lengths),
    )


def decode_code_spec_bytes_fast_native(data: bytes) -> str:
    if not native_decoder_available():
        raise NativeDecoderUnavailable("Native Spectrum decoder extension is not installed")

    meta = parse_header(data)
    if meta["language_id"] == LANGUAGE_TEXT:
        raise NativeDecoderUnavailable("Native decoder only handles byte-literal code-like streams")

    tables = _tables_for_version(meta["dict_version"])
    return _spectrum_native.decode_code_spec_bytes_fast(
        data,
        tables.token_blob,
        tables.token_offsets,
        tables.token_lengths,
        tables.extension_ids,
        tables.extension_blob,
        tables.extension_offsets,
        tables.extension_lengths,
        D.SPEC_ID_RLE,
        D.SPEC_ID_UNICODE,
    )


def decode_code_spec_bytes_native_or_fast(data: bytes) -> str:
    from rag.codebase_benchmark import decode_code_spec_bytes_fast

    try:
        return decode_code_spec_bytes_fast_native(data)
    except NativeDecoderUnavailable:
        return decode_code_spec_bytes_fast(data)
