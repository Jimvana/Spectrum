from __future__ import annotations

from pathlib import Path

from spectrum_core import (
    SpectrumPack,
    decode_file,
    encode_file,
    inspect_pack,
    inspect_spec,
    pack,
    unpack,
    verify_pack,
    verify_spec,
)


def test_spec_round_trip(tmp_path: Path) -> None:
    source = tmp_path / "hello.py"
    source.write_bytes(b"def hello(name):\r\n    return f'hello {name}'\r\n")
    spec = tmp_path / "hello.py.spec"
    decoded = tmp_path / "decoded.py"

    encoded = encode_file(source, spec)
    info = inspect_spec(spec)
    result = decode_file(spec, decoded)
    report = verify_spec(spec)

    source_bytes = source.read_bytes()
    assert encoded.original_size == len(source_bytes)
    assert info.original_bytes == encoded.original_size
    assert result.ok
    assert decoded.read_bytes() == source_bytes
    assert report.valid
    assert report.chunks_checked == 1


def test_pack_round_trip(tmp_path: Path) -> None:
    source_dir = tmp_path / "docs"
    source_dir.mkdir()
    (source_dir / "README.md").write_bytes(b"# Demo\r\n\r\nSpectrum memory notes.\r\n")
    nested = source_dir / "src"
    nested.mkdir()
    (nested / "app.js").write_text("export const value = 42;\n", encoding="utf-8")

    pack_path = tmp_path / "docs.specpack"
    decoded_dir = tmp_path / "decoded"

    summary = pack(source_dir, pack_path)
    inspected = inspect_pack(pack_path)
    results = unpack(pack_path, decoded_dir)
    report = verify_pack(pack_path)

    assert summary["entries"] == 2
    assert inspected["format"] == "spectrum.specpack"
    assert inspected["entries"] == 2
    assert len(results) == 2
    assert all(result.ok for result in results)
    assert (decoded_dir / "README.md").read_bytes() == (source_dir / "README.md").read_bytes()
    assert (decoded_dir / "src" / "app.js").read_bytes() == (nested / "app.js").read_bytes()
    assert report.valid

    with SpectrumPack.open(pack_path) as opened:
        assert len(opened.entries) == 2
        assert opened.read_spec(opened.entries[0]).startswith(b"SPEC")
