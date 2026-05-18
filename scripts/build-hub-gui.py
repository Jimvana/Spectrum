from __future__ import annotations

import argparse
import json
import os
import plistlib
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
DEFAULT_BUNDLE_IDENTIFIER = "co.uk.agegatepro.spectrumhub"


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


def package_version() -> str:
    package_json = ROOT / "package.json"
    try:
        metadata = json.loads(package_json.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return "0.0.0"
    version = str(metadata.get("version") or "0.0.0")
    return version.removeprefix("v")


def macos_icon(work: Path) -> Path | None:
    source = ASSETS / "spec-icon.png"
    if not source.exists():
        return None
    try:
        from PIL import Image
    except Exception:
        return None

    destination = work / "SpectrumHub.icns"
    destination.parent.mkdir(parents=True, exist_ok=True)
    image = Image.open(source).convert("RGBA")
    sizes = [16, 32, 64, 128, 256, 512, 1024]
    rendered = []
    for size in sizes:
        canvas = Image.new("RGBA", (size, size), (0, 0, 0, 0))
        image.thumbnail((size, size), Image.LANCZOS)
        left = (size - image.width) // 2
        top = (size - image.height) // 2
        canvas.alpha_composite(image, (left, top))
        rendered.append(canvas)
        image = Image.open(source).convert("RGBA")
    rendered[-1].save(destination, format="ICNS", append_images=rendered[:-1])
    return destination


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

    if args.platform in {"windows", "macos", "linux"}:
        command.append("--windowed")

    if args.platform == "windows":
        icon = ASSETS / "spec-icon.ico"
        if icon.exists():
            command.extend(["--icon", str(icon)])
        if args.uac_admin:
            command.append("--uac-admin")
    elif args.platform == "macos":
        command.extend(["--osx-bundle-identifier", args.bundle_identifier])
        icon = macos_icon(args.work)
        if icon is not None:
            command.extend(["--icon", str(icon)])
    elif args.platform == "linux":
        icon = ASSETS / "spec-icon.png"
        if icon.exists():
            command.extend(["--icon", str(icon)])

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
            "--collect-submodules",
            "cryptography",
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


def update_macos_plist(app: Path, args: argparse.Namespace) -> None:
    plist_path = app / "Contents" / "Info.plist"
    if not plist_path.exists():
        return
    with plist_path.open("rb") as file:
        plist = plistlib.load(file)
    plist["CFBundleDisplayName"] = "Spectrum Hub"
    plist["CFBundleName"] = "Spectrum Hub"
    plist["CFBundleIdentifier"] = args.bundle_identifier
    plist["CFBundleShortVersionString"] = args.app_version
    plist["CFBundleVersion"] = args.app_version
    with plist_path.open("wb") as file:
        plistlib.dump(plist, file, sort_keys=False)


def resign_macos_app(app: Path) -> None:
    xattr = shutil.which("xattr")
    if xattr is not None:
        subprocess.run([xattr, "-cr", str(app)], check=True)

    codesign = shutil.which("codesign")
    if codesign is None:
        return
    subprocess.run(
        [codesign, "--force", "--deep", "--sign", "-", str(app)],
        check=True,
    )


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
        "--app-version",
        default=os.environ.get("SPECTRUM_HUB_APP_VERSION", package_version()),
        help="macOS only: CFBundleShortVersionString/CFBundleVersion value.",
    )
    parser.add_argument(
        "--bundle-identifier",
        default=os.environ.get("SPECTRUM_HUB_BUNDLE_IDENTIFIER", DEFAULT_BUNDLE_IDENTIFIER),
        help="macOS only: reverse-DNS bundle identifier.",
    )
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

    if args.platform == "macos":
        app = expected_output(args.dist, args.platform)
        update_macos_plist(app, args)
        resign_macos_app(app)

    print(f"Built: {expected_output(args.dist, args.platform)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
