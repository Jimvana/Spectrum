"""
Audit document/query normalization for Spectrum retrieval.

The audit compares the current base token stream with the shared retrieval
normalization path. It is intentionally small and inspectable so regressions can
be added as troublesome queries are found.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_ROOT))

import dictionary as D
from rag.normalization import (  # noqa: E402
    dict_token_ids_from_text,
    normalized_text_variants,
    retrieval_token_ids,
)


DEFAULT_CASES = [
    {"name": "camelcase-title", "document": "AfghanistanPeople", "query": "Afghanistan people"},
    {"name": "camelcase-query", "document": "Afghanistan people", "query": "AfghanistanPeople"},
    {"name": "hyphen-space", "document": "United-States foreign policy", "query": "United States foreign policy"},
    {"name": "apostrophe-joined", "document": "don't stop", "query": "dont stop"},
    {"name": "apostrophe-curly", "document": "don\u2019t stop", "query": "don't stop"},
    {"name": "possessive", "document": "Afghanistan's population", "query": "Afghanistan population"},
    {"name": "year-suffix", "document": "1990s conflict", "query": "1990 s conflict"},
    {"name": "html-entity", "document": "AT&amp;T history", "query": "AT&T history"},
    {"name": "slash-separator", "document": "link/url anchor href", "query": "link url anchor href"},
    {"name": "underscore-identifier", "document": "write_binary_postings", "query": "write binary postings"},
]


def token_name(token_id: int) -> str:
    return D.SPEC_ID_TO_TOKEN.get(token_id, f"<{token_id}>")


def describe_ids(ids: list[int]) -> list[dict]:
    return [{"id": token_id, "token": token_name(token_id)} for token_id in ids]


def overlap(left: list[int], right: list[int]) -> list[int]:
    right_set = set(right)
    return [token_id for token_id in dict.fromkeys(left) if token_id in right_set]


def audit_case(case: dict) -> dict:
    doc = case["document"]
    query = case["query"]
    doc_base = dict_token_ids_from_text(doc)
    query_base = dict_token_ids_from_text(query)
    doc_norm = retrieval_token_ids(doc)
    query_norm = retrieval_token_ids(query)
    base_overlap = overlap(doc_base, query_base)
    norm_overlap = overlap(doc_norm, query_norm)
    return {
        "name": case["name"],
        "document": doc,
        "query": query,
        "base": {
            "document": describe_ids(doc_base),
            "query": describe_ids(query_base),
            "overlap": describe_ids(base_overlap),
            "overlap_count": len(base_overlap),
        },
        "normalized": {
            "document": describe_ids(doc_norm),
            "query": describe_ids(query_norm),
            "overlap": describe_ids(norm_overlap),
            "overlap_count": len(norm_overlap),
        },
        "variants": {
            "document": normalized_text_variants(doc),
            "query": normalized_text_variants(query),
        },
    }


def write_markdown(path: Path, report: dict) -> None:
    lines = [
        "# Spectrum Normalization Audit",
        "",
        f"- Cases: {report['summary']['cases']}",
        f"- Improved: {report['summary']['improved']}",
        f"- Still zero overlap: {report['summary']['still_zero_overlap']}",
        "",
        "| Case | Base overlap | Normalized overlap | Added tokens |",
        "|---|---:|---:|---|",
    ]
    for row in report["cases"]:
        added = [
            item["token"] for item in row["normalized"]["overlap"]
            if item not in row["base"]["overlap"]
        ]
        lines.append(
            f"| {row['name']} | {row['base']['overlap_count']} | "
            f"{row['normalized']['overlap_count']} | `{', '.join(added[:8])}` |"
        )

    lines.extend(["", "## Details", ""])
    for row in report["cases"]:
        lines.extend([
            f"### {row['name']}",
            "",
            f"- Document: `{row['document']}`",
            f"- Query: `{row['query']}`",
            f"- Document variants: `{row['variants']['document']}`",
            f"- Query variants: `{row['variants']['query']}`",
            f"- Base overlap: `{[item['token'] for item in row['base']['overlap']]}`",
            f"- Normalized overlap: `{[item['token'] for item in row['normalized']['overlap']]}`",
            "",
        ])

    path.write_text("\n".join(lines), encoding="utf-8")


def load_cases(path: str) -> list[dict]:
    if not path:
        return DEFAULT_CASES
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(data, list):
        raise ValueError("Normalization audit cases must be a JSON list")
    return data


def run(args: argparse.Namespace) -> dict:
    cases = [audit_case(case) for case in load_cases(args.cases)]
    improved = sum(
        1 for case in cases
        if case["normalized"]["overlap_count"] > case["base"]["overlap_count"]
    )
    still_zero = sum(1 for case in cases if case["normalized"]["overlap_count"] == 0)
    report = {
        "format": "spectrum-normalization-audit-v1",
        "summary": {
            "cases": len(cases),
            "improved": improved,
            "still_zero_overlap": still_zero,
        },
        "cases": cases,
    }

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "normalization_audit.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    write_markdown(out_dir / "normalization_audit.md", report)
    print(f"[normalization-audit] wrote {out_dir / 'normalization_audit.md'}")
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description="Audit Spectrum document/query retrieval normalization.")
    parser.add_argument("--cases", default="", help="Optional JSON list of audit cases.")
    parser.add_argument("--out-dir", default="benchmarks/generated/normalization_audit")
    args = parser.parse_args()
    run(args)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
