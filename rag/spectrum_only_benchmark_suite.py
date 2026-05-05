"""
Spectrum-only retrieval benchmark suite.

This suite repeats the Spectrum-only experiment on small, deliberately messy
corpora and mixed-language/file-type stress data. It compares:

- raw_text_bm25
- local_lsa_embeddings (TF-IDF + SVD dense cosine, local embedding proxy)
- spectrum_bm25
- spectrum_only_binary_cosine

The corpora and holdout query sets are defined in code so the run is
repeatable and not coupled to a single storage benchmark's generated queries.
"""

from __future__ import annotations

import argparse
import json
import math
import re
import struct
import sys
import time
import zlib
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from statistics import mean

_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_ROOT))

import dictionary as D
from rag.ranking_eval import RawTextBM25, SpectrumOnlySimilarity, raw_bm25_rank
from rag.query import encode_query
from rag.storage_benchmark import BinarySpectrumBM25, write_binary_postings
from spec_format.spec_decoder import HEADER_SIZE, ids_to_tokens, parse_header
from spec_format.spec_encoder import (
    FLAG_RLE,
    LANGUAGE_CSS,
    LANGUAGE_HTML,
    LANGUAGE_JAVA,
    LANGUAGE_JS,
    LANGUAGE_PHP,
    LANGUAGE_PYTHON,
    LANGUAGE_RUST,
    LANGUAGE_SQL,
    LANGUAGE_TEXT,
    LANGUAGE_TS,
    apply_rle_ids,
    build_header,
    tokens_to_ids,
)
from tokenizers.css_tokenizer import tokenise_css
from tokenizers.html_tokenizer import tokenise_html
from tokenizers.java_tokenizer import tokenise_java
from tokenizers.js_tokenizer import tokenise_js
from tokenizers.php_tokenizer import tokenise_php
from tokenizers.rust_tokenizer import tokenise_rust
from tokenizers.sql_tokenizer import tokenise_sql
from tokenizers.text_tokenizer import reconstruct_text, tokenize_text
from tokenizers.ts_tokenizer import tokenise_ts

try:
    import numpy as np
    from sklearn.decomposition import TruncatedSVD
    from sklearn.feature_extraction.text import TfidfVectorizer
    from sklearn.metrics.pairwise import cosine_similarity
except Exception as exc:  # pragma: no cover
    raise SystemExit(
        "This benchmark requires numpy and scikit-learn. "
        f"Import failed: {exc}"
    )


TOKENIZER_BY_LANG = {
    LANGUAGE_HTML: tokenise_html,
    LANGUAGE_JS: tokenise_js,
    LANGUAGE_CSS: tokenise_css,
    LANGUAGE_TEXT: tokenize_text,
    LANGUAGE_TS: tokenise_ts,
    LANGUAGE_SQL: tokenise_sql,
    LANGUAGE_RUST: tokenise_rust,
    LANGUAGE_PHP: tokenise_php,
    LANGUAGE_JAVA: tokenise_java,
}
WORD_RE = re.compile(r"[A-Za-z][A-Za-z0-9']+")


@dataclass(frozen=True)
class BenchDoc:
    id: int
    title: str
    text: str
    language_id: int = LANGUAGE_TEXT
    path: str = ""


@dataclass(frozen=True)
class QuerySet:
    name: str
    source: str
    queries: list[dict]


def messy_natural_docs() -> list[BenchDoc]:
    raw = [
        (
            "coffee_machine_error",
            "ops-notes/coffee_machine_error.txt",
            "Coffee machine keeps flashing E17 after the office move. "
            "Tried unplugging it, reseating the water tank, and clearing grounds. "
            "The fix was priming the pump from the maintenance menu; not a bean issue.",
        ),
        (
            "vpn_login_loop",
            "helpdesk/vpn_login_loop.md",
            "VPN auth loops on Okta after laptop sleep. User sees login accepted then bounced "
            "back to the sign-in page. Clearing the stale device certificate and renewing the "
            "wireguard profile stopped the loop.",
        ),
        (
            "invoice_csv_import",
            "finance/invoice_csv_import.md",
            "Messy CSV import: invoice rows arrive with semicolon delimiters, euro decimals, "
            "and stray quoted newlines. Normalise headers before upload; reject rows missing vendor_id.",
        ),
        (
            "staging_checkout_500",
            "incidents/staging_checkout_500.txt",
            "Checkout on staging throws HTTP 500 when discount code is blank. Stack trace points "
            "to coupon lookup returning None; prod is unaffected because the feature flag is off.",
        ),
        (
            "printer_duplex_jam",
            "facilities/printer_duplex_jam.txt",
            "The third floor printer jams only on duplex print jobs. Single-sided pages are fine. "
            "Replacing tray two rollers fixed the recurring paper feed issue.",
        ),
        (
            "meeting_room_echo",
            "av/meeting_room_echo.md",
            "Boardroom calls sound hollow with a nasty echo. The ceiling mic and camera speaker "
            "were both active. Disabling speaker tracking on the old bar removed feedback.",
        ),
        (
            "warehouse_scanner_sync",
            "warehouse/scanner_sync.txt",
            "Handheld scanners show synced but counts are missing in inventory. Battery swaps reset "
            "the local queue. Force-upload pending scans before replacing the pack.",
        ),
        (
            "customer_churn_notes",
            "sales/customer_churn_notes.md",
            "Customer says the dashboard is too slow and exports time out at month end. They care "
            "less about UI polish than reliable scheduled CSV delivery.",
        ),
        (
            "kitchen_fridge_alarm",
            "facilities/kitchen_fridge_alarm.txt",
            "Kitchen fridge alarm beeps every morning around 7am. Door seal is loose after cleaning; "
            "temperature is fine once the gasket is pressed back into place.",
        ),
        (
            "mobile_push_silent",
            "mobile/push_silent.md",
            "Push notifications arrive silently on Android 14. Payload has channel_id set to legacy. "
            "Create the channel before registering the token or alerts stay muted.",
        ),
    ]
    return [
        BenchDoc(i, title, text=f"{path}\n\n{text}", path=path)
        for i, (title, path, text) in enumerate(raw)
    ]


def messy_query_sets() -> list[QuerySet]:
    return [
        QuerySet(
            name="validation",
            source="hand-authored operational queries",
            queries=[
                {"query": "coffee maker e17 flashing after move", "relevant_ids": [0]},
                {"query": "vpn keeps sending user back to okta login", "relevant_ids": [1]},
                {"query": "csv invoice semicolon euro decimal import problem", "relevant_ids": [2]},
                {"query": "staging checkout error with empty coupon", "relevant_ids": [3]},
                {"query": "duplex printing paper jam tray rollers", "relevant_ids": [4]},
            ],
        ),
        QuerySet(
            name="holdout",
            source="separate paraphrase set, not generated from document titles",
            queries=[
                {"query": "espresso machine not beans needs pump primed", "relevant_ids": [0]},
                {"query": "laptop wakes then vpn sign in repeats forever", "relevant_ids": [1]},
                {"query": "finance upload breaks on weird quoted line breaks", "relevant_ids": [2]},
                {"query": "blank promo code crashes test checkout", "relevant_ids": [3]},
                {"query": "double sided jobs jam but normal print works", "relevant_ids": [4]},
                {"query": "conference room audio echo from microphone speaker", "relevant_ids": [5]},
                {"query": "inventory scanner says synced but counts missing", "relevant_ids": [6]},
                {"query": "client wants scheduled exports because dashboard slow", "relevant_ids": [7]},
                {"query": "fridge beeping each morning loose door seal", "relevant_ids": [8]},
                {"query": "android push alert muted because channel missing", "relevant_ids": [9]},
            ],
        ),
    ]


def noisy_forum_docs() -> list[BenchDoc]:
    raw = [
        (
            "battery_drain_thread",
            "forum/mobile/battery_drain.txt",
            "phone batt is cooked after the update lol. drops 40 percent by lunch, "
            "but usage screen says nothing wild. disabling always-on location for the weather widget helped.",
        ),
        (
            "router_dns_thread",
            "forum/network/router_dns.txt",
            "wifi is up but pages randomly say dns_probe_finished. reboot did nada. "
            "router had stale isp dns; switching to cloudflare fixed lookups.",
        ),
        (
            "game_save_corrupt",
            "forum/games/save_corrupt.txt",
            "save file loads to black screen after the dlc patch. old autosaves work. "
            "delete shader cache and verify game files before reinstalling.",
        ),
        (
            "plant_yellow_leaves",
            "forum/garden/yellow_leaves.txt",
            "monstera leaves going yellow at the edges, soil still wet days later. "
            "not enough drainage; repot with perlite and stop watering on a calendar.",
        ),
        (
            "train_delay_refund",
            "forum/travel/train_refund.txt",
            "train was 52 min late and app says no refund button. use delay repay form, "
            "attach ticket pdf, choose other disruption reason.",
        ),
        (
            "headphones_pairing",
            "forum/audio/headphones_pairing.txt",
            "buds connect to mac but not phone, keeps saying already paired. "
            "forget device on both, hold case button until amber flash, then pair phone first.",
        ),
        (
            "sourdough_flat_loaf",
            "forum/cooking/sourdough_flat.txt",
            "loaf spreads like a pancake, starter bubbles fine tho. likely overproofed and weak shaping. "
            "shorten bulk ferment and build more tension.",
        ),
        (
            "bank_card_declined",
            "forum/money/card_declined.txt",
            "card declined online only, tap payments fine. merchant uses 3ds challenge but popup blocked. "
            "allow bank verification window or use app approval.",
        ),
        (
            "window_condensation",
            "forum/home/window_condensation.txt",
            "bedroom windows soaked every morning. not a leak, humidity too high overnight. "
            "crack vent, run extractor after showers, move laundry drying.",
        ),
        (
            "bike_brake_rubbing",
            "forum/bikes/brake_rub.txt",
            "front disc brake does the shh shh noise after wheel went back on. "
            "loosen caliper, squeeze lever, tighten bolts evenly.",
        ),
    ]
    return [
        BenchDoc(i, title, text=f"{path}\n\n{text}", path=path)
        for i, (title, path, text) in enumerate(raw)
    ]


def noisy_forum_query_sets() -> list[QuerySet]:
    return [
        QuerySet(
            name="validation",
            source="informal natural-language support queries",
            queries=[
                {"query": "phone loses battery after update weather location", "relevant_ids": [0]},
                {"query": "wifi connected but dns errors on websites", "relevant_ids": [1]},
                {"query": "game black screen after dlc save load", "relevant_ids": [2]},
                {"query": "monstera yellow leaves wet soil drainage", "relevant_ids": [3]},
                {"query": "late train refund no button in app", "relevant_ids": [4]},
            ],
        ),
        QuerySet(
            name="holdout",
            source="noisy paraphrases with slang, typos, and omitted exact titles",
            queries=[
                {"query": "mobile battery cooked since os patch", "relevant_ids": [0]},
                {"query": "internet works then browser says dns probe thingy", "relevant_ids": [1]},
                {"query": "dlc broke my save black screen not reinstall", "relevant_ids": [2]},
                {"query": "houseplant yellow edges and soggy pot", "relevant_ids": [3]},
                {"query": "claim money back for delayed rail journey", "relevant_ids": [4]},
                {"query": "earbuds stuck paired to laptop wont connect phone", "relevant_ids": [5]},
                {"query": "bread dough collapses flat even active starter", "relevant_ids": [6]},
                {"query": "online card payment fails because verification popup", "relevant_ids": [7]},
                {"query": "water on inside bedroom glass every morning", "relevant_ids": [8]},
                {"query": "disc rotor scraping after putting wheel back", "relevant_ids": [9]},
            ],
        ),
    ]


def mixed_language_docs() -> list[BenchDoc]:
    samples = [
        (
            "python_retry_backoff",
            "services/retry_backoff.py",
            LANGUAGE_PYTHON,
            "import time\n\n"
            "def retry_with_backoff(client, payload):\n"
            "    for attempt in range(5):\n"
            "        try:\n"
            "            return client.send(payload)\n"
            "        except TimeoutError:\n"
            "            time.sleep(2 ** attempt)\n",
        ),
        (
            "javascript_cart_total",
            "web/cartTotal.js",
            LANGUAGE_JS,
            "export function cartTotal(items) {\n"
            "  return items.reduce((sum, item) => sum + item.price * item.quantity, 0);\n"
            "}\n",
        ),
        (
            "typescript_feature_flag",
            "app/featureFlag.ts",
            LANGUAGE_TS,
            "type FlagMap = Record<string, boolean>;\n"
            "export const isEnabled = (flags: FlagMap, key: string) => flags[key] === true;\n",
        ),
        (
            "css_print_layout",
            "styles/print.css",
            LANGUAGE_CSS,
            "@media print {\n  .sidebar { display: none; }\n  article { font-size: 11pt; }\n}\n",
        ),
        (
            "html_invoice_template",
            "templates/invoice.html",
            LANGUAGE_HTML,
            "<section class=\"invoice\"><h1>Invoice</h1><p data-vendor-id=\"\"></p></section>\n",
        ),
        (
            "sql_overdue_accounts",
            "sql/overdue_accounts.sql",
            LANGUAGE_SQL,
            "select account_id, due_date from invoices where paid_at is null and due_date < current_date;\n",
        ),
        (
            "rust_token_bucket",
            "src/token_bucket.rs",
            LANGUAGE_RUST,
            "pub struct TokenBucket { capacity: u32, remaining: u32 }\n"
            "impl TokenBucket { pub fn allow(&mut self) -> bool { self.remaining > 0 } }\n",
        ),
        (
            "java_email_validator",
            "src/main/EmailValidator.java",
            LANGUAGE_JAVA,
            "public final class EmailValidator {\n"
            "  public static boolean valid(String email) { return email.contains(\"@\"); }\n"
            "}\n",
        ),
        (
            "php_upload_limit",
            "public/upload.php",
            LANGUAGE_PHP,
            "<?php\nif ($_FILES['upload']['size'] > 10485760) { http_response_code(413); }\n",
        ),
        (
            "markdown_runbook_cache",
            "docs/cache-runbook.md",
            LANGUAGE_TEXT,
            "# Cache Runbook\n\nIf Redis memory is high, evict stale sessions before restarting workers.\n",
        ),
    ]
    return [
        BenchDoc(i, title, text=f"{path}\n\n{text}", language_id=lang, path=path)
        for i, (title, path, lang, text) in enumerate(samples)
    ]


def mixed_query_sets() -> list[QuerySet]:
    return [
        QuerySet(
            name="validation",
            source="file intent queries",
            queries=[
                {"query": "python timeout retry exponential backoff", "relevant_ids": [0]},
                {"query": "cart total reduce price quantity javascript", "relevant_ids": [1]},
                {"query": "typescript feature flag boolean map", "relevant_ids": [2]},
                {"query": "print stylesheet hide sidebar", "relevant_ids": [3]},
                {"query": "invoice html vendor id template", "relevant_ids": [4]},
            ],
        ),
        QuerySet(
            name="holdout",
            source="cross-file-type stress queries",
            queries=[
                {"query": "retry client send after timeout", "relevant_ids": [0]},
                {"query": "sum shopping basket item quantities", "relevant_ids": [1]},
                {"query": "check if named flag is enabled", "relevant_ids": [2]},
                {"query": "hide navigation when printing article", "relevant_ids": [3]},
                {"query": "markup for invoice vendor field", "relevant_ids": [4]},
                {"query": "find unpaid invoices past due date", "relevant_ids": [5]},
                {"query": "rust rate limiter remaining tokens", "relevant_ids": [6]},
                {"query": "java validate email contains at sign", "relevant_ids": [7]},
                {"query": "php reject upload over ten megabytes", "relevant_ids": [8]},
                {"query": "redis memory high evict stale sessions", "relevant_ids": [9]},
            ],
        ),
    ]


def tokenise_for_language(text: str, language_id: int) -> list[str]:
    tokenizer = TOKENIZER_BY_LANG.get(language_id)
    if tokenizer is not None:
        try:
            return tokenizer(text)
        except Exception:
            pass
    if language_id == LANGUAGE_PYTHON:
        from encoder.encoder import tokenise_source

        try:
            return tokenise_source(text)
        except Exception:
            pass
    return tokenize_text(text) if language_id == LANGUAGE_TEXT else list(text)


def decode_spec_bytes(data: bytes) -> str:
    meta = parse_header(data)
    raw_stream = zlib.decompress(data[HEADER_SIZE:])
    ids = list(struct.unpack(f"<{len(raw_stream) // 4}I", raw_stream))
    tokens = ids_to_tokens(ids)
    text = reconstruct_text(tokens) if meta["language_id"] == LANGUAGE_TEXT else "".join(tokens)
    encoded = text.encode("utf-8")
    if len(encoded) > meta["orig_length"]:
        text = encoded[: meta["orig_length"]].decode("utf-8", errors="replace")
    return text


def encode_doc(doc: BenchDoc) -> tuple[bytes, list[int]]:
    tokens = tokenise_for_language(doc.text, doc.language_id)
    raw_ids = tokens_to_ids(tokens)
    encoded_ids = apply_rle_ids(raw_ids)
    source_bytes = doc.text.encode("utf-8")
    body = zlib.compress(struct.pack(f"<{len(encoded_ids)}I", *encoded_ids), level=9)
    header = build_header(
        D.DICT_VERSION,
        len(source_bytes),
        sum(source_bytes) & 0xFFFF,
        FLAG_RLE,
        doc.language_id,
    )
    data = header + body
    if decode_spec_bytes(data) != doc.text:
        tokens = list(doc.text)
        raw_ids = tokens_to_ids(tokens)
        encoded_ids = apply_rle_ids(raw_ids)
        body = zlib.compress(struct.pack(f"<{len(encoded_ids)}I", *encoded_ids), level=9)
        data = header + body

    dict_ids = [token_id for token_id in raw_ids if token_id < D.SPEC_ID_ASCII_BASE]
    dict_ids.extend(retrieval_token_ids(f"{doc.path} {doc.title}"))
    return data, dict_ids


def retrieval_token_ids(text: str) -> list[int]:
    # Local wrapper keeps this benchmark independent of codebase-specific aliases.
    from rag.normalization import retrieval_token_ids as normalize

    return normalize(text)


class LocalLSAEmbeddings:
    def __init__(self, docs: list[BenchDoc]):
        self.docs = docs
        self.vectorizer = TfidfVectorizer(
            lowercase=True,
            stop_words="english",
            ngram_range=(1, 2),
            max_features=20_000,
            sublinear_tf=True,
        )
        tfidf = self.vectorizer.fit_transform([doc.text for doc in docs])
        dims = max(1, min(32, tfidf.shape[0] - 1, tfidf.shape[1] - 1))
        if dims < 2:
            self.matrix = tfidf.toarray()
            self.svd = None
        else:
            self.svd = TruncatedSVD(n_components=dims, random_state=7)
            self.matrix = self.svd.fit_transform(tfidf)
        norms = np.linalg.norm(self.matrix, axis=1, keepdims=True)
        self.matrix = self.matrix / np.maximum(norms, 1e-12)

    def rank(self, query: str, top_k: int) -> list[tuple[int, float]]:
        q = self.vectorizer.transform([query])
        qv = q.toarray() if self.svd is None else self.svd.transform(q)
        qv = qv / max(float(np.linalg.norm(qv)), 1e-12)
        scores = cosine_similarity(qv, self.matrix)[0]
        ranked = sorted(enumerate(scores), key=lambda item: item[1], reverse=True)
        return [(int(doc_id), float(score)) for doc_id, score in ranked[:top_k] if score > 0]


def build_spectrum(docs: list[BenchDoc], out_dir: Path) -> BinarySpectrumBM25:
    out_dir.mkdir(parents=True, exist_ok=True)
    chunk_dir = out_dir / "chunks"
    chunk_dir.mkdir(exist_ok=True)
    documents = []
    postings: dict[int, list[tuple[int, int]]] = {}
    total_tokens = 0
    for doc in docs:
        data, ids = encode_doc(doc)
        spec_path = chunk_dir / f"doc_{doc.id:04d}.spec"
        spec_path.write_bytes(data)
        freq = Counter(ids)
        total_tokens += len(ids)
        documents.append({
            "id": doc.id,
            "path": spec_path.relative_to(out_dir).as_posix(),
            "name": doc.title,
            "title": doc.title,
            "source_path": doc.path,
            "language_id": doc.language_id,
            "orig_length": len(doc.text.encode("utf-8")),
            "token_count": len(ids),
        })
        for token_id, count in freq.items():
            postings.setdefault(token_id, []).append((doc.id, count))
    avg_doc_length = total_tokens / len(documents) if documents else 0.0
    write_binary_postings(out_dir / "postings.bin", documents, postings, avg_doc_length)
    (out_dir / "docs.json").write_text(
        json.dumps({"documents": documents, "avg_doc_length": avg_doc_length}, indent=2),
        encoding="utf-8",
    )
    return BinarySpectrumBM25(documents, postings, avg_doc_length)


def percentile(values: list[float], pct: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    idx = min(len(ordered) - 1, math.ceil((pct / 100) * len(ordered)) - 1)
    return ordered[idx]


def summarize_ranks(queries: list[dict], ranker, top_k: int) -> tuple[dict, list[dict]]:
    hit1 = 0
    recall = 0
    rr = []
    latencies = []
    details = []
    for item in queries:
        relevant = set(item["relevant_ids"])
        started = time.perf_counter()
        ranked = ranker(item["query"])
        latencies.append((time.perf_counter() - started) * 1000)
        ids = [doc_id for doc_id, _score in ranked]
        rank = next((idx + 1 for idx, doc_id in enumerate(ids) if doc_id in relevant), None)
        if rank == 1:
            hit1 += 1
        if rank is not None:
            recall += 1
        rr.append(1 / rank if rank else 0.0)
        details.append({
            "query": item["query"],
            "relevant_ids": sorted(relevant),
            "rank": rank,
            "top": [{"doc_id": doc_id, "score": round(score, 4)} for doc_id, score in ranked],
        })
    total = max(1, len(queries))
    return {
        "hit_at_1": round(hit1 / total, 4),
        f"recall_at_{top_k}": round(recall / total, 4),
        "mrr": round(mean(rr) if rr else 0.0, 4),
        "avg_query_ms": round(mean(latencies) if latencies else 0.0, 4),
        "p95_query_ms": round(percentile(latencies, 95), 4),
    }, details


def spectrum_bm25_rank(bm25: BinarySpectrumBM25, query: str, top_k: int) -> list[tuple[int, float]]:
    query_ids = encode_query(query, lang="txt", normalize=True)
    if not query_ids:
        return []
    query_counts = Counter(query_ids)
    scores: dict[int, float] = {}
    for token_id, query_count in query_counts.items():
        rows = bm25.postings.get(token_id)
        if not rows:
            continue
        idf = bm25.idf(token_id)
        for doc_id, tf in rows:
            dl = bm25._lengths[doc_id]
            norm = 1 - bm25.b + bm25.b * (dl / bm25.avdl) if bm25.avdl > 0 else 1.0
            score = idf * (tf * (bm25.k1 + 1)) / (tf + bm25.k1 * norm)
            scores[doc_id] = scores.get(doc_id, 0.0) + score * query_count
    return sorted(scores.items(), key=lambda item: item[1], reverse=True)[:top_k]


def validate_queries(docs: list[BenchDoc], query_set: QuerySet) -> dict:
    doc_tokens = [set(token.lower() for token in WORD_RE.findall(doc.text)) for doc in docs]
    duplicate_count = len(query_set.queries) - len({row["query"].lower() for row in query_set.queries})
    high_overlap = []
    max_overlaps = []
    for row in query_set.queries:
        q_tokens = set(token.lower() for token in WORD_RE.findall(row["query"]))
        best = 0.0
        for doc_id in row["relevant_ids"]:
            union = q_tokens | doc_tokens[doc_id]
            overlap = len(q_tokens & doc_tokens[doc_id]) / len(union) if union else 0.0
            best = max(best, overlap)
        max_overlaps.append(best)
        if best >= 0.5:
            high_overlap.append(row["query"])
    return {
        "query_source": query_set.source,
        "queries": len(query_set.queries),
        "duplicate_queries": duplicate_count,
        "avg_relevant_doc_jaccard": round(mean(max_overlaps) if max_overlaps else 0.0, 4),
        "max_relevant_doc_jaccard": round(max(max_overlaps) if max_overlaps else 0.0, 4),
        "high_overlap_queries": high_overlap,
    }


def run_corpus(name: str, docs: list[BenchDoc], query_sets: list[QuerySet], out_dir: Path, top_k: int) -> dict:
    corpus_dir = out_dir / name
    corpus_dir.mkdir(parents=True, exist_ok=True)
    (corpus_dir / "docs.json").write_text(
        json.dumps([doc.__dict__ for doc in docs], indent=2),
        encoding="utf-8",
    )
    raw_bm25 = RawTextBM25([{"text": doc.text} for doc in docs])
    embeddings = LocalLSAEmbeddings(docs)
    bm25 = build_spectrum(docs, corpus_dir / "spectrum_spec")
    spectrum_only = SpectrumOnlySimilarity(bm25)

    report = {
        "documents": len(docs),
        "query_sets": {},
    }
    for query_set in query_sets:
        rows = {}
        details = {}
        rows["raw_text_bm25"], details["raw_text_bm25"] = summarize_ranks(
            query_set.queries,
            lambda query: raw_bm25_rank(raw_bm25, query, top_k),
            top_k,
        )
        rows["local_lsa_embeddings"], details["local_lsa_embeddings"] = summarize_ranks(
            query_set.queries,
            lambda query: embeddings.rank(query, top_k),
            top_k,
        )
        rows["spectrum_bm25"], details["spectrum_bm25"] = summarize_ranks(
            query_set.queries,
            lambda query: spectrum_bm25_rank(bm25, query, top_k),
            top_k,
        )
        rows["spectrum_only_binary_cosine"], details["spectrum_only_binary_cosine"] = summarize_ranks(
            query_set.queries,
            lambda query: spectrum_only.rank(encode_query(query, lang="txt", normalize=True), top_k),
            top_k,
        )
        report["query_sets"][query_set.name] = {
            "validation": validate_queries(docs, query_set),
            "summary": rows,
            "details": details,
        }
    return report


def write_markdown(path: Path, report: dict) -> None:
    top_k = report["settings"]["top_k"]
    lines = [
        "# Spectrum-Only Benchmark Suite",
        "",
        f"- Top-k: {top_k}",
        "- Embeddings row uses a local TF-IDF + SVD dense cosine proxy, not an external neural embedding service.",
        "",
    ]
    for corpus_name, corpus in report["corpora"].items():
        lines.extend([
            f"## {corpus_name}",
            "",
            f"- Documents: {corpus['documents']}",
            "",
        ])
        for set_name, query_set in corpus["query_sets"].items():
            validation = query_set["validation"]
            lines.extend([
                f"### {set_name}",
                "",
                f"- Query source: {validation['query_source']}",
                f"- Duplicate queries: {validation['duplicate_queries']}",
                f"- Avg relevant-doc lexical Jaccard: {validation['avg_relevant_doc_jaccard']:.3f}",
                "",
                f"| Variant | Hit@1 | MRR | Recall@{top_k} | Avg ms | P95 ms |",
                "|---|---:|---:|---:|---:|---:|",
            ])
            for variant, row in query_set["summary"].items():
                lines.append(
                    f"| {variant} | {row['hit_at_1']:.3f} | {row['mrr']:.3f} | "
                    f"{row[f'recall_at_{top_k}']:.3f} | {row['avg_query_ms']:.3f} | "
                    f"{row['p95_query_ms']:.3f} |"
                )
            lines.append("")
    path.write_text("\n".join(lines), encoding="utf-8")


def run(args: argparse.Namespace) -> dict:
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    report = {
        "format": "spectrum-only-benchmark-suite-v1",
        "settings": {"top_k": args.top_k},
        "corpora": {
            "messy_natural_language": run_corpus(
                "messy_natural_language",
                messy_natural_docs(),
                messy_query_sets(),
                out_dir,
                args.top_k,
            ),
            "noisy_forum_language": run_corpus(
                "noisy_forum_language",
                noisy_forum_docs(),
                noisy_forum_query_sets(),
                out_dir,
                args.top_k,
            ),
            "mixed_language_file_types": run_corpus(
                "mixed_language_file_types",
                mixed_language_docs(),
                mixed_query_sets(),
                out_dir,
                args.top_k,
            ),
        },
    }
    (out_dir / "benchmark_suite.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    write_markdown(out_dir / "benchmark_suite.md", report)
    print(f"[spectrum-only-suite] wrote {out_dir / 'benchmark_suite.md'}")
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description="Run Spectrum-only retrieval benchmark suite.")
    parser.add_argument("--out-dir", default="benchmarks/generated/spectrum_only_benchmark_suite")
    parser.add_argument("--top-k", type=int, default=5)
    args = parser.parse_args()
    run(args)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
