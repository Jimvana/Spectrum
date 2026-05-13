from __future__ import annotations

import tempfile
from dataclasses import dataclass
from pathlib import Path

from .pack import SpectrumPack
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


def verify_pack(pack_path: str | Path) -> ValidationReport:
    results: list[tuple[str, DecodeResult]] = []
    with tempfile.TemporaryDirectory(prefix="spectrum-core-verify-pack-") as tmp_name:
        tmp = Path(tmp_name)
        with SpectrumPack.open(pack_path) as opened:
            for entry in opened.entries:
                spec_path = opened.extract_spec(entry, tmp / "pack")
                result = decode_file(spec_path, tmp / "decoded" / entry.source)
                results.append((entry.source, result))
    return _report(results)


def verify_path(path: str | Path) -> ValidationReport:
    target = Path(path)
    if target.suffix.lower() == ".specpack":
        return verify_pack(target)
    if target.is_dir():
        results: list[tuple[str, DecodeResult]] = []
        with tempfile.TemporaryDirectory(prefix="spectrum-core-verify-dir-") as tmp_name:
            tmp = Path(tmp_name)
            for spec in sorted(target.rglob("*.spec")):
                result = decode_file(spec, tmp / spec.relative_to(target))
                results.append((str(spec), result))
        return _report(results)
    return verify_spec(target)
