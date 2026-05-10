"""
Decode one page from a Spectrum Wikipedia page index.

This is the first decode-on-demand reader: it uses page_index.json to locate a
page span inside full-XML .spec shards, then reconstructs only that page.
"""

from __future__ import annotations

import argparse
import html
import json
import struct
import sys
import zlib
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import dictionary as D
from spec_format.extension_tokens import extension_id_to_literal
from spec_format.spec_decoder import HEADER_SIZE, parse_header
from tools.wiki_page_index import TextBuilder, normalize_title


class ReadError(Exception):
    pass


def load_index(path: Path) -> dict:
    if path.is_dir():
        path = path / "page_index.json"
    if not path.exists():
        raise FileNotFoundError(f"Page index not found: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def resolve_manifest_dir(index_path: Path, page_index: dict) -> Path:
    manifest_path = Path(page_index["source_manifest"])
    if not manifest_path.is_absolute():
        manifest_path = (Path.cwd() / manifest_path).resolve()
    return manifest_path.parent


def id_to_token(token_id: int, ascii_base: int) -> str:
    if ascii_base <= token_id < ascii_base + 128:
        return chr(token_id - ascii_base)
    literal = extension_id_to_literal(token_id)
    if literal is not None:
        return literal
    tok = D.SPEC_ID_TO_TOKEN.get(token_id)
    if tok is None:
        raise ReadError(f"unknown token ID {token_id}")
    return tok


def find_page(page_index: dict, page_id: int | None, title: str | None) -> dict:
    if page_id is not None:
        for page in page_index["pages"]:
            if page["id"] == page_id:
                return page
        raise ReadError(f"No page with id {page_id}")

    if title is None:
        raise ReadError("Provide either --id or --title")

    key = normalize_title(title)
    ids = page_index.get("title_index", {}).get(key)
    if not ids:
        raise ReadError(f"No page titled {title!r}")
    wanted = ids[0]
    for page in page_index["pages"]:
        if page["id"] == wanted:
            return page
    raise ReadError(f"Title index points to missing page id {wanted}")


def token_range_for_chunk(page: dict, chunk_index: int) -> tuple[int, int | None]:
    start = page["start"]
    end = page["end"]
    if end is None:
        raise ReadError(f"Page {page['id']} is incomplete in this index.")

    if chunk_index == start["chunk_index"] == end["chunk_index"]:
        return start["token"], end["token"]
    if chunk_index == start["chunk_index"]:
        return start["token"], None
    if chunk_index == end["chunk_index"]:
        return 0, end["token"]
    return 0, None


def append_token(builder: TextBuilder, token_id: int, token: str | None) -> None:
    if token is None:
        token = id_to_token(token_id, D.SPEC_ID_ASCII_BASE)
    builder.accept(token)


def decode_chunk_range(
    shard_path: Path,
    start_token: int,
    end_token: int | None,
    builder: TextBuilder,
) -> int:
    raw = shard_path.read_bytes()
    meta = parse_header(raw)
    if meta["dict_version"] != D.DICT_VERSION:
        raise ReadError(f"{shard_path}: expected dict v{D.DICT_VERSION}, got v{meta['dict_version']}")

    raw_stream = zlib.decompress(raw[HEADER_SIZE:])
    values = struct.iter_unpack("<I", raw_stream)
    token_pos = 0
    emitted = 0
    previous_id: int | None = None
    previous_token: str | None = None

    def in_range(pos: int) -> bool:
        if pos < start_token:
            return False
        if end_token is not None and pos > end_token:
            return False
        return True

    for (value,) in values:
        if end_token is not None and token_pos > end_token:
            break

        if value == D.SPEC_ID_RLE:
            try:
                (repeat,) = next(values)
            except StopIteration as exc:
                raise ReadError(f"{shard_path}: RLE marker at end of stream") from exc
            if previous_id is None:
                raise ReadError(f"{shard_path}: RLE marker before any token")
            for _ in range(repeat):
                if in_range(token_pos):
                    append_token(builder, previous_id, previous_token)
                    emitted += 1
                token_pos += 1
                if end_token is not None and token_pos > end_token:
                    break
            continue

        if value == D.SPEC_ID_UNICODE:
            try:
                (codepoint,) = next(values)
            except StopIteration as exc:
                raise ReadError(f"{shard_path}: Unicode marker at end of stream") from exc
            token = chr(codepoint)
            if in_range(token_pos):
                append_token(builder, value, token)
                emitted += 1
            previous_id = value
            previous_token = token
            token_pos += 1
            continue

        token = id_to_token(value, D.SPEC_ID_ASCII_BASE) if in_range(token_pos) else None
        if in_range(token_pos):
            append_token(builder, value, token)
            emitted += 1
        previous_id = value
        previous_token = token
        token_pos += 1

    return emitted


def extract_text_element(page_xml: str) -> str:
    start = page_xml.find("<text")
    if start < 0:
        return ""
    start_close = page_xml.find(">", start)
    if start_close < 0:
        return ""
    end = page_xml.find("</text>", start_close + 1)
    if end < 0:
        return ""
    return html.unescape(page_xml[start_close + 1:end])


def read_page(index_path: Path, page_id: int | None, title: str | None, text_only: bool) -> tuple[dict, str]:
    page_index = load_index(index_path)
    page = find_page(page_index, page_id, title)
    if page["end"] is None:
        raise ReadError(f"Page {page['id']} ({page['title']!r}) is incomplete in this index.")

    manifest_dir = resolve_manifest_dir(index_path, page_index)
    start_chunk = page["start"]["chunk_index"]
    end_chunk = page["end"]["chunk_index"]
    builder = TextBuilder()

    for chunk_index in range(start_chunk, end_chunk + 1):
        chunk_path = page["start"]["chunk_path"] if chunk_index == start_chunk else None
        if chunk_index == end_chunk:
            chunk_path = page["end"]["chunk_path"]
        if chunk_path is None:
            chunk_path = page_index["pages"][page["id"]]["start"]["chunk_path"].replace(
                f"{start_chunk:06d}", f"{chunk_index:06d}"
            )
        start_token, end_token = token_range_for_chunk(page, chunk_index)
        decode_chunk_range(manifest_dir / chunk_path, start_token, end_token, builder)

    page_xml = builder.text()
    return page, extract_text_element(page_xml) if text_only else page_xml


def main() -> int:
    parser = argparse.ArgumentParser(description="Decode one page from a Spectrum Wiki page index.")
    parser.add_argument("index", help="Path to page_index.json or its containing directory.")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--id", type=int, help="Page id in the generated page index.")
    group.add_argument("--title", help="Exact page title to read.")
    parser.add_argument("--text", action="store_true", help="Output raw MediaWiki text instead of page XML.")
    parser.add_argument("--out", default=None, help="Output path. Defaults to stdout.")
    args = parser.parse_args()

    page, output = read_page(Path(args.index), args.id, args.title, args.text)
    if args.out:
        out = Path(args.out)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(output, encoding="utf-8")
        print(f"[wiki-read] wrote {out} | page={page['id']} title={page['title']!r} bytes={len(output.encode('utf-8')):,}")
    else:
        print(output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
