"""
Build a page/title index for full-XML Spectrum Wikipedia shard sets.

The indexer scans decoded token IDs directly from .spec shards. It records
<page>...</page> spans and reconstructs only <title> text, so it can build a
browser/reader index without writing the decoded XML corpus to disk.
"""

from __future__ import annotations

import argparse
import json
import struct
import sys
import time
import unicodedata
import zlib
from dataclasses import dataclass, field
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import dictionary as D
from spec_format.extension_tokens import extension_id_to_literal
from spec_format.spec_decoder import HEADER_SIZE, parse_header


LANGUAGE_XML = 9

ID_PAGE_OPEN = D.TOKEN_TO_SPEC_ID["<page>"]
ID_PAGE_CLOSE = D.TOKEN_TO_SPEC_ID["</page>"]
ID_TITLE_OPEN = D.TOKEN_TO_SPEC_ID["<title>"]
ID_TITLE_CLOSE = D.TOKEN_TO_SPEC_ID["</title>"]
ID_TEXT_OPEN = D.TOKEN_TO_SPEC_ID["<text"]
ID_TEXT_CLOSE = D.TOKEN_TO_SPEC_ID["</text>"]


class IndexError(Exception):
    pass


@dataclass
class TextBuilder:
    """Small streaming text reconstructor for XML title content."""

    result: list[str] = field(default_factory=list)
    cap_mode: str | None = None
    in_spelled_word: bool = False
    spelling: list[str] = field(default_factory=list)

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
            self.result.append(self.apply_cap("".join(self.spelling)))
            self.cap_mode = None
            self.in_spelled_word = False
            self.spelling = []
            return
        if tok == "CTRL:NUM_SEP":
            return

        if self.in_spelled_word:
            self.spelling.append(tok)
            return

        self.result.append(self.apply_cap(tok))
        self.cap_mode = None

    def text(self) -> str:
        return "".join(self.result)


@dataclass
class OpenPage:
    page_id: int
    start_chunk: int
    start_path: str
    start_token: int
    title: str | None = None
    title_start_chunk: int | None = None
    title_start_token: int | None = None
    title_end_chunk: int | None = None
    title_end_token: int | None = None
    text_start_chunk: int | None = None
    text_start_token: int | None = None
    text_end_chunk: int | None = None
    text_end_token: int | None = None


@dataclass
class ScanState:
    next_page_id: int = 0
    pages: list[dict] = field(default_factory=list)
    open_page: OpenPage | None = None
    in_title: bool = False
    title_builder: TextBuilder | None = None
    total_tokens: int = 0
    title_count: int = 0
    text_count: int = 0
    malformed_events: list[str] = field(default_factory=list)


def normalize_title(title: str) -> str:
    return " ".join(title.replace("_", " ").casefold().split())


def load_manifest(path: Path) -> tuple[Path, dict]:
    manifest_path = path / "manifest.json" if path.is_dir() else path
    if not manifest_path.exists():
        raise FileNotFoundError(f"Manifest not found: {manifest_path}")
    return manifest_path, json.loads(manifest_path.read_text(encoding="utf-8"))


def id_to_token(token_id: int, ascii_base: int) -> str:
    if ascii_base <= token_id < ascii_base + 128:
        return chr(token_id - ascii_base)
    if token_id == D.SPEC_ID_UNICODE:
        raise IndexError("Unicode marker cannot be resolved without its codepoint")
    literal = extension_id_to_literal(token_id)
    if literal is not None:
        return literal
    tok = D.SPEC_ID_TO_TOKEN.get(token_id)
    if tok is None:
        raise IndexError(f"unknown token ID {token_id}")
    return tok


def finalize_page(state: ScanState, chunk_index: int, chunk_path: str, token_pos: int) -> None:
    page = state.open_page
    if page is None:
        state.malformed_events.append(f"{chunk_path}:{token_pos}: </page> without <page>")
        return

    title = page.title or ""
    state.pages.append({
        "id": page.page_id,
        "title": title,
        "title_normalized": normalize_title(title),
        "start": {
            "chunk_index": page.start_chunk,
            "chunk_path": page.start_path,
            "token": page.start_token,
        },
        "end": {
            "chunk_index": chunk_index,
            "chunk_path": chunk_path,
            "token": token_pos,
        },
        "title_span": {
            "start_chunk_index": page.title_start_chunk,
            "start_token": page.title_start_token,
            "end_chunk_index": page.title_end_chunk,
            "end_token": page.title_end_token,
        },
        "text_span": {
            "start_chunk_index": page.text_start_chunk,
            "start_token": page.text_start_token,
            "end_chunk_index": page.text_end_chunk,
            "end_token": page.text_end_token,
        },
        "spans_chunks": page.start_chunk != chunk_index,
    })
    state.open_page = None


def handle_token(
    state: ScanState,
    token_id: int,
    token: str | None,
    chunk_index: int,
    chunk_path: str,
    token_pos: int,
) -> None:
    if token_id == ID_PAGE_OPEN:
        if state.open_page is not None:
            state.malformed_events.append(f"{chunk_path}:{token_pos}: nested <page>")
        state.open_page = OpenPage(
            page_id=state.next_page_id,
            start_chunk=chunk_index,
            start_path=chunk_path,
            start_token=token_pos,
        )
        state.next_page_id += 1
        return

    if token_id == ID_PAGE_CLOSE:
        finalize_page(state, chunk_index, chunk_path, token_pos)
        return

    page = state.open_page
    if page is None:
        return

    if token_id == ID_TITLE_OPEN:
        state.in_title = True
        state.title_builder = TextBuilder()
        page.title_start_chunk = chunk_index
        page.title_start_token = token_pos
        return

    if token_id == ID_TITLE_CLOSE:
        if state.in_title and state.title_builder is not None:
            page.title = state.title_builder.text()
            page.title_end_chunk = chunk_index
            page.title_end_token = token_pos
            state.title_count += 1
        state.in_title = False
        state.title_builder = None
        return

    if token_id == ID_TEXT_OPEN:
        page.text_start_chunk = chunk_index
        page.text_start_token = token_pos
        return

    if token_id == ID_TEXT_CLOSE:
        page.text_end_chunk = chunk_index
        page.text_end_token = token_pos
        state.text_count += 1
        return

    if state.in_title and state.title_builder is not None:
        if token is None:
            token = id_to_token(token_id, D.SPEC_ID_ASCII_BASE)
        state.title_builder.accept(token)


def scan_chunk(manifest_dir: Path, chunk: dict, chunk_index: int, state: ScanState) -> int:
    rel_path = chunk["path"]
    shard_path = manifest_dir / rel_path
    raw = shard_path.read_bytes()
    meta = parse_header(raw)
    if meta["dict_version"] != D.DICT_VERSION:
        raise IndexError(f"{rel_path}: expected dict v{D.DICT_VERSION}, got v{meta['dict_version']}")
    if meta["language_id"] != LANGUAGE_XML:
        raise IndexError(f"{rel_path}: expected language {LANGUAGE_XML}, got {meta['language_id']}")

    raw_stream = zlib.decompress(raw[HEADER_SIZE:])
    if len(raw_stream) % 4:
        raise IndexError(f"{rel_path}: raw stream length is not divisible by 4")

    values = struct.iter_unpack("<I", raw_stream)
    token_pos = 0
    previous_id: int | None = None
    previous_token: str | None = None

    for (value,) in values:
        if value == D.SPEC_ID_RLE:
            try:
                (repeat,) = next(values)
            except StopIteration as exc:
                raise IndexError(f"{rel_path}: RLE marker at end of stream") from exc
            if previous_id is None:
                raise IndexError(f"{rel_path}: RLE marker before any token")
            for _ in range(repeat):
                handle_token(state, previous_id, previous_token, chunk_index, rel_path, token_pos)
                token_pos += 1
            continue

        if value == D.SPEC_ID_UNICODE:
            try:
                (codepoint,) = next(values)
            except StopIteration as exc:
                raise IndexError(f"{rel_path}: Unicode marker at end of stream") from exc
            token = chr(codepoint)
            handle_token(state, value, token, chunk_index, rel_path, token_pos)
            previous_id = value
            previous_token = token
            token_pos += 1
            continue

        token: str | None = None
        if state.in_title:
            token = id_to_token(value, D.SPEC_ID_ASCII_BASE)
        handle_token(state, value, token, chunk_index, rel_path, token_pos)
        previous_id = value
        previous_token = token
        token_pos += 1

    state.total_tokens += token_pos
    return token_pos


def build_index(manifest_path: Path, output_path: Path, limit: int | None = None) -> dict:
    manifest_path, manifest = load_manifest(manifest_path)
    manifest_dir = manifest_path.parent
    chunks = manifest.get("chunks", [])
    if limit is not None:
        chunks = chunks[:limit]
    if manifest.get("mode") != "full-xml":
        raise IndexError("Only full-xml manifests are supported.")
    if manifest.get("dict_version") != D.DICT_VERSION:
        raise IndexError(f"Expected manifest dict v{D.DICT_VERSION}, got {manifest.get('dict_version')}")

    state = ScanState()
    started = time.perf_counter()
    print(f"[wiki-index] {manifest_path} | chunks={len(chunks):,}")

    for chunk_index, chunk in enumerate(chunks):
        chunk_started = time.perf_counter()
        token_count = scan_chunk(manifest_dir, chunk, chunk_index, state)
        elapsed = time.perf_counter() - chunk_started
        print(
            f"[wiki-index] scanned {chunk['path']:<28} "
            f"tokens={token_count:>10,} pages={len(state.pages):>8,} {elapsed:>6.2f}s"
        )

    if state.open_page is not None:
        page = state.open_page
        state.pages.append({
            "id": page.page_id,
            "title": page.title or "",
            "title_normalized": normalize_title(page.title or ""),
            "start": {
                "chunk_index": page.start_chunk,
                "chunk_path": page.start_path,
                "token": page.start_token,
            },
            "end": None,
            "title_span": {
                "start_chunk_index": page.title_start_chunk,
                "start_token": page.title_start_token,
                "end_chunk_index": page.title_end_chunk,
                "end_token": page.title_end_token,
            },
            "text_span": {
                "start_chunk_index": page.text_start_chunk,
                "start_token": page.text_start_token,
                "end_chunk_index": page.text_end_chunk,
                "end_token": page.text_end_token,
            },
            "spans_chunks": True,
            "complete": False,
        })

    title_index: dict[str, list[int]] = {}
    for page in state.pages:
        key = page["title_normalized"]
        if key:
            title_index.setdefault(key, []).append(page["id"])

    elapsed = time.perf_counter() - started
    result = {
        "format": "spectrum-wikipedia-page-index-v1",
        "source_manifest": str(manifest_path),
        "project": manifest.get("project"),
        "mode": manifest.get("mode"),
        "dict_version": manifest.get("dict_version"),
        "chunks_indexed": len(chunks),
        "stats": {
            "pages": len(state.pages),
            "titles": state.title_count,
            "text_spans": state.text_count,
            "tokens_scanned": state.total_tokens,
            "malformed_events": len(state.malformed_events),
            "elapsed_seconds": round(elapsed, 3),
        },
        "malformed_events": state.malformed_events[:100],
        "title_index": title_index,
        "pages": state.pages,
    }

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(
        f"[wiki-index] wrote {output_path} | pages={len(state.pages):,} "
        f"titles={state.title_count:,} tokens={state.total_tokens:,} {elapsed:.2f}s"
    )
    return result


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Build a page/title index for Spectrum full-XML Wikipedia shards."
    )
    parser.add_argument("manifest", help="Path to manifest.json or a directory containing it.")
    parser.add_argument(
        "--out",
        default=None,
        help="Output JSON path. Default: <manifest-dir>/page_index.json",
    )
    parser.add_argument("--limit", type=int, default=None, help="Index only first N chunks.")
    args = parser.parse_args()

    manifest_path = Path(args.manifest)
    default_out_dir = manifest_path if manifest_path.is_dir() else manifest_path.parent
    output_path = Path(args.out) if args.out else default_out_dir / "page_index.json"
    build_index(manifest_path, output_path, limit=args.limit)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
