"""
Spectrum RAG — Query Engine
============================
Encodes a query string as .spec token IDs (without writing any file to disk),
scores indexed documents using BM25, and returns ranked results — all without
decompressing or decoding a single indexed .spec file.

Usage
-----
    from rag.indexer import load_index
    from rag.query   import search

    index   = load_index("rag/index.bin")
    results = search("for loop over list append", index, top_k=5)
    for r in results:
        print(r["rank"], r["name"], r["score"])

BM25 parameters
---------------
k1 = 1.5   — term saturation: higher = more weight to high-frequency terms
b  = 0.75  — length normalisation: 1.0 = full, 0.0 = none
"""

import sys
import math
from pathlib import Path
from collections import Counter

# ── project root on path ───────────────────────────────────────────────────
_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_ROOT))

import dictionary as D
from spec_format.spec_encoder import tokens_to_ids, LANGUAGE_PYTHON
from encoder.encoder        import tokenise_source
from tokenizers.html_tokenizer import tokenise_html
from tokenizers.js_tokenizer   import tokenise_js
from tokenizers.css_tokenizer  import tokenise_css
from tokenizers.text_tokenizer import tokenize_text
from rag.normalization import retrieval_token_ids

# ─────────────────────────────────────────────────────────────────────────────
# Query encoding — text → dict token IDs (no file I/O)
# ─────────────────────────────────────────────────────────────────────────────

_LANG_TOKENIZERS = {
    0: tokenise_source,    # Python
    1: tokenise_html,      # HTML
    2: tokenise_js,        # JS
    3: tokenise_css,       # CSS
    4: tokenize_text,      # Plain text / English
}

_LANG_NAMES = {0: "Python", 1: "HTML", 2: "JS", 3: "CSS", 4: "Text"}

# Extensions the caller can pass as shorthand
_EXT_TO_LANG = {
    "py": 0, "python": 0,
    "html": 1, "htm": 1,
    "js": 2, "javascript": 2,
    "css": 3,
    "txt": 4, "text": 4, "en": 4,
}


def is_meaningful_retrieval_id(token_id: int) -> bool:
    token = D.SPEC_ID_TO_TOKEN.get(token_id, "")
    if not token or token.startswith("CTRL:"):
        return False
    if token.isspace():
        return False
    return any(ch.isalnum() for ch in token)


def encode_query(query_text: str, lang: int | str = 4, normalize: bool = False) -> list[int]:
    """
    Tokenise a query string using the appropriate Spectrum tokenizer, convert
    to token IDs, and return only dictionary token IDs (filters fallbacks).

    Parameters
    ----------
    query_text : str
        The raw query (e.g. a sentence, code snippet, or keyword list).
    lang : int or str
        Language ID (0–4) or a string alias ("py", "css", "txt", etc.).
        Defaults to 4 (plain text) — suitable for mixed or unknown queries.

    Returns
    -------
    list[int]
        Dictionary token IDs only (IDs < SPEC_ID_ASCII_BASE).
    """
    if isinstance(lang, str):
        lang = _EXT_TO_LANG.get(lang.lower(), 4)

    if lang == 4 and normalize:
        return [
            token_id for token_id in retrieval_token_ids(query_text)
            if is_meaningful_retrieval_id(token_id)
        ]

    tokenizer = _LANG_TOKENIZERS.get(lang, tokenize_text)
    tokens    = tokenizer(query_text)
    all_ids   = tokens_to_ids(tokens)

    ascii_base = D.SPEC_ID_ASCII_BASE
    return [
        i for i in all_ids
        if i < ascii_base and is_meaningful_retrieval_id(i)
    ]


# ─────────────────────────────────────────────────────────────────────────────
# BM25 scorer
# ─────────────────────────────────────────────────────────────────────────────

class BM25:
    """
    BM25 retrieval over a Spectrum RAG index.

    The index is the dict produced by rag.indexer.build_index / load_index.
    Document frequency vectors and the inverted index are loaded once on init.
    """

    def __init__(self, index: dict, k1: float = 1.5, b: float = 0.75):
        self.k1 = k1
        self.b  = b

        meta = index["meta"]
        self.N   = meta["total_docs"]
        self.avdl = meta["avg_doc_length"]

        self.docs = index["documents"]

        # Rebuild per-doc frequency dicts from the stored [[id, count]] lists
        self._freq: list[dict[int, int]] = [
            {int(tid): cnt for tid, cnt in doc["freq"]}
            for doc in self.docs
        ]
        self._lengths = [doc["token_count"] for doc in self.docs]

        # Inverted index: str key → list of doc_ids
        self._inv: dict[int, list[int]] = {
            int(k): v for k, v in index["inverted"].items()
        }

    def idf(self, token_id: int) -> float:
        """Robertson-Spärck Jones IDF (always ≥ 0)."""
        df = len(self._inv.get(token_id, []))
        return math.log((self.N - df + 0.5) / (df + 0.5) + 1)

    def score(self, doc_id: int, query_ids: list[int]) -> float:
        """BM25 score for a single document against a list of query token IDs."""
        freq   = self._freq[doc_id]
        dl     = self._lengths[doc_id]
        norm   = 1 - self.b + self.b * (dl / self.avdl) if self.avdl > 0 else 1.0
        total  = 0.0
        for tid in query_ids:
            tf  = freq.get(tid, 0)
            if tf == 0:
                continue
            idf = self.idf(tid)
            total += idf * (tf * (self.k1 + 1)) / (tf + self.k1 * norm)
        return total


# ─────────────────────────────────────────────────────────────────────────────
# Public search function
# ─────────────────────────────────────────────────────────────────────────────

def search(query_text: str,
           index: dict,
           top_k: int = 10,
           lang: int | str = 4,
           bm25: BM25 | None = None) -> list[dict]:
    """
    Encode a query and retrieve the top-k most relevant .spec documents.

    Parameters
    ----------
    query_text : str
        The query — a sentence, code snippet, keyword list, etc.
    index : dict
        The index produced by rag.indexer.
    top_k : int
        Number of results to return.
    lang : int or str
        Language hint for tokenising the query (default: "txt" / 4).
    bm25 : BM25, optional
        Pre-built BM25 instance (avoids re-constructing on repeated calls).

    Returns
    -------
    list of dicts, each containing:
        rank        : int   (1-based)
        doc_id      : int
        name        : str
        path        : str
        language    : str
        score       : float
        token_count : int
        orig_length : int
        matched_tokens : list[str]   (human-readable query tokens that matched)
    """
    scorer     = bm25 or BM25(index)
    query_ids  = encode_query(query_text, lang=lang, normalize=True)

    if not query_ids:
        print("[query] WARNING: query produced no dictionary token IDs.")
        return []

    # Candidate set: only docs that contain at least one query token
    candidates: set[int] = set()
    for tid in set(query_ids):
        candidates.update(scorer._inv.get(tid, []))

    if not candidates:
        print("[query] No matching documents found.")
        return []

    # Score candidates
    scored = [(doc_id, scorer.score(doc_id, query_ids))
              for doc_id in candidates]
    scored.sort(key=lambda x: x[1], reverse=True)

    # Build result list
    query_id_set = set(query_ids)
    results = []
    for rank, (doc_id, score) in enumerate(scored[:top_k], start=1):
        doc = index["documents"][doc_id]
        doc_freq = {int(tid): cnt for tid, cnt in doc["freq"]}

        matched = [
            D.SPEC_ID_TO_TOKEN[tid]
            for tid in query_id_set
            if tid in doc_freq and is_meaningful_retrieval_id(tid)
        ]

        results.append({
            "rank":          rank,
            "doc_id":        doc_id,
            "name":          doc["name"],
            "path":          doc["path"],
            "language":      _LANG_NAMES.get(doc["language_id"], "?"),
            "score":         round(score, 4),
            "token_count":   doc["token_count"],
            "orig_length":   doc["orig_length"],
            "matched_tokens": sorted(matched),
        })

    return results


def print_results(results: list[dict], query: str = "") -> None:
    """Pretty-print search results to stdout."""
    if query:
        print(f'\n── Query: "{query}" ──────────────────────────────────────')
    if not results:
        print("  (no results)")
        return
    print(f"  {'Rank':<5} {'Score':>8}  {'Name':<35} {'Lang':<7} {'Tokens':>8}")
    print("  " + "─" * 70)
    for r in results:
        print(f"  {r['rank']:<5} {r['score']:>8.4f}  "
              f"{r['name']:<35} {r['language']:<7} {r['token_count']:>8,}")
        if r["matched_tokens"]:
            preview = ", ".join(r["matched_tokens"][:8])
            if len(r["matched_tokens"]) > 8:
                preview += f" … (+{len(r['matched_tokens'])-8} more)"
            print(f"  {'':5}   matched: {preview}")
    print()


def print_results(results: list[dict], query: str = "") -> None:
    """Pretty-print search results to stdout using Windows-safe ASCII."""
    if query:
        print(f'\n-- Query: "{query}" {"-" * 38}')
    if not results:
        print("  (no results)")
        return
    print(f"  {'Rank':<5} {'Score':>8}  {'Name':<35} {'Lang':<7} {'Tokens':>8}")
    print("  " + "-" * 70)
    for r in results:
        print(f"  {r['rank']:<5} {r['score']:>8.4f}  "
              f"{r['name']:<35} {r['language']:<7} {r['token_count']:>8,}")
        if r["matched_tokens"]:
            preview = ", ".join(r["matched_tokens"][:8])
            if len(r["matched_tokens"]) > 8:
                preview += f" ... (+{len(r['matched_tokens'])-8} more)"
            print(f"  {'':5}   matched: {preview}")
    print()


# ─────────────────────────────────────────────────────────────────────────────
# CLI
# ─────────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import argparse
    from rag.indexer import load_index

    parser = argparse.ArgumentParser(
        description="Spectrum RAG Query — search .spec index without decompression")
    parser.add_argument("query",   help="Query string")
    parser.add_argument("--index", default="rag/index.bin",
                        help="Path to index file (default: rag/index.bin)")
    parser.add_argument("--top",   type=int, default=10,
                        help="Number of results (default: 10)")
    parser.add_argument("--lang",  default="txt",
                        help="Query language: py/html/js/css/txt (default: txt)")
    args = parser.parse_args()

    idx     = load_index(Path(_ROOT) / args.index)
    results = search(args.query, idx, top_k=args.top, lang=args.lang)
    print_results(results, query=args.query)
