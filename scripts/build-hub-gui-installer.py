from __future__ import annotations

import argparse
import json
import os
import plistlib
import platform
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_APP_IDENTIFIER = "co.uk.agegatepro.spectrumhub"
DEFAULT_INSTALLER_IDENTIFIER = "co.uk.agegatepro.spectrumhub.pkg"


def host_platform() -> str:
    system = platform.system().lower()
    if system == "darwin":
        return "macos"
    if system == "windows":
        return "windows"
    if system == "linux":
        return "linux"
    return system


def package_version() -> str:
    package_json = ROOT / "package.json"
    try:
        metadata = json.loads(package_json.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return "0.0.0"
    return str(metadata.get("version") or "0.0.0").removeprefix("v")


def run(command: list[str], *, cwd: Path = ROOT, env: dict[str, str] | None = None) -> None:
    print(" ".join(command), flush=True)
    subprocess.run(command, cwd=cwd, check=True, env=env)


def build_app(args: argparse.Namespace) -> None:
    if args.skip_app_build:
        return
    run(
        [
            sys.executable,
            str(ROOT / "scripts/build-hub-gui.py"),
            "--platform",
            args.platform,
            "--dist",
            str(args.dist),
            "--app-version",
            args.app_version,
            "--bundle-identifier",
            args.app_identifier,
        ]
    )


def shell_single_quote(value: str) -> str:
    return "'" + value.replace("'", "'\"'\"'") + "'"


def write_macos_postinstall(path: Path, *, cli_package: str, require_npm: bool) -> None:
    npm_required = "1" if require_npm else "0"
    path.write_text(
        f"""#!/bin/sh
set -u

LOG_FILE="/var/log/spectrum-hub-install.log"
CLI_PACKAGE={shell_single_quote(cli_package)}
REQUIRE_NPM="{npm_required}"

log() {{
  printf '%s\\n' "$1" >> "$LOG_FILE"
}}

run_as_console_user() {{
  console_user="$(stat -f "%Su" /dev/console 2>/dev/null || true)"
  if [ -z "$console_user" ] || [ "$console_user" = "root" ]; then
    return 1
  fi
  su - "$console_user" -c "$1"
}}

find_user_npm() {{
  run_as_console_user 'command -v npm' 2>/dev/null && return 0
  for candidate in /opt/homebrew/bin/npm /usr/local/bin/npm /usr/bin/npm; do
    if [ -x "$candidate" ]; then
      printf '%s\\n' "$candidate"
      return 0
    fi
  done
  return 1
}}

install_cli() {{
  npm_path="$(find_user_npm || true)"
  if [ -z "$npm_path" ]; then
    log "npm was not found; install Node.js 18+ and run: npm install -g $CLI_PACKAGE"
    return 0
  fi

  quoted_npm="'$(printf "%s" "$npm_path" | sed "s/'/'\\\\''/g")'"
  install_command="$quoted_npm install -g $CLI_PACKAGE"
  if run_as_console_user "$install_command" >> "$LOG_FILE" 2>&1; then
    log "Installed Spectrum CLI with $npm_path: $CLI_PACKAGE"
    return 0
  fi

  log "User-level npm install failed; retrying as installer user."
  if "$npm_path" install -g "$CLI_PACKAGE" >> "$LOG_FILE" 2>&1; then
    log "Installed Spectrum CLI as installer user with $npm_path: $CLI_PACKAGE"
    return 0
  fi

  log "Spectrum CLI install failed; run manually: npm install -g $CLI_PACKAGE"
  [ "$REQUIRE_NPM" = "1" ] && return 1
  return 0
}}

log "Starting Spectrum Hub postinstall."
install_cli
status=$?
if [ "$status" -ne 0 ]; then
  log "Spectrum CLI install failed."
  exit "$status"
fi
log "Spectrum Hub postinstall complete."
exit 0
""",
        encoding="utf-8",
    )
    path.chmod(0o755)


def clean_macos_metadata(path: Path) -> None:
    xattr = shutil.which("xattr")
    if xattr is not None:
        subprocess.run([xattr, "-cr", str(path)], check=True)

    dot_clean = shutil.which("dot_clean")
    if dot_clean is not None:
        subprocess.run([dot_clean, "-m", str(path)], check=True)

    for apple_double in path.rglob("._*"):
        if apple_double.is_file() or apple_double.is_symlink():
            apple_double.unlink()


def write_macos_component_plist(root: Path, path: Path) -> None:
    component = [
        {
            "RootRelativeBundlePath": "Applications/Spectrum Hub.app",
            "BundleHasStrictIdentifier": True,
            "BundleIsRelocatable": False,
            "BundleIsVersionChecked": True,
            "BundleOverwriteAction": "upgrade",
            "ChildBundles": [
                {
                    "RootRelativeBundlePath": "Applications/Spectrum Hub.app/Contents/Frameworks/Python.framework",
                    "BundleOverwriteAction": "",
                }
            ],
        }
    ]
    with path.open("wb") as file:
        plistlib.dump(component, file, sort_keys=False)


def build_macos_pkg(args: argparse.Namespace) -> Path:
    pkgbuild = shutil.which("pkgbuild")
    if pkgbuild is None:
        raise RuntimeError("pkgbuild is required to create a macOS installer package.")

    build_app(args)
    app = args.dist / "SpectrumHub.app"
    if not app.exists():
        raise RuntimeError(f"Built app was not found: {app}")

    stage_parent = Path(tempfile.mkdtemp(prefix="spectrum-hub-gui-installer-"))
    stage = stage_parent / "macos-pkg"
    root = stage / "root"
    scripts = stage / "scripts"
    component_plist = stage / "components.plist"
    app_destination = root / "Applications" / "Spectrum Hub.app"
    output = args.output or args.dist / "installer" / f"SpectrumHub-{args.app_version}-macos.pkg"

    try:
        app_destination.parent.mkdir(parents=True, exist_ok=True)
        scripts.mkdir(parents=True, exist_ok=True)
        output.parent.mkdir(parents=True, exist_ok=True)

        shutil.copytree(app, app_destination, symlinks=True, copy_function=shutil.copy)
        write_macos_postinstall(
            scripts / "postinstall",
            cli_package=args.cli_package,
            require_npm=args.require_cli_install,
        )
        clean_macos_metadata(stage)
        write_macos_component_plist(root, component_plist)

        pkg_env = os.environ.copy()
        pkg_env["COPYFILE_DISABLE"] = "1"

        run(
            [
                pkgbuild,
                "--root",
                str(root),
                "--scripts",
                str(scripts),
                "--component-plist",
                str(component_plist),
                "--identifier",
                args.installer_identifier,
                "--version",
                args.app_version,
                "--install-location",
                "/",
                str(output),
            ],
            env=pkg_env,
        )
    finally:
        if os.environ.get("SPECTRUM_HUB_KEEP_INSTALLER_STAGE") != "1":
            shutil.rmtree(stage_parent, ignore_errors=True)
    return output


def build_windows_installer() -> None:
    script = ROOT / "scripts/build-hub-gui-installer.ps1"
    powershell = shutil.which("powershell") or shutil.which("pwsh")
    if powershell is None:
        raise RuntimeError("PowerShell is required to build the Windows installer.")
    run([powershell, "-ExecutionPolicy", "Bypass", "-File", str(script)])


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build the Spectrum Hub GUI installer for the host platform.")
    parser.add_argument("--platform", choices=["windows", "macos", "linux"], default=host_platform())
    parser.add_argument("--dist", type=Path, default=ROOT / "dist")
    parser.add_argument("--work", type=Path, default=ROOT / "build/spectrum-hub-gui-installer")
    parser.add_argument("--output", type=Path)
    parser.add_argument("--skip-app-build", action="store_true")
    parser.add_argument("--app-version", default=os.environ.get("SPECTRUM_HUB_APP_VERSION", package_version()))
    parser.add_argument("--app-identifier", default=os.environ.get("SPECTRUM_HUB_BUNDLE_IDENTIFIER", DEFAULT_APP_IDENTIFIER))
    parser.add_argument(
        "--installer-identifier",
        default=os.environ.get("SPECTRUM_HUB_INSTALLER_IDENTIFIER", DEFAULT_INSTALLER_IDENTIFIER),
    )
    parser.add_argument("--cli-package", default=os.environ.get("SPECTRUM_HUB_CLI_PACKAGE", "spectrumstore@latest"))
    parser.add_argument(
        "--require-cli-install",
        action="store_true",
        help="Fail the installer if npm cannot install the Spectrum CLI.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    current_platform = host_platform()
    if args.platform != current_platform:
        print(
            f"Installer builds must run on the target OS: host is {current_platform}, target is {args.platform}.",
            file=sys.stderr,
        )
        return 2

    try:
        if args.platform == "windows":
            build_windows_installer()
            return 0
        if args.platform == "macos":
            output = build_macos_pkg(args)
            print(f"Built: {output}")
            return 0
        print("Linux installer packaging is not implemented yet.", file=sys.stderr)
        return 2
    except subprocess.CalledProcessError as exc:
        return exc.returncode
    except RuntimeError as exc:
        print(str(exc), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
