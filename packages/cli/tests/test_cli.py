from __future__ import annotations

import json
import os
import socket
import subprocess
import sys
import threading
from pathlib import Path

from spectrum_core import pack
from spectrum_cli.main import main
from spectrum_server.app import PackRegistry, SpectrumServer, create_handler


ROOT = Path(__file__).resolve().parents[3]


def unused_local_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


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


def test_cli_append_adds_documents_to_existing_pack(tmp_path: Path, capsys) -> None:
    docs = tmp_path / "docs"
    docs.mkdir()
    (docs / "note.md").write_text("Original context.\n", encoding="utf-8")
    pack_path = tmp_path / "docs.specpack"
    decoded = tmp_path / "decoded"
    extra = tmp_path / "extra"
    extra.mkdir()
    (extra / "deploy.md").write_text("Deploy context grows here.\n", encoding="utf-8")

    assert main(["pack", str(docs), str(pack_path), "--json"]) == 0
    capsys.readouterr()

    assert main(["append", str(pack_path), str(extra), "--json"]) == 0
    append_output = json.loads(capsys.readouterr().out)
    assert append_output["entries"] == 2
    assert append_output["appended_entries"] == 1

    assert main(["unpack", str(pack_path), str(decoded), "--json"]) == 0
    capsys.readouterr()
    assert (decoded / "note.md").read_text(encoding="utf-8") == "Original context.\n"
    assert (decoded / "deploy.md").read_text(encoding="utf-8") == "Deploy context grows here.\n"


def test_cli_project_init_and_add_create_portable_pack(tmp_path: Path, capsys) -> None:
    project = tmp_path / "site"
    project.mkdir()
    (project / "app.py").write_text("print('hello')\n", encoding="utf-8")
    pack_path = tmp_path / "site.specpack"

    assert main(["project", "init", str(project), str(pack_path), "--name", "Site", "--no-index", "--json"]) == 0
    init_output = json.loads(capsys.readouterr().out)
    assert init_output["name"] == "Site"
    assert pack_path.exists()
    assert not (project / ".spectrum-project").exists()
    assert ".spectrum-project/project.md" in init_output["created_files"]
    assert ".spectrum-project/ops.json" in init_output["created_files"]

    decoded = tmp_path / "project-init-decoded"
    assert main(["unpack", str(pack_path), str(decoded), "--json"]) == 0
    capsys.readouterr()
    assert (decoded / ".spectrum-project" / "project.md").exists()
    ops = json.loads((decoded / ".spectrum-project" / "ops.json").read_text(encoding="utf-8"))
    assert ops["project"]["name"] == "Site"
    assert ops["policy"]["ssh_requires_confirmation"]
    assert init_output["verify"]["valid"]
    launcher_names = {Path(path).name for path in init_output["launcher_files"]}
    assert {"start.cmd", "start.ps1", "start.command", "start.sh", "README.md", "metadata.json"} <= launcher_names

    notes = tmp_path / "notes"
    notes.mkdir()
    (notes / "handoff.md").write_text("Remember the production deploy check.\n", encoding="utf-8")
    assert main(["project", "add", str(pack_path), str(notes), "--no-index", "--json"]) == 0
    add_output = json.loads(capsys.readouterr().out)
    assert add_output["append"]["appended_entries"] == 1
    assert add_output["verify"]["valid"]


def test_cli_project_init_defaults_pack_to_spectrum_folder(tmp_path: Path, capsys) -> None:
    project = tmp_path / "site"
    project.mkdir()
    (project / "index.html").write_text("<h1>Site</h1>\n", encoding="utf-8")

    assert main(["project", "init", str(project), "--name", "Site", "--no-index", "--json"]) == 0
    output = json.loads(capsys.readouterr().out)
    runtime = project / ".spectrum"
    pack_path = runtime / "project.specpack"

    assert Path(output["pack"]) == pack_path.resolve()
    assert pack_path.exists()
    assert (runtime / "start.cmd").exists()
    assert (runtime / "start.ps1").exists()
    assert (runtime / "start.command").exists()
    assert (runtime / "start.sh").exists()
    assert (runtime / "README.md").exists()
    metadata = json.loads((runtime / "metadata.json").read_text(encoding="utf-8"))
    assert metadata["pack"] == "project.specpack"
    assert metadata["dashboard_url"] == "http://127.0.0.1:7777/project"


def test_cli_hub_build_creates_pack_without_serving(tmp_path: Path, capsys) -> None:
    project = tmp_path / "hub-site"
    project.mkdir()
    (project / "index.html").write_text("<h1>Hub</h1>\n", encoding="utf-8")
    pack_path = tmp_path / "hub.specpack"

    assert (
        main(
            [
                "hub",
                "-b",
                "--source",
                str(project),
                "--name",
                "Hub Site",
                "--pack",
                str(pack_path),
                "--no-serve",
                "--json",
            ]
        )
        == 0
    )
    output = capsys.readouterr().out
    assert "Start it later with:" in output
    assert pack_path.exists()
    assert (pack_path.parent / "start.cmd").exists()


def test_cli_hub_verify_finds_running_server(tmp_path: Path, capsys) -> None:
    docs = tmp_path / "docs"
    docs.mkdir()
    (docs / "note.md").write_text("Hub verify server.\n", encoding="utf-8")
    pack_path = tmp_path / "docs.specpack"
    pack(docs, pack_path)

    registry = PackRegistry()
    registry.add("repo", pack_path)
    server = SpectrumServer(("127.0.0.1", 0), create_handler(registry), quiet=True)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    port = server.server_address[1]

    try:
        assert main(["hub", "-v", "--ports", str(port), "--json"]) == 0
        output = json.loads(capsys.readouterr().out)
        assert output["servers"][0]["running"]
        assert output["servers"][0]["packs"][0]["id"] == "repo"
        assert output["servers"][0]["dashboard_url"] == f"http://127.0.0.1:{port}/project"
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


def test_cli_hub_verify_reports_no_running_servers(capsys) -> None:
    port = unused_local_port()

    assert main(["hub", "-v", "--ports", str(port)]) == 0

    output = capsys.readouterr().out
    assert output.strip() == "No spectrum servers operating"
    assert "not running" not in output


def test_cli_hub_verify_discovers_running_server(tmp_path: Path, capsys, monkeypatch) -> None:
    import spectrum_cli.main as cli_main

    docs = tmp_path / "docs"
    docs.mkdir()
    (docs / "note.md").write_text("Hub discovery server.\n", encoding="utf-8")
    pack_path = tmp_path / "docs.specpack"
    pack(docs, pack_path)

    registry = PackRegistry()
    registry.add("repo", pack_path)
    server = SpectrumServer(("127.0.0.1", 0), create_handler(registry), quiet=True)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    port = server.server_address[1]

    try:
        monkeypatch.setattr(cli_main, "_discover_listening_tcp_ports", lambda: [port])
        assert main(["hub", "-v", "--json"]) == 0
        output = json.loads(capsys.readouterr().out)
        running_ports = {server_info["port"] for server_info in output["running"]}
        assert port in running_ports
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


def test_cli_project_serve_reports_existing_different_pack(tmp_path: Path, capsys) -> None:
    docs = tmp_path / "docs"
    docs.mkdir()
    (docs / "note.md").write_text("Already served.\n", encoding="utf-8")
    served_pack = tmp_path / "served.specpack"
    pack(docs, served_pack)

    other = tmp_path / "other"
    other.mkdir()
    (other / "note.md").write_text("Requested pack.\n", encoding="utf-8")
    requested_pack = tmp_path / "requested.specpack"
    pack(other, requested_pack)

    registry = PackRegistry()
    registry.add("repo", served_pack)
    server = SpectrumServer(("127.0.0.1", 0), create_handler(registry), quiet=True)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    port = server.server_address[1]

    try:
        assert main(["project", "serve", str(requested_pack), "--port", str(port)]) == 1
        err = capsys.readouterr().err
        assert "already has a Spectrum server running" in err
        assert str(served_pack.resolve()) in err
        assert str(requested_pack.resolve()) in err
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


def test_cli_project_restart_can_stop_existing_server(tmp_path: Path, capsys) -> None:
    docs = tmp_path / "docs"
    docs.mkdir()
    (docs / "note.md").write_text("Restart server.\n", encoding="utf-8")
    pack_path = tmp_path / "docs.specpack"
    pack(docs, pack_path)

    registry = PackRegistry()
    registry.add("repo", pack_path)
    server = SpectrumServer(("127.0.0.1", 0), create_handler(registry), quiet=True)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    port = server.server_address[1]

    try:
        assert main(["project", "restart", str(pack_path), "--port", str(port), "--no-start"]) == 0
        assert "stopped Spectrum server" in capsys.readouterr().err
        thread.join(timeout=5)
        assert not thread.is_alive()
    finally:
        server.server_close()


def test_cli_project_restart_rejects_different_pack_without_force(tmp_path: Path, capsys) -> None:
    docs = tmp_path / "docs"
    docs.mkdir()
    (docs / "note.md").write_text("Served pack.\n", encoding="utf-8")
    served_pack = tmp_path / "served.specpack"
    pack(docs, served_pack)

    other = tmp_path / "other"
    other.mkdir()
    (other / "note.md").write_text("Other pack.\n", encoding="utf-8")
    other_pack = tmp_path / "other.specpack"
    pack(other, other_pack)

    registry = PackRegistry()
    registry.add("repo", served_pack)
    server = SpectrumServer(("127.0.0.1", 0), create_handler(registry), quiet=True)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    port = server.server_address[1]

    try:
        assert main(["project", "restart", str(other_pack), "--port", str(port), "--no-start"]) == 1
        err = capsys.readouterr().err
        assert "use --force" in err
        assert thread.is_alive()
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


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
