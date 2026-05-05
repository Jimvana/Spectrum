#!/usr/bin/env python3
from __future__ import annotations

import contextlib
import io
import json
import os
import pickle
import shutil
import tempfile
import time
import webbrowser
from dataclasses import asdict, dataclass
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import unquote, urlparse

import numpy as np
from scipy import sparse


GUI_DIR = Path(__file__).resolve().parent
CLI_DIR = GUI_DIR.parent
REPO_ROOT = CLI_DIR.parent

import sys

for candidate in [REPO_ROOT, CLI_DIR]:
    if str(candidate) not in sys.path:
        sys.path.insert(0, str(candidate))

from rag.query import BM25, encode_query, search as spectrum_search
from spectrum_cli.main import (
    BenchDoc,
    SimpleBM25,
    build_raw_bm25_store,
    ensure_benchmark_pack,
    evaluate_raw,
    evaluate_spectrum,
    generate_benchmark_queries,
    is_pack,
    load_benchmark_docs_from_pack,
    load_index_from_pack,
    pack_has_index,
    percentile,
)
from rag.storage_benchmark import (
    binary_postings_format,
    dir_size,
    load_binary_postings,
    preferred_binary_postings_path,
)


@dataclass
class LoadedCorpus:
    target: str
    pack_path: str
    files: int
    raw_bytes: int
    spectrum_bytes: int
    raw_payload_bytes: int
    raw_index_bytes: int
    spectrum_payload_bytes: int
    spectrum_index_bytes: int
    raw_build_sec: float
    spectrum_build_sec: float


class GuiState:
    def __init__(self) -> None:
        self.tmp = tempfile.TemporaryDirectory(prefix="spectrum-gui-")
        self.tmp_path = Path(self.tmp.name)
        self.target: Path | None = None
        self.pack_path: Path | None = None
        self.docs: list[BenchDoc] = []
        self.docs_by_source: dict[str, BenchDoc] = {}
        self.raw_index: dict | None = None
        self.raw_bm25: SimpleBM25 | None = None
        self.raw_tfidf_store = None
        self.raw_backend = "Raw Text BM25 Baseline"
        self.spectrum_index: dict | None = None
        self.spectrum_bm25: BM25 | None = None
        self.legacy_spectrum_bm25 = None
        self.legacy_spectrum_docs: list[dict] | None = None
        self.legacy_spectrum_format = ""
        self.embedding_store: EmbeddingStore | None = None
        self.prebuilt_vector_store = None
        self.summary: LoadedCorpus | None = None


STATE = GuiState()


def quiet_call(func, *args, **kwargs):
    with contextlib.redirect_stdout(io.StringIO()):
        return func(*args, **kwargs)


def json_response(handler: BaseHTTPRequestHandler, status: int, payload: dict) -> None:
    body = json.dumps(payload, indent=2).encode("utf-8")
    handler.send_response(status)
    handler.send_header("Content-Type", "application/json; charset=utf-8")
    handler.send_header("Content-Length", str(len(body)))
    handler.end_headers()
    handler.wfile.write(body)


def error_response(handler: BaseHTTPRequestHandler, status: int, message: str) -> None:
    json_response(handler, status, {"error": message})


def read_json(handler: BaseHTTPRequestHandler) -> dict:
    length = int(handler.headers.get("Content-Length", "0"))
    if not length:
        return {}
    return json.loads(handler.rfile.read(length).decode("utf-8"))


def pack_storage_breakdown(pack_path: Path) -> tuple[int, int]:
    import zipfile

    payload = 0
    index = 0
    with zipfile.ZipFile(pack_path) as pack:
        for item in pack.infolist():
            if item.filename == "index.bin":
                index += item.file_size
            elif item.filename.startswith("files/"):
                payload += item.file_size
    return payload, index


def source_from_spectrum_path(path: str) -> str:
    normalized = path.replace("\\", "/")
    marker = "/files/"
    if marker in normalized:
        normalized = normalized.split(marker, 1)[1]
    elif normalized.startswith("files/"):
        normalized = normalized[len("files/") :]
    if normalized.endswith(".spec"):
        normalized = normalized[: -len(".spec")]
    return normalized


def snippet_for(doc: BenchDoc | None, query: str, max_len: int = 360) -> str:
    if doc is None:
        return ""
    text = " ".join(doc.text.replace("\r", "\n").split())
    if not text:
        return ""
    lower = text.lower()
    terms = [part.lower() for part in query.replace("_", " ").replace("-", " ").split() if len(part) > 2]
    hit = -1
    for term in terms:
        hit = lower.find(term)
        if hit >= 0:
            break
    if hit < 0:
        hit = 0
    start = max(0, hit - max_len // 3)
    end = min(len(text), start + max_len)
    prefix = "..." if start else ""
    suffix = "..." if end < len(text) else ""
    return f"{prefix}{text[start:end]}{suffix}"


def metric_delta(primary: float, baseline: float) -> float:
    return primary - baseline


class TfidfSearchStore:
    def __init__(self, docs: list[BenchDoc], store_dir: Path) -> None:
        self.docs = docs
        with (store_dir / "tfidf_vectorizer.pkl").open("rb") as handle:
            self.vectorizer = pickle.load(handle)
        self.matrix = sparse.load_npz(store_dir / "tfidf_matrix.npz")
        self.backend = "Raw Text TF-IDF"

    def search(self, query: str, top_k: int = 5) -> tuple[list[dict], float]:
        start = time.perf_counter()
        query_vec = self.vectorizer.transform([query])
        scores = (self.matrix @ query_vec.T).toarray().ravel()
        order = np.argsort(-scores)[:top_k]
        elapsed = (time.perf_counter() - start) * 1000
        results = []
        for rank, doc_idx in enumerate(order.tolist(), start=1):
            if scores[doc_idx] <= 0:
                continue
            doc = self.docs[doc_idx]
            results.append({
                "rank": rank,
                "doc_id": doc.id,
                "name": doc.name,
                "path": doc.path,
                "source_path": doc.path,
                "score": round(float(scores[doc_idx]), 4),
                "snippet": snippet_for(doc, query),
            })
        return results, elapsed


class PrebuiltVectorStore:
    def __init__(self, docs: list[BenchDoc], store_dir: Path) -> None:
        self.docs = docs
        meta_path = store_dir / "meta.json"
        self.meta = json.loads(meta_path.read_text(encoding="utf-8")) if meta_path.exists() else {}
        with (store_dir / "tfidf_vectorizer.pkl").open("rb") as handle:
            self.vectorizer = pickle.load(handle)
        with (store_dir / "svd.pkl").open("rb") as handle:
            self.svd = pickle.load(handle)
        self.vectors = np.load(store_dir / "vectors.npy")
        self.backend = self.meta.get("backend", f"Prebuilt vectors ({self.vectors.shape[1]} dims)")
        self.build_sec = float(self.meta.get("build_seconds") or 0.0)
        self.memory_bytes = dir_size(store_dir)

    def search(self, query: str, top_k: int = 5) -> tuple[list[dict], float]:
        start = time.perf_counter()
        query_matrix = self.vectorizer.transform([query])
        query_vec = self.svd.transform(query_matrix)
        norm = np.linalg.norm(query_vec, axis=1, keepdims=True)
        norm[norm == 0] = 1.0
        query_vec = (query_vec / norm).astype("float32")[0]
        scores = self.vectors @ query_vec
        order = np.argsort(-scores)[:top_k]
        elapsed = (time.perf_counter() - start) * 1000
        results = []
        for rank, doc_idx in enumerate(order.tolist(), start=1):
            doc = self.docs[doc_idx]
            results.append({
                "rank": rank,
                "doc_id": doc.id,
                "name": doc.name,
                "path": doc.path,
                "source_path": doc.path,
                "score": round(float(scores[doc_idx]), 4),
                "snippet": snippet_for(doc, query),
            })
        return results, elapsed


class EmbeddingStore:
    def __init__(self, docs: list[BenchDoc]) -> None:
        self.docs = docs
        self.backend = "not built"
        self.vectors: np.ndarray | None = None
        self._tokenizer = None
        self._model = None
        self._lsa_vectorizer = None
        self._lsa_svd = None
        self.build_sec = 0.0
        self.memory_bytes = 0
        self._build()

    def _texts(self) -> list[str]:
        texts = []
        for doc in self.docs:
            text = " ".join(doc.text.replace("\r", "\n").split())
            texts.append(f"{doc.path}\n{text[:6000]}")
        return texts

    def _build(self) -> None:
        start = time.perf_counter()
        texts = self._texts()
        backend = os.environ.get("SPECTRUM_EMBEDDING_BACKEND", "transformer").lower()
        if backend in {"lsa", "tfidf"}:
            self._build_lsa(texts)
            self.build_sec = time.perf_counter() - start
            self.memory_bytes = int(self.vectors.nbytes if self.vectors is not None else 0)
            return
        try:
            self._build_transformer(texts)
        except Exception as exc:
            print(f"[gui] Transformer embeddings unavailable, falling back to LSA vectors: {exc}")
            self._build_lsa(texts)
        self.build_sec = time.perf_counter() - start
        self.memory_bytes = int(self.vectors.nbytes if self.vectors is not None else 0)

    def _build_transformer(self, texts: list[str]) -> None:
        import torch
        from transformers import AutoModel, AutoTokenizer

        model_name = os.environ.get("SPECTRUM_EMBEDDING_MODEL", "sentence-transformers/all-MiniLM-L6-v2")
        self._tokenizer = AutoTokenizer.from_pretrained(model_name)
        self._model = AutoModel.from_pretrained(model_name)
        self._model.eval()
        vectors = []
        batch_size = int(os.environ.get("SPECTRUM_EMBEDDING_BATCH", "12"))
        with torch.no_grad():
            for offset in range(0, len(texts), batch_size):
                batch = texts[offset : offset + batch_size]
                encoded = self._tokenizer(
                    batch,
                    padding=True,
                    truncation=True,
                    max_length=256,
                    return_tensors="pt",
                )
                output = self._model(**encoded)
                mask = encoded["attention_mask"].unsqueeze(-1).expand(output.last_hidden_state.size()).float()
                summed = torch.sum(output.last_hidden_state * mask, dim=1)
                counts = torch.clamp(mask.sum(dim=1), min=1e-9)
                pooled = summed / counts
                normalized = torch.nn.functional.normalize(pooled, p=2, dim=1)
                vectors.append(normalized.cpu().numpy().astype("float32"))
        self.vectors = np.vstack(vectors)
        self.backend = f"Transformer embeddings ({model_name})"

    def _build_lsa(self, texts: list[str]) -> None:
        from sklearn.decomposition import TruncatedSVD
        from sklearn.feature_extraction.text import TfidfVectorizer
        from sklearn.preprocessing import normalize

        max_features = int(os.environ.get("SPECTRUM_LSA_FEATURES", "20000"))
        self._lsa_vectorizer = TfidfVectorizer(
            analyzer="word",
            token_pattern=r"(?u)\b[A-Za-z_][A-Za-z0-9_/-]{2,}\b",
            lowercase=True,
            max_features=max_features,
            ngram_range=(1, 2),
        )
        matrix = self._lsa_vectorizer.fit_transform(texts)
        if matrix.shape[0] < 2 or matrix.shape[1] < 2:
            dense = matrix.toarray().astype("float32")
            self.vectors = normalize(dense).astype("float32")
            self.backend = "Dense TF-IDF vectors"
            return
        dims = max(1, min(384, matrix.shape[0] - 1, matrix.shape[1] - 1))
        self._lsa_svd = TruncatedSVD(n_components=dims, random_state=7)
        dense = self._lsa_svd.fit_transform(matrix)
        self.vectors = normalize(dense).astype("float32")
        self.backend = f"LSA dense vectors ({dims} dims)"

    def _embed_query(self, query: str) -> np.ndarray:
        if self.vectors is None:
            raise RuntimeError("Embedding index is not built.")
        if self._tokenizer is not None and self._model is not None:
            import torch

            with torch.no_grad():
                encoded = self._tokenizer(
                    [query],
                    padding=True,
                    truncation=True,
                    max_length=256,
                    return_tensors="pt",
                )
                output = self._model(**encoded)
                mask = encoded["attention_mask"].unsqueeze(-1).expand(output.last_hidden_state.size()).float()
                pooled = torch.sum(output.last_hidden_state * mask, dim=1) / torch.clamp(mask.sum(dim=1), min=1e-9)
                normalized = torch.nn.functional.normalize(pooled, p=2, dim=1)
                return normalized.cpu().numpy().astype("float32")[0]
        if self._lsa_vectorizer is not None:
            matrix = self._lsa_vectorizer.transform([query])
            if self._lsa_svd is not None:
                dense = self._lsa_svd.transform(matrix)
            else:
                dense = matrix.toarray()
            norm = np.linalg.norm(dense, axis=1, keepdims=True)
            norm[norm == 0] = 1.0
            return (dense / norm).astype("float32")[0]
        raise RuntimeError("No embedding backend is available.")

    def search(self, query: str, top_k: int = 5) -> tuple[list[dict], float]:
        start = time.perf_counter()
        query_vec = self._embed_query(query)
        assert self.vectors is not None
        scores = self.vectors @ query_vec
        order = np.argsort(-scores)[:top_k]
        elapsed = (time.perf_counter() - start) * 1000
        results = []
        for rank, doc_idx in enumerate(order.tolist(), start=1):
            doc = self.docs[doc_idx]
            results.append(
                {
                    "rank": rank,
                    "doc_id": doc.id,
                    "name": doc.name,
                    "path": doc.path,
                    "source_path": doc.path,
                    "score": round(float(scores[doc_idx]), 4),
                    "snippet": snippet_for(doc, query),
                }
            )
        return results, elapsed


def load_corpus(target_text: str, include_all: bool = False) -> LoadedCorpus:
    target = Path(target_text).expanduser().resolve()
    if not target.exists():
        raise FileNotFoundError(f"Target not found: {target}")

    benchmark_summary = try_load_benchmark_store(target)
    if benchmark_summary is not None:
        return benchmark_summary

    STATE.target = target
    STATE.docs = []
    STATE.docs_by_source = {}
    STATE.raw_index = None
    STATE.raw_bm25 = None
    STATE.raw_tfidf_store = None
    STATE.raw_backend = "Raw Text BM25 Baseline"
    STATE.spectrum_index = None
    STATE.spectrum_bm25 = None
    STATE.legacy_spectrum_bm25 = None
    STATE.legacy_spectrum_docs = None
    STATE.legacy_spectrum_format = ""
    STATE.embedding_store = None
    STATE.prebuilt_vector_store = None
    STATE.summary = None

    work_dir = STATE.tmp_path / "loaded"
    if work_dir.exists():
        shutil.rmtree(work_dir)
    work_dir.mkdir(parents=True)

    start = time.perf_counter()
    pack_path = quiet_call(ensure_benchmark_pack, target, work_dir, include_all=include_all)
    spectrum_build_sec = time.perf_counter() - start
    if is_pack(target) and not pack_has_index(target):
        spectrum_build_sec = time.perf_counter() - start

    spectrum_index = quiet_call(load_index_from_pack, pack_path)
    docs = quiet_call(load_benchmark_docs_from_pack, pack_path)
    if not docs:
        raise ValueError("No documents could be decoded from the target.")

    raw_store_dir = STATE.tmp_path / "raw_bm25"
    if raw_store_dir.exists():
        shutil.rmtree(raw_store_dir)
    raw_index, raw_payload_bytes, raw_index_bytes, raw_build_sec = quiet_call(
        build_raw_bm25_store, docs, raw_store_dir
    )
    spectrum_payload_bytes, spectrum_index_bytes = pack_storage_breakdown(pack_path)

    STATE.pack_path = pack_path
    STATE.docs = docs
    STATE.docs_by_source = {doc.path.replace("\\", "/"): doc for doc in docs}
    STATE.raw_index = raw_index
    STATE.raw_bm25 = SimpleBM25(raw_index)
    STATE.raw_backend = "Raw Text BM25 Baseline"
    STATE.spectrum_index = spectrum_index
    STATE.spectrum_bm25 = BM25(spectrum_index)

    raw_bytes = sum(len(doc.text.encode("utf-8")) for doc in docs)
    summary = LoadedCorpus(
        target=str(target),
        pack_path=str(pack_path),
        files=len(docs),
        raw_bytes=raw_bytes,
        spectrum_bytes=pack_path.stat().st_size,
        raw_payload_bytes=raw_payload_bytes,
        raw_index_bytes=raw_index_bytes,
        spectrum_payload_bytes=spectrum_payload_bytes,
        spectrum_index_bytes=spectrum_index_bytes,
        raw_build_sec=raw_build_sec,
        spectrum_build_sec=spectrum_build_sec,
    )
    STATE.summary = summary
    return summary


def try_load_benchmark_store(target: Path) -> LoadedCorpus | None:
    spectrum_dir = target / "spectrum_spec"
    raw_dir = target / "conventional_tfidf"
    postings_path = preferred_binary_postings_path(spectrum_dir)
    if not (spectrum_dir / "docs.json").exists() or not postings_path.exists():
        return None
    if not (raw_dir / "chunks.jsonl").exists():
        raise FileNotFoundError(f"Benchmark folder has Spectrum data but no raw chunks: {raw_dir / 'chunks.jsonl'}")

    STATE.target = target
    STATE.pack_path = None
    STATE.docs = []
    STATE.docs_by_source = {}
    STATE.raw_index = None
    STATE.raw_bm25 = None
    STATE.raw_tfidf_store = None
    STATE.raw_backend = "Raw Text BM25 Baseline"
    STATE.spectrum_index = None
    STATE.spectrum_bm25 = None
    STATE.legacy_spectrum_bm25 = None
    STATE.legacy_spectrum_docs = None
    STATE.legacy_spectrum_format = ""
    STATE.embedding_store = None
    STATE.prebuilt_vector_store = None
    STATE.summary = None

    docs_meta = json.loads((spectrum_dir / "docs.json").read_text(encoding="utf-8"))
    spectrum_docs = docs_meta["documents"]
    spectrum_bm25 = load_binary_postings(postings_path, spectrum_docs)
    spectrum_format = binary_postings_format(postings_path)
    manifest_path = target / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8")) if manifest_path.exists() else {}

    docs: list[BenchDoc] = []
    with (raw_dir / "chunks.jsonl").open(encoding="utf-8") as handle:
        for line in handle:
            if not line.strip():
                continue
            row = json.loads(line)
            source_path = row.get("source_path") or row.get("path") or row.get("title") or f"doc_{row['id']}"
            docs.append(BenchDoc(int(row["id"]), Path(source_path).stem, source_path, row.get("text", "")))
    if not docs:
        raise ValueError("Benchmark folder has no raw chunks to search.")

    STATE.docs = docs
    STATE.docs_by_source = {doc.path.replace("\\", "/"): doc for doc in docs}
    if (raw_dir / "tfidf_vectorizer.pkl").exists() and (raw_dir / "tfidf_matrix.npz").exists():
        STATE.raw_tfidf_store = TfidfSearchStore(docs, raw_dir)
        STATE.raw_backend = STATE.raw_tfidf_store.backend
    vector_dir = target / "vector_db"
    if (vector_dir / "vectors.npy").exists() and (vector_dir / "tfidf_vectorizer.pkl").exists():
        STATE.prebuilt_vector_store = PrebuiltVectorStore(docs, vector_dir)
    STATE.legacy_spectrum_bm25 = spectrum_bm25
    STATE.legacy_spectrum_docs = spectrum_docs
    STATE.legacy_spectrum_format = spectrum_format

    report_path = target / "report.json"
    report = json.loads(report_path.read_text(encoding="utf-8")) if report_path.exists() else {}
    stores = report.get("stores", {})
    raw_bytes = int(report.get("corpus", {}).get("raw_bytes") or sum(len(doc.text.encode("utf-8")) for doc in docs))
    spectrum_store = stores.get("spectrum", {})
    conventional_store = stores.get("conventional", {})
    spectrum_components = spectrum_store.get("components", {})
    conventional_components = conventional_store.get("components", {})
    spectrum_payload_bytes = sum(
        item.stat().st_size
        for item in (spectrum_dir / "chunks").glob("*.spec")
    )
    spectrum_index_bytes = postings_path.stat().st_size + (spectrum_dir / "docs.json").stat().st_size
    spectrum_metadata_bytes = (spectrum_dir / "meta.json").stat().st_size if (spectrum_dir / "meta.json").exists() else 0
    spectrum_bytes = spectrum_payload_bytes + spectrum_index_bytes + spectrum_metadata_bytes
    raw_store_bytes = int(
        manifest.get("conventional_tfidf_bytes")
        or conventional_store.get("bytes")
        or sum(item.stat().st_size for item in raw_dir.rglob("*") if item.is_file())
    )

    summary = LoadedCorpus(
        target=str(target),
        pack_path=str(spectrum_dir),
        files=len(docs),
        raw_bytes=raw_bytes,
        spectrum_bytes=spectrum_bytes,
        raw_payload_bytes=raw_store_bytes,
        raw_index_bytes=0,
        spectrum_payload_bytes=spectrum_payload_bytes,
        spectrum_index_bytes=spectrum_index_bytes,
        raw_build_sec=float(conventional_store.get("build_seconds") or 0.0),
        spectrum_build_sec=float(spectrum_store.get("build_seconds") or 0.0),
    )
    STATE.summary = summary
    return summary


def ensure_loaded() -> None:
    if not STATE.summary:
        raise RuntimeError("Load a folder, .specpack, or benchmark folder first.")
    if STATE.spectrum_index is None and STATE.legacy_spectrum_bm25 is None:
        raise RuntimeError("Load a folder or .specpack first.")


def ensure_raw_bm25() -> SimpleBM25:
    ensure_loaded()
    if STATE.raw_bm25 is not None:
        return STATE.raw_bm25
    raw_store_dir = STATE.tmp_path / "raw_bm25"
    if raw_store_dir.exists():
        shutil.rmtree(raw_store_dir)
    raw_index, raw_payload_bytes, raw_index_bytes, raw_build_sec = quiet_call(
        build_raw_bm25_store, STATE.docs, raw_store_dir
    )
    STATE.raw_index = raw_index
    STATE.raw_bm25 = SimpleBM25(raw_index)
    if STATE.summary is not None:
        STATE.summary.raw_payload_bytes = raw_payload_bytes
        STATE.summary.raw_index_bytes = raw_index_bytes
        STATE.summary.raw_build_sec = raw_build_sec
    return STATE.raw_bm25


def search_raw_loaded(query: str, top_k: int) -> tuple[list[dict], float, str]:
    ensure_loaded()
    if STATE.raw_tfidf_store is not None:
        results, elapsed = STATE.raw_tfidf_store.search(query, top_k)
        return results, elapsed, STATE.raw_tfidf_store.backend
    raw_bm25 = ensure_raw_bm25()
    start = time.perf_counter()
    raw_results = raw_bm25.search(query, top_k=top_k)
    raw_ms = (time.perf_counter() - start) * 1000
    decorated_raw = []
    for rank, result in enumerate(raw_results, start=1):
        doc = STATE.docs_by_source.get(result["path"].replace("\\", "/"))
        item = dict(result)
        item["rank"] = rank
        item["source_path"] = result["path"]
        item["score"] = round(float(result["score"]), 4)
        item["snippet"] = snippet_for(doc, query)
        decorated_raw.append(item)
    return decorated_raw, raw_ms, STATE.raw_backend


def ensure_embedding_store():
    ensure_loaded()
    if STATE.prebuilt_vector_store is not None:
        return STATE.prebuilt_vector_store
    if STATE.embedding_store is None:
        STATE.embedding_store = EmbeddingStore(STATE.docs)
    return STATE.embedding_store


def search_loaded(query: str, top_k: int) -> dict:
    ensure_loaded()
    decorated_spectrum, spectrum_ms = search_spectrum_loaded(query, top_k)

    decorated_raw, raw_ms, raw_backend = search_raw_loaded(query, top_k)

    embedding_store = ensure_embedding_store()
    embedding_results, embedding_ms = embedding_store.search(query, top_k=top_k)

    return {
        "query": query,
        "top_k": top_k,
        "query_tokens": encode_query(query, lang="txt", normalize=True),
        "spectrum": {
            "backend": f"Spectrum .spec BM25 ({STATE.legacy_spectrum_format})" if STATE.legacy_spectrum_format else "Spectrum .spec BM25",
            "query_ms": spectrum_ms,
            "results": decorated_spectrum,
        },
        "raw": {"backend": raw_backend, "query_ms": raw_ms, "results": decorated_raw},
        "embedding": {
            "backend": embedding_store.backend,
            "build_sec": embedding_store.build_sec,
            "memory_bytes": embedding_store.memory_bytes,
            "query_ms": embedding_ms,
            "results": embedding_results,
        },
    }


def search_spectrum_loaded(query: str, top_k: int) -> tuple[list[dict], float]:
    if STATE.spectrum_index is not None:
        assert STATE.spectrum_bm25 is not None
        start = time.perf_counter()
        spectrum_results = spectrum_search(query, STATE.spectrum_index, top_k=top_k, lang="txt", bm25=STATE.spectrum_bm25)
        spectrum_ms = (time.perf_counter() - start) * 1000
        decorated = []
        for result in spectrum_results:
            source = source_from_spectrum_path(result.get("path", ""))
            doc = STATE.docs_by_source.get(source)
            item = dict(result)
            item["source_path"] = source
            item["snippet"] = snippet_for(doc, query)
            decorated.append(item)
        return decorated, spectrum_ms

    if STATE.legacy_spectrum_bm25 is None or STATE.legacy_spectrum_docs is None:
        raise RuntimeError("Spectrum index is not loaded.")
    query_ids = encode_query(query, lang="txt", normalize=True)
    start = time.perf_counter()
    doc_ids = STATE.legacy_spectrum_bm25.search(
        query_ids,
        top_k=top_k,
        max_df_ratio=0.9,
        title_boost=0.5,
    )
    if not doc_ids and query_ids:
        doc_ids = STATE.legacy_spectrum_bm25.search(
            query_ids,
            top_k=top_k,
            max_df_ratio=None,
            title_boost=0.5,
        )
    spectrum_ms = (time.perf_counter() - start) * 1000
    results = []
    for rank, doc_id in enumerate(doc_ids, start=1):
        meta = STATE.legacy_spectrum_docs[doc_id]
        source = meta.get("source_path") or meta.get("title") or meta.get("path")
        doc = STATE.docs_by_source.get(str(source).replace("\\", "/"))
        results.append(
            {
                "rank": rank,
                "doc_id": doc_id,
                "name": meta.get("title") or meta.get("name") or Path(str(source)).stem,
                "path": meta.get("path", ""),
                "source_path": source,
                "language": "Text",
                "score": round(float(STATE.legacy_spectrum_bm25.score(doc_id, query_ids)), 4),
                "token_count": meta.get("token_count", 0),
                "orig_length": meta.get("orig_length", 0),
                "matched_tokens": [],
                "snippet": snippet_for(doc, query),
            }
        )
    return results, spectrum_ms


def evaluate_embedding(store: EmbeddingStore, queries: list[dict], top_k: int) -> tuple[dict, list[int]]:
    ranks = []
    times = []
    for query in queries:
        results, elapsed = store.search(query["query"], top_k=top_k)
        times.append(elapsed)
        rank = 0
        for idx, result in enumerate(results, start=1):
            if result["source_path"] == query["expected_path"] or result["name"] == query["expected_name"]:
                rank = idx
                break
        ranks.append(rank)
    total = len(ranks) or 1
    return {
        "hit_at_1": sum(1 for rank in ranks if rank == 1) / total,
        "mrr": sum((1 / rank) for rank in ranks if rank) / total,
        "recall_at_5": sum(1 for rank in ranks if 1 <= rank <= 5) / total,
        "avg_query_ms": sum(times) / len(times) if times else 0.0,
        "p95_query_ms": percentile(times, 95),
    }, ranks


def evaluate_raw_loaded(queries: list[dict], top_k: int) -> tuple[dict, list[int], str]:
    if STATE.raw_tfidf_store is not None:
        ranks = []
        times = []
        for query in queries:
            results, elapsed = STATE.raw_tfidf_store.search(query["query"], top_k)
            times.append(elapsed)
            rank = 0
            for idx, result in enumerate(results, start=1):
                if result["source_path"] == query["expected_path"] or result["name"] == query["expected_name"]:
                    rank = idx
                    break
            ranks.append(rank)
        total = len(ranks) or 1
        return {
            "hit_at_1": sum(1 for rank in ranks if rank == 1) / total,
            "mrr": sum((1 / rank) for rank in ranks if rank) / total,
            "recall_at_5": sum(1 for rank in ranks if 1 <= rank <= 5) / total,
            "avg_query_ms": sum(times) / len(times) if times else 0.0,
            "p95_query_ms": percentile(times, 95),
        }, ranks, STATE.raw_tfidf_store.backend

    ensure_raw_bm25()
    assert STATE.raw_index is not None
    bm25 = SimpleBM25(STATE.raw_index)
    ranks = []
    times = []
    for query in queries:
        start = time.perf_counter()
        results = bm25.search(query["query"], top_k=top_k)
        times.append((time.perf_counter() - start) * 1000)
        rank = next((idx for idx, result in enumerate(results, start=1) if result["path"] == query["expected_path"]), 0)
        ranks.append(rank)
    return evaluate_raw(STATE.raw_index, queries, top_k), ranks, STATE.raw_backend


def benchmark_loaded(query_limit: int, top_k: int) -> dict:
    ensure_loaded()
    assert STATE.summary is not None

    queries = generate_benchmark_queries(STATE.docs, min(query_limit, len(STATE.docs)))
    if not queries:
        raise ValueError("Could not generate benchmark queries for this corpus.")

    raw_eval, raw_ranks, raw_backend = evaluate_raw_loaded(queries, top_k)
    if STATE.spectrum_index is not None:
        spectrum_eval = evaluate_spectrum(STATE.spectrum_index, queries, top_k)
    else:
        spectrum_eval, _legacy_ranks = evaluate_legacy_spectrum(queries, top_k)
    embedding_store = ensure_embedding_store()
    embedding_eval, embedding_ranks = evaluate_embedding(embedding_store, queries, top_k)

    per_query = []
    spectrum_bm25 = BM25(STATE.spectrum_index) if STATE.spectrum_index is not None else None
    for query_idx, item in enumerate(queries):
        query = item["query"]
        raw_rank = raw_ranks[query_idx]
        spectrum_rank = 0
        if STATE.spectrum_index is not None:
            assert spectrum_bm25 is not None
            spectrum_results = spectrum_search(query, STATE.spectrum_index, top_k=top_k, lang="txt", bm25=spectrum_bm25)
            for rank_idx, result in enumerate(spectrum_results, start=1):
                if source_from_spectrum_path(result.get("path", "")) == item["expected_path"]:
                    spectrum_rank = rank_idx
                    break
        else:
            spectrum_rank = _legacy_ranks[query_idx]
        per_query.append(
            {
                "query": query,
                "expected_path": item["expected_path"],
                "raw_rank": raw_rank,
                "spectrum_rank": spectrum_rank,
                "embedding_rank": embedding_ranks[query_idx],
            }
        )

    raw_total = STATE.summary.raw_payload_bytes + STATE.summary.raw_index_bytes
    spectrum_total = STATE.summary.spectrum_bytes
    return {
        "queries": len(queries),
        "top_k": top_k,
        "summary": asdict(STATE.summary),
        "raw": {
            "backend": raw_backend,
            "bytes": raw_total,
            "ratio_vs_raw_text": raw_total / STATE.summary.raw_bytes if STATE.summary.raw_bytes else 0,
            **raw_eval,
        },
        "spectrum": {
            "bytes": spectrum_total,
            "ratio_vs_raw_text": spectrum_total / STATE.summary.raw_bytes if STATE.summary.raw_bytes else 0,
            **spectrum_eval,
        },
        "embedding": {
            "backend": embedding_store.backend,
            "bytes": embedding_store.memory_bytes,
            "build_sec": embedding_store.build_sec,
            **embedding_eval,
        },
        "delta": {
            "hit_at_1": metric_delta(spectrum_eval["hit_at_1"], raw_eval["hit_at_1"]),
            "mrr": metric_delta(spectrum_eval["mrr"], raw_eval["mrr"]),
            "recall_at_5": metric_delta(spectrum_eval["recall_at_5"], raw_eval["recall_at_5"]),
            "avg_query_ms": metric_delta(spectrum_eval["avg_query_ms"], raw_eval["avg_query_ms"]),
            "bytes": spectrum_total - raw_total,
        },
        "per_query": per_query,
    }


def evaluate_legacy_spectrum(queries: list[dict], top_k: int) -> tuple[dict, list[int]]:
    assert STATE.legacy_spectrum_bm25 is not None
    assert STATE.legacy_spectrum_docs is not None
    ranks = []
    times = []
    for query in queries:
        query_ids = encode_query(query["query"], lang="txt", normalize=True)
        start = time.perf_counter()
        doc_ids = STATE.legacy_spectrum_bm25.search(query_ids, top_k=top_k, max_df_ratio=0.9, title_boost=0.5)
        times.append((time.perf_counter() - start) * 1000)
        rank = 0
        for idx, doc_id in enumerate(doc_ids, start=1):
            meta = STATE.legacy_spectrum_docs[doc_id]
            source = meta.get("source_path") or meta.get("title") or ""
            if source == query["expected_path"] or meta.get("name") == query["expected_name"]:
                rank = idx
                break
        ranks.append(rank)
    total = len(ranks) or 1
    return {
        "hit_at_1": sum(1 for rank in ranks if rank == 1) / total,
        "mrr": sum((1 / rank) for rank in ranks if rank) / total,
        "recall_at_5": sum(1 for rank in ranks if 1 <= rank <= 5) / total,
        "avg_query_ms": sum(times) / len(times) if times else 0.0,
        "p95_query_ms": percentile(times, 95),
    }, ranks


class SpectrumGuiHandler(BaseHTTPRequestHandler):
    server_version = "SpectrumGui/0.1"

    def log_message(self, fmt: str, *args) -> None:
        print(f"[gui] {self.address_string()} - {fmt % args}")

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        path = unquote(parsed.path)
        if path == "/api/state":
            json_response(self, HTTPStatus.OK, {"loaded": STATE.summary is not None, "summary": asdict(STATE.summary) if STATE.summary else None})
            return

        if path == "/":
            path = "/index.html"
        file_path = (GUI_DIR / path.lstrip("/")).resolve()
        if not str(file_path).startswith(str(GUI_DIR)) or not file_path.exists() or not file_path.is_file():
            error_response(self, HTTPStatus.NOT_FOUND, "Not found")
            return

        content_type = "text/html; charset=utf-8"
        if file_path.suffix == ".css":
            content_type = "text/css; charset=utf-8"
        elif file_path.suffix == ".js":
            content_type = "application/javascript; charset=utf-8"
        body = file_path.read_bytes()
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_POST(self) -> None:
        try:
            payload = read_json(self)
            parsed = urlparse(self.path)
            if parsed.path == "/api/load":
                summary = load_corpus(str(payload.get("path", "")), bool(payload.get("includeAll", False)))
                json_response(self, HTTPStatus.OK, {"summary": asdict(summary)})
                return
            if parsed.path == "/api/search":
                query = str(payload.get("query", "")).strip()
                if not query:
                    raise ValueError("Query is required.")
                top_k = max(1, min(25, int(payload.get("topK", 5))))
                json_response(self, HTTPStatus.OK, search_loaded(query, top_k))
                return
            if parsed.path == "/api/benchmark":
                queries = max(1, min(500, int(payload.get("queries", 60))))
                top_k = max(1, min(25, int(payload.get("topK", 5))))
                json_response(self, HTTPStatus.OK, benchmark_loaded(queries, top_k))
                return
            error_response(self, HTTPStatus.NOT_FOUND, "Not found")
        except Exception as exc:
            error_response(self, HTTPStatus.BAD_REQUEST, str(exc))


def run(host: str = "127.0.0.1", port: int = 8765, open_browser: bool = False) -> None:
    server = ThreadingHTTPServer((host, port), SpectrumGuiHandler)
    url = f"http://{host}:{server.server_port}"
    print(f"Spectrum GUI running at {url}")
    print("Press Ctrl+C to stop.")
    if open_browser:
        webbrowser.open(url)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopping Spectrum GUI.")
    finally:
        server.server_close()


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Run the Spectrum local GUI")
    parser.add_argument("--host", default=os.environ.get("SPEC_GUI_HOST", "127.0.0.1"))
    parser.add_argument("--port", type=int, default=int(os.environ.get("SPEC_GUI_PORT", "8765")))
    parser.add_argument("--open", action="store_true", help="Open the GUI in the default browser")
    args = parser.parse_args()
    run(host=args.host, port=args.port, open_browser=args.open)
