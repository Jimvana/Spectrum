#!/usr/bin/env python3
from __future__ import annotations

import argparse
import contextlib
import io
import json
import math
import re
import shutil
import sys
import tempfile
import time
import zipfile
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable


CLI_DIR = Path(__file__).resolve().parents[1]
DEFAULT_REPO_ROOT = CLI_DIR.parent
VENDORED_REPO_ROOT = CLI_DIR / "vendor" / "spectrum_algo"
REPO_ROOT = Path(__file__).resolve()
root_candidates = []
if "SPECTRUM_REPO_ROOT" in __import__("os").environ:
    root_candidates.append(Path(__import__("os").environ["SPECTRUM_REPO_ROOT"]).expanduser())
root_candidates.extend([Path.cwd(), *Path.cwd().parents, DEFAULT_REPO_ROOT, VENDORED_REPO_ROOT])
for parent in root_candidates:
    if (parent / "spec_format" / "spec_encoder.py").exists() and (parent / "dictionary.py").exists():
        REPO_ROOT = parent
        break

if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))
if str(CLI_DIR) not in sys.path:
    sys.path.insert(0, str(CLI_DIR))

import dictionary as D
from rag.indexer import RETRIEVAL_PROFILE, build_index, index_directory, load_index, save_index
from rag.normalization import retrieval_token_ids
from rag.query import BM25, encode_query, print_results, search
from spec_format.spec_decoder import SpecFormatError, decode_file, parse_header
from spec_format.spec_encoder import (
    LANGUAGE_CSS,
    LANGUAGE_HTML,
    LANGUAGE_JS,
    LANGUAGE_JAVA,
    LANGUAGE_PHP,
    LANGUAGE_PYTHON,
    LANGUAGE_RUST,
    LANGUAGE_SQL,
    LANGUAGE_TEXT,
    LANGUAGE_TS,
    LANGUAGE_XML,
    encode_file,
)


VERSION = "0.4.1"
PACK_VERSION = 1
PACK_INDEX_NAME = "index.bin"
SUPPORTED_EXTS = {
    ".py",
    ".html",
    ".htm",
    ".js",
    ".mjs",
    ".cjs",
    ".css",
    ".txt",
    ".md",
    ".ts",
    ".tsx",
    ".sql",
    ".rs",
    ".php",
    ".phtml",
    ".xml",
    ".java",
}
LANG_MAP = {
    "py": LANGUAGE_PYTHON,
    "python": LANGUAGE_PYTHON,
    "html": LANGUAGE_HTML,
    "js": LANGUAGE_JS,
    "javascript": LANGUAGE_JS,
    "css": LANGUAGE_CSS,
    "txt": LANGUAGE_TEXT,
    "text": LANGUAGE_TEXT,
    "md": LANGUAGE_TEXT,
    "ts": LANGUAGE_TS,
    "typescript": LANGUAGE_TS,
    "sql": LANGUAGE_SQL,
    "rs": LANGUAGE_RUST,
    "rust": LANGUAGE_RUST,
    "php": LANGUAGE_PHP,
    "xml": LANGUAGE_XML,
    "wiki": LANGUAGE_XML,
    "java": LANGUAGE_JAVA,
}
LANG_NAMES = {
    LANGUAGE_PYTHON: "Python",
    LANGUAGE_HTML: "HTML",
    LANGUAGE_JS: "JavaScript",
    LANGUAGE_CSS: "CSS",
    LANGUAGE_TEXT: "Text",
    LANGUAGE_TS: "TypeScript",
    LANGUAGE_SQL: "SQL",
    LANGUAGE_RUST: "Rust",
    LANGUAGE_PHP: "PHP",
    LANGUAGE_XML: "XML/Wiki",
    LANGUAGE_JAVA: "Java",
}


@dataclass
class EncodeResult:
    source: Path
    output: Path
    original_size: int
    spec_size: int


@dataclass
class BenchDoc:
    id: int
    name: str
    path: str
    text: str


def die(message: str, code: int = 1) -> None:
    print(f"spec: {message}", file=sys.stderr)
    raise SystemExit(code)


def rel_to_posix(path: Path) -> str:
    return path.as_posix()


def is_pack(path: Path) -> bool:
    return path.suffix.lower() == ".specpack"


def is_index_file(path: Path) -> bool:
    return path.suffix.lower() == ".bin" or path.name.endswith(".index")


def default_index_path(target: Path) -> Path:
    if target.is_dir():
        return target / "spectrum.index.bin"
    return target.with_name(target.name + ".index.bin")


def pack_has_index(pack_path: Path) -> bool:
    with zipfile.ZipFile(pack_path) as pack:
        return PACK_INDEX_NAME in pack.namelist()


def replace_pack_member(pack_path: Path, source: Path, arcname: str) -> None:
    with tempfile.TemporaryDirectory(prefix="spectrum-pack-write-") as tmp_name:
        tmp_zip = Path(tmp_name) / pack_path.name
        with zipfile.ZipFile(pack_path) as src, zipfile.ZipFile(
            tmp_zip, "w", compression=zipfile.ZIP_DEFLATED
        ) as dst:
            for item in src.infolist():
                if item.filename == arcname:
                    continue
                dst.writestr(item, src.read(item.filename))
            dst.write(source, arcname)
        tmp_zip.replace(pack_path)


def iter_source_files(root: Path, include_all: bool = False) -> Iterable[Path]:
    if root.is_file():
        yield root
        return
    for path in sorted(root.rglob("*")):
        if not path.is_file():
            continue
        if ".git" in path.parts or "node_modules" in path.parts or "__pycache__" in path.parts:
            continue
        if path.suffix.lower() in {".spec", ".specpack"}:
            continue
        if include_all or path.suffix.lower() in SUPPORTED_EXTS:
            yield path


def default_spec_output(source: Path, base: Path | None = None, out_dir: Path | None = None) -> Path:
    if out_dir is None:
        return source.with_name(source.name + ".spec")
    rel = source.name if base is None else source.relative_to(base)
    return out_dir / Path(str(rel) + ".spec")


def encode_one(source: Path, output: Path, lang: str | None, no_rle: bool, zlib_level: int) -> EncodeResult:
    language_id = LANG_MAP[lang] if lang else LANGUAGE_PYTHON
    stats = encode_file(
        str(source),
        str(output),
        use_rle=not no_rle,
        language_id=language_id,
        zlib_level=zlib_level,
    )
    return EncodeResult(
        source=source,
        output=output,
        original_size=int(stats["original_size"]),
        spec_size=int(stats["spec_size"]),
    )


def build_index_for_target(target: Path, output: Path | None = None) -> Path:
    if is_pack(target):
        with tempfile.TemporaryDirectory(prefix="spectrum-index-") as tmp_name:
            tmp = Path(tmp_name)
            with zipfile.ZipFile(target) as pack:
                pack.extractall(tmp)
            index = index_directory(tmp / "files")
            index_path = output or (tmp / PACK_INDEX_NAME)
            index_path.parent.mkdir(parents=True, exist_ok=True)
            save_index(index, index_path)
            if output is None:
                replace_pack_member(target, index_path, PACK_INDEX_NAME)
                print(f"[indexer] Embedded index -> {target}#{PACK_INDEX_NAME}")
                return target
            return index_path
    elif target.is_file() and target.suffix.lower() == ".spec":
        output = output or default_index_path(target)
        output.parent.mkdir(parents=True, exist_ok=True)
        index = build_index([target])
    else:
        output = output or default_index_path(target)
        output.parent.mkdir(parents=True, exist_ok=True)
        index = index_directory(target)

    save_index(index, output)
    return output


def load_index_from_pack(pack_path: Path) -> dict:
    with tempfile.TemporaryDirectory(prefix="spectrum-pack-index-") as tmp_name:
        tmp = Path(tmp_name)
        with zipfile.ZipFile(pack_path) as pack:
            if PACK_INDEX_NAME not in pack.namelist():
                raise FileNotFoundError(PACK_INDEX_NAME)
            pack.extract(PACK_INDEX_NAME, tmp)
        return load_index(tmp / PACK_INDEX_NAME)


def index_profile(index: dict) -> str | None:
    return index.get("meta", {}).get("retrieval_profile")


def command_encode(args: argparse.Namespace) -> int:
    source = Path(args.input).expanduser().resolve()
    if not source.exists():
        die(f"input not found: {source}")

    if args.archive:
        if source.is_file():
            default_name = source.name + ".specpack"
            base = source.parent
        else:
            default_name = source.name.rstrip("/") + ".specpack"
            base = source
        pack_path = Path(args.output).expanduser().resolve() if args.output else Path.cwd() / default_name
        files = list(iter_source_files(source, include_all=args.all))
        if not files:
            die("no encodable files found")

        with tempfile.TemporaryDirectory(prefix="spectrum-pack-") as tmp_name:
            tmp = Path(tmp_name)
            entries = []
            total_original = 0
            total_spec = 0
            for file_path in files:
                rel = file_path.relative_to(base) if source.is_dir() else Path(file_path.name)
                spec_rel = Path("files") / Path(str(rel) + ".spec")
                spec_path = tmp / spec_rel
                result = encode_one(file_path, spec_path, args.lang, args.no_rle, args.zlib_level)
                total_original += result.original_size
                total_spec += result.spec_size
                entries.append(
                    {
                        "source": rel_to_posix(rel),
                        "spec": rel_to_posix(spec_rel),
                        "original_size": result.original_size,
                        "spec_size": result.spec_size,
                    }
                )

            manifest = {
                "format": "spectrum.specpack",
                "version": PACK_VERSION,
                "dict_version": D.DICT_VERSION,
                "source_root": source.name,
                "entries": entries,
            }
            pack_path.parent.mkdir(parents=True, exist_ok=True)
            with zipfile.ZipFile(pack_path, "w", compression=zipfile.ZIP_DEFLATED) as pack:
                pack.writestr("manifest.json", json.dumps(manifest, indent=2))
                for entry in entries:
                    pack.write(tmp / entry["spec"], entry["spec"])

        print(
            f"Packed {len(entries)} files -> {pack_path} "
            f"({total_original:,} B source, {total_spec:,} B spec payload)"
        )
        if args.index:
            print(f"Building embedded index for {pack_path.name}...")
            build_index_for_target(pack_path)
        return 0

    out_dir = Path(args.output).expanduser().resolve() if args.output and source.is_dir() else None
    if source.is_file():
        output = Path(args.output).expanduser().resolve() if args.output else default_spec_output(source)
        encode_one(source, output, args.lang, args.no_rle, args.zlib_level)
        if args.index:
            build_index_for_target(output)
        return 0

    files = list(iter_source_files(source, include_all=args.all))
    if not files:
        die("no encodable files found")
    output_root = out_dir or source.with_name(source.name + ".specdir")
    total_original = 0
    total_spec = 0
    for file_path in files:
        output = default_spec_output(file_path, base=source, out_dir=output_root)
        result = encode_one(file_path, output, args.lang, args.no_rle, args.zlib_level)
        total_original += result.original_size
        total_spec += result.spec_size
    print(f"Encoded {len(files)} files -> {output_root} ({total_original:,} B -> {total_spec:,} B)")
    if args.index:
        build_index_for_target(output_root)
    return 0


def decode_spec_file(spec_path: Path, output: Path | None = None) -> dict:
    if output is None:
        if spec_path.name.endswith(".spec"):
            output = spec_path.with_name(spec_path.name[: -len(".spec")])
        else:
            output = spec_path.with_suffix("")
    return decode_file(str(spec_path), str(output))


def command_decode(args: argparse.Namespace) -> int:
    input_path = Path(args.input).expanduser().resolve()
    if not input_path.exists():
        die(f"input not found: {input_path}")

    if is_pack(input_path):
        out_root = Path(args.output).expanduser().resolve() if args.output else Path.cwd() / input_path.stem
        with tempfile.TemporaryDirectory(prefix="spectrum-unpack-") as tmp_name:
            tmp = Path(tmp_name)
            with zipfile.ZipFile(input_path) as pack:
                manifest = json.loads(pack.read("manifest.json").decode("utf-8"))
                pack.extractall(tmp)
            for entry in manifest.get("entries", []):
                spec_path = tmp / entry["spec"]
                output = out_root / entry["source"]
                decode_file(str(spec_path), str(output))
        print(f"Decoded {input_path.name} -> {out_root}")
        return 0

    if input_path.is_dir():
        out_root = Path(args.output).expanduser().resolve() if args.output else input_path.with_name(input_path.name + "_decoded")
        specs = sorted(input_path.rglob("*.spec"))
        if not specs:
            die("no .spec files found")
        for spec_path in specs:
            rel = spec_path.relative_to(input_path)
            name = rel.name[: -len(".spec")] if rel.name.endswith(".spec") else rel.stem
            output = out_root / rel.parent / name
            decode_file(str(spec_path), str(output))
        print(f"Decoded {len(specs)} files -> {out_root}")
        return 0

    output = Path(args.output).expanduser().resolve() if args.output else None
    result = decode_spec_file(input_path, output)
    return 0 if result["length_ok"] and result["checksum_ok"] else 1


def spec_info(path: Path) -> dict:
    raw = path.read_bytes()
    meta = parse_header(raw)
    return {
        "path": str(path),
        "bytes": len(raw),
        "dict_version": meta["dict_version"],
        "language": LANG_NAMES.get(meta["language_id"], f"lang{meta['language_id']}"),
        "original_bytes": meta["orig_length"],
        "rle": meta["rle_enabled"],
        "checksum": meta["checksum"],
        "ratio": round(len(raw) / meta["orig_length"], 4) if meta["orig_length"] else 0,
    }


def print_info_row(info: dict) -> None:
    print(f"Path:        {info['path']}")
    print(f"Type:        .spec")
    print(f"Dict:        v{info['dict_version']}")
    print(f"Language:    {info['language']}")
    print(f"Original:    {info['original_bytes']:,} B")
    print(f"Stored:      {info['bytes']:,} B")
    print(f"Ratio:       {info['ratio']:.4f}x")
    print(f"RLE:         {'yes' if info['rle'] else 'no'}")
    print(f"Checksum:    {info['checksum']}")


def command_info(args: argparse.Namespace) -> int:
    path = Path(args.input).expanduser().resolve()
    if not path.exists():
        die(f"input not found: {path}")
    if is_pack(path):
        with zipfile.ZipFile(path) as pack:
            manifest = json.loads(pack.read("manifest.json").decode("utf-8"))
            embedded_index = PACK_INDEX_NAME in pack.namelist()
            entries = manifest.get("entries", [])
            total_original = sum(int(entry.get("original_size", 0)) for entry in entries)
            total_spec = sum(int(entry.get("spec_size", 0)) for entry in entries)
        print(f"Path:        {path}")
        print("Type:        .specpack")
        print(f"Format:      v{manifest.get('version', '?')}")
        print(f"Dict:        v{manifest.get('dict_version', '?')}")
        print(f"Files:       {len(entries):,}")
        print(f"Original:    {total_original:,} B")
        print(f"Spec bytes:  {total_spec:,} B")
        print(f"Pack bytes:  {path.stat().st_size:,} B")
        if embedded_index:
            try:
                profile = index_profile(load_index_from_pack(path)) or "legacy"
            except Exception:
                profile = "unreadable"
            print(f"Index:       embedded ({profile})")
        else:
            print("Index:       not built")
        return 0
    print_info_row(spec_info(path))
    return 0


def command_verify(args: argparse.Namespace) -> int:
    path = Path(args.input).expanduser().resolve()
    if not path.exists():
        die(f"input not found: {path}")
    failures = 0
    checked = 0
    with tempfile.TemporaryDirectory(prefix="spectrum-verify-") as tmp_name:
        tmp = Path(tmp_name)
        if is_pack(path):
            with zipfile.ZipFile(path) as pack:
                manifest = json.loads(pack.read("manifest.json").decode("utf-8"))
                pack.extractall(tmp / "pack")
            for entry in manifest.get("entries", []):
                checked += 1
                result = decode_file(str(tmp / "pack" / entry["spec"]), str(tmp / "decoded" / entry["source"]))
                if not (result["length_ok"] and result["checksum_ok"]):
                    failures += 1
        elif path.is_dir():
            for spec_path in sorted(path.rglob("*.spec")):
                checked += 1
                result = decode_file(str(spec_path), str(tmp / spec_path.name))
                if not (result["length_ok"] and result["checksum_ok"]):
                    failures += 1
        else:
            checked += 1
            result = decode_file(str(path), str(tmp / path.stem))
            if not (result["length_ok"] and result["checksum_ok"]):
                failures += 1
    if failures:
        print(f"Verify failed: {failures}/{checked} files failed")
        return 1
    print(f"Verify OK: {checked} file{'s' if checked != 1 else ''}")
    return 0


def command_index(args: argparse.Namespace) -> int:
    source = Path(args.input).expanduser().resolve()
    if not source.exists():
        die(f"input not found: {source}")
    output = Path(args.output).expanduser().resolve() if args.output else None
    build_index_for_target(source, output)
    return 0


def command_search(args: argparse.Namespace) -> int:
    index = None
    if args.index:
        index_path = Path(args.index).expanduser().resolve()
    elif args.target:
        target = Path(args.target).expanduser().resolve()
        if not target.exists():
            die(f"target not found: {target}")
        if is_pack(target):
            if not pack_has_index(target):
                print(f"No embedded index found. Building index for {target.name}...")
                build_index_for_target(target)
            index = load_index_from_pack(target)
            if index_profile(index) != RETRIEVAL_PROFILE:
                print(f"Embedded index uses an old retrieval profile. Rebuilding {target.name}...")
                build_index_for_target(target)
                index = load_index_from_pack(target)
            index_path = None
        elif is_index_file(target):
            index_path = target
        else:
            index_path = default_index_path(target)
            if not index_path.exists():
                print(f"No index found. Building index for {target.name}...")
                build_index_for_target(target, index_path)
            else:
                existing = load_index(index_path)
                if index_profile(existing) != RETRIEVAL_PROFILE:
                    print(f"Index uses an old retrieval profile. Rebuilding {target.name}...")
                    build_index_for_target(target, index_path)
                else:
                    index = existing
    else:
        cwd_index = Path.cwd() / "spectrum.index.bin"
        cwd_packs = sorted(Path.cwd().glob("*.specpack"))
        if cwd_index.exists():
            index_path = cwd_index
        elif len(cwd_packs) == 1:
            target = cwd_packs[0]
            print(f"Using {target.name}")
            if not pack_has_index(target):
                print(f"No embedded index found. Building index for {target.name}...")
                build_index_for_target(target)
            index = load_index_from_pack(target)
            if index_profile(index) != RETRIEVAL_PROFILE:
                print(f"Embedded index uses an old retrieval profile. Rebuilding {target.name}...")
                build_index_for_target(target)
                index = load_index_from_pack(target)
            index_path = None
        elif len(cwd_packs) > 1:
            die("multiple .specpack files found; pass the one you want to search")
        else:
            candidates = [
                Path.cwd() / "rag" / "index.bin",
                REPO_ROOT / "rag" / "index.bin",
            ]
            index_path = next((candidate for candidate in candidates if candidate.exists()), candidates[0])
    if index is None and not index_path.exists():
        die("no index found; run `spec index <folder-or-pack>` or pass --index")
    if index is None:
        index = load_index(index_path)
    results = search(args.query, index, top_k=args.top, lang=args.lang)
    print_results(results, query=args.query)
    return 0


WORD_RE = re.compile(r"[A-Za-z][A-Za-z0-9_/-]{2,}")


def percentile(values: list[float], pct: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    idx = min(len(ordered) - 1, max(0, math.ceil(len(ordered) * pct / 100) - 1))
    return ordered[idx]


def dir_size(path: Path) -> int:
    if path.is_file():
        return path.stat().st_size
    return sum(item.stat().st_size for item in path.rglob("*") if item.is_file())


def quiet_call(func, *args, **kwargs):
    with contextlib.redirect_stdout(io.StringIO()):
        return func(*args, **kwargs)


def load_benchmark_docs_from_folder(root: Path, include_all: bool = False) -> list[BenchDoc]:
    docs: list[BenchDoc] = []
    for path in iter_source_files(root, include_all=include_all):
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except Exception:
            continue
        docs.append(BenchDoc(len(docs), path.stem, rel_to_posix(path.relative_to(root)), text))
    return docs


def load_benchmark_docs_from_pack(pack_path: Path) -> list[BenchDoc]:
    docs: list[BenchDoc] = []
    with tempfile.TemporaryDirectory(prefix="spectrum-bench-pack-") as tmp_name:
        tmp = Path(tmp_name)
        with zipfile.ZipFile(pack_path) as pack:
            manifest = json.loads(pack.read("manifest.json").decode("utf-8"))
            pack.extractall(tmp / "pack")
        for entry in manifest.get("entries", []):
            spec_path = tmp / "pack" / entry["spec"]
            out_path = tmp / "decoded" / entry["source"]
            result = quiet_call(decode_file, str(spec_path), str(out_path))
            if result.get("length_ok") and result.get("checksum_ok"):
                text = out_path.read_text(encoding="utf-8", errors="replace")
                docs.append(BenchDoc(len(docs), Path(entry["source"]).stem, entry["source"], text))
    return docs


def ensure_benchmark_pack(target: Path, tmp: Path, include_all: bool = False) -> Path:
    if is_pack(target):
        if not pack_has_index(target):
            build_index_for_target(target)
        else:
            index = load_index_from_pack(target)
            if index_profile(index) != RETRIEVAL_PROFILE:
                build_index_for_target(target)
        return target

    if target.is_file() and target.suffix.lower() == ".spec":
        pack_path = tmp / (target.stem + ".specpack")
        manifest = {
            "format": "spectrum.specpack",
            "version": PACK_VERSION,
            "dict_version": D.DICT_VERSION,
            "source_root": target.stem,
            "entries": [{"source": target.stem, "spec": f"files/{target.name}", "original_size": 0, "spec_size": target.stat().st_size}],
        }
        with zipfile.ZipFile(pack_path, "w", compression=zipfile.ZIP_DEFLATED) as pack:
            pack.writestr("manifest.json", json.dumps(manifest, indent=2))
            pack.write(target, f"files/{target.name}")
        build_index_for_target(pack_path)
        return pack_path

    pack_path = tmp / (target.name + ".specpack")
    files = list(iter_source_files(target, include_all=include_all))
    if not files:
        die("no benchmarkable files found")
    pack_tmp = tmp / "pack-build"
    entries = []
    for file_path in files:
        rel = file_path.relative_to(target)
        spec_rel = Path("files") / Path(str(rel) + ".spec")
        spec_path = pack_tmp / spec_rel
        result = quiet_call(encode_one, file_path, spec_path, None, False, 9)
        entries.append({
            "source": rel_to_posix(rel),
            "spec": rel_to_posix(spec_rel),
            "original_size": result.original_size,
            "spec_size": result.spec_size,
        })
    manifest = {
        "format": "spectrum.specpack",
        "version": PACK_VERSION,
        "dict_version": D.DICT_VERSION,
        "source_root": target.name,
        "entries": entries,
    }
    with zipfile.ZipFile(pack_path, "w", compression=zipfile.ZIP_DEFLATED) as pack:
        pack.writestr("manifest.json", json.dumps(manifest, indent=2))
        for entry in entries:
            pack.write(pack_tmp / entry["spec"], entry["spec"])
    build_index_for_target(pack_path)
    return pack_path


def token_ids_for_benchmark_text(text: str, path: str = "") -> list[int]:
    ids = []
    seen = set()
    for token_id in retrieval_token_ids(f"{path} {text}"):
        token = D.SPEC_ID_TO_TOKEN.get(token_id, "")
        if token_id not in seen and token and not token.startswith("CTRL:") and any(ch.isalnum() for ch in token):
            ids.append(token_id)
            seen.add(token_id)
    return ids


def build_raw_bm25_store(docs: list[BenchDoc], out_dir: Path) -> tuple[dict, int, int, float]:
    start = time.perf_counter()
    out_dir.mkdir(parents=True, exist_ok=True)
    documents = []
    inverted: dict[int, list[int]] = {}
    total_tokens = 0

    chunks_path = out_dir / "chunks.jsonl"
    with chunks_path.open("w", encoding="utf-8") as f:
        for doc in docs:
            f.write(json.dumps({"id": doc.id, "name": doc.name, "path": doc.path, "text": doc.text}, ensure_ascii=False) + "\n")
            ids = token_ids_for_benchmark_text(doc.text, doc.path)
            freq = Counter(ids)
            total_tokens += len(ids)
            documents.append({
                "id": doc.id,
                "name": doc.name,
                "path": doc.path,
                "token_count": len(ids),
                "freq": [[tid, count] for tid, count in freq.items()],
            })
            for tid in freq:
                inverted.setdefault(tid, []).append(doc.id)

    index = {
        "meta": {
            "total_docs": len(documents),
            "avg_doc_length": round(total_tokens / len(documents), 2) if documents else 0.0,
            "retrieval_profile": RETRIEVAL_PROFILE,
        },
        "documents": documents,
        "inverted": {str(tid): doc_ids for tid, doc_ids in inverted.items()},
    }
    (out_dir / "raw_bm25_index.json").write_text(json.dumps(index, separators=(",", ":")), encoding="utf-8")
    return index, chunks_path.stat().st_size, (out_dir / "raw_bm25_index.json").stat().st_size, time.perf_counter() - start


class SimpleBM25:
    def __init__(self, index: dict, k1: float = 1.5, b: float = 0.75):
        self.docs = index["documents"]
        self.N = index["meta"]["total_docs"]
        self.avdl = index["meta"]["avg_doc_length"] or 1.0
        self.k1 = k1
        self.b = b
        self.freq = [{int(tid): int(count) for tid, count in doc["freq"]} for doc in self.docs]
        self.lengths = [int(doc["token_count"]) for doc in self.docs]
        self.inv = {int(tid): doc_ids for tid, doc_ids in index["inverted"].items()}

    def idf(self, token_id: int) -> float:
        df = len(self.inv.get(token_id, []))
        return math.log((self.N - df + 0.5) / (df + 0.5) + 1)

    def search(self, query: str, top_k: int = 5) -> list[dict]:
        query_ids = encode_query(query, lang="txt", normalize=True)
        candidates = set()
        for tid in set(query_ids):
            candidates.update(self.inv.get(tid, []))
        scored = []
        for doc_id in candidates:
            freq = self.freq[doc_id]
            dl = self.lengths[doc_id]
            norm = 1 - self.b + self.b * (dl / self.avdl)
            score = 0.0
            for tid in query_ids:
                tf = freq.get(tid, 0)
                if tf:
                    score += self.idf(tid) * (tf * (self.k1 + 1)) / (tf + self.k1 * norm)
            scored.append((doc_id, score))
        scored.sort(key=lambda item: item[1], reverse=True)
        return [{"doc_id": doc_id, "name": self.docs[doc_id]["name"], "path": self.docs[doc_id]["path"], "score": score} for doc_id, score in scored[:top_k]]


def generate_benchmark_queries(docs: list[BenchDoc], limit: int) -> list[dict]:
    queries = []
    for doc in docs:
        words = []
        for value in [Path(doc.path).stem, doc.path, doc.text[:500]]:
            for match in WORD_RE.findall(value):
                word = match.replace("_", " ").replace("-", " ").replace("/", " ").lower()
                for part in word.split():
                    if len(part) >= 3 and part not in words:
                        words.append(part)
                if len(words) >= 5:
                    break
            if len(words) >= 5:
                break
        if words:
            queries.append({"query": " ".join(words[:5]), "expected_name": doc.name, "expected_path": doc.path})
        if len(queries) >= limit:
            break
    return queries


def evaluate_raw(index: dict, queries: list[dict], top_k: int) -> dict:
    bm25 = SimpleBM25(index)
    ranks = []
    times = []
    for query in queries:
        start = time.perf_counter()
        results = bm25.search(query["query"], top_k=top_k)
        times.append((time.perf_counter() - start) * 1000)
        rank = 0
        for idx, result in enumerate(results, start=1):
            if result["path"] == query["expected_path"] or result["name"] == query["expected_name"]:
                rank = idx
                break
        ranks.append(rank)
    return summarize_ranks(ranks, times)


def evaluate_spectrum(index: dict, queries: list[dict], top_k: int) -> dict:
    bm25 = BM25(index)
    ranks = []
    times = []
    for query in queries:
        start = time.perf_counter()
        query_ids = encode_query(query["query"], lang="txt", normalize=True)
        candidates = set()
        for tid in set(query_ids):
            candidates.update(bm25._inv.get(tid, []))
        scored = [(doc_id, bm25.score(doc_id, query_ids)) for doc_id in candidates]
        scored.sort(key=lambda item: item[1], reverse=True)
        results = [
            {"doc_id": doc_id, "name": index["documents"][doc_id]["name"], "path": index["documents"][doc_id]["path"]}
            for doc_id, _ in scored[:top_k]
        ]
        times.append((time.perf_counter() - start) * 1000)
        rank = 0
        for idx, result in enumerate(results, start=1):
            result_path = result.get("path", "")
            if result["name"] == query["expected_name"] or result_path.endswith(query["expected_path"] + ".spec"):
                rank = idx
                break
        ranks.append(rank)
    return summarize_ranks(ranks, times)


def summarize_ranks(ranks: list[int], times: list[float]) -> dict:
    total = len(ranks) or 1
    return {
        "hit_at_1": sum(1 for rank in ranks if rank == 1) / total,
        "mrr": sum((1 / rank) for rank in ranks if rank) / total,
        "recall_at_5": sum(1 for rank in ranks if 1 <= rank <= 5) / total,
        "avg_query_ms": sum(times) / len(times) if times else 0.0,
        "p95_query_ms": percentile(times, 95),
    }


def write_benchmark_report(report: dict, out_dir: Path) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    md = f"""# Spectrum Benchmark

- Target: `{report['target']}`
- Files: {report['files']}
- Queries: {report['queries']}

## Storage

| Store | Bytes | Ratio vs raw | Payload bytes | Index bytes | Build sec |
|---|---:|---:|---:|---:|---:|
| Raw text + BM25 | {report['raw']['bytes']:,} | {report['raw']['ratio_vs_raw']:.3f}x | {report['raw']['payload_bytes']:,} | {report['raw']['index_bytes']:,} | {report['raw']['build_sec']:.3f} |
| Spectrum `.specpack` + BM25 | {report['spectrum']['bytes']:,} | {report['spectrum']['ratio_vs_raw']:.3f}x | {report['spectrum']['payload_bytes']:,} | {report['spectrum']['index_bytes']:,} | {report['spectrum']['build_sec']:.3f} |

## Retrieval

| Store | Hit@1 | MRR | Recall@5 | Avg ms | P95 ms |
|---|---:|---:|---:|---:|---:|
| Raw text + BM25 | {report['raw']['hit_at_1']:.3f} | {report['raw']['mrr']:.3f} | {report['raw']['recall_at_5']:.3f} | {report['raw']['avg_query_ms']:.3f} | {report['raw']['p95_query_ms']:.3f} |
| Spectrum `.specpack` + BM25 | {report['spectrum']['hit_at_1']:.3f} | {report['spectrum']['mrr']:.3f} | {report['spectrum']['recall_at_5']:.3f} | {report['spectrum']['avg_query_ms']:.3f} | {report['spectrum']['p95_query_ms']:.3f} |

## Fidelity

- Spectrum verified: `{report['spectrum']['verified']}`

This is a local sparse-retrieval benchmark against raw text + BM25. It is not an embedding/vector database benchmark.
"""
    (out_dir / "report.md").write_text(md, encoding="utf-8")


def command_benchmark(args: argparse.Namespace) -> int:
    target = Path(args.input).expanduser().resolve()
    if not target.exists():
        die(f"input not found: {target}")
    out_dir = Path(args.output).expanduser().resolve() if args.output else Path.cwd() / "spec-benchmark"
    if out_dir.exists() and args.clean:
        shutil.rmtree(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    with tempfile.TemporaryDirectory(prefix="spectrum-bench-") as tmp_name:
        tmp = Path(tmp_name)
        start = time.perf_counter()
        pack_path = ensure_benchmark_pack(target, tmp, include_all=args.all)
        spectrum_build_sec = time.perf_counter() - start
        spectrum_index = load_index_from_pack(pack_path)

        docs = load_benchmark_docs_from_pack(pack_path)
        if not docs:
            die("no documents available for benchmark")
        queries = generate_benchmark_queries(docs, min(args.queries, len(docs)))
        if not queries:
            die("could not generate benchmark queries")

        raw_bytes = sum(len(doc.text.encode("utf-8")) for doc in docs)
        raw_index, raw_payload_bytes, raw_index_bytes, raw_build_sec = build_raw_bm25_store(docs, out_dir / "raw_bm25")

        raw_eval = evaluate_raw(raw_index, queries, top_k=args.top)
        spectrum_eval = evaluate_spectrum(spectrum_index, queries, top_k=args.top)

        if pack_path != target:
            spectrum_pack_path = out_dir / pack_path.name
            shutil.copy2(pack_path, spectrum_pack_path)
        else:
            spectrum_pack_path = pack_path

        pack_payload = 0
        pack_index = 0
        with zipfile.ZipFile(pack_path) as pack:
            for item in pack.infolist():
                if item.filename == PACK_INDEX_NAME:
                    pack_index += item.file_size
                elif item.filename.startswith("files/"):
                    pack_payload += item.file_size

        report = {
            "target": str(target),
            "files": len(docs),
            "queries": len(queries),
            "raw_bytes": raw_bytes,
            "raw": {
                "bytes": raw_payload_bytes + raw_index_bytes,
                "ratio_vs_raw": (raw_payload_bytes + raw_index_bytes) / raw_bytes if raw_bytes else 0,
                "payload_bytes": raw_payload_bytes,
                "index_bytes": raw_index_bytes,
                "build_sec": raw_build_sec,
                **raw_eval,
            },
            "spectrum": {
                "bytes": pack_path.stat().st_size,
                "ratio_vs_raw": pack_path.stat().st_size / raw_bytes if raw_bytes else 0,
                "payload_bytes": pack_payload,
                "index_bytes": pack_index,
                "build_sec": spectrum_build_sec,
                "verified": True,
                **spectrum_eval,
            },
        }
        (out_dir / "queries.json").write_text(json.dumps(queries, indent=2), encoding="utf-8")
        write_benchmark_report(report, out_dir)

    print(f"Benchmark written to {out_dir / 'report.md'}")
    print()
    print((out_dir / "report.md").read_text(encoding="utf-8"))
    return 0


def command_gui(args: argparse.Namespace) -> int:
    from gui.server import run

    run(host=args.host, port=args.port, open_browser=args.open)
    return 0


class SpecHelpFormatter(argparse.RawDescriptionHelpFormatter):
    pass


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="spec",
        formatter_class=SpecHelpFormatter,
        description="spec - semantic compression and searchable .spec storage",
        epilog="""Examples:
  spec encode ./docs -a
  spec encode ./docs -a --index
  spec encode app.py -o app.py.spec
  spec decode ./docs.specpack
  spec index ./docs.specpack
  spec search "oauth callback handler" ./docs.specpack
  spec benchmark ./docs.specpack
  spec search "oauth callback handler" ./docs.specdir
  spec info app.py.spec
  spec verify ./docs.specpack""",
    )
    parser.add_argument("--version", action="version", version=f"spec {VERSION}")
    sub = parser.add_subparsers(dest="command", metavar="<command>")

    encode = sub.add_parser("encode", help="Encode a file or folder to .spec", formatter_class=SpecHelpFormatter)
    encode.add_argument("input", help="File or folder to encode")
    encode.add_argument("-o", "--output", help="Output file, folder, or .specpack path")
    encode.add_argument("-a", "--archive", action="store_true", help="Write a single .specpack archive")
    encode.add_argument("--index", action="store_true", help="Build a search index after encoding; archives embed it")
    encode.add_argument("--all", action="store_true", help="Include every non-.spec file in folders")
    encode.add_argument("--lang", choices=sorted(LANG_MAP), help="Force language instead of extension detection")
    encode.add_argument("--no-rle", action="store_true", help="Disable RLE compression")
    encode.add_argument("--zlib-level", type=int, default=9, choices=range(1, 10), metavar="1-9", help="zlib compression level")
    encode.set_defaults(func=command_encode)

    decode = sub.add_parser("decode", help="Decode .spec or .specpack back to source")
    decode.add_argument("input", help=".spec file, .spec directory, or .specpack")
    decode.add_argument("-o", "--output", help="Output path")
    decode.set_defaults(func=command_decode)

    index = sub.add_parser("index", help="Build a search index")
    index.add_argument("input", help=".spec file, .spec folder, or .specpack")
    index.add_argument("-o", "--output", help="Output index path (default: embed in .specpack, sidecar otherwise)")
    index.set_defaults(func=command_index)

    search_parser = sub.add_parser("search", help="Search a Spectrum index")
    search_parser.add_argument("query", help="Query string")
    search_parser.add_argument("target", nargs="?", help=".spec, .spec folder, .specpack, or index file; packs auto-build embedded indexes")
    search_parser.add_argument("--index", help="Index path")
    search_parser.add_argument("--top", type=int, default=10, help="Number of results")
    search_parser.add_argument("--lang", default="txt", help="Query language: py/html/js/css/txt")
    search_parser.set_defaults(func=command_search)

    benchmark = sub.add_parser("benchmark", help="Compare Spectrum against raw text + BM25")
    benchmark.add_argument("input", help="Source folder, .spec file, or .specpack")
    benchmark.add_argument("-o", "--output", help="Output report directory (default: ./spec-benchmark)")
    benchmark.add_argument("--queries", type=int, default=80, help="Maximum generated queries")
    benchmark.add_argument("--top", type=int, default=5, help="Top-k for retrieval metrics")
    benchmark.add_argument("--all", action="store_true", help="Include every non-.spec file when benchmarking a folder")
    benchmark.add_argument("--clean", action="store_true", help="Delete the output directory before running")
    benchmark.set_defaults(func=command_benchmark)

    gui = sub.add_parser("gui", help="Run the local Spectrum search/benchmark GUI")
    gui.add_argument("--host", default="127.0.0.1", help="Host to bind")
    gui.add_argument("--port", type=int, default=8765, help="Port to bind")
    gui.add_argument("--open", action="store_true", help="Open the GUI in the default browser")
    gui.set_defaults(func=command_gui)

    info = sub.add_parser("info", help="Inspect a .spec file or .specpack")
    info.add_argument("input", help=".spec file or .specpack")
    info.set_defaults(func=command_info)

    verify = sub.add_parser("verify", help="Validate .spec checksum/fidelity")
    verify.add_argument("input", help=".spec file, .spec directory, or .specpack")
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
    except (SpecFormatError, zipfile.BadZipFile, KeyError, ValueError) as exc:
        die(str(exc))
    except KeyboardInterrupt:
        die("cancelled", 130)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
