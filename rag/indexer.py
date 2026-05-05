"""
Spectrum RAG — Indexer
======================
Reads .spec files and builds a retrieval index without ever decoding back to
source text.  Only dictionary token IDs are indexed — ASCII/Unicode fallback
characters are filtered out because they carry no structural meaning for
retrieval purposes.

Logical index layout (saved as compact binary by default, JSON-compatible):
  {
    "meta": {
      "total_docs":      N,
      "avg_doc_length":  float,   # mean dict-token count per doc
      "built_at":        ISO timestamp
    },
    "documents": [
      {
        "id":           int,
        "path":         str,      # path to the .spec file
        "name":         str,      # filename stem
        "language_id":  int,      # 0=Py 1=HTML 2=JS 3=CSS 4=Text
        "orig_length":  int,      # original source bytes
        "token_count":  int,      # number of dict tokens in this doc
        "freq":         [[id, count], ...]  # sparse frequency vector
      },
      ...
    ],
    "inverted": {
      "<token_id>": [doc_id, ...]   # which docs contain this token
    }
  }
"""

import sys
import json
import struct
import zlib
from collections import Counter
from pathlib import Path
from datetime import datetime, timezone

# ── project root on path ───────────────────────────────────────────────────
_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_ROOT))
import dictionary as D
from rag.normalization import retrieval_token_ids

# ── constants (must match spec_encoder / spec_decoder) ─────────────────────
MAGIC       = b'SPEC'
HEADER_SIZE = 16
FLAG_RLE    = 0b0000_0001

INDEX_MAGIC = b"SRB1"
INDEX_VERSION = 2
RETRIEVAL_PROFILE = "universal_v1"

LANG_NAMES = {0: "Python", 1: "HTML", 2: "JS", 3: "CSS", 4: "Text"}


def is_meaningful_retrieval_id(token_id: int) -> bool:
    token = D.SPEC_ID_TO_TOKEN.get(token_id, "")
    if not token or token.startswith("CTRL:"):
        return False
    if token.isspace():
        return False
    return any(ch.isalnum() for ch in token)


# ─────────────────────────────────────────────────────────────────────────────
# Low-level: read token IDs from a .spec file
# ─────────────────────────────────────────────────────────────────────────────

def extract_token_ids(spec_path: str | Path) -> tuple[dict, list[int]]:
    """
    Parse a .spec file and return (metadata, dict_token_ids).

    dict_token_ids contains ONLY dictionary token IDs (IDs < SPEC_ID_ASCII_BASE).
    ASCII fallbacks, Unicode fallbacks, and RLE markers are consumed/skipped so
    that the returned list reflects a clean token frequency distribution.

    Returns
    -------
    meta : dict
        Header fields: dict_version, orig_length, language_id, rle_enabled.
    dict_token_ids : list[int]
        Flat stream of dictionary token IDs after RLE expansion.
    """
    raw = Path(spec_path).read_bytes()
    if raw[:4] != MAGIC:
        raise ValueError(f"Not a .spec file: {spec_path}")

    dict_version, = struct.unpack_from(">H", raw, 4)
    flags,         = struct.unpack_from(">H", raw, 6)
    orig_length,   = struct.unpack_from(">I", raw, 8)
    language_id,   = struct.unpack_from(">H", raw, 12)
    rle_enabled    = bool(flags & FLAG_RLE)

    meta = {
        "dict_version": dict_version,
        "orig_length":  orig_length,
        "language_id":  language_id,
        "rle_enabled":  rle_enabled,
    }

    # Decompress body
    body       = raw[HEADER_SIZE:]
    raw_stream = zlib.decompress(body)

    # Unpack uint32 LE stream
    count = len(raw_stream) // 4
    ids   = list(struct.unpack(f"<{count}I", raw_stream[:count * 4]))

    ascii_base    = D.SPEC_ID_ASCII_BASE
    rle_marker    = D.SPEC_ID_RLE
    unicode_marker = D.SPEC_ID_UNICODE

    # Expand RLE; keep only dictionary tokens
    dict_ids: list[int] = []
    last_dict_id: int | None = None
    fallback_chars: list[str] = []

    def flush_fallback_chars() -> None:
        if not fallback_chars:
            return
        text = "".join(fallback_chars)
        fallback_chars.clear()
        if any(ch.isalpha() for ch in text):
            dict_ids.extend(
                token_id for token_id in retrieval_token_ids(text)
                if is_meaningful_retrieval_id(token_id)
            )
    i = 0
    n = len(ids)

    while i < n:
        val = ids[i]

        if val == rle_marker:
            # Next uint32 = repeat count for the previous token
            if i + 1 < n and last_dict_id is not None:
                repeat = ids[i + 1]
                dict_ids.extend([last_dict_id] * repeat)
            i += 2
            continue

        if val == unicode_marker:
            # Next uint32 = Unicode code point — skip for indexing
            if i + 1 < n:
                fallback_chars.append(chr(ids[i + 1]))
            i += 2
            last_dict_id = None
            continue

        if val >= ascii_base:
            # ASCII fallback character — skip for indexing
            cp = val - ascii_base
            if 0 <= cp <= 127:
                fallback_chars.append(chr(cp))
            last_dict_id = None
            i += 1
            continue

        # Dictionary token — keep meaningful retrieval terms only
        flush_fallback_chars()
        if is_meaningful_retrieval_id(val):
            dict_ids.append(val)
        last_dict_id = val
        i += 1

    flush_fallback_chars()
    return meta, dict_ids


# ─────────────────────────────────────────────────────────────────────────────
# Index builder
# ─────────────────────────────────────────────────────────────────────────────

def build_index(spec_paths: list[str | Path]) -> dict:
    """
    Build a retrieval index from a list of .spec file paths.

    Returns the index as a plain dict (JSON-serialisable).
    """
    documents     = []
    inverted: dict[int, list[int]] = {}   # token_id → [doc_ids]
    total_tokens  = 0

    for doc_id, path in enumerate(spec_paths):
        path = Path(path)
        try:
            meta, ids = extract_token_ids(path)
        except Exception as e:
            print(f"[indexer] WARNING: skipping {path.name} — {e}")
            continue

        path_alias_text = " ".join([path.stem, *path.parts])
        ids.extend(
            token_id for token_id in retrieval_token_ids(path_alias_text)
            if is_meaningful_retrieval_id(token_id)
        )

        freq = Counter(ids)
        token_count = len(ids)
        total_tokens += token_count

        doc = {
            "id":          doc_id,
            "path":        str(path),
            "name":        path.stem,
            "language_id": meta["language_id"],
            "orig_length": meta["orig_length"],
            "token_count": token_count,
            "freq":        [[tid, cnt] for tid, cnt in freq.items()],
        }
        documents.append(doc)
        print(f"[indexer] Indexed {path.name:<35}  "
              f"lang={LANG_NAMES.get(meta['language_id'], '?'):<6}  "
              f"dict_tokens={token_count:>8,}  "
              f"unique={len(freq):>6,}")

        # Update inverted index
        for tid in freq:
            inverted.setdefault(tid, []).append(doc_id)

    avg_doc_length = total_tokens / len(documents) if documents else 0.0

    index = {
        "meta": {
            "total_docs":     len(documents),
            "avg_doc_length": round(avg_doc_length, 2),
            "built_at":       datetime.now(timezone.utc).isoformat(),
            "retrieval_profile": RETRIEVAL_PROFILE,
        },
        "documents": documents,
        "inverted":  {str(tid): doc_ids for tid, doc_ids in inverted.items()},
    }

    print(f"\n[indexer] Built index: {len(documents)} docs, "
          f"{len(inverted):,} unique tokens, "
          f"avg doc length {avg_doc_length:,.0f} tokens")

    return index


def index_directory(dir_path: str | Path,
                    pattern: str = "**/*.spec") -> dict:
    """
    Walk a directory and index all .spec files matching `pattern`.
    """
    dir_path = Path(dir_path)
    paths    = sorted(dir_path.glob(pattern))
    if not paths:
        raise FileNotFoundError(
            f"No .spec files found in {dir_path} with pattern '{pattern}'")
    print(f"[indexer] Found {len(paths)} .spec files in {dir_path}\n")
    return build_index(paths)


# ─────────────────────────────────────────────────────────────────────────────
# Persistence
# ─────────────────────────────────────────────────────────────────────────────

def _save_index_json_legacy(index: dict, path: str | Path) -> None:
    """Save index to a JSON file."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(index, f, separators=(",", ":"))
    size_kb = path.stat().st_size / 1024
    print(f"[indexer] Saved index → {path}  ({size_kb:.1f} KB)")


def _load_index_json_legacy(path: str | Path) -> dict:
    """Load index from a JSON file."""
    with open(path, encoding="utf-8") as f:
        index = json.load(f)
    print(f"[indexer] Loaded index: {index['meta']['total_docs']} docs, "
          f"built {index['meta']['built_at']}")
    return index


def _build_inverted_from_documents(documents: list[dict]) -> dict[str, list[int]]:
    """Rebuild token -> doc ids from per-document frequency vectors."""
    inverted: dict[int, list[int]] = {}
    for doc in documents:
        doc_id = int(doc["id"])
        for tid, _ in doc["freq"]:
            inverted.setdefault(int(tid), []).append(doc_id)
    return {str(tid): doc_ids for tid, doc_ids in inverted.items()}


def _save_json_index(index: dict, path: Path) -> None:
    with open(path, "w", encoding="utf-8") as f:
        json.dump(index, f, separators=(",", ":"))


def _save_binary_index(index: dict, path: Path) -> None:
    """
    Save compact binary metadata and sparse frequency vectors.

    The inverted index is not stored because it duplicates the frequency data
    and is rebuilt when the index is loaded.
    """
    meta = index["meta"]
    documents = index["documents"]
    built_at = str(meta.get("built_at", "")).encode("utf-8")
    extra_meta = json.dumps(
        {
            key: value
            for key, value in meta.items()
            if key not in {"total_docs", "avg_doc_length", "built_at"}
        },
        separators=(",", ":"),
    ).encode("utf-8")

    with open(path, "wb") as f:
        f.write(INDEX_MAGIC)
        f.write(struct.pack(
            "<IIIdI",
            INDEX_VERSION,
            len(documents),
            sum(len(doc["freq"]) for doc in documents),
            float(meta.get("avg_doc_length", 0.0)),
            len(built_at),
        ))
        f.write(built_at)
        f.write(struct.pack("<I", len(extra_meta)))
        f.write(extra_meta)

        for doc in documents:
            path_bytes = str(doc["path"]).encode("utf-8")
            name_bytes = str(doc["name"]).encode("utf-8")
            freq = [(int(tid), int(count)) for tid, count in doc["freq"]]

            f.write(struct.pack(
                "<IIQQIII",
                int(doc["id"]),
                int(doc["language_id"]),
                int(doc["orig_length"]),
                int(doc["token_count"]),
                len(path_bytes),
                len(name_bytes),
                len(freq),
            ))
            f.write(path_bytes)
            f.write(name_bytes)
            for tid, count in freq:
                f.write(struct.pack("<II", tid, count))


def save_index(index: dict, path: str | Path) -> None:
    """Save index. Use .json for legacy JSON, otherwise compact binary."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.suffix.lower() == ".json":
        _save_json_index(index, path)
        index_format = "JSON"
    else:
        _save_binary_index(index, path)
        index_format = "binary"
    size_kb = path.stat().st_size / 1024
    print(f"[indexer] Saved {index_format} index -> {path}  ({size_kb:.1f} KB)")


def _load_json_index(path: Path) -> dict:
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def _load_binary_index(path: Path) -> dict:
    raw = path.read_bytes()
    if raw[:4] != INDEX_MAGIC:
        raise ValueError(f"Not a Spectrum binary RAG index: {path}")

    offset = 4
    version, total_docs, _total_freq_rows, avg_doc_length, built_at_len = struct.unpack_from(
        "<IIIdI", raw, offset
    )
    offset += struct.calcsize("<IIIdI")
    if version not in (1, 2):
        raise ValueError(f"Unsupported Spectrum binary RAG index version: {version}")

    built_at = raw[offset:offset + built_at_len].decode("utf-8")
    offset += built_at_len
    extra_meta = {}
    if version >= 2:
        extra_meta_len, = struct.unpack_from("<I", raw, offset)
        offset += 4
        if extra_meta_len:
            extra_meta = json.loads(raw[offset:offset + extra_meta_len].decode("utf-8"))
        offset += extra_meta_len

    documents = []
    doc_header = struct.Struct("<IIQQIII")
    freq_row = struct.Struct("<II")

    for _ in range(total_docs):
        (
            doc_id,
            language_id,
            orig_length,
            token_count,
            path_len,
            name_len,
            freq_count,
        ) = doc_header.unpack_from(raw, offset)
        offset += doc_header.size

        doc_path = raw[offset:offset + path_len].decode("utf-8")
        offset += path_len
        name = raw[offset:offset + name_len].decode("utf-8")
        offset += name_len

        freq = []
        for _ in range(freq_count):
            tid, count = freq_row.unpack_from(raw, offset)
            offset += freq_row.size
            freq.append([tid, count])

        documents.append({
            "id": doc_id,
            "path": doc_path,
            "name": name,
            "language_id": language_id,
            "orig_length": orig_length,
            "token_count": token_count,
            "freq": freq,
        })

    meta = {
        "total_docs": total_docs,
        "avg_doc_length": round(avg_doc_length, 2),
        "built_at": built_at,
    }
    meta.update(extra_meta)

    return {
        "meta": meta,
        "documents": documents,
        "inverted": _build_inverted_from_documents(documents),
    }


def load_index(path: str | Path) -> dict:
    """Load a JSON or compact binary index."""
    path = Path(path)
    with open(path, "rb") as f:
        magic = f.read(4)
    if magic == INDEX_MAGIC:
        index = _load_binary_index(path)
        index_format = "binary"
    else:
        index = _load_json_index(path)
        index.setdefault("inverted", _build_inverted_from_documents(index["documents"]))
        index_format = "JSON"
    print(f"[indexer] Loaded index: {index['meta']['total_docs']} docs, "
          f"built {index['meta']['built_at']} ({index_format})")
    return index


# ─────────────────────────────────────────────────────────────────────────────
# CLI
# ─────────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(
        description="Spectrum RAG Indexer — build an index from .spec files")
    parser.add_argument("dir", help="Directory containing .spec files")
    parser.add_argument("--out", default="rag/index.bin",
                        help="Output index path (default: rag/index.bin; use .json for legacy JSON)")
    parser.add_argument("--pattern", default="**/*.spec",
                        help="Glob pattern for .spec files (default: **/*.spec)")
    args = parser.parse_args()

    idx = index_directory(args.dir, args.pattern)
    save_index(idx, Path(_ROOT) / args.out)
