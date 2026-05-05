"""
Spectrum BM25 parameter sweep for existing storage benchmark outputs.

The sweep is profile-labelled on purpose: results should become retrieval
settings for a corpus profile, not global .spec codec defaults.
"""

from __future__ import annotations

import argparse
import itertools
import json
import sys
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from statistics import mean

_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_ROOT))

from rag.ranking_eval import (  # noqa: E402
    conventional_rank,
    load_conventional,
    load_queries,
    load_spectrum,
    percentile,
    resolve_labelled_queries,
    title_token_sets,
)
from rag.query import encode_query  # noqa: E402
from rag.storage_benchmark import BinarySpectrumBM25  # noqa: E402


@dataclass(frozen=True)
class SweepVariant:
    k1: float
    b: float
    max_df_ratio: float | None
    title_boost: float
    unique_query_terms: bool

    @property
    def name(self) -> str:
        df = "none" if self.max_df_ratio is None else f"{self.max_df_ratio:g}"
        unique = "uniq" if self.unique_query_terms else "tf"
        return (
            f"k1={self.k1:g},b={self.b:g},df={df},"
            f"title={self.title_boost:g},{unique}"
        )


def parse_float_list(value: str, allow_none: bool = False) -> list[float | None]:
    items: list[float | None] = []
    for raw in value.split(","):
        item = raw.strip()
        if not item:
            continue
        if allow_none and item.lower() in {"none", "null", "off"}:
            items.append(None)
        else:
            items.append(float(item))
    if not items:
        raise ValueError(f"Empty sweep list: {value!r}")
    return items


def parse_bool_list(value: str) -> list[bool]:
    mapping = {
        "0": False,
        "false": False,
        "no": False,
        "off": False,
        "1": True,
        "true": True,
        "yes": True,
        "on": True,
    }
    items = []
    for raw in value.split(","):
        item = raw.strip().lower()
        if not item:
            continue
        if item not in mapping:
            raise ValueError(f"Invalid bool sweep value: {raw!r}")
        items.append(mapping[item])
    if not items:
        raise ValueError(f"Empty bool sweep list: {value!r}")
    return items


def evaluate_ids(queries: list[dict], ranker, top_k: int) -> dict:
    hit1 = 0
    recallk = 0
    reciprocal_ranks = []
    latencies = []

    for item in queries:
        relevant = set(item["relevant_ids"])
        started = time.perf_counter()
        ids = ranker(item["query"])
        latencies.append((time.perf_counter() - started) * 1000)

        if ids and ids[0] in relevant:
            hit1 += 1
        if relevant.intersection(ids):
            recallk += 1
        rank = next((i + 1 for i, doc_id in enumerate(ids) if doc_id in relevant), None)
        reciprocal_ranks.append(1 / rank if rank else 0.0)

    total = max(1, len(queries))
    return {
        "hit_at_1": round(hit1 / total, 4),
        f"recall_at_{top_k}": round(recallk / total, 4),
        "mrr": round(mean(reciprocal_ranks) if reciprocal_ranks else 0.0, 4),
        "avg_query_ms": round(mean(latencies) if latencies else 0.0, 4),
        "p95_query_ms": round(percentile(latencies, 95), 4),
    }


def sort_key(row: dict, top_k: int) -> tuple:
    metrics = row["metrics"]
    return (
        metrics["hit_at_1"],
        metrics["mrr"],
        metrics[f"recall_at_{top_k}"],
        -metrics["avg_query_ms"],
        -metrics["p95_query_ms"],
    )


def format_value(value: float | None | bool) -> str:
    if value is None:
        return "none"
    if isinstance(value, bool):
        return "yes" if value else "no"
    return f"{value:g}"


def write_markdown(path: Path, report: dict) -> None:
    top_k = report["settings"]["top_k"]
    top_n = report["settings"]["top_n"]
    conv = report["baseline"]["conventional_tfidf"]
    lines = [
        "# Spectrum BM25 Parameter Sweep",
        "",
        f"- Profile: `{report['settings']['profile']}`",
        f"- Benchmark dir: `{report['settings']['benchmark_dir']}`",
        f"- Queries: {report['settings']['queries']:,}",
        f"- Variants: {report['settings']['variants']:,}",
        f"- Top-k: {top_k}",
        "",
        "## Conventional Baseline",
        "",
        "| Hit@1 | MRR | Recall@k | Avg ms | P95 ms |",
        "|---:|---:|---:|---:|---:|",
        (
            f"| {conv['hit_at_1']:.3f} | {conv['mrr']:.3f} | "
            f"{conv[f'recall_at_{top_k}']:.3f} | {conv['avg_query_ms']:.3f} | "
            f"{conv['p95_query_ms']:.3f} |"
        ),
        "",
        f"## Top {top_n} Spectrum Variants",
        "",
        "| Rank | k1 | b | DF max | Title boost | Unique terms | Hit@1 | MRR | Recall@k | Avg ms | P95 ms |",
        "|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]

    for idx, row in enumerate(report["top_variants"], start=1):
        variant = row["variant"]
        metrics = row["metrics"]
        lines.append(
            f"| {idx} | {format_value(variant['k1'])} | {format_value(variant['b'])} | "
            f"{format_value(variant['max_df_ratio'])} | {format_value(variant['title_boost'])} | "
            f"{format_value(variant['unique_query_terms'])} | {metrics['hit_at_1']:.3f} | "
            f"{metrics['mrr']:.3f} | {metrics[f'recall_at_{top_k}']:.3f} | "
            f"{metrics['avg_query_ms']:.3f} | {metrics['p95_query_ms']:.3f} |"
        )

    best = report["top_variants"][0] if report["top_variants"] else None
    if best:
        lines.extend([
            "",
            "## Best Variant",
            "",
            f"- Name: `{best['name']}`",
            f"- Quality gap vs conventional Hit@1: {best['gaps']['hit_at_1']:+.4f}",
            f"- Quality gap vs conventional MRR: {best['gaps']['mrr']:+.4f}",
            f"- Query latency delta vs conventional avg ms: {best['gaps']['avg_query_ms']:+.4f}",
            "",
            "Treat this as a profile result, not a global `.spec` default.",
        ])

    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def run(args: argparse.Namespace) -> dict:
    benchmark_dir = Path(args.benchmark_dir)
    spectrum_dir = benchmark_dir / "spectrum_spec"
    documents, loaded_bm25 = load_spectrum(spectrum_dir)
    queries = resolve_labelled_queries(
        load_queries(Path(args.queries) if args.queries else benchmark_dir / "queries.json"),
        documents,
    )
    title_ids = title_token_sets(documents, args.retrieval_normalization)
    _, vectorizer, matrix = load_conventional(benchmark_dir)

    top_k = args.top_k
    conventional = evaluate_ids(
        queries,
        lambda query: [doc_id for doc_id, _score in conventional_rank(vectorizer, matrix, query, top_k)],
        top_k,
    )

    k1_values = parse_float_list(args.k1)
    b_values = parse_float_list(args.b)
    df_values = parse_float_list(args.max_df_ratio, allow_none=True)
    title_boost_values = parse_float_list(args.title_boost)
    unique_values = parse_bool_list(args.unique_query_terms)

    variants = [
        SweepVariant(
            k1=float(k1),
            b=float(b),
            max_df_ratio=None if df is None else float(df),
            title_boost=float(title_boost),
            unique_query_terms=unique,
        )
        for k1, b, df, title_boost, unique in itertools.product(
            k1_values,
            b_values,
            df_values,
            title_boost_values,
            unique_values,
        )
    ]

    rows = []
    started = time.perf_counter()
    for idx, variant in enumerate(variants, start=1):
        bm25 = BinarySpectrumBM25(
            documents,
            loaded_bm25.postings,
            loaded_bm25.avdl,
            k1=variant.k1,
            b=variant.b,
        )

        def ranker(query: str, bm25=bm25, variant=variant) -> list[int]:
            query_ids = encode_query(query, lang="txt", normalize=args.retrieval_normalization)
            return bm25.search(
                query_ids,
                top_k,
                max_df_ratio=variant.max_df_ratio,
                unique_query_terms=variant.unique_query_terms,
                title_ids=title_ids,
                title_boost=variant.title_boost,
            )

        metrics = evaluate_ids(queries, ranker, top_k)
        rows.append({
            "name": variant.name,
            "variant": asdict(variant),
            "metrics": metrics,
            "gaps": {
                "hit_at_1": round(metrics["hit_at_1"] - conventional["hit_at_1"], 4),
                "mrr": round(metrics["mrr"] - conventional["mrr"], 4),
                f"recall_at_{top_k}": round(
                    metrics[f"recall_at_{top_k}"] - conventional[f"recall_at_{top_k}"],
                    4,
                ),
                "avg_query_ms": round(metrics["avg_query_ms"] - conventional["avg_query_ms"], 4),
            },
        })
        if args.progress and (idx == 1 or idx % args.progress == 0 or idx == len(variants)):
            print(f"[parameter-sweep] {idx:,}/{len(variants):,} variants")

    rows.sort(key=lambda row: sort_key(row, top_k), reverse=True)
    top_rows = rows[: args.top_n]

    report = {
        "format": "spectrum-bm25-parameter-sweep-v1",
        "settings": {
            "profile": args.profile,
            "benchmark_dir": str(benchmark_dir),
            "queries": len(queries),
            "top_k": top_k,
            "variants": len(variants),
            "top_n": args.top_n,
            "elapsed_seconds": round(time.perf_counter() - started, 4),
            "sweep": {
                "k1": k1_values,
                "b": b_values,
                "max_df_ratio": df_values,
                "title_boost": title_boost_values,
                "unique_query_terms": unique_values,
            },
            "retrieval_normalization": args.retrieval_normalization,
            "note": "Sweep results are corpus-profile retrieval settings, not .spec codec defaults.",
        },
        "baseline": {
            "conventional_tfidf": conventional,
        },
        "top_variants": top_rows,
        "all_variants": rows if args.include_all else [],
    }

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "parameter_sweep.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    write_markdown(out_dir / "parameter_sweep.md", report)
    print(f"[parameter-sweep] wrote {out_dir / 'parameter_sweep.md'}")
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description="Sweep Spectrum BM25 ranking parameters.")
    parser.add_argument("--benchmark-dir", default="benchmarks/generated/storage_benchmark_6k_full_current")
    parser.add_argument("--queries", default="", help="Optional query JSON path. Defaults to benchmark-dir/queries.json.")
    parser.add_argument("--out-dir", default="benchmarks/generated/parameter_sweep")
    parser.add_argument("--profile", default="wiki-full-xml")
    parser.add_argument("--top-k", type=int, default=5)
    parser.add_argument("--top-n", type=int, default=25)
    parser.add_argument("--k1", default="0.9,1.2,1.5,1.8,2.1")
    parser.add_argument("--b", default="0,0.25,0.5,0.75,1.0")
    parser.add_argument("--max-df-ratio", default="none,0.5,0.75,0.9")
    parser.add_argument("--title-boost", default="0,0.25,0.5,1.0")
    parser.add_argument("--unique-query-terms", default="false,true")
    parser.add_argument(
        "--retrieval-normalization",
        action="store_true",
        help="Normalize query text to match stores built with --retrieval-normalization.",
    )
    parser.add_argument("--include-all", action="store_true", help="Write every variant to JSON, not only the top rows.")
    parser.add_argument("--progress", type=int, default=100, help="Print progress every N variants; 0 disables progress.")
    args = parser.parse_args()
    run(args)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
