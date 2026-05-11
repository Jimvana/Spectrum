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
import math
import re
import time
import zipfile
from collections import OrderedDict
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
DEFAULT_DECODE_CACHE_BYTES = 64 * 1024 * 1024
DEFAULT_MAX_AUTO_DECODE_SPEC_BYTES = 16 * 1024
DECODE_POLICY_NONE = "none"
DECODE_POLICY_AUTO = "auto"
DECODE_POLICY_EXACT = "exact"
DECODE_POLICIES = {DECODE_POLICY_NONE, DECODE_POLICY_AUTO, DECODE_POLICY_EXACT}
_CODEY_TERM_RE = re.compile(r"^(?=.*[A-Za-z])(?=.*[0-9])[A-Za-z0-9_]+$|[_./\\-]")
_ALIAS_GROUPS = (
    ("expire", "expires", "expired", "expiry", "links expire", "timed", "timestamp", "max_age", "age"),
    ("tampered", "messed with", "broken token", "bad signature", "bad data", "unsign", "signature"),
    ("setup entry point", "entry point", "cli", "command", "pyproject", "project.scripts", "entry_points", "console_scripts"),
    ("url", "urls", "link", "links", "safe", "base64", "url_safe", "urlsafe"),
)
_ALIAS_KEY_RE = re.compile(r"[A-Za-z0-9]+")


def _alias_key(value: str) -> tuple[str, ...]:
    return tuple(match.group(0).lower() for match in _ALIAS_KEY_RE.finditer(value))


_ALIAS_LOOKUP = {
    _alias_key(alias): tuple(group)
    for group in _ALIAS_GROUPS
    for alias in group
}
_TEST_INTENT_TERMS = {"test", "tests", "broken", "fails", "failure", "regression", "tampered"}
_IMPLEMENTATION_INTENT_TERMS = {
    "code",
    "function",
    "class",
    "implementation",
    "where",
    "sign",
    "verify",
    "url",
    "json",
}
_PACKAGING_INTENT_TERMS = {"setup", "entry", "point", "cli", "command", "pyproject", "script", "scripts"}
_GITHUB_INTENT_TERMS = {"github", "issue", "pull", "workflow", "ci", "template", "action", "actions"}
_RERANK_STOPWORDS = {
    "a",
    "an",
    "and",
    "for",
    "how",
    "if",
    "in",
    "is",
    "it",
    "of",
    "one",
    "or",
    "the",
    "then",
    "there",
    "they",
    "where",
    "with",
}


def _snippet_terms(query: str) -> list[str]:
    terms = [term.lower() for term in _SNIPPET_TERM_RE.findall(query)]
    return list(dict.fromkeys(term for term in terms if len(term) >= 2))


def expand_query_aliases(query: str) -> tuple[str, list[str]]:
    query_key = _alias_key(query)
    present_keys = {
        query_key[start:end]
        for start in range(len(query_key))
        for end in range(start + 1, len(query_key) + 1)
    }
    aliases: list[str] = []
    for trigger_key, group in _ALIAS_LOOKUP.items():
        if trigger_key and trigger_key in present_keys:
            aliases.extend(group)
    aliases = [
        alias
        for alias in dict.fromkeys(aliases)
        if _alias_key(alias) not in present_keys
    ]
    if not aliases:
        return query, []
    return f"{query} {' '.join(aliases)}", aliases


def _rerank_query_terms(query: str) -> set[str]:
    expanded_query, _aliases = expand_query_aliases(query)
    terms = _split_code_words(expanded_query) or _snippet_terms(expanded_query)
    return {term for term in terms if term not in _RERANK_STOPWORDS}


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
    intent_path_boost: float = 4.0
    metadata_penalty: float = 2.0


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
        intent_path_boost=profile.intent_path_boost,
        metadata_penalty=profile.metadata_penalty,
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
        return sum(self.score_breakdown(doc_id, query_terms).values())

    def score_breakdown(self, doc_id: int, query_terms: set[str]) -> dict[str, float]:
        fields = self.fields_by_id.get(doc_id)
        if not fields or not query_terms:
            return {}

        path_terms = fields["path"]
        contributions = {
            "path": self.profile.path_boost * len(query_terms & path_terms),
            "filename": self.profile.path_boost * 0.5 * len(query_terms & fields["filename"]),
            "identifier": self.profile.identifier_boost * len(query_terms & fields["identifier"]),
            "structure": self.profile.structure_boost * len(query_terms & fields["structure"]),
            "proximity": self.proximity_score(doc_id, query_terms),
        }
        if query_terms & _TEST_INTENT_TERMS and "tests" in path_terms:
            contributions["test_path_intent"] = self.profile.intent_path_boost
        if query_terms & _IMPLEMENTATION_INTENT_TERMS and "src" in path_terms:
            contributions["src_path_intent"] = self.profile.intent_path_boost
        if query_terms & _PACKAGING_INTENT_TERMS and (
            "pyproject" in path_terms or "setup" in path_terms or "scripts" in path_terms
        ):
            contributions["packaging_path_intent"] = self.profile.intent_path_boost
        if "github" in path_terms and not (query_terms & _GITHUB_INTENT_TERMS):
            contributions["metadata_penalty"] = -self.profile.metadata_penalty
        return contributions

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
        query_terms = _rerank_query_terms(query)
        if not query_terms:
            return ranked_doc_ids[:top_k]
        scored = []
        for rank, doc_id in enumerate(ranked_doc_ids, start=1):
            score = self.score(doc_id, query_terms) + base_weight * (len(ranked_doc_ids) - rank)
            scored.append((doc_id, score))
        scored.sort(key=lambda item: item[1], reverse=True)
        return [doc_id for doc_id, score in scored[:top_k]]

    def explain(self, doc_id: int, query: str) -> dict:
        expanded_query, aliases = expand_query_aliases(query)
        query_terms = _rerank_query_terms(expanded_query)
        fields = self.fields_by_id.get(doc_id, {})
        matched = {name: sorted(query_terms & values) for name, values in fields.items()}
        contributions = self.score_breakdown(doc_id, query_terms)
        return {
            "query_terms": sorted(query_terms),
            "matched_aliases": aliases,
            "matched_fields": matched,
            "rerank_contributions": {
                key: round(value, 4)
                for key, value in contributions.items()
                if value
            },
            "rerank_score": round(sum(contributions.values()), 4),
        }


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


def path_term_index(documents: list[dict]) -> dict[str, list[int]]:
    index: dict[str, list[int]] = {}
    for doc in documents:
        doc_id = int(doc["id"])
        source_path = str(doc.get("source_path", doc.get("title", "")))
        path = Path(source_path)
        path_text = " ".join((*path.parts, path.stem))
        for term in set(_split_code_words(path_text)):
            index.setdefault(term, []).append(doc_id)
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
    deferred: bool = False
    defer_reason: str = ""
    spec_bytes: int = 0
    payload_bytes: int = 0
    decode_policy: str = DECODE_POLICY_AUTO


@dataclass(frozen=True)
class CandidatePolicy:
    enabled: bool = DEFAULT_SELECTIVE_CANDIDATES
    max_df_ratio: float = DEFAULT_CANDIDATE_MAX_DF_RATIO
    rare_df_ratio: float = DEFAULT_CANDIDATE_RARE_DF_RATIO
    max_precandidates: int = DEFAULT_MAX_PRECANDIDATES
    min_strong_matches: float = DEFAULT_MIN_STRONG_MATCHES
    graded_weighting: bool = True
    min_candidate_weight: float = DEFAULT_MIN_CANDIDATE_WEIGHT
    fallback_to_full_search: bool = True
    title_fallback_max_candidates: int = DEFAULT_MAX_PRECANDIDATES


class SpectrumServingRetriever:
    def __init__(
        self,
        spectrum_store_dir: Path,
        snippets_by_id: dict[int, str],
        preload_specs: bool = True,
        snippet_chars: int = 2000,
        k1: float = DEFAULT_SERVING_K1,
        b: float = DEFAULT_SERVING_B,
        max_df_ratio: float | None = DEFAULT_SERVING_MAX_DF_RATIO,
        title_boost: float = DEFAULT_SERVING_TITLE_BOOST,
        rerank_profile: CodeRerankProfile | None = CodeRerankProfile(),
        candidate_policy: CandidatePolicy | None = CandidatePolicy(),
        full_decoder: Callable[[bytes], str] = decode_code_spec_bytes_native_or_fast,
        decode_cache_bytes: int = DEFAULT_DECODE_CACHE_BYTES,
        max_auto_decode_spec_bytes: int | None = DEFAULT_MAX_AUTO_DECODE_SPEC_BYTES,
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
        self.decode_cache_bytes = max(0, decode_cache_bytes)
        self.max_auto_decode_spec_bytes = max_auto_decode_spec_bytes
        self.title_index = title_token_index(self.documents) if title_boost else None
        self.path_term_index = path_term_index(self.documents)
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
        self.decoded_cache: OrderedDict[int, tuple[str, int]] = OrderedDict()
        self.decoded_cache_bytes = 0
        self.last_search_trace: dict | None = None

    @classmethod
    def from_codebase_benchmark(
        cls,
        benchmark_dir: Path,
        snippet_chars: int = 2000,
        sidecar_path: Path | None = None,
        preload_specs: bool = True,
        k1: float = DEFAULT_SERVING_K1,
        b: float = DEFAULT_SERVING_B,
        max_df_ratio: float | None = DEFAULT_SERVING_MAX_DF_RATIO,
        title_boost: float = DEFAULT_SERVING_TITLE_BOOST,
        rerank_profile: CodeRerankProfile | None = CodeRerankProfile(),
        candidate_policy: CandidatePolicy | None = CandidatePolicy(),
        full_decoder: Callable[[bytes], str] = decode_code_spec_bytes_native_or_fast,
        decode_cache_bytes: int = DEFAULT_DECODE_CACHE_BYTES,
        max_auto_decode_spec_bytes: int | None = DEFAULT_MAX_AUTO_DECODE_SPEC_BYTES,
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
            decode_cache_bytes=decode_cache_bytes,
            max_auto_decode_spec_bytes=max_auto_decode_spec_bytes,
        )

    @staticmethod
    def load_or_build_snippets(
        benchmark_dir: Path,
        snippet_chars: int = 2000,
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

    def _title_fallback_search(
        self,
        query: str,
        query_ids: list[int],
        token_stats: list[dict],
        token_weights: dict[int, float],
        candidate_limit: int,
    ) -> tuple[list[int], dict]:
        if not self.title_index and not self.path_term_index:
            return [], {
                "title_candidate_pool": 0,
                "title_generation_token_ids": [],
                "path_generation_terms": [],
            }

        stats_by_id = {int(row["token_id"]): row for row in token_stats}
        title_token_ids = [
            token_id for token_id in dict.fromkeys(query_ids)
            if (
                token_id in (self.title_index or {})
                and stats_by_id.get(token_id, {}).get("token_type") != "common"
                and any(ch.isalnum() for ch in _token_text(token_id))
            )
        ]
        title_token_ids.sort(
            key=lambda token_id: (
                len(self.title_index.get(token_id, ())),
                -token_weights.get(token_id, 0.0),
                token_id,
            )
        )

        max_candidates = max(candidate_limit, self.candidate_policy.title_fallback_max_candidates)
        scores: dict[int, float] = {}
        matched_counts: dict[int, int] = {}
        path_terms = [
            term for term in _rerank_query_terms(query)
            if term in self.path_term_index
        ]
        path_terms.sort(key=lambda term: (len(self.path_term_index.get(term, ())), term))
        for term in path_terms:
            if len(scores) >= max_candidates:
                break
            docs = self.path_term_index.get(term, ())
            if not docs:
                continue
            df = max(1, len(docs))
            term_idf = math.log((max(1, self.bm25.N) - df + 0.5) / (df + 0.5) + 1)
            remaining = max_candidates - len(scores)
            for doc_id in docs[:remaining]:
                scores[doc_id] = scores.get(doc_id, 0.0) + 1.0 + term_idf
                matched_counts[doc_id] = matched_counts.get(doc_id, 0) + 1

        for token_id in title_token_ids:
            if len(scores) >= max_candidates:
                break
            docs = self.title_index.get(token_id, ())
            if not docs:
                continue
            df = max(1, len(docs))
            title_idf = math.log((max(1, self.bm25.N) - df + 0.5) / (df + 0.5) + 1)
            # Common terms can be useful in path searches when combined with rarer terms,
            # but should not dominate fallback ranking on their own.
            token_score = max(token_weights.get(token_id, 0.0), title_idf / max(math.log(self.bm25.N + 1), 1.0))
            remaining = max_candidates - len(scores)
            for doc_id in docs[:remaining]:
                scores[doc_id] = scores.get(doc_id, 0.0) + token_score
                matched_counts[doc_id] = matched_counts.get(doc_id, 0) + 1

        if not scores:
            return [], {
                "title_candidate_pool": 0,
                "title_generation_token_ids": title_token_ids,
                "path_generation_terms": path_terms,
            }

        ranked = sorted(
            scores.items(),
            key=lambda item: (
                -matched_counts.get(item[0], 0),
                -item[1],
                item[0],
            ),
        )
        doc_ids = [doc_id for doc_id, _score in ranked[:candidate_limit]]
        return doc_ids, {
            "title_candidate_pool": len(scores),
            "title_generation_token_ids": title_token_ids,
            "path_generation_terms": path_terms,
        }

    def search_ids_with_trace(
        self,
        query: str,
        top_k: int = 5,
        include_raw_postings: bool = False,
    ) -> tuple[list[int], dict]:
        candidate_count = max(top_k, self.reranker.profile.candidates if self.reranker else top_k)
        expanded_query, aliases = expand_query_aliases(query)
        query_ids = retrieval_token_ids(expanded_query)
        token_stats = self.query_token_stats(expanded_query)
        token_weights: dict[int, float] = {}
        raw_postings_matches = (
            len(self.bm25.candidate_ids(query_ids))
            if include_raw_postings
            else None
        )
        retrieval_started = time.perf_counter()
        used_fallback = False
        fallback_strategy = ""
        title_fallback_trace: dict = {}
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
                strong_token_ids=self._strong_query_token_ids(expanded_query),
                graded_weighting=self.candidate_policy.graded_weighting,
                min_candidate_weight=self.candidate_policy.min_candidate_weight,
            )
            token_weights = {
                int(token_id): float(weight)
                for token_id, weight in trace.get("token_weights", {}).items()
            }
            if (
                self.candidate_policy.fallback_to_full_search
                and len(doc_ids) < top_k
            ):
                title_fallback_ids, title_fallback_trace = self._title_fallback_search(
                    expanded_query,
                    query_ids,
                    token_stats,
                    token_weights,
                    candidate_count,
                )
                if title_fallback_ids:
                    merged_doc_ids = list(dict.fromkeys([*doc_ids, *title_fallback_ids]))
                    doc_ids = merged_doc_ids[:candidate_count]
                    used_fallback = True
                    fallback_strategy = "title_index"
                else:
                    fallback_ids = self.bm25.search(
                        query_ids,
                        candidate_count,
                        max_df_ratio=self.max_df_ratio,
                        title_index=self.title_index,
                        title_boost=self.title_boost,
                    )
                    merged_doc_ids = list(dict.fromkeys([*doc_ids, *fallback_ids]))
                    doc_ids = merged_doc_ids[:candidate_count]
                    used_fallback = True
                    fallback_strategy = "full_bm25"
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
            doc_ids = self.reranker.rerank(doc_ids, expanded_query, top_k=top_k)
        else:
            doc_ids = doc_ids[:top_k]
        rerank_ms = (time.perf_counter() - rerank_started) * 1000
        trace.update({
            "raw_postings_matches": raw_postings_matches,
            "initial_postings_matches": trace.get("candidate_pool", raw_postings_matches),
            "reranker_in": len(doc_ids),
            "used_fallback_search": used_fallback,
            "fallback_strategy": fallback_strategy,
            **title_fallback_trace,
            "hydrated": 0,
            "retrieval_ms": retrieval_ms,
            "rerank_ms": rerank_ms,
            "token_stats": token_stats,
            "expanded_query": expanded_query,
            "matched_aliases": aliases,
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

    def _spec_size(self, doc_id: int) -> int:
        data = self.spec_bytes.get(doc_id)
        if data is not None:
            return len(data)
        if self.spectrum_pack_path is not None:
            with zipfile.ZipFile(self.spectrum_pack_path) as pack:
                return pack.getinfo(self.spec_members[doc_id]).file_size
        return self.spec_paths[doc_id].stat().st_size

    def _spec_data(self, doc_id: int) -> bytes:
        data = self.spec_bytes.get(doc_id)
        if data is not None:
            return data
        if self.spectrum_pack_path is not None:
            with zipfile.ZipFile(self.spectrum_pack_path) as pack:
                return pack.read(self.spec_members[doc_id])
        return self.spec_paths[doc_id].read_bytes()

    def _cache_get(self, doc_id: int) -> str | None:
        cached = self.decoded_cache.get(doc_id)
        if cached is None:
            return None
        text, size = cached
        self.decoded_cache.move_to_end(doc_id)
        return text

    def _cache_put(self, doc_id: int, text: str) -> None:
        size = len(text.encode("utf-8"))
        if self.decode_cache_bytes <= 0 or size > self.decode_cache_bytes:
            return
        existing = self.decoded_cache.pop(doc_id, None)
        if existing is not None:
            self.decoded_cache_bytes -= existing[1]
        self.decoded_cache[doc_id] = (text, size)
        self.decoded_cache_bytes += size
        while self.decoded_cache_bytes > self.decode_cache_bytes and self.decoded_cache:
            _old_id, (_old_text, old_size) = self.decoded_cache.popitem(last=False)
            self.decoded_cache_bytes -= old_size

    def decode(
        self,
        doc_id: int,
        *,
        force: bool = False,
        fallback_text: str = "",
        decode_policy: str = DECODE_POLICY_AUTO,
    ) -> SpectrumDecodedPayload:
        if force:
            decode_policy = DECODE_POLICY_EXACT
        if decode_policy not in DECODE_POLICIES:
            raise ValueError(f"Unknown decode policy: {decode_policy}")
        doc = self.docs_by_id[doc_id]
        started = time.perf_counter()
        spec_size = self._spec_size(doc_id)
        if decode_policy == DECODE_POLICY_NONE:
            text = fallback_text
            return SpectrumDecodedPayload(
                id=doc_id,
                title=str(doc.get("title", "")),
                source_path=str(doc.get("source_path", doc.get("title", ""))),
                text=text,
                cache_hit=False,
                decode_ms=(time.perf_counter() - started) * 1000,
                deferred=True,
                defer_reason="decode_policy_none",
                spec_bytes=spec_size,
                payload_bytes=len(text.encode("utf-8")),
                decode_policy=decode_policy,
            )
        cached_text = self._cache_get(doc_id)
        cached = cached_text is not None
        if cached_text is not None:
            text = cached_text
        else:
            if (
                decode_policy == DECODE_POLICY_AUTO
                and self.max_auto_decode_spec_bytes is not None
                and spec_size > self.max_auto_decode_spec_bytes
            ):
                text = fallback_text
                return SpectrumDecodedPayload(
                    id=doc_id,
                    title=str(doc.get("title", "")),
                    source_path=str(doc.get("source_path", doc.get("title", ""))),
                    text=text,
                    cache_hit=False,
                    decode_ms=(time.perf_counter() - started) * 1000,
                    deferred=True,
                    defer_reason="spec_payload_over_auto_decode_limit",
                    spec_bytes=spec_size,
                    payload_bytes=len(text.encode("utf-8")),
                    decode_policy=decode_policy,
                )
            data = self._spec_data(doc_id)
            text = self.full_decoder(data)
            self._cache_put(doc_id, text)
        return SpectrumDecodedPayload(
            id=doc_id,
            title=str(doc.get("title", "")),
            source_path=str(doc.get("source_path", doc.get("title", ""))),
            text=text,
            cache_hit=cached,
            decode_ms=(time.perf_counter() - started) * 1000,
            spec_bytes=spec_size,
            payload_bytes=len(text.encode("utf-8")),
            decode_policy=decode_policy,
        )

    def clear_cache(self) -> None:
        self.decoded_cache.clear()
        self.decoded_cache_bytes = 0
