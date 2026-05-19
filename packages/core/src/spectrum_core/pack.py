from __future__ import annotations

import json
import base64
import hashlib
import io
import os
import re
import shutil
import struct
import tempfile
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

from . import _repo as _repo  # noqa: F401 - ensures repo modules are importable.
from .spec import DecodeResult, decode_file, encode_file
import dictionary as D

from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.scrypt import Scrypt


PACK_FORMAT = "spectrum.specpack"
PACK_VERSION = 1
PACK_COMPRESSION = zipfile.ZIP_STORED
PACK_INDEX_NAME = "index.bin"
ENCRYPTED_PACK_MAGIC = b"SPENC001"
ENCRYPTED_PACK_VERSION = 1
ENCRYPTED_PACK_HEADER_LEN = 4

KDF_PROFILES = {
    "interactive": {"n": 2**15, "r": 8, "p": 1},
    "strong": {"n": 2**17, "r": 8, "p": 1},
    "low-memory": {"n": 2**14, "r": 8, "p": 1},
}

SUPPORTED_EXTENSIONS = {
    ".py", ".html", ".htm", ".js", ".mjs", ".cjs", ".css", ".txt", ".md",
    ".ts", ".tsx", ".sql", ".rs", ".php", ".phtml", ".xml", ".java", ".c",
    ".h", ".cpp", ".cc", ".cxx", ".hpp", ".hh", ".hxx", ".go", ".cs",
    ".sh", ".bash", ".zsh", ".json", ".yaml", ".yml", ".toml",
}

EXTERNAL_MEDIA_EXTENSIONS = {
    ".3g2", ".3gp", ".aac", ".aiff", ".ape", ".apng", ".arw", ".avif",
    ".avi", ".bmp", ".cr2", ".cr3", ".dng", ".flac", ".gif", ".heic",
    ".heif", ".ico", ".jpeg", ".jpg", ".m4a", ".m4v", ".mkv", ".mov",
    ".mp3", ".mp4", ".mpeg", ".mpg", ".nef", ".ogg", ".opus", ".orf",
    ".png", ".psd", ".raf", ".raw", ".rw2", ".tif", ".tiff", ".wav",
    ".webm", ".webp", ".wma", ".wmv",
    ".bin", ".ckpt", ".db", ".ggml", ".gguf", ".h5", ".mdb", ".model",
    ".npy", ".npz", ".onnx", ".pb", ".pt", ".pth", ".safetensors",
    ".sqlite", ".sqlite3", ".tflite", ".weights",
}


@dataclass(frozen=True)
class PackEntry:
    source: str
    spec: str
    original_size: int
    spec_size: int
    source_id: str | None = None
    metadata: dict[str, Any] | None = None


@dataclass(frozen=True)
class ExternalEntry:
    source: str
    kind: str
    sidecar_path: str
    blob: str
    sha256: str
    size_bytes: int
    original_path: str | None = None


@dataclass(frozen=True)
class EncryptOptions:
    kdf_profile: str = "interactive"
    hint: str | None = None


@dataclass(frozen=True)
class EncryptedPackInfo:
    encrypted: bool
    version: int | None = None
    aead: str | None = None
    kdf: str | None = None
    kdf_profile: str | None = None
    scrypt_n: int | None = None
    scrypt_r: int | None = None
    scrypt_p: int | None = None
    salt_b64: str | None = None
    nonce_b64: str | None = None
    hint: str | None = None
    encrypted_payload_bytes: int | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            key: value
            for key, value in self.__dict__.items()
            if value is not None
        }


class LockedPackError(ValueError):
    pass


class InvalidPassphraseError(ValueError):
    pass


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


def _external_entry_to_manifest(entry: ExternalEntry) -> dict[str, Any]:
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


def _read_all(path_or_bytes: str | Path | bytes | bytearray) -> bytes:
    if isinstance(path_or_bytes, (bytes, bytearray)):
        return bytes(path_or_bytes)
    return Path(path_or_bytes).read_bytes()


def _parse_encrypted_pack(data: bytes) -> tuple[dict[str, Any], bytes, bytes]:
    if not data.startswith(ENCRYPTED_PACK_MAGIC):
        raise ValueError("not an encrypted Spectrum pack")
    offset = len(ENCRYPTED_PACK_MAGIC)
    if len(data) < offset + ENCRYPTED_PACK_HEADER_LEN:
        raise ValueError("truncated encrypted Spectrum pack")
    header_len = struct.unpack(">I", data[offset : offset + ENCRYPTED_PACK_HEADER_LEN])[0]
    header_start = offset + ENCRYPTED_PACK_HEADER_LEN
    header_end = header_start + header_len
    if header_len <= 0 or header_end > len(data):
        raise ValueError("invalid encrypted Spectrum pack header")
    header_bytes = data[header_start:header_end]
    try:
        header = json.loads(header_bytes.decode("utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError("invalid encrypted Spectrum pack header JSON") from exc
    ciphertext = data[header_end:]
    return header, header_bytes, ciphertext


def is_encrypted_pack(path_or_bytes: str | Path | bytes | bytearray) -> bool:
    data = _read_all(path_or_bytes)
    return data.startswith(ENCRYPTED_PACK_MAGIC)


def inspect_encrypted_header(path_or_bytes: str | Path | bytes | bytearray) -> EncryptedPackInfo:
    data = _read_all(path_or_bytes)
    header, _header_bytes, ciphertext = _parse_encrypted_pack(data)
    kdf_params = header.get("kdf_params") or {}
    return EncryptedPackInfo(
        encrypted=True,
        version=int(header.get("version", 0)),
        aead=str(header.get("aead") or ""),
        kdf=str(header.get("kdf") or ""),
        kdf_profile=str(header.get("kdf_profile") or ""),
        scrypt_n=int(kdf_params.get("n", 0)),
        scrypt_r=int(kdf_params.get("r", 0)),
        scrypt_p=int(kdf_params.get("p", 0)),
        salt_b64=str(header.get("salt_b64") or ""),
        nonce_b64=str(header.get("nonce_b64") or ""),
        hint=header.get("hint"),
        encrypted_payload_bytes=len(ciphertext),
    )


def _derive_key(passphrase: str, header: dict[str, Any]) -> bytes:
    if not passphrase:
        raise ValueError("passphrase is required")
    if header.get("kdf") != "scrypt":
        raise ValueError(f"unsupported encrypted pack KDF: {header.get('kdf')!r}")
    params = header.get("kdf_params") or {}
    salt = base64.b64decode(str(header.get("salt_b64") or ""))
    return Scrypt(
        salt=salt,
        n=int(params["n"]),
        r=int(params["r"]),
        p=int(params["p"]),
        length=32,
    ).derive(passphrase.encode("utf-8"))


def encrypt_pack_bytes(
    plain_pack: bytes,
    passphrase: str,
    options: EncryptOptions | None = None,
) -> bytes:
    if not passphrase:
        raise ValueError("passphrase must not be empty")
    options = options or EncryptOptions()
    try:
        params = KDF_PROFILES[options.kdf_profile]
    except KeyError as exc:
        raise ValueError(f"unknown KDF profile: {options.kdf_profile}") from exc
    salt = os.urandom(16)
    nonce = os.urandom(12)
    header = {
        "format": "spectrum.encrypted-specpack",
        "version": ENCRYPTED_PACK_VERSION,
        "aead": "aes-256-gcm",
        "kdf": "scrypt",
        "kdf_profile": options.kdf_profile,
        "kdf_params": params,
        "salt_b64": base64.b64encode(salt).decode("ascii"),
        "nonce_b64": base64.b64encode(nonce).decode("ascii"),
    }
    if options.hint:
        header["hint"] = options.hint
    header_bytes = json.dumps(header, sort_keys=True, separators=(",", ":")).encode("utf-8")
    key = Scrypt(salt=salt, length=32, **params).derive(passphrase.encode("utf-8"))
    ciphertext = AESGCM(key).encrypt(nonce, plain_pack, header_bytes)
    return (
        ENCRYPTED_PACK_MAGIC
        + struct.pack(">I", len(header_bytes))
        + header_bytes
        + ciphertext
    )


def decrypt_pack_bytes(encrypted_pack: bytes, passphrase: str) -> bytes:
    header, header_bytes, ciphertext = _parse_encrypted_pack(encrypted_pack)
    if header.get("aead") != "aes-256-gcm":
        raise ValueError(f"unsupported encrypted pack AEAD: {header.get('aead')!r}")
    try:
        nonce = base64.b64decode(str(header.get("nonce_b64") or ""))
        key = _derive_key(passphrase, header)
        return AESGCM(key).decrypt(nonce, ciphertext, header_bytes)
    except Exception as exc:
        raise InvalidPassphraseError("encrypted pack authentication failed") from exc


def _open_zip_from_path(path: Path, passphrase: str | None = None) -> tuple[zipfile.ZipFile, io.BytesIO | None]:
    data = path.read_bytes()
    if data.startswith(ENCRYPTED_PACK_MAGIC):
        if passphrase is None:
            raise LockedPackError("encrypted Spectrum pack is locked; unlock with a passphrase")
        plain = decrypt_pack_bytes(data, passphrase)
        buffer = io.BytesIO(plain)
        return zipfile.ZipFile(buffer), buffer
    return zipfile.ZipFile(path), None


def _write_plain_or_encrypted(
    output: Path,
    plain_pack: bytes,
    *,
    encrypt: bool,
    passphrase: str | None,
    kdf_profile: str = "interactive",
    hint: str | None = None,
) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    if encrypt:
        if passphrase is None:
            raise ValueError("passphrase is required when encrypt=True")
        output.write_bytes(encrypt_pack_bytes(plain_pack, passphrase, EncryptOptions(kdf_profile, hint)))
    else:
        output.write_bytes(plain_pack)


def _inspect_archive(path: Path, archive: zipfile.ZipFile, *, pack_size: int) -> dict:
    manifest = _load_manifest(archive)
    members = set(archive.namelist())
    entries = [_validate_entry(entry, members) for entry in manifest.get("entries", [])]
    external_entries = [_validate_external_entry(entry) for entry in manifest.get("external_entries", [])]
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
        "external_entries": len(external_entries),
        "original_size": total_original,
        "spec_size": total_spec,
        "external_size": sum(entry.size_bytes for entry in external_entries),
        "pack_size": pack_size,
        "ratio": round(pack_size / total_original, 4) if total_original else 0.0,
        "missing_entries": missing,
    }


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


def _validate_external_entry(raw: dict) -> ExternalEntry:
    source = str(raw.get("source", ""))
    sidecar_path = str(raw.get("sidecar_path", "")).replace("\\", "/")
    blob = str(raw.get("blob", "")).replace("\\", "/")
    _safe_relative_path(source, field="source")
    sidecar_rel = _safe_relative_path(sidecar_path, field="sidecar")
    blob_rel = _safe_relative_path(blob, field="blob")
    if sidecar_rel.parts[0].endswith(".specpack"):
        raise ValueError(f"unsafe sidecar path: {sidecar_path!r}")
    if blob_rel.parts[0] != "blobs":
        raise ValueError(f"unsafe blob path: {blob!r}")
    kind = str(raw.get("kind") or "")
    if kind != "external_media":
        raise ValueError(f"unsupported external entry kind: {kind!r}")
    sha256 = str(raw.get("sha256") or "")
    if len(sha256) != 64 or any(char not in "0123456789abcdef" for char in sha256.lower()):
        raise ValueError(f"invalid external entry sha256 for {source!r}")
    return ExternalEntry(
        source=source,
        kind=kind,
        sidecar_path=sidecar_rel.as_posix(),
        blob=blob_rel.as_posix(),
        sha256=sha256.lower(),
        size_bytes=int(raw.get("size_bytes", 0)),
        original_path=str(raw.get("original_path")) if raw.get("original_path") is not None else None,
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


def is_external_media_file(path: str | Path) -> bool:
    return Path(path).suffix.lower() in EXTERNAL_MEDIA_EXTENSIONS


def _split_pack_inputs(files: Iterable[Path], *, externalize_media: bool) -> tuple[list[Path], list[Path]]:
    encodable: list[Path] = []
    external: list[Path] = []
    for path in files:
        if externalize_media and is_external_media_file(path):
            external.append(path)
        else:
            encodable.append(path)
    return encodable, external


def _sidecar_dir_for_pack(output: Path) -> Path:
    return output.with_suffix(".media")


def _sidecar_rel_for_pack(output: Path) -> str:
    return _sidecar_dir_for_pack(output).name


def _safe_export_folder_name(value: str) -> str:
    name = re.sub(r'[<>:"/\\|?*\x00-\x1f]+', "-", value).strip(" .-")
    return name or "spectrum-export"


def _unique_child_dir(parent: Path, name: str) -> Path:
    base = _safe_export_folder_name(name)
    candidate = parent / base
    suffix = 2
    while candidate.exists():
        candidate = parent / f"{base}-{suffix}"
        suffix += 1
    return candidate


def _copy_external_file(source: Path, sidecar_dir: Path) -> tuple[str, str, int]:
    digest = hashlib.sha256()
    size = 0
    with source.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            size += len(chunk)
            digest.update(chunk)
    sha256 = digest.hexdigest()
    suffix = source.suffix.lower()
    blob_rel = Path("blobs") / f"{sha256}{suffix}"
    target = sidecar_dir / blob_rel
    target.parent.mkdir(parents=True, exist_ok=True)
    if not target.exists():
        shutil.copy2(source, target)
    _write_restore_media(sidecar_dir, [])
    return blob_rel.as_posix(), sha256, size


def _write_restore_media(sidecar_dir: Path, entries: list[ExternalEntry]) -> None:
    sidecar_dir.mkdir(parents=True, exist_ok=True)
    restore_path = sidecar_dir / "restore_media.json"
    payload = {
        "format": "spectrum.restore-media",
        "version": 1,
        "entries": [_external_entry_to_manifest(entry) for entry in entries],
    }
    restore_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _copy_existing_external_entries(entries: list[ExternalEntry], from_pack: Path, to_pack: Path) -> list[ExternalEntry]:
    if not entries:
        return []
    from_sidecar = from_pack.parent
    to_sidecar = _sidecar_dir_for_pack(to_pack)
    copied: list[ExternalEntry] = []
    for entry in entries:
        source_blob = _safe_join(from_sidecar, entry.sidecar_path, field="sidecar")
        target_blob = to_sidecar / entry.blob
        target_blob.parent.mkdir(parents=True, exist_ok=True)
        if source_blob.exists() and source_blob.resolve() != target_blob.resolve():
            shutil.copy2(source_blob, target_blob)
        copied.append(
            ExternalEntry(
                source=entry.source,
                kind=entry.kind,
                sidecar_path=f"{to_sidecar.name}/{entry.blob}",
                blob=entry.blob,
                sha256=entry.sha256,
                size_bytes=entry.size_bytes,
                original_path=entry.original_path,
            )
        )
    _write_restore_media(to_sidecar, copied)
    return copied


def _external_entry_from_file(file_path: Path, rel: Path, output: Path) -> ExternalEntry:
    sidecar_dir = _sidecar_dir_for_pack(output)
    blob, sha256, size = _copy_external_file(file_path, sidecar_dir)
    source_name = _posix(rel)
    entry = ExternalEntry(
        source=source_name,
        kind="external_media",
        sidecar_path=f"{sidecar_dir.name}/{blob}",
        blob=blob,
        sha256=sha256,
        size_bytes=size,
        original_path=source_name,
    )
    return entry


def _looks_binary(path: Path, sample_size: int = 8192) -> bool:
    try:
        with path.open("rb") as handle:
            sample = handle.read(sample_size)
    except OSError:
        return False
    if b"\x00" in sample:
        return True
    try:
        sample.decode("utf-8")
    except UnicodeDecodeError:
        return True
    return False


def _encode_verified_or_external(
    file_path: Path,
    rel: Path,
    output: Path,
    tmp: Path,
    *,
    source_is_file: bool,
    language: str | int | None,
    rle: str,
    zlib_level: int,
    verbose: bool,
    externalize_media: bool,
    metadata_by_source: dict[str, dict[str, Any]] | None = None,
    ids_by_source: dict[str, str] | None = None,
) -> tuple[PackEntry | None, ExternalEntry | None]:
    source_name = _posix(rel)
    if externalize_media and (is_external_media_file(file_path) or _looks_binary(file_path)):
        return None, _external_entry_from_file(file_path, rel, output)

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

    verify_path = tmp / "_roundtrip" / (Path(file_path.name) if source_is_file else rel)
    verify_path.parent.mkdir(parents=True, exist_ok=True)
    decoded = decode_file(spec_path, verify_path, verbose=verbose)
    if not decoded.ok or verify_path.read_bytes() != file_path.read_bytes():
        if externalize_media:
            try:
                spec_path.unlink()
            except FileNotFoundError:
                pass
            return None, _external_entry_from_file(file_path, rel, output)
        raise ValueError(f"encoded file did not verify losslessly: {file_path}")

    return (
        PackEntry(
            source=source_name,
            spec=_posix(spec_rel),
            original_size=result.original_size,
            spec_size=result.spec_size,
            source_id=(ids_by_source or {}).get(source_name),
            metadata=(metadata_by_source or {}).get(source_name),
        ),
        None,
    )


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
    encrypt: bool = False,
    passphrase: str | None = None,
    kdf_profile: str = "interactive",
    hint: str | None = None,
    externalize_media: bool = True,
) -> dict:
    """Create a `.specpack` archive from a file or folder."""
    source = Path(input_path).resolve()
    output = Path(output_path).resolve()
    if not source.exists():
        raise FileNotFoundError(source)

    base = source.parent if source.is_file() else source
    files, external_files = _split_pack_inputs(iter_source_files(source, include_all=include_all), externalize_media=externalize_media)
    if not files and not external_files:
        raise ValueError(f"no encodable files found under {source}")

    with tempfile.TemporaryDirectory(prefix="spectrum-core-pack-") as tmp_name:
        tmp = Path(tmp_name)
        entries: list[PackEntry] = []
        external_entries: list[ExternalEntry] = []
        for file_path in files:
            rel = Path(file_path.name) if source.is_file() else file_path.relative_to(base)
            entry, external_entry = _encode_verified_or_external(
                file_path,
                rel,
                output,
                tmp,
                source_is_file=source.is_file(),
                language=language,
                rle=rle,
                zlib_level=zlib_level,
                verbose=verbose,
                externalize_media=externalize_media,
                metadata_by_source=metadata_by_source,
                ids_by_source=ids_by_source,
            )
            if entry is not None:
                entries.append(entry)
            if external_entry is not None:
                external_entries.append(external_entry)
        for file_path in external_files:
            rel = Path(file_path.name) if source.is_file() else file_path.relative_to(base)
            external_entries.append(_external_entry_from_file(file_path, rel, output))
        if external_entries:
            _write_restore_media(_sidecar_dir_for_pack(output), external_entries)

        manifest = {
            "format": PACK_FORMAT,
            "version": PACK_VERSION,
            "dict_version": D.DICT_VERSION,
            "source_root": source.name,
            "entries": [_entry_to_manifest(entry) for entry in entries],
            "external_entries": [_external_entry_to_manifest(entry) for entry in external_entries],
        }

        tmp_zip = tmp / output.name
        with zipfile.ZipFile(tmp_zip, "w", compression=PACK_COMPRESSION) as archive:
            archive.writestr("manifest.json", json.dumps(manifest, indent=2))
            for entry in entries:
                archive.write(tmp / entry.spec, entry.spec)

        _write_plain_or_encrypted(
            output,
            tmp_zip.read_bytes(),
            encrypt=encrypt,
            passphrase=passphrase,
            kdf_profile=kdf_profile,
            hint=hint,
        )

    return inspect_pack(output, passphrase=passphrase if encrypt else None)


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
    passphrase: str | None = None,
    kdf_profile: str | None = None,
    hint: str | None = None,
    externalize_media: bool = True,
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
    files, external_files = _split_pack_inputs(iter_source_files(source, include_all=include_all), externalize_media=externalize_media)
    if not files and not external_files:
        raise ValueError(f"no encodable files found under {source}")

    original_encrypted = is_encrypted_pack(pack_file)
    encrypted_info = inspect_encrypted_header(pack_file) if original_encrypted else None
    with SpectrumPack.open(pack_file, passphrase=passphrase) as opened:
        manifest = dict(opened.manifest)
        existing_entries = list(opened.entries)
        existing_external_entries = list(opened.external_entries)
        existing_members = set(opened._zip.namelist())

    existing_by_source = {entry.source: entry for entry in existing_entries}
    existing_external_by_source = {entry.source: entry for entry in existing_external_entries}
    new_sources: set[str] = set()
    encoded_entries: list[PackEntry] = []
    new_external_entries: list[ExternalEntry] = []

    with tempfile.TemporaryDirectory(prefix="spectrum-core-append-") as tmp_name:
        tmp = Path(tmp_name)
        for file_path in [*files, *external_files]:
            rel = Path(file_path.name) if source.is_file() else file_path.relative_to(base)
            source_name = _posix(rel)
            if source_name in new_sources:
                raise ValueError(f"duplicate appended source path: {source_name}")
            if (source_name in existing_by_source or source_name in existing_external_by_source) and not replace:
                raise ValueError(f"source already exists in pack: {source_name}")
            new_sources.add(source_name)
            if file_path in external_files:
                new_external_entries.append(_external_entry_from_file(file_path, rel, output))
                continue

            entry, external_entry = _encode_verified_or_external(
                file_path,
                rel,
                output,
                tmp,
                source_is_file=source.is_file(),
                language=language,
                rle=rle,
                zlib_level=zlib_level,
                verbose=verbose,
                externalize_media=externalize_media,
                metadata_by_source=metadata_by_source,
                ids_by_source=ids_by_source,
            )
            if entry is not None:
                if entry.spec in existing_members and source_name not in existing_by_source and not replace:
                    raise ValueError(f"spec member already exists in pack: {entry.spec}")
                encoded_entries.append(entry)
            if external_entry is not None:
                new_external_entries.append(external_entry)

        removed_specs = {
            existing_by_source[source_name].spec
            for source_name in new_sources
            if source_name in existing_by_source
        }
        removed_external = {
            source_name
            for source_name in new_sources
            if source_name in existing_external_by_source
        }
        kept_entries = [entry for entry in existing_entries if entry.source not in new_sources]
        kept_external_entries = [entry for entry in existing_external_entries if entry.source not in new_sources]
        kept_external_entries = _copy_existing_external_entries(kept_external_entries, pack_file, output)
        merged_entries = [*kept_entries, *encoded_entries]
        merged_external_entries = [*kept_external_entries, *new_external_entries]
        manifest["entries"] = [_entry_to_manifest(entry) for entry in merged_entries]
        manifest["external_entries"] = [_external_entry_to_manifest(entry) for entry in merged_external_entries]
        if merged_external_entries:
            _write_restore_media(_sidecar_dir_for_pack(output), merged_external_entries)

        tmp_zip = tmp / output.name
        with SpectrumPack.open(pack_file, passphrase=passphrase) as opened, zipfile.ZipFile(
            tmp_zip, "w", compression=PACK_COMPRESSION
        ) as target_archive:
            source_archive = opened._zip
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
        final_plain = tmp_zip.read_bytes()
        final_encrypted = original_encrypted
        final_profile = kdf_profile or (encrypted_info.kdf_profile if encrypted_info else "interactive") or "interactive"
        final_hint = hint if hint is not None else (encrypted_info.hint if encrypted_info else None)
        if output == pack_file:
            _write_plain_or_encrypted(
                pack_file,
                final_plain,
                encrypt=final_encrypted,
                passphrase=passphrase,
                kdf_profile=final_profile,
                hint=final_hint,
            )
        else:
            _write_plain_or_encrypted(
                output,
                final_plain,
                encrypt=final_encrypted,
                passphrase=passphrase,
                kdf_profile=final_profile,
                hint=final_hint,
            )

    summary = inspect_pack(output, passphrase=passphrase if original_encrypted else None)
    summary["appended_entries"] = len(encoded_entries) + len(new_external_entries)
    summary["appended_encoded_entries"] = len(encoded_entries)
    summary["appended_external_entries"] = len(new_external_entries)
    summary["replaced_entries"] = len(removed_specs) + len(removed_external)
    summary["replaced_encoded_entries"] = len(removed_specs)
    summary["replaced_external_entries"] = len(removed_external)
    summary["dropped_embedded_index"] = PACK_INDEX_NAME in existing_members
    return summary


def unpack(
    pack_path: str | Path,
    output_dir: str | Path,
    *,
    verbose: bool = False,
    passphrase: str | None = None,
) -> list[DecodeResult]:
    """Decode all entries in a `.specpack` archive to an output directory."""
    target = Path(output_dir)
    results: list[DecodeResult] = []
    with SpectrumPack.open(pack_path, passphrase=passphrase) as opened:
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
            opened.restore_external_files(target)
    return results


def export_distributable(
    pack_path: str | Path,
    parent_dir: str | Path,
    *,
    folder_name: str | None = None,
    verbose: bool = False,
    passphrase: str | None = None,
) -> dict[str, Any]:
    """Restore a `.specpack` into a new project folder under ``parent_dir``."""
    pack_file = Path(pack_path).expanduser().resolve()
    parent = Path(parent_dir).expanduser().resolve()
    if not parent.exists():
        raise FileNotFoundError(parent)
    if not parent.is_dir():
        raise NotADirectoryError(parent)

    with SpectrumPack.open(pack_file, passphrase=passphrase) as opened:
        source_root = str(opened.manifest.get("source_root") or "").strip()
        encoded_count = len(opened.entries)
        external_count = len(opened.external_entries)

    root_name = folder_name or source_root or pack_file.stem
    target = _unique_child_dir(parent, root_name)
    target.mkdir(parents=True)
    try:
        results = unpack(pack_file, target, verbose=verbose, passphrase=passphrase)
    except Exception:
        shutil.rmtree(target, ignore_errors=True)
        raise

    restored_encoded = sum(1 for result in results if result.ok)
    restored_files = sum(1 for path in target.rglob("*") if path.is_file())
    return {
        "pack_path": str(pack_file),
        "output_dir": str(target),
        "source_root": source_root,
        "encoded_entries": encoded_count,
        "external_entries": external_count,
        "restored_encoded_entries": restored_encoded,
        "restored_files": restored_files,
        "valid": restored_encoded == encoded_count,
        "results": results,
    }


def decode_member(
    pack_path: str | Path,
    source: str,
    output_path: str | Path,
    *,
    verbose: bool = False,
    passphrase: str | None = None,
) -> DecodeResult:
    """Decode one source member from a `.specpack` archive."""
    with SpectrumPack.open(pack_path, passphrase=passphrase) as opened:
        entry = opened.find_entry(source)
        if entry is None:
            raise FileNotFoundError(f"source member not found: {source}")
        with tempfile.TemporaryDirectory(prefix="spectrum-core-member-") as tmp_name:
            spec_path = opened.extract_spec(entry, Path(tmp_name))
            return decode_file(spec_path, output_path, verbose=verbose)


def inspect_pack(pack_path: str | Path, *, passphrase: str | None = None) -> dict:
    path = Path(pack_path)
    if is_encrypted_pack(path) and passphrase is None:
        info = inspect_encrypted_header(path).to_dict()
        return {
            "path": str(path),
            "format": "spectrum.encrypted-specpack",
            "encrypted": True,
            "locked": True,
            "pack_size": path.stat().st_size,
            **info,
        }
    archive, buffer = _open_zip_from_path(path, passphrase)
    try:
        summary = _inspect_archive(path, archive, pack_size=path.stat().st_size)
    finally:
        archive.close()
        if buffer is not None:
            buffer.close()
    summary["encrypted"] = is_encrypted_pack(path)
    summary["locked"] = False
    return summary


class SpectrumPack:
    """Reader for Spectrum `.specpack` archives."""

    def __init__(self, path: Path, archive: zipfile.ZipFile, manifest: dict, buffer: io.BytesIO | None = None):
        self.path = path
        self._zip = archive
        self._buffer = buffer
        self.manifest = manifest
        members = set(archive.namelist())
        self.entries = [_validate_entry(entry, members) for entry in manifest.get("entries", [])]
        self.external_entries = [_validate_external_entry(entry) for entry in manifest.get("external_entries", [])]

    @classmethod
    def open(cls, path: str | Path, *, passphrase: str | None = None) -> "SpectrumPack":
        pack_path = Path(path)
        archive, buffer = _open_zip_from_path(pack_path, passphrase)
        try:
            manifest = _load_manifest(archive)
            return cls(pack_path, archive, manifest, buffer)
        except Exception:
            archive.close()
            if buffer is not None:
                buffer.close()
            raise

    def close(self) -> None:
        self._zip.close()
        if self._buffer is not None:
            self._buffer.close()

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

    def external_blob_path(self, entry: ExternalEntry) -> Path:
        return _safe_join(self.path.parent, entry.sidecar_path, field="sidecar")

    def restore_external_files(self, output_dir: str | Path) -> list[Path]:
        restored: list[Path] = []
        root = Path(output_dir)
        for entry in self.external_entries:
            blob = self.external_blob_path(entry)
            if not blob.exists():
                raise FileNotFoundError(f"external media sidecar missing: {blob}")
            size = 0
            digest = hashlib.sha256()
            target = _safe_join(root, entry.source, field="source")
            target.parent.mkdir(parents=True, exist_ok=True)
            with blob.open("rb") as source_handle, target.open("wb") as target_handle:
                for chunk in iter(lambda: source_handle.read(1024 * 1024), b""):
                    size += len(chunk)
                    digest.update(chunk)
                    target_handle.write(chunk)
            if size != entry.size_bytes:
                raise ValueError(f"external media size mismatch: {entry.source}")
            if digest.hexdigest() != entry.sha256:
                raise ValueError(f"external media checksum mismatch: {entry.source}")
            restored.append(target)
        return restored
