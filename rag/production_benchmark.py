"""
Production-engine benchmark runner for existing Spectrum codebase benchmarks.

The runner consumes a benchmark directory created by rag/codebase_benchmark.py
and evaluates multiple retrieval engines against the exact same chunks and
queries. Core local baselines always run. Production adapters are optional and
report a skipped status when their service or dependency is unavailable.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import shutil
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from statistics import mean
from typing import Protocol

_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_ROOT))

from rag.ranking_eval import RawTextBM25, conventional_rank, raw_bm25_rank
from rag.spectrum_serving import SpectrumServingRetriever, title_token_index, windowed_snippet
from rag.storage_benchmark import load_binary_postings, preferred_binary_postings_path, reset_dir
from rag.codebase_benchmark import decode_code_spec_bytes, decode_code_spec_bytes_fast

try:
    import numpy as np
    from sklearn.decomposition import TruncatedSVD
    from sklearn.feature_extraction.text import TfidfVectorizer
    from sklearn.preprocessing import normalize
except Exception as exc:  # pragma: no cover
    raise SystemExit(
        "This benchmark requires numpy and scikit-learn. "
        f"Import failed: {exc}"
    )


@dataclass(frozen=True)
class CorpusDoc:
    id: int
    title: str
    text: str
    path: str


@dataclass
class EngineReport:
    name: str
    status: str
    build_seconds: float = 0.0
    build_cpu_seconds: float = 0.0
    index_bytes: int | None = None
    error: str = ""
    metrics: dict | None = None


class SearchEngine(Protocol):
    name: str

    def build(self, docs: list[CorpusDoc], work_dir: Path) -> EngineReport:
        ...

    def search(self, query: str, top_k: int) -> list[int]:
        ...

    def hydrate(self, doc_ids: list[int]) -> list[str]:
        ...


def read_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def read_jsonl(path: Path) -> list[dict]:
    rows = []
    with path.open(encoding="utf-8") as f:
        for line in f:
            if line.strip():
                rows.append(json.loads(line))
    return rows


def dir_size(path: Path) -> int:
    if not path.exists():
        return 0
    return sum(item.stat().st_size for item in path.rglob("*") if item.is_file())


def percentile(values: list[float], pct: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    idx = min(len(ordered) - 1, math.ceil((pct / 100) * len(ordered)) - 1)
    return ordered[idx]


def load_corpus(benchmark_dir: Path) -> list[CorpusDoc]:
    rows = read_jsonl(benchmark_dir / "conventional_tfidf" / "chunks.jsonl")
    return [
        CorpusDoc(
            id=int(row["id"]),
            title=str(row.get("title", row.get("source_path", row["id"]))),
            text=str(row["text"]),
            path=str(row.get("source_path", row.get("title", row["id"]))),
        )
        for row in rows
    ]


def load_queries(benchmark_dir: Path, query_path: Path | None) -> list[dict]:
    path = query_path if query_path else benchmark_dir / "queries.json"
    data = read_json(path)
    if not isinstance(data, list):
        raise ValueError(f"Expected query list at {path}")
    return data


def evaluate_engine(
    engine: SearchEngine,
    docs: list[CorpusDoc],
    queries: list[dict],
    top_k: int,
    work_dir: Path,
    hydrate_limit: int | None,
) -> EngineReport:
    try:
        report = engine.build(docs, work_dir)
    except Exception as exc:
        return EngineReport(name=engine.name, status="error", error=str(exc))
    if report.status != "ok":
        return report

    hit1 = 0
    recall = 0
    rr = []
    latencies = []
    end_to_end_latencies = []
    hydrate_latencies = []
    cpu_latencies = []
    cpu_search_latencies = []
    cpu_hydrate_latencies = []
    hydrated_bytes = []
    for item in queries:
        relevant = set(int(doc_id) for doc_id in item.get("relevant_ids", []))
        started = time.perf_counter()
        cpu_started = time.process_time()
        result_ids = engine.search(str(item["query"]), top_k)
        search_done = time.perf_counter()
        cpu_search_done = time.process_time()
        ids_to_hydrate = result_ids if hydrate_limit is None else result_ids[:hydrate_limit]
        payloads = engine.hydrate(ids_to_hydrate)
        hydrate_done = time.perf_counter()
        cpu_hydrate_done = time.process_time()
        latencies.append((search_done - started) * 1000)
        hydrate_latencies.append((hydrate_done - search_done) * 1000)
        end_to_end_latencies.append((hydrate_done - started) * 1000)
        cpu_search_latencies.append((cpu_search_done - cpu_started) * 1000)
        cpu_hydrate_latencies.append((cpu_hydrate_done - cpu_search_done) * 1000)
        cpu_latencies.append((cpu_hydrate_done - cpu_started) * 1000)
        hydrated_bytes.append(sum(len(payload.encode("utf-8")) for payload in payloads))
        if result_ids and result_ids[0] in relevant:
            hit1 += 1
        if relevant.intersection(result_ids):
            recall += 1
        rank = next((i + 1 for i, doc_id in enumerate(result_ids) if doc_id in relevant), None)
        rr.append(1 / rank if rank else 0.0)

    total = max(1, len(queries))
    report.metrics = {
        "hit_at_1": round(hit1 / total, 4),
        f"recall_at_{top_k}": round(recall / total, 4),
        "mrr": round(mean(rr) if rr else 0.0, 4),
        "avg_query_ms": round(mean(latencies) if latencies else 0.0, 4),
        "p95_query_ms": round(percentile(latencies, 95), 4),
        "avg_hydrate_ms": round(mean(hydrate_latencies) if hydrate_latencies else 0.0, 4),
        "p95_hydrate_ms": round(percentile(hydrate_latencies, 95), 4),
        "avg_end_to_end_ms": round(mean(end_to_end_latencies) if end_to_end_latencies else 0.0, 4),
        "p95_end_to_end_ms": round(percentile(end_to_end_latencies, 95), 4),
        "avg_cpu_query_ms": round(mean(cpu_search_latencies) if cpu_search_latencies else 0.0, 4),
        "avg_cpu_hydrate_ms": round(mean(cpu_hydrate_latencies) if cpu_hydrate_latencies else 0.0, 4),
        "avg_cpu_end_to_end_ms": round(mean(cpu_latencies) if cpu_latencies else 0.0, 4),
        "cpu_utilization_pct": round(
            (sum(cpu_latencies) / sum(end_to_end_latencies) * 100)
            if end_to_end_latencies and sum(end_to_end_latencies)
            else 0.0,
            2,
        ),
        "avg_hydrated_bytes": round(mean(hydrated_bytes) if hydrated_bytes else 0.0, 2),
        "hydrate_limit": hydrate_limit if hydrate_limit is not None else top_k,
    }
    return report


class RawHydrationMixin:
    def build_hydrator(self, docs: list[CorpusDoc]) -> None:
        self.docs_by_id = {doc.id: doc.text for doc in docs}

    def hydrate(self, doc_ids: list[int]) -> list[str]:
        return [self.docs_by_id[doc_id] for doc_id in doc_ids if doc_id in self.docs_by_id]


class TfidfEngine(RawHydrationMixin):
    name = "raw_tfidf_sklearn"

    def build(self, docs: list[CorpusDoc], work_dir: Path) -> EngineReport:
        started = time.perf_counter()
        cpu_started = time.process_time()
        self.build_hydrator(docs)
        self.vectorizer = TfidfVectorizer(
            lowercase=True,
            stop_words="english",
            max_features=100_000,
            norm="l2",
        )
        self.matrix = self.vectorizer.fit_transform([doc.text for doc in docs])
        return EngineReport(
            name=self.name,
            status="ok",
            build_seconds=round(time.perf_counter() - started, 4),
            build_cpu_seconds=round(time.process_time() - cpu_started, 4),
        )

    def search(self, query: str, top_k: int) -> list[int]:
        return [doc_id for doc_id, _score in conventional_rank(self.vectorizer, self.matrix, query, top_k)]


class RawBM25Engine(RawHydrationMixin):
    name = "raw_bm25_python"

    def build(self, docs: list[CorpusDoc], work_dir: Path) -> EngineReport:
        started = time.perf_counter()
        cpu_started = time.process_time()
        self.build_hydrator(docs)
        self.bm25 = RawTextBM25([doc.__dict__ for doc in docs])
        return EngineReport(
            name=self.name,
            status="ok",
            build_seconds=round(time.perf_counter() - started, 4),
            build_cpu_seconds=round(time.process_time() - cpu_started, 4),
        )

    def search(self, query: str, top_k: int) -> list[int]:
        return [doc_id for doc_id, _score in raw_bm25_rank(self.bm25, query, top_k)]


class SpectrumBM25Engine:
    def __init__(
        self,
        benchmark_dir: Path,
        name: str = "spectrum_spb_bm25",
        cache_hydration: bool = False,
        fast_decode: bool = False,
        preload_specs: bool = True,
        title_boost: float = 0.5,
    ):
        self.benchmark_dir = benchmark_dir
        self.name = name
        self.cache_hydration = cache_hydration
        self.fast_decode = fast_decode
        self.preload_specs = preload_specs
        self.title_boost = title_boost

    def build(self, docs: list[CorpusDoc], work_dir: Path) -> EngineReport:
        started = time.perf_counter()
        cpu_started = time.process_time()
        store_dir = self.benchmark_dir / "spectrum_spec"
        self.store_dir = store_dir
        docs_meta = read_json(store_dir / "docs.json")
        self.spec_paths = {
            int(doc["id"]): store_dir / doc["path"]
            for doc in docs_meta["documents"]
        }
        self.hydration_cache: dict[int, str] = {}
        self.title_index = title_token_index(docs_meta["documents"]) if self.title_boost else None
        self.spec_bytes: dict[int, bytes] = {}
        if self.preload_specs:
            self.spec_bytes = {
                doc_id: path.read_bytes()
                for doc_id, path in self.spec_paths.items()
            }
        self.bm25 = load_binary_postings(
            preferred_binary_postings_path(store_dir),
            docs_meta["documents"],
        )
        return EngineReport(
            name=self.name,
            status="ok",
            build_seconds=round(time.perf_counter() - started, 4),
            build_cpu_seconds=round(time.process_time() - cpu_started, 4),
            index_bytes=dir_size(store_dir),
        )

    def search(self, query: str, top_k: int) -> list[int]:
        from rag.normalization import retrieval_token_ids

        self.last_query = query
        return self.bm25.search(
            retrieval_token_ids(query),
            top_k,
            max_df_ratio=0.9,
            title_index=self.title_index,
            title_boost=self.title_boost,
        )

    def hydrate(self, doc_ids: list[int]) -> list[str]:
        payloads = []
        for doc_id in doc_ids:
            if self.cache_hydration and doc_id in self.hydration_cache:
                payloads.append(self.hydration_cache[doc_id])
                continue
            path = self.spec_paths.get(doc_id)
            if path is not None:
                decoder = decode_code_spec_bytes_fast if self.fast_decode else decode_code_spec_bytes
                data = self.spec_bytes.get(doc_id)
                if data is None:
                    data = path.read_bytes()
                payload = decoder(data)
                if self.cache_hydration:
                    self.hydration_cache[doc_id] = payload
                payloads.append(payload)
        return payloads


class SpectrumSnippetSidecarEngine(SpectrumBM25Engine):
    def __init__(self, benchmark_dir: Path, snippet_chars: int = 600):
        super().__init__(benchmark_dir, name="spectrum_snippet_sidecar")
        self.snippet_chars = snippet_chars

    def build(self, docs: list[CorpusDoc], work_dir: Path) -> EngineReport:
        report = super().build(docs, work_dir)
        self.snippets_by_id = {doc.id: doc.text[: self.snippet_chars] for doc in docs}
        snippet_bytes = sum(len(value.encode("utf-8")) for value in self.snippets_by_id.values())
        report.index_bytes = (report.index_bytes or 0) + snippet_bytes
        return report

    def hydrate(self, doc_ids: list[int]) -> list[str]:
        query = getattr(self, "last_query", "")
        return [
            windowed_snippet(self.snippets_by_id[doc_id], query, self.snippet_chars)
            for doc_id in doc_ids
            if doc_id in self.snippets_by_id
        ]


class SpectrumServingPipelineEngine:
    def __init__(
        self,
        benchmark_dir: Path,
        name: str = "spectrum_serving_pipeline",
        preload_specs: bool = True,
    ):
        self.benchmark_dir = benchmark_dir
        self.name = name
        self.preload_specs = preload_specs

    def build(self, docs: list[CorpusDoc], work_dir: Path) -> EngineReport:
        started = time.perf_counter()
        cpu_started = time.process_time()
        sidecar_path = work_dir / "snippet_sidecar.json"
        self.retriever = SpectrumServingRetriever.from_codebase_benchmark(
            self.benchmark_dir,
            sidecar_path=sidecar_path,
            preload_specs=self.preload_specs,
        )
        store_bytes = dir_size(self.benchmark_dir / "spectrum_spec")
        sidecar_bytes = sidecar_path.stat().st_size if sidecar_path.exists() else 0
        return EngineReport(
            name=self.name,
            status="ok",
            build_seconds=round(time.perf_counter() - started, 4),
            build_cpu_seconds=round(time.process_time() - cpu_started, 4),
            index_bytes=store_bytes + sidecar_bytes,
        )

    def search(self, query: str, top_k: int) -> list[int]:
        self.last_results = self.retriever.search(query, top_k=top_k)
        return [result.id for result in self.last_results]

    def hydrate(self, doc_ids: list[int]) -> list[str]:
        if not doc_ids:
            return []
        snippets = [
            result.snippet
            for result in getattr(self, "last_results", [])
            if result.id in set(doc_ids)
        ]
        selected = self.retriever.decode(doc_ids[0]).text
        return snippets + [selected]


class DenseLsaEngine(RawHydrationMixin):
    name = "dense_lsa_numpy"

    def __init__(self, dimensions: int = 256):
        self.dimensions = dimensions

    def build(self, docs: list[CorpusDoc], work_dir: Path) -> EngineReport:
        started = time.perf_counter()
        cpu_started = time.process_time()
        self.build_hydrator(docs)
        self.vectorizer = TfidfVectorizer(
            lowercase=True,
            stop_words="english",
            max_features=100_000,
            norm="l2",
        )
        tfidf = self.vectorizer.fit_transform([doc.text for doc in docs])
        dims = min(self.dimensions, max(1, min(tfidf.shape) - 1))
        self.svd = TruncatedSVD(n_components=dims, random_state=42)
        self.matrix = normalize(self.svd.fit_transform(tfidf))
        return EngineReport(
            name=self.name,
            status="ok",
            build_seconds=round(time.perf_counter() - started, 4),
            build_cpu_seconds=round(time.process_time() - cpu_started, 4),
            index_bytes=int(self.matrix.nbytes),
        )

    def search(self, query: str, top_k: int) -> list[int]:
        q = self.vectorizer.transform([query])
        q_dense = normalize(self.svd.transform(q))
        scores = self.matrix @ q_dense.T
        order = np.argsort(-scores.ravel())[:top_k]
        return [int(idx) for idx in order if scores[int(idx)] > 0]


class FaissLsaEngine(DenseLsaEngine):
    name = "faiss_lsa_flat"

    def build(self, docs: list[CorpusDoc], work_dir: Path) -> EngineReport:
        try:
            import faiss
        except Exception as exc:
            return EngineReport(name=self.name, status="skipped", error=f"faiss not available: {exc}")
        report = super().build(docs, work_dir)
        self.index = faiss.IndexFlatIP(self.matrix.shape[1])
        self.index.add(self.matrix.astype("float32"))
        return EngineReport(
            name=self.name,
            status="ok",
            build_seconds=report.build_seconds,
            build_cpu_seconds=report.build_cpu_seconds,
            index_bytes=report.index_bytes,
        )

    def search(self, query: str, top_k: int) -> list[int]:
        q = self.vectorizer.transform([query])
        q_dense = normalize(self.svd.transform(q)).astype("float32")
        scores, ids = self.index.search(q_dense, top_k)
        return [int(doc_id) for doc_id, score in zip(ids[0], scores[0]) if doc_id >= 0 and score > 0]


class HybridRrfEngine:
    name = "hybrid_spectrum_dense_rrf"

    def __init__(self, spectrum: SpectrumBM25Engine, dense: DenseLsaEngine, rrf_k: int = 60):
        self.spectrum = spectrum
        self.dense = dense
        self.rrf_k = rrf_k

    def build(self, docs: list[CorpusDoc], work_dir: Path) -> EngineReport:
        started = time.perf_counter()
        cpu_started = time.process_time()
        spectrum_report = self.spectrum.build(docs, work_dir / "spectrum")
        if spectrum_report.status != "ok":
            return EngineReport(name=self.name, status=spectrum_report.status, error=spectrum_report.error)
        dense_report = self.dense.build(docs, work_dir / "dense")
        if dense_report.status != "ok":
            return EngineReport(name=self.name, status=dense_report.status, error=dense_report.error)
        return EngineReport(
            name=self.name,
            status="ok",
            build_seconds=round(time.perf_counter() - started, 4),
            build_cpu_seconds=round(time.process_time() - cpu_started, 4),
            index_bytes=(spectrum_report.index_bytes or 0) + (dense_report.index_bytes or 0),
        )

    def search(self, query: str, top_k: int) -> list[int]:
        candidates = top_k * 10
        rankings = [
            self.spectrum.search(query, candidates),
            self.dense.search(query, candidates),
        ]
        scores: dict[int, float] = {}
        for ranking in rankings:
            for rank, doc_id in enumerate(ranking, start=1):
                scores[doc_id] = scores.get(doc_id, 0.0) + 1 / (self.rrf_k + rank)
        return [doc_id for doc_id, _score in sorted(scores.items(), key=lambda item: item[1], reverse=True)[:top_k]]

    def hydrate(self, doc_ids: list[int]) -> list[str]:
        return self.spectrum.hydrate(doc_ids)


class ChromaLsaEngine(DenseLsaEngine):
    name = "chroma_lsa"

    def build(self, docs: list[CorpusDoc], work_dir: Path) -> EngineReport:
        try:
            import chromadb
        except Exception as exc:
            return EngineReport(name=self.name, status="skipped", error=f"chromadb not available: {exc}")
        report = super().build(docs, work_dir)
        self.client = chromadb.PersistentClient(path=str(work_dir / "chroma"))
        collection_name = "spectrum_prod_bench_" + hashlib.sha1(str(work_dir).encode()).hexdigest()[:8]
        self.collection = self.client.get_or_create_collection(collection_name)
        embeddings = self.matrix.astype("float32").tolist()
        batch_size = 1_000
        for start in range(0, len(docs), batch_size):
            batch = docs[start : start + batch_size]
            self.collection.add(
                ids=[str(doc.id) for doc in batch],
                documents=[doc.text for doc in batch],
                metadatas=[{"title": doc.title, "path": doc.path} for doc in batch],
                embeddings=embeddings[start : start + batch_size],
            )
        return EngineReport(
            name=self.name,
            status="ok",
            build_seconds=report.build_seconds,
            build_cpu_seconds=report.build_cpu_seconds,
            index_bytes=dir_size(work_dir / "chroma"),
        )

    def search(self, query: str, top_k: int) -> list[int]:
        q = self.vectorizer.transform([query])
        q_dense = normalize(self.svd.transform(q)).astype("float32").tolist()
        result = self.collection.query(query_embeddings=q_dense, n_results=top_k)
        return [int(doc_id) for doc_id in result.get("ids", [[]])[0]]


class OpenSearchEngine:
    name = "opensearch_bm25_http"

    def build(self, docs: list[CorpusDoc], work_dir: Path) -> EngineReport:
        url = os.environ.get("OPENSEARCH_URL", "").rstrip("/")
        if not url:
            return EngineReport(name=self.name, status="skipped", error="Set OPENSEARCH_URL to enable.")
        try:
            import requests
        except Exception as exc:
            return EngineReport(name=self.name, status="skipped", error=f"requests not available: {exc}")

        self.requests = requests
        self.url = url
        self.docs_by_id = {doc.id: doc.text for doc in docs}
        self.index = os.environ.get("OPENSEARCH_INDEX", "spectrum-prod-bench")
        auth = os.environ.get("OPENSEARCH_AUTH", "")
        self.auth = tuple(auth.split(":", 1)) if ":" in auth else None
        started = time.perf_counter()
        cpu_started = time.process_time()
        self.requests.delete(f"{self.url}/{self.index}", auth=self.auth, timeout=30)
        mapping = {"mappings": {"properties": {"text": {"type": "text"}, "title": {"type": "text"}}}}
        response = self.requests.put(f"{self.url}/{self.index}", json=mapping, auth=self.auth, timeout=30)
        response.raise_for_status()
        bulk_lines = []
        for doc in docs:
            bulk_lines.append(json.dumps({"index": {"_index": self.index, "_id": str(doc.id)}}))
            bulk_lines.append(json.dumps({"text": doc.text, "title": doc.title, "path": doc.path}))
        response = self.requests.post(
            f"{self.url}/_bulk",
            data="\n".join(bulk_lines) + "\n",
            headers={"Content-Type": "application/x-ndjson"},
            auth=self.auth,
            timeout=120,
        )
        response.raise_for_status()
        self.requests.post(f"{self.url}/{self.index}/_refresh", auth=self.auth, timeout=30).raise_for_status()
        return EngineReport(
            name=self.name,
            status="ok",
            build_seconds=round(time.perf_counter() - started, 4),
            build_cpu_seconds=round(time.process_time() - cpu_started, 4),
        )

    def search(self, query: str, top_k: int) -> list[int]:
        body = {
            "size": top_k,
            "query": {
                "multi_match": {
                    "query": query,
                    "fields": ["title^2", "text"],
                }
            },
        }
        response = self.requests.get(f"{self.url}/{self.index}/_search", json=body, auth=self.auth, timeout=30)
        response.raise_for_status()
        hits = response.json().get("hits", {}).get("hits", [])
        return [int(hit["_id"]) for hit in hits]

    def hydrate(self, doc_ids: list[int]) -> list[str]:
        return [self.docs_by_id[doc_id] for doc_id in doc_ids if doc_id in self.docs_by_id]


class ZoektCliEngine:
    name = "zoekt_cli"

    def build(self, docs: list[CorpusDoc], work_dir: Path) -> EngineReport:
        if not shutil.which("zoekt-index") or not shutil.which("zoekt-query"):
            return EngineReport(name=self.name, status="skipped", error="zoekt-index and zoekt-query not found on PATH.")
        started = time.perf_counter()
        cpu_started = time.process_time()
        self.source_dir = work_dir / "zoekt_source"
        self.index_dir = work_dir / "zoekt_index"
        self.docs_by_id = {doc.id: doc.text for doc in docs}
        self.source_dir.mkdir(parents=True, exist_ok=True)
        self.index_dir.mkdir(parents=True, exist_ok=True)
        self.path_to_id = {}
        for doc in docs:
            path = self.source_dir / f"doc_{doc.id:06d}.txt"
            path.write_text(doc.text, encoding="utf-8")
            self.path_to_id[path.name] = doc.id
        subprocess.run(
            ["zoekt-index", f"-index={self.index_dir}", str(self.source_dir)],
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        return EngineReport(
            name=self.name,
            status="ok",
            build_seconds=round(time.perf_counter() - started, 4),
            build_cpu_seconds=round(time.process_time() - cpu_started, 4),
            index_bytes=dir_size(self.index_dir),
        )

    def search(self, query: str, top_k: int) -> list[int]:
        proc = subprocess.run(
            ["zoekt-query", f"-index_dir={self.index_dir}", f"-limit={top_k}", query],
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        ids = []
        for line in proc.stdout.splitlines():
            for name, doc_id in self.path_to_id.items():
                if name in line and doc_id not in ids:
                    ids.append(doc_id)
                    break
        return ids[:top_k]

    def hydrate(self, doc_ids: list[int]) -> list[str]:
        return [self.docs_by_id[doc_id] for doc_id in doc_ids if doc_id in self.docs_by_id]


class PyseriniLuceneEngine:
    name = "lucene_pyserini_bm25"

    def build(self, docs: list[CorpusDoc], work_dir: Path) -> EngineReport:
        try:
            import pyserini  # noqa: F401
        except Exception as exc:
            return EngineReport(name=self.name, status="skipped", error=f"pyserini not available: {exc}")
        return EngineReport(
            name=self.name,
            status="skipped",
            error="Pyserini detected, but index build wiring is not implemented yet.",
        )

    def search(self, query: str, top_k: int) -> list[int]:
        return []

    def hydrate(self, doc_ids: list[int]) -> list[str]:
        return []


def make_engines(names: list[str], benchmark_dir: Path) -> list[SearchEngine]:
    factories = {
        "tfidf": lambda: TfidfEngine(),
        "raw_bm25": lambda: RawBM25Engine(),
        "spectrum": lambda: SpectrumBM25Engine(benchmark_dir),
        "spectrum_cached": lambda: SpectrumBM25Engine(
            benchmark_dir,
            name="spectrum_spb_bm25_cached",
            cache_hydration=True,
        ),
        "spectrum_fast": lambda: SpectrumBM25Engine(
            benchmark_dir,
            name="spectrum_spb_bm25_fast",
            fast_decode=True,
        ),
        "spectrum_fast_cached": lambda: SpectrumBM25Engine(
            benchmark_dir,
            name="spectrum_spb_bm25_fast_cached",
            cache_hydration=True,
            fast_decode=True,
        ),
        "spectrum_fast_ram": lambda: SpectrumBM25Engine(
            benchmark_dir,
            name="spectrum_spb_bm25_fast_ram",
            fast_decode=True,
            preload_specs=True,
        ),
        "spectrum_fast_ram_cached": lambda: SpectrumBM25Engine(
            benchmark_dir,
            name="spectrum_spb_bm25_fast_ram_cached",
            cache_hydration=True,
            fast_decode=True,
            preload_specs=True,
        ),
        "spectrum_snippet": lambda: SpectrumSnippetSidecarEngine(benchmark_dir),
        "spectrum_serving": lambda: SpectrumServingPipelineEngine(benchmark_dir),
        "spectrum_serving_ram": lambda: SpectrumServingPipelineEngine(
            benchmark_dir,
            name="spectrum_serving_pipeline_ram",
            preload_specs=True,
        ),
        "dense_lsa": lambda: DenseLsaEngine(),
        "faiss": lambda: FaissLsaEngine(),
        "chroma": lambda: ChromaLsaEngine(),
        "hybrid": lambda: HybridRrfEngine(SpectrumBM25Engine(benchmark_dir), DenseLsaEngine()),
        "opensearch": lambda: OpenSearchEngine(),
        "zoekt": lambda: ZoektCliEngine(),
        "lucene": lambda: PyseriniLuceneEngine(),
    }
    engines = []
    for name in names:
        if name not in factories:
            raise ValueError(f"Unknown engine '{name}'. Choices: {', '.join(sorted(factories))}")
        engines.append(factories[name]())
    return engines


def write_markdown(out_dir: Path, report: dict) -> None:
    top_k = report["settings"]["top_k"]
    lines = [
        "# Production Engine Benchmark",
        "",
        f"- Benchmark dir: `{report['settings']['benchmark_dir']}`",
        f"- Docs: {report['corpus']['docs']:,}",
        f"- Queries: {report['settings']['queries']:,}",
        f"- Hydrate limit: {report['settings']['hydrate_limit']}",
        "",
        "## Results",
        "",
        f"| Engine | Status | Hit@1 | MRR | Recall@{top_k} | Search ms | Hydrate ms | E2E ms | P95 E2E ms | CPU E2E ms | CPU util % | Build sec | Build CPU sec | Index bytes | Notes |",
        "|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|",
    ]
    for row in report["engines"]:
        metrics = row.get("metrics") or {}
        lines.append(
            f"| {row['name']} | {row['status']} | "
            f"{metrics.get('hit_at_1', '')} | {metrics.get('mrr', '')} | "
            f"{metrics.get(f'recall_at_{top_k}', '')} | {metrics.get('avg_query_ms', '')} | "
            f"{metrics.get('avg_hydrate_ms', '')} | {metrics.get('avg_end_to_end_ms', '')} | "
            f"{metrics.get('p95_end_to_end_ms', '')} | {metrics.get('avg_cpu_end_to_end_ms', '')} | "
            f"{metrics.get('cpu_utilization_pct', '')} | {row.get('build_seconds', '')} | "
            f"{row.get('build_cpu_seconds', '')} | "
            f"{row.get('index_bytes') or ''} | {row.get('error', '')} |"
        )
    lines.extend([
        "",
        "## Notes",
        "",
        "- `dense_lsa_numpy`, `faiss_lsa_flat`, and `chroma_lsa` use the same local LSA vectors so they measure vector-index plumbing, not frontier embedding quality.",
        "- `Search ms` is retrieval only; `E2E ms` is retrieval plus hydration of the returned top-k payloads.",
        "- Standard RAG engines hydrate from raw text already held in memory. Spectrum serving preloads `.spec` payload bytes into RAM, then byte-prism decodes selected payloads on demand.",
        "- `opensearch_bm25_http`, `zoekt_cli`, and `lucene_pyserini_bm25` are dependency-gated production adapters.",
        "- Use labelled human queries before treating these numbers as product-level retrieval claims.",
    ])
    (out_dir / "production_benchmark.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def run(args: argparse.Namespace) -> dict:
    benchmark_dir = Path(args.benchmark_dir).resolve()
    out_dir = Path(args.out_dir).resolve()
    reset_dir(out_dir)
    docs = load_corpus(benchmark_dir)
    queries = load_queries(benchmark_dir, Path(args.queries).resolve() if args.queries else None)
    if args.max_queries:
        queries = queries[: args.max_queries]
    engines = make_engines(args.engine, benchmark_dir)

    reports = []
    hydrate_limit = None if args.hydrate_limit < 0 else args.hydrate_limit
    for engine in engines:
        engine_dir = out_dir / engine.name
        engine_dir.mkdir(parents=True, exist_ok=True)
        result = evaluate_engine(engine, docs, queries, args.top_k, engine_dir, hydrate_limit)
        reports.append(result.__dict__)
        print(f"[prod-bench] {engine.name}: {result.status}")

    report = {
        "format": "spectrum-production-engine-benchmark-v1",
        "settings": {
            "benchmark_dir": str(benchmark_dir),
            "out_dir": str(out_dir),
            "queries": len(queries),
            "top_k": args.top_k,
            "hydrate_limit": hydrate_limit if hydrate_limit is not None else args.top_k,
            "engines": args.engine,
        },
        "corpus": {
            "docs": len(docs),
            "raw_bytes": sum(len(doc.text.encode("utf-8")) for doc in docs),
        },
        "engines": reports,
    }
    (out_dir / "production_benchmark.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    write_markdown(out_dir, report)
    print(f"[prod-bench] wrote {out_dir / 'production_benchmark.md'}")
    return report


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Benchmark Spectrum outputs against local and production retrieval engines."
    )
    parser.add_argument("--benchmark-dir", required=True, help="Existing rag/codebase_benchmark.py output directory.")
    parser.add_argument("--out-dir", default="benchmarks/generated/production_benchmark", help="Output directory.")
    parser.add_argument("--queries", default="", help="Optional query JSON path. Defaults to benchmark-dir/queries.json.")
    parser.add_argument("--max-queries", type=int, default=0, help="Limit query count for smoke runs; 0 means all.")
    parser.add_argument("--top-k", type=int, default=5, help="Recall@k and result count.")
    parser.add_argument(
        "--engine",
        action="append",
        default=[],
        help="Engine to run. Repeatable. Choices: tfidf, raw_bm25, spectrum, spectrum_cached, spectrum_fast, spectrum_fast_cached, spectrum_fast_ram, spectrum_fast_ram_cached, spectrum_snippet, spectrum_serving, spectrum_serving_ram, dense_lsa, faiss, chroma, hybrid, opensearch, zoekt, lucene.",
    )
    parser.add_argument(
        "--hydrate-limit",
        type=int,
        default=-1,
        help="Number of returned docs to hydrate; -1 hydrates top-k, 1 simulates final-result-only hydration, 0 measures search only.",
    )
    args = parser.parse_args()
    if not args.engine:
        args.engine = ["tfidf", "raw_bm25", "spectrum_serving", "dense_lsa", "hybrid"]
    run(args)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
