from __future__ import annotations

import argparse
import os
import platform
import shutil
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PYTHONPATH_ENTRIES = [
    ROOT / "packages/core/src",
    ROOT / "packages/index/src",
    ROOT / "packages/cli/src",
    ROOT / "packages/server/src",
]
ASSETS = ROOT / "packages/cli/src/spectrum_cli/assets"
RUNTIME = ROOT / "CLI Tool/vendor/spectrum_algo"
ENTRYPOINT = ROOT / "packages/cli/src/spectrum_cli/gui.py"


def host_platform() -> str:
    system = platform.system().lower()
    if system == "darwin":
        return "macos"
    if system == "windows":
        return "windows"
    if system == "linux":
        return "linux"
    return system


def data_arg(source: Path, dest: str) -> str:
    separator = ";" if host_platform() == "windows" else ":"
    return f"{source}{separator}{dest}"


def env_with_pythonpath() -> dict[str, str]:
    env = os.environ.copy()
    entries = [str(path) for path in PYTHONPATH_ENTRIES]
    existing = env.get("PYTHONPATH")
    if existing:
        entries.append(existing)
    env["PYTHONPATH"] = os.pathsep.join(entries)
    env.setdefault("SPECTRUM_REPO_ROOT", str(RUNTIME))
    return env


def pyinstaller_available() -> bool:
    return subprocess.run(
        [sys.executable, "-m", "PyInstaller", "--version"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    ).returncode == 0


def module_available(module: str, env: dict[str, str]) -> bool:
    return subprocess.run(
        [sys.executable, "-c", f"import {module}"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        env=env,
    ).returncode == 0


def spectrum_hub_running() -> bool:
    if host_platform() != "windows":
        return False
    tasklist = shutil.which("tasklist")
    if tasklist is None:
        return False
    result = subprocess.run(
        [tasklist, "/FI", "IMAGENAME eq SpectrumHub.exe"],
        capture_output=True,
        text=True,
    )
    return "SpectrumHub.exe" in result.stdout


def build_command(args: argparse.Namespace, env: dict[str, str]) -> list[str]:
    command = [
        sys.executable,
        "-m",
        "PyInstaller",
        "--noconfirm",
        "--clean",
        "--name",
        "SpectrumHub",
        "--distpath",
        str(args.dist),
        "--workpath",
        str(args.work),
        "--specpath",
        str(args.specpath),
    ]

    if args.platform in {"windows", "macos"}:
        command.append("--windowed")

    if args.platform == "windows":
        icon = ASSETS / "spec-icon.ico"
        if icon.exists():
            command.extend(["--icon", str(icon)])
        if args.uac_admin:
            command.append("--uac-admin")
    elif args.platform == "macos":
        # PyInstaller expects .icns for a polished app icon. Build the .app
        # first; add .icns generation when release signing/notarization lands.
        pass

    for path in PYTHONPATH_ENTRIES:
        command.extend(["--paths", str(path)])

    command.extend(
        [
            "--add-data",
            data_arg(RUNTIME, "spectrum_runtime"),
            "--add-data",
            data_arg(ASSETS, "spectrum_cli/assets"),
            "--hidden-import",
            "spectrum_cli.gui",
            "--hidden-import",
            "spectrum_server.app",
            "--hidden-import",
            "spectrum_index.api",
            "--hidden-import",
            "spectrum_core.pack",
        ]
    )

    if module_available("tkinterdnd2", env):
        command.extend(["--collect-submodules", "tkinterdnd2"])

    command.append(str(ENTRYPOINT))
    return command


def expected_output(dist: Path, target_platform: str) -> Path:
    if target_platform == "windows":
        return dist / "SpectrumHub" / "SpectrumHub.exe"
    if target_platform == "macos":
        return dist / "SpectrumHub.app"
    return dist / "SpectrumHub" / "SpectrumHub"


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build the Spectrum Hub desktop GUI with PyInstaller.")
    parser.add_argument(
        "--platform",
        choices=["windows", "macos", "linux"],
        default=host_platform(),
        help="Target platform. PyInstaller builds must run on the target OS.",
    )
    parser.add_argument("--dist", type=Path, default=Path(os.environ.get("SPECTRUM_HUB_DIST_ROOT", ROOT / "dist")))
    parser.add_argument("--work", type=Path, default=ROOT / "build/spectrum-hub-gui")
    parser.add_argument("--specpath", type=Path, default=ROOT / "build/spectrum-hub-gui")
    parser.add_argument(
        "--uac-admin",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Windows only: request administrator privileges in the executable manifest.",
    )
    parser.add_argument(
        "--allow-running",
        action="store_true",
        default=os.environ.get("SPECTRUM_HUB_ALLOW_RUNNING") == "1",
        help="Windows only: allow building while SpectrumHub.exe is running.",
    )
    parser.add_argument("--dry-run", action="store_true", help="Print the PyInstaller command without running it.")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    current_platform = host_platform()
    if args.platform != current_platform:
        print(
            f"PyInstaller cannot cross-compile Spectrum Hub here: host is {current_platform}, target is {args.platform}.",
            file=sys.stderr,
        )
        return 2

    env = env_with_pythonpath()
    command = build_command(args, env)
    print(" ".join(command), flush=True)

    if args.dry_run:
        return 0

    if not pyinstaller_available():
        print("PyInstaller is not installed. Run: npm run deps:hub-gui", file=sys.stderr)
        return 1

    if spectrum_hub_running() and not args.allow_running:
        print(
            "SpectrumHub.exe is still running. Close Spectrum Hub before rebuilding, or set SPECTRUM_HUB_ALLOW_RUNNING=1.",
            file=sys.stderr,
        )
        return 1

    result = subprocess.run(command, cwd=ROOT, env=env)
    if result.returncode:
        return result.returncode

    print(f"Built: {expected_output(args.dist, args.platform)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
