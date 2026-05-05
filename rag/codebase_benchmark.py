"""
Codebase RAG storage benchmark: conventional raw-code TF-IDF vs Spectrum .spec.

This is intentionally separate from the Wiki benchmark. Code retrieval needs
path, filename, and identifier signals that are not always represented as core
dictionary tokens in the lossless payload.
"""

from __future__ import annotations

import argparse
import json
import math
import re
import struct
import sys
import time
import zlib
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from statistics import mean

_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_ROOT))

import dictionary as D
from rag.normalization import retrieval_token_ids
from rag.query import encode_query
from rag.storage_benchmark import (
    BinarySpectrumBM25,
    build_conventional_store,
    dir_size,
    rel_path,
    reset_dir,
    write_binary_postings,
    write_binary_postings_v2,
)
from spec_format.spec_decoder import HEADER_SIZE, ids_to_tokens, parse_header
from spec_format._frozen import get_ascii_base_for_version, get_id_to_token_for_version
from spec_format.extension_tokens import extension_id_to_literal
from spec_format.spec_encoder import (
    FLAG_RLE,
    LANGUAGE_C,
    LANGUAGE_CPP,
    LANGUAGE_CSHARP,
    LANGUAGE_CSS,
    LANGUAGE_GO,
    LANGUAGE_HTML,
    LANGUAGE_JS,
    LANGUAGE_JAVA,
    LANGUAGE_JSON,
    LANGUAGE_PHP,
    LANGUAGE_PYTHON,
    LANGUAGE_RUST,
    LANGUAGE_SHELL,
    LANGUAGE_SQL,
    LANGUAGE_TEXT,
    LANGUAGE_TOML,
    LANGUAGE_TS,
    LANGUAGE_YAML,
    apply_rle_ids,
    build_header,
    tokens_to_ids,
)
from tokenizers.config_tokenizer import tokenise_config
from tokenizers.c_tokenizer import tokenise_c
from tokenizers.cpp_tokenizer import tokenise_cpp
from tokenizers.csharp_tokenizer import tokenise_csharp
from tokenizers.css_tokenizer import tokenise_css
from tokenizers.go_tokenizer import tokenise_go
from tokenizers.html_tokenizer import tokenise_html
from tokenizers.java_tokenizer import tokenise_java
from tokenizers.js_tokenizer import tokenise_js
from tokenizers.php_tokenizer import tokenise_php
from tokenizers.rust_tokenizer import tokenise_rust
from tokenizers.shell_tokenizer import tokenise_shell
from tokenizers.sql_tokenizer import tokenise_sql
from tokenizers.text_tokenizer import tokenize_text
from tokenizers.ts_tokenizer import tokenise_ts

try:
    import numpy as np
except Exception as exc:  # pragma: no cover
    raise SystemExit(f"This benchmark requires numpy. Import failed: {exc}")


LANG_BY_EXT = {
    ".py": LANGUAGE_PYTHON,
    ".html": LANGUAGE_HTML,
    ".htm": LANGUAGE_HTML,
    ".js": LANGUAGE_JS,
    ".mjs": LANGUAGE_JS,
    ".cjs": LANGUAGE_JS,
    ".css": LANGUAGE_CSS,
    ".md": LANGUAGE_TEXT,
    ".txt": LANGUAGE_TEXT,
    ".ts": LANGUAGE_TS,
    ".tsx": LANGUAGE_TS,
    ".sql": LANGUAGE_SQL,
    ".rs": LANGUAGE_RUST,
    ".php": LANGUAGE_PHP,
    ".phtml": LANGUAGE_PHP,
    ".java": LANGUAGE_JAVA,
    ".c": LANGUAGE_C,
    ".h": LANGUAGE_C,
    ".cpp": LANGUAGE_CPP,
    ".cc": LANGUAGE_CPP,
    ".cxx": LANGUAGE_CPP,
    ".hpp": LANGUAGE_CPP,
    ".hh": LANGUAGE_CPP,
    ".hxx": LANGUAGE_CPP,
    ".go": LANGUAGE_GO,
    ".cs": LANGUAGE_CSHARP,
    ".sh": LANGUAGE_SHELL,
    ".bash": LANGUAGE_SHELL,
    ".zsh": LANGUAGE_SHELL,
    ".json": LANGUAGE_JSON,
    ".yaml": LANGUAGE_YAML,
    ".yml": LANGUAGE_YAML,
    ".toml": LANGUAGE_TOML,
}

LANG_NAMES = {
    LANGUAGE_PYTHON: "python",
    LANGUAGE_HTML: "html",
    LANGUAGE_JS: "javascript",
    LANGUAGE_CSS: "css",
    LANGUAGE_TEXT: "text",
    LANGUAGE_TS: "typescript",
    LANGUAGE_SQL: "sql",
    LANGUAGE_RUST: "rust",
    LANGUAGE_PHP: "php",
    LANGUAGE_JAVA: "java",
    LANGUAGE_C: "c",
    LANGUAGE_CPP: "cpp",
    LANGUAGE_GO: "go",
    LANGUAGE_CSHARP: "csharp",
    LANGUAGE_SHELL: "shell",
    LANGUAGE_JSON: "json",
    LANGUAGE_YAML: "yaml",
    LANGUAGE_TOML: "toml",
}

TOKENIZER_BY_LANG = {
    LANGUAGE_HTML: tokenise_html,
    LANGUAGE_JS: tokenise_js,
    LANGUAGE_CSS: tokenise_css,
    LANGUAGE_TEXT: tokenize_text,
    LANGUAGE_TS: tokenise_ts,
    LANGUAGE_SQL: tokenise_sql,
    LANGUAGE_RUST: tokenise_rust,
    LANGUAGE_PHP: tokenise_php,
    LANGUAGE_JAVA: tokenise_java,
    LANGUAGE_C: tokenise_c,
    LANGUAGE_CPP: tokenise_cpp,
    LANGUAGE_GO: tokenise_go,
    LANGUAGE_CSHARP: tokenise_csharp,
    LANGUAGE_SHELL: tokenise_shell,
    LANGUAGE_JSON: tokenise_config,
    LANGUAGE_YAML: tokenise_config,
    LANGUAGE_TOML: tokenise_config,
}

DEFAULT_EXCLUDE_DIRS = {
    ".git",
    "__pycache__",
    ".pytest_cache",
    ".mypy_cache",
    ".ruff_cache",
    ".venv",
    "venv",
    "env",
    "node_modules",
    "deck_workspace",
    "output_images",
    "results",
    "spec compressed",
    "wiki_enwiki_dump",
    "wiki_enwiki_fullxml_1hr",
    "wiki_enwiki_fullxml_sample",
    "wiki_enwiki_raw_10pct",
    "wiki_enwiki_raw_sample",
}
DEFAULT_EXCLUDE_PREFIXES = (
    "codebase_benchmark",
    "normalization_audit",
    "parameter_sweep",
    "ranking_eval",
    "storage_benchmark",
)

IDENT_RE = re.compile(r"[A-Za-z_][A-Za-z0-9_]{1,}")
SPLIT_RE = re.compile(r"[_\-.\\/]+|(?<=[a-z0-9])(?=[A-Z])|(?<=[A-Z])(?=[A-Z][a-z])")


@dataclass
class CodeChunk:
    id: int
    title: str
    text: str
    page_index: int
    chunk_index: int
    source_path: str
    language_id: int


def tokenize_source_for_language(text: str, language_id: int) -> list[str]:
    tokenizer = TOKENIZER_BY_LANG.get(language_id)
    try:
        if tokenizer is not None:
            return tokenizer(text)
        from encoder.encoder import tokenise_source

        return tokenise_source(text)
    except Exception:
        # Code chunks may start or end mid-syntax. Character fallback preserves
        # exact bytes while retrieval aliases still index path/identifier signal.
        return list(text)


def percentile(values: list[float], pct: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    idx = min(len(ordered) - 1, math.ceil((pct / 100) * len(ordered)) - 1)
    return ordered[idx]


def decode_code_spec_bytes(data: bytes) -> str:
    meta = parse_header(data)
    raw_stream = zlib.decompress(data[HEADER_SIZE:])
    ids = list(struct.unpack(f"<{len(raw_stream) // 4}I", raw_stream))
    if meta["dict_version"] == D.DICT_VERSION:
        tokens = ids_to_tokens(ids)
    else:
        tokens = ids_to_tokens(
            ids,
            id_to_token=get_id_to_token_for_version(meta["dict_version"]),
            ascii_base=get_ascii_base_for_version(meta["dict_version"]),
        )
    if meta["language_id"] == LANGUAGE_TEXT:
        from tokenizers.text_tokenizer import reconstruct_text

        text = reconstruct_text(tokens)
    else:
        text = "".join(tokens)
    encoded = text.encode("utf-8")
    if len(encoded) > meta["orig_length"]:
        text = encoded[: meta["orig_length"]].decode("utf-8", errors="replace")
    return text


_PRISM_CACHE: dict[int, tuple[dict[int, bytes], int]] = {}


def _byte_prism_for_version(dict_version: int) -> tuple[dict[int, bytes], int]:
    cached = _PRISM_CACHE.get(dict_version)
    if cached is not None:
        return cached
    if dict_version == D.DICT_VERSION:
        id_to_token = D.SPEC_ID_TO_TOKEN
        ascii_base = D.SPEC_ID_ASCII_BASE
    else:
        id_to_token = get_id_to_token_for_version(dict_version)
        ascii_base = get_ascii_base_for_version(dict_version)
    prism = {
        token_id: token.encode("utf-8")
        for token_id, token in id_to_token.items()
    }
    for offset in range(128):
        prism[ascii_base + offset] = bytes((offset,))
    _PRISM_CACHE[dict_version] = (prism, ascii_base)
    return prism, ascii_base


def decode_code_spec_bytes_fast(data: bytes) -> str:
    """
    Fast serving decoder for code-like chunks.

    This is the "byte prism" path: inflate the ID stream and append each token's
    raw UTF-8 bytes directly to an output buffer. Plain text chunks still use
    the control-token reconstructor because their token stream includes
    capitalisation and spelling control tokens that are not literal bytes.
    """
    meta = parse_header(data)
    if meta["language_id"] == LANGUAGE_TEXT:
        return decode_code_spec_bytes(data)

    raw_stream = zlib.decompress(data[HEADER_SIZE:])
    ids = struct.iter_unpack("<I", raw_stream)
    prism, _ascii_base = _byte_prism_for_version(meta["dict_version"])
    out = bytearray()
    last_piece: bytes | None = None
    pending_unicode = False
    pending_rle = False

    for (val,) in ids:
        if pending_unicode:
            piece = chr(val).encode("utf-8")
            out.extend(piece)
            last_piece = piece
            pending_unicode = False
            continue
        if pending_rle:
            if last_piece is not None and val:
                out.extend(last_piece * val)
            pending_rle = False
            continue
        if val == D.SPEC_ID_UNICODE:
            pending_unicode = True
            continue
        if val == D.SPEC_ID_RLE:
            pending_rle = True
            continue

        extension_literal = extension_id_to_literal(val)
        if extension_literal is not None:
            piece = extension_literal.encode("utf-8")
        else:
            piece = prism.get(val)
            if piece is None:
                raise ValueError(f"Unknown token ID {val} for dict v{meta['dict_version']}")
        out.extend(piece)
        last_piece = piece

    if len(out) > meta["orig_length"]:
        del out[meta["orig_length"]:]
    return out.decode("utf-8", errors="replace")


def split_words(value: str) -> list[str]:
    words: list[str] = []
    for part in SPLIT_RE.split(value):
        part = part.strip()
        if len(part) >= 2 and not part.isdigit():
            words.append(part.lower())
    return words


def retrieval_alias_ids(text: str, source_path: str, language_id: int) -> list[int]:
    aliases: list[int] = []
    seen: set[int] = set()

    def add(value: str) -> None:
        for token_id in retrieval_token_ids(value):
            if token_id not in seen:
                seen.add(token_id)
                aliases.append(token_id)

    path = Path(source_path)
    add(" ".join(path.parts))
    add(path.stem)
    add(LANG_NAMES.get(language_id, "code"))

    identifier_words: list[str] = []
    for ident in IDENT_RE.findall(text):
        identifier_words.extend(split_words(ident))
    if identifier_words:
        add(" ".join(identifier_words))

    return aliases


def pack_spec_bytes(text: str, tokens: list[str], language_id: int) -> tuple[bytes, list[int]]:
    source_bytes = text.encode("utf-8")
    checksum = sum(source_bytes) & 0xFFFF
    raw_ids = tokens_to_ids(tokens)
    encoded_ids = apply_rle_ids(raw_ids)
    raw_stream = struct.pack(f"<{len(encoded_ids)}I", *encoded_ids)
    body = zlib.compress(raw_stream, level=9)
    header = build_header(
        D.DICT_VERSION,
        len(source_bytes),
        checksum,
        FLAG_RLE,
        language_id,
    )
    return header + body, raw_ids


def encode_code_to_spec_bytes(chunk: CodeChunk) -> tuple[bytes, list[int]]:
    tokens = tokenize_source_for_language(chunk.text, chunk.language_id)
    data, raw_ids = pack_spec_bytes(chunk.text, tokens, chunk.language_id)
    if decode_code_spec_bytes(data) != chunk.text:
        tokens = list(chunk.text)
        data, raw_ids = pack_spec_bytes(chunk.text, tokens, chunk.language_id)

    dict_ids = [token_id for token_id in raw_ids if token_id < D.SPEC_ID_ASCII_BASE]
    dict_ids.extend(retrieval_alias_ids(chunk.text, chunk.source_path, chunk.language_id))
    return data, dict_ids


def should_skip(path: Path, root: Path, exclude_dirs: set[str], max_file_bytes: int) -> bool:
    if path.suffix.lower() not in LANG_BY_EXT:
        return True
    if path.stat().st_size > max_file_bytes:
        return True
    rel_parts = path.relative_to(root).parts
    return any(
        part in exclude_dirs or part.startswith(DEFAULT_EXCLUDE_PREFIXES)
        for part in rel_parts[:-1]
    )


def collect_source_files(root: Path, max_file_bytes: int, exclude_dirs: set[str]) -> list[Path]:
    files = []
    for path in root.rglob("*"):
        if path.is_file() and not should_skip(path, root, exclude_dirs, max_file_bytes):
            files.append(path)
    return sorted(files)


def make_code_chunks(
    root: Path,
    paths: list[Path],
    chunk_chars: int,
    overlap_chars: int,
) -> list[CodeChunk]:
    chunks: list[CodeChunk] = []
    for file_idx, path in enumerate(paths):
        text = path.read_text(encoding="utf-8", errors="replace")
        rel = rel_path(path, root)
        language_id = LANG_BY_EXT[path.suffix.lower()]
        body = f"{rel}\n\n{text}"
        if chunk_chars <= 0:
            chunks.append(CodeChunk(
                id=len(chunks),
                title=rel,
                text=body,
                page_index=file_idx,
                chunk_index=0,
                source_path=rel,
                language_id=language_id,
            ))
            continue
        step = max(1, chunk_chars - overlap_chars)
        start = 0
        chunk_index = 0
        while start < len(body):
            part = body[start : start + chunk_chars]
            chunks.append(CodeChunk(
                id=len(chunks),
                title=rel,
                text=part,
                page_index=file_idx,
                chunk_index=chunk_index,
                source_path=rel,
                language_id=language_id,
            ))
            chunk_index += 1
            if start + chunk_chars >= len(body):
                break
            start += step
    return chunks


def build_spectrum_code_store(
    chunks: list[CodeChunk],
    out_dir: Path,
    verify_fidelity: bool,
    k1: float,
    b: float,
    postings_format: str,
) -> tuple[dict, list[dict], BinarySpectrumBM25]:
    if postings_format not in {"v1", "v2", "both"}:
        raise ValueError(f"Unsupported postings format: {postings_format}")
    reset_dir(out_dir)
    chunk_dir = out_dir / "chunks"
    chunk_dir.mkdir(parents=True, exist_ok=True)
    started = time.perf_counter()
    cpu_started = time.process_time()

    documents = []
    postings: dict[int, list[tuple[int, int]]] = {}
    total_tokens = 0
    fidelity_failures = []

    for chunk in chunks:
        data, dict_ids = encode_code_to_spec_bytes(chunk)
        spec_path = chunk_dir / f"chunk_{chunk.id:06d}.spec"
        spec_path.write_bytes(data)
        if verify_fidelity and decode_code_spec_bytes(data) != chunk.text:
            fidelity_failures.append(chunk.id)

        freq = Counter(dict_ids)
        total_tokens += len(dict_ids)
        documents.append({
            "id": chunk.id,
            "path": rel_path(spec_path, out_dir),
            "name": f"chunk_{chunk.id:06d}",
            "title": chunk.title,
            "source_path": chunk.source_path,
            "page_index": chunk.page_index,
            "chunk_index": chunk.chunk_index,
            "language_id": chunk.language_id,
            "orig_length": len(chunk.text.encode("utf-8")),
            "token_count": len(dict_ids),
        })
        for token_id, count in freq.items():
            postings.setdefault(token_id, []).append((chunk.id, count))

    avg_doc_length = total_tokens / len(documents) if documents else 0.0
    written_index_formats = []
    if postings_format in {"v1", "both"}:
        write_binary_postings(out_dir / "postings.bin", documents, postings, avg_doc_length)
        written_index_formats.append("SPB1")
    if postings_format in {"v2", "both"}:
        write_binary_postings_v2(out_dir / "postings_v2.bin", documents, postings, avg_doc_length)
        written_index_formats.append("SPB2")
    (out_dir / "docs.json").write_text(
        json.dumps({
            "format": "spectrum-code-rag-binary-postings-docs-v1",
            "total_docs": len(documents),
            "avg_doc_length": round(avg_doc_length, 2),
            "dict_version": D.DICT_VERSION,
            "documents": documents,
        }, ensure_ascii=False, separators=(",", ":")),
        encoding="utf-8",
    )
    meta = {
        "format": "spectrum-code-rag-store-v1",
        "index_format": "spectrum-rag-binary-postings-" + postings_format,
        "binary_index_formats": written_index_formats,
        "chunks": len(chunks),
        "dict_version": D.DICT_VERSION,
        "retrieval_aliases": ["path", "filename", "language", "identifiers"],
        "fidelity_verified": verify_fidelity,
        "fidelity_failures": fidelity_failures,
        "lossless_ok": not fidelity_failures if verify_fidelity else None,
        "build_seconds": round(time.perf_counter() - started, 4),
        "build_cpu_seconds": round(time.process_time() - cpu_started, 4),
    }
    (out_dir / "meta.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")
    return meta, documents, BinarySpectrumBM25(documents, postings, avg_doc_length, k1=k1, b=b)


def make_file_queries(chunks: list[CodeChunk], count: int) -> list[dict]:
    by_file: dict[str, list[int]] = {}
    for chunk in chunks:
        by_file.setdefault(chunk.source_path, []).append(chunk.id)

    queries = []
    for source_path, relevant_ids in by_file.items():
        path = Path(source_path)
        words = split_words(path.stem)
        parent_words = split_words(" ".join(path.parent.parts))
        query_words = words + parent_words[:3]
        if not query_words:
            query_words = [path.stem]
        queries.append({
            "query": " ".join(dict.fromkeys(query_words)),
            "title": source_path,
            "relevant_ids": relevant_ids,
        })

    queries.sort(key=lambda item: item["title"])
    return queries[:count] if count else queries


def conventional_search(vectorizer, matrix, query: str, top_k: int) -> list[int]:
    q = vectorizer.transform([query])
    scores = (matrix @ q.T).toarray().ravel()
    if not np.any(scores):
        return []
    order = np.argsort(-scores)[:top_k]
    return [int(idx) for idx in order if scores[idx] > 0]


def title_token_sets(documents: list[dict]) -> list[set[int]]:
    return [set(retrieval_token_ids(doc.get("title", ""))) for doc in documents]


def title_token_index(documents: list[dict]) -> dict[int, list[int]]:
    index: dict[int, list[int]] = {}
    for doc_id, doc in enumerate(documents):
        for token_id in set(retrieval_token_ids(doc.get("title", ""))):
            index.setdefault(token_id, []).append(doc_id)
    return index


def evaluate(
    queries: list[dict],
    conventional,
    spectrum: BinarySpectrumBM25,
    documents: list[dict],
    top_k: int,
    max_df_ratio: float | None,
    title_boost: float,
) -> dict:
    vectorizer, matrix = conventional
    spectrum_title_index = title_token_index(documents) if title_boost else None
    metrics = {
        "conventional": {"hit1": 0, "recall": 0, "rr": [], "latencies": []},
        "spectrum": {"hit1": 0, "recall": 0, "rr": [], "latencies": []},
    }
    for item in queries:
        relevant = set(item["relevant_ids"])
        started = time.perf_counter()
        conventional_ids = conventional_search(vectorizer, matrix, item["query"], top_k)
        metrics["conventional"]["latencies"].append((time.perf_counter() - started) * 1000)

        query_ids = retrieval_token_ids(item["query"])
        started = time.perf_counter()
        spectrum_ids = spectrum.search(
            query_ids,
            top_k,
            max_df_ratio=max_df_ratio,
            title_index=spectrum_title_index,
            title_boost=title_boost,
        )
        metrics["spectrum"]["latencies"].append((time.perf_counter() - started) * 1000)

        for name, ids in (("conventional", conventional_ids), ("spectrum", spectrum_ids)):
            if ids and ids[0] in relevant:
                metrics[name]["hit1"] += 1
            if relevant.intersection(ids):
                metrics[name]["recall"] += 1
            rank = next((i + 1 for i, doc_id in enumerate(ids) if doc_id in relevant), None)
            metrics[name]["rr"].append(1 / rank if rank else 0.0)

    total = max(1, len(queries))
    return {
        name: {
            "hit_at_1": round(row["hit1"] / total, 4),
            f"recall_at_{top_k}": round(row["recall"] / total, 4),
            "mrr": round(mean(row["rr"]) if row["rr"] else 0.0, 4),
            "avg_query_ms": round(mean(row["latencies"]) if row["latencies"] else 0.0, 4),
            "p95_query_ms": round(percentile(row["latencies"], 95), 4),
        }
        for name, row in metrics.items()
    }


def write_report(out_dir: Path, report: dict) -> None:
    top_k = report["settings"]["top_k"]
    lines = [
        "# Spectrum Codebase Storage Benchmark",
        "",
        f"- Source root: `{report['settings']['source_root']}`",
        f"- Files: {report['corpus']['files']:,}",
        f"- Chunks: {report['corpus']['chunks']:,}",
        f"- Raw chunk bytes: {report['corpus']['raw_bytes']:,}",
        f"- Queries: {report['settings']['queries']:,}",
        "",
        "## Storage",
        "",
        "| Store | Bytes | Ratio vs raw | Payload bytes | Index bytes | Build sec |",
        "|---|---:|---:|---:|---:|---:|",
    ]
    for key, label in (("conventional", "Conventional raw+TF-IDF"), ("spectrum", "Spectrum `.spec`+binary BM25")):
        row = report["stores"][key]
        lines.append(
            f"| {label} | {row['bytes']:,} | {row['ratio_vs_raw']:.3f}x | "
            f"{row['components']['payload_bytes']:,} | {row['components']['index_bytes']:,} | "
            f"{row['build_seconds']:.3f} |"
        )
    lines.extend([
        "",
        "## Retrieval",
        "",
        f"| Store | Hit@1 | MRR | Recall@{top_k} | Avg ms | P95 ms |",
        "|---|---:|---:|---:|---:|---:|",
    ])
    for key, label in (("conventional", "Conventional raw+TF-IDF"), ("spectrum", "Spectrum `.spec`+binary BM25")):
        row = report["retrieval"][key]
        lines.append(
            f"| {label} | {row['hit_at_1']:.3f} | {row['mrr']:.3f} | "
            f"{row[f'recall_at_{top_k}']:.3f} | {row['avg_query_ms']:.3f} | "
            f"{row['p95_query_ms']:.3f} |"
        )
    spectrum = report["stores"]["spectrum"]
    lines.extend([
        "",
        "## Fidelity",
        "",
        f"- Spectrum lossless: `{spectrum['lossless_ok']}`",
        f"- Fidelity failures: {spectrum['fidelity_failures']}",
        "",
        "The Spectrum store indexes retrieval-only aliases from paths and identifiers; "
        "the `.spec` chunk payloads remain byte-for-byte lossless.",
    ])
    (out_dir / "report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def run(args: argparse.Namespace) -> dict:
    source_root = Path(args.source_root).resolve()
    out_dir = Path(args.out_dir)
    reset_dir(out_dir)

    exclude_dirs = DEFAULT_EXCLUDE_DIRS.union(
        item.strip() for item in args.exclude_dir if item.strip()
    )
    paths = collect_source_files(source_root, args.max_file_bytes, exclude_dirs)
    if args.max_files:
        paths = paths[: args.max_files]
    chunks = make_code_chunks(source_root, paths, args.chunk_chars, args.overlap_chars)
    raw_bytes = sum(len(chunk.text.encode("utf-8")) for chunk in chunks)

    conventional_dir = out_dir / "conventional_tfidf"
    spectrum_dir = out_dir / "spectrum_spec"
    conventional_meta, vectorizer, matrix = build_conventional_store(chunks, conventional_dir)
    spectrum_meta, documents, bm25 = build_spectrum_code_store(
        chunks,
        spectrum_dir,
        verify_fidelity=not args.skip_verify,
        k1=args.spectrum_k1,
        b=args.spectrum_b,
        postings_format=args.postings_format,
    )

    queries = make_file_queries(chunks, args.queries)
    (out_dir / "queries.json").write_text(json.dumps(queries, indent=2), encoding="utf-8")
    retrieval = evaluate(
        queries,
        conventional=(vectorizer, matrix),
        spectrum=bm25,
        documents=documents,
        top_k=args.top_k,
        max_df_ratio=args.spectrum_max_df_ratio,
        title_boost=args.spectrum_title_boost,
    )

    conventional_components = {
        "payload_bytes": (conventional_dir / "chunks.jsonl").stat().st_size,
        "index_bytes": (conventional_dir / "tfidf_matrix.npz").stat().st_size
        + (conventional_dir / "tfidf_vocabulary.json").stat().st_size,
        "metadata_bytes": (conventional_dir / "meta.json").stat().st_size,
    }
    spectrum_components = {
        "payload_bytes": dir_size(spectrum_dir / "chunks"),
        "index_bytes": sum(
            path.stat().st_size
            for path in (spectrum_dir / "postings.bin", spectrum_dir / "postings_v2.bin")
            if path.exists()
        ) + (spectrum_dir / "docs.json").stat().st_size,
        "metadata_bytes": (spectrum_dir / "meta.json").stat().st_size,
    }
    report = {
        "format": "spectrum-codebase-storage-benchmark-v1",
        "settings": {
            "source_root": str(source_root),
            "max_files": args.max_files,
            "max_file_bytes": args.max_file_bytes,
            "chunk_chars": args.chunk_chars,
            "overlap_chars": args.overlap_chars,
            "queries": len(queries),
            "top_k": args.top_k,
            "skip_verify": args.skip_verify,
            "spectrum_k1": args.spectrum_k1,
            "spectrum_b": args.spectrum_b,
            "spectrum_max_df_ratio": args.spectrum_max_df_ratio,
            "spectrum_title_boost": args.spectrum_title_boost,
            "postings_format": args.postings_format,
        },
        "corpus": {
            "files": len(paths),
            "chunks": len(chunks),
            "raw_bytes": raw_bytes,
            "extensions": dict(sorted(Counter(path.suffix.lower() for path in paths).items())),
        },
        "stores": {
            "conventional": {
                "bytes": dir_size(conventional_dir),
                "ratio_vs_raw": dir_size(conventional_dir) / raw_bytes if raw_bytes else math.nan,
                "build_seconds": conventional_meta["build_seconds"],
                "build_cpu_seconds": conventional_meta["build_cpu_seconds"],
                "components": conventional_components,
            },
            "spectrum": {
                "bytes": dir_size(spectrum_dir),
                "ratio_vs_raw": dir_size(spectrum_dir) / raw_bytes if raw_bytes else math.nan,
                "build_seconds": spectrum_meta["build_seconds"],
                "build_cpu_seconds": spectrum_meta["build_cpu_seconds"],
                "fidelity_verified": spectrum_meta["fidelity_verified"],
                "lossless_ok": spectrum_meta["lossless_ok"],
                "fidelity_failures": (
                    len(spectrum_meta["fidelity_failures"])
                    if spectrum_meta["fidelity_verified"] else None
                ),
                "components": spectrum_components,
            },
        },
        "retrieval": retrieval,
    }
    (out_dir / "report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    write_report(out_dir, report)
    print(f"[codebase-bench] wrote {out_dir / 'report.md'}")
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description="Benchmark raw-code RAG storage vs Spectrum .spec code RAG storage.")
    parser.add_argument("--source-root", default=".", help="Codebase root to scan.")
    parser.add_argument("--out-dir", default="benchmarks/generated/codebase_benchmark", help="Output benchmark directory.")
    parser.add_argument("--max-files", type=int, default=120, help="Maximum source files to include; 0 means all.")
    parser.add_argument("--max-file-bytes", type=int, default=1_000_000, help="Skip individual source files larger than this.")
    parser.add_argument("--chunk-chars", type=int, default=0, help="Characters per code chunk; 0 keeps one chunk per file.")
    parser.add_argument("--overlap-chars", type=int, default=600, help="Character overlap between chunks.")
    parser.add_argument("--queries", type=int, default=80, help="Number of generated file/path queries; 0 means all files.")
    parser.add_argument("--top-k", type=int, default=5, help="Recall@k and search result count.")
    parser.add_argument("--skip-verify", action="store_true", help="Skip Spectrum decode-after-encode checks.")
    parser.add_argument("--spectrum-k1", type=float, default=1.5, help="Spectrum BM25 k1 parameter.")
    parser.add_argument("--spectrum-b", type=float, default=0.75, help="Spectrum BM25 b parameter.")
    parser.add_argument("--spectrum-max-df-ratio", type=float, default=0.9, help="Spectrum query-time DF filter.")
    parser.add_argument("--spectrum-title-boost", type=float, default=0.5, help="Boost matching path/title aliases.")
    parser.add_argument(
        "--postings-format",
        choices=["v1", "v2", "both"],
        default="v1",
        help="Binary postings format to write for the Spectrum store.",
    )
    parser.add_argument(
        "--exclude-dir",
        action="append",
        default=[],
        help="Additional directory names to exclude. Can be repeated.",
    )
    args = parser.parse_args()
    if args.max_files == 0:
        args.max_files = None
    run(args)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
