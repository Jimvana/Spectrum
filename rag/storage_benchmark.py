"""
RAG storage benchmark: conventional local vector store vs Spectrum .spec store.

The benchmark builds two stores from the same corpus:

1. Conventional local RAG baseline
   - raw chunk text in JSONL
   - sklearn TF-IDF sparse vector matrix
   - chunk metadata

2. Spectrum RAG store
   - one lossless .spec file per chunk
   - compact binary Spectrum token BM25 postings/frequency index
   - no raw chunk text stored in the Spectrum store

It then measures disk size, build time, retrieval quality, query latency,
decode latency, and lossless round-trip fidelity.
"""

from __future__ import annotations

import argparse
import heapq
import html
import json
import math
import re
import shutil
import struct
import sys
import time
import zlib
from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from statistics import mean

_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_ROOT))

import dictionary as D
from rag.normalization import retrieval_token_ids
from rag.query import encode_query
from spec_format.spec_decoder import HEADER_SIZE, ids_to_tokens, parse_header
from spec_format.spec_encoder import (
    FLAG_RLE,
    LANGUAGE_TEXT,
    apply_rle_ids,
    build_header,
    tokens_to_ids,
)
from tokenizers.text_tokenizer import reconstruct_text, tokenize_text

try:
    import numpy as np
    from scipy import sparse
    from sklearn.feature_extraction.text import TfidfVectorizer
except Exception as exc:  # pragma: no cover - runtime dependency check
    raise SystemExit(
        "This benchmark requires numpy, scipy, and scikit-learn. "
        f"Import failed: {exc}"
    )


PAGE_RE = re.compile(r"<page>\s*(.*?)\s*</page>", re.DOTALL)
TITLE_RE = re.compile(r"<title>(.*?)</title>", re.DOTALL)
TEXT_RE = re.compile(r"<text\b[^>]*>(.*?)</text>", re.DOTALL)
WORD_RE = re.compile(r"[A-Za-z][A-Za-z0-9']+")
BINARY_INDEX_MAGIC = b"SPB1"
BINARY_INDEX_VERSION = 1
BINARY_INDEX_MAGIC_V2 = b"SPB2"
BINARY_INDEX_VERSION_V2 = 2


@dataclass
class Chunk:
    id: int
    title: str
    text: str
    page_index: int
    chunk_index: int


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def dir_size(path: Path) -> int:
    if not path.exists():
        return 0
    return sum(p.stat().st_size for p in path.rglob("*") if p.is_file())


def reset_dir(path: Path) -> None:
    if path.exists():
        shutil.rmtree(path)
    path.mkdir(parents=True, exist_ok=True)


def rel_path(path: Path, base: Path) -> str:
    try:
        return path.relative_to(base).as_posix()
    except ValueError:
        return path.as_posix()


def decode_spec_to_text(spec_path: Path) -> str:
    raw = spec_path.read_bytes()
    meta = parse_header(raw)
    raw_stream = zlib.decompress(raw[HEADER_SIZE:])
    ids = list(struct.unpack(f"<{len(raw_stream) // 4}I", raw_stream))
    tokens = ids_to_tokens(ids)
    if meta["language_id"] in (LANGUAGE_TEXT, 9):
        text = reconstruct_text(tokens)
    else:
        text = "".join(tokens)
    encoded = text.encode("utf-8")
    if len(encoded) > meta["orig_length"]:
        text = encoded[: meta["orig_length"]].decode("utf-8", errors="replace")
    return text


def extract_wiki_pages(page_index_path: Path, max_pages: int) -> list[tuple[str, str]]:
    page_index = read_json(page_index_path)
    manifest_path = Path(page_index["source_manifest"])
    if not manifest_path.is_absolute():
        manifest_path = (_ROOT / manifest_path).resolve()
    manifest = read_json(manifest_path)
    manifest_dir = manifest_path.parent

    pages: list[tuple[str, str]] = []
    for chunk in manifest["chunks"]:
        if len(pages) >= max_pages:
            break
        xml = decode_spec_to_text(manifest_dir / chunk["path"])
        for match in PAGE_RE.finditer(xml):
            title_match = TITLE_RE.search(match.group(1))
            text_match = TEXT_RE.search(match.group(1))
            if not title_match or not text_match:
                continue
            title = html.unescape(title_match.group(1)).strip()
            text = html.unescape(text_match.group(1)).strip()
            if not title or not text:
                continue
            pages.append((title, text))
            if len(pages) >= max_pages:
                break
    return pages


def make_chunks(
    pages: list[tuple[str, str]],
    chunk_chars: int,
    overlap_chars: int,
) -> list[Chunk]:
    chunks: list[Chunk] = []
    for page_idx, (title, text) in enumerate(pages):
        body = f"{title}\n\n{text}"
        if len(body) <= chunk_chars:
            chunks.append(Chunk(len(chunks), title, body, page_idx, 0))
            continue

        start = 0
        local_idx = 0
        step = max(1, chunk_chars - overlap_chars)
        while start < len(body):
            part = body[start : start + chunk_chars]
            chunks.append(Chunk(len(chunks), title, part, page_idx, local_idx))
            local_idx += 1
            if start + chunk_chars >= len(body):
                break
            start += step
    return chunks


def encode_text_to_spec_bytes(
    text: str,
    retrieval_normalization: bool = False,
) -> tuple[bytes, list[int]]:
    source_bytes = text.encode("utf-8")
    checksum = sum(source_bytes) & 0xFFFF
    tokens = tokenize_text(text)
    raw_ids = tokens_to_ids(tokens)
    if retrieval_normalization:
        dict_ids = retrieval_token_ids(text)
    else:
        dict_ids = [token_id for token_id in raw_ids if token_id < D.SPEC_ID_ASCII_BASE]
    encoded_ids = apply_rle_ids(raw_ids)
    raw_stream = struct.pack(f"<{len(encoded_ids)}I", *encoded_ids)
    body = zlib.compress(raw_stream, level=9)
    header = build_header(
        D.DICT_VERSION,
        len(source_bytes),
        checksum,
        FLAG_RLE,
        LANGUAGE_TEXT,
    )
    return header + body, dict_ids


def decode_spec_bytes(data: bytes) -> str:
    meta = parse_header(data)
    raw_stream = zlib.decompress(data[HEADER_SIZE:])
    ids = list(struct.unpack(f"<{len(raw_stream) // 4}I", raw_stream))
    text = reconstruct_text(ids_to_tokens(ids))
    encoded = text.encode("utf-8")
    if len(encoded) > meta["orig_length"]:
        text = encoded[: meta["orig_length"]].decode("utf-8", errors="replace")
    return text


def write_uvarint(value: int, out: bytearray) -> None:
    if value < 0:
        raise ValueError(f"uvarint cannot encode negative value: {value}")
    while value >= 0x80:
        out.append((value & 0x7F) | 0x80)
        value >>= 7
    out.append(value)


def read_uvarint(data: bytes, offset: int) -> tuple[int, int]:
    value = 0
    shift = 0
    while True:
        if offset >= len(data):
            raise ValueError("Truncated uvarint")
        byte = data[offset]
        offset += 1
        value |= (byte & 0x7F) << shift
        if byte < 0x80:
            return value, offset
        shift += 7
        if shift > 63:
            raise ValueError("uvarint is too large")


def build_conventional_store(chunks: list[Chunk], out_dir: Path) -> tuple[dict, object, object]:
    reset_dir(out_dir)
    started = time.perf_counter()
    cpu_started = time.process_time()

    records_path = out_dir / "chunks.jsonl"
    print(f"[storage-bench] writing {len(chunks):,} raw chunks", flush=True)
    with records_path.open("w", encoding="utf-8") as f:
        for chunk in chunks:
            f.write(json.dumps(chunk.__dict__, ensure_ascii=False) + "\n")

    documents = [chunk.text for chunk in chunks]
    vectorizer = TfidfVectorizer(
        lowercase=True,
        stop_words="english",
        max_features=100_000,
        norm="l2",
    )
    print("[storage-bench] fitting raw TF-IDF matrix", flush=True)
    matrix = vectorizer.fit_transform(documents)
    print(f"[storage-bench] raw TF-IDF features: {matrix.shape[1]:,}", flush=True)
    sparse.save_npz(out_dir / "tfidf_matrix.npz", matrix, compressed=True)
    vocabulary = {term: int(index) for term, index in vectorizer.vocabulary_.items()}
    (out_dir / "tfidf_vocabulary.json").write_text(
        json.dumps(vocabulary, separators=(",", ":")),
        encoding="utf-8",
    )
    meta = {
        "format": "conventional-local-rag-tfidf-v1",
        "chunks": len(chunks),
        "features": int(matrix.shape[1]),
        "build_seconds": round(time.perf_counter() - started, 4),
        "build_cpu_seconds": round(time.process_time() - cpu_started, 4),
    }
    (out_dir / "meta.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")
    return meta, vectorizer, matrix


class BinarySpectrumBM25:
    def __init__(
        self,
        documents: list[dict],
        postings: dict[int, list[tuple[int, int]]],
        avg_doc_length: float,
        k1: float = 1.5,
        b: float = 0.75,
    ):
        self.docs = documents
        self.postings = postings
        self.N = len(documents)
        self.avdl = avg_doc_length
        self.k1 = k1
        self.b = b
        self._lengths = [doc["token_count"] for doc in documents]
        self._norms = [
            1 - self.b + self.b * (length / self.avdl) if self.avdl > 0 else 1.0
            for length in self._lengths
        ]
        self._idf_cache = {
            token_id: math.log((self.N - len(rows) + 0.5) / (len(rows) + 0.5) + 1)
            for token_id, rows in postings.items()
        }
        self._df_ratio_cache = {
            token_id: len(rows) / self.N if self.N else 0.0
            for token_id, rows in postings.items()
        }

    def idf(self, token_id: int) -> float:
        return self._idf_cache.get(token_id, 0.0)

    def candidate_ids(self, query_ids: list[int]) -> set[int]:
        candidates: set[int] = set()
        for token_id in set(query_ids):
            candidates.update(doc_id for doc_id, _ in self.postings.get(token_id, ()))
        return candidates

    def score(self, doc_id: int, query_ids: list[int]) -> float:
        dl = self._lengths[doc_id]
        norm = 1 - self.b + self.b * (dl / self.avdl) if self.avdl > 0 else 1.0
        total = 0.0
        for token_id in query_ids:
            tf = 0
            for posting_doc_id, posting_tf in self.postings.get(token_id, ()):
                if posting_doc_id == doc_id:
                    tf = posting_tf
                    break
            if tf:
                total += self.idf(token_id) * (tf * (self.k1 + 1)) / (tf + self.k1 * norm)
        return total

    def search(
        self,
        query_ids: list[int],
        top_k: int,
        max_df_ratio: float | None = None,
        unique_query_terms: bool = False,
        title_ids: list[set[int]] | None = None,
        title_index: dict[int, list[int]] | None = None,
        title_boost: float = 0.0,
    ) -> list[int]:
        scores: dict[int, float] = {}
        if unique_query_terms:
            query_ids = list(dict.fromkeys(query_ids))
        if max_df_ratio is not None:
            df_ratios = self._df_ratio_cache
            query_ids = [
                token_id for token_id in query_ids
                if df_ratios.get(token_id, 0.0) <= max_df_ratio
            ]
        query_freq = Counter(query_ids)
        norms = self._norms
        k1 = self.k1
        k1_plus_1 = k1 + 1
        postings = self.postings
        idf_cache = self._idf_cache
        for token_id, query_count in query_freq.items():
            rows = postings.get(token_id)
            if not rows:
                continue
            idf = idf_cache.get(token_id, 0.0)
            for doc_id, tf in rows:
                score = idf * (tf * k1_plus_1) / (tf + k1 * norms[doc_id])
                scores[doc_id] = scores.get(doc_id, 0.0) + score * query_count

        if title_boost and title_index:
            for token_id in set(query_ids):
                for doc_id in title_index.get(token_id, ()):
                    scores[doc_id] = scores.get(doc_id, 0.0) + title_boost
        elif title_boost and title_ids:
            qset = set(query_ids)
            for doc_id, doc_title_ids in enumerate(title_ids):
                matched = qset.intersection(doc_title_ids)
                if matched:
                    scores[doc_id] = scores.get(doc_id, 0.0) + title_boost * len(matched)

        ranked = heapq.nlargest(top_k, scores.items(), key=lambda item: item[1])
        return [doc_id for doc_id, score in ranked[:top_k] if score > 0]


def write_binary_postings(
    path: Path,
    documents: list[dict],
    postings: dict[int, list[tuple[int, int]]],
    avg_doc_length: float,
) -> None:
    terms = sorted(postings)
    term_header_size = 16
    header_size = 28
    doc_table_size = len(documents) * 4
    term_table_size = len(terms) * term_header_size
    postings_offset = header_size + doc_table_size + term_table_size

    term_rows = []
    body = bytearray()
    for token_id in terms:
        rows = sorted(postings[token_id])
        offset = postings_offset + len(body)
        term_rows.append((token_id, len(rows), offset))
        for doc_id, tf in rows:
            body.extend(struct.pack("<II", doc_id, tf))

    with path.open("wb") as f:
        f.write(BINARY_INDEX_MAGIC)
        f.write(struct.pack("<IIII", BINARY_INDEX_VERSION, len(documents), len(terms), 0))
        f.write(struct.pack("<d", avg_doc_length))
        for doc in documents:
            f.write(struct.pack("<I", doc["token_count"]))
        for token_id, doc_freq, offset in term_rows:
            f.write(struct.pack("<IIQ", token_id, doc_freq, offset))
        f.write(body)


def write_binary_postings_v2(
    path: Path,
    documents: list[dict],
    postings: dict[int, list[tuple[int, int]]],
    avg_doc_length: float,
) -> None:
    terms = sorted(postings)
    term_header_size = 24
    header_size = 28
    doc_table_size = len(documents) * 4
    term_table_size = len(terms) * term_header_size
    postings_offset = header_size + doc_table_size + term_table_size

    term_rows = []
    body = bytearray()
    for token_id in terms:
        rows = sorted(postings[token_id], key=lambda item: item[0])
        offset = postings_offset + len(body)
        body_start = len(body)
        previous_doc_id = 0
        for doc_id, tf in rows:
            if doc_id < previous_doc_id:
                raise ValueError(f"Postings for token {token_id} are not sorted by doc id")
            write_uvarint(doc_id - previous_doc_id, body)
            write_uvarint(tf, body)
            previous_doc_id = doc_id
        term_rows.append((token_id, len(rows), offset, len(body) - body_start))

    with path.open("wb") as f:
        f.write(BINARY_INDEX_MAGIC_V2)
        f.write(struct.pack("<IIII", BINARY_INDEX_VERSION_V2, len(documents), len(terms), 0))
        f.write(struct.pack("<d", avg_doc_length))
        for doc in documents:
            f.write(struct.pack("<I", doc["token_count"]))
        for token_id, doc_freq, offset, byte_length in term_rows:
            f.write(struct.pack("<IIQII", token_id, doc_freq, offset, byte_length, 0))
        f.write(body)


def load_binary_postings_v1(
    path: Path,
    documents: list[dict],
    raw: bytes | None = None,
) -> BinarySpectrumBM25:
    if raw is None:
        raw = path.read_bytes()
    if raw[:4] != BINARY_INDEX_MAGIC:
        raise ValueError(f"Not a Spectrum binary postings index: {path}")
    version, total_docs, total_terms, _reserved = struct.unpack_from("<IIII", raw, 4)
    if version != BINARY_INDEX_VERSION:
        raise ValueError(f"Unsupported Spectrum binary index version: {version}")
    avg_doc_length, = struct.unpack_from("<d", raw, 20)
    if total_docs != len(documents):
        raise ValueError(
            f"Binary index doc count mismatch: {total_docs} != {len(documents)}"
        )

    offset = 28 + total_docs * 4
    expected_new_postings_offset = 28 + total_docs * 4 + total_terms * 16
    first_postings_offset = None
    if total_terms:
        first_postings_offset = struct.unpack_from("<Q", raw, offset + 8)[0]
    legacy_postings_offset = first_postings_offset == expected_new_postings_offset - 4
    postings: dict[int, list[tuple[int, int]]] = {}
    for _ in range(total_terms):
        token_id, doc_freq, postings_pos = struct.unpack_from("<IIQ", raw, offset)
        offset += 16
        rows = []
        if legacy_postings_offset:
            # Compatibility for indexes written before the header-size constant
            # matched the actual 28-byte header.
            postings_pos += 4
        for i in range(doc_freq):
            doc_id, tf = struct.unpack_from("<II", raw, postings_pos + i * 8)
            rows.append((doc_id, tf))
        postings[token_id] = rows

    return BinarySpectrumBM25(documents, postings, avg_doc_length)


def load_binary_postings_v2(
    path: Path,
    documents: list[dict],
    raw: bytes | None = None,
) -> BinarySpectrumBM25:
    if raw is None:
        raw = path.read_bytes()
    if raw[:4] != BINARY_INDEX_MAGIC_V2:
        raise ValueError(f"Not a Spectrum SPB2 binary postings index: {path}")
    version, total_docs, total_terms, _flags = struct.unpack_from("<IIII", raw, 4)
    if version != BINARY_INDEX_VERSION_V2:
        raise ValueError(f"Unsupported Spectrum binary index version: {version}")
    avg_doc_length, = struct.unpack_from("<d", raw, 20)
    if total_docs != len(documents):
        raise ValueError(
            f"Binary index doc count mismatch: {total_docs} != {len(documents)}"
        )

    offset = 28 + total_docs * 4
    postings: dict[int, list[tuple[int, int]]] = {}
    for _ in range(total_terms):
        token_id, doc_freq, postings_pos, byte_length, _reserved = struct.unpack_from("<IIQII", raw, offset)
        offset += 24
        end = postings_pos + byte_length
        if end > len(raw):
            raise ValueError(f"SPB2 postings list for token {token_id} extends past EOF")
        rows = []
        doc_id = 0
        pos = postings_pos
        for _i in range(doc_freq):
            doc_gap, pos = read_uvarint(raw, pos)
            tf, pos = read_uvarint(raw, pos)
            doc_id += doc_gap
            rows.append((doc_id, tf))
        if pos != end:
            raise ValueError(f"SPB2 postings list for token {token_id} has trailing bytes")
        postings[token_id] = rows

    return BinarySpectrumBM25(documents, postings, avg_doc_length)


def load_binary_postings(path: Path, documents: list[dict]) -> BinarySpectrumBM25:
    raw = path.read_bytes()
    magic = raw[:4]
    if magic == BINARY_INDEX_MAGIC:
        return load_binary_postings_v1(path, documents, raw)
    if magic == BINARY_INDEX_MAGIC_V2:
        return load_binary_postings_v2(path, documents, raw)
    raise ValueError(f"Not a Spectrum binary postings index: {path}")


def preferred_binary_postings_path(store_dir: Path) -> Path:
    v2_path = store_dir / "postings_v2.bin"
    if v2_path.exists():
        return v2_path
    return store_dir / "postings.bin"


def binary_postings_format(path: Path) -> str:
    raw = path.read_bytes()[:4]
    if raw == BINARY_INDEX_MAGIC_V2:
        return "SPB2"
    if raw == BINARY_INDEX_MAGIC:
        return "SPB1"
    return "unknown"


def build_spectrum_store(
    chunks: list[Chunk],
    out_dir: Path,
    verify_fidelity: bool = True,
    k1: float = 1.5,
    b: float = 0.75,
    retrieval_normalization: bool = False,
    postings_format: str = "v1",
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
        data, dict_ids = encode_text_to_spec_bytes(
            chunk.text,
            retrieval_normalization=retrieval_normalization,
        )
        spec_path = chunk_dir / f"chunk_{chunk.id:06d}.spec"
        spec_path.write_bytes(data)

        if verify_fidelity:
            decoded = decode_spec_bytes(data)
            if decoded != chunk.text:
                fidelity_failures.append(chunk.id)

        freq = Counter(dict_ids)
        total_tokens += len(dict_ids)
        documents.append({
            "id": chunk.id,
            "path": rel_path(spec_path, out_dir),
            "name": f"chunk_{chunk.id:06d}",
            "title": chunk.title,
            "page_index": chunk.page_index,
            "chunk_index": chunk.chunk_index,
            "language_id": LANGUAGE_TEXT,
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
    docs_meta = {
        "format": "spectrum-rag-binary-postings-docs-v1",
        "total_docs": len(documents),
        "avg_doc_length": round(avg_doc_length, 2),
        "dict_version": D.DICT_VERSION,
        "documents": documents,
    }
    (out_dir / "docs.json").write_text(
        json.dumps(docs_meta, ensure_ascii=False, separators=(",", ":")),
        encoding="utf-8",
    )
    meta = {
        "format": "spectrum-rag-store-v1",
        "index_format": "spectrum-rag-binary-postings-" + postings_format,
        "binary_index_formats": written_index_formats,
        "chunks": len(chunks),
        "dict_version": D.DICT_VERSION,
        "retrieval_normalization": retrieval_normalization,
        "fidelity_verified": verify_fidelity,
        "fidelity_failures": fidelity_failures,
        "lossless_ok": not fidelity_failures if verify_fidelity else None,
        "build_seconds": round(time.perf_counter() - started, 4),
        "build_cpu_seconds": round(time.process_time() - cpu_started, 4),
    }
    (out_dir / "meta.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")
    return meta, documents, BinarySpectrumBM25(documents, postings, avg_doc_length, k1=k1, b=b)


def make_queries(chunks: list[Chunk], count: int) -> list[dict]:
    title_to_ids: dict[str, set[int]] = {}
    for chunk in chunks:
        title_to_ids.setdefault(chunk.title, set()).add(chunk.id)

    if not chunks:
        return []
    step = max(1, len(chunks) // count)
    queries = []
    seen_titles = set()
    stride_indices = list(range(0, len(chunks), step))
    stride_index_set = set(stride_indices)
    remaining_indices = [idx for idx in range(len(chunks)) if idx not in stride_index_set]
    for idx in stride_indices + remaining_indices:
        chunk = chunks[idx]
        if len(queries) >= count:
            break
        if chunk.title in seen_titles:
            continue
        seen_titles.add(chunk.title)
        words = WORD_RE.findall(chunk.text)
        preview = " ".join(words[:10])
        query = f"{chunk.title} {preview}".strip()
        queries.append({
            "query": query,
            "title": chunk.title,
            "relevant_ids": sorted(title_to_ids[chunk.title]),
        })
    return queries


def conventional_search(vectorizer, matrix, query: str, top_k: int) -> list[int]:
    q = vectorizer.transform([query])
    scores = (matrix @ q.T).toarray().ravel()
    if not np.any(scores):
        return []
    order = np.argsort(-scores)[:top_k]
    return [int(idx) for idx in order if scores[idx] > 0]


def title_token_sets(
    documents: list[dict],
    retrieval_normalization: bool = False,
) -> list[set[int]]:
    return [
        set(encode_query(doc.get("title", ""), lang="txt", normalize=retrieval_normalization))
        for doc in documents
    ]


def spectrum_search(
    bm25: BinarySpectrumBM25,
    query: str,
    top_k: int,
    max_df_ratio: float | None = None,
    unique_query_terms: bool = False,
    title_ids: list[set[int]] | None = None,
    title_boost: float = 0.0,
    retrieval_normalization: bool = False,
) -> list[int]:
    query_ids = encode_query(query, lang="txt", normalize=retrieval_normalization)
    return bm25.search(
        query_ids,
        top_k,
        max_df_ratio=max_df_ratio,
        unique_query_terms=unique_query_terms,
        title_ids=title_ids,
        title_boost=title_boost,
    )


def evaluate_retrieval(
    queries: list[dict],
    conventional,
    spectrum,
    top_k: int,
    spectrum_max_df_ratio: float | None = None,
    spectrum_unique_query_terms: bool = False,
    spectrum_title_boost: float = 0.0,
    retrieval_normalization: bool = False,
) -> dict:
    vectorizer, matrix = conventional
    spectrum_base_dir, documents, bm25 = spectrum
    spectrum_title_ids = (
        title_token_sets(documents, retrieval_normalization)
        if spectrum_title_boost else None
    )

    metrics = {
        "conventional": {
            "hit1": 0,
            "recallk": 0,
            "rr": [],
            "latencies_ms": [],
            "cpu_ms": [],
        },
        "spectrum": {
            "hit1": 0,
            "recallk": 0,
            "rr": [],
            "latencies_ms": [],
            "cpu_ms": [],
            "decode_ms": [],
            "decode_cpu_ms": [],
            "decode_input_bytes": [],
        },
    }

    for item in queries:
        relevant = set(item["relevant_ids"])

        started = time.perf_counter()
        cpu_started = time.process_time()
        conv_ids = conventional_search(vectorizer, matrix, item["query"], top_k)
        metrics["conventional"]["latencies_ms"].append((time.perf_counter() - started) * 1000)
        metrics["conventional"]["cpu_ms"].append((time.process_time() - cpu_started) * 1000)

        started = time.perf_counter()
        cpu_started = time.process_time()
        spec_ids = spectrum_search(
            bm25,
            item["query"],
            top_k,
            max_df_ratio=spectrum_max_df_ratio,
            unique_query_terms=spectrum_unique_query_terms,
            title_ids=spectrum_title_ids,
            title_boost=spectrum_title_boost,
            retrieval_normalization=retrieval_normalization,
        )
        metrics["spectrum"]["latencies_ms"].append((time.perf_counter() - started) * 1000)
        metrics["spectrum"]["cpu_ms"].append((time.process_time() - cpu_started) * 1000)

        if spec_ids:
            spec_path = spectrum_base_dir / documents[spec_ids[0]]["path"]
            decode_started = time.perf_counter()
            decode_cpu_started = time.process_time()
            spec_data = spec_path.read_bytes()
            _ = decode_spec_bytes(spec_data)
            metrics["spectrum"]["decode_ms"].append((time.perf_counter() - decode_started) * 1000)
            metrics["spectrum"]["decode_cpu_ms"].append((time.process_time() - decode_cpu_started) * 1000)
            metrics["spectrum"]["decode_input_bytes"].append(len(spec_data))

        for name, ids in (("conventional", conv_ids), ("spectrum", spec_ids)):
            if ids and ids[0] in relevant:
                metrics[name]["hit1"] += 1
            if relevant.intersection(ids):
                metrics[name]["recallk"] += 1
            rank = next((i + 1 for i, doc_id in enumerate(ids) if doc_id in relevant), None)
            metrics[name]["rr"].append(1 / rank if rank else 0.0)

    total = max(1, len(queries))
    summary = {}
    for name, values in metrics.items():
        summary[name] = {
            "hit_at_1": round(values["hit1"] / total, 4),
            f"recall_at_{top_k}": round(values["recallk"] / total, 4),
            "mrr": round(mean(values["rr"]) if values["rr"] else 0.0, 4),
            "avg_query_ms": round(mean(values["latencies_ms"]) if values["latencies_ms"] else 0.0, 4),
            "avg_query_cpu_ms": round(mean(values["cpu_ms"]) if values["cpu_ms"] else 0.0, 4),
        }
        if name == "spectrum":
            summary[name]["avg_decode_ms"] = round(
                mean(values["decode_ms"]) if values["decode_ms"] else 0.0,
                4,
            )
            summary[name]["avg_decode_cpu_ms"] = round(
                mean(values["decode_cpu_ms"]) if values["decode_cpu_ms"] else 0.0,
                4,
            )
            summary[name]["avg_decode_input_bytes"] = round(
                mean(values["decode_input_bytes"]) if values["decode_input_bytes"] else 0.0,
                1,
            )
    return summary


def write_report(out_dir: Path, report: dict) -> None:
    md = out_dir / "report.md"
    c = report["stores"]["conventional"]
    s = report["stores"]["spectrum"]
    fidelity_failures = s["fidelity_failures"]
    fidelity_failures_text = "not checked" if fidelity_failures is None else f"{fidelity_failures:,}"
    lines = [
        "# Spectrum RAG Storage Benchmark",
        "",
    "This benchmark compares a conventional local RAG store against a Spectrum `.spec` token store with a compact binary postings/frequency index on the same chunks.",
        "",
        "## Corpus",
        "",
        f"- Pages: {report['corpus']['pages']:,}",
        f"- Chunks: {report['corpus']['chunks']:,}",
        f"- Raw chunk bytes: {report['corpus']['raw_bytes']:,}",
        f"- Spectrum BM25: k1={report['settings']['spectrum_k1']}, b={report['settings']['spectrum_b']}, max_df_ratio={report['settings']['spectrum_max_df_ratio']}, title_boost={report['settings']['spectrum_title_boost']}",
        f"- Retrieval normalization: `{report['settings']['retrieval_normalization']}`",
        f"- Spectrum fidelity verification skipped: `{report['settings']['skip_verify']}`",
        "",
        "## Storage",
        "",
        "| Store | Bytes | Ratio vs raw chunks | Build wall sec | Build CPU sec | MiB/CPU sec |",
        "|---|---:|---:|---:|---:|---:|",
        f"| Conventional raw+TF-IDF | {c['bytes']:,} | {c['ratio_vs_raw']:.3f}x | {c['build_seconds']:.3f} | {c['build_cpu_seconds']:.3f} | {c['build_mib_per_cpu_second']:.3f} |",
        f"| Spectrum `.spec`+binary BM25 | {s['bytes']:,} | {s['ratio_vs_raw']:.3f}x | {s['build_seconds']:.3f} | {s['build_cpu_seconds']:.3f} | {s['build_mib_per_cpu_second']:.3f} |",
        "",
        "## Storage Components",
        "",
        "| Store | Payload bytes | Index/vector bytes | Metadata bytes |",
        "|---|---:|---:|---:|",
        f"| Conventional raw+TF-IDF | {c['components']['payload_bytes']:,} | {c['components']['index_bytes']:,} | {c['components']['metadata_bytes']:,} |",
        f"| Spectrum `.spec`+binary BM25 | {s['components']['payload_bytes']:,} | {s['components']['index_bytes']:,} | {s['components']['metadata_bytes']:,} |",
        "",
        "## Retrieval",
        "",
        "| Store | Hit@1 | MRR | Recall@k | Avg query wall ms | Avg query CPU ms | Avg decode wall ms | Avg decode CPU ms | Avg decode input bytes |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    top_k = report["settings"]["top_k"]
    for name, label in (("conventional", "Conventional raw+TF-IDF"), ("spectrum", "Spectrum `.spec`+binary BM25")):
        row = report["retrieval"][name]
        lines.append(
            f"| {label} | {row['hit_at_1']:.3f} | {row['mrr']:.3f} | "
            f"{row[f'recall_at_{top_k}']:.3f} | {row['avg_query_ms']:.3f} | "
            f"{row.get('avg_query_cpu_ms', 0.0):.3f} | "
            f"{row.get('avg_decode_ms', 0.0):.3f} | "
            f"{row.get('avg_decode_cpu_ms', 0.0):.3f} | "
            f"{row.get('avg_decode_input_bytes', 0.0):,.1f} |"
        )
    lines.extend([
        "",
        "## Fidelity",
        "",
        f"- Spectrum verification run: `{s['fidelity_verified']}`",
        f"- Spectrum lossless round-trip: `{s['lossless_ok']}`",
        f"- Fidelity failures: {fidelity_failures_text}",
        "",
        "The conventional baseline is a portable local RAG proxy: raw text chunk store plus persisted TF-IDF vectors. The Spectrum store keeps chunk text only as `.spec` payloads and stores token postings/frequencies in `postings.bin`. Chroma/FAISS/neural embeddings can be added as an additional baseline later.",
    ])
    md.write_text("\n".join(lines) + "\n", encoding="utf-8")


def append_benchmark_log(log_path: Path, report: dict, change_note: str) -> None:
    """Append a compact, comparable benchmark entry."""
    log_path.parent.mkdir(parents=True, exist_ok=True)
    if not log_path.exists():
        log_path.write_text(
            "# Spectrum Benchmark Log\n\n"
            "Cumulative benchmark history. Each entry records what changed "
            "between runs so storage, speed, and ranking movement has context.\n\n",
            encoding="utf-8",
        )

    settings = report["settings"]
    corpus = report["corpus"]
    c = report["stores"]["conventional"]
    s = report["stores"]["spectrum"]
    fidelity_failures = s["fidelity_failures"]
    fidelity_failures_text = "not checked" if fidelity_failures is None else f"{fidelity_failures:,}"
    cr = report["retrieval"]["conventional"]
    sr = report["retrieval"]["spectrum"]
    top_k = settings["top_k"]
    timestamp = datetime.now(timezone.utc).isoformat(timespec="seconds")

    entry = [
        f"## {timestamp}",
        "",
        f"**Change note:** {change_note.strip() or 'No change note supplied.'}",
        "",
        f"**Run:** `{settings['page_index']}`, pages={corpus['pages']:,}, "
        f"chunks={corpus['chunks']:,}, raw={corpus['raw_bytes']:,} bytes, "
        f"chunk_chars={settings['chunk_chars']:,}, overlap={settings['overlap_chars']:,}, "
        f"queries={settings['queries']:,}, top_k={top_k}, "
        f"spectrum_k1={settings['spectrum_k1']}, spectrum_b={settings['spectrum_b']}, "
        f"spectrum_max_df_ratio={settings['spectrum_max_df_ratio']}, "
        f"spectrum_title_boost={settings['spectrum_title_boost']}, "
        f"retrieval_normalization={settings['retrieval_normalization']}, "
        f"skip_verify={settings['skip_verify']}",
        "",
        "| Metric | Conventional raw+TF-IDF | Spectrum `.spec`+binary BM25 |",
        "|---|---:|---:|",
        f"| Total store bytes | {c['bytes']:,} | {s['bytes']:,} |",
        f"| Ratio vs raw chunks | {c['ratio_vs_raw']:.3f}x | {s['ratio_vs_raw']:.3f}x |",
        f"| Payload bytes | {c['components']['payload_bytes']:,} | {s['components']['payload_bytes']:,} |",
        f"| Index/vector bytes | {c['components']['index_bytes']:,} | {s['components']['index_bytes']:,} |",
        f"| Build seconds | {c['build_seconds']:.3f} | {s['build_seconds']:.3f} |",
        f"| Build CPU seconds | {c['build_cpu_seconds']:.3f} | {s['build_cpu_seconds']:.3f} |",
        f"| Build MiB/CPU second | {c['build_mib_per_cpu_second']:.3f} | {s['build_mib_per_cpu_second']:.3f} |",
        f"| Hit@1 | {cr['hit_at_1']:.3f} | {sr['hit_at_1']:.3f} |",
        f"| MRR | {cr['mrr']:.3f} | {sr['mrr']:.3f} |",
        f"| Recall@{top_k} | {cr[f'recall_at_{top_k}']:.3f} | {sr[f'recall_at_{top_k}']:.3f} |",
        f"| Avg query ms | {cr['avg_query_ms']:.3f} | {sr['avg_query_ms']:.3f} |",
        f"| Avg query CPU ms | {cr.get('avg_query_cpu_ms', 0.0):.3f} | {sr.get('avg_query_cpu_ms', 0.0):.3f} |",
        f"| Avg decode ms | 0.000 | {sr.get('avg_decode_ms', 0.0):.3f} |",
        f"| Avg decode CPU ms | 0.000 | {sr.get('avg_decode_cpu_ms', 0.0):.3f} |",
        f"| Avg decode input bytes | 0 | {sr.get('avg_decode_input_bytes', 0.0):,.1f} |",
        f"| Spectrum fidelity verified | n/a | {s['fidelity_verified']} |",
        f"| Spectrum lossless | n/a | {s['lossless_ok']} |",
        f"| Fidelity failures | n/a | {fidelity_failures_text} |",
        "",
    ]
    with open(log_path, "a", encoding="utf-8") as f:
        f.write("\n".join(entry) + "\n")


def run(args: argparse.Namespace) -> dict:
    out_dir = Path(args.out_dir)
    reset_dir(out_dir)

    page_index = Path(args.page_index)
    print(f"[storage-bench] extracting pages from {page_index}")
    pages = extract_wiki_pages(page_index, max_pages=args.max_pages)
    chunks = make_chunks(pages, args.chunk_chars, args.overlap_chars)
    raw_bytes = sum(len(chunk.text.encode("utf-8")) for chunk in chunks)
    print(f"[storage-bench] corpus: {len(pages):,} pages, {len(chunks):,} chunks, {raw_bytes:,} bytes")

    conventional_dir = out_dir / "conventional_tfidf"
    spectrum_dir = out_dir / "spectrum_spec"

    print("[storage-bench] building conventional raw+TF-IDF store")
    conventional_meta, vectorizer, matrix = build_conventional_store(chunks, conventional_dir)

    print("[storage-bench] building Spectrum .spec+binary BM25 store")
    spectrum_meta, spectrum_docs, spectrum_bm25 = build_spectrum_store(
        chunks,
        spectrum_dir,
        verify_fidelity=not args.skip_verify,
        k1=args.spectrum_k1,
        b=args.spectrum_b,
        retrieval_normalization=args.retrieval_normalization,
        postings_format=args.postings_format,
    )

    queries = make_queries(chunks, args.queries)
    (out_dir / "queries.json").write_text(json.dumps(queries, indent=2), encoding="utf-8")
    print(f"[storage-bench] evaluating {len(queries):,} queries")
    retrieval = evaluate_retrieval(
        queries,
        conventional=(vectorizer, matrix),
        spectrum=(spectrum_dir, spectrum_docs, spectrum_bm25),
        top_k=args.top_k,
        spectrum_max_df_ratio=args.spectrum_max_df_ratio,
        spectrum_unique_query_terms=args.spectrum_unique_query_terms,
        spectrum_title_boost=args.spectrum_title_boost,
        retrieval_normalization=args.retrieval_normalization,
    )

    conventional_bytes = dir_size(conventional_dir)
    spectrum_bytes = dir_size(spectrum_dir)
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
        "format": "spectrum-rag-storage-benchmark-v1",
        "settings": {
            "page_index": str(page_index),
            "max_pages": args.max_pages,
            "chunk_chars": args.chunk_chars,
            "overlap_chars": args.overlap_chars,
            "queries": len(queries),
            "top_k": args.top_k,
            "skip_verify": args.skip_verify,
            "spectrum_k1": args.spectrum_k1,
            "spectrum_b": args.spectrum_b,
            "spectrum_max_df_ratio": args.spectrum_max_df_ratio,
            "spectrum_unique_query_terms": args.spectrum_unique_query_terms,
            "spectrum_title_boost": args.spectrum_title_boost,
            "retrieval_normalization": args.retrieval_normalization,
            "postings_format": args.postings_format,
        },
        "corpus": {
            "pages": len(pages),
            "chunks": len(chunks),
            "raw_bytes": raw_bytes,
        },
        "stores": {
            "conventional": {
                "bytes": conventional_bytes,
                "ratio_vs_raw": conventional_bytes / raw_bytes if raw_bytes else math.nan,
                "build_seconds": conventional_meta["build_seconds"],
                "build_cpu_seconds": conventional_meta["build_cpu_seconds"],
                "build_mib_per_wall_second": (
                    (raw_bytes / (1024 * 1024)) / conventional_meta["build_seconds"]
                    if raw_bytes and conventional_meta["build_seconds"] else math.nan
                ),
                "build_mib_per_cpu_second": (
                    (raw_bytes / (1024 * 1024)) / conventional_meta["build_cpu_seconds"]
                    if raw_bytes and conventional_meta["build_cpu_seconds"] else math.nan
                ),
                "components": conventional_components,
            },
            "spectrum": {
                "bytes": spectrum_bytes,
                "ratio_vs_raw": spectrum_bytes / raw_bytes if raw_bytes else math.nan,
                "build_seconds": spectrum_meta["build_seconds"],
                "build_cpu_seconds": spectrum_meta["build_cpu_seconds"],
                "build_mib_per_wall_second": (
                    (raw_bytes / (1024 * 1024)) / spectrum_meta["build_seconds"]
                    if raw_bytes and spectrum_meta["build_seconds"] else math.nan
                ),
                "build_mib_per_cpu_second": (
                    (raw_bytes / (1024 * 1024)) / spectrum_meta["build_cpu_seconds"]
                    if raw_bytes and spectrum_meta["build_cpu_seconds"] else math.nan
                ),
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
    if args.append_log:
        append_benchmark_log(Path(args.benchmark_log), report, args.change_note)
        print(f"[storage-bench] appended {args.benchmark_log}")
    print(f"[storage-bench] wrote {out_dir / 'report.md'}")
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description="Benchmark conventional RAG storage vs Spectrum RAG storage.")
    parser.add_argument(
        "--page-index",
        default="wiki_enwiki_fullxml_sample/page_index.json",
        help="Spectrum Wiki page_index.json to use as the source corpus.",
    )
    parser.add_argument("--out-dir", default="benchmarks/generated/storage_benchmark", help="Output benchmark directory.")
    parser.add_argument("--max-pages", type=int, default=200, help="Maximum wiki pages to extract.")
    parser.add_argument("--chunk-chars", type=int, default=1800, help="Characters per RAG chunk.")
    parser.add_argument("--overlap-chars", type=int, default=180, help="Character overlap between chunks.")
    parser.add_argument("--queries", type=int, default=50, help="Number of generated title/content queries.")
    parser.add_argument("--top-k", type=int, default=5, help="Recall@k and search result count.")
    parser.add_argument(
        "--skip-verify",
        action="store_true",
        help="Skip decode-after-encode fidelity verification during Spectrum store build.",
    )
    parser.add_argument("--spectrum-k1", type=float, default=1.5, help="Spectrum BM25 k1 parameter.")
    parser.add_argument("--spectrum-b", type=float, default=0.75, help="Spectrum BM25 b parameter.")
    parser.add_argument(
        "--spectrum-max-df-ratio",
        type=float,
        default=None,
        help="Optional Spectrum query-time document-frequency filter, e.g. 0.9.",
    )
    parser.add_argument(
        "--spectrum-unique-query-terms",
        action="store_true",
        help="Score each Spectrum query token at most once.",
    )
    parser.add_argument(
        "--spectrum-title-boost",
        type=float,
        default=0.0,
        help="Add this score per matching query token in the document title.",
    )
    parser.add_argument(
        "--retrieval-normalization",
        action="store_true",
        help="Add retrieval-only normalized aliases for text queries and document indexes.",
    )
    parser.add_argument(
        "--postings-format",
        choices=["v1", "v2", "both"],
        default="v1",
        help="Binary postings format to write for the Spectrum store.",
    )
    parser.add_argument(
        "--append-log",
        action="store_true",
        help="Append this run to the cumulative benchmark log.",
    )
    parser.add_argument(
        "--benchmark-log",
        default="BENCHMARK_LOG.md",
        help="Path to the cumulative benchmark log.",
    )
    parser.add_argument(
        "--change-note",
        default="",
        help="Short note describing what changed since the previous benchmark.",
    )
    args = parser.parse_args()
    run(args)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
