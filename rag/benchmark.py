"""
Spectrum RAG — Benchmark
=========================
Compares Spectrum BM25 retrieval (operating on .spec token IDs) against a
raw-text BM25 baseline (operating on whitespace-split words).

Two tests are run:

1. Self-retrieval test
   Each document is used as its own query.  A perfect retrieval system returns
   rank-1 = the document itself.  MRR (Mean Reciprocal Rank) across all docs
   measures overall index quality.  Both systems are scored the same way.

2. Manual query test
   A set of hand-written queries is run against both systems.  Results are
   printed side-by-side so you can see where the systems agree or diverge.

Run from the project root:
    python -m rag.benchmark

or:
    python rag/benchmark.py
"""

import sys
import re
import math
from pathlib import Path
from collections import Counter

_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_ROOT))
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from rag.indexer import index_directory, save_index, load_index, extract_token_ids
from rag.query   import BM25, search, print_results, encode_query
import dictionary as D

# ─────────────────────────────────────────────────────────────────────────────
# Raw-text BM25 baseline
# ─────────────────────────────────────────────────────────────────────────────

def _tokenise_raw(text: str) -> list[str]:
    """Minimal whitespace + punctuation tokenizer for the baseline."""
    return re.findall(r"[a-zA-Z_][a-zA-Z0-9_]*", text.lower())


class RawTextBM25:
    """
    BM25 over raw source files — the baseline to beat.
    Reads the original source files (not .spec), tokenizes by word, and scores.
    """

    def __init__(self, source_paths: list[Path], k1: float = 1.5, b: float = 0.75):
        self.k1 = k1
        self.b  = b
        self.docs: list[dict] = []
        self._freq: list[Counter] = []
        self._inv:  dict[str, list[int]] = {}

        for doc_id, path in enumerate(source_paths):
            try:
                text   = path.read_text(encoding="utf-8", errors="replace")
                tokens = _tokenise_raw(text)
            except Exception as e:
                print(f"[baseline] WARNING: skipping {path.name} — {e}")
                continue

            freq = Counter(tokens)
            self.docs.append({
                "id":   doc_id,
                "name": path.stem,
                "path": str(path),
                "token_count": len(tokens),
            })
            self._freq.append(freq)
            for tok in freq:
                self._inv.setdefault(tok, []).append(doc_id)

        total = sum(d["token_count"] for d in self.docs)
        self.N    = len(self.docs)
        self.avdl = total / self.N if self.N else 0.0

    def idf(self, token: str) -> float:
        df = len(self._inv.get(token, []))
        return math.log((self.N - df + 0.5) / (df + 0.5) + 1)

    def score(self, doc_id: int, query_tokens: list[str]) -> float:
        freq = self._freq[doc_id]
        dl   = self.docs[doc_id]["token_count"]
        norm = 1 - self.b + self.b * (dl / self.avdl) if self.avdl > 0 else 1.0
        total = 0.0
        for tok in query_tokens:
            tf = freq.get(tok, 0)
            if tf == 0:
                continue
            total += self.idf(tok) * (tf * (self.k1 + 1)) / (tf + self.k1 * norm)
        return total

    def search(self, query_text: str, top_k: int = 10) -> list[dict]:
        query_tokens = _tokenise_raw(query_text)
        candidates: set[int] = set()
        for tok in set(query_tokens):
            candidates.update(self._inv.get(tok, []))
        if not candidates:
            return []
        scored = [(doc_id, self.score(doc_id, query_tokens))
                  for doc_id in candidates]
        scored.sort(key=lambda x: x[1], reverse=True)
        results = []
        for rank, (doc_id, score) in enumerate(scored[:top_k], start=1):
            results.append({
                "rank":  rank,
                "name":  self.docs[doc_id]["name"],
                "path":  self.docs[doc_id]["path"],
                "score": round(score, 4),
            })
        return results


# ─────────────────────────────────────────────────────────────────────────────
# Self-retrieval test
# ─────────────────────────────────────────────────────────────────────────────

def self_retrieval_test(index: dict, baseline: RawTextBM25) -> dict:
    """
    For each indexed .spec file, query both systems with the full document
    content and record what rank the document itself appears at.

    Returns a summary dict with MRR and per-doc details.
    """
    bm25   = BM25(index)
    docs   = index["documents"]

    spec_ranks: list[int]     = []
    baseline_ranks: list[int] = []
    details: list[dict]       = []

    for doc in docs:
        doc_id   = doc["id"]
        doc_name = doc["name"]
        lang_id  = doc["language_id"]

        # ── Spectrum: query using the document's own token IDs ─────────────
        _, own_ids = extract_token_ids(doc["path"])
        if not own_ids:
            continue

        candidates: set[int] = set()
        for tid in set(own_ids):
            candidates.update(bm25._inv.get(tid, []))

        scored = sorted(
            [(did, bm25.score(did, own_ids)) for did in candidates],
            key=lambda x: x[1], reverse=True
        )
        spec_rank = next(
            (i + 1 for i, (did, _) in enumerate(scored) if did == doc_id),
            len(docs) + 1
        )

        # ── Baseline: query using the raw source text ─────────────────────
        # Find matching baseline doc by name
        b_doc_id = next(
            (i for i, d in enumerate(baseline.docs) if d["name"] == doc_name),
            None
        )
        if b_doc_id is not None:
            src_path  = Path(baseline.docs[b_doc_id]["path"])
            try:
                raw_text  = src_path.read_text(encoding="utf-8", errors="replace")
                b_results = baseline.search(raw_text, top_k=len(baseline.docs))
                baseline_rank = next(
                    (r["rank"] for r in b_results if r["name"] == doc_name),
                    len(docs) + 1
                )
            except Exception:
                baseline_rank = len(docs) + 1
        else:
            baseline_rank = len(docs) + 1

        spec_ranks.append(spec_rank)
        baseline_ranks.append(baseline_rank)

        details.append({
            "name":           doc_name,
            "spec_rank":      spec_rank,
            "baseline_rank":  baseline_rank,
        })

        spec_sym    = "✓" if spec_rank     == 1 else f"#{spec_rank}"
        base_sym    = "✓" if baseline_rank == 1 else f"#{baseline_rank}"
        print(f"  {doc_name:<35}  Spectrum: {spec_sym:<4}  Baseline: {base_sym}")

    mrr_spec     = sum(1/r for r in spec_ranks)     / len(spec_ranks)     if spec_ranks     else 0
    mrr_baseline = sum(1/r for r in baseline_ranks) / len(baseline_ranks) if baseline_ranks else 0
    top1_spec     = sum(1 for r in spec_ranks     if r == 1) / len(spec_ranks)     if spec_ranks     else 0
    top1_baseline = sum(1 for r in baseline_ranks if r == 1) / len(baseline_ranks) if baseline_ranks else 0

    return {
        "spectrum_mrr":      round(mrr_spec,     4),
        "baseline_mrr":      round(mrr_baseline, 4),
        "spectrum_top1":     round(top1_spec,     4),
        "baseline_top1":     round(top1_baseline, 4),
        "details":           details,
    }


# ─────────────────────────────────────────────────────────────────────────────
# Manual query test
# ─────────────────────────────────────────────────────────────────────────────

MANUAL_QUERIES = [
    # (query_text, lang_hint, description)
    ("for loop range append list",        "py",   "Python iteration patterns"),
    ("class __init__ self return",        "py",   "Python class structure"),
    ("function var const return if else", "js",   "JS control flow"),
    ("margin padding font-size color",    "css",  "CSS box model & typography"),
    ("html head body div class href",     "html", "HTML document structure"),
    ("the and of to in a is that",        "txt",  "Common English words (prose)"),
    ("error exception try catch raise",   "py",   "Error handling"),
    ("background-color display flex",     "css",  "CSS layout"),
]


def manual_query_test(index: dict, baseline: RawTextBM25, top_k: int = 5) -> None:
    """Run manual queries and print side-by-side results."""
    bm25 = BM25(index)

    for query_text, lang, description in MANUAL_QUERIES:
        print(f"\n{'═'*72}")
        print(f"  Query: \"{query_text}\"  [{description}]")
        print(f"{'─'*72}")

        # Spectrum
        spec_results = search(query_text, index, top_k=top_k,
                              lang=lang, bm25=bm25)
        print(f"  {'SPECTRUM BM25':<35}  {'BASELINE BM25'}")
        print(f"  {'─'*35}  {'─'*30}")

        base_results = baseline.search(query_text, top_k=top_k)

        max_rows = max(len(spec_results), len(base_results))
        for i in range(max_rows):
            s = spec_results[i] if i < len(spec_results) else None
            b = base_results[i] if i < len(base_results) else None
            s_str = f"{i+1}. {s['name']:<28} {s['score']:>7.3f}" if s else " " * 37
            b_str = f"{i+1}. {b['name']:<28} {b['score']:>7.3f}" if b else ""
            print(f"  {s_str}  {b_str}")


# ─────────────────────────────────────────────────────────────────────────────
# Entry point
# ─────────────────────────────────────────────────────────────────────────────

def main():
    import argparse

    parser = argparse.ArgumentParser(
        description="Spectrum RAG Benchmark — Spectrum BM25 vs raw-text BM25")
    parser.add_argument("--spec-dir",   default="spec_format/output",
                        help="Directory of indexed .spec files")
    parser.add_argument("--source-dir", default="test_sources",
                        help="Directory of original source files (for baseline)")
    parser.add_argument("--index",      default="rag/index.bin",
                        help="Index path (built if missing; use .json for legacy JSON)")
    parser.add_argument("--rebuild",    action="store_true",
                        help="Force rebuild the index")
    args = parser.parse_args()

    spec_dir   = _ROOT / args.spec_dir
    source_dir = _ROOT / args.source_dir
    index_path = _ROOT / args.index

    # ── Build / load Spectrum index ────────────────────────────────────────
    if args.rebuild or not index_path.exists():
        print("── Building Spectrum index ───────────────────────────────────\n")
        index = index_directory(spec_dir)
        save_index(index, index_path)
    else:
        index = load_index(index_path)

    # ── Build raw-text baseline ────────────────────────────────────────────
    print("\n── Building raw-text BM25 baseline ──────────────────────────────\n")
    # Map spec doc names back to source files
    source_paths = []
    for doc in index["documents"]:
        name     = doc["name"]
        # Try common extensions
        for ext in (".py", ".html", ".htm", ".js", ".css", ".txt"):
            candidate = source_dir / (name + ext)
            # Strip _decoded suffix if present
            if not candidate.exists():
                candidate = source_dir / (name.replace("_decoded", "") + ext)
            if candidate.exists():
                source_paths.append(candidate)
                break

    if not source_paths:
        print(f"[benchmark] WARNING: no source files found in {source_dir} — "
              "baseline will be empty. Pass --source-dir to point at your sources.")

    baseline = RawTextBM25(source_paths)
    print(f"[baseline] Loaded {len(baseline.docs)} source documents")

    # ── Self-retrieval test ────────────────────────────────────────────────
    print("\n── Self-retrieval test ───────────────────────────────────────────\n")
    summary = self_retrieval_test(index, baseline)

    print(f"\n  ┌─────────────────────────────────────────────┐")
    print(f"  │  Metric              Spectrum    Baseline   │")
    print(f"  ├─────────────────────────────────────────────┤")
    print(f"  │  MRR                 {summary['spectrum_mrr']:.4f}      {summary['baseline_mrr']:.4f}     │")
    print(f"  │  Top-1 accuracy      {summary['spectrum_top1']*100:.1f}%       {summary['baseline_top1']*100:.1f}%      │")
    print(f"  └─────────────────────────────────────────────┘")

    # ── Manual query test ─────────────────────────────────────────────────
    print("\n── Manual query test ─────────────────────────────────────────────")
    manual_query_test(index, baseline)

    print(f"\n{'═'*72}")
    print("  Benchmark complete.")


if __name__ == "__main__":
    main()
