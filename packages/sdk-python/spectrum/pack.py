from __future__ import annotations

import shutil
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable

from spectrum_core import (
    SpectrumPack as CorePack,
    decode_member,
    inspect_pack,
    pack as core_pack,
    unpack as core_unpack,
    verify_pack,
)
from spectrum_index import build_pack_index, search_pack


@dataclass(frozen=True)
class Document:
    """Input document for building a Spectrum pack."""

    id: str
    content: str | bytes
    path: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class DecodedDocument:
    """Decoded document returned from a Spectrum pack."""

    path: str
    content: str
    content_bytes: bytes
    id: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


class SpectrumPack:
    """Developer-friendly SDK wrapper around `.specpack` files."""

    def __init__(self, path: str | Path):
        self.path = Path(path)

    @classmethod
    def open(cls, path: str | Path) -> "SpectrumPack":
        pack_path = Path(path)
        if not pack_path.exists():
            raise FileNotFoundError(pack_path)
        return cls(pack_path)

    @classmethod
    def create(
        cls,
        *,
        input_path: str | Path,
        output_path: str | Path,
        include_all: bool = False,
        language: str | int | None = None,
        rle: str = "off",
        zlib_level: int = 9,
    ) -> "SpectrumPack":
        core_pack(
            input_path,
            output_path,
            include_all=include_all,
            language=language,
            rle=rle,
            zlib_level=zlib_level,
        )
        return cls(output_path)

    @classmethod
    def from_documents(
        cls,
        documents: Iterable[Document],
        output_path: str | Path,
        *,
        rle: str = "off",
        zlib_level: int = 9,
    ) -> "SpectrumPack":
        """Create a pack from in-memory documents.

        Document IDs and metadata are persisted in the pack manifest so callers
        can recover provenance when documents are decoded later.
        """
        with tempfile.TemporaryDirectory(prefix="spectrum-sdk-docs-") as tmp_name:
            root = Path(tmp_name)
            ids_by_source: dict[str, str] = {}
            metadata_by_source: dict[str, dict[str, Any]] = {}
            wrote = 0
            for document in documents:
                rel = Path(document.path or f"{document.id}.txt")
                if rel.is_absolute() or ".." in rel.parts:
                    raise ValueError(f"unsafe document path: {rel}")
                rel_posix = rel.as_posix()
                target = root / rel
                target.parent.mkdir(parents=True, exist_ok=True)
                if isinstance(document.content, bytes):
                    target.write_bytes(document.content)
                else:
                    target.write_text(document.content, encoding="utf-8", newline="")
                ids_by_source[rel_posix] = document.id
                if document.metadata:
                    metadata_by_source[rel_posix] = dict(document.metadata)
                wrote += 1
            if wrote == 0:
                raise ValueError("at least one document is required")
            core_pack(
                root,
                output_path,
                include_all=True,
                rle=rle,
                zlib_level=zlib_level,
                ids_by_source=ids_by_source,
                metadata_by_source=metadata_by_source,
            )
        return cls(output_path)

    def inspect(self) -> dict:
        return inspect_pack(self.path)

    def verify(self) -> dict:
        return verify_pack(self.path).to_dict()

    def build_index(self, *, embed: bool = True, output_path: str | Path | None = None, incremental: bool = True) -> dict:
        result = build_pack_index(self.path, output_path=output_path, embed=embed, incremental=incremental)
        return {key: value for key, value in result.items() if key != "index"}

    def search(self, query: str, *, top_k: int = 10, language: str | int = "txt") -> list[dict]:
        return search_pack(self.path, query, top_k=top_k, language=language)

    def unpack(self, output_dir: str | Path) -> list[DecodedDocument]:
        target = Path(output_dir)
        results = core_unpack(self.path, target)
        decoded: list[DecodedDocument] = []
        with CorePack.open(self.path) as opened:
            entries = list(opened.entries)
        for entry, result in zip(entries, results):
            path = target / entry.source
            content_bytes = path.read_bytes()
            decoded.append(
                DecodedDocument(
                    path=entry.source,
                    content=content_bytes.decode("utf-8", errors="replace"),
                    content_bytes=content_bytes,
                    id=entry.source_id,
                    metadata=entry.metadata or {},
                )
            )
            if not result.ok:
                raise ValueError(f"decoded document failed verification: {entry.source}")
        return decoded

    def read_document(self, path: str) -> DecodedDocument:
        """Decode one document from the pack without unpacking every entry."""
        with CorePack.open(self.path) as opened:
            entry = opened.find_entry(path)
            if entry is None:
                raise FileNotFoundError(path)
        with tempfile.TemporaryDirectory(prefix="spectrum-sdk-read-") as tmp_name:
            output = Path(tmp_name) / "document"
            result = decode_member(self.path, path, output)
            content_bytes = output.read_bytes()
        if not result.ok:
            raise ValueError(f"decoded document failed verification: {path}")
        return DecodedDocument(
            path=entry.source,
            content=content_bytes.decode("utf-8", errors="replace"),
            content_bytes=content_bytes,
            id=entry.source_id,
            metadata=entry.metadata or {},
        )

    def extract_to(self, output_dir: str | Path) -> Path:
        target = Path(output_dir)
        if target.exists():
            shutil.rmtree(target)
        target.mkdir(parents=True)
        self.unpack(target)
        return target

    @property
    def entries(self) -> list[dict]:
        with CorePack.open(self.path) as opened:
            return [entry.__dict__.copy() for entry in opened.entries]
