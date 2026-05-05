#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import math
import sys
import time
from pathlib import Path
from statistics import mean

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from rag.query import encode_query
from rag.storage_benchmark import (
    load_binary_postings,
    write_binary_postings_v2,
)


DEFAULT_QUERIES = [
    "primary signal",
    "Resistant to",
    "The framework must be",
    "double effective context length",
    "reward hacking Goodhart",
    "agentbench reasoning depth",
]


def percentile(values: list[float], pct: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    idx = min(len(ordered) - 1, math.ceil((pct / 100) * len(ordered)) - 1)
    return ordered[idx]


def load_timed(path: Path, documents: list[dict]):
    started = time.perf_counter()
    bm25 = load_binary_postings(path, documents)
    return bm25, (time.perf_counter() - started) * 1000


def run_queries(bm25, query_ids_by_text: list[tuple[str, list[int]]], top_k: int, repeats: int) -> tuple[dict[str, list[int]], dict[str, list[float]], list[float]]:
    rankings: dict[str, list[int]] = {}
    scores: dict[str, list[float]] = {}
    latencies: list[float] = []
    for _ in range(repeats):
        for query, query_ids in query_ids_by_text:
            started = time.perf_counter()
            doc_ids = bm25.search(query_ids, top_k=top_k)
            latencies.append((time.perf_counter() - started) * 1000)
            rankings[query] = doc_ids
            scores[query] = [bm25.score(doc_id, query_ids) for doc_id in doc_ids]
    return rankings, scores, latencies


def benchmark(store: Path, queries: list[str], top_k: int, repeats: int, convert_missing: bool) -> dict:
    docs_meta = json.loads((store / "docs.json").read_text(encoding="utf-8"))
    documents = docs_meta["documents"]
    v1_path = store / "postings.bin"
    v2_path = store / "postings_v2.bin"
    if not v1_path.exists():
        raise FileNotFoundError(f"Missing SPB1 postings: {v1_path}")

    v1_bm25, v1_load_ms = load_timed(v1_path, documents)
    if not v2_path.exists():
        if not convert_missing:
            raise FileNotFoundError(f"Missing SPB2 postings: {v2_path}")
        write_binary_postings_v2(v2_path, documents, v1_bm25.postings, v1_bm25.avdl)
    v2_bm25, v2_load_ms = load_timed(v2_path, documents)

    store_meta_path = store / "meta.json"
    store_meta = json.loads(store_meta_path.read_text(encoding="utf-8")) if store_meta_path.exists() else {}
    retrieval_normalization = bool(store_meta.get("retrieval_normalization", True))
    query_ids_by_text = [
        (query, encode_query(query, lang="txt", normalize=retrieval_normalization))
        for query in queries
    ]

    v1_rankings, v1_scores, v1_latencies = run_queries(v1_bm25, query_ids_by_text, top_k, repeats)
    v2_rankings, v2_scores, v2_latencies = run_queries(v2_bm25, query_ids_by_text, top_k, repeats)

    comparisons = []
    all_rankings_equal = True
    max_score_abs_diff = 0.0
    for query in queries:
        rankings_equal = v1_rankings[query] == v2_rankings[query]
        all_rankings_equal = all_rankings_equal and rankings_equal
        score_diffs = [
            abs(a - b)
            for a, b in zip(v1_scores[query], v2_scores[query])
        ]
        query_max_diff = max(score_diffs) if score_diffs else 0.0
        max_score_abs_diff = max(max_score_abs_diff, query_max_diff)
        comparisons.append({
            "query": query,
            "v1_top_ids": v1_rankings[query],
            "v2_top_ids": v2_rankings[query],
            "top_k_equal": rankings_equal,
            "max_score_abs_diff": query_max_diff,
        })

    v1_bytes = v1_path.stat().st_size
    v2_bytes = v2_path.stat().st_size
    return {
        "store": str(store),
        "documents": len(documents),
        "queries": queries,
        "top_k": top_k,
        "repeats": repeats,
        "retrieval_normalization": retrieval_normalization,
        "sizes": {
            "spb1_bytes": v1_bytes,
            "spb2_bytes": v2_bytes,
            "reduction_pct": round((1 - v2_bytes / v1_bytes) * 100, 2) if v1_bytes else 0.0,
        },
        "load_ms": {
            "spb1": round(v1_load_ms, 4),
            "spb2": round(v2_load_ms, 4),
        },
        "query_latency_ms": {
            "spb1_avg": round(mean(v1_latencies), 4) if v1_latencies else 0.0,
            "spb1_p95": round(percentile(v1_latencies, 95), 4),
            "spb2_avg": round(mean(v2_latencies), 4) if v2_latencies else 0.0,
            "spb2_p95": round(percentile(v2_latencies, 95), 4),
        },
        "quality": {
            "all_top_k_equal": all_rankings_equal,
            "max_score_abs_diff": max_score_abs_diff,
            "comparisons": comparisons,
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Compare Spectrum SPB1 and SPB2 postings files.")
    parser.add_argument("--store", required=True, help="Spectrum store directory containing docs.json and postings.bin.")
    parser.add_argument("--queries", nargs="*", default=DEFAULT_QUERIES, help="Queries to compare.")
    parser.add_argument("--top-k", type=int, default=5, help="Number of results to compare.")
    parser.add_argument("--repeats", type=int, default=5, help="Repeated query timing passes.")
    parser.add_argument(
        "--no-convert-missing",
        action="store_true",
        help="Fail instead of creating postings_v2.bin when it is missing.",
    )
    parser.add_argument("--json-output", help="Optional path to write the full JSON report.")
    args = parser.parse_args()

    report = benchmark(
        Path(args.store),
        args.queries,
        args.top_k,
        args.repeats,
        convert_missing=not args.no_convert_missing,
    )
    if args.json_output:
        Path(args.json_output).write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
