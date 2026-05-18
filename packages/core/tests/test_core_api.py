from __future__ import annotations

import json
import zipfile
from pathlib import Path

from spectrum_core import (
    SpectrumPack,
    append_to_pack,
    decode_member,
    decode_file,
    encode_file,
    encrypt_pack_bytes,
    decrypt_pack_bytes,
    inspect_pack,
    inspect_encrypted_header,
    is_encrypted_pack,
    inspect_spec,
    pack,
    unpack,
    verify_pack,
    verify_spec,
)
from spectrum_core.pack import iter_source_files


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


def test_encrypted_pack_round_trip_requires_passphrase(tmp_path: Path) -> None:
    source_dir = tmp_path / "docs"
    source_dir.mkdir()
    (source_dir / "README.md").write_text("# Secret\n\nDeploy notes.\n", encoding="utf-8")
    pack_path = tmp_path / "docs.specpack"
    decoded_dir = tmp_path / "decoded"

    summary = pack(source_dir, pack_path, encrypt=True, passphrase="six uncommon words here", hint="test hint")
    locked = inspect_pack(pack_path)

    assert is_encrypted_pack(pack_path)
    assert summary["encrypted"] is True
    assert locked["format"] == "spectrum.encrypted-specpack"
    assert locked["locked"] is True
    assert locked["hint"] == "test hint"
    assert inspect_encrypted_header(pack_path).hint == "test hint"

    try:
        SpectrumPack.open(pack_path)
    except ValueError as exc:
        assert "locked" in str(exc)
    else:
        raise AssertionError("encrypted pack opened without a passphrase")

    unlocked = inspect_pack(pack_path, passphrase="six uncommon words here")
    results = unpack(pack_path, decoded_dir, passphrase="six uncommon words here")
    report = verify_pack(pack_path, passphrase="six uncommon words here")

    assert unlocked["entries"] == 1
    assert all(result.ok for result in results)
    assert (decoded_dir / "README.md").read_text(encoding="utf-8") == "# Secret\n\nDeploy notes.\n"
    assert report.valid


def test_encrypted_pack_wrong_passphrase_and_tamper_fail(tmp_path: Path) -> None:
    plain = b"PK\x03\x04not really a pack but authenticated bytes"
    encrypted = encrypt_pack_bytes(plain, "correct horse battery staple")

    try:
        decrypt_pack_bytes(encrypted, "wrong passphrase")
    except ValueError as exc:
        assert "authentication failed" in str(exc)
    else:
        raise AssertionError("wrong passphrase decrypted encrypted bytes")

    tampered = encrypted[:-1] + bytes([encrypted[-1] ^ 1])
    try:
        decrypt_pack_bytes(tampered, "correct horse battery staple")
    except ValueError as exc:
        assert "authentication failed" in str(exc)
    else:
        raise AssertionError("tampered encrypted bytes decrypted")


def test_iter_source_files_skips_media_and_macos_library_dirs(tmp_path: Path) -> None:
    source_dir = tmp_path / "Desktop"
    source_dir.mkdir()
    (source_dir / "note.md").write_text("Text should be packed.\n", encoding="utf-8")
    (source_dir / "photo.jpg").write_bytes(b"not text")
    photos = source_dir / "Photos Library.photoslibrary"
    photos.mkdir()
    (photos / "metadata.json").write_text('{"should": "skip"}\n', encoding="utf-8")
    music = source_dir / "Music"
    music.mkdir()
    (music / "lyrics.txt").write_text("Do not scan protected media folders.\n", encoding="utf-8")

    files = [path.relative_to(source_dir).as_posix() for path in iter_source_files(source_dir, include_all=True)]

    assert files == ["note.md"]


def test_pack_rejects_unsafe_manifest_paths(tmp_path: Path) -> None:
    source_dir = tmp_path / "docs"
    source_dir.mkdir()
    (source_dir / "note.md").write_text("Safe text.\n", encoding="utf-8")
    good_pack = tmp_path / "good.specpack"
    bad_pack = tmp_path / "bad.specpack"
    pack(source_dir, good_pack)

    with zipfile.ZipFile(good_pack) as src, zipfile.ZipFile(bad_pack, "w") as dst:
        manifest = json.loads(src.read("manifest.json").decode("utf-8"))
        manifest["entries"][0]["source"] = "../escaped.md"
        dst.writestr("manifest.json", json.dumps(manifest))
        for item in src.infolist():
            if item.filename != "manifest.json":
                dst.writestr(item, src.read(item.filename))

    try:
        SpectrumPack.open(bad_pack)
    except ValueError as exc:
        assert "unsafe source path" in str(exc)
    else:
        raise AssertionError("unsafe pack manifest was accepted")


def test_decode_member_decodes_one_source(tmp_path: Path) -> None:
    source_dir = tmp_path / "docs"
    nested = source_dir / "notes"
    nested.mkdir(parents=True)
    (nested / "memory.md").write_text("Selective hydration works.\n", encoding="utf-8")
    pack_path = tmp_path / "docs.specpack"
    output = tmp_path / "memory.md"
    pack(source_dir, pack_path)

    result = decode_member(pack_path, "notes/memory.md", output)

    assert result.ok
    assert output.read_text(encoding="utf-8") == "Selective hydration works.\n"


def test_append_to_pack_preserves_existing_and_adds_new_source(tmp_path: Path) -> None:
    source_dir = tmp_path / "docs"
    source_dir.mkdir()
    (source_dir / "README.md").write_bytes(b"# Demo\r\n")
    pack_path = tmp_path / "docs.specpack"
    pack(source_dir, pack_path)

    append_dir = tmp_path / "append"
    append_dir.mkdir()
    (append_dir / "agent.md").write_text("SSH alias and deploy notes.\n", encoding="utf-8")

    summary = append_to_pack(pack_path, append_dir)
    decoded_dir = tmp_path / "decoded"
    results = unpack(pack_path, decoded_dir)

    assert summary["entries"] == 2
    assert summary["appended_entries"] == 1
    assert summary["replaced_entries"] == 0
    assert all(result.ok for result in results)
    assert (decoded_dir / "README.md").read_bytes() == b"# Demo\r\n"
    assert (decoded_dir / "agent.md").read_text(encoding="utf-8") == "SSH alias and deploy notes.\n"


def test_append_to_pack_rejects_conflicts_unless_replace(tmp_path: Path) -> None:
    source_dir = tmp_path / "docs"
    source_dir.mkdir()
    note = source_dir / "note.md"
    note.write_text("old\n", encoding="utf-8")
    pack_path = tmp_path / "docs.specpack"
    pack(source_dir, pack_path)

    note.write_text("new\n", encoding="utf-8")
    try:
        append_to_pack(pack_path, note)
    except ValueError as exc:
        assert "source already exists" in str(exc)
    else:
        raise AssertionError("append accepted a duplicate source path without replace")

    summary = append_to_pack(pack_path, note, replace=True)
    output = tmp_path / "note.md"
    result = decode_member(pack_path, "note.md", output)

    assert summary["entries"] == 1
    assert summary["replaced_entries"] == 1
    assert result.ok
    assert output.read_text(encoding="utf-8") == "new\n"
