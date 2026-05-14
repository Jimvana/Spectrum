from __future__ import annotations

import argparse
import importlib.util
import json
import os
import platform
import tempfile
import sys
from dataclasses import asdict, is_dataclass
from pathlib import Path


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
    from spectrum_core import unpack

    results = unpack(args.input, args.output, verbose=args.verbose)
    emit(results, as_json=args.json)
    return 0 if all(result.ok for result in results) else 1


def command_inspect(args: argparse.Namespace) -> int:
    from spectrum_core import inspect_pack, inspect_spec

    path = Path(args.input)
    if path.suffix.lower() == ".specpack":
        emit(inspect_pack(path), as_json=args.json)
    else:
        emit(inspect_spec(path), as_json=args.json)
    return 0


def command_verify(args: argparse.Namespace) -> int:
    from spectrum_core import verify_path

    report = verify_path(args.input)
    emit(report.to_dict(), as_json=args.json)
    return 0 if report.valid else 1


def command_index(args: argparse.Namespace) -> int:
    from spectrum_index import build_index

    result = build_index(args.input, output_path=args.output, embed=args.embed, verbose=args.verbose)
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
    )
    emit(results, as_json=args.json)
    return 0


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

    for module_name in ["spectrum_core", "spectrum_index", "spectrum_cli"]:
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

    index = sub.add_parser("index", help="Build a retrieval index for .spec, .spec directory, or .specpack")
    index.add_argument("input")
    index.add_argument("-o", "--output", help="Output index path")
    index.add_argument("--embed", action="store_true", help="Embed index.bin into a .specpack")
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
    search.add_argument("--json", action="store_true")
    search.set_defaults(func=command_search)

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
