from __future__ import annotations

import argparse
import getpass
import os
import sys

from .app import PackRegistry, run_server


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="spectrum-server", description="Run the local Spectrum HTTP API")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=7777)
    parser.add_argument("--pack", action="append", default=[], help="Register a pack as id=path or path")
    parser.add_argument("--quiet", action="store_true")
    parser.add_argument("--unlock", action="store_true", help="Prompt to unlock encrypted packs at startup")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    registry = PackRegistry()
    try:
        passphrase = None
        if args.unlock:
            passphrase = os.environ.get("SPECTRUM_PASSPHRASE")
            if passphrase is None:
                passphrase = getpass.getpass("Unlock passphrase: ")
            if not passphrase:
                raise ValueError("passphrase must not be empty")
        for idx, value in enumerate(args.pack, start=1):
            if "=" in value:
                pack_id, path = value.split("=", 1)
            else:
                path = value
                pack_id = f"pack-{idx}"
            registry.add(pack_id, path, passphrase=passphrase)
        print(f"spectrum-server listening on http://{args.host}:{args.port}", file=sys.stderr)
        run_server(host=args.host, port=args.port, registry=registry, quiet=args.quiet)
    except KeyboardInterrupt:
        return 130
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
