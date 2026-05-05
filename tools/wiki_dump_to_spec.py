"""
Stream a Wikimedia pages-articles dump into Spectrum .spec chunks.

The full English Wikipedia dump is too large for the current single-file
.spec header because original_length is uint32. This script keeps each output
chunk below a configurable text size and writes a manifest describing the
portable shard set.
"""

from __future__ import annotations

import argparse
import bz2
import json
import re
import struct
import sys
import time
import urllib.request
import xml.etree.ElementTree as ET
import zlib
from pathlib import Path
from typing import BinaryIO, Iterable

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import dictionary as D
from spec_format.libraries import (
    planned_wikipedia_lossless_libraries,
    wikipedia_libraries,
)
from spec_format.spec_encoder import (
    FLAG_RLE,
    LANGUAGE_TEXT,
    LANGUAGE_XML,
    apply_rle_ids,
    build_header,
    token_to_spec_id,
)
from tokenizers.text_tokenizer import tokenize_text
from tokenizers.wiki_tokenizer import tokenize_wiki_source


DEFAULT_CHUNK_BYTES = 64 * 1024 * 1024
DEFAULT_USER_AGENT = "SpectrumAlgo/0.1 (offline research; Wikimedia dump reader)"


def latest_dump_url(project: str) -> str:
    return (
        f"https://dumps.wikimedia.org/{project}/latest/"
        f"{project}-latest-pages-articles-multistream.xml.bz2"
    )


def download(url: str, output_path: Path, overwrite: bool = False) -> Path:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    if output_path.exists() and not overwrite:
        print(f"[wiki-spec] using existing {output_path}")
        return output_path

    tmp_path = output_path.with_suffix(output_path.suffix + ".part")
    request = urllib.request.Request(url, headers={"User-Agent": DEFAULT_USER_AGENT})
    print(f"[wiki-spec] downloading {url}")
    with urllib.request.urlopen(request) as response, tmp_path.open("wb") as out:
        total_header = response.headers.get("Content-Length")
        total = int(total_header) if total_header else 0
        copied = 0
        last_report = time.monotonic()
        while True:
            block = response.read(1024 * 1024)
            if not block:
                break
            out.write(block)
            copied += len(block)
            now = time.monotonic()
            if now - last_report >= 10:
                if total:
                    pct = copied * 100 / total
                    print(f"[wiki-spec] downloaded {copied:,}/{total:,} bytes ({pct:.1f}%)")
                else:
                    print(f"[wiki-spec] downloaded {copied:,} bytes")
                last_report = now

    tmp_path.replace(output_path)
    print(f"[wiki-spec] saved {output_path} ({output_path.stat().st_size:,} bytes)")
    return output_path


def local_name(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def child_text(elem: ET.Element, name: str) -> str:
    for child in elem:
        if local_name(child.tag) == name:
            return child.text or ""
    return ""


def revision_text(page: ET.Element) -> str:
    for child in page:
        if local_name(child.tag) != "revision":
            continue
        for rev_child in child:
            if local_name(rev_child.tag) == "text":
                return rev_child.text or ""
    return ""


def has_redirect(page: ET.Element) -> bool:
    return any(local_name(child.tag) == "redirect" for child in page)


def iter_articles(stream: BinaryIO, include_redirects: bool = False) -> Iterable[tuple[str, str]]:
    context = ET.iterparse(stream, events=("start", "end"))
    _, root = next(context)

    for event, elem in context:
        if event != "end" or local_name(elem.tag) != "page":
            continue

        namespace = child_text(elem, "ns")
        if namespace == "0" and (include_redirects or not has_redirect(elem)):
            title = child_text(elem, "title")
            text = revision_text(elem)
            if text:
                yield title, text

        root.clear()


COMMENT_RE = re.compile(r"<!--.*?-->", re.S)
REF_RE = re.compile(r"<ref\b[^>/]*?>.*?</ref>|<ref\b[^/]*?/>", re.I | re.S)
TAG_RE = re.compile(r"</?[a-zA-Z][^>]*>")
TEMPLATE_RE = re.compile(r"\{\{[^{}]*\}\}", re.S)
TABLE_RE = re.compile(r"\{\|.*?\|\}", re.S)
FILE_LINK_RE = re.compile(
    r"\[\[(?:File|Image|Media):[^\]]*\]\]",
    re.I,
)
INTERNAL_LINK_RE = re.compile(r"\[\[([^\]|#]+)(?:#[^\]|]*)?(?:\|([^\]]+))?\]\]")
EXTERNAL_LINK_RE = re.compile(r"\[(?:https?|ftp)://[^\s\]]+(?:\s+([^\]]+))?\]")


def clean_wikitext(text: str) -> str:
    """Cheap MediaWiki markup cleanup for compression experiments."""
    text = COMMENT_RE.sub("", text)
    text = REF_RE.sub("", text)
    text = TABLE_RE.sub("", text)
    text = FILE_LINK_RE.sub("", text)

    previous = None
    while previous != text:
        previous = text
        text = TEMPLATE_RE.sub("", text)

    text = INTERNAL_LINK_RE.sub(lambda m: m.group(2) or m.group(1), text)
    text = EXTERNAL_LINK_RE.sub(lambda m: m.group(1) or "", text)
    text = TAG_RE.sub("", text)
    text = text.replace("'''", "").replace("''", "")
    text = re.sub(r"^=+\s*(.*?)\s*=+\s*$", r"\1", text, flags=re.M)
    text = re.sub(r"^[*#:;]+\s*", "", text, flags=re.M)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def article_record(title: str, text: str, mode: str) -> str:
    body = clean_wikitext(text) if mode == "clean-text" else text.strip()
    if not body:
        return ""
    return f"# {title}\n\n{body}\n\n"


def encode_text_to_spec_bytes(
    source: str,
    zlib_level: int = 9,
    use_rle: bool = True,
    mode: str = "clean-text",
) -> dict:
    source_bytes = source.encode("utf-8")
    tokens = tokenize_wiki_source(source) if mode in ("raw-wikitext", "full-xml") else tokenize_text(source)

    ids: list[int] = []
    for token in tokens:
        ids.extend(token_to_spec_id(token))

    raw_id_count = len(ids)
    flags = 0
    if use_rle:
        ids = apply_rle_ids(ids)
        flags |= FLAG_RLE

    raw_stream = struct.pack(f"<{len(ids)}I", *ids)
    compressed = zlib.compress(raw_stream, level=zlib_level)
    language_id = LANGUAGE_XML if mode == "full-xml" else LANGUAGE_TEXT
    header = build_header(
        D.DICT_VERSION,
        len(source_bytes),
        sum(source_bytes) & 0xFFFF,
        flags,
        language_id,
    )

    return {
        "bytes": header + compressed,
        "original_size": len(source_bytes),
        "token_count": len(tokens),
        "raw_id_count": raw_id_count,
        "encoded_id_count": len(ids),
        "raw_stream_bytes": len(raw_stream),
        "compressed_bytes": len(compressed),
    }


def write_chunk(
    text_parts: list[str],
    output_dir: Path,
    chunk_index: int,
    zlib_level: int,
    use_rle: bool,
    article_count: int,
    resume_existing: bool,
    mode: str,
) -> dict:
    text = "".join(text_parts)
    out_path = output_dir / "chunks" / f"wiki_{chunk_index:06d}.spec"

    if resume_existing and out_path.exists():
        source_bytes = text.encode("utf-8")
        stats = {
            "original_size": len(source_bytes),
            "token_count": None,
            "raw_id_count": None,
            "encoded_id_count": None,
            "raw_stream_bytes": None,
            "compressed_bytes": None,
            "resumed": True,
        }
    else:
        stats = encode_text_to_spec_bytes(
            text,
            zlib_level=zlib_level,
            use_rle=use_rle,
            mode=mode,
        )
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_bytes(stats.pop("bytes"))
        stats["resumed"] = False

    stats["path"] = str(out_path.relative_to(output_dir))
    stats["spec_size"] = out_path.stat().st_size
    stats["ratio"] = round(stats["spec_size"] / max(stats["original_size"], 1), 6)
    stats["article_count"] = article_count
    print(
        f"[wiki-spec] chunk {chunk_index:06d}"
        f"{' resumed' if stats['resumed'] else ''}: "
        f"{stats['original_size']:,} text bytes -> {stats['spec_size']:,} spec bytes "
        f"({stats['ratio']:.4f}x)"
    )
    return stats


def write_manifest(output_dir: Path, manifest: dict, partial: bool) -> None:
    name = "manifest.partial.json" if partial else "manifest.json"
    path = output_dir / name
    path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")


def encode_dump(args: argparse.Namespace) -> dict:
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    if args.input:
        dump_path = Path(args.input)
    else:
        dump_path = output_dir / "downloads" / f"{args.project}-latest-pages-articles-multistream.xml.bz2"
        download(latest_dump_url(args.project), dump_path, overwrite=args.force_download)

    if args.download_only:
        return {"dump_path": str(dump_path), "download_only": True}

    if args.mode == "full-xml":
        return encode_full_xml_dump(args, dump_path, output_dir)

    chunks: list[dict] = []
    chunk_parts: list[str] = []
    chunk_bytes = 0
    chunk_articles = 0
    article_count = 0
    text_bytes = 0
    started = time.monotonic()

    def build_manifest(partial: bool) -> dict:
        spec_bytes = sum(chunk["spec_size"] for chunk in chunks)
        return {
            "format": "spectrum-wikipedia-shards-v1",
            "status": "partial" if partial else "complete",
            "project": args.project,
            "source_dump": str(dump_path),
            "source_dump_bytes": dump_path.stat().st_size if dump_path.exists() else None,
            "mode": args.mode,
            "dict_version": D.DICT_VERSION,
            "library_model": "manifest-declared",
            "libraries": wikipedia_libraries(args.mode),
            "planned_lossless_libraries": planned_wikipedia_lossless_libraries(),
            "chunk_target_bytes": args.chunk_bytes,
            "article_count": article_count,
            "text_bytes": text_bytes,
            "spec_bytes": spec_bytes,
            "ratio": round(spec_bytes / max(text_bytes, 1), 6),
            "chunks": chunks,
        }

    def flush_chunk(partial: bool) -> None:
        nonlocal chunk_parts, chunk_bytes, chunk_articles
        chunks.append(
            write_chunk(
                chunk_parts,
                output_dir,
                len(chunks),
                args.zlib_level,
                not args.no_rle,
                chunk_articles,
                args.resume_existing,
                args.mode,
            )
        )
        write_manifest(output_dir, build_manifest(partial=True), partial=True)
        chunk_parts = []
        chunk_bytes = 0
        chunk_articles = 0

    with bz2.open(dump_path, "rb") as stream:
        for title, wikitext in iter_articles(stream, include_redirects=args.include_redirects):
            record = article_record(title, wikitext, args.mode)
            if not record:
                continue

            record_size = len(record.encode("utf-8"))
            if chunk_parts and chunk_bytes + record_size > args.chunk_bytes:
                flush_chunk(partial=True)

            chunk_parts.append(record)
            chunk_bytes += record_size
            chunk_articles += 1
            text_bytes += record_size
            article_count += 1

            if article_count % args.report_every == 0:
                elapsed = max(time.monotonic() - started, 0.001)
                rate = article_count / elapsed
                print(
                    f"[wiki-spec] processed {article_count:,} articles, "
                    f"{text_bytes:,} text bytes ({rate:.1f} articles/s)"
                )

            if args.max_pages and article_count >= args.max_pages:
                break

    if chunk_parts:
        flush_chunk(partial=True)

    manifest = build_manifest(partial=False)
    manifest_path = output_dir / "manifest.json"
    write_manifest(output_dir, manifest, partial=False)
    print(f"[wiki-spec] wrote {manifest_path}")
    print(
        f"[wiki-spec] total: {article_count:,} articles, "
        f"{text_bytes:,} text bytes -> {manifest['spec_bytes']:,} spec bytes "
        f"({manifest['ratio']:.4f}x)"
    )
    return manifest


def encode_full_xml_dump(args: argparse.Namespace, dump_path: Path, output_dir: Path) -> dict:
    chunks: list[dict] = []
    text_bytes = 0
    chunk_parts: list[str] = []
    chunk_bytes = 0

    def build_manifest(partial: bool) -> dict:
        spec_bytes = sum(chunk["spec_size"] for chunk in chunks)
        return {
            "format": "spectrum-wikipedia-shards-v1",
            "status": "partial" if partial else "complete",
            "project": args.project,
            "source_dump": str(dump_path),
            "source_dump_bytes": dump_path.stat().st_size if dump_path.exists() else None,
            "mode": args.mode,
            "dict_version": D.DICT_VERSION,
            "library_model": "manifest-declared",
            "libraries": wikipedia_libraries(args.mode),
            "chunk_target_bytes": args.chunk_bytes,
            "article_count": None,
            "text_bytes": text_bytes,
            "spec_bytes": spec_bytes,
            "ratio": round(spec_bytes / max(text_bytes, 1), 6),
            "chunks": chunks,
        }

    def flush_chunk(partial: bool) -> None:
        nonlocal chunk_parts, chunk_bytes
        if not chunk_parts:
            return
        chunks.append(
            write_chunk(
                chunk_parts,
                output_dir,
                len(chunks),
                args.zlib_level,
                not args.no_rle,
                0,
                args.resume_existing,
                args.mode,
            )
        )
        write_manifest(output_dir, build_manifest(partial=True), partial=True)
        chunk_parts = []
        chunk_bytes = 0

    decoder = None
    import codecs
    decoder = codecs.getincrementaldecoder("utf-8")("strict")

    with bz2.open(dump_path, "rb") as stream:
        while True:
            block = stream.read(1024 * 1024)
            if not block:
                tail = decoder.decode(b"", final=True)
                if tail:
                    encoded_tail = tail.encode("utf-8")
                    chunk_parts.append(tail)
                    chunk_bytes += len(encoded_tail)
                    text_bytes += len(encoded_tail)
                break

            text = decoder.decode(block, final=False)
            if not text:
                continue

            encoded_size = len(text.encode("utf-8"))
            chunk_parts.append(text)
            chunk_bytes += encoded_size
            text_bytes += encoded_size

            if chunk_bytes >= args.chunk_bytes:
                flush_chunk(partial=True)

            if args.max_input_bytes and text_bytes >= args.max_input_bytes:
                break

    if chunk_parts:
        flush_chunk(partial=True)

    manifest = build_manifest(partial=False)
    write_manifest(output_dir, manifest, partial=False)
    print(f"[wiki-spec] wrote {output_dir / 'manifest.json'}")
    print(
        f"[wiki-spec] total full XML: "
        f"{text_bytes:,} text bytes -> {manifest['spec_bytes']:,} spec bytes "
        f"({manifest['ratio']:.4f}x)"
    )
    return manifest


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Download/stream a Wikimedia article dump into .spec text chunks."
    )
    parser.add_argument("--project", default="enwiki", help="Wikimedia project, e.g. enwiki or simplewiki")
    parser.add_argument("--input", default=None, help="Existing pages-articles .xml.bz2 file")
    parser.add_argument("--output-dir", default="wiki_spec_output", help="Output directory")
    parser.add_argument("--mode", choices=["clean-text", "raw-wikitext", "full-xml"], default="clean-text")
    parser.add_argument("--max-pages", type=int, default=0, help="Stop after N articles; 0 means all")
    parser.add_argument("--max-input-bytes", type=int, default=0,
                        help="Stop full-xml mode after approximately N decompressed UTF-8 bytes; 0 means all")
    parser.add_argument("--chunk-bytes", type=int, default=DEFAULT_CHUNK_BYTES)
    parser.add_argument("--zlib-level", type=int, default=9, choices=range(1, 10))
    parser.add_argument("--no-rle", action="store_true")
    parser.add_argument("--include-redirects", action="store_true")
    parser.add_argument("--download-only", action="store_true")
    parser.add_argument("--force-download", action="store_true")
    parser.add_argument("--report-every", type=int, default=1000)
    parser.add_argument(
        "--resume-existing",
        action="store_true",
        help="Reuse existing chunk files while replaying the dump from the beginning.",
    )
    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    encode_dump(args)


if __name__ == "__main__":
    main()
