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
import time
from dataclasses import dataclass
from pathlib import Path

from rag.codebase_benchmark import decode_code_spec_bytes_fast
from rag.normalization import retrieval_token_ids
from rag.storage_benchmark import load_binary_postings, preferred_binary_postings_path


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


class SpectrumServingRetriever:
    def __init__(
        self,
        spectrum_store_dir: Path,
        snippets_by_id: dict[int, str],
    ):
        self.spectrum_store_dir = Path(spectrum_store_dir)
        docs_meta = json.loads((self.spectrum_store_dir / "docs.json").read_text(encoding="utf-8"))
        self.documents = docs_meta["documents"]
        self.docs_by_id = {int(doc["id"]): doc for doc in self.documents}
        self.spec_paths = {
            int(doc["id"]): self.spectrum_store_dir / doc["path"]
            for doc in self.documents
        }
        self.snippets_by_id = snippets_by_id
        self.bm25 = load_binary_postings(
            preferred_binary_postings_path(self.spectrum_store_dir),
            self.documents,
        )
        self.decoded_cache: dict[int, str] = {}

    @classmethod
    def from_codebase_benchmark(
        cls,
        benchmark_dir: Path,
        snippet_chars: int = 600,
        sidecar_path: Path | None = None,
    ) -> "SpectrumServingRetriever":
        benchmark_dir = Path(benchmark_dir)
        snippets_by_id = cls.load_or_build_snippets(
            benchmark_dir,
            snippet_chars=snippet_chars,
            sidecar_path=sidecar_path,
        )
        return cls(benchmark_dir / "spectrum_spec", snippets_by_id=snippets_by_id)

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

    def search(self, query: str, top_k: int = 5) -> list[SpectrumSearchResult]:
        doc_ids = self.bm25.search(
            retrieval_token_ids(query),
            top_k,
            max_df_ratio=0.9,
        )
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
                    snippet=self.snippets_by_id.get(doc_id, ""),
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
            text = decode_code_spec_bytes_fast(self.spec_paths[doc_id].read_bytes())
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
