from __future__ import annotations

import tempfile
import hashlib
from dataclasses import dataclass
from pathlib import Path

from .pack import ExternalEntry, PackEntry, SpectrumPack
from .spec import DecodeResult, decode_file


@dataclass(frozen=True)
class ValidationReport:
    valid: bool
    chunks_checked: int
    decode_passed: int
    decode_failed: int
    failures: tuple[str, ...] = ()

    def to_dict(self) -> dict:
        return {
            "valid": self.valid,
            "chunks_checked": self.chunks_checked,
            "decode_passed": self.decode_passed,
            "decode_failed": self.decode_failed,
            "failures": list(self.failures),
        }


def _report(results: list[tuple[str, DecodeResult]]) -> ValidationReport:
    failures = tuple(name for name, result in results if not result.ok)
    return ValidationReport(
        valid=not failures,
        chunks_checked=len(results),
        decode_passed=len(results) - len(failures),
        decode_failed=len(failures),
        failures=failures,
    )


def verify_spec(spec_path: str | Path) -> ValidationReport:
    spec = Path(spec_path)
    with tempfile.TemporaryDirectory(prefix="spectrum-core-verify-") as tmp_name:
        result = decode_file(spec, Path(tmp_name) / spec.stem)
    return _report([(str(spec), result)])


def verify_pack(pack_path: str | Path, *, passphrase: str | None = None) -> ValidationReport:
    results: list[tuple[str, DecodeResult]] = []
    external_failures: list[str] = []
    external_checked = 0
    with tempfile.TemporaryDirectory(prefix="spectrum-core-verify-pack-") as tmp_name:
        tmp = Path(tmp_name)
        with SpectrumPack.open(pack_path, passphrase=passphrase) as opened:
            for entry in opened.entries:
                spec_path = opened.extract_spec(entry, tmp / "pack")
                result = decode_file(spec_path, tmp / "decoded" / entry.source)
                results.append((entry.source, result))
            for entry in opened.external_entries:
                external_checked += 1
                blob = opened.external_blob_path(entry)
                if not blob.exists():
                    external_failures.append(f"{entry.source}: missing sidecar")
                    continue
                size = 0
                digest = hashlib.sha256()
                with blob.open("rb") as handle:
                    for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                        size += len(chunk)
                        digest.update(chunk)
                if size != entry.size_bytes:
                    external_failures.append(f"{entry.source}: size mismatch")
                    continue
                if digest.hexdigest() != entry.sha256:
                    external_failures.append(f"{entry.source}: checksum mismatch")
    report = _report(results)
    failures = (*report.failures, *external_failures)
    return ValidationReport(
        valid=not failures,
        chunks_checked=report.chunks_checked + external_checked,
        decode_passed=report.decode_passed,
        decode_failed=report.decode_failed + len(external_failures),
        failures=failures,
    )


def _verify_external_entry(opened: SpectrumPack, entry: ExternalEntry) -> str | None:
    blob = opened.external_blob_path(entry)
    if not blob.exists():
        return f"{entry.source}: missing sidecar"
    size = 0
    digest = hashlib.sha256()
    with blob.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            size += len(chunk)
            digest.update(chunk)
    if size != entry.size_bytes:
        return f"{entry.source}: size mismatch"
    if digest.hexdigest() != entry.sha256:
        return f"{entry.source}: checksum mismatch"
    return None


def verify_pack_sources(
    pack_path: str | Path,
    source_paths: list[str] | tuple[str, ...] | set[str],
    *,
    passphrase: str | None = None,
) -> ValidationReport:
    """Verify only selected pack sources.

    Encoded entries are decoded and external entries have their sidecar blob
    size/checksum checked. This is intended for append/upsert workflows that
    already know which sources changed.
    """
    wanted = {str(path).replace("\\", "/") for path in source_paths}
    results: list[tuple[str, DecodeResult]] = []
    failures: list[str] = []
    external_checked = 0
    with tempfile.TemporaryDirectory(prefix="spectrum-core-verify-changed-") as tmp_name:
        tmp = Path(tmp_name)
        with SpectrumPack.open(pack_path, passphrase=passphrase) as opened:
            encoded_by_source: dict[str, PackEntry] = {entry.source: entry for entry in opened.entries}
            external_by_source: dict[str, ExternalEntry] = {entry.source: entry for entry in opened.external_entries}
            for source in sorted(wanted):
                entry = encoded_by_source.get(source)
                if entry is not None:
                    spec_path = opened.extract_spec(entry, tmp / "pack")
                    result = decode_file(spec_path, tmp / "decoded" / entry.source)
                    results.append((entry.source, result))
                    continue
                external = external_by_source.get(source)
                if external is not None:
                    external_checked += 1
                    failure = _verify_external_entry(opened, external)
                    if failure is not None:
                        failures.append(failure)
                    continue
                failures.append(f"{source}: missing from pack")

    report = _report(results)
    all_failures = (*report.failures, *failures)
    return ValidationReport(
        valid=not all_failures,
        chunks_checked=report.chunks_checked + external_checked,
        decode_passed=report.decode_passed,
        decode_failed=report.decode_failed + len(failures),
        failures=all_failures,
    )


def verify_path(path: str | Path, *, passphrase: str | None = None) -> ValidationReport:
    target = Path(path)
    if target.suffix.lower() == ".specpack":
        return verify_pack(target, passphrase=passphrase)
    if target.is_dir():
        results: list[tuple[str, DecodeResult]] = []
        with tempfile.TemporaryDirectory(prefix="spectrum-core-verify-dir-") as tmp_name:
            tmp = Path(tmp_name)
            for spec in sorted(target.rglob("*.spec")):
                result = decode_file(spec, tmp / spec.relative_to(target))
                results.append((str(spec), result))
        return _report(results)
    return verify_spec(target)
