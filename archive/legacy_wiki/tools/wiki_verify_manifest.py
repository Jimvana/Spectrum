"""
Verify Spectrum Wikipedia shard manifests.

This checks the manifest metadata and each referenced .spec shard without
writing decoded XML to disk. In full verification mode it reconstructs the
decoded byte stream in memory piece-by-piece only to verify the .spec header
length/checksum.
"""

from __future__ import annotations

import argparse
import os
import json
import struct
import sys
import time
import unicodedata
import zlib
from concurrent.futures import ProcessPoolExecutor, as_completed
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import dictionary as D
from spec_format.extension_tokens import extension_id_to_literal
from spec_format.spec_decoder import HEADER_SIZE, MAGIC, parse_header
from spec_format._frozen import get_ascii_base_for_version, get_id_to_token_for_version


EXPECTED_FORMAT = "spectrum-wikipedia-shards-v1"
EXPECTED_MODE = "full-xml"
EXPECTED_DICT_VERSION = 10
EXPECTED_LANGUAGE_ID = 9


class VerificationError(Exception):
    pass


@dataclass
class TextChecksumReconstructor:
    """Streaming equivalent of tokenizers.text_tokenizer.reconstruct_text()."""

    byte_length: int = 0
    checksum: int = 0
    cap_mode: str | None = None
    in_spelled_word: bool = False
    spelling: list[str] = field(default_factory=list)

    def emit(self, text: str) -> None:
        data = text.encode("utf-8")
        self.byte_length += len(data)
        self.checksum = (self.checksum + sum(data)) & 0xFFFF

    def apply_cap(self, word: str) -> str:
        if not word or self.cap_mode is None:
            return word
        if self.cap_mode == "first":
            return unicodedata.normalize("NFC", word[0].upper() + word[1:])
        if self.cap_mode == "all":
            return unicodedata.normalize("NFC", word.upper())
        return word

    def accept(self, tok: str) -> None:
        if tok == "CTRL:CAP_FIRST":
            self.cap_mode = "first"
            return
        if tok == "CTRL:CAP_ALL":
            self.cap_mode = "all"
            return
        if tok == "CTRL:BEGIN_WORD":
            self.in_spelled_word = True
            self.spelling = []
            return
        if tok == "CTRL:END_WORD":
            self.emit(self.apply_cap("".join(self.spelling)))
            self.cap_mode = None
            self.in_spelled_word = False
            self.spelling = []
            return
        if tok == "CTRL:NUM_SEP":
            return

        if self.in_spelled_word:
            self.spelling.append(tok)
            return

        self.emit(self.apply_cap(tok))
        self.cap_mode = None

    def finish(self) -> None:
        if self.in_spelled_word:
            raise VerificationError("Token stream ended inside CTRL:BEGIN_WORD.")


@dataclass
class StreamStats:
    encoded_id_count: int = 0
    raw_id_count: int = 0
    token_count: int = 0
    dictionary_tokens: int = 0
    ascii_fallbacks: int = 0
    unicode_fallbacks: int = 0
    extension_tokens: int = 0
    rle_runs: int = 0
    rle_repeated_ids: int = 0
    decoded_length: int | None = None
    decoded_checksum: int | None = None


def load_manifest(path: Path) -> dict:
    if path.is_dir():
        path = path / "manifest.json"
    if not path.exists():
        raise FileNotFoundError(f"Manifest not found: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def validate_manifest(manifest: dict, manifest_path: Path) -> list[str]:
    errors: list[str] = []
    if manifest.get("format") != EXPECTED_FORMAT:
        errors.append(
            f"manifest format is {manifest.get('format')!r}, expected {EXPECTED_FORMAT!r}"
        )
    if manifest.get("status") != "complete":
        errors.append(f"manifest status is {manifest.get('status')!r}, expected 'complete'")
    if manifest.get("mode") != EXPECTED_MODE:
        errors.append(f"manifest mode is {manifest.get('mode')!r}, expected {EXPECTED_MODE!r}")
    if manifest.get("dict_version") != EXPECTED_DICT_VERSION:
        errors.append(
            f"manifest dict_version is {manifest.get('dict_version')!r}, "
            f"expected {EXPECTED_DICT_VERSION}"
        )
    if not manifest.get("chunks"):
        errors.append("manifest has no chunks")

    required = {(lib.get("name"), lib.get("version")) for lib in manifest.get("libraries", [])}
    for required_library in (
        ("spectrum-core", EXPECTED_DICT_VERSION),
        ("english-text", 1),
        ("wikimedia-xml", 1),
    ):
        if required_library not in required:
            errors.append(f"missing library declaration {required_library[0]}@{required_library[1]}")

    if not manifest_path.exists():
        errors.append(f"manifest path does not exist: {manifest_path}")
    return errors


def id_to_token(token_id: int, id_table: dict[int, str], ascii_base: int) -> tuple[str, str]:
    if ascii_base <= token_id < ascii_base + 128:
        return chr(token_id - ascii_base), "ascii"

    literal = extension_id_to_literal(token_id)
    if literal is not None:
        return literal, "extension"

    tok = id_table.get(token_id)
    if tok is not None:
        return tok, "dictionary"

    raise VerificationError(f"unknown token ID {token_id}")


def iter_uint32(raw_stream: bytes) -> Iterable[int]:
    if len(raw_stream) % 4 != 0:
        raise VerificationError(
            f"decompressed stream length {len(raw_stream):,} is not divisible by 4"
        )
    for (value,) in struct.iter_unpack("<I", raw_stream):
        yield value


def scan_stream(raw_stream: bytes, meta: dict, verify_checksum: bool) -> StreamStats:
    stats = StreamStats(encoded_id_count=len(raw_stream) // 4)
    dict_version = meta["dict_version"]
    if dict_version == D.DICT_VERSION:
        id_table = D.SPEC_ID_TO_TOKEN
        ascii_base = D.SPEC_ID_ASCII_BASE
    else:
        id_table = get_id_to_token_for_version(dict_version)
        ascii_base = get_ascii_base_for_version(dict_version)

    reconstructor = TextChecksumReconstructor() if verify_checksum else None
    previous_token: str | None = None
    previous_kind: str | None = None
    values = iter_uint32(raw_stream)

    for val in values:
        if val == D.SPEC_ID_RLE:
            try:
                repeat = next(values)
            except StopIteration as exc:
                raise VerificationError("RLE marker at end of stream") from exc
            stats.rle_runs += 1
            stats.encoded_id_count = len(raw_stream) // 4
            stats.raw_id_count += repeat
            stats.token_count += repeat
            stats.rle_repeated_ids += repeat
            if previous_token is None:
                raise VerificationError("RLE marker appeared before any token")
            if previous_kind == "dictionary":
                stats.dictionary_tokens += repeat
            elif previous_kind == "ascii":
                stats.ascii_fallbacks += repeat
            elif previous_kind == "extension":
                stats.extension_tokens += repeat
            elif previous_kind == "unicode":
                stats.unicode_fallbacks += repeat
            if reconstructor is not None:
                for _ in range(repeat):
                    reconstructor.accept(previous_token)
            continue

        if val == D.SPEC_ID_UNICODE:
            try:
                codepoint = next(values)
            except StopIteration as exc:
                raise VerificationError("Unicode marker at end of stream") from exc
            try:
                tok = chr(codepoint)
            except ValueError as exc:
                raise VerificationError(f"invalid Unicode codepoint {codepoint}") from exc
            stats.raw_id_count += 2
            stats.token_count += 1
            stats.unicode_fallbacks += 1
            previous_token = tok
            previous_kind = "unicode"
            if reconstructor is not None:
                reconstructor.accept(tok)
            continue

        if verify_checksum:
            tok, kind = id_to_token(val, id_table, ascii_base)
        elif ascii_base <= val < ascii_base + 128:
            tok, kind = "", "ascii"
        elif extension_id_to_literal(val) is not None:
            tok, kind = "", "extension"
        elif val in id_table:
            tok, kind = "", "dictionary"
        else:
            raise VerificationError(f"unknown token ID {val}")

        stats.raw_id_count += 1
        stats.token_count += 1
        if kind == "dictionary":
            stats.dictionary_tokens += 1
        elif kind == "ascii":
            stats.ascii_fallbacks += 1
        elif kind == "extension":
            stats.extension_tokens += 1
        previous_token = tok
        previous_kind = kind
        if reconstructor is not None:
            reconstructor.accept(tok)

    if reconstructor is not None:
        reconstructor.finish()
        stats.decoded_length = reconstructor.byte_length
        stats.decoded_checksum = reconstructor.checksum

    return stats


def verify_chunk(
    manifest_dir: Path,
    chunk: dict,
    index: int,
    verify_checksum: bool,
) -> tuple[list[str], StreamStats | None]:
    errors: list[str] = []
    rel_path = chunk.get("path")
    if not rel_path:
        return [f"chunk {index}: missing path"], None

    shard_path = manifest_dir / rel_path
    if not shard_path.exists():
        return [f"{rel_path}: file not found"], None

    raw = shard_path.read_bytes()
    if chunk.get("spec_size") is not None and len(raw) != chunk["spec_size"]:
        errors.append(f"{rel_path}: spec_size {len(raw):,} != manifest {chunk['spec_size']:,}")

    try:
        meta = parse_header(raw)
    except Exception as exc:
        return [f"{rel_path}: bad header: {exc}"], None

    if meta["dict_version"] != EXPECTED_DICT_VERSION:
        errors.append(
            f"{rel_path}: dict_version {meta['dict_version']} != {EXPECTED_DICT_VERSION}"
        )
    if meta["language_id"] != EXPECTED_LANGUAGE_ID:
        errors.append(
            f"{rel_path}: language_id {meta['language_id']} != {EXPECTED_LANGUAGE_ID}"
        )
    if chunk.get("original_size") is not None and meta["orig_length"] != chunk["original_size"]:
        errors.append(
            f"{rel_path}: original_size {meta['orig_length']:,} != "
            f"manifest {chunk['original_size']:,}"
        )
    if raw[:4] != MAGIC or len(raw) < HEADER_SIZE:
        errors.append(f"{rel_path}: invalid .spec wrapper")

    try:
        raw_stream = zlib.decompress(raw[HEADER_SIZE:])
    except zlib.error as exc:
        return errors + [f"{rel_path}: zlib decompression failed: {exc}"], None

    if chunk.get("raw_stream_bytes") is not None and len(raw_stream) != chunk["raw_stream_bytes"]:
        errors.append(
            f"{rel_path}: raw_stream_bytes {len(raw_stream):,} != "
            f"manifest {chunk['raw_stream_bytes']:,}"
        )

    try:
        stats = scan_stream(raw_stream, meta, verify_checksum=verify_checksum)
    except Exception as exc:
        return errors + [f"{rel_path}: token stream invalid: {exc}"], None

    for key, actual in (
        ("encoded_id_count", stats.encoded_id_count),
        ("raw_id_count", stats.raw_id_count),
        ("token_count", stats.token_count),
    ):
        expected = chunk.get(key)
        if expected is not None and actual != expected:
            errors.append(f"{rel_path}: {key} {actual:,} != manifest {expected:,}")

    if verify_checksum:
        if stats.decoded_length != meta["orig_length"]:
            errors.append(
                f"{rel_path}: decoded length {stats.decoded_length:,} != "
                f"header {meta['orig_length']:,}"
            )
        if stats.decoded_checksum != meta["checksum"]:
            errors.append(
                f"{rel_path}: checksum {stats.decoded_checksum:#06x} != "
                f"header {meta['checksum']:#06x}"
            )

    return errors, stats


def verify_chunk_worker(args: tuple[str, dict, int, bool]) -> dict:
    manifest_dir, chunk, index, verify_checksum = args
    started = time.perf_counter()
    rel_path = chunk.get("path", f"chunk-{index}")
    errors, stats = verify_chunk(Path(manifest_dir), chunk, index, verify_checksum)
    elapsed = time.perf_counter() - started
    return {
        "index": index,
        "path": rel_path,
        "errors": errors,
        "stats": stats,
        "elapsed": elapsed,
        "original_size": int(chunk.get("original_size") or 0),
        "spec_size": int(chunk.get("spec_size") or 0),
    }


def default_worker_count(chunk_count: int) -> int:
    cpu_count = os.cpu_count() or 1
    return max(1, min(4, cpu_count, chunk_count))


def print_chunk_result(result: dict) -> None:
    stats = result["stats"]
    rel_path = result["path"]
    if stats is None:
        print(f"[wiki-verify] FAIL {rel_path}")
        return

    print(
        f"[wiki-verify] ok {rel_path:<28} "
        f"orig={result['original_size']:>10,} "
        f"spec={result['spec_size']:>10,} "
        f"tokens={stats.token_count:>10,} "
        f"rle={stats.rle_runs:>6,} "
        f"{result['elapsed']:>6.2f}s"
    )


def verify_manifest(
    manifest_path: Path,
    verify_checksum: bool,
    limit: int | None = None,
    workers: int | None = None,
) -> int:
    manifest_path = manifest_path / "manifest.json" if manifest_path.is_dir() else manifest_path
    manifest = load_manifest(manifest_path)
    manifest_dir = manifest_path.parent
    errors = validate_manifest(manifest, manifest_path)

    chunks = manifest.get("chunks", [])
    if limit is not None:
        chunks = chunks[:limit]
    worker_count = workers if workers is not None else default_worker_count(len(chunks))
    worker_count = max(1, min(worker_count, len(chunks) or 1))

    total_original = 0
    total_spec = 0
    total_tokens = 0
    started = time.perf_counter()

    print(
        f"[wiki-verify] {manifest_path} | chunks={len(chunks):,} | "
        f"checksum={'on' if verify_checksum else 'off'} | workers={worker_count}"
    )

    jobs = [
        (str(manifest_dir.resolve()), chunk, index, verify_checksum)
        for index, chunk in enumerate(chunks)
    ]

    results: list[dict] = []
    if worker_count == 1:
        for job in jobs:
            result = verify_chunk_worker(job)
            results.append(result)
            print_chunk_result(result)
    else:
        with ProcessPoolExecutor(max_workers=worker_count) as executor:
            futures = [executor.submit(verify_chunk_worker, job) for job in jobs]
            for future in as_completed(futures):
                result = future.result()
                results.append(result)
                print_chunk_result(result)

    for result in sorted(results, key=lambda item: item["index"]):
        chunk_errors = result["errors"]
        stats = result["stats"]
        errors.extend(chunk_errors)
        if stats is not None:
            total_original += result["original_size"]
            total_spec += result["spec_size"]
            total_tokens += stats.token_count

    if manifest.get("text_bytes") is not None and limit is None and total_original:
        if total_original != manifest["text_bytes"]:
            errors.append(
                f"manifest text_bytes {manifest['text_bytes']:,} != "
                f"sum of chunks {total_original:,}"
            )
    if manifest.get("spec_bytes") is not None and limit is None and total_spec:
        if total_spec != manifest["spec_bytes"]:
            errors.append(
                f"manifest spec_bytes {manifest['spec_bytes']:,} != "
                f"sum of chunks {total_spec:,}"
            )

    elapsed = time.perf_counter() - started
    print(
        f"[wiki-verify] scanned {len(chunks):,} chunks, "
        f"{total_original:,} original bytes, {total_spec:,} spec bytes, "
        f"{total_tokens:,} decoded tokens in {elapsed:.2f}s"
    )

    if errors:
        print("[wiki-verify] FAILED")
        for error in errors:
            print(f"  - {error}")
        return 1

    print("[wiki-verify] PASS")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Verify a Spectrum Wikipedia full-XML shard manifest."
    )
    parser.add_argument(
        "manifest",
        help="Path to manifest.json or a directory containing manifest.json.",
    )
    parser.add_argument(
        "--structure-only",
        action="store_true",
        help="Skip decoded byte length/checksum verification.",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Verify only the first N chunks.",
    )
    parser.add_argument(
        "--workers",
        type=int,
        default=None,
        help="Number of parallel shard workers. Default: min(4, CPU count, chunks).",
    )
    args = parser.parse_args()

    return verify_manifest(
        Path(args.manifest),
        verify_checksum=not args.structure_only,
        limit=args.limit,
        workers=args.workers,
    )


if __name__ == "__main__":
    raise SystemExit(main())
