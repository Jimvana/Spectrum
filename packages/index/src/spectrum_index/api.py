from __future__ import annotations

import contextlib
import hashlib
import io
import json
import shutil
import tempfile
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

import spectrum_core._repo as _repo  # noqa: F401 - ensures repo modules are importable.
from spectrum_core import (
    EncryptOptions,
    SpectrumPack,
    decrypt_pack_bytes,
    encrypt_pack_bytes,
    inspect_encrypted_header,
    is_encrypted_pack,
    is_generated_path,
)
from rag.indexer import RETRIEVAL_PROFILE
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


def _build_inverted_from_documents(documents: list[dict]) -> dict[str, list[int]]:
    inverted: dict[int, list[int]] = {}
    for doc in documents:
        doc_id = int(doc["id"])
        for tid, _count in doc["freq"]:
            inverted.setdefault(int(tid), []).append(doc_id)
    return {str(tid): doc_ids for tid, doc_ids in inverted.items()}


def _finalize_documents(documents: list[dict]) -> dict:
    total_tokens = 0
    finalized = []
    for doc_id, document in enumerate(documents):
        doc = dict(document)
        doc["id"] = doc_id
        total_tokens += int(doc.get("token_count", 0))
        finalized.append(doc)
    avg_doc_length = total_tokens / len(finalized) if finalized else 0.0
    return {
        "meta": {
            "total_docs": len(finalized),
            "avg_doc_length": round(avg_doc_length, 2),
            "built_at": datetime.now(timezone.utc).isoformat(),
            "retrieval_profile": RETRIEVAL_PROFILE,
            "pack_fingerprint_schema": "encoded_spec_sha256_v1",
        },
        "documents": finalized,
        "inverted": _build_inverted_from_documents(finalized),
    }


def _pack_entry_fingerprints(pack_path: Path, *, passphrase: str | None = None) -> dict[str, dict[str, Any]]:
    fingerprints: dict[str, dict[str, Any]] = {}
    with SpectrumPack.open(pack_path, passphrase=passphrase) as opened:
        for entry in opened.entries:
            spec_bytes = opened.read_spec(entry)
            fingerprints[entry.source] = {
                "source_path": entry.source,
                "path": entry.spec,
                "name": Path(entry.source).name,
                "spec_sha256": hashlib.sha256(spec_bytes).hexdigest(),
                "spec_size": entry.spec_size,
                "orig_length": entry.original_size,
            }
    return fingerprints


def _attach_pack_fingerprints(index: dict, fingerprints: dict[str, dict[str, Any]]) -> None:
    for document in index.get("documents", []):
        source = str(document.get("source_path") or "")
        fingerprint = fingerprints.get(source)
        if fingerprint:
            document.update(fingerprint)
            document["original_size"] = fingerprint["orig_length"]


def _index_changed_entry(entry, fingerprint: dict[str, Any], tmp: Path, source_pack: SpectrumPack, *, verbose: bool) -> dict:
    spec_path = source_pack.extract_spec(entry, tmp / "changed")
    with _quiet(verbose):
        changed_index = _build_spec_index([spec_path])
    if not changed_index.get("documents"):
        raise ValueError(f"changed entry did not produce an index document: {entry.source}")
    document = dict(changed_index["documents"][0])
    document.update(fingerprint)
    document["original_size"] = fingerprint["orig_length"]
    return document


def _incremental_pack_index(
    pack_path: Path,
    old_index: dict,
    fingerprints: dict[str, dict[str, Any]],
    tmp: Path,
    *,
    verbose: bool,
    passphrase: str | None = None,
    progress_message: Callable[[str], None],
) -> tuple[dict, dict[str, int]]:
    old_by_source = {
        str(document.get("source_path")): document
        for document in old_index.get("documents", [])
        if document.get("source_path") and document.get("spec_sha256")
    }
    if len(old_by_source) != len(old_index.get("documents", [])):
        raise ValueError("embedded index does not contain pack fingerprints")

    added = []
    changed = []
    kept = []
    for source, fingerprint in fingerprints.items():
        old_doc = old_by_source.get(source)
        if old_doc is None:
            added.append(source)
        elif old_doc.get("spec_sha256") != fingerprint["spec_sha256"]:
            changed.append(source)
        else:
            doc = dict(old_doc)
            doc.update(fingerprint)
            kept.append(doc)
    deleted = sorted(set(old_by_source) - set(fingerprints))
    changed_sources = sorted([*added, *changed])
    progress_message(
        f"incremental diff: kept {len(kept)}, added {len(added)}, changed {len(changed)}, deleted {len(deleted)}"
    )

    kept_count = len(kept)
    new_documents = list(kept)
    if changed_sources:
        with SpectrumPack.open(pack_path, passphrase=passphrase) as opened:
            entries_by_source = {entry.source: entry for entry in opened.entries}
            for source in changed_sources:
                progress_message(f"indexing changed source {source}")
                new_documents.append(
                    _index_changed_entry(
                        entries_by_source[source],
                        fingerprints[source],
                        tmp,
                        opened,
                        verbose=verbose,
                    )
                )
    new_documents.sort(key=lambda document: str(document.get("source_path") or document.get("path") or "").lower())
    return _finalize_documents(new_documents), {
        "kept": kept_count,
        "added": len(added),
        "changed": len(changed),
        "deleted": len(deleted),
        "reindexed": len(changed_sources),
    }


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
    incremental: bool = False,
) -> dict[str, Any]:
    """Build a retrieval index for a `.spec`, `.spec` directory, or `.specpack`."""
    path = Path(target).expanduser().resolve()
    if not path.exists():
        raise FileNotFoundError(path)

    if path.suffix.lower() == ".specpack":
        return build_pack_index(
            path,
            output_path=output_path,
            embed=embed,
            verbose=verbose,
            passphrase=passphrase,
            incremental=incremental,
        )

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
    progress_callback: Callable[[str], None] | None = None,
    incremental: bool = False,
) -> dict[str, Any]:
    """Build an index for a `.specpack`, optionally embedding it as `index.bin`."""
    pack = Path(pack_path).expanduser().resolve()
    if not pack.exists():
        raise FileNotFoundError(pack)

    progress: list[str] = []

    def progress_message(message: str) -> None:
        progress.append(message)
        if progress_callback is not None:
            progress_callback(message)
        if verbose:
            print(f"[spectrum-index] {message}")

    incremental_stats: dict[str, int] | None = None
    used_incremental = False
    with tempfile.TemporaryDirectory(prefix="spectrum-index-pack-") as tmp_name:
        tmp = Path(tmp_name)
        progress_message("fingerprinting pack specs")
        fingerprints = _pack_entry_fingerprints(pack, passphrase=passphrase)
        progress_message(f"fingerprinted {len(fingerprints)} specs")
        index = None
        if incremental:
            progress_message("loading embedded index for incremental rebuild")
            try:
                old_index = _load_embedded_pack_index(pack, passphrase=passphrase)
                if old_index is None:
                    raise FileNotFoundError(f"no embedded {PACK_INDEX_NAME} in {pack}")
                index, incremental_stats = _incremental_pack_index(
                    pack,
                    old_index,
                    fingerprints,
                    tmp,
                    verbose=verbose,
                    passphrase=passphrase,
                    progress_message=progress_message,
                )
                used_incremental = True
                progress_message(f"incrementally indexed {incremental_stats['reindexed']} changed documents")
            except Exception as exc:
                progress_message(f"incremental rebuild unavailable: {exc}; falling back to full rebuild")
        if index is None:
            progress_message("extracting pack specs")
            files_dir = _extract_pack(pack, tmp, passphrase=passphrase)
            spec_count = sum(1 for _ in files_dir.rglob("*.spec"))
            progress_message(f"extracted {spec_count} specs")
            with _quiet(verbose):
                progress_message("building retrieval index")
                index = index_directory(files_dir)
            progress_message(f"indexed {index['meta']['total_docs']} documents")
            _apply_pack_manifest_paths(index, tmp)
            _attach_pack_fingerprints(index, fingerprints)
        index_path = Path(output_path).expanduser().resolve() if output_path else tmp / PACK_INDEX_NAME
        with _quiet(verbose):
            progress_message("saving index")
            save_index(index, index_path)
        progress_message(f"saved index to {index_path}")
        if embed:
            progress_message("embedding index in pack")
            _replace_zip_member(pack, index_path, PACK_INDEX_NAME, passphrase=passphrase)
            progress_message("embedded index in pack")
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
        "incremental": used_incremental,
        "incremental_stats": incremental_stats,
        "progress": progress,
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
    include_generated: bool = False,
) -> list[dict]:
    """Search a loaded index or index file path."""
    loaded = load_index(index) if isinstance(index, (str, Path)) else index
    with _quiet(False):
        results = _search(query, loaded, top_k=max(top_k * 4, top_k), lang=language)
    documents = loaded.get("documents", [])
    filtered: list[dict] = []
    for result in results:
        doc_id = int(result.get("doc_id", -1))
        if 0 <= doc_id < len(documents):
            doc = documents[doc_id]
            if "source_path" in doc:
                result["source_path"] = doc["source_path"]
        source_path = str(result.get("source_path") or result.get("path") or "")
        if include_generated or not is_generated_path(source_path):
            filtered.append(result)
        if len(filtered) >= top_k:
            break
    return filtered


def search_pack(
    pack_path: str | Path,
    query: str,
    *,
    top_k: int = 10,
    language: str | int = "txt",
    index_path: str | Path | None = None,
    build_if_missing: bool = True,
    passphrase: str | None = None,
    include_generated: bool = False,
) -> list[dict]:
    """Search a `.specpack` using an index file, embedded index, or temporary index."""
    pack = Path(pack_path).expanduser().resolve()
    if index_path is not None:
        return search_index(index_path, query, top_k=top_k, language=language, include_generated=include_generated)

    embedded = _load_embedded_pack_index(pack, passphrase=passphrase)
    if embedded is not None:
        return search_index(embedded, query, top_k=top_k, language=language, include_generated=include_generated)

    if not build_if_missing:
        raise FileNotFoundError(f"no embedded {PACK_INDEX_NAME} in {pack}")

    built = build_pack_index(pack, passphrase=passphrase)
    return search_index(built["index"], query, top_k=top_k, language=language, include_generated=include_generated)


def dump_results(results: list[dict]) -> str:
    return json.dumps(results, indent=2)
