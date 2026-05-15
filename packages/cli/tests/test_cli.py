from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

from spectrum_cli.main import main


ROOT = Path(__file__).resolve().parents[3]


def test_cli_help_does_not_import_image_dependencies() -> None:
    env = os.environ.copy()
    env["PYTHONPATH"] = os.pathsep.join(
        str(path)
        for path in [
            ROOT / "packages/core/src",
            ROOT / "packages/index/src",
            ROOT / "packages/cli/src",
        ]
    )
    code = """
import importlib.abc
import sys

class BlockPIL(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        if fullname == "PIL" or fullname.startswith("PIL."):
            raise ModuleNotFoundError("blocked PIL")
        return None

sys.meta_path.insert(0, BlockPIL())
from spectrum_cli.main import main
raise SystemExit(main(["--help"]))
"""
    result = subprocess.run(
        [sys.executable, "-c", code],
        cwd=ROOT,
        env=env,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    assert result.returncode == 0, result.stderr
    assert "Spectrum Store Developer Preview" in result.stdout


def test_cli_doctor_reports_install_health(capsys) -> None:
    assert main(["doctor", "--json"]) == 0
    output = json.loads(capsys.readouterr().out)
    assert output["ok"]
    check_names = {check["name"] for check in output["checks"]}
    assert "python" in check_names
    assert "spectrum-runtime" in check_names
    assert "temp-write" in check_names


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


def test_cli_load_dry_run_prints_walkthrough(tmp_path: Path, capsys) -> None:
    docs = tmp_path / "docs"
    docs.mkdir()
    pack_path = tmp_path / "docs.specpack"

    assert main(["load", str(docs), str(pack_path), "--dry-run", "--no-color"]) == 0
    output = capsys.readouterr().out
    assert "Spectrum load will walk you through" in output
    assert "spectrum doctor" in output
    assert f"spectrum pack {docs} {pack_path} --json" in output
    assert f"spectrum serve {pack_path} --port 7777" in output
    assert "Dry run only" in output


def test_cli_load_can_pack_without_serving(tmp_path: Path, capsys) -> None:
    docs = tmp_path / "docs"
    docs.mkdir()
    (docs / "note.md").write_text("Guided load packs this repo.\n", encoding="utf-8")
    pack_path = tmp_path / "docs.specpack"

    assert main(["load", str(docs), str(pack_path), "--yes", "--no-serve", "--no-color"]) == 0
    output = capsys.readouterr().out
    assert pack_path.exists()
    assert "Spectrum doctor: ok" in output
    assert "Pack ready:" in output
    assert f"Start it later with: spectrum serve {pack_path} --port 7777" in output


def test_cli_load_appends_specpack_suffix_for_bare_output(tmp_path: Path, capsys) -> None:
    docs = tmp_path / "docs"
    docs.mkdir()
    pack_base = tmp_path / "output"

    assert main(["load", str(docs), str(pack_base), "--dry-run", "--no-color"]) == 0
    output = capsys.readouterr().out
    assert f"spectrum pack {docs} {pack_base}.specpack --json" in output
    assert f"spectrum serve {pack_base}.specpack --port 7777" in output


def test_cli_load_rejects_non_specpack_extension(tmp_path: Path, capsys) -> None:
    docs = tmp_path / "docs"
    docs.mkdir()
    output = tmp_path / "output.zip"

    assert main(["load", str(docs), str(output), "--dry-run", "--no-color"]) == 1
    assert "output path must end with .specpack" in capsys.readouterr().err
