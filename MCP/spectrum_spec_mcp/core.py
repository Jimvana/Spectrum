"""Core Spectrum .spec readers used by the MCP server."""

from __future__ import annotations

import json
import os
import struct
import sys
import zipfile
import zlib
from dataclasses import dataclass
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

import dictionary as D  # noqa: E402
from spec_format._frozen import (  # noqa: E402
    MIN_SUPPORTED_VERSION,
    get_ascii_base_for_version,
    get_id_to_token_for_version,
)
from spec_format.spec_decoder import (  # noqa: E402
    HEADER_SIZE,
    LANGUAGE_TEXT,
    LANGUAGE_XML,
    SpecFormatError,
    ids_to_tokens,
    parse_header,
)
from tokenizers.text_tokenizer import reconstruct_text  # noqa: E402


LANGUAGE_NAMES = {
    0: "Python",
    1: "HTML",
    2: "JavaScript",
    3: "CSS",
    4: "Text",
    5: "TypeScript",
    6: "SQL",
    7: "Rust",
    8: "PHP",
    9: "XML/Wiki",
    10: "Java",
    11: "C",
    12: "C++",
    13: "Go",
    14: "C#",
    15: "Shell",
    16: "JSON",
    17: "YAML",
    18: "TOML",
}

PACK_INDEX_NAME = "spectrum_index.json"


@dataclass(frozen=True)
class DecodedSpec:
    text: str
    metadata: dict[str, Any]


def allowed_roots() -> list[Path]:
    configured = os.environ.get("SPECTRUM_SPEC_ROOTS", "")
    roots = [Path(item).expanduser() for item in configured.split(os.pathsep) if item.strip()]
    if not roots:
        roots = [REPO_ROOT]
    return [root.resolve() for root in roots]


def resolve_allowed_path(path: str | Path) -> Path:
    candidate = Path(path).expanduser()
    if not candidate.is_absolute():
        candidate = REPO_ROOT / candidate
    candidate = candidate.resolve()
    roots = allowed_roots()
    if not any(candidate == root or root in candidate.parents for root in roots):
        root_list = ", ".join(str(root) for root in roots)
        raise PermissionError(f"Path is outside allowed roots: {candidate}. Allowed roots: {root_list}")
    return candidate


def _tables_for_version(dict_version: int) -> tuple[dict[int, str], int, str]:
    if dict_version < MIN_SUPPORTED_VERSION:
        raise SpecFormatError(
            f"Dict version {dict_version} is below minimum supported version {MIN_SUPPORTED_VERSION}."
        )
    if dict_version == D.DICT_VERSION:
        return D.SPEC_ID_TO_TOKEN, D.SPEC_ID_ASCII_BASE, ""
    if dict_version < D.DICT_VERSION:
        return (
            get_id_to_token_for_version(dict_version),
            get_ascii_base_for_version(dict_version),
            f"decoded with frozen v{dict_version} dictionary",
        )
    return (
        D.SPEC_ID_TO_TOKEN,
        D.SPEC_ID_ASCII_BASE,
        f"file dictionary v{dict_version} is newer than local v{D.DICT_VERSION}",
    )


def inspect_spec_bytes(raw: bytes, source: str) -> dict[str, Any]:
    meta = parse_header(raw)
    original_bytes = meta["orig_length"]
    stored_bytes = len(raw)
    return {
        "source": source,
        "type": ".spec",
        "stored_bytes": stored_bytes,
        "dict_version": meta["dict_version"],
        "language_id": meta["language_id"],
        "language": LANGUAGE_NAMES.get(meta["language_id"], f"lang{meta['language_id']}"),
        "original_bytes": original_bytes,
        "rle_enabled": meta["rle_enabled"],
        "checksum": meta["checksum"],
        "compression_ratio": round(stored_bytes / original_bytes, 6) if original_bytes else 0,
    }


def decode_spec_bytes(raw: bytes, source: str = "<bytes>") -> DecodedSpec:
    meta = parse_header(raw)
    dict_version = meta["dict_version"]
    id_to_token, ascii_base, compatibility_note = _tables_for_version(dict_version)

    try:
        raw_stream = zlib.decompress(raw[HEADER_SIZE:])
    except zlib.error as exc:
        raise SpecFormatError(f"zlib decompression failed: {exc}") from exc

    count = len(raw_stream) // 4
    ids = list(struct.unpack(f"<{count}I", raw_stream[: count * 4]))
    tokens = ids_to_tokens(ids, id_to_token=id_to_token, ascii_base=ascii_base)

    if meta["language_id"] in (LANGUAGE_TEXT, LANGUAGE_XML):
        text = reconstruct_text(tokens)
    else:
        text = "".join(tokens)

    original_bytes = meta["orig_length"]
    text_bytes = text.encode("utf-8")
    if len(text_bytes) > original_bytes:
        text = text_bytes[:original_bytes].decode("utf-8", errors="replace")

    decoded_bytes = len(text.encode("utf-8"))
    actual_checksum = sum(text.encode("utf-8")) & 0xFFFF
    checksum_ok = actual_checksum == meta["checksum"]
    length_ok = decoded_bytes == original_bytes

    metadata = inspect_spec_bytes(raw, source)
    metadata.update(
        {
            "decoded_bytes": decoded_bytes,
            "token_count": len(tokens),
            "length_ok": length_ok,
            "checksum_ok": checksum_ok,
            "fidelity": "perfect" if length_ok and checksum_ok else "mismatch",
            "compatibility_note": compatibility_note,
        }
    )
    return DecodedSpec(text=text, metadata=metadata)


def inspect_spec(path: str) -> dict[str, Any]:
    spec_path = resolve_allowed_path(path)
    return inspect_spec_bytes(spec_path.read_bytes(), str(spec_path))


def read_spec(path: str, max_chars: int = 200_000) -> dict[str, Any]:
    spec_path = resolve_allowed_path(path)
    decoded = decode_spec_bytes(spec_path.read_bytes(), str(spec_path))
    text = decoded.text
    truncated = len(text) > max_chars
    return {
        "text": text[:max_chars],
        "truncated": truncated,
        "metadata": decoded.metadata,
    }


def list_spec_files(root: str | None = None, limit: int = 500) -> dict[str, Any]:
    search_root = resolve_allowed_path(root) if root else allowed_roots()[0]
    if not search_root.exists():
        raise FileNotFoundError(str(search_root))

    patterns = ["*.spec", "*.specpack"]
    files: list[Path] = []
    if search_root.is_file():
        files = [search_root] if search_root.suffix.lower() in {".spec", ".specpack"} else []
    else:
        for pattern in patterns:
            files.extend(search_root.rglob(pattern))

    files = sorted(path.resolve() for path in files)[:limit]
    return {
        "root": str(search_root),
        "count": len(files),
        "limit": limit,
        "files": [str(path) for path in files],
    }


def inspect_specpack(path: str) -> dict[str, Any]:
    pack_path = resolve_allowed_path(path)
    with zipfile.ZipFile(pack_path) as pack:
        manifest = json.loads(pack.read("manifest.json").decode("utf-8"))
        names = set(pack.namelist())
    entries = manifest.get("entries", [])
    return {
        "source": str(pack_path),
        "type": ".specpack",
        "format": manifest.get("format"),
        "version": manifest.get("version"),
        "dict_version": manifest.get("dict_version"),
        "source_root": manifest.get("source_root"),
        "file_count": len(entries),
        "original_bytes": sum(int(entry.get("original_size", 0)) for entry in entries),
        "spec_bytes": sum(int(entry.get("spec_size", 0)) for entry in entries),
        "pack_bytes": pack_path.stat().st_size,
        "has_index": PACK_INDEX_NAME in names,
        "entries": entries[:200],
        "entries_truncated": len(entries) > 200,
    }


def read_specpack_member(path: str, source: str, max_chars: int = 200_000) -> dict[str, Any]:
    pack_path = resolve_allowed_path(path)
    with zipfile.ZipFile(pack_path) as pack:
        manifest = json.loads(pack.read("manifest.json").decode("utf-8"))
        entries = manifest.get("entries", [])
        match = next((entry for entry in entries if entry.get("source") == source), None)
        if match is None:
            raise FileNotFoundError(f"No source member named {source!r} in {pack_path}")
        raw = pack.read(match["spec"])

    decoded = decode_spec_bytes(raw, f"{pack_path}:{source}")
    text = decoded.text
    return {
        "text": text[:max_chars],
        "truncated": len(text) > max_chars,
        "metadata": decoded.metadata,
        "pack_entry": match,
    }


def _snippet(text: str, query: str, radius: int = 240) -> str:
    lower = text.lower()
    pos = lower.find(query.lower())
    if pos < 0:
        return text[: radius * 2]
    start = max(0, pos - radius)
    end = min(len(text), pos + len(query) + radius)
    prefix = "..." if start else ""
    suffix = "..." if end < len(text) else ""
    return prefix + text[start:end] + suffix


def search_specs(query: str, root: str | None = None, limit: int = 20, max_file_bytes: int = 5_000_000) -> dict[str, Any]:
    if not query:
        raise ValueError("query must not be empty")
    search_root = resolve_allowed_path(root) if root else allowed_roots()[0]
    candidates = list_spec_files(str(search_root), limit=10_000)["files"]

    matches: list[dict[str, Any]] = []
    for candidate in candidates:
        path = Path(candidate)
        if len(matches) >= limit:
            break
        if path.stat().st_size > max_file_bytes:
            continue
        try:
            if path.suffix.lower() == ".spec":
                decoded = decode_spec_bytes(path.read_bytes(), str(path))
                if query.lower() in decoded.text.lower():
                    matches.append(
                        {
                            "source": str(path),
                            "type": ".spec",
                            "snippet": _snippet(decoded.text, query),
                            "metadata": decoded.metadata,
                        }
                    )
            elif path.suffix.lower() == ".specpack":
                with zipfile.ZipFile(path) as pack:
                    manifest = json.loads(pack.read("manifest.json").decode("utf-8"))
                    for entry in manifest.get("entries", []):
                        if len(matches) >= limit:
                            break
                        raw = pack.read(entry["spec"])
                        if len(raw) > max_file_bytes:
                            continue
                        decoded = decode_spec_bytes(raw, f"{path}:{entry.get('source')}")
                        if query.lower() in decoded.text.lower():
                            matches.append(
                                {
                                    "source": str(path),
                                    "member": entry.get("source"),
                                    "type": ".specpack_member",
                                    "snippet": _snippet(decoded.text, query),
                                    "metadata": decoded.metadata,
                                }
                            )
        except Exception as exc:  # keep searching even if one file is stale/corrupt
            matches.append({"source": str(path), "error": str(exc)})

    return {
        "query": query,
        "root": str(search_root),
        "count": len(matches),
        "limit": limit,
        "matches": matches,
    }
