"""
Standard Spectrum serving retriever.

The serving flow is:

1. Search Spectrum token postings.
2. Return path/title/snippet sidecars immediately.
3. Decode full `.spec` payloads only when selected.
4. Cache decoded payloads for repeat access.

This module deliberately keeps snippet serving separate from full lossless
decode. Snippets are the fast result-list path; `.spec` decode is the exact
payload path.
"""

from __future__ import annotations

import json
import re
import time
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

import dictionary as D
from rag.native_decoder import decode_code_spec_bytes_native_or_fast
from rag.normalization import retrieval_token_ids
from rag.storage_benchmark import (
    load_binary_postings,
    load_binary_postings_bytes,
    preferred_binary_postings_path,
)

_SNIPPET_TERM_RE = re.compile(r"[A-Za-z0-9_]{2,}")
_IDENT_RE = re.compile(r"[A-Za-z_][A-Za-z0-9_]{1,}")
_SPLIT_RE = re.compile(r"[_\-.\\/]+|(?<=[a-z0-9])(?=[A-Z])|(?<=[A-Z])(?=[A-Z][a-z])")
_FUNCTION_RE = re.compile(
    r"\b(?:def|function|func|fn|class|interface|type|struct|enum|const|let|var|export\s+(?:default\s+)?)\s+([A-Za-z_][A-Za-z0-9_]*)"
)
_IMPORT_RE = re.compile(r"\b(?:import|from|require)\b[^\"'\n]*[\"']([^\"']+)[\"']")
DEFAULT_SERVING_K1 = 1.2
DEFAULT_SERVING_B = 0.75
DEFAULT_SERVING_MAX_DF_RATIO = None
DEFAULT_SERVING_TITLE_BOOST = 1.0
DEFAULT_RERANK_CANDIDATES = 50
DEFAULT_IDENTIFIER_BOOST = 0.9
DEFAULT_PATH_BOOST = 1.2
DEFAULT_STRUCTURE_BOOST = 1.5
DEFAULT_PROXIMITY_BOOST = 0.6
DEFAULT_SELECTIVE_CANDIDATES = True
DEFAULT_CANDIDATE_MAX_DF_RATIO = 0.10
DEFAULT_CANDIDATE_RARE_DF_RATIO = 0.05
DEFAULT_MAX_PRECANDIDATES = 2000
DEFAULT_MIN_STRONG_MATCHES = 0.35
DEFAULT_MIN_CANDIDATE_WEIGHT = 0.05
_CODEY_TERM_RE = re.compile(r"^(?=.*[A-Za-z])(?=.*[0-9])[A-Za-z0-9_]+$|[_./\\-]")


def _snippet_terms(query: str) -> list[str]:
    terms = [term.lower() for term in _SNIPPET_TERM_RE.findall(query)]
    return list(dict.fromkeys(term for term in terms if len(term) >= 2))


def _split_code_words(value: str) -> list[str]:
    words: list[str] = []
    for ident in _IDENT_RE.findall(value):
        for part in _SPLIT_RE.split(ident):
            part = part.strip().lower()
            if len(part) >= 2 and not part.isdigit():
                words.append(part)
    return list(dict.fromkeys(words))


def _term_positions(text: str) -> dict[str, list[int]]:
    positions: dict[str, list[int]] = {}
    for idx, match in enumerate(_IDENT_RE.finditer(text)):
        for word in _split_code_words(match.group(0)):
            rows = positions.setdefault(word, [])
            if len(rows) < 8:
                rows.append(idx)
    return positions


def _field_tokens(document: dict, text: str) -> dict[str, set[str]]:
    source_path = str(document.get("source_path", document.get("title", "")))
    path = Path(source_path)
    path_text = " ".join((*path.parts, path.stem))
    identifier_words = _split_code_words(text)
    structural_text = " ".join(
        [match.group(1) for match in _FUNCTION_RE.finditer(text)]
        + [match.group(1) for match in _IMPORT_RE.finditer(text)]
    )
    return {
        "path": set(_split_code_words(path_text)),
        "filename": set(_split_code_words(path.stem)),
        "identifier": set(identifier_words),
        "structure": set(_split_code_words(structural_text)),
    }


def _token_text(token_id: int) -> str:
    return D.SPEC_ID_TO_TOKEN.get(token_id, f"<{token_id}>")


def _is_codey_query_token(token: str) -> bool:
    return bool(_CODEY_TERM_RE.search(token)) or token.isupper()


@dataclass(frozen=True)
class CodeRerankProfile:
    candidates: int = DEFAULT_RERANK_CANDIDATES
    identifier_boost: float = DEFAULT_IDENTIFIER_BOOST
    path_boost: float = DEFAULT_PATH_BOOST
    structure_boost: float = DEFAULT_STRUCTURE_BOOST
    proximity_boost: float = DEFAULT_PROXIMITY_BOOST


def code_rerank_profile(name: str, candidates: int | None = None) -> CodeRerankProfile | None:
    profiles = {
        "off": None,
        "none": None,
        "fast": CodeRerankProfile(candidates=10),
        "balanced": CodeRerankProfile(candidates=25),
        "accurate": CodeRerankProfile(candidates=50),
        "quality": CodeRerankProfile(candidates=50),
    }
    key = name.lower()
    if key not in profiles:
        raise ValueError(f"Unknown code rerank profile: {name}")
    profile = profiles[key]
    if candidates is None:
        return profile
    if candidates <= 0:
        return None
    if profile is None:
        return CodeRerankProfile(candidates=candidates)
    return CodeRerankProfile(
        candidates=candidates,
        identifier_boost=profile.identifier_boost,
        path_boost=profile.path_boost,
        structure_boost=profile.structure_boost,
        proximity_boost=profile.proximity_boost,
    )


class CodeSignalReranker:
    def __init__(
        self,
        documents: list[dict],
        text_by_id: dict[int, str],
        profile: CodeRerankProfile = CodeRerankProfile(),
    ):
        self.profile = profile
        self.fields_by_id: dict[int, dict[str, set[str]]] = {}
        self.positions_by_id: dict[int, dict[str, list[int]]] = {}
        for doc in documents:
            doc_id = int(doc["id"])
            text = text_by_id.get(doc_id, "")
            self.fields_by_id[doc_id] = _field_tokens(doc, text)
            self.positions_by_id[doc_id] = _term_positions(text)

    def score(self, doc_id: int, query_terms: set[str]) -> float:
        fields = self.fields_by_id.get(doc_id)
        if not fields or not query_terms:
            return 0.0

        score = 0.0
        score += self.profile.path_boost * len(query_terms & fields["path"])
        score += self.profile.path_boost * 0.5 * len(query_terms & fields["filename"])
        score += self.profile.identifier_boost * len(query_terms & fields["identifier"])
        score += self.profile.structure_boost * len(query_terms & fields["structure"])
        score += self.proximity_score(doc_id, query_terms)
        return score

    def proximity_score(self, doc_id: int, query_terms: set[str]) -> float:
        positions = self.positions_by_id.get(doc_id, {})
        matched_positions = [
            pos
            for term in query_terms
            for pos in positions.get(term, ())
        ]
        if len(matched_positions) < 2:
            return 0.0
        matched_positions.sort()
        best_span = min(
            matched_positions[idx + 1] - matched_positions[idx]
            for idx in range(len(matched_positions) - 1)
        )
        if best_span <= 3:
            return self.profile.proximity_boost
        if best_span <= 12:
            return self.profile.proximity_boost * 0.5
        return 0.0

    def rerank(
        self,
        ranked_doc_ids: list[int],
        query: str,
        base_weight: float = 0.01,
        top_k: int = 5,
    ) -> list[int]:
        query_terms = set(_split_code_words(query) or _snippet_terms(query))
        if not query_terms:
            return ranked_doc_ids[:top_k]
        scored = []
        for rank, doc_id in enumerate(ranked_doc_ids, start=1):
            score = self.score(doc_id, query_terms) + base_weight * (len(ranked_doc_ids) - rank)
            scored.append((doc_id, score))
        scored.sort(key=lambda item: item[1], reverse=True)
        return [doc_id for doc_id, score in scored[:top_k]]


def windowed_snippet(text: str, query: str, limit: int) -> str:
    if limit <= 0:
        return ""
    text = text.strip()
    if len(text) <= limit:
        return text

    lowered = text.lower()
    positions = []
    for term in _snippet_terms(query):
        pos = lowered.find(term)
        if pos >= 0:
            positions.append(pos)
    if positions:
        start = max(0, min(positions) - limit // 3)
    else:
        start = 0

    end = min(len(text), start + limit)
    if end - start < limit:
        start = max(0, end - limit)
    prefix = "..." if start > 0 else ""
    suffix = "..." if end < len(text) else ""
    body_limit = max(0, limit - len(prefix) - len(suffix))
    snippet = text[start:end].strip()[:body_limit].strip()
    return prefix + snippet + suffix


def title_token_index(documents: list[dict]) -> dict[int, list[int]]:
    index: dict[int, list[int]] = {}
    for doc in documents:
        doc_id = int(doc["id"])
        title = str(doc.get("title", ""))
        source_path = str(doc.get("source_path", ""))
        for token_id in set(retrieval_token_ids(f"{title} {source_path}")):
            index.setdefault(token_id, []).append(doc_id)
    return index


@dataclass(frozen=True)
class SpectrumSearchResult:
    id: int
    title: str
    source_path: str
    score_rank: int
    snippet: str


@dataclass(frozen=True)
class SpectrumDecodedPayload:
    id: int
    title: str
    source_path: str
    text: str
    cache_hit: bool
    decode_ms: float


@dataclass(frozen=True)
class CandidatePolicy:
    enabled: bool = DEFAULT_SELECTIVE_CANDIDATES
    max_df_ratio: float = DEFAULT_CANDIDATE_MAX_DF_RATIO
    rare_df_ratio: float = DEFAULT_CANDIDATE_RARE_DF_RATIO
    max_precandidates: int = DEFAULT_MAX_PRECANDIDATES
    min_strong_matches: float = DEFAULT_MIN_STRONG_MATCHES
    graded_weighting: bool = True
    min_candidate_weight: float = DEFAULT_MIN_CANDIDATE_WEIGHT


class SpectrumServingRetriever:
    def __init__(
        self,
        spectrum_store_dir: Path,
        snippets_by_id: dict[int, str],
        preload_specs: bool = True,
        snippet_chars: int = 600,
        k1: float = DEFAULT_SERVING_K1,
        b: float = DEFAULT_SERVING_B,
        max_df_ratio: float | None = DEFAULT_SERVING_MAX_DF_RATIO,
        title_boost: float = DEFAULT_SERVING_TITLE_BOOST,
        rerank_profile: CodeRerankProfile | None = CodeRerankProfile(),
        candidate_policy: CandidatePolicy | None = CandidatePolicy(),
        full_decoder: Callable[[bytes], str] = decode_code_spec_bytes_native_or_fast,
    ):
        self.spectrum_store_dir = Path(spectrum_store_dir)
        self.spectrum_pack_path: Path | None = (
            self.spectrum_store_dir
            if self.spectrum_store_dir.is_file() and self.spectrum_store_dir.suffix.lower() == ".specpack"
            else None
        )
        if self.spectrum_pack_path is not None:
            with zipfile.ZipFile(self.spectrum_pack_path) as pack:
                docs_meta = json.loads(pack.read("docs.json").decode("utf-8"))
                index_bytes = pack.read("index.bin")
        else:
            docs_meta = json.loads((self.spectrum_store_dir / "docs.json").read_text(encoding="utf-8"))
            index_bytes = None
        self.documents = docs_meta["documents"]
        self.docs_by_id = {int(doc["id"]): doc for doc in self.documents}
        self.spec_paths = {
            int(doc["id"]): self.spectrum_store_dir / doc["path"]
            for doc in self.documents
        }
        self.spec_members = {
            int(doc["id"]): str(doc["path"]).replace("\\", "/")
            for doc in self.documents
        }
        self.spec_bytes: dict[int, bytes] = {}
        if preload_specs:
            if self.spectrum_pack_path is not None:
                with zipfile.ZipFile(self.spectrum_pack_path) as pack:
                    self.spec_bytes = {
                        doc_id: pack.read(member)
                        for doc_id, member in self.spec_members.items()
                    }
            else:
                self.spec_bytes = {
                    doc_id: path.read_bytes()
                    for doc_id, path in self.spec_paths.items()
                }
        self.snippets_by_id = snippets_by_id
        self.snippet_chars = snippet_chars
        self.max_df_ratio = max_df_ratio
        self.title_boost = title_boost
        self.candidate_policy = candidate_policy
        self.full_decoder = full_decoder
        self.title_index = title_token_index(self.documents) if title_boost else None
        self.reranker = (
            CodeSignalReranker(self.documents, snippets_by_id, rerank_profile)
            if rerank_profile and rerank_profile.candidates > 0
            else None
        )
        if index_bytes is not None:
            self.bm25 = load_binary_postings_bytes(
                index_bytes,
                self.documents,
                source_name=f"{self.spectrum_pack_path}#index.bin",
                k1=k1,
                b=b,
            )
        else:
            self.bm25 = load_binary_postings(
                preferred_binary_postings_path(self.spectrum_store_dir),
                self.documents,
                k1=k1,
                b=b,
            )
        self.decoded_cache: dict[int, str] = {}
        self.last_search_trace: dict | None = None

    @classmethod
    def from_codebase_benchmark(
        cls,
        benchmark_dir: Path,
        snippet_chars: int = 600,
        sidecar_path: Path | None = None,
        preload_specs: bool = True,
        k1: float = DEFAULT_SERVING_K1,
        b: float = DEFAULT_SERVING_B,
        max_df_ratio: float | None = DEFAULT_SERVING_MAX_DF_RATIO,
        title_boost: float = DEFAULT_SERVING_TITLE_BOOST,
        rerank_profile: CodeRerankProfile | None = CodeRerankProfile(),
        candidate_policy: CandidatePolicy | None = CandidatePolicy(),
        full_decoder: Callable[[bytes], str] = decode_code_spec_bytes_native_or_fast,
    ) -> "SpectrumServingRetriever":
        benchmark_dir = Path(benchmark_dir)
        snippets_by_id = cls.load_or_build_snippets(
            benchmark_dir,
            snippet_chars=snippet_chars,
            sidecar_path=sidecar_path,
        )
        spectrum_store = benchmark_dir / "spectrum.specpack"
        if not spectrum_store.exists():
            spectrum_store = benchmark_dir / "spectrum_spec"
        return cls(
            spectrum_store,
            snippets_by_id=snippets_by_id,
            preload_specs=preload_specs,
            snippet_chars=snippet_chars,
            k1=k1,
            b=b,
            max_df_ratio=max_df_ratio,
            title_boost=title_boost,
            rerank_profile=rerank_profile,
            candidate_policy=candidate_policy,
            full_decoder=full_decoder,
        )

    @staticmethod
    def load_or_build_snippets(
        benchmark_dir: Path,
        snippet_chars: int = 600,
        sidecar_path: Path | None = None,
    ) -> dict[int, str]:
        benchmark_dir = Path(benchmark_dir)
        if sidecar_path and sidecar_path.exists():
            rows = json.loads(sidecar_path.read_text(encoding="utf-8"))
            return {int(key): value for key, value in rows.items()}

        snippets: dict[int, str] = {}
        chunks_path = benchmark_dir / "conventional_tfidf" / "chunks.jsonl"
        with chunks_path.open(encoding="utf-8") as handle:
            for line in handle:
                if not line.strip():
                    continue
                row = json.loads(line)
                snippets[int(row["id"])] = str(row["text"])[:snippet_chars]

        if sidecar_path:
            sidecar_path.parent.mkdir(parents=True, exist_ok=True)
            sidecar_path.write_text(
                json.dumps(snippets, ensure_ascii=False, separators=(",", ":")),
                encoding="utf-8",
            )
        return snippets

    def query_token_stats(self, query: str) -> list[dict]:
        policy = self.candidate_policy or CandidatePolicy()
        rows = []
        for stat in self.bm25.token_stats(retrieval_token_ids(query)):
            token_id = int(stat["token_id"])
            token = _token_text(token_id)
            df_ratio = float(stat["df_ratio"])
            if stat["df"] <= 0:
                token_type = "missing"
            elif df_ratio <= policy.rare_df_ratio:
                token_type = "rare"
            elif df_ratio > policy.max_df_ratio:
                token_type = "common"
            elif _is_codey_query_token(token) or (
                self.title_index is not None and token_id in self.title_index
            ):
                token_type = "identifier/path"
            else:
                token_type = "text"
            rows.append({
                "token_id": token_id,
                "token": token,
                "document_frequency": int(stat["df"]),
                "df_ratio": df_ratio,
                "postings_length": int(stat["postings_length"]),
                "token_type": token_type,
            })
        return rows

    def _strong_query_token_ids(self, query: str) -> set[int]:
        strong_ids: set[int] = set()
        for row in self.query_token_stats(query):
            if row["token_type"] in {"rare", "identifier/path"}:
                strong_ids.add(int(row["token_id"]))
        return strong_ids

    def search_ids_with_trace(
        self,
        query: str,
        top_k: int = 5,
        include_raw_postings: bool = False,
    ) -> tuple[list[int], dict]:
        candidate_count = max(top_k, self.reranker.profile.candidates if self.reranker else top_k)
        query_ids = retrieval_token_ids(query)
        token_stats = self.query_token_stats(query)
        raw_postings_matches = (
            len(self.bm25.candidate_ids(query_ids))
            if include_raw_postings
            else None
        )
        retrieval_started = time.perf_counter()
        if self.candidate_policy and self.candidate_policy.enabled:
            doc_ids, trace = self.bm25.selective_search(
                query_ids,
                top_k=top_k,
                candidate_limit=candidate_count,
                max_candidate_df_ratio=self.candidate_policy.max_df_ratio,
                rare_df_ratio=self.candidate_policy.rare_df_ratio,
                max_precandidates=self.candidate_policy.max_precandidates,
                min_strong_matches=self.candidate_policy.min_strong_matches,
                title_index=self.title_index,
                title_boost=self.title_boost,
                strong_token_ids=self._strong_query_token_ids(query),
                graded_weighting=self.candidate_policy.graded_weighting,
                min_candidate_weight=self.candidate_policy.min_candidate_weight,
            )
        else:
            doc_ids = self.bm25.search(
                query_ids,
                candidate_count,
                max_df_ratio=self.max_df_ratio,
                title_index=self.title_index,
                title_boost=self.title_boost,
            )
            trace = {
                "candidate_pool": raw_postings_matches,
                "generation_token_ids": list(dict.fromkeys(query_ids)),
                "dropped_token_ids": [],
                "reranker_in": len(doc_ids),
            }
        retrieval_ms = (time.perf_counter() - retrieval_started) * 1000
        rerank_started = time.perf_counter()
        if self.reranker:
            doc_ids = self.reranker.rerank(doc_ids, query, top_k=top_k)
        else:
            doc_ids = doc_ids[:top_k]
        rerank_ms = (time.perf_counter() - rerank_started) * 1000
        trace.update({
            "raw_postings_matches": raw_postings_matches,
            "initial_postings_matches": trace.get("candidate_pool", raw_postings_matches),
            "reranker_in": trace.get("reranker_in", 0),
            "hydrated": 0,
            "retrieval_ms": retrieval_ms,
            "rerank_ms": rerank_ms,
            "token_stats": token_stats,
        })
        self.last_search_trace = trace
        return doc_ids, trace

    def search(self, query: str, top_k: int = 5) -> list[SpectrumSearchResult]:
        doc_ids, _trace = self.search_ids_with_trace(query, top_k=top_k)
        results = []
        for rank, doc_id in enumerate(doc_ids, start=1):
            doc = self.docs_by_id.get(doc_id)
            if doc is None:
                continue
            results.append(
                SpectrumSearchResult(
                    id=doc_id,
                    title=str(doc.get("title", "")),
                    source_path=str(doc.get("source_path", doc.get("title", ""))),
                    score_rank=rank,
                    snippet=windowed_snippet(
                        self.snippets_by_id.get(doc_id, ""),
                        query,
                        self.snippet_chars,
                    ),
                )
            )
        return results

    def decode(self, doc_id: int) -> SpectrumDecodedPayload:
        doc = self.docs_by_id[doc_id]
        started = time.perf_counter()
        cached = doc_id in self.decoded_cache
        if cached:
            text = self.decoded_cache[doc_id]
        else:
            data = self.spec_bytes.get(doc_id)
            if data is None:
                if self.spectrum_pack_path is not None:
                    with zipfile.ZipFile(self.spectrum_pack_path) as pack:
                        data = pack.read(self.spec_members[doc_id])
                else:
                    data = self.spec_paths[doc_id].read_bytes()
            text = self.full_decoder(data)
            self.decoded_cache[doc_id] = text
        return SpectrumDecodedPayload(
            id=doc_id,
            title=str(doc.get("title", "")),
            source_path=str(doc.get("source_path", doc.get("title", ""))),
            text=text,
            cache_hit=cached,
            decode_ms=(time.perf_counter() - started) * 1000,
        )

    def clear_cache(self) -> None:
        self.decoded_cache.clear()
