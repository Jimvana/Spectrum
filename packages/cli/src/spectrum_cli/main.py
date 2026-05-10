from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict, is_dataclass
from pathlib import Path

from spectrum_core import (
    decode_file,
    encode_file,
    inspect_pack,
    inspect_spec,
    pack,
    unpack,
    verify_path,
)


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


def command_encode(args: argparse.Namespace) -> int:
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
    result = decode_file(args.input, args.output, verbose=args.verbose)
    emit(result, as_json=args.json)
    return 0 if result.ok else 1


def command_pack(args: argparse.Namespace) -> int:
    summary = pack(
        args.input,
        args.output,
        include_all=args.all,
        language=args.language,
        rle=args.rle,
        zlib_level=args.zlib_level,
        verbose=args.verbose,
    )
    emit(summary, as_json=args.json)
    return 0


def command_unpack(args: argparse.Namespace) -> int:
    results = unpack(args.input, args.output, verbose=args.verbose)
    emit(results, as_json=args.json)
    return 0 if all(result.ok for result in results) else 1


def command_inspect(args: argparse.Namespace) -> int:
    path = Path(args.input)
    if path.suffix.lower() == ".specpack":
        emit(inspect_pack(path), as_json=args.json)
    else:
        emit(inspect_spec(path), as_json=args.json)
    return 0


def command_verify(args: argparse.Namespace) -> int:
    report = verify_path(args.input)
    emit(report.to_dict(), as_json=args.json)
    return 0 if report.valid else 1


def add_common_codec_options(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--language", help="Force a language instead of extension detection")
    parser.add_argument("--rle", default="off", choices=["off", "auto", "force"], help="RLE mode")
    parser.add_argument("--zlib-level", type=int, default=9, choices=range(1, 10), metavar="1-9")
    parser.add_argument("--verbose", action="store_true", help="Show lower-level codec output")
    parser.add_argument("--json", action="store_true", help="Emit machine-readable JSON")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="spectrum-core", description="Spectrum Core command line tools")
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
    add_common_codec_options(pack_parser)
    pack_parser.set_defaults(func=command_pack)

    unpack_parser = sub.add_parser("unpack", aliases=["decode-pack"], help="Decode a .specpack")
    unpack_parser.add_argument("input")
    unpack_parser.add_argument("output")
    unpack_parser.add_argument("--verbose", action="store_true")
    unpack_parser.add_argument("--json", action="store_true")
    unpack_parser.set_defaults(func=command_unpack)

    inspect = sub.add_parser("inspect", aliases=["info"], help="Inspect .spec or .specpack metadata")
    inspect.add_argument("input")
    inspect.add_argument("--json", action="store_true")
    inspect.set_defaults(func=command_inspect)

    verify = sub.add_parser("verify", help="Verify .spec, .spec directory, or .specpack fidelity")
    verify.add_argument("input")
    verify.add_argument("--json", action="store_true")
    verify.set_defaults(func=command_verify)

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
        print(f"spectrum-core: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
