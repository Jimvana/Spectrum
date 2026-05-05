"""
Compare Spectrum retrieval against local retrieval baselines.

Baselines:
  - Raw BM25 over source files (Lucene-style lexical proxy)
  - Tree-sitter chunk BM25, aggregated back to files
  - TF-IDF + TruncatedSVD dense vectors (local embedding proxy)
  - Hybrid BM25 + dense via reciprocal rank fusion

This is intentionally a small-corpus sanity benchmark. It does not replace a
real Lucene/Zoekt/neural-embedding benchmark, but it gives comparable local
signals without external services.
"""

from __future__ import annotations

import math
import re
import sys
import time
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np
from sklearn.decomposition import TruncatedSVD
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
from tree_sitter_language_pack import get_parser

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

from rag.indexer import index_directory, load_index, save_index
from rag.query import BM25 as SpectrumBM25
from rag.query import search as spectrum_search


SOURCE_DIR = ROOT / "test_sources"
SPEC_DIR = ROOT / "spec_format" / "output"
INDEX_PATH = ROOT / "rag" / "index.json"

EXTS = {".py", ".html", ".htm", ".js", ".css", ".txt"}
LANG_BY_EXT = {
    ".py": "python",
    ".js": "javascript",
    ".css": "css",
    ".html": "html",
    ".htm": "html",
}


QUERIES = [
    ("for loop range append list", "py", {"mega_stdlib", "encoder", "fibonacci"}),
    ("class __init__ self return", "py", {"mega_stdlib", "decoder", "encoder", "fibonacci"}),
    ("function var const return if else", "js", {"jquery", "bootstrap_js"}),
    ("margin padding font-size color", "css", {"bootstrap_css", "bulma.min", "normalize"}),
    ("html head body div class href", "html", {"socat", "underscore_docs"}),
    ("the and of to in a is that", "txt", {"moby_dick", "sample_english"}),
    ("error exception try catch raise", "py", {"mega_stdlib", "decoder"}),
    ("background-color display flex", "css", {"bootstrap_css", "bulma.min", "normalize"}),
]


def label_for_source(path: Path) -> str:
    if path.name == "bootstrap.css":
        return "bootstrap_css"
    if path.name == "bootstrap.js":
        return "bootstrap_js"
    if path.name == "moby dick.txt":
        return "moby_dick"
    if path.name == "underscore_docs.html":
        return "underscore_docs"
    return path.stem


def tokenize(text: str) -> list[str]:
    return re.findall(r"[a-zA-Z_][a-zA-Z0-9_-]*|__[a-zA-Z0-9_]+__", text.lower())


class BM25:
    def __init__(self, docs: list[dict], k1: float = 1.5, b: float = 0.75):
        self.docs = docs
        self.k1 = k1
        self.b = b
        self.freq = [Counter(d["tokens"]) for d in docs]
        self.lengths = [len(d["tokens"]) for d in docs]
        self.N = len(docs)
        self.avdl = sum(self.lengths) / self.N if self.N else 0.0
        self.inv = defaultdict(list)
        for doc_id, freq in enumerate(self.freq):
            for tok in freq:
                self.inv[tok].append(doc_id)

    def idf(self, token: str) -> float:
        df = len(self.inv.get(token, []))
        return math.log((self.N - df + 0.5) / (df + 0.5) + 1)

    def score_doc(self, doc_id: int, query_tokens: list[str]) -> float:
        freq = self.freq[doc_id]
        dl = self.lengths[doc_id]
        norm = 1 - self.b + self.b * (dl / self.avdl) if self.avdl else 1.0
        total = 0.0
        for tok in query_tokens:
            tf = freq.get(tok, 0)
            if tf:
                total += self.idf(tok) * (tf * (self.k1 + 1)) / (tf + self.k1 * norm)
        return total

    def search(self, query: str, top_k: int = 10) -> list[tuple[str, float]]:
        q = tokenize(query)
        candidates = set()
        for tok in set(q):
            candidates.update(self.inv.get(tok, []))
        scored = [(self.docs[i]["label"], self.score_doc(i, q)) for i in candidates]
        scored.sort(key=lambda x: x[1], reverse=True)
        return scored[:top_k]


def load_sources() -> list[dict]:
    docs = []
    for path in sorted(SOURCE_DIR.iterdir()):
        if path.is_file() and path.suffix.lower() in EXTS:
            text = path.read_text(encoding="utf-8", errors="replace")
            docs.append({
                "label": label_for_source(path),
                "path": path,
                "text": text,
                "tokens": tokenize(text),
            })
    return docs


CHUNK_NODE_TYPES = {
    "python": {"function_definition", "class_definition"},
    "javascript": {"function_declaration", "class_declaration", "method_definition", "lexical_declaration"},
    "css": {"rule_set", "at_rule"},
    "html": {"element", "script_element", "style_element"},
}


def tree_chunks_for_doc(doc: dict) -> list[dict]:
    ext = doc["path"].suffix.lower()
    lang = LANG_BY_EXT.get(ext)
    text = doc["text"]
    if not lang:
        return window_chunks(doc, 180, 80)

    try:
        parser = get_parser(lang)
        tree = parser.parse(text.encode("utf-8", errors="replace"))
    except Exception:
        return window_chunks(doc, 180, 80)

    target_types = CHUNK_NODE_TYPES.get(lang, set())
    chunks = []

    def visit(node):
        if node.type in target_types and node.end_byte > node.start_byte:
            part = text.encode("utf-8")[node.start_byte:node.end_byte].decode("utf-8", errors="replace")
            toks = tokenize(part)
            if len(toks) >= 3:
                chunks.append({"label": doc["label"], "text": part, "tokens": toks})
                return
        for child in node.children:
            visit(child)

    visit(tree.root_node)
    return chunks or window_chunks(doc, 180, 80)


def window_chunks(doc: dict, size: int, stride: int) -> list[dict]:
    toks = doc["tokens"]
    if not toks:
        return [{"label": doc["label"], "text": doc["text"], "tokens": []}]
    chunks = []
    for i in range(0, len(toks), stride):
        part = toks[i:i + size]
        if part:
            chunks.append({"label": doc["label"], "text": " ".join(part), "tokens": part})
        if i + size >= len(toks):
            break
    return chunks


class ChunkBM25:
    def __init__(self, source_docs: list[dict]):
        chunks = []
        for doc in source_docs:
            chunks.extend(tree_chunks_for_doc(doc))
        self.chunk_count = len(chunks)
        self.bm25 = BM25(chunks)

    def search(self, query: str, top_k: int = 10) -> list[tuple[str, float]]:
        chunk_results = self.bm25.search(query, top_k=100)
        best = {}
        for label, score in chunk_results:
            best[label] = max(score, best.get(label, 0.0))
        return sorted(best.items(), key=lambda x: x[1], reverse=True)[:top_k]


class DenseLSA:
    def __init__(self, docs: list[dict]):
        self.labels = [d["label"] for d in docs]
        self.vectorizer = TfidfVectorizer(
            lowercase=True,
            token_pattern=r"(?u)\b[a-zA-Z_][a-zA-Z0-9_-]+\b",
            ngram_range=(1, 2),
            sublinear_tf=True,
        )
        tfidf = self.vectorizer.fit_transform([d["text"] for d in docs])
        dims = max(2, min(64, tfidf.shape[0] - 1, tfidf.shape[1] - 1))
        self.svd = TruncatedSVD(n_components=dims, random_state=7)
        self.matrix = self.svd.fit_transform(tfidf)
        norms = np.linalg.norm(self.matrix, axis=1, keepdims=True)
        self.matrix = self.matrix / np.maximum(norms, 1e-12)

    def search(self, query: str, top_k: int = 10) -> list[tuple[str, float]]:
        q = self.vectorizer.transform([query])
        qv = self.svd.transform(q)
        qv = qv / max(np.linalg.norm(qv), 1e-12)
        scores = cosine_similarity(qv, self.matrix)[0]
        ranked = sorted(zip(self.labels, scores), key=lambda x: x[1], reverse=True)
        return [(label, float(score)) for label, score in ranked[:top_k]]


def rrf(result_lists: list[list[tuple[str, float]]], top_k: int = 10, k: int = 60) -> list[tuple[str, float]]:
    scores = defaultdict(float)
    for results in result_lists:
        for rank, (label, _) in enumerate(results, start=1):
            scores[label] += 1.0 / (k + rank)
    return sorted(scores.items(), key=lambda x: x[1], reverse=True)[:top_k]


def spectrum_adapter(index: dict):
    scorer = SpectrumBM25(index)

    def run(query: str, lang: str = "txt", top_k: int = 10) -> list[tuple[str, float]]:
        results = spectrum_search(query, index, top_k=top_k, lang=lang, bm25=scorer)
        return [(r["name"], float(r["score"])) for r in results]

    return run


def metrics(results: list[tuple[str, float]], expected: set[str]) -> tuple[int, float, int]:
    labels = [r[0] for r in results]
    hit_at_1 = int(bool(labels) and labels[0] in expected)
    rr = 0.0
    for i, label in enumerate(labels, start=1):
        if label in expected:
            rr = 1.0 / i
            break
    recall_at_5 = len(set(labels[:5]) & expected)
    return hit_at_1, rr, recall_at_5


def benchmark_method(name: str, fn, queries=QUERIES):
    rows = []
    times = []
    for query, lang, expected in queries:
        t0 = time.perf_counter()
        if name == "Spectrum BM25":
            results = fn(query, lang=lang, top_k=10)
        else:
            results = fn(query, top_k=10)
        times.append((time.perf_counter() - t0) * 1000)
        h1, rr, r5 = metrics(results, expected)
        rows.append((query, expected, results[:5], h1, rr, r5))
    return {
        "name": name,
        "rows": rows,
        "hit1": sum(r[3] for r in rows) / len(rows),
        "mrr": sum(r[4] for r in rows) / len(rows),
        "recall5": sum(r[5] for r in rows) / sum(len(r[1]) for r in rows),
        "avg_ms": sum(times) / len(times),
        "p95_ms": sorted(times)[int(len(times) * 0.95) - 1],
    }


def main():
    if not INDEX_PATH.exists():
        index = index_directory(SPEC_DIR)
        save_index(index, INDEX_PATH)
    else:
        index = load_index(INDEX_PATH)

    t0 = time.perf_counter()
    source_docs = load_sources()
    raw_bm25 = BM25(source_docs)
    raw_build_ms = (time.perf_counter() - t0) * 1000

    t0 = time.perf_counter()
    chunk_bm25 = ChunkBM25(source_docs)
    chunk_build_ms = (time.perf_counter() - t0) * 1000

    t0 = time.perf_counter()
    dense = DenseLSA(source_docs)
    dense_build_ms = (time.perf_counter() - t0) * 1000

    spec = spectrum_adapter(index)

    def hybrid(query: str, top_k: int = 10):
        return rrf([raw_bm25.search(query, top_k=10), dense.search(query, top_k=10)], top_k=top_k)

    reports = [
        benchmark_method("Spectrum BM25", spec),
        benchmark_method("Raw BM25", raw_bm25.search),
        benchmark_method("Tree-sitter chunk BM25", chunk_bm25.search),
        benchmark_method("Dense LSA proxy", dense.search),
        benchmark_method("Hybrid Raw BM25 + LSA", hybrid),
    ]

    print("\nBuild/index time")
    print(f"  Raw BM25 source index:          {raw_build_ms:8.2f} ms ({len(source_docs)} docs)")
    print(f"  Tree-sitter chunk BM25 index:   {chunk_build_ms:8.2f} ms ({chunk_bm25.chunk_count} chunks)")
    print(f"  Dense LSA proxy index:          {dense_build_ms:8.2f} ms ({len(source_docs)} docs)")
    print("  Spectrum index:                 prebuilt rag/index.json")

    print("\nRetrieval quality on labelled query set")
    print(f"{'Method':<28} {'Hit@1':>8} {'MRR':>8} {'Recall@5':>10} {'Avg ms/q':>10} {'P95 ms':>8}")
    for r in reports:
        print(f"{r['name']:<28} {r['hit1']*100:7.1f}% {r['mrr']:8.3f} {r['recall5']*100:9.1f}% {r['avg_ms']:10.3f} {r['p95_ms']:8.3f}")

    print("\nTop-5 results by query")
    for i, (query, _, expected) in enumerate(QUERIES, start=1):
        print(f"\n{i}. {query}  expected={sorted(expected)}")
        for r in reports:
            top = ", ".join(label for label, _ in r["rows"][i - 1][2])
            print(f"  {r['name']:<28} {top}")


if __name__ == "__main__":
    main()
