"""
Ranking evaluation harness for existing RAG storage benchmark outputs.

This compares Spectrum ranking variants against the same fixed query set and
emits diagnostics for failed/weak queries. It deliberately avoids query
expansion so the measured signal stays close to Spectrum's own token stream.
"""

from __future__ import annotations

import argparse
import json
import math
import re
import sys
import time
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from statistics import mean

_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_ROOT))

import dictionary as D
from rag.query import encode_query
from rag.storage_benchmark import BinarySpectrumBM25, load_binary_postings, preferred_binary_postings_path
from spec_format.spec_encoder import tokens_to_ids
from tokenizers.text_tokenizer import tokenize_text

try:
    import numpy as np
    from sklearn.feature_extraction.text import TfidfVectorizer
except Exception as exc:  # pragma: no cover - runtime dependency check
    raise SystemExit(
        "This harness requires numpy and scikit-learn. "
        f"Import failed: {exc}"
    )


@dataclass(frozen=True)
class Variant:
    name: str
    unique_query_terms: bool = False
    max_df_ratio: float | None = None
    title_boost: float = 0.0
    k1: float = 1.5
    b: float = 0.75


WORD_RE = re.compile(r"[A-Za-z][A-Za-z0-9']+")

VARIANTS = [
    Variant("spectrum_bm25"),
    Variant("spectrum_bm25_unique_query", unique_query_terms=True),
    Variant("spectrum_bm25_df90", max_df_ratio=0.90),
    Variant("spectrum_bm25_df75", max_df_ratio=0.75),
    Variant("spectrum_bm25_df50", max_df_ratio=0.50),
    Variant("spectrum_bm25_title_boost_1", title_boost=1.0),
    Variant("spectrum_bm25_title_boost_2", title_boost=2.0),
    Variant("spectrum_bm25_b025_title_boost_025", b=0.25, title_boost=0.25),
    Variant("spectrum_bm25_b1_df90", b=1.0, max_df_ratio=0.90),
]


def read_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def percentile(values: list[float], pct: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    idx = min(len(ordered) - 1, math.ceil((pct / 100) * len(ordered)) - 1)
    return ordered[idx]


def load_queries(path: Path) -> list[dict]:
    data = read_json(path)
    if not isinstance(data, list):
        raise ValueError(f"Expected a query list: {path}")
    return data


def resolve_labelled_queries(queries: list[dict], documents: list[dict]) -> list[dict]:
    title_to_ids: dict[str, list[int]] = {}
    for doc in documents:
        title_to_ids.setdefault(doc.get("title", ""), []).append(int(doc["id"]))

    resolved = []
    missing = []
    for item in queries:
        row = dict(item)
        if "relevant_ids" not in row:
            title = row.get("title", "")
            ids = title_to_ids.get(title, [])
            if not ids:
                missing.append(title)
            row["relevant_ids"] = ids
        resolved.append(row)
    if missing:
        unique = ", ".join(sorted(set(missing))[:10])
        raise ValueError(f"Labelled query titles not found in benchmark docs: {unique}")
    return resolved


def load_spectrum(store_dir: Path) -> tuple[list[dict], BinarySpectrumBM25]:
    docs_meta = read_json(store_dir / "docs.json")
    documents = docs_meta["documents"]
    bm25 = load_binary_postings(preferred_binary_postings_path(store_dir), documents)
    return documents, bm25


def load_conventional(benchmark_dir: Path):
    records_path = benchmark_dir / "conventional_tfidf" / "chunks.jsonl"
    chunks = []
    with records_path.open(encoding="utf-8") as f:
        for line in f:
            if line.strip():
                chunks.append(json.loads(line))
    vectorizer = TfidfVectorizer(
        lowercase=True,
        stop_words="english",
        max_features=100_000,
        norm="l2",
    )
    matrix = vectorizer.fit_transform([chunk["text"] for chunk in chunks])
    return chunks, vectorizer, matrix


class RawTextBM25:
    def __init__(self, chunks: list[dict], k1: float = 1.5, b: float = 0.75):
        self.chunks = chunks
        self.k1 = k1
        self.b = b
        self.freq = [Counter(self.tokenize(chunk.get("text", ""))) for chunk in chunks]
        self.lengths = [sum(freq.values()) for freq in self.freq]
        self.N = len(chunks)
        self.avdl = sum(self.lengths) / self.N if self.N else 0.0
        self.inverted: dict[str, list[tuple[int, int]]] = {}
        for doc_id, freq in enumerate(self.freq):
            for token, count in freq.items():
                self.inverted.setdefault(token, []).append((doc_id, count))

    @staticmethod
    def tokenize(text: str) -> list[str]:
        return [match.group(0).lower() for match in WORD_RE.finditer(text)]

    def idf(self, token: str) -> float:
        df = len(self.inverted.get(token, ()))
        return math.log((self.N - df + 0.5) / (df + 0.5) + 1)


def raw_bm25_rank(raw_bm25: RawTextBM25, query: str, top_k: int) -> list[tuple[int, float]]:
    query_tokens = raw_bm25.tokenize(query)
    if not query_tokens:
        return []

    scores: dict[int, float] = {}
    query_counts = Counter(query_tokens)
    for token, query_count in query_counts.items():
        rows = raw_bm25.inverted.get(token)
        if not rows:
            continue
        idf = raw_bm25.idf(token)
        for doc_id, tf in rows:
            dl = raw_bm25.lengths[doc_id]
            norm = 1 - raw_bm25.b + raw_bm25.b * (dl / raw_bm25.avdl) if raw_bm25.avdl else 1.0
            score = idf * (tf * (raw_bm25.k1 + 1)) / (tf + raw_bm25.k1 * norm)
            scores[doc_id] = scores.get(doc_id, 0.0) + score * query_count

    ranked = sorted(scores.items(), key=lambda item: item[1], reverse=True)
    return [(doc_id, score) for doc_id, score in ranked[:top_k] if score > 0]


class SpectrumOnlySimilarity:
    """
    Direct .spec token-vector similarity with BM25 intentionally removed.

    Documents and queries are binary vectors over Spectrum dictionary token IDs.
    The score is binary cosine: overlap / sqrt(|query_terms| * |doc_terms|).
    This avoids IDF, BM25 length normalization, and term-frequency weighting.
    """

    def __init__(self, bm25: BinarySpectrumBM25):
        self.postings = bm25.postings
        self.doc_unique_counts = [0 for _ in bm25.docs]
        for rows in self.postings.values():
            for doc_id, _tf in rows:
                self.doc_unique_counts[doc_id] += 1

    def rank(self, query_ids: list[int], top_k: int) -> list[tuple[int, float]]:
        query_terms = set(query_ids)
        if not query_terms:
            return []

        overlaps: dict[int, int] = {}
        for token_id in query_terms:
            for doc_id, _tf in self.postings.get(token_id, ()):
                overlaps[doc_id] = overlaps.get(doc_id, 0) + 1

        q_norm = math.sqrt(len(query_terms))
        scores = []
        for doc_id, overlap in overlaps.items():
            doc_norm = math.sqrt(self.doc_unique_counts[doc_id])
            if doc_norm:
                scores.append((doc_id, overlap / (q_norm * doc_norm)))
        scores.sort(key=lambda item: item[1], reverse=True)
        return [(doc_id, score) for doc_id, score in scores[:top_k] if score > 0]


def conventional_rank(vectorizer, matrix, query: str, top_k: int) -> list[tuple[int, float]]:
    q = vectorizer.transform([query])
    scores = (matrix @ q.T).toarray().ravel()
    if not np.any(scores):
        return []
    order = np.argsort(-scores)[:top_k]
    return [(int(idx), float(scores[idx])) for idx in order if scores[idx] > 0]


def spectrum_only_rank(
    similarity: SpectrumOnlySimilarity,
    query: str,
    top_k: int,
    retrieval_normalization: bool = False,
) -> tuple[list[tuple[int, float]], list[int]]:
    query_ids = encode_query(query, lang="txt", normalize=retrieval_normalization)
    return similarity.rank(query_ids, top_k), query_ids


def token_name(token_id: int) -> str:
    return D.SPEC_ID_TO_TOKEN.get(token_id, f"<{token_id}>")


def title_token_sets(
    documents: list[dict],
    retrieval_normalization: bool = False,
) -> list[set[int]]:
    return [
        set(encode_query(doc.get("title", ""), lang="txt", normalize=retrieval_normalization))
        for doc in documents
    ]


def spectrum_rank(
    bm25: BinarySpectrumBM25,
    documents: list[dict],
    title_ids: list[set[int]],
    query: str,
    variant: Variant,
    top_k: int,
    retrieval_normalization: bool = False,
) -> tuple[list[tuple[int, float]], list[int]]:
    query_ids = encode_query(query, lang="txt", normalize=retrieval_normalization)
    if variant.unique_query_terms:
        query_ids = list(dict.fromkeys(query_ids))
    if variant.max_df_ratio is not None and bm25.N:
        query_ids = [
            tid for tid in query_ids
            if len(bm25.postings.get(tid, ())) / bm25.N <= variant.max_df_ratio
        ]
    if not query_ids:
        return [], []

    query_counts = Counter(query_ids)
    scores: dict[int, float] = {}
    for token_id, query_count in query_counts.items():
        rows = bm25.postings.get(token_id)
        if not rows:
            continue
        idf = bm25.idf(token_id)
        for doc_id, tf in rows:
            dl = bm25._lengths[doc_id]
            norm = 1 - variant.b + variant.b * (dl / bm25.avdl) if bm25.avdl > 0 else 1.0
            score = idf * (tf * (variant.k1 + 1)) / (tf + variant.k1 * norm)
            scores[doc_id] = scores.get(doc_id, 0.0) + score * query_count

    if variant.title_boost:
        qset = set(query_ids)
        for doc_id, doc_title_ids in enumerate(title_ids):
            matched = qset.intersection(doc_title_ids)
            if matched:
                scores[doc_id] = scores.get(doc_id, 0.0) + variant.title_boost * len(matched)

    ranked = sorted(scores.items(), key=lambda item: item[1], reverse=True)
    return [(doc_id, score) for doc_id, score in ranked[:top_k] if score > 0], query_ids


def query_diagnostics(query: str, bm25: BinarySpectrumBM25, query_ids: list[int]) -> dict:
    tokens = tokenize_text(query)
    all_ids = tokens_to_ids(tokens)
    dict_ids = [tid for tid in all_ids if tid < D.SPEC_ID_ASCII_BASE]
    fallback_count = len(all_ids) - len(dict_ids)
    seen = []
    for tid in dict.fromkeys(query_ids):
        df = len(bm25.postings.get(tid, ()))
        seen.append({
            "id": tid,
            "token": token_name(tid),
            "query_tf": query_ids.count(tid),
            "df": df,
            "df_ratio": round(df / bm25.N, 4) if bm25.N else 0.0,
            "idf": round(bm25.idf(tid), 4),
        })
    noisy = [item for item in seen if item["df_ratio"] >= 0.75]
    return {
        "tokens": tokens,
        "dict_token_count": len(dict_ids),
        "fallback_count": fallback_count,
        "query_tokens": seen,
        "noisy_tokens": noisy,
    }


def evaluate_ranked(
    queries: list[dict],
    ranker,
    top_k: int,
) -> tuple[dict, list[dict]]:
    hit1 = 0
    recallk = 0
    reciprocal_ranks = []
    latencies = []
    details = []

    for item in queries:
        relevant = set(item["relevant_ids"])
        started = time.perf_counter()
        ranked, extra = ranker(item["query"])
        latencies.append((time.perf_counter() - started) * 1000)
        ids = [doc_id for doc_id, _score in ranked]
        if ids and ids[0] in relevant:
            hit1 += 1
        if relevant.intersection(ids):
            recallk += 1
        rank = next((i + 1 for i, doc_id in enumerate(ids) if doc_id in relevant), None)
        reciprocal_ranks.append(1 / rank if rank else 0.0)
        details.append({
            "query": item["query"],
            "title": item.get("title", ""),
            "relevant_ids": sorted(relevant),
            "rank": rank,
            "top": [{"doc_id": doc_id, "score": round(score, 4)} for doc_id, score in ranked],
            "extra": extra,
        })

    total = max(1, len(queries))
    return {
        "hit_at_1": round(hit1 / total, 4),
        f"recall_at_{top_k}": round(recallk / total, 4),
        "mrr": round(mean(reciprocal_ranks) if reciprocal_ranks else 0.0, 4),
        "avg_query_ms": round(mean(latencies) if latencies else 0.0, 4),
        "p95_query_ms": round(percentile(latencies, 95), 4),
    }, details


def write_markdown(path: Path, report: dict) -> None:
    top_k = report["settings"]["top_k"]
    lines = [
        "# Spectrum Ranking Evaluation",
        "",
        f"- Benchmark dir: `{report['settings']['benchmark_dir']}`",
        f"- Queries: {report['settings']['queries']:,}",
        f"- Top-k: {top_k}",
        "",
        "## Summary",
        "",
        "| Variant | Hit@1 | MRR | Recall@k | Avg ms | P95 ms |",
        "|---|---:|---:|---:|---:|---:|",
    ]
    for name, row in report["summary"].items():
        lines.append(
            f"| {name} | {row['hit_at_1']:.3f} | {row['mrr']:.3f} | "
            f"{row[f'recall_at_{top_k}']:.3f} | {row['avg_query_ms']:.3f} | "
            f"{row['p95_query_ms']:.3f} |"
        )

    ranking_changes = report["diagnostics"].get("spectrum_only_ranking_changes", [])
    lines.extend(["", "## Spectrum-Only Ranking Changes", ""])
    if not ranking_changes:
        lines.append("Spectrum-only returned the same top result as Spectrum BM25 for every query.")
    else:
        lines.extend([
            "| Query | Relevant | Spectrum BM25 top | Spectrum-only top |",
            "|---|---|---:|---:|",
        ])
        for item in ranking_changes:
            lines.append(
                f"| `{item['query']}` | {item['relevant_ids']} | "
                f"{item['spectrum_bm25_top']} | {item['spectrum_only_top']} |"
            )

    lines.extend(["", "## Diagnostics", ""])
    failures = report["diagnostics"]["failed_or_weak_queries"]
    if not failures:
        lines.append("No failed or weak Spectrum baseline queries.")
    for item in failures:
        lines.extend([
            f"### {item['title'] or item['query'][:60]}",
            "",
            f"- Query: `{item['query']}`",
            f"- Baseline rank: {item['baseline_rank']}",
            f"- Relevant ids: {item['relevant_ids']}",
            f"- Top docs: {item['top_doc_ids']}",
            f"- Fallback tokens dropped: {item['diagnostics']['fallback_count']}",
            "",
            "| Token | ID | TF | DF ratio | IDF |",
            "|---|---:|---:|---:|---:|",
        ])
        for token in item["diagnostics"]["query_tokens"]:
            lines.append(
                f"| `{token['token']}` | {token['id']} | {token['query_tf']} | "
                f"{token['df_ratio']:.3f} | {token['idf']:.3f} |"
            )
        lines.append("")

    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def run(args: argparse.Namespace) -> dict:
    benchmark_dir = Path(args.benchmark_dir)
    spectrum_dir = benchmark_dir / "spectrum_spec"
    documents, bm25 = load_spectrum(spectrum_dir)
    queries = resolve_labelled_queries(
        load_queries(Path(args.queries) if args.queries else benchmark_dir / "queries.json"),
        documents,
    )
    title_ids = title_token_sets(documents, args.retrieval_normalization)
    raw_chunks, vectorizer, matrix = load_conventional(benchmark_dir)
    raw_bm25 = RawTextBM25(raw_chunks)
    spectrum_only = SpectrumOnlySimilarity(bm25)

    summary = {}
    details = {}

    raw_bm25_summary, raw_bm25_details = evaluate_ranked(
        queries,
        lambda query: (raw_bm25_rank(raw_bm25, query, args.top_k), {}),
        args.top_k,
    )
    summary["raw_text_bm25"] = raw_bm25_summary
    details["raw_text_bm25"] = raw_bm25_details

    conv_summary, conv_details = evaluate_ranked(
        queries,
        lambda query: (conventional_rank(vectorizer, matrix, query, args.top_k), {}),
        args.top_k,
    )
    summary["conventional_tfidf"] = conv_summary
    details["conventional_tfidf"] = conv_details

    baseline_details = []
    for variant in VARIANTS:
        variant_summary, variant_details = evaluate_ranked(
            queries,
            lambda query, variant=variant: spectrum_rank(
                bm25, documents, title_ids, query, variant, args.top_k, args.retrieval_normalization
            ),
            args.top_k,
        )
        summary[variant.name] = variant_summary
        details[variant.name] = variant_details
        if variant.name == "spectrum_bm25":
            baseline_details = variant_details

    spectrum_only_summary, spectrum_only_details = evaluate_ranked(
        queries,
        lambda query: spectrum_only_rank(
            spectrum_only, query, args.top_k, args.retrieval_normalization
        ),
        args.top_k,
    )
    summary["spectrum_only_binary_cosine"] = spectrum_only_summary
    details["spectrum_only_binary_cosine"] = spectrum_only_details

    failed_or_weak = []
    for item in baseline_details:
        rank = item["rank"]
        if rank == 1:
            continue
        query_ids = item["extra"]
        failed_or_weak.append({
            "query": item["query"],
            "title": item["title"],
            "baseline_rank": rank,
            "relevant_ids": item["relevant_ids"],
            "top_doc_ids": [row["doc_id"] for row in item["top"]],
            "diagnostics": query_diagnostics(item["query"], bm25, query_ids),
        })

    spectrum_only_changes = []
    for bm25_item, only_item in zip(baseline_details, spectrum_only_details, strict=True):
        bm25_top = bm25_item["top"][0]["doc_id"] if bm25_item["top"] else None
        only_top = only_item["top"][0]["doc_id"] if only_item["top"] else None
        if bm25_top != only_top:
            spectrum_only_changes.append({
                "query": bm25_item["query"],
                "title": bm25_item["title"],
                "relevant_ids": bm25_item["relevant_ids"],
                "spectrum_bm25_top": bm25_top,
                "spectrum_only_top": only_top,
                "spectrum_bm25_rank": bm25_item["rank"],
                "spectrum_only_rank": only_item["rank"],
            })

    report = {
        "format": "spectrum-ranking-eval-v2",
        "settings": {
            "benchmark_dir": str(benchmark_dir),
            "queries": len(queries),
            "top_k": args.top_k,
            "note": "No query expansion is used by any Spectrum variant. spectrum_only_binary_cosine removes BM25/IDF/term-frequency weighting.",
            "retrieval_normalization": args.retrieval_normalization,
        },
        "summary": summary,
        "diagnostics": {
            "failed_or_weak_queries": failed_or_weak[: args.max_diagnostics],
            "failed_or_weak_count": len(failed_or_weak),
            "spectrum_only_ranking_changes": spectrum_only_changes[: args.max_diagnostics],
            "spectrum_only_ranking_change_count": len(spectrum_only_changes),
        },
    }

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "ranking_eval.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    write_markdown(out_dir / "ranking_eval.md", report)
    print(f"[ranking-eval] wrote {out_dir / 'ranking_eval.md'}")
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description="Evaluate Spectrum ranking variants without query expansion.")
    parser.add_argument("--benchmark-dir", default="benchmarks/generated/storage_benchmark_6k")
    parser.add_argument("--queries", default="", help="Optional query JSON path. Defaults to benchmark-dir/queries.json.")
    parser.add_argument("--out-dir", default="benchmarks/generated/ranking_eval")
    parser.add_argument("--top-k", type=int, default=5)
    parser.add_argument("--max-diagnostics", type=int, default=20)
    parser.add_argument(
        "--retrieval-normalization",
        action="store_true",
        help="Normalize query text to match stores built with --retrieval-normalization.",
    )
    args = parser.parse_args()
    run(args)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
