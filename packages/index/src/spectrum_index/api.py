from __future__ import annotations

import contextlib
import io
import json
import shutil
import tempfile
import zipfile
from pathlib import Path
from typing import Any

import spectrum_core._repo as _repo  # noqa: F401 - ensures repo modules are importable.
from spectrum_core import (
    EncryptOptions,
    SpectrumPack,
    decrypt_pack_bytes,
    encrypt_pack_bytes,
    inspect_encrypted_header,
    is_encrypted_pack,
)
from rag.indexer import build_index as _build_spec_index
from rag.indexer import index_directory, load_index as _load_index, save_index
from rag.query import search as _search

PACK_INDEX_NAME = "index.bin"


def _quiet(enabled: bool):
    if enabled:
        return contextlib.nullcontext()
    return contextlib.redirect_stdout(io.StringIO())


def _replace_zip_member(zip_path: Path, member_path: Path, arcname: str, *, passphrase: str | None = None) -> None:
    with tempfile.TemporaryDirectory(prefix="spectrum-index-zip-") as tmp_name:
        tmp_zip = Path(tmp_name) / zip_path.name
        encrypted = is_encrypted_pack(zip_path)
        plain_path = zip_path
        encrypted_info = inspect_encrypted_header(zip_path) if encrypted else None
        if encrypted:
            if passphrase is None:
                raise ValueError("encrypted Spectrum pack is locked; unlock with a passphrase")
            plain_path = Path(tmp_name) / "plain.specpack"
            plain_path.write_bytes(decrypt_pack_bytes(zip_path.read_bytes(), passphrase))
        with zipfile.ZipFile(plain_path) as source, zipfile.ZipFile(tmp_zip, "w", compression=zipfile.ZIP_STORED) as target:
            for item in source.infolist():
                if item.filename == arcname:
                    continue
                target.writestr(item, source.read(item.filename))
            target.write(member_path, arcname)
        if encrypted:
            assert encrypted_info is not None
            zip_path.write_bytes(
                encrypt_pack_bytes(
                    tmp_zip.read_bytes(),
                    passphrase or "",
                    EncryptOptions(encrypted_info.kdf_profile or "interactive", encrypted_info.hint),
                )
            )
        else:
            shutil.move(str(tmp_zip), zip_path)


def _extract_pack(pack_path: Path, tmp: Path, *, passphrase: str | None = None) -> Path:
    with SpectrumPack.open(pack_path, passphrase=passphrase) as pack:
        (tmp / "manifest.json").write_text(json.dumps(pack.manifest), encoding="utf-8")
        pack.extract_specs(tmp)
    return tmp / "files"


def _apply_pack_manifest_paths(index: dict, pack_root: Path) -> None:
    manifest_path = pack_root / "manifest.json"
    if not manifest_path.exists():
        return
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    entries = {
        str(entry.get("spec", "")).replace("\\", "/"): str(entry.get("source", ""))
        for entry in manifest.get("entries", [])
    }
    for document in index.get("documents", []):
        spec_path = Path(str(document.get("path", "")))
        try:
            spec_rel = spec_path.relative_to(pack_root).as_posix()
        except ValueError:
            spec_rel = spec_path.as_posix()
        document["path"] = spec_rel
        source = entries.get(spec_rel)
        if source:
            document["source_path"] = source
            document["name"] = Path(source).name


def _apply_pack_manifest_from_zip(index: dict, pack_path: Path, *, passphrase: str | None = None) -> None:
    with SpectrumPack.open(pack_path, passphrase=passphrase) as opened:
        manifest = opened.manifest
    entries = {
        str(entry.get("spec", "")).replace("\\", "/"): str(entry.get("source", ""))
        for entry in manifest.get("entries", [])
    }
    for document in index.get("documents", []):
        spec_rel = str(document.get("path", "")).replace("\\", "/")
        source = entries.get(spec_rel)
        if source:
            document["source_path"] = source
            document["name"] = Path(source).name


def build_index(
    target: str | Path,
    output_path: str | Path | None = None,
    *,
    embed: bool = False,
    verbose: bool = False,
    passphrase: str | None = None,
) -> dict[str, Any]:
    """Build a retrieval index for a `.spec`, `.spec` directory, or `.specpack`."""
    path = Path(target).expanduser().resolve()
    if not path.exists():
        raise FileNotFoundError(path)

    if path.suffix.lower() == ".specpack":
        return build_pack_index(path, output_path=output_path, embed=embed, verbose=verbose, passphrase=passphrase)

    with _quiet(verbose):
        if path.is_file():
            index = _build_spec_index([path])
        else:
            index = index_directory(path)

    if output_path is not None:
        with _quiet(verbose):
            save_index(index, output_path)
    return {
        "target": str(path),
        "index_path": str(output_path) if output_path else None,
        "embedded": False,
        "documents": index["meta"]["total_docs"],
        "tokens": len(index["inverted"]),
        "index": index,
    }


def build_pack_index(
    pack_path: str | Path,
    output_path: str | Path | None = None,
    *,
    embed: bool = False,
    verbose: bool = False,
    passphrase: str | None = None,
) -> dict[str, Any]:
    """Build an index for a `.specpack`, optionally embedding it as `index.bin`."""
    pack = Path(pack_path).expanduser().resolve()
    if not pack.exists():
        raise FileNotFoundError(pack)

    with tempfile.TemporaryDirectory(prefix="spectrum-index-pack-") as tmp_name:
        tmp = Path(tmp_name)
        files_dir = _extract_pack(pack, tmp, passphrase=passphrase)
        with _quiet(verbose):
            index = index_directory(files_dir)
        _apply_pack_manifest_paths(index, tmp)
        index_path = Path(output_path).expanduser().resolve() if output_path else tmp / PACK_INDEX_NAME
        with _quiet(verbose):
            save_index(index, index_path)
        if embed:
            _replace_zip_member(pack, index_path, PACK_INDEX_NAME, passphrase=passphrase)
            final_path = f"{pack}#{PACK_INDEX_NAME}"
        elif output_path is not None:
            final_path = str(index_path)
        else:
            final_path = None

    return {
        "target": str(pack),
        "index_path": final_path,
        "embedded": embed,
        "documents": index["meta"]["total_docs"],
        "tokens": len(index["inverted"]),
        "index": index,
    }


def load_index(path: str | Path) -> dict:
    with _quiet(False):
        return _load_index(path)


def _load_embedded_pack_index(pack_path: Path, *, passphrase: str | None = None) -> dict | None:
    with SpectrumPack.open(pack_path, passphrase=passphrase) as opened:
        archive = opened._zip
        if PACK_INDEX_NAME not in archive.namelist():
            return None
        with tempfile.TemporaryDirectory(prefix="spectrum-index-read-") as tmp_name:
            index_path = Path(tmp_name) / PACK_INDEX_NAME
            index_path.write_bytes(archive.read(PACK_INDEX_NAME))
            index = load_index(index_path)
            _apply_pack_manifest_from_zip(index, pack_path, passphrase=passphrase)
            return index


def search_index(
    index: dict | str | Path,
    query: str,
    *,
    top_k: int = 10,
    language: str | int = "txt",
) -> list[dict]:
    """Search a loaded index or index file path."""
    loaded = load_index(index) if isinstance(index, (str, Path)) else index
    with _quiet(False):
        results = _search(query, loaded, top_k=top_k, lang=language)
    documents = loaded.get("documents", [])
    for result in results:
        doc_id = int(result.get("doc_id", -1))
        if 0 <= doc_id < len(documents):
            doc = documents[doc_id]
            if "source_path" in doc:
                result["source_path"] = doc["source_path"]
    return results


def search_pack(
    pack_path: str | Path,
    query: str,
    *,
    top_k: int = 10,
    language: str | int = "txt",
    index_path: str | Path | None = None,
    build_if_missing: bool = True,
    passphrase: str | None = None,
) -> list[dict]:
    """Search a `.specpack` using an index file, embedded index, or temporary index."""
    pack = Path(pack_path).expanduser().resolve()
    if index_path is not None:
        return search_index(index_path, query, top_k=top_k, language=language)

    embedded = _load_embedded_pack_index(pack, passphrase=passphrase)
    if embedded is not None:
        return search_index(embedded, query, top_k=top_k, language=language)

    if not build_if_missing:
        raise FileNotFoundError(f"no embedded {PACK_INDEX_NAME} in {pack}")

    built = build_pack_index(pack, passphrase=passphrase)
    return search_index(built["index"], query, top_k=top_k, language=language)


def dump_results(results: list[dict]) -> str:
    return json.dumps(results, indent=2)
