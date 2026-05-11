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


def test_cli_index_and_search(tmp_path: Path, capsys) -> None:
    docs = tmp_path / "docs"
    docs.mkdir()
    (docs / "auth.md").write_text("Authentication middleware validates bearer tokens.\n", encoding="utf-8")
    (docs / "billing.md").write_text("Payment records and invoice exports.\n", encoding="utf-8")
    pack_path = tmp_path / "docs.specpack"

    assert main(["pack", str(docs), str(pack_path), "--json"]) == 0
    capsys.readouterr()

    assert main(["index", str(pack_path), "--embed", "--json"]) == 0
    index_output = json.loads(capsys.readouterr().out)
    assert index_output["embedded"]

    assert main(["search", str(pack_path), "authentication bearer middleware", "--top", "1", "--json"]) == 0
    search_output = json.loads(capsys.readouterr().out)
    assert search_output[0]["path"].endswith("auth.md.spec")
    assert search_output[0]["source_path"] == "auth.md"
