from __future__ import annotations

import json
import tempfile
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

from . import _repo as _repo  # noqa: F401 - ensures repo modules are importable.
from .spec import DecodeResult, EncodeResult, decode_file, encode_file
import dictionary as D


PACK_FORMAT = "spectrum.specpack"
PACK_VERSION = 1
PACK_COMPRESSION = zipfile.ZIP_STORED

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


def _posix(path: Path) -> str:
    return path.as_posix()


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
            entries.append(
                PackEntry(
                    source=_posix(rel),
                    spec=_posix(spec_rel),
                    original_size=result.original_size,
                    spec_size=result.spec_size,
                )
            )

        manifest = {
            "format": PACK_FORMAT,
            "version": PACK_VERSION,
            "dict_version": D.DICT_VERSION,
            "source_root": source.name,
            "entries": [entry.__dict__ for entry in entries],
        }

        output.parent.mkdir(parents=True, exist_ok=True)
        with zipfile.ZipFile(output, "w", compression=PACK_COMPRESSION) as archive:
            archive.writestr("manifest.json", json.dumps(manifest, indent=2))
            for entry in entries:
                archive.write(tmp / entry.spec, entry.spec)

    return inspect_pack(output)


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
            opened._zip.extractall(tmp)
            for entry in opened.entries:
                results.append(
                    decode_file(
                        tmp / entry.spec,
                        target / entry.source,
                        verbose=verbose,
                    )
                )
    return results


def inspect_pack(pack_path: str | Path) -> dict:
    path = Path(pack_path)
    with zipfile.ZipFile(path) as archive:
        manifest = json.loads(archive.read("manifest.json").decode("utf-8"))
        members = set(archive.namelist())
    entries = manifest.get("entries", [])
    missing = [entry["spec"] for entry in entries if entry.get("spec") not in members]
    total_original = sum(int(entry.get("original_size", 0)) for entry in entries)
    total_spec = sum(int(entry.get("spec_size", 0)) for entry in entries)
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
        self.entries = [PackEntry(**entry) for entry in manifest.get("entries", [])]

    @classmethod
    def open(cls, path: str | Path) -> "SpectrumPack":
        pack_path = Path(path)
        archive = zipfile.ZipFile(pack_path)
        manifest = json.loads(archive.read("manifest.json").decode("utf-8"))
        if manifest.get("format") != PACK_FORMAT:
            archive.close()
            raise ValueError(f"unsupported pack format: {manifest.get('format')!r}")
        return cls(pack_path, archive, manifest)

    def close(self) -> None:
        self._zip.close()

    def __enter__(self) -> "SpectrumPack":
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.close()

    def read_spec(self, entry: PackEntry | str) -> bytes:
        spec_member = entry.spec if isinstance(entry, PackEntry) else entry
        return self._zip.read(spec_member)

    def extract_specs(self, output_dir: str | Path) -> list[Path]:
        target = Path(output_dir)
        paths: list[Path] = []
        for entry in self.entries:
            self._zip.extract(entry.spec, target)
            paths.append(target / entry.spec)
        return paths
