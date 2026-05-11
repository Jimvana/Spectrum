from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PYTHONPATH_ENTRIES = [
    ROOT / "packages/core/src",
    ROOT / "packages/index/src",
    ROOT / "packages/cli/src",
    ROOT / "packages/sdk-python",
    ROOT / "packages/server/src",
]
PYTHON_TEST_PATHS = [
    "packages/core/tests",
    "packages/index/tests",
    "packages/cli/tests",
    "packages/sdk-python/tests",
    "packages/server/tests",
]


def _env_with_pythonpath() -> dict[str, str]:
    env = os.environ.copy()
    entries = [str(path) for path in PYTHONPATH_ENTRIES]
    existing = env.get("PYTHONPATH")
    if existing:
        entries.append(existing)
    env["PYTHONPATH"] = os.pathsep.join(entries)
    return env


def _run(command: list[str], *, cwd: Path, env: dict[str, str] | None = None) -> int:
    print(f"$ {' '.join(command)}", flush=True)
    return subprocess.run(command, cwd=cwd, env=env).returncode


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run Spectrum workspace tests.")
    parser.add_argument(
        "--python-only",
        action="store_true",
        help="Run only Python package tests.",
    )
    parser.add_argument(
        "--js-only",
        action="store_true",
        help="Run only JavaScript SDK tests.",
    )
    args = parser.parse_args(argv)

    if args.python_only and args.js_only:
        parser.error("--python-only and --js-only cannot be used together")

    if not args.js_only:
        code = _run(
            [sys.executable, "-m", "pytest", *PYTHON_TEST_PATHS],
            cwd=ROOT,
            env=_env_with_pythonpath(),
        )
        if code:
            return code

    if not args.python_only:
        npm = shutil.which("npm")
        if npm is None:
            print("npm was not found on PATH; cannot run JavaScript SDK tests.", file=sys.stderr)
            return 1
        code = _run([npm, "test"], cwd=ROOT / "packages/sdk-js")
        if code:
            return code

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
