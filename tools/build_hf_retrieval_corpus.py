#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import pickle
import random
import time
import urllib.parse
import urllib.request
import urllib.error
import sys
from dataclasses import asdict
from pathlib import Path

import numpy as np
from scipy import sparse
from sklearn.decomposition import TruncatedSVD
from sklearn.preprocessing import normalize

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from rag.storage_benchmark import (
    Chunk,
    build_conventional_store,
    build_spectrum_store,
    dir_size,
    reset_dir,
)


DATASET = "WithinUsAI/GPT5.5_thinking_max_distill_god_seed_25K"
BASE_URL = "https://datasets-server.huggingface.co"


def api_json(endpoint: str, params: dict) -> dict:
    url = f"{BASE_URL}/{endpoint}?{urllib.parse.urlencode(params)}"
    request = urllib.request.Request(url, headers={"User-Agent": "spectrum-algo-test-corpus-builder/1.0"})
    for attempt in range(8):
        try:
            with urllib.request.urlopen(request, timeout=60) as response:
                return json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            if exc.code not in {429, 500, 502, 503, 504} or attempt == 7:
                raise
            retry_after = exc.headers.get("Retry-After")
            wait = int(retry_after) if retry_after and retry_after.isdigit() else min(90, 10 * (attempt + 1))
            wait += random.uniform(0, 2)
            print(f"[hf-corpus] HTTP {exc.code}; sleeping {wait:.1f}s")
            time.sleep(wait)
    raise RuntimeError("unreachable")


def row_to_text(row: dict) -> str:
    tags = row.get("tags") or []
    if isinstance(tags, list):
        tags_text = ", ".join(str(tag) for tag in tags)
    else:
        tags_text = str(tags)
    parts = [
        f"ID: {row.get('id', '')}",
        f"Category: {row.get('category', '')}",
        f"Difficulty: {row.get('difficulty', '')}",
        f"Tags: {tags_text}",
        "",
        "Instruction:",
        str(row.get("instruction") or ""),
        "",
        "Input:",
        str(row.get("input") or ""),
        "",
        "Output:",
        str(row.get("output") or ""),
    ]
    return "\n".join(parts).strip() + "\n"


def download_rows(dataset: str, limit: int | None, cache_dir: Path) -> list[dict]:
    rows: list[dict] = []
    offset = 0
    page_size = 100
    cache_dir.mkdir(parents=True, exist_ok=True)
    while True:
        remaining = None if limit is None else limit - len(rows)
        if remaining is not None and remaining <= 0:
            break
        length = page_size if remaining is None else min(page_size, remaining)
        cache_path = cache_dir / f"rows_{offset:06d}_{length:03d}.json"
        if cache_path.exists():
            data = json.loads(cache_path.read_text(encoding="utf-8"))
        else:
            data = api_json(
                "rows",
                {
                    "dataset": dataset,
                    "config": "default",
                    "split": "train",
                    "offset": offset,
                    "length": length,
                },
            )
            cache_path.write_text(json.dumps(data), encoding="utf-8")
        page = [item["row"] for item in data.get("rows", [])]
        if not page:
            break
        rows.extend(page)
        offset += len(page)
        total = data.get("num_rows_total")
        print(f"[hf-corpus] downloaded {len(rows):,}/{total or '?'} rows")
        if total is not None and offset >= int(total):
            break
    return rows


def write_raw_dataset(rows: list[dict], out_dir: Path) -> None:
    raw_dir = out_dir / "raw_dataset"
    reset_dir(raw_dir)
    (raw_dir / "rows.jsonl").write_text(
        "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows),
        encoding="utf-8",
    )
    docs_dir = raw_dir / "documents"
    docs_dir.mkdir()
    for idx, row in enumerate(rows):
        row_id = str(row.get("id") or f"row_{idx:05d}")
        (docs_dir / f"{idx:05d}_{row_id}.txt").write_text(row_to_text(row), encoding="utf-8")


def make_chunks(rows: list[dict]) -> list[Chunk]:
    chunks = []
    for idx, row in enumerate(rows):
        title = str(row.get("id") or f"row_{idx:05d}")
        category = str(row.get("category") or "uncategorized")
        chunks.append(
            Chunk(
                id=idx,
                title=f"{category}/{title}",
                text=row_to_text(row),
                page_index=idx,
                chunk_index=0,
            )
        )
    return chunks


def build_vector_store(conventional_dir: Path, out_dir: Path, dims: int) -> dict:
    reset_dir(out_dir)
    started = time.perf_counter()
    with (conventional_dir / "tfidf_vectorizer.pkl").open("rb") as handle:
        vectorizer = pickle.load(handle)
    matrix = sparse.load_npz(conventional_dir / "tfidf_matrix.npz")
    n_components = max(1, min(dims, matrix.shape[0] - 1, matrix.shape[1] - 1))
    svd = TruncatedSVD(n_components=n_components, random_state=7)
    vectors = normalize(svd.fit_transform(matrix)).astype("float32")
    np.save(out_dir / "vectors.npy", vectors)
    with (out_dir / "tfidf_vectorizer.pkl").open("wb") as handle:
        pickle.dump(vectorizer, handle)
    with (out_dir / "svd.pkl").open("wb") as handle:
        pickle.dump(svd, handle)
    meta = {
        "format": "spectrum-gui-local-vector-db-v1",
        "backend": f"LSA dense vectors ({n_components} dims)",
        "documents": int(vectors.shape[0]),
        "dimensions": int(vectors.shape[1]),
        "build_seconds": round(time.perf_counter() - started, 4),
    }
    (out_dir / "meta.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")
    return meta


def main() -> int:
    parser = argparse.ArgumentParser(description="Build a local retrieval corpus from a Hugging Face dataset")
    parser.add_argument("--dataset", default=DATASET)
    parser.add_argument("--out-dir", default="test data/gpt55_thinking_max_distill_god_seed_25k")
    parser.add_argument("--limit", type=int, default=0, help="Limit rows for smoke tests; 0 means all rows")
    parser.add_argument("--vector-dims", type=int, default=384)
    args = parser.parse_args()

    out_dir = Path(args.out_dir).expanduser().resolve()
    out_dir.mkdir(parents=True, exist_ok=True)

    rows = download_rows(args.dataset, None if args.limit == 0 else args.limit, out_dir / "download_cache")
    if not rows:
        raise SystemExit("No rows downloaded.")

    write_raw_dataset(rows, out_dir)
    chunks = make_chunks(rows)

    conventional_dir = out_dir / "conventional_tfidf"
    conventional_meta, vectorizer, _matrix = build_conventional_store(chunks, conventional_dir)
    with (conventional_dir / "tfidf_vectorizer.pkl").open("wb") as handle:
        pickle.dump(vectorizer, handle)

    spectrum_meta, _documents, _bm25 = build_spectrum_store(
        chunks,
        out_dir / "spectrum_spec",
        verify_fidelity=True,
        retrieval_normalization=True,
    )
    vector_meta = build_vector_store(conventional_dir, out_dir / "vector_db", args.vector_dims)

    manifest = {
        "format": "spectrum-gui-test-corpus-v1",
        "dataset": args.dataset,
        "rows": len(rows),
        "raw_dataset_bytes": dir_size(out_dir / "raw_dataset"),
        "conventional_tfidf_bytes": dir_size(conventional_dir),
        "spectrum_spec_bytes": dir_size(out_dir / "spectrum_spec"),
        "vector_db_bytes": dir_size(out_dir / "vector_db"),
        "conventional_tfidf": conventional_meta,
        "spectrum_spec": spectrum_meta,
        "vector_db": vector_meta,
    }
    (out_dir / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(json.dumps(manifest, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
