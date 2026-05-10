from __future__ import annotations

import contextlib
import io
from dataclasses import dataclass
from pathlib import Path

from . import _repo as _repo  # noqa: F401 - ensures repo modules are importable.
from .languages import LANGUAGE_NAMES, language_id
from spec_format.spec_decoder import decode_file as _decode_file
from spec_format.spec_decoder import parse_header
from spec_format.spec_encoder import RLE_MODE_OFF
from spec_format.spec_encoder import encode_file as _encode_file


@dataclass(frozen=True)
class EncodeResult:
    source_path: Path
    output_path: Path
    original_size: int
    spec_size: int
    token_count: int
    ratio: float
    dict_version: int | None = None
    rle_mode: str | None = None


@dataclass(frozen=True)
class DecodeResult:
    spec_path: Path
    output_path: Path
    dict_version: int
    original_length: int
    decoded_length: int
    token_count: int
    length_ok: bool
    checksum_ok: bool

    @property
    def ok(self) -> bool:
        return self.length_ok and self.checksum_ok


@dataclass(frozen=True)
class SpecInfo:
    path: Path
    bytes: int
    dict_version: int
    language_id: int
    language: str
    original_bytes: int
    checksum: int
    rle: bool
    ratio: float


def _quiet(enabled: bool):
    if enabled:
        return contextlib.nullcontext()
    return contextlib.redirect_stdout(io.StringIO())


def encode_file(
    source_path: str | Path,
    output_path: str | Path,
    *,
    language: str | int | None = None,
    rle: str = RLE_MODE_OFF,
    zlib_level: int = 9,
    verbose: bool = False,
) -> EncodeResult:
    """Encode one source file to `.spec`."""
    source = Path(source_path)
    output = Path(output_path)
    with _quiet(verbose):
        stats = _encode_file(
            str(source),
            str(output),
            use_rle=rle,
            language_id=language_id(language),
            zlib_level=zlib_level,
        )
    info = inspect_spec(output)
    return EncodeResult(
        source_path=source,
        output_path=output,
        original_size=int(stats["original_size"]),
        spec_size=int(stats["spec_size"]),
        token_count=int(stats["token_count"]),
        ratio=float(stats["ratio"]),
        dict_version=info.dict_version,
        rle_mode=str(stats.get("rle_mode", rle)),
    )


def decode_file(
    spec_path: str | Path,
    output_path: str | Path,
    *,
    verbose: bool = False,
) -> DecodeResult:
    """Decode one `.spec` file back to source text."""
    spec = Path(spec_path)
    output = Path(output_path)
    with _quiet(verbose):
        result = _decode_file(str(spec), str(output))
    return DecodeResult(
        spec_path=spec,
        output_path=output,
        dict_version=int(result["dict_version"]),
        original_length=int(result["orig_length"]),
        decoded_length=int(result["decoded_length"]),
        token_count=int(result["token_count"]),
        length_ok=bool(result["length_ok"]),
        checksum_ok=bool(result["checksum_ok"]),
    )


def inspect_spec(path: str | Path) -> SpecInfo:
    """Read `.spec` header metadata without decoding the body."""
    spec = Path(path)
    raw = spec.read_bytes()
    meta = parse_header(raw)
    original = int(meta["orig_length"])
    return SpecInfo(
        path=spec,
        bytes=len(raw),
        dict_version=int(meta["dict_version"]),
        language_id=int(meta["language_id"]),
        language=LANGUAGE_NAMES.get(int(meta["language_id"]), f"lang{meta['language_id']}"),
        original_bytes=original,
        checksum=int(meta["checksum"]),
        rle=bool(meta["rle_enabled"]),
        ratio=round(len(raw) / original, 4) if original else 0.0,
    )
