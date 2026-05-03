#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from rag.storage_benchmark import load_binary_postings, write_binary_postings_v2


def convert(store: Path, output: Path | None = None) -> dict:
    docs_path = store / "docs.json"
    postings_path = store / "postings.bin"
    output_path = output or (store / "postings_v2.bin")
    if not docs_path.exists():
        raise FileNotFoundError(f"Missing docs metadata: {docs_path}")
    if not postings_path.exists():
        raise FileNotFoundError(f"Missing SPB1 postings: {postings_path}")

    docs_meta = json.loads(docs_path.read_text(encoding="utf-8"))
    documents = docs_meta["documents"]
    bm25 = load_binary_postings(postings_path, documents)
    write_binary_postings_v2(output_path, documents, bm25.postings, bm25.avdl)

    return {
        "store": str(store),
        "input": str(postings_path),
        "output": str(output_path),
        "input_bytes": postings_path.stat().st_size,
        "output_bytes": output_path.stat().st_size,
        "reduction_pct": round(
            (1 - output_path.stat().st_size / postings_path.stat().st_size) * 100,
            2,
        ),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Convert Spectrum SPB1 postings.bin to SPB2 postings_v2.bin.")
    parser.add_argument("--store", required=True, help="Spectrum store directory containing docs.json and postings.bin.")
    parser.add_argument("--output", help="Optional output path. Defaults to STORE/postings_v2.bin.")
    args = parser.parse_args()

    result = convert(Path(args.store), Path(args.output) if args.output else None)
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
