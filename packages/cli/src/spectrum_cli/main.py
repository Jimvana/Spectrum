from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor
import getpass
import importlib.util
import json
import os
import platform
import subprocess
import tempfile
import sys
import time
from dataclasses import asdict, is_dataclass
from http.client import HTTPException
from pathlib import Path
from urllib.error import URLError
from urllib.request import Request, urlopen


SPECTRUM_BANNER = [
    "  █████████                               █████                                        ",
    " ███▒▒▒▒▒███                             ▒▒███                                         ",
    "▒███    ▒▒▒  ████████   ██████   ██████  ███████   ████████  █████ ████ █████████████ ",
    "▒▒█████████ ▒▒███▒▒███ ███▒▒███ ███▒▒███▒▒▒███▒   ▒▒███▒▒███▒▒███ ▒███ ▒▒███▒▒███▒▒███",
    " ▒▒▒▒▒▒▒▒███ ▒███ ▒███▒███████ ▒███ ▒▒▒   ▒███     ▒███ ▒▒▒  ▒███ ▒███  ▒███ ▒███ ▒███",
    " ███    ▒███ ▒███ ▒███▒███▒▒▒  ▒███  ███  ▒███ ███ ▒███      ▒███ ▒███  ▒███ ▒███ ▒███",
    "▒▒█████████  ▒███████ ▒▒██████ ▒▒██████   ▒▒█████  █████     ▒▒████████ █████▒███ █████",
    " ▒▒▒▒▒▒▒▒▒   ▒███▒▒▒   ▒▒▒▒▒▒   ▒▒▒▒▒▒     ▒▒▒▒▒  ▒▒▒▒▒       ▒▒▒▒▒▒▒▒ ▒▒▒▒▒ ▒▒▒ ▒▒▒▒▒ ",
    "             ▒███                                                                      ",
    "             █████                                                                     ",
    "            ▒▒▒▒▒                                                                      ",
]

SPECTRUM_COLORS = [
    "\033[38;2;255;0;76m",
    "\033[38;2;255;122;0m",
    "\033[38;2;255;208;0m",
    "\033[38;2;88;214;141m",
    "\033[38;2;0;212;255m",
    "\033[38;2;77;124;255m",
    "\033[38;2;155;92;255m",
    "\033[38;2;255;79;216m",
]
ANSI_RESET = "\033[0m"
PROJECT_CONTEXT_DIR = ".spectrum-project"
PROJECT_RUNTIME_DIR = ".spectrum"
PROJECT_PACK_NAME = "project.specpack"
PROJECT_CONTEXT_FILES = {
    "project.md": """# Project

Name: {name}
Root: {root}

Describe what this project is, who uses it, and where the important source
folders live.
""",
    "status.md": """# Status

Current state:

- Fill in the last known working state.
- Note active tasks, blockers, and what an agent should check first.
""",
    "agent-rules.md": """# Agent Rules

- Search and hydrate this pack before making project assumptions.
- Ask before using SSH, deploying, reading secrets, or changing production data.
- Append durable notes after important work.
""",
    "architecture.md": """# Architecture

Record the main app structure, services, data stores, frameworks, and important
tradeoffs.
""",
    "deploy.md": """# Deploy

Record deployment commands, build steps, verification checks, and rollback notes.
""",
    "server.md": """# Server

Record hosts, service names, install paths, log paths, restart commands, and
health checks.
""",
    "ssh.md": """# SSH

Store SSH aliases and connection notes here. Prefer aliases such as
`project-prod` instead of raw keys.
""",
    "secrets.refs.md": """# Secret References

Store references to secrets, not raw secrets.

Examples:

- SSH key: available through local ssh-agent.
- Password vault: 1Password or Bitwarden item name.
- Env file: path on the server or local machine.
""",
    "ops.json": "",
    "runbook.md": """# Runbook

Record common operations, troubleshooting steps, recovery commands, and checks.
""",
    "decisions.md": """# Decisions

Record important project decisions, dates, and reasons.
""",
}


def _json_default(value):
    if isinstance(value, Path):
        return str(value)
    if is_dataclass(value):
        return asdict(value)
    raise TypeError(f"Object of type {type(value).__name__} is not JSON serializable")


def emit(value, *, as_json: bool) -> None:
    if as_json:
        print(json.dumps(value, default=_json_default, indent=2))
    else:
        print(value)


def _supports_color(*, disabled: bool, forced: bool) -> bool:
    if disabled or "NO_COLOR" in os.environ:
        return False
    if forced:
        return True
    if not sys.stdout.isatty():
        return False
    if os.name != "nt":
        return True
    if os.environ.get("WT_SESSION") or os.environ.get("ANSICON"):
        return True
    if os.environ.get("ConEmuANSI", "").upper() == "ON":
        return True
    term = os.environ.get("TERM", "").lower()
    return any(marker in term for marker in ["xterm", "ansi", "color", "cygwin"])


def print_banner(*, color: bool) -> None:
    for idx, line in enumerate(SPECTRUM_BANNER):
        if color:
            print(f"{SPECTRUM_COLORS[idx % len(SPECTRUM_COLORS)]}{line}{ANSI_RESET}")
        else:
            print(line)


def _prompt(message: str, default: str) -> str:
    suffix = f" [{default}]" if default else ""
    try:
        value = input(f"{message}{suffix}: ").strip()
    except EOFError:
        value = ""
    return value or default


def _confirm(message: str, *, default: bool) -> bool:
    marker = "Y/n" if default else "y/N"
    try:
        value = input(f"{message} [{marker}]: ").strip().lower()
    except EOFError:
        return default
    if not value:
        return default
    return value in {"y", "yes"}


def _read_passphrase(*, confirm: bool = False, allow_env: bool = True) -> str:
    env_value = os.environ.get("SPECTRUM_PASSPHRASE") if allow_env else None
    if env_value is not None:
        print("spectrum: using SPECTRUM_PASSPHRASE; environment variables can leak secrets", file=sys.stderr)
        if not env_value:
            raise ValueError("passphrase must not be empty")
        return env_value
    prompt = "Create passphrase: " if confirm else "Unlock passphrase: "
    value = getpass.getpass(prompt)
    if not value:
        raise ValueError("passphrase must not be empty")
    if confirm:
        repeated = getpass.getpass("Confirm passphrase: ")
        if value != repeated:
            raise ValueError("passphrases do not match")
        if len(value) < 12:
            print("spectrum: warning: short passphrases are easier to guess; prefer a long memorable phrase", file=sys.stderr)
    return value


def _unlock_passphrase(args: argparse.Namespace) -> str | None:
    return _read_passphrase(confirm=False) if getattr(args, "unlock", False) else None


def _default_pack_path(source: Path) -> Path:
    name = source.resolve().name if source.exists() else source.name
    if not name or name in {".", ".."}:
        name = Path.cwd().name
    return Path.cwd() / f"{name}.specpack"


def _default_project_pack_path(project_dir: Path) -> Path:
    return project_dir / PROJECT_RUNTIME_DIR / PROJECT_PACK_NAME


def _normalize_load_output(path: Path) -> Path:
    if path.suffix.lower() == ".specpack":
        return path
    if path.suffix:
        raise ValueError("output path must end with .specpack")
    return path.with_suffix(".specpack")


def _preflight_output_path(output: Path) -> None:
    parent = output.parent if output.parent != Path("") else Path.cwd()
    try:
        parent.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        raise PermissionError(f"cannot create output folder {parent}: {exc}") from exc
    if not parent.is_dir():
        raise NotADirectoryError(f"output folder is not a directory: {parent}")

    probe = parent / f".spectrum-write-test-{os.getpid()}.tmp"
    try:
        probe.write_bytes(b"spectrum")
    except OSError as exc:
        raise PermissionError(f"cannot write to output folder {parent}: {exc}") from exc
    finally:
        try:
            probe.unlink()
        except FileNotFoundError:
            pass
        except OSError:
            pass

    if output.exists():
        if output.is_dir():
            raise IsADirectoryError(f"output path is a directory: {output}")
        try:
            with output.open("r+b"):
                pass
        except OSError as exc:
            raise PermissionError(f"cannot replace existing specpack {output}: {exc}") from exc


def _quote_command_arg(value: str | Path) -> str:
    text = str(value)
    if not text:
        return '""'
    if any(char.isspace() for char in text):
        return f'"{text}"'
    return text


def _split_path_list(value: str) -> list[str]:
    return [item.strip().strip('"') for item in value.split(",") if item.strip()]


def _port_from_endpoint(value: str) -> int | None:
    value = value.strip()
    if not value:
        return None
    if value.startswith("[") and "]:" in value:
        value = value.rsplit("]:", 1)[1]
    elif ":" in value:
        value = value.rsplit(":", 1)[1]
    elif "." in value:
        value = value.rsplit(".", 1)[1]
    if not value.isdigit():
        return None
    port = int(value)
    return port if 0 < port < 65536 else None


def _discover_listening_tcp_ports() -> list[int]:
    commands = [
        ["netstat", "-ano", "-p", "tcp"],
        ["netstat", "-an", "-p", "tcp"],
        ["netstat", "-ltn"],
    ]
    ports: set[int] = set()
    for command in commands:
        try:
            result = subprocess.run(
                command,
                stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL,
                text=True,
                timeout=3,
                check=False,
            )
        except (OSError, subprocess.TimeoutExpired):
            continue
        if result.returncode != 0 or not result.stdout:
            continue
        for line in result.stdout.splitlines():
            parts = line.split()
            if not parts or not parts[0].lower().startswith("tcp"):
                continue
            upper_line = line.upper()
            if "LISTEN" not in upper_line and "LISTENING" not in upper_line:
                continue
            local = parts[1] if len(parts) > 1 and (":" in parts[1] or "." in parts[1]) else None
            if local is None and len(parts) > 3:
                local = parts[3]
            port = _port_from_endpoint(local or "")
            if port is not None:
                ports.add(port)
        if ports:
            break
    return sorted(ports)


def _write_project_templates(context_root: Path, project_dir: Path, *, name: str, replace: bool) -> list[str]:
    context_dir = context_root / PROJECT_CONTEXT_DIR
    context_dir.mkdir(parents=True, exist_ok=True)
    created: list[str] = []
    for filename, template in PROJECT_CONTEXT_FILES.items():
        path = context_dir / filename
        if path.exists() and not replace:
            continue
        if filename == "ops.json":
            content = json.dumps(
                {
                    "project": {
                        "name": name,
                        "root": str(project_dir.resolve()),
                    },
                    "sites": [
                        {
                            "name": "",
                            "domains": [],
                            "ssh": {
                                "host": "",
                                "user": "",
                                "identity_file": "",
                                "safe_probe": "whoami; hostname; pwd",
                            },
                            "deploy": {
                                "remote_path": "",
                                "nginx_config": "",
                                "health_check": "",
                            },
                        }
                    ],
                    "policy": {
                        "ssh_requires_confirmation": True,
                        "deploy_requires_confirmation": True,
                        "read_secrets_requires_confirmation": True,
                        "safe_readonly_commands": ["whoami", "hostname", "pwd", "ls", "cat"],
                    },
                },
                indent=2,
            ) + "\n"
        else:
            content = template.format(name=name, root=project_dir.resolve())
        path.write_text(content, encoding="utf-8")
        created.append(f"{PROJECT_CONTEXT_DIR}/{filename}")
    return created


def _write_project_launchers(pack_path: Path, *, name: str, port: int, encrypted: bool = False) -> list[Path]:
    runtime_dir = pack_path.parent
    runtime_dir.mkdir(parents=True, exist_ok=True)
    pack_name = pack_path.name
    dashboard_url = f"http://127.0.0.1:{port}/project"
    context_url = f"http://127.0.0.1:{port}/projects/repo/context"
    unlock_flag = " --unlock" if encrypted else ""
    written: list[Path] = []

    files = {
        "start.ps1": f"""$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
$Pack = Join-Path $Root "{pack_name}"
Write-Host "Starting Spectrum project server..."
Write-Host "Dashboard: {dashboard_url}"
Write-Host "Agent context: {context_url}"
spectrum project serve "$Pack" --port {port}{unlock_flag}
""",
        "start.cmd": f"""@echo off
cd /d "%~dp0"
powershell -ExecutionPolicy Bypass -File "%~dp0start.ps1"
pause
""",
        "start.command": f"""#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"
echo "Starting Spectrum project server..."
echo "Dashboard: {dashboard_url}"
echo "Agent context: {context_url}"
spectrum project serve "./{pack_name}" --port {port}{unlock_flag}
echo
read -r -p "Press enter to close..."
""",
        "start.sh": f"""#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"
echo "Starting Spectrum project server..."
echo "Dashboard: {dashboard_url}"
echo "Agent context: {context_url}"
spectrum project serve "./{pack_name}" --port {port}{unlock_flag}
""",
        "README.md": f"""# Spectrum Project Launcher

Project: {name}

This folder contains the portable Spectrum project pack and launchers.

## Start The Local Server

Windows:

```text
Double-click start.cmd
```

PowerShell:

```powershell
.\\start.ps1
```

macOS:

```text
Double-click start.command
```

Linux:

```bash
./start.sh
```

## URLs

- Dashboard: {dashboard_url}
- Agent context: {context_url}

The pack file is `{pack_name}`.
{"It is encrypted; the launcher will prompt for the passphrase before serving." if encrypted else ""}
""",
        "metadata.json": json.dumps(
            {
                "name": name,
                "pack": pack_name,
                "port": port,
                "dashboard_url": dashboard_url,
                "context_url": context_url,
                "launcher_version": 1,
            },
            indent=2,
        )
        + "\n",
    }

    for filename, content in files.items():
        path = runtime_dir / filename
        path.write_text(content, encoding="utf-8", newline="\n")
        if filename in {"start.command", "start.sh"}:
            try:
                path.chmod(path.stat().st_mode | 0o111)
            except OSError:
                pass
        written.append(path)
    return written


def command_encode(args: argparse.Namespace) -> int:
    from spectrum_core import encode_file

    result = encode_file(
        args.input,
        args.output,
        language=args.language,
        rle=args.rle,
        zlib_level=args.zlib_level,
        verbose=args.verbose,
    )
    emit(result, as_json=args.json)
    return 0


def command_decode(args: argparse.Namespace) -> int:
    from spectrum_core import decode_file

    result = decode_file(args.input, args.output, verbose=args.verbose)
    emit(result, as_json=args.json)
    return 0 if result.ok else 1


def command_pack(args: argparse.Namespace) -> int:
    from spectrum_core import pack

    encrypt = bool(getattr(args, "encrypt", False))
    passphrase = _read_passphrase(confirm=True) if encrypt else None
    summary = pack(
        args.input,
        args.output,
        include_all=args.all,
        language=args.language,
        rle=args.rle,
        zlib_level=args.zlib_level,
        verbose=args.verbose,
        encrypt=encrypt,
        passphrase=passphrase,
        kdf_profile=getattr(args, "kdf_profile", "interactive"),
        hint=getattr(args, "hint", None),
    )
    emit(summary, as_json=args.json)
    return 0


def command_append(args: argparse.Namespace) -> int:
    from spectrum_core import append_to_pack

    passphrase = _unlock_passphrase(args)
    summary = append_to_pack(
        args.pack,
        args.input,
        output_path=args.output,
        include_all=args.all,
        language=args.language,
        rle=args.rle,
        zlib_level=args.zlib_level,
        replace=args.replace,
        verbose=args.verbose,
        passphrase=passphrase,
    )
    emit(summary, as_json=args.json)
    return 0


def command_unpack(args: argparse.Namespace) -> int:
    from spectrum_core import unpack

    results = unpack(args.input, args.output, verbose=args.verbose, passphrase=_unlock_passphrase(args))
    emit(results, as_json=args.json)
    return 0 if all(result.ok for result in results) else 1


def command_inspect(args: argparse.Namespace) -> int:
    from spectrum_core import inspect_pack, inspect_spec

    path = Path(args.input)
    if path.suffix.lower() == ".specpack":
        emit(inspect_pack(path, passphrase=_unlock_passphrase(args)), as_json=args.json)
    else:
        emit(inspect_spec(path), as_json=args.json)
    return 0


def command_verify(args: argparse.Namespace) -> int:
    from spectrum_core import verify_path

    report = verify_path(args.input, passphrase=_unlock_passphrase(args))
    emit(report.to_dict(), as_json=args.json)
    return 0 if report.valid else 1


def command_index(args: argparse.Namespace) -> int:
    from spectrum_index import build_index

    result = build_index(
        args.input,
        output_path=args.output,
        embed=args.embed,
        verbose=args.verbose,
        passphrase=_unlock_passphrase(args),
    )
    payload = {key: value for key, value in result.items() if key != "index"}
    emit(payload, as_json=args.json)
    return 0


def command_search(args: argparse.Namespace) -> int:
    from spectrum_index import search_pack

    results = search_pack(
        args.pack,
        args.query,
        top_k=args.top,
        language=args.language,
        index_path=args.index,
        build_if_missing=not args.no_build,
        passphrase=_unlock_passphrase(args),
    )
    emit(results, as_json=args.json)
    return 0


def _running_server_info(host: str, port: int) -> dict | None:
    base = f"http://{host}:{port}"
    try:
        with urlopen(f"{base}/health", timeout=1.0) as response:
            health = json.loads(response.read().decode("utf-8"))
        with urlopen(f"{base}/packs", timeout=1.0) as response:
            packs = json.loads(response.read().decode("utf-8"))
    except (OSError, URLError, TimeoutError, json.JSONDecodeError):
        return None
    return {
        "base_url": base,
        "health": health,
        "packs": packs.get("packs", []),
        "dashboard_url": f"{base}/project",
        "context_url": f"{base}/projects/repo/context",
    }


def _shutdown_running_server(host: str, port: int, *, timeout: float = 5.0) -> dict | None:
    base = f"http://{host}:{port}"
    try:
        request = Request(f"{base}/shutdown", method="POST")
        with urlopen(request, timeout=timeout) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except (OSError, URLError, TimeoutError, HTTPException, json.JSONDecodeError):
        return None

    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if _running_server_info(host, port) is None:
            return payload
        time.sleep(0.1)
    return payload


def command_serve(args: argparse.Namespace) -> int:
    from spectrum_server.app import ApiError, PackRegistry, run_server

    requested_paths: list[Path] = []
    if args.specpack:
        requested_paths.append(Path(args.specpack).expanduser())
    for value in args.pack:
        path_value = value.split("=", 1)[1] if "=" in value else value
        requested_paths.append(Path(path_value).expanduser())

    running = _running_server_info(args.host, args.port)
    if running is not None:
        requested = {str(path.resolve()) for path in requested_paths}
        served = {str(Path(pack_info["path"]).resolve()) for pack_info in running["packs"]}
        if requested and requested <= served:
            print(f"spectrum serve already running on {running['base_url']}", file=sys.stderr)
            print(f"project dashboard: {running['dashboard_url']}", file=sys.stderr)
            print(f"agent context: {running['context_url']}", file=sys.stderr)
            return 0
        served_list = ", ".join(sorted(served)) or "no registered packs"
        requested_list = ", ".join(sorted(requested)) or "no requested packs"
        raise ValueError(
            f"port {args.port} already has a Spectrum server running for {served_list}; "
            f"requested {requested_list}. Stop the existing server or choose another port."
        )

    registry = PackRegistry()
    passphrase = getattr(args, "passphrase", None)
    if passphrase is None and getattr(args, "unlock", False):
        passphrase = _read_passphrase(confirm=False)
    try:
        if args.specpack:
            registry.add("repo", args.specpack, passphrase=passphrase)
        for idx, value in enumerate(args.pack, start=1):
            if "=" in value:
                pack_id, path = value.split("=", 1)
            else:
                pack_id = f"pack-{idx}"
                path = value
            registry.add(pack_id, path, passphrase=passphrase)
    except ApiError as exc:
        raise ValueError(exc.message) from exc

    print(f"spectrum serve listening on http://{args.host}:{args.port}", file=sys.stderr)
    print(f"project dashboard: http://{args.host}:{args.port}/project", file=sys.stderr)
    print(f"agent context: http://{args.host}:{args.port}/projects/repo/context", file=sys.stderr)
    try:
        run_server(host=args.host, port=args.port, registry=registry, quiet=args.quiet)
    except KeyboardInterrupt:
        return 130
    return 0


def command_project_init(args: argparse.Namespace) -> int:
    from spectrum_core import append_to_pack, pack, verify_pack
    from spectrum_index import build_index

    project_dir = Path(args.source).expanduser()
    if project_dir.exists() and not project_dir.is_dir():
        raise ValueError("project source must be a directory")
    project_dir.mkdir(parents=True, exist_ok=True)

    output = _normalize_load_output(Path(args.output).expanduser()) if args.output else _default_project_pack_path(project_dir)
    _preflight_output_path(output)
    name = args.name or project_dir.resolve().name
    encrypt = bool(getattr(args, "encrypt", False))
    kdf_profile = getattr(args, "kdf_profile", "interactive")
    hint = getattr(args, "hint", None)
    passphrase = getattr(args, "passphrase", None)
    if encrypt and passphrase is None:
        passphrase = _read_passphrase(confirm=True)
    with tempfile.TemporaryDirectory(prefix="spectrum-project-context-") as tmp_name:
        context_root = Path(tmp_name)
        created = _write_project_templates(context_root, project_dir, name=name, replace=True)
        try:
            pack_summary = pack(
                project_dir,
                output,
                include_all=args.all,
                language=args.language,
                rle=args.rle,
                zlib_level=args.zlib_level,
                verbose=args.verbose,
                encrypt=encrypt,
                passphrase=passphrase,
                kdf_profile=kdf_profile,
                hint=hint,
            )
            pack_summary = append_to_pack(
                output,
                context_root,
                include_all=True,
                replace=True,
                language=args.language,
                rle=args.rle,
                zlib_level=args.zlib_level,
                verbose=args.verbose,
                passphrase=passphrase,
            )
            pack_summary["context_entries"] = len(created)
        except ValueError as exc:
            if "no encodable files found" not in str(exc):
                raise
            pack_summary = pack(
                context_root,
                output,
                include_all=True,
                language=args.language,
                rle=args.rle,
                zlib_level=args.zlib_level,
                verbose=args.verbose,
                encrypt=encrypt,
                passphrase=passphrase,
                kdf_profile=kdf_profile,
                hint=hint,
            )
    launchers = _write_project_launchers(output, name=name, port=args.port, encrypted=encrypt)
    verify_report = verify_pack(output, passphrase=passphrase).to_dict()
    index_summary = None
    if not args.no_index:
        result = build_index(output, embed=True, verbose=args.verbose, passphrase=passphrase)
        index_summary = {key: value for key, value in result.items() if key != "index"}

    payload = {
        "project": str(project_dir.resolve()),
        "name": name,
        "pack": str(output.resolve()),
        "context_dir": PROJECT_CONTEXT_DIR,
        "created_files": created,
        "launcher_files": [str(path.resolve()) for path in launchers],
        "pack_summary": pack_summary,
        "verify": verify_report,
        "index": index_summary,
        "serve_command": f"spectrum project serve {_quote_command_arg(output)} --port {args.port}{' --unlock' if encrypt else ''}",
        "dashboard_url": f"http://127.0.0.1:{args.port}/project",
        "context_endpoint": f"http://127.0.0.1:{args.port}/projects/repo/context",
    }
    if args.json:
        emit(payload, as_json=True)
    else:
        print(f"Project pack ready: {output}")
        print(f"Context files: embedded at {PROJECT_CONTEXT_DIR}/")
        print(f"Launchers: {output.parent}")
        print(f"Verify: {'valid' if verify_report.get('valid') else 'failed'}")
        if index_summary:
            print("Search index: embedded")
        print(f"Dashboard: {payload['dashboard_url']}")
        print(f"Serve it with: {payload['serve_command']}")
        print(f"Agent context: {payload['context_endpoint']}")
    return 0 if verify_report.get("valid") else 1


def command_project_add(args: argparse.Namespace) -> int:
    from spectrum_core import append_to_pack, verify_pack
    from spectrum_index import build_index

    passphrase = _unlock_passphrase(args)
    append_summary = append_to_pack(
        args.pack,
        args.input,
        include_all=args.all,
        language=args.language,
        rle=args.rle,
        zlib_level=args.zlib_level,
        replace=args.replace,
        verbose=args.verbose,
        passphrase=passphrase,
    )
    verify_report = verify_pack(args.pack, passphrase=passphrase).to_dict()
    index_summary = None
    if not args.no_index:
        result = build_index(args.pack, embed=True, verbose=args.verbose, passphrase=passphrase)
        index_summary = {key: value for key, value in result.items() if key != "index"}
    payload = {
        "pack": str(Path(args.pack).expanduser().resolve()),
        "append": append_summary,
        "verify": verify_report,
        "index": index_summary,
    }
    emit(payload, as_json=args.json)
    return 0 if verify_report.get("valid") else 1


def command_project_serve(args: argparse.Namespace) -> int:
    return command_serve(
        argparse.Namespace(
            specpack=args.pack,
            pack=[],
            host=args.host,
            port=args.port,
            quiet=args.quiet,
            unlock=getattr(args, "unlock", False),
            passphrase=None,
        )
    )


def command_project_restart(args: argparse.Namespace) -> int:
    pack_path = Path(args.pack).expanduser().resolve()
    running = _running_server_info(args.host, args.port)
    if running is not None:
        served = {str(Path(pack_info["path"]).resolve()) for pack_info in running["packs"]}
        requested = str(pack_path)
        if served and requested not in served and not args.force:
            served_list = ", ".join(sorted(served))
            raise ValueError(
                f"port {args.port} is serving {served_list}; "
                "use --force to restart it with a different pack."
            )
        stopped = _shutdown_running_server(args.host, args.port, timeout=args.timeout)
        if stopped is None:
            raise ValueError(f"could not stop Spectrum server on http://{args.host}:{args.port}")
        print(f"stopped Spectrum server on http://{args.host}:{args.port}", file=sys.stderr)

    if args.no_start:
        return 0

    return command_project_serve(argparse.Namespace(pack=str(pack_path), host=args.host, port=args.port, quiet=args.quiet, unlock=getattr(args, "unlock", False)))


def command_project(args: argparse.Namespace) -> int:
    print("Use a project subcommand: init, add, serve, or restart")
    return 0


def command_hub(args: argparse.Namespace) -> int:
    if args.gui:
        from spectrum_cli.gui import main as gui_main

        return gui_main()
    if args.build:
        return command_hub_build(args)
    if args.append:
        return command_hub_append(args)
    if args.serve:
        return command_hub_serve(args)
    if args.verify_servers:
        return command_hub_verify(args)
    print("Use one hub action: -b build, -a append, -s serve, or -v verify servers")
    return 0


def command_hub_build(args: argparse.Namespace) -> int:
    print("Spectrum Hub: build a portable project pack")
    project_text = args.source or _prompt("Project folder/location", ".")
    project_dir = Path(project_text).expanduser()
    default_name = project_dir.resolve().name if project_dir.exists() else project_dir.name or "project"
    name = args.name or _prompt("Specpack/project name", default_name)
    default_pack = _default_project_pack_path(project_dir)
    pack_text = args.pack or _prompt("Specpack path", str(default_pack))
    if args.input is not None:
        extra_text = args.input
    elif args.yes or args.no_serve:
        extra_text = ""
    else:
        extra_text = _prompt("Extra files or folders to add, comma-separated", "")
    port = args.port or 7777

    init_code = command_project_init(
        argparse.Namespace(
            source=str(project_dir),
            output=pack_text,
            name=name,
            replace_template=False,
            no_index=False,
            port=port,
            all=args.all,
            language=args.language,
            rle=args.rle,
            zlib_level=args.zlib_level,
            verbose=args.verbose,
            json=args.json,
            encrypt=getattr(args, "encrypt", False),
            kdf_profile=getattr(args, "kdf_profile", "interactive"),
            hint=getattr(args, "hint", None),
        )
    )
    if init_code:
        return init_code

    for item in _split_path_list(extra_text):
        add_code = command_project_add(
            argparse.Namespace(
                pack=pack_text,
                input=item,
                replace=False,
                no_index=False,
                all=args.all,
                language=args.language,
                rle=args.rle,
                zlib_level=args.zlib_level,
                verbose=args.verbose,
                json=args.json,
                unlock=getattr(args, "unlock", False),
            )
        )
        if add_code:
            return add_code

    if args.no_serve:
        print(f"Start it later with: spectrum project serve {_quote_command_arg(pack_text)} --port {port}{' --unlock' if getattr(args, 'encrypt', False) else ''}")
        return 0
    if args.yes or _confirm("Serve this project now?", default=True):
        return command_project_serve(argparse.Namespace(pack=pack_text, host=args.host, port=port, quiet=False, unlock=getattr(args, "encrypt", False)))
    print(f"Start it later with: spectrum project serve {_quote_command_arg(pack_text)} --port {port}{' --unlock' if getattr(args, 'encrypt', False) else ''}")
    return 0


def command_hub_append(args: argparse.Namespace) -> int:
    print("Spectrum Hub: append files to a portable project pack")
    pack_text = args.pack or _prompt("Specpack path", str(_default_project_pack_path(Path.cwd())))
    input_text = args.input or _prompt("Files or folders to add, comma-separated", "")
    if not input_text:
        raise ValueError("at least one file or folder is required")
    for item in _split_path_list(input_text):
        code = command_project_add(
            argparse.Namespace(
                pack=pack_text,
                input=item,
                replace=args.replace,
                no_index=False,
                all=args.all,
                language=args.language,
                rle=args.rle,
                zlib_level=args.zlib_level,
                verbose=args.verbose,
                json=args.json,
                unlock=getattr(args, "unlock", False),
            )
        )
        if code:
            return code
    return 0


def command_hub_serve(args: argparse.Namespace) -> int:
    print("Spectrum Hub: serve a portable project pack")
    pack_text = args.pack or _prompt("Specpack path", str(_default_project_pack_path(Path.cwd())))
    port_text = str(args.port) if args.port is not None else _prompt("Port", "7777")
    try:
        port = int(port_text)
    except ValueError as exc:
        raise ValueError(f"invalid port: {port_text}") from exc
    return command_project_serve(argparse.Namespace(pack=pack_text, host=args.host, port=port, quiet=False, unlock=getattr(args, "unlock", False)))


def _probe_spectrum_server(host: str, port: int, timeout: float) -> dict[str, object]:
    base = f"http://{host}:{port}"
    server_info: dict[str, object] = {"port": port, "base_url": base, "running": False}
    try:
        with urlopen(f"{base}/health", timeout=timeout) as response:
            health = json.loads(response.read().decode("utf-8"))
        with urlopen(f"{base}/packs", timeout=timeout) as response:
            packs = json.loads(response.read().decode("utf-8"))
        server_info.update(
            {
                "running": True,
                "health": health,
                "packs": packs.get("packs", []),
                "dashboard_url": f"{base}/project",
                "context_url": f"{base}/projects/repo/context",
            }
        )
    except (OSError, URLError, TimeoutError, HTTPException, json.JSONDecodeError) as exc:
        server_info["error"] = str(exc)
    return server_info


def command_hub_verify(args: argparse.Namespace) -> int:
    ports = (
        [int(value.strip()) for value in str(args.ports).split(",") if value.strip()]
        if args.ports
        else _discover_listening_tcp_ports()
    )
    if ports:
        workers = min(32, len(ports))
        with ThreadPoolExecutor(max_workers=workers) as executor:
            servers = list(executor.map(lambda port: _probe_spectrum_server(args.host, port, args.timeout), ports))
    else:
        servers = []

    payload = {"servers": servers, "running": [server for server in servers if server["running"]]}
    if args.json:
        emit(payload, as_json=True)
    else:
        if not payload["running"]:
            print("No spectrum servers operating")
            return 0
        for server in servers:
            if server["running"]:
                print(f"[ok] {server['base_url']}")
                print(f"     dashboard: {server['dashboard_url']}")
                print(f"     context: {server['context_url']}")
                for pack_info in server.get("packs", []):
                    print(f"     pack {pack_info['id']}: {pack_info['path']}")
    return 0


def command_load(args: argparse.Namespace) -> int:
    print_banner(color=_supports_color(disabled=args.no_color, forced=args.color))
    print()
    print("Spectrum load will walk you through the local agent-retrieval path:")
    print("  1. check this install")
    print("  2. pack a repo into a .specpack")
    print("  3. serve that pack on the local HTTP API")
    print()

    source_text = args.source or _prompt("Repo or folder to pack", ".")
    source = Path(source_text).expanduser()
    default_output = str(_default_pack_path(source))
    output_text = args.output or _prompt("Output .specpack path", default_output)
    output = _normalize_load_output(Path(output_text).expanduser())

    port = args.port
    if args.source is None and args.output is None and args.port == 7777:
        port_text = _prompt("Local API port", str(args.port))
        try:
            port = int(port_text)
        except ValueError as exc:
            raise ValueError(f"invalid port: {port_text}") from exc

    if not source.exists():
        raise FileNotFoundError(source)
    encrypt = bool(getattr(args, "encrypt", False))
    kdf_profile = getattr(args, "kdf_profile", "interactive")
    hint = getattr(args, "hint", None)
    commands = [
        "spectrum doctor",
        f"spectrum pack {_quote_command_arg(source)} {_quote_command_arg(output)}{' --encrypt' if encrypt else ''} --json",
        f"spectrum serve {_quote_command_arg(output)} --port {port}{' --unlock' if encrypt else ''}",
    ]

    print("Commands:")
    for command in commands:
        print(f"  {command}")
    print()

    if args.dry_run:
        print("Dry run only. No pack was written and no server was started.")
        return 0

    if not args.yes and not _confirm("Run these steps now?", default=True):
        print("Stopped before making changes.")
        return 0

    doctor_code = command_doctor(argparse.Namespace(json=False))
    if doctor_code:
        return doctor_code

    passphrase = _read_passphrase(confirm=True) if encrypt else None
    print()
    print(f"Packing {_quote_command_arg(source)} -> {_quote_command_arg(output)}")
    from spectrum_core import pack

    summary = pack(
        str(source),
        str(output),
        include_all=args.all,
        language=args.language,
        rle=args.rle,
        zlib_level=args.zlib_level,
        verbose=args.verbose,
        encrypt=encrypt,
        passphrase=passphrase,
        kdf_profile=kdf_profile,
        hint=hint,
    )
    emit(summary, as_json=True)

    print()
    print(f"Pack ready: {output}")
    print(f"Local API: http://127.0.0.1:{port}")
    print("Press Ctrl+C to stop the server.")
    print()

    if args.no_serve:
        print(f"Start it later with: {commands[-1]}")
        return 0

    if not args.yes and not _confirm("Start the local API server now?", default=True):
        print(f"Start it later with: {commands[-1]}")
        return 0

    return command_serve(
        argparse.Namespace(
            specpack=str(output),
            pack=[],
            host="127.0.0.1",
            port=port,
            quiet=False,
            unlock=encrypt,
            passphrase=passphrase,
        )
    )


def _doctor_check(name: str, ok: bool, detail: str, fix: str | None = None) -> dict[str, object]:
    payload: dict[str, object] = {"name": name, "ok": ok, "detail": detail}
    if fix:
        payload["fix"] = fix
    return payload


def _find_spectrum_root() -> Path | None:
    candidates: list[Path] = []
    env_root = os.environ.get("SPECTRUM_REPO_ROOT")
    if env_root:
        candidates.append(Path(env_root).expanduser())
    here = Path(__file__).resolve()
    candidates.extend([here, *here.parents, Path.cwd(), *Path.cwd().parents])

    for candidate in candidates:
        if candidate.is_file():
            candidate = candidate.parent
        if (candidate / "dictionary.py").exists() and (candidate / "spec_format" / "spec_encoder.py").exists():
            return candidate.resolve()
    return None


def command_doctor(args: argparse.Namespace) -> int:
    checks: list[dict[str, object]] = []

    python_version = ".".join(str(part) for part in sys.version_info[:3])
    checks.append(
        _doctor_check(
            "python",
            sys.version_info >= (3, 10),
            f"{python_version} at {sys.executable}",
            "Install Python 3.10+ and make sure it is available on PATH.",
        )
    )

    node_command = os.environ.get("SPECTRUM_NODE_COMMAND")
    if node_command:
        checks.append(_doctor_check("node-wrapper", True, node_command))
    else:
        checks.append(
            _doctor_check(
                "node-wrapper",
                True,
                "not running through the npm wrapper",
            )
        )

    for module_name in ["spectrum_core", "spectrum_index", "spectrum_cli", "spectrum_server"]:
        spec = importlib.util.find_spec(module_name)
        checks.append(
            _doctor_check(
                f"import:{module_name}",
                spec is not None,
                str(spec.origin) if spec and spec.origin else "not found",
                "Reinstall the package or run from a checkout with the package sources on PYTHONPATH.",
            )
        )

    spectrum_root = _find_spectrum_root()
    checks.append(
        _doctor_check(
            "spectrum-runtime",
            spectrum_root is not None,
            str(spectrum_root) if spectrum_root else "not found",
            "Reinstall spectrumstore, or set SPECTRUM_REPO_ROOT to the bundled runtime directory.",
        )
    )
    if spectrum_root:
        for relative in [
            "dictionary.py",
            "english_tokens.py",
            "spec_format/spec_encoder.py",
            "spec_format/spec_decoder.py",
        ]:
            path = spectrum_root / relative
            checks.append(
                _doctor_check(
                    f"runtime-file:{relative}",
                    path.exists(),
                    str(path),
                    "Reinstall spectrumstore; the bundled runtime is incomplete.",
                )
            )

    try:
        with tempfile.TemporaryDirectory(prefix="spectrum-doctor-") as tmp:
            probe = Path(tmp) / "write-probe.txt"
            probe.write_text("ok", encoding="utf-8")
            ok = probe.read_text(encoding="utf-8") == "ok"
            checks.append(_doctor_check("temp-write", ok, str(probe.parent)))
    except OSError as exc:
        checks.append(
            _doctor_check(
                "temp-write",
                False,
                str(exc),
                "Check permissions for your system temporary directory.",
            )
        )

    payload = {
        "ok": all(bool(check["ok"]) for check in checks),
        "platform": {
            "system": platform.system(),
            "release": platform.release(),
            "machine": platform.machine(),
        },
        "checks": checks,
    }

    if args.json:
        emit(payload, as_json=True)
    else:
        status = "ok" if payload["ok"] else "failed"
        print(f"Spectrum doctor: {status}")
        for check in checks:
            marker = "ok" if check["ok"] else "fail"
            print(f"[{marker}] {check['name']}: {check['detail']}")
            if not check["ok"] and "fix" in check:
                print(f"      fix: {check['fix']}")

    return 0 if payload["ok"] else 1


def add_common_codec_options(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--language", help="Force a language instead of extension detection")
    parser.add_argument("--rle", default="off", choices=["off", "auto", "force"], help="RLE mode")
    parser.add_argument("--zlib-level", type=int, default=9, choices=range(1, 10), metavar="1-9")
    parser.add_argument("--verbose", action="store_true", help="Show lower-level codec output")
    parser.add_argument("--json", action="store_true", help="Emit machine-readable JSON")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="spectrum",
        description="Spectrum Store Developer Preview command line tools",
    )
    sub = parser.add_subparsers(dest="command")

    encode = sub.add_parser("encode", help="Encode one file to .spec")
    encode.add_argument("input")
    encode.add_argument("output")
    add_common_codec_options(encode)
    encode.set_defaults(func=command_encode)

    decode = sub.add_parser("decode", help="Decode one .spec file")
    decode.add_argument("input")
    decode.add_argument("output")
    decode.add_argument("--verbose", action="store_true")
    decode.add_argument("--json", action="store_true")
    decode.set_defaults(func=command_decode)

    pack_parser = sub.add_parser("pack", help="Create a .specpack from a file or folder")
    pack_parser.add_argument("input")
    pack_parser.add_argument("output")
    pack_parser.add_argument("--all", action="store_true", help="Include every non-.spec file")
    pack_parser.add_argument("--encrypt", action="store_true", help="Encrypt the output .specpack")
    pack_parser.add_argument("--kdf-profile", default="interactive", choices=["interactive", "strong", "low-memory"])
    pack_parser.add_argument("--hint", help="Optional non-secret passphrase hint")
    add_common_codec_options(pack_parser)
    pack_parser.set_defaults(func=command_pack)

    append = sub.add_parser("append", help="Append files or a folder to an existing .specpack")
    append.add_argument("pack", help="Existing .specpack to append to")
    append.add_argument("input", help="File or folder to append")
    append.add_argument("-o", "--output", help="Write a new .specpack instead of updating in place")
    append.add_argument("--replace", action="store_true", help="Replace existing source paths in the pack")
    append.add_argument("--unlock", action="store_true", help="Prompt to unlock an encrypted pack")
    append.add_argument("--all", action="store_true", help="Include every non-.spec file")
    add_common_codec_options(append)
    append.set_defaults(func=command_append)

    unpack_parser = sub.add_parser("unpack", aliases=["decode-pack"], help="Decode a .specpack")
    unpack_parser.add_argument("input")
    unpack_parser.add_argument("output")
    unpack_parser.add_argument("--verbose", action="store_true")
    unpack_parser.add_argument("--unlock", action="store_true", help="Prompt to unlock an encrypted pack")
    unpack_parser.add_argument("--json", action="store_true")
    unpack_parser.set_defaults(func=command_unpack)

    inspect = sub.add_parser("inspect", aliases=["info"], help="Inspect .spec or .specpack metadata")
    inspect.add_argument("input")
    inspect.add_argument("--unlock", action="store_true", help="Prompt to unlock an encrypted pack")
    inspect.add_argument("--json", action="store_true")
    inspect.set_defaults(func=command_inspect)

    verify = sub.add_parser("verify", help="Verify .spec, .spec directory, or .specpack fidelity")
    verify.add_argument("input")
    verify.add_argument("--unlock", action="store_true", help="Prompt to unlock an encrypted pack")
    verify.add_argument("--json", action="store_true")
    verify.set_defaults(func=command_verify)

    index = sub.add_parser("index", help="Build a retrieval index for .spec, .spec directory, or .specpack")
    index.add_argument("input")
    index.add_argument("-o", "--output", help="Output index path")
    index.add_argument("--embed", action="store_true", help="Embed index.bin into a .specpack")
    index.add_argument("--unlock", action="store_true", help="Prompt to unlock an encrypted pack")
    index.add_argument("--verbose", action="store_true")
    index.add_argument("--json", action="store_true")
    index.set_defaults(func=command_index)

    search = sub.add_parser("search", help="Search a .specpack")
    search.add_argument("pack")
    search.add_argument("query")
    search.add_argument("--top", type=int, default=10)
    search.add_argument("--language", default="txt")
    search.add_argument("--index", help="Use a separate index file")
    search.add_argument("--no-build", action="store_true", help="Fail if no index is available")
    search.add_argument("--unlock", action="store_true", help="Prompt to unlock an encrypted pack")
    search.add_argument("--json", action="store_true")
    search.set_defaults(func=command_search)

    serve = sub.add_parser("serve", help="Run the local Spectrum HTTP API")
    serve.add_argument("specpack", nargs="?", help="Register one .specpack as pack id 'repo'")
    serve.add_argument("--pack", action="append", default=[], help="Register another pack as id=path or path")
    serve.add_argument("--host", default="127.0.0.1")
    serve.add_argument("--port", type=int, default=7777)
    serve.add_argument("--quiet", action="store_true")
    serve.add_argument("--unlock", action="store_true", help="Prompt to unlock encrypted packs at startup")
    serve.set_defaults(func=command_serve)

    project = sub.add_parser("project", help="Portable project pack workflows")
    project.set_defaults(func=command_project)
    project_sub = project.add_subparsers(dest="project_command")

    project_init = project_sub.add_parser("init", help="Create a portable project pack")
    project_init.add_argument("source", help="Project folder to initialize")
    project_init.add_argument("output", nargs="?", help="Output .specpack path")
    project_init.add_argument("--name", help="Human-readable project name")
    project_init.add_argument("--replace-template", action="store_true", help="Overwrite existing context template files")
    project_init.add_argument("--no-index", action="store_true", help="Skip embedding a search index")
    project_init.add_argument("--encrypt", action="store_true", help="Encrypt the output project .specpack")
    project_init.add_argument("--kdf-profile", default="interactive", choices=["interactive", "strong", "low-memory"])
    project_init.add_argument("--hint", help="Optional non-secret passphrase hint")
    project_init.add_argument("--port", type=int, default=7777, help="Port to show in the suggested serve command")
    project_init.add_argument("--all", action="store_true", help="Include every non-.spec file")
    add_common_codec_options(project_init)
    project_init.set_defaults(func=command_project_init)

    project_add = project_sub.add_parser("add", help="Append files or notes to a portable project pack")
    project_add.add_argument("pack", help="Existing .specpack to append to")
    project_add.add_argument("input", help="File or folder to append")
    project_add.add_argument("--replace", action="store_true", help="Replace existing source paths in the pack")
    project_add.add_argument("--no-index", action="store_true", help="Skip rebuilding the embedded search index")
    project_add.add_argument("--unlock", action="store_true", help="Prompt to unlock an encrypted pack")
    project_add.add_argument("--all", action="store_true", help="Include every non-.spec file")
    add_common_codec_options(project_add)
    project_add.set_defaults(func=command_project_add)

    project_serve = project_sub.add_parser("serve", help="Serve a portable project pack locally")
    project_serve.add_argument("pack", help="Existing .specpack to serve as pack id 'repo'")
    project_serve.add_argument("--host", default="127.0.0.1")
    project_serve.add_argument("--port", type=int, default=7777)
    project_serve.add_argument("--quiet", action="store_true")
    project_serve.add_argument("--unlock", action="store_true", help="Prompt to unlock encrypted packs at startup")
    project_serve.set_defaults(func=command_project_serve)

    project_restart = project_sub.add_parser("restart", help="Restart a local portable project server")
    project_restart.add_argument("pack", help="Existing .specpack to serve as pack id 'repo'")
    project_restart.add_argument("--host", default="127.0.0.1")
    project_restart.add_argument("--port", type=int, default=7777)
    project_restart.add_argument("--quiet", action="store_true")
    project_restart.add_argument("--timeout", type=float, default=5.0, help="Seconds to wait for the old server to stop")
    project_restart.add_argument("--force", action="store_true", help="Restart even if the port is serving a different pack")
    project_restart.add_argument("--no-start", action="store_true", help="Stop the old server and exit without starting a new one")
    project_restart.add_argument("--unlock", action="store_true", help="Prompt to unlock an encrypted pack when restarted")
    project_restart.set_defaults(func=command_project_restart)

    hub = sub.add_parser("hub", help="Guided portable project hub")
    hub_actions = hub.add_mutually_exclusive_group()
    hub_actions.add_argument("-b", "--build", action="store_true", help="Walk through building a project specpack")
    hub_actions.add_argument("-a", "--append", action="store_true", help="Walk through appending files to a specpack")
    hub_actions.add_argument("-s", "--serve", action="store_true", help="Walk through serving a specpack")
    hub_actions.add_argument("-v", "--verify-servers", action="store_true", help="Find running local Spectrum API servers")
    hub.add_argument("--gui", action="store_true", help="Launch the Spectrum Hub desktop GUI")
    hub.add_argument("--name", help="Project/specpack name for build mode")
    hub.add_argument("--source", help="Project folder/location for build mode")
    hub.add_argument("--pack", help="Specpack path")
    hub.add_argument("--input", help="Extra files or folders, comma-separated")
    hub.add_argument("--host", default="127.0.0.1")
    hub.add_argument("--port", type=int, default=None)
    hub.add_argument("--ports", default=None, help="Comma-separated ports for -v; default discovers local listening ports")
    hub.add_argument("--timeout", type=float, default=1.0, help="Per-port timeout for -v")
    hub.add_argument("--replace", action="store_true", help="Replace existing source paths when appending")
    hub.add_argument("--encrypt", action="store_true", help="Encrypt created packs in build mode")
    hub.add_argument("--unlock", action="store_true", help="Prompt to unlock encrypted packs in append or serve mode")
    hub.add_argument("--kdf-profile", default="interactive", choices=["interactive", "strong", "low-memory"])
    hub.add_argument("--hint", help="Optional non-secret passphrase hint")
    hub.add_argument("--yes", "-y", action="store_true", help="Accept prompts where possible")
    hub.add_argument("--no-serve", action="store_true", help="Build only and print the serve command")
    hub.add_argument("--all", action="store_true", help="Include every non-.spec file")
    add_common_codec_options(hub)
    hub.set_defaults(func=command_hub)

    load = sub.add_parser("load", help="Guided walkthrough for pack and local serve")
    load.add_argument("source", nargs="?", help="Repo or folder to pack")
    load.add_argument("output", nargs="?", help="Output .specpack path")
    load.add_argument("--port", type=int, default=7777)
    load.add_argument("--all", action="store_true", help="Include every non-.spec file")
    load.add_argument("--encrypt", action="store_true", help="Encrypt the output .specpack")
    load.add_argument("--kdf-profile", default="interactive", choices=["interactive", "strong", "low-memory"])
    load.add_argument("--hint", help="Optional non-secret passphrase hint")
    load.add_argument("--language", help="Force a language instead of extension detection")
    load.add_argument("--rle", default="off", choices=["off", "auto", "force"], help="RLE mode")
    load.add_argument("--zlib-level", type=int, default=9, choices=range(1, 10), metavar="1-9")
    load.add_argument("--verbose", action="store_true", help="Show lower-level codec output")
    load.add_argument("--yes", "-y", action="store_true", help="Accept prompts and run without confirmation")
    load.add_argument("--no-serve", action="store_true", help="Pack only and print the serve command")
    load.add_argument("--dry-run", action="store_true", help="Show the walkthrough without running commands")
    load.add_argument("--color", action="store_true", help="Force ANSI banner colors")
    load.add_argument("--no-color", action="store_true", help="Disable ANSI banner colors")
    load.set_defaults(func=command_load)

    doctor = sub.add_parser("doctor", help="Check local runtime and bundled install health")
    doctor.add_argument("--json", action="store_true")
    doctor.set_defaults(func=command_doctor)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if not hasattr(args, "func"):
        parser.print_help()
        return 0
    try:
        return int(args.func(args))
    except (FileNotFoundError, ValueError, KeyError, OSError) as exc:
        print(f"spectrum: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
