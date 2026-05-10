from __future__ import annotations

import json
from pathlib import Path

from spectrum_cli.main import main


def test_cli_pack_inspect_unpack_verify(tmp_path: Path, capsys) -> None:
    docs = tmp_path / "docs"
    docs.mkdir()
    (docs / "note.md").write_bytes(b"# Note\r\n\r\nCLI package round trip.\r\n")
    pack_path = tmp_path / "docs.specpack"
    decoded = tmp_path / "decoded"

    assert main(["pack", str(docs), str(pack_path), "--json"]) == 0
    pack_output = json.loads(capsys.readouterr().out)
    assert pack_output["entries"] == 1

    assert main(["inspect", str(pack_path), "--json"]) == 0
    inspect_output = json.loads(capsys.readouterr().out)
    assert inspect_output["format"] == "spectrum.specpack"

    assert main(["unpack", str(pack_path), str(decoded), "--json"]) == 0
    unpack_output = json.loads(capsys.readouterr().out)
    assert unpack_output[0]["checksum_ok"]
    assert (decoded / "note.md").read_bytes() == (docs / "note.md").read_bytes()

    assert main(["verify", str(pack_path), "--json"]) == 0
    verify_output = json.loads(capsys.readouterr().out)
    assert verify_output["valid"]
