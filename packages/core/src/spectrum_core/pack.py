from __future__ import annotations

import json
import tempfile
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

from . import _repo as _repo  # noqa: F401 - ensures repo modules are importable.
from .spec import DecodeResult, EncodeResult, decode_file, encode_file
import dictionary as D


PACK_FORMAT = "spectrum.specpack"
PACK_VERSION = 1
PACK_COMPRESSION = zipfile.ZIP_STORED
PACK_INDEX_NAME = "index.bin"

SUPPORTED_EXTENSIONS = {
    ".py", ".html", ".htm", ".js", ".mjs", ".cjs", ".css", ".txt", ".md",
    ".ts", ".tsx", ".sql", ".rs", ".php", ".phtml", ".xml", ".java", ".c",
    ".h", ".cpp", ".cc", ".cxx", ".hpp", ".hh", ".hxx", ".go", ".cs",
    ".sh", ".bash", ".zsh", ".json", ".yaml", ".yml", ".toml",
}


@dataclass(frozen=True)
class PackEntry:
    source: str
    spec: str
    original_size: int
    spec_size: int
    source_id: str | None = None
    metadata: dict[str, Any] | None = None


def _posix(path: Path) -> str:
    return path.as_posix()


def _safe_relative_path(value: str, *, field: str) -> Path:
    if not value:
        raise ValueError(f"{field} path is required")
    path = Path(value.replace("\\", "/"))
    if path.is_absolute() or ".." in path.parts:
        raise ValueError(f"unsafe {field} path: {value!r}")
    if any(part in {"", ".", ".."} for part in path.parts):
        raise ValueError(f"unsafe {field} path: {value!r}")
    return path


def _safe_join(root: Path, relative: str, *, field: str) -> Path:
    rel = _safe_relative_path(relative, field=field)
    target = (root / rel).resolve()
    root_resolved = root.resolve()
    if target != root_resolved and root_resolved not in target.parents:
        raise ValueError(f"unsafe {field} path: {relative!r}")
    return target


def _entry_to_manifest(entry: PackEntry) -> dict[str, Any]:
    return {
        key: value
        for key, value in entry.__dict__.items()
        if value is not None
    }


def _load_manifest(archive: zipfile.ZipFile) -> dict:
    try:
        manifest = json.loads(archive.read("manifest.json").decode("utf-8"))
    except KeyError as exc:
        raise ValueError("missing manifest.json") from exc
    if manifest.get("format") != PACK_FORMAT:
        raise ValueError(f"unsupported pack format: {manifest.get('format')!r}")
    return manifest


def _validate_entry(raw: dict, members: set[str]) -> PackEntry:
    source = str(raw.get("source", ""))
    spec = str(raw.get("spec", "")).replace("\\", "/")
    _safe_relative_path(source, field="source")
    spec_path = _safe_relative_path(spec, field="spec")
    if spec_path.parts[0] != "files" or spec_path.suffix.lower() != ".spec":
        raise ValueError(f"unsafe spec path: {spec!r}")
    if spec not in members:
        raise ValueError(f"missing spec member: {spec}")
    metadata = raw.get("metadata")
    if metadata is not None and not isinstance(metadata, dict):
        raise ValueError(f"metadata for {source!r} must be an object")
    source_id = raw.get("source_id")
    return PackEntry(
        source=source,
        spec=spec,
        original_size=int(raw.get("original_size", 0)),
        spec_size=int(raw.get("spec_size", 0)),
        source_id=str(source_id) if source_id is not None else None,
        metadata=metadata,
    )


def iter_source_files(root: str | Path, *, include_all: bool = False) -> Iterable[Path]:
    root_path = Path(root)
    if root_path.is_file():
        yield root_path
        return
    for path in sorted(root_path.rglob("*")):
        if not path.is_file():
            continue
        if any(part in {".git", "node_modules", "__pycache__"} for part in path.parts):
            continue
        if path.suffix.lower() in {".spec", ".specpack"}:
            continue
        if include_all or path.suffix.lower() in SUPPORTED_EXTENSIONS:
            yield path


def pack(
    input_path: str | Path,
    output_path: str | Path,
    *,
    include_all: bool = False,
    language: str | int | None = None,
    rle: str = "off",
    zlib_level: int = 9,
    verbose: bool = False,
    metadata_by_source: dict[str, dict[str, Any]] | None = None,
    ids_by_source: dict[str, str] | None = None,
) -> dict:
    """Create a `.specpack` archive from a file or folder."""
    source = Path(input_path).resolve()
    output = Path(output_path).resolve()
    if not source.exists():
        raise FileNotFoundError(source)

    base = source.parent if source.is_file() else source
    files = list(iter_source_files(source, include_all=include_all))
    if not files:
        raise ValueError(f"no encodable files found under {source}")

    with tempfile.TemporaryDirectory(prefix="spectrum-core-pack-") as tmp_name:
        tmp = Path(tmp_name)
        entries: list[PackEntry] = []
        for file_path in files:
            rel = Path(file_path.name) if source.is_file() else file_path.relative_to(base)
            spec_rel = Path("files") / Path(str(rel) + ".spec")
            spec_path = tmp / spec_rel
            result = encode_file(
                file_path,
                spec_path,
                language=language,
                rle=rle,
                zlib_level=zlib_level,
                verbose=verbose,
            )
            source_name = _posix(rel)
            entries.append(
                PackEntry(
                    source=source_name,
                    spec=_posix(spec_rel),
                    original_size=result.original_size,
                    spec_size=result.spec_size,
                    source_id=(ids_by_source or {}).get(source_name),
                    metadata=(metadata_by_source or {}).get(source_name),
                )
            )

        manifest = {
            "format": PACK_FORMAT,
            "version": PACK_VERSION,
            "dict_version": D.DICT_VERSION,
            "source_root": source.name,
            "entries": [_entry_to_manifest(entry) for entry in entries],
        }

        output.parent.mkdir(parents=True, exist_ok=True)
        with zipfile.ZipFile(output, "w", compression=PACK_COMPRESSION) as archive:
            archive.writestr("manifest.json", json.dumps(manifest, indent=2))
            for entry in entries:
                archive.write(tmp / entry.spec, entry.spec)

    return inspect_pack(output)


def append_to_pack(
    pack_path: str | Path,
    input_path: str | Path,
    *,
    output_path: str | Path | None = None,
    include_all: bool = False,
    language: str | int | None = None,
    rle: str = "off",
    zlib_level: int = 9,
    verbose: bool = False,
    replace: bool = False,
    metadata_by_source: dict[str, dict[str, Any]] | None = None,
    ids_by_source: dict[str, str] | None = None,
) -> dict:
    """Append source files to an existing `.specpack`.

    The archive is rewritten through a temporary file so existing members are
    preserved and the manifest is updated atomically when appending in place.
    Existing source paths are rejected unless `replace=True`.
    """
    pack_file = Path(pack_path).expanduser().resolve()
    source = Path(input_path).expanduser().resolve()
    output = Path(output_path).expanduser().resolve() if output_path else pack_file
    if not pack_file.exists():
        raise FileNotFoundError(pack_file)
    if pack_file.suffix.lower() != ".specpack":
        raise ValueError("pack path must end with .specpack")
    if output.suffix.lower() != ".specpack":
        raise ValueError("output path must end with .specpack")
    if not source.exists():
        raise FileNotFoundError(source)

    base = source.parent if source.is_file() else source
    files = list(iter_source_files(source, include_all=include_all))
    if not files:
        raise ValueError(f"no encodable files found under {source}")

    with SpectrumPack.open(pack_file) as opened:
        manifest = dict(opened.manifest)
        existing_entries = list(opened.entries)
        existing_members = set(opened._zip.namelist())

    existing_by_source = {entry.source: entry for entry in existing_entries}
    new_sources: set[str] = set()
    encoded_entries: list[PackEntry] = []

    with tempfile.TemporaryDirectory(prefix="spectrum-core-append-") as tmp_name:
        tmp = Path(tmp_name)
        for file_path in files:
            rel = Path(file_path.name) if source.is_file() else file_path.relative_to(base)
            source_name = _posix(rel)
            if source_name in new_sources:
                raise ValueError(f"duplicate appended source path: {source_name}")
            if source_name in existing_by_source and not replace:
                raise ValueError(f"source already exists in pack: {source_name}")
            new_sources.add(source_name)

            spec_rel = Path("files") / Path(str(rel) + ".spec")
            spec_name = _posix(spec_rel)
            if spec_name in existing_members and source_name not in existing_by_source and not replace:
                raise ValueError(f"spec member already exists in pack: {spec_name}")

            spec_path = tmp / spec_rel
            result = encode_file(
                file_path,
                spec_path,
                language=language,
                rle=rle,
                zlib_level=zlib_level,
                verbose=verbose,
            )
            encoded_entries.append(
                PackEntry(
                    source=source_name,
                    spec=spec_name,
                    original_size=result.original_size,
                    spec_size=result.spec_size,
                    source_id=(ids_by_source or {}).get(source_name),
                    metadata=(metadata_by_source or {}).get(source_name),
                )
            )

        removed_specs = {
            existing_by_source[source_name].spec
            for source_name in new_sources
            if source_name in existing_by_source
        }
        kept_entries = [entry for entry in existing_entries if entry.source not in new_sources]
        merged_entries = [*kept_entries, *encoded_entries]
        manifest["entries"] = [_entry_to_manifest(entry) for entry in merged_entries]

        tmp_zip = tmp / output.name
        with zipfile.ZipFile(pack_file) as source_archive, zipfile.ZipFile(
            tmp_zip, "w", compression=PACK_COMPRESSION
        ) as target_archive:
            for item in source_archive.infolist():
                if item.filename == "manifest.json":
                    continue
                if item.filename == PACK_INDEX_NAME:
                    continue
                if item.filename in removed_specs:
                    continue
                target_archive.writestr(item, source_archive.read(item.filename))
            target_archive.writestr("manifest.json", json.dumps(manifest, indent=2))
            for entry in encoded_entries:
                target_archive.write(tmp / entry.spec, entry.spec)

        output.parent.mkdir(parents=True, exist_ok=True)
        if output == pack_file:
            tmp_zip.replace(pack_file)
        else:
            output.write_bytes(tmp_zip.read_bytes())

    summary = inspect_pack(output)
    summary["appended_entries"] = len(encoded_entries)
    summary["replaced_entries"] = len(removed_specs)
    summary["dropped_embedded_index"] = PACK_INDEX_NAME in existing_members
    return summary


def unpack(
    pack_path: str | Path,
    output_dir: str | Path,
    *,
    verbose: bool = False,
) -> list[DecodeResult]:
    """Decode all entries in a `.specpack` archive to an output directory."""
    target = Path(output_dir)
    results: list[DecodeResult] = []
    with SpectrumPack.open(pack_path) as opened:
        with tempfile.TemporaryDirectory(prefix="spectrum-core-unpack-") as tmp_name:
            tmp = Path(tmp_name)
            for entry in opened.entries:
                spec_path = opened.extract_spec(entry, tmp)
                results.append(
                    decode_file(
                        spec_path,
                        _safe_join(target, entry.source, field="source"),
                        verbose=verbose,
                    )
                )
    return results


def decode_member(
    pack_path: str | Path,
    source: str,
    output_path: str | Path,
    *,
    verbose: bool = False,
) -> DecodeResult:
    """Decode one source member from a `.specpack` archive."""
    with SpectrumPack.open(pack_path) as opened:
        entry = opened.find_entry(source)
        if entry is None:
            raise FileNotFoundError(f"source member not found: {source}")
        with tempfile.TemporaryDirectory(prefix="spectrum-core-member-") as tmp_name:
            spec_path = opened.extract_spec(entry, Path(tmp_name))
            return decode_file(spec_path, output_path, verbose=verbose)


def inspect_pack(pack_path: str | Path) -> dict:
    path = Path(pack_path)
    with zipfile.ZipFile(path) as archive:
        manifest = _load_manifest(archive)
        members = set(archive.namelist())
        entries = [_validate_entry(entry, members) for entry in manifest.get("entries", [])]
    missing = [entry.spec for entry in entries if entry.spec not in members]
    total_original = sum(entry.original_size for entry in entries)
    total_spec = sum(entry.spec_size for entry in entries)
    return {
        "path": str(path),
        "format": manifest.get("format"),
        "version": manifest.get("version"),
        "dict_version": manifest.get("dict_version"),
        "source_root": manifest.get("source_root"),
        "entries": len(entries),
        "original_size": total_original,
        "spec_size": total_spec,
        "pack_size": path.stat().st_size,
        "ratio": round(path.stat().st_size / total_original, 4) if total_original else 0.0,
        "missing_entries": missing,
    }


class SpectrumPack:
    """Reader for Spectrum `.specpack` archives."""

    def __init__(self, path: Path, archive: zipfile.ZipFile, manifest: dict):
        self.path = path
        self._zip = archive
        self.manifest = manifest
        members = set(archive.namelist())
        self.entries = [_validate_entry(entry, members) for entry in manifest.get("entries", [])]

    @classmethod
    def open(cls, path: str | Path) -> "SpectrumPack":
        pack_path = Path(path)
        archive = zipfile.ZipFile(pack_path)
        try:
            manifest = _load_manifest(archive)
            return cls(pack_path, archive, manifest)
        except Exception:
            archive.close()
            raise

    def close(self) -> None:
        self._zip.close()

    def __enter__(self) -> "SpectrumPack":
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.close()

    def read_spec(self, entry: PackEntry | str) -> bytes:
        spec_member = entry.spec if isinstance(entry, PackEntry) else entry
        _safe_relative_path(spec_member, field="spec")
        return self._zip.read(spec_member)

    def find_entry(self, source: str) -> PackEntry | None:
        source = _safe_relative_path(source, field="source").as_posix()
        return next((entry for entry in self.entries if entry.source == source), None)

    def extract_spec(self, entry: PackEntry | str, output_dir: str | Path) -> Path:
        spec_member = entry.spec if isinstance(entry, PackEntry) else entry
        target = _safe_join(Path(output_dir), spec_member, field="spec")
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(self.read_spec(spec_member))
        return target

    def extract_specs(self, output_dir: str | Path) -> list[Path]:
        paths: list[Path] = []
        for entry in self.entries:
            paths.append(self.extract_spec(entry, output_dir))
        return paths
