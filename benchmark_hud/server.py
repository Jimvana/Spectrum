from __future__ import annotations

import argparse
import json
import math
import mimetypes
import re
import shutil
import struct
import subprocess
import sys
import time
import uuid
import zlib
from collections import Counter
from dataclasses import asdict, dataclass
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from statistics import mean
from typing import Iterable
from urllib.parse import parse_qs, urlparse

APP_DIR = Path(__file__).resolve().parent
ROOT = APP_DIR.parent
RUNS_DIR = APP_DIR / "runs"

sys.path.insert(0, str(ROOT))

import dictionary as D
from encoder.encoder import tokenise_source
from rag.normalization import retrieval_token_ids
from rag.spectrum_serving import CodeSignalReranker, coderag_rerank_profile, expand_query_aliases
from spec_format.spec_encoder import (
    FLAG_RLE,
    LANGUAGE_C,
    LANGUAGE_CPP,
    LANGUAGE_CSHARP,
    LANGUAGE_CSS,
    LANGUAGE_GO,
    LANGUAGE_HTML,
    LANGUAGE_JAVA,
    LANGUAGE_JSON,
    LANGUAGE_JS,
    LANGUAGE_PHP,
    LANGUAGE_POWERSHELL,
    LANGUAGE_PYTHON,
    LANGUAGE_RUST,
    LANGUAGE_SHELL,
    LANGUAGE_SQL,
    LANGUAGE_TEXT,
    LANGUAGE_TOML,
    LANGUAGE_TS,
    LANGUAGE_XML,
    LANGUAGE_YAML,
    apply_rle_ids,
    build_header,
    tokens_to_ids,
)
from tokenizers.c_tokenizer import tokenise_c
from tokenizers.config_tokenizer import tokenise_config
from tokenizers.cpp_tokenizer import tokenise_cpp
from tokenizers.csharp_tokenizer import tokenise_csharp
from tokenizers.css_tokenizer import tokenise_css
from tokenizers.go_tokenizer import tokenise_go
from tokenizers.html_tokenizer import tokenise_html
from tokenizers.java_tokenizer import tokenise_java
from tokenizers.js_tokenizer import tokenise_js
from tokenizers.php_tokenizer import tokenise_php
from tokenizers.powershell_tokenizer import tokenise_powershell
from tokenizers.rust_tokenizer import tokenise_rust
from tokenizers.shell_tokenizer import tokenise_shell
from tokenizers.sql_tokenizer import tokenise_sql
from tokenizers.text_tokenizer import tokenize_text
from tokenizers.ts_tokenizer import tokenise_ts
from tokenizers.xml_tokenizer import tokenize_xml_compatible_source

try:
    import numpy as np
    from scipy import sparse
    from sklearn.decomposition import TruncatedSVD
    from sklearn.feature_extraction.text import TfidfVectorizer
    from sklearn.preprocessing import normalize

    ML_IMPORT_ERROR = ""
except Exception as exc:  # pragma: no cover - dependency-gated benchmark path
    np = None
    sparse = None
    TruncatedSVD = None
    TfidfVectorizer = None
    normalize = None
    ML_IMPORT_ERROR = str(exc)


LANG_BY_EXT = {
    ".py": LANGUAGE_PYTHON,
    ".html": LANGUAGE_HTML,
    ".htm": LANGUAGE_HTML,
    ".js": LANGUAGE_JS,
    ".mjs": LANGUAGE_JS,
    ".cjs": LANGUAGE_JS,
    ".css": LANGUAGE_CSS,
    ".md": LANGUAGE_TEXT,
    ".txt": LANGUAGE_TEXT,
    ".ts": LANGUAGE_TS,
    ".tsx": LANGUAGE_TS,
    ".sql": LANGUAGE_SQL,
    ".rs": LANGUAGE_RUST,
    ".php": LANGUAGE_PHP,
    ".phtml": LANGUAGE_PHP,
    ".xml": LANGUAGE_XML,
    ".java": LANGUAGE_JAVA,
    ".c": LANGUAGE_C,
    ".h": LANGUAGE_C,
    ".cpp": LANGUAGE_CPP,
    ".cc": LANGUAGE_CPP,
    ".cxx": LANGUAGE_CPP,
    ".hpp": LANGUAGE_CPP,
    ".hh": LANGUAGE_CPP,
    ".hxx": LANGUAGE_CPP,
    ".go": LANGUAGE_GO,
    ".cs": LANGUAGE_CSHARP,
    ".sh": LANGUAGE_SHELL,
    ".bash": LANGUAGE_SHELL,
    ".zsh": LANGUAGE_SHELL,
    ".ps1": LANGUAGE_POWERSHELL,
    ".psm1": LANGUAGE_POWERSHELL,
    ".psd1": LANGUAGE_POWERSHELL,
    ".json": LANGUAGE_JSON,
    ".yaml": LANGUAGE_YAML,
    ".yml": LANGUAGE_YAML,
    ".toml": LANGUAGE_TOML,
}

TOKENIZER_BY_LANG = {
    LANGUAGE_PYTHON: tokenise_source,
    LANGUAGE_HTML: tokenise_html,
    LANGUAGE_JS: tokenise_js,
    LANGUAGE_CSS: tokenise_css,
    LANGUAGE_TEXT: tokenize_text,
    LANGUAGE_TS: tokenise_ts,
    LANGUAGE_SQL: tokenise_sql,
    LANGUAGE_RUST: tokenise_rust,
    LANGUAGE_PHP: tokenise_php,
    LANGUAGE_XML: tokenize_xml_compatible_source,
    LANGUAGE_JAVA: tokenise_java,
    LANGUAGE_C: tokenise_c,
    LANGUAGE_CPP: tokenise_cpp,
    LANGUAGE_GO: tokenise_go,
    LANGUAGE_CSHARP: tokenise_csharp,
    LANGUAGE_SHELL: tokenise_shell,
    LANGUAGE_POWERSHELL: tokenise_powershell,
    LANGUAGE_JSON: tokenise_config,
    LANGUAGE_YAML: tokenise_config,
    LANGUAGE_TOML: tokenise_config,
}

LANG_NAMES = {
    LANGUAGE_PYTHON: "python",
    LANGUAGE_HTML: "html",
    LANGUAGE_JS: "javascript",
    LANGUAGE_CSS: "css",
    LANGUAGE_TEXT: "text",
    LANGUAGE_TS: "typescript",
    LANGUAGE_SQL: "sql",
    LANGUAGE_RUST: "rust",
    LANGUAGE_PHP: "php",
    LANGUAGE_XML: "xml",
    LANGUAGE_JAVA: "java",
    LANGUAGE_C: "c",
    LANGUAGE_CPP: "cpp",
    LANGUAGE_GO: "go",
    LANGUAGE_CSHARP: "csharp",
    LANGUAGE_SHELL: "shell",
    LANGUAGE_POWERSHELL: "powershell",
    LANGUAGE_JSON: "json",
    LANGUAGE_YAML: "yaml",
    LANGUAGE_TOML: "toml",
}

EXCLUDE_DIRS = {
    ".git",
    ".pytest_cache",
    ".mypy_cache",
    ".ruff_cache",
    ".venv",
    "__pycache__",
    "archive",
    "benchmark_hud",
    "deck_workspace",
    "external_repos",
    "node_modules",
    "output_images",
    "results",
    "spec compressed",
    "wiki_enwiki_dump",
    "wiki_enwiki_fullxml_1hr",
    "wiki_enwiki_fullxml_sample",
    "wiki_enwiki_raw_10pct",
    "wiki_enwiki_raw_sample",
}

PRESETS = {
    "small": {
        "label": "Small",
        "roots": ["test_sources", "packages/core/src", "rag"],
        "max_files": 18,
        "max_file_bytes": 180_000,
        "chunk_chars": 0,
        "default_queries": 18,
    },
    "medium": {
        "label": "Medium",
        "roots": ["rag", "packages", "Runtime"],
        "max_files": 72,
        "max_file_bytes": 220_000,
        "chunk_chars": 0,
        "default_queries": 42,
    },
    "large": {
        "label": "Large",
        "roots": ["."],
        "max_files": 180,
        "max_file_bytes": 180_000,
        "chunk_chars": 4200,
        "overlap_chars": 450,
        "default_queries": 70,
    },
    "custom": {
        "label": "My own repo",
        "roots": [],
        "max_files": 220,
        "max_file_bytes": 220_000,
        "chunk_chars": 4200,
        "overlap_chars": 450,
        "default_queries": 42,
    },
}

SPECTRUM_PROFILES = {
    "fast": "Fast",
    "balanced": "Balanced",
    "accurate": "Accurate",
}


def resolved_spectrum_config(profile_name: str, preset_name: str, run_dir: Path | None = None) -> dict:
    profile = coderag_rerank_profile(profile_name)
    preset = PRESETS[preset_name]
    index_dir = run_dir / "spectrum" if run_dir else None
    return {
        "retrieval_mode": "coderag",
        "profile": profile_name,
        "profile_label": SPECTRUM_PROFILES[profile_name],
        "index_directory": rel_path(index_dir) if index_dir else "per-run spectrum directory",
        "fresh_index_per_run": True,
        "reuses_encoded_corpus_between_runs": False,
        "query_expansion": {
            "enabled": True,
            "method": "expand_query_aliases",
            "profile_specific": False,
        },
        "build": {
            "profile_affects_build": False,
            "chunk_chars": int(preset.get("chunk_chars", 0) or 0),
            "overlap_chars": int(preset.get("overlap_chars", 0) or 0),
            "tokenisation_profile_specific": False,
            "compression_profile_specific": False,
            "stored_metadata_profile_specific": False,
            "index_postings_profile_specific": False,
        },
        "ranking": {
            "base_ranker": "BM25 over Spectrum retrieval token IDs",
            "profile_affects_ranking": True,
            "profile_effect": "CodeRAG candidate window and repo-aware code/path/doc scoring",
            "reranker": "CodeSignalReranker",
            "rerank_profile": asdict(profile) if profile else None,
        },
    }

WORD_RE = re.compile(r"[A-Za-z][A-Za-z0-9_]{1,}")
IDENT_RE = re.compile(r"[A-Za-z_][A-Za-z0-9_]{2,}")
SPLIT_RE = re.compile(r"[_\-.\\/]+|(?<=[a-z0-9])(?=[A-Z])|(?<=[A-Z])(?=[A-Z][a-z])")
GITHUB_REPO_RE = re.compile(r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$")


@dataclass
class BenchDoc:
    id: int
    title: str
    text: str
    source_path: str
    language_id: int
    chunk_index: int = 0


@dataclass
class Query:
    query: str
    title: str
    relevant_ids: list[int]


@dataclass
class EngineBuild:
    status: str
    build_ms: float = 0.0
    size_bytes: int = 0
    error: str = ""
    extra: dict | None = None


def rel_path(path: Path, base: Path = ROOT) -> str:
    try:
        return path.relative_to(base).as_posix()
    except ValueError:
        return path.as_posix()


def dir_size(path: Path) -> int:
    if not path.exists():
        return 0
    return sum(item.stat().st_size for item in path.rglob("*") if item.is_file())


def format_bytes(value: int) -> str:
    units = ("B", "KB", "MB", "GB")
    size = float(value)
    for unit in units:
        if size < 1024 or unit == units[-1]:
            return f"{size:.1f} {unit}" if unit != "B" else f"{int(size)} B"
        size /= 1024
    return f"{value} B"


def percentile(values: list[float], pct: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    idx = min(len(ordered) - 1, math.ceil((pct / 100) * len(ordered)) - 1)
    return ordered[idx]


def split_words(value: str) -> list[str]:
    words = []
    for part in SPLIT_RE.split(value):
        part = part.strip().lower()
        if len(part) > 1 and not part.isdigit():
            words.append(part)
    return words


def collect_files(preset_name: str, custom_root: Path | None = None) -> list[Path]:
    preset = PRESETS[preset_name]
    max_file_bytes = int(preset["max_file_bytes"])
    paths: list[Path] = []
    seen: set[Path] = set()
    roots = [custom_root] if custom_root else [(ROOT / root_name).resolve() for root_name in preset["roots"]]
    for root in roots:
        if root is None:
            continue
        if not root.exists():
            continue
        candidates = [root] if root.is_file() else root.rglob("*")
        for path in candidates:
            if not path.is_file():
                continue
            if path.suffix.lower() not in LANG_BY_EXT:
                continue
            if path.stat().st_size > max_file_bytes:
                continue
            exclude_base = custom_root or ROOT
            try:
                rel_parts = path.relative_to(exclude_base).parts
            except ValueError:
                rel_parts = path.parts
            if any(part in EXCLUDE_DIRS for part in rel_parts):
                continue
            resolved = path.resolve()
            if resolved not in seen:
                seen.add(resolved)
                paths.append(path)
    return sorted(paths, key=lambda item: rel_path(item))[: int(preset["max_files"])]


def make_docs(paths: list[Path], preset_name: str, source_base: Path = ROOT) -> list[BenchDoc]:
    preset = PRESETS[preset_name]
    chunk_chars = int(preset.get("chunk_chars", 0) or 0)
    overlap_chars = int(preset.get("overlap_chars", 0) or 0)
    docs: list[BenchDoc] = []
    for path in paths:
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        if not text.strip():
            continue
        source_path = rel_path(path, base=source_base)
        language_id = LANG_BY_EXT[path.suffix.lower()]
        body = f"{source_path}\n\n{text}"
        if chunk_chars <= 0 or len(body) <= chunk_chars:
            docs.append(BenchDoc(len(docs), source_path, body, source_path, language_id, 0))
            continue
        step = max(1, chunk_chars - overlap_chars)
        chunk_index = 0
        start = 0
        while start < len(body):
            part = body[start : start + chunk_chars]
            docs.append(BenchDoc(len(docs), f"{source_path}#{chunk_index}", part, source_path, language_id, chunk_index))
            chunk_index += 1
            if start + chunk_chars >= len(body):
                break
            start += step
    return docs


def query_words_for_doc(doc: BenchDoc) -> list[str]:
    path = Path(doc.source_path)
    words = []
    words.extend(split_words(path.stem))
    words.extend(split_words(" ".join(path.parent.parts[-3:])))
    identifiers = Counter(word.lower() for word in IDENT_RE.findall(doc.text) if len(word) > 2)
    for ident, _count in identifiers.most_common(12):
        words.extend(split_words(ident))
        if len(words) >= 12:
            break
    deduped = []
    for word in words:
        if word not in deduped and len(word) > 1:
            deduped.append(word)
    return deduped[:9] or [path.stem.lower()]


def make_queries(docs: list[BenchDoc], limit: int) -> list[Query]:
    by_source: dict[str, list[BenchDoc]] = {}
    for doc in docs:
        by_source.setdefault(doc.source_path, []).append(doc)
    queries = []
    templates = (
        "find code for {words}",
        "where is {words} implemented",
        "show repository context for {words}",
        "which file handles {words}",
    )
    for source_path, group in sorted(by_source.items()):
        words = query_words_for_doc(group[0])
        phrase = " ".join(words)
        template = templates[len(queries) % len(templates)]
        queries.append(Query(
            query=template.format(words=phrase),
            title=source_path,
            relevant_ids=[doc.id for doc in group],
        ))
    return queries[:limit]


def normalize_github_repo(value: str) -> tuple[str, str]:
    repo = value.strip()
    if not repo:
        raise ValueError("Enter a GitHub repo as owner/name or https://github.com/owner/name")
    if GITHUB_REPO_RE.match(repo):
        owner_name = repo
    else:
        match = re.match(r"^https://github\.com/([A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+?)(?:\.git)?/?$", repo)
        if not match:
            raise ValueError("Only GitHub repos are supported. Use owner/name or https://github.com/owner/name")
        owner_name = match.group(1)
    url = f"https://github.com/{owner_name}.git"
    slug = re.sub(r"[^A-Za-z0-9_.-]+", "-", owner_name.replace("/", "-")).strip("-")
    return url, slug or "github-repo"


def repo_display_name(preset_name: str, repo_url: str | None) -> str:
    if repo_url:
        try:
            url, _slug = normalize_github_repo(repo_url)
            return url.removeprefix("https://github.com/").removesuffix(".git")
        except ValueError:
            return repo_url.strip()
    return f"Spectrum local checkout ({PRESETS[preset_name]['label']})"


def prepare_github_clone(repo: str, run_dir: Path) -> tuple[str, str, Path]:
    git = shutil.which("git")
    if git is None:
        raise RuntimeError("git was not found on PATH")
    url, slug = normalize_github_repo(repo)
    target = run_dir / "source" / slug
    target.parent.mkdir(parents=True, exist_ok=True)
    return git, url, target


def write_clone_metadata(repo: str, url: str, target: Path, run_dir: Path, started: float) -> None:
    (run_dir / "source.json").write_text(
        json.dumps(
            {
                "type": "github",
                "repo": repo,
                "url": url,
                "path": rel_path(target),
                "clone_ms": round((time.perf_counter() - started) * 1000, 4),
            },
            indent=2,
        ),
        encoding="utf-8",
    )


def clone_github_repo(repo: str, run_dir: Path, *, timeout_seconds: int = 1_200) -> Path:
    git, url, target = prepare_github_clone(repo, run_dir)
    started = time.perf_counter()
    result = subprocess.run(
        [git, "clone", "--quiet", "--depth", "1", "--filter=blob:none", url, str(target)],
        cwd=ROOT,
        capture_output=True,
        text=True,
        timeout=timeout_seconds,
    )
    if result.returncode:
        error = (result.stderr or result.stdout or "git clone failed").strip().splitlines()[-1]
        raise RuntimeError(error)
    write_clone_metadata(repo, url, target, run_dir, started)
    return target


def clone_github_repo_events(repo: str, run_dir: Path, *, timeout_seconds: int = 1_200) -> Iterable[dict]:
    git, url, target = prepare_github_clone(repo, run_dir)
    started = time.perf_counter()
    process = subprocess.Popen(
        [git, "clone", "--quiet", "--depth", "1", "--filter=blob:none", url, str(target)],
        cwd=ROOT,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    last_tick = 0
    while process.poll() is None:
        elapsed = int(time.perf_counter() - started)
        if elapsed >= timeout_seconds:
            process.kill()
            process.communicate()
            raise RuntimeError(f"git clone timed out after {timeout_seconds} seconds")
        if elapsed >= last_tick:
            yield emit("phase", {"message": f"Cloning GitHub repository ({elapsed}s)", "repo": repo})
            last_tick = elapsed + 5
        time.sleep(0.5)

    stdout, stderr = process.communicate()
    if process.returncode:
        error = (stderr or stdout or "git clone failed").strip().splitlines()[-1]
        raise RuntimeError(error)
    write_clone_metadata(repo, url, target, run_dir, started)
    yield emit("phase", {"message": "GitHub repository cloned", "repo": repo, "path": rel_path(target)})
    yield {"type": "_clone_done", "path": target}


def encode_code_to_spec_bytes(text: str, source_path: str, language_id: int) -> tuple[bytes, list[int]]:
    tokenizer = TOKENIZER_BY_LANG.get(language_id, tokenize_text)
    try:
        tokens = tokenizer(text)
    except Exception:
        tokens = list(text)
    source_bytes = text.encode("utf-8")
    checksum = sum(source_bytes) & 0xFFFF
    raw_ids = tokens_to_ids(tokens)
    encoded_ids = apply_rle_ids(raw_ids)
    raw_stream = struct.pack(f"<{len(encoded_ids)}I", *encoded_ids)
    body = zlib.compress(raw_stream, level=9)
    header = build_header(D.DICT_VERSION, len(source_bytes), checksum, FLAG_RLE, language_id)
    dict_ids = [token_id for token_id in raw_ids if token_id < D.SPEC_ID_ASCII_BASE]
    dict_ids.extend(retrieval_alias_ids(text, source_path, language_id))
    return header + body, dict_ids


def retrieval_alias_ids(text: str, source_path: str, language_id: int) -> list[int]:
    ids: list[int] = []
    seen: set[int] = set()

    def add(value: str) -> None:
        for token_id in retrieval_token_ids(value):
            if token_id not in seen:
                seen.add(token_id)
                ids.append(token_id)

    path = Path(source_path)
    add(" ".join(path.parts))
    add(path.stem)
    add(LANG_NAMES.get(language_id, "code"))
    identifier_words: list[str] = []
    for ident in IDENT_RE.findall(text):
        identifier_words.extend(split_words(ident))
        if len(identifier_words) > 120:
            break
    if identifier_words:
        add(" ".join(identifier_words))
    return ids


def raw_tokens(text: str) -> list[str]:
    return [match.group(0).lower() for match in WORD_RE.finditer(text)]


def write_binary_postings(path: Path, documents: list[dict], postings: dict) -> None:
    out = bytearray()
    out.extend(b"HUDSPB1")
    out.extend(struct.pack("<II", len(documents), len(postings)))
    for doc in documents:
        title = str(doc.get("title", "")).encode("utf-8")
        source_path = str(doc.get("source_path", "")).encode("utf-8")
        out.extend(struct.pack("<III", int(doc["id"]), int(doc["token_count"]), int(doc["orig_length"])))
        out.extend(struct.pack("<II", len(title), len(source_path)))
        out.extend(title)
        out.extend(source_path)
    for token_id, rows in sorted(postings.items(), key=lambda item: str(item[0])):
        numeric = isinstance(token_id, int)
        if numeric:
            token_bytes = b""
            out.extend(struct.pack("<BI", 1, token_id))
        else:
            token_bytes = str(token_id).encode("utf-8")
            out.extend(struct.pack("<BI", 0, len(token_bytes)))
            out.extend(token_bytes)
        out.extend(struct.pack("<I", len(rows)))
        for doc_id, count in rows:
            out.extend(struct.pack("<II", int(doc_id), int(count)))
    path.write_bytes(out)


class PostingBM25:
    def __init__(self, documents: list[dict], postings: dict, avg_doc_length: float, k1: float = 1.5, b: float = 0.75):
        self.documents = documents
        self.postings = postings
        self.avg_doc_length = avg_doc_length
        self.k1 = k1
        self.b = b
        self.n_docs = len(documents)
        self.lengths = [int(doc["token_count"]) for doc in documents]
        self.norms = [
            1 - b + b * (length / avg_doc_length) if avg_doc_length > 0 else 1.0
            for length in self.lengths
        ]
        self.idf = {
            token: math.log((self.n_docs - len(rows) + 0.5) / (len(rows) + 0.5) + 1)
            for token, rows in postings.items()
        }

    def search(self, query_terms: list, top_k: int) -> list[int]:
        scores: dict[int, float] = {}
        query_freq = Counter(query_terms)
        for token, query_count in query_freq.items():
            rows = self.postings.get(token)
            if not rows:
                continue
            idf = self.idf.get(token, 0.0)
            for doc_id, tf in rows:
                norm = self.norms[doc_id]
                score = idf * (tf * (self.k1 + 1)) / (tf + self.k1 * norm)
                scores[doc_id] = scores.get(doc_id, 0.0) + score * query_count
        return [
            doc_id
            for doc_id, score in sorted(scores.items(), key=lambda item: item[1], reverse=True)[:top_k]
            if score > 0
        ]


class BenchmarkEngine:
    key = "engine"
    label = "Engine"
    reconstructable = False

    def build(self, docs: list[BenchDoc], run_dir: Path) -> EngineBuild:
        raise NotImplementedError

    def search(self, query: str, top_k: int) -> list[int]:
        raise NotImplementedError

    def debug_failure(self, query: str, result_ids: list[int], expected_ids: list[int], doc_by_id: dict[int, BenchDoc]) -> dict:
        return {}


class SpectrumEngine(BenchmarkEngine):
    key = "spectrum"
    label = "Spectrum CodeRAG"
    reconstructable = True

    def __init__(self, profile_name: str = "accurate"):
        profile_name = profile_name.lower()
        if profile_name not in SPECTRUM_PROFILES:
            raise ValueError(f"Unknown Spectrum profile: {profile_name}")
        self.profile_name = profile_name
        self.profile_label = SPECTRUM_PROFILES[profile_name]
        self.label = f"Spectrum CodeRAG ({self.profile_label})"
        self.retrieval_mode = "coderag"
        self.rerank_profile = coderag_rerank_profile(profile_name)

    def build(self, docs: list[BenchDoc], run_dir: Path) -> EngineBuild:
        out_dir = run_dir / self.key
        chunk_dir = out_dir / "chunks"
        chunk_dir.mkdir(parents=True, exist_ok=True)
        started = time.perf_counter()
        postings: dict[int, list[tuple[int, int]]] = {}
        documents = []
        text_by_id = {}
        total_tokens = 0
        for doc in docs:
            data, dict_ids = encode_code_to_spec_bytes(doc.text, doc.source_path, doc.language_id)
            spec_rel = Path("chunks") / f"chunk_{doc.id:06d}.spec"
            (out_dir / spec_rel).write_bytes(data)
            freq = Counter(dict_ids)
            total_tokens += len(dict_ids)
            text_by_id[doc.id] = doc.text
            documents.append({
                "id": doc.id,
                "title": doc.title,
                "source_path": doc.source_path,
                "path": spec_rel.as_posix(),
                "language_id": doc.language_id,
                "orig_length": len(doc.text.encode("utf-8")),
                "token_count": len(dict_ids),
            })
            for token_id, count in freq.items():
                postings.setdefault(token_id, []).append((doc.id, count))
        avg_doc_length = total_tokens / len(documents) if documents else 0.0
        (out_dir / "docs.json").write_text(json.dumps({"documents": documents}, separators=(",", ":")), encoding="utf-8")
        write_binary_postings(out_dir / "index.hudspb", documents, postings)
        self.bm25 = PostingBM25(documents, postings, avg_doc_length)
        self.reranker = (
            CodeSignalReranker(documents, text_by_id, self.rerank_profile)
            if self.rerank_profile and self.rerank_profile.candidates > 0
            else None
        )
        return EngineBuild(
            status="ok",
            build_ms=(time.perf_counter() - started) * 1000,
            size_bytes=dir_size(out_dir),
            extra={
                "tokens": total_tokens,
                "artifacts": rel_path(out_dir),
                "retrieval_mode": self.retrieval_mode,
                "profile": self.profile_name,
                "rerank_candidates": self.rerank_profile.candidates if self.rerank_profile else 0,
            },
        )

    def search(self, query: str, top_k: int) -> list[int]:
        expanded_query, _aliases = expand_query_aliases(query)
        candidate_count = max(top_k, self.reranker.profile.candidates if self.reranker else top_k)
        doc_ids = self.bm25.search(retrieval_token_ids(expanded_query), candidate_count)
        if self.reranker:
            return self.reranker.rerank(doc_ids, expanded_query, top_k=top_k)
        return doc_ids[:top_k]

    def debug_failure(self, query: str, result_ids: list[int], expected_ids: list[int], doc_by_id: dict[int, BenchDoc]) -> dict:
        return spectrum_debug_passes(query, result_ids, expected_ids, doc_by_id, self.reranker)


class RawBM25Engine(BenchmarkEngine):
    key = "raw_bm25"
    label = "Raw BM25"
    reconstructable = True

    def build(self, docs: list[BenchDoc], run_dir: Path) -> EngineBuild:
        out_dir = run_dir / self.key
        out_dir.mkdir(parents=True, exist_ok=True)
        started = time.perf_counter()
        documents = []
        postings: dict[str, list[tuple[int, int]]] = {}
        total_tokens = 0
        records_path = out_dir / "chunks.jsonl"
        with records_path.open("w", encoding="utf-8") as handle:
            for doc in docs:
                handle.write(json.dumps(doc.__dict__, ensure_ascii=False, separators=(",", ":")) + "\n")
                tokens = raw_tokens(doc.text)
                total_tokens += len(tokens)
                freq = Counter(tokens)
                documents.append({
                    "id": doc.id,
                    "title": doc.title,
                    "source_path": doc.source_path,
                    "orig_length": len(doc.text.encode("utf-8")),
                    "token_count": len(tokens),
                })
                for token, count in freq.items():
                    postings.setdefault(token, []).append((doc.id, count))
        write_binary_postings(out_dir / "index.hudbm25", documents, postings)
        avg_doc_length = total_tokens / len(documents) if documents else 0.0
        self.bm25 = PostingBM25(documents, postings, avg_doc_length)
        return EngineBuild(
            status="ok",
            build_ms=(time.perf_counter() - started) * 1000,
            size_bytes=dir_size(out_dir),
            extra={"tokens": total_tokens, "artifacts": rel_path(out_dir)},
        )

    def search(self, query: str, top_k: int) -> list[int]:
        return self.bm25.search(raw_tokens(query), top_k)


class TfidfEngine(BenchmarkEngine):
    key = "tfidf"
    label = "TF-IDF"
    reconstructable = True

    def build(self, docs: list[BenchDoc], run_dir: Path) -> EngineBuild:
        if ML_IMPORT_ERROR:
            return EngineBuild(status="skipped", error=f"scikit-learn stack unavailable: {ML_IMPORT_ERROR}")
        out_dir = run_dir / self.key
        out_dir.mkdir(parents=True, exist_ok=True)
        started = time.perf_counter()
        try:
            self.vectorizer = TfidfVectorizer(lowercase=True, stop_words="english", max_features=100_000, norm="l2")
            self.matrix = self.vectorizer.fit_transform([doc.text for doc in docs])
        except Exception as exc:
            return EngineBuild(status="skipped", error=str(exc))
        sparse.save_npz(out_dir / "tfidf_matrix.npz", self.matrix, compressed=True)
        vocabulary = {term: int(index) for term, index in self.vectorizer.vocabulary_.items()}
        (out_dir / "vocabulary.json").write_text(json.dumps(vocabulary, separators=(",", ":")), encoding="utf-8")
        with (out_dir / "chunks.jsonl").open("w", encoding="utf-8") as handle:
            for doc in docs:
                handle.write(json.dumps(doc.__dict__, ensure_ascii=False, separators=(",", ":")) + "\n")
        return EngineBuild(
            status="ok",
            build_ms=(time.perf_counter() - started) * 1000,
            size_bytes=dir_size(out_dir),
            extra={"features": int(self.matrix.shape[1]), "artifacts": rel_path(out_dir)},
        )

    def search(self, query: str, top_k: int) -> list[int]:
        q = self.vectorizer.transform([query])
        scores = (self.matrix @ q.T).toarray().ravel()
        if not np.any(scores):
            return []
        order = np.argsort(-scores)[:top_k]
        return [int(doc_id) for doc_id in order if scores[int(doc_id)] > 0]


class DenseVectorEngine(BenchmarkEngine):
    key = "dense_vector"
    label = "Dense Vector"

    def __init__(self, dimensions: int = 96):
        self.dimensions = dimensions

    def build(self, docs: list[BenchDoc], run_dir: Path) -> EngineBuild:
        if ML_IMPORT_ERROR:
            return EngineBuild(status="skipped", error=f"scikit-learn stack unavailable: {ML_IMPORT_ERROR}")
        out_dir = run_dir / self.key
        out_dir.mkdir(parents=True, exist_ok=True)
        started = time.perf_counter()
        try:
            self.vectorizer = TfidfVectorizer(lowercase=True, stop_words="english", max_features=100_000, norm="l2")
            tfidf = self.vectorizer.fit_transform([doc.text for doc in docs])
            dims = min(self.dimensions, max(1, min(tfidf.shape) - 1))
            if min(tfidf.shape) < 2:
                return EngineBuild(status="skipped", error="corpus too small for SVD vector benchmark")
            self.svd = TruncatedSVD(n_components=dims, random_state=42)
            self.matrix = normalize(self.svd.fit_transform(tfidf)).astype("float32")
        except Exception as exc:
            return EngineBuild(status="skipped", error=str(exc))
        np.save(out_dir / "dense_lsa.npy", self.matrix)
        vocabulary = {term: int(index) for term, index in self.vectorizer.vocabulary_.items()}
        (out_dir / "vocabulary.json").write_text(json.dumps(vocabulary, separators=(",", ":")), encoding="utf-8")
        return EngineBuild(
            status="ok",
            build_ms=(time.perf_counter() - started) * 1000,
            size_bytes=dir_size(out_dir),
            extra={"dimensions": int(self.matrix.shape[1]), "artifacts": rel_path(out_dir)},
        )

    def search(self, query: str, top_k: int) -> list[int]:
        q = self.vectorizer.transform([query])
        q_dense = normalize(self.svd.transform(q)).astype("float32")
        scores = self.matrix @ q_dense.T
        order = np.argsort(-scores.ravel())[:top_k]
        return [int(doc_id) for doc_id in order if scores[int(doc_id)] > 0]


class ChromaEngine(DenseVectorEngine):
    key = "chroma"
    label = "Chroma"
    reconstructable = True

    def build(self, docs: list[BenchDoc], run_dir: Path) -> EngineBuild:
        try:
            import chromadb
        except Exception as exc:
            return EngineBuild(status="skipped", error=f"chromadb unavailable: {exc}")
        report = super().build(docs, run_dir)
        if report.status != "ok":
            return report
        out_dir = run_dir / self.key
        try:
            client = chromadb.PersistentClient(path=str(out_dir / "chroma"))
            self.collection = client.get_or_create_collection("coderag")
            self.collection.add(
                ids=[str(doc.id) for doc in docs],
                embeddings=self.matrix.astype("float32").tolist(),
                documents=[doc.text for doc in docs],
                metadatas=[
                    {
                        "title": doc.title,
                        "source_path": doc.source_path,
                        "language_id": doc.language_id,
                        "chunk_index": doc.chunk_index,
                    }
                    for doc in docs
                ],
            )
        except Exception as exc:
            return EngineBuild(status="skipped", error=f"chroma build failed: {exc}")
        report.size_bytes = dir_size(out_dir)
        report.extra = dict(report.extra or {}, backend="chromadb.PersistentClient")
        return report

    def search(self, query: str, top_k: int) -> list[int]:
        q = self.vectorizer.transform([query])
        q_dense = normalize(self.svd.transform(q)).astype("float32")
        result = self.collection.query(query_embeddings=q_dense.tolist(), n_results=top_k)
        ids = result.get("ids", [[]])[0]
        return [int(doc_id) for doc_id in ids]


class FaissEngine(DenseVectorEngine):
    key = "faiss"
    label = "FAISS Flat"

    def build(self, docs: list[BenchDoc], run_dir: Path) -> EngineBuild:
        try:
            import faiss
        except Exception as exc:
            return EngineBuild(status="skipped", error=f"faiss unavailable: {exc}")
        report = super().build(docs, run_dir)
        if report.status != "ok":
            return report
        out_dir = run_dir / self.key
        self.index = faiss.IndexFlatIP(self.matrix.shape[1])
        self.index.add(self.matrix.astype("float32"))
        faiss.write_index(self.index, str(out_dir / "faiss.index"))
        report.size_bytes = dir_size(out_dir)
        report.extra = dict(report.extra or {}, backend="faiss.IndexFlatIP")
        return report

    def search(self, query: str, top_k: int) -> list[int]:
        q = self.vectorizer.transform([query])
        q_dense = normalize(self.svd.transform(q)).astype("float32")
        scores, ids = self.index.search(q_dense, top_k)
        return [int(doc_id) for doc_id, score in zip(ids[0], scores[0]) if doc_id >= 0 and score > 0]


class HybridSparseDenseEngine(BenchmarkEngine):
    key = "hybrid"
    label = "Hybrid Sparse+Dense"
    reconstructable = True

    def __init__(self, dimensions: int = 96):
        self.dimensions = dimensions

    def build(self, docs: list[BenchDoc], run_dir: Path) -> EngineBuild:
        if ML_IMPORT_ERROR:
            return EngineBuild(status="skipped", error=f"scikit-learn stack unavailable: {ML_IMPORT_ERROR}")
        out_dir = run_dir / self.key
        out_dir.mkdir(parents=True, exist_ok=True)
        started = time.perf_counter()
        documents = []
        postings: dict[str, list[tuple[int, int]]] = {}
        total_tokens = 0
        with (out_dir / "chunks.jsonl").open("w", encoding="utf-8") as handle:
            for doc in docs:
                handle.write(json.dumps(doc.__dict__, ensure_ascii=False, separators=(",", ":")) + "\n")
                tokens = raw_tokens(doc.text)
                total_tokens += len(tokens)
                freq = Counter(tokens)
                documents.append({
                    "id": doc.id,
                    "title": doc.title,
                    "source_path": doc.source_path,
                    "orig_length": len(doc.text.encode("utf-8")),
                    "token_count": len(tokens),
                })
                for token, count in freq.items():
                    postings.setdefault(token, []).append((doc.id, count))
        write_binary_postings(out_dir / "index.hudbm25", documents, postings)
        avg_doc_length = total_tokens / len(documents) if documents else 0.0
        self.bm25 = PostingBM25(documents, postings, avg_doc_length)
        try:
            self.vectorizer = TfidfVectorizer(lowercase=True, stop_words="english", max_features=100_000, norm="l2")
            tfidf = self.vectorizer.fit_transform([doc.text for doc in docs])
            if min(tfidf.shape) < 2:
                return EngineBuild(status="skipped", error="corpus too small for hybrid vector benchmark")
            dims = min(self.dimensions, max(1, min(tfidf.shape) - 1))
            self.svd = TruncatedSVD(n_components=dims, random_state=42)
            self.matrix = normalize(self.svd.fit_transform(tfidf)).astype("float32")
        except Exception as exc:
            return EngineBuild(status="skipped", error=str(exc))
        np.save(out_dir / "dense_lsa.npy", self.matrix)
        vocabulary = {term: int(index) for term, index in self.vectorizer.vocabulary_.items()}
        (out_dir / "vocabulary.json").write_text(json.dumps(vocabulary, separators=(",", ":")), encoding="utf-8")
        return EngineBuild(
            status="ok",
            build_ms=(time.perf_counter() - started) * 1000,
            size_bytes=dir_size(out_dir),
            extra={"tokens": total_tokens, "dimensions": int(self.matrix.shape[1]), "artifacts": rel_path(out_dir)},
        )

    def search(self, query: str, top_k: int) -> list[int]:
        candidate_count = max(40, top_k * 8)
        sparse_ids = self.bm25.search(raw_tokens(query), candidate_count)
        q = self.vectorizer.transform([query])
        q_dense = normalize(self.svd.transform(q)).astype("float32")
        scores = self.matrix @ q_dense.T
        dense_ids = [int(doc_id) for doc_id in np.argsort(-scores.ravel())[:candidate_count] if scores[int(doc_id)] > 0]
        fused: dict[int, float] = {}
        for rank, doc_id in enumerate(sparse_ids, start=1):
            fused[doc_id] = fused.get(doc_id, 0.0) + 1.0 / (60 + rank)
        for rank, doc_id in enumerate(dense_ids, start=1):
            fused[doc_id] = fused.get(doc_id, 0.0) + 1.0 / (60 + rank)
        return [doc_id for doc_id, _score in sorted(fused.items(), key=lambda item: item[1], reverse=True)[:top_k]]


def engines(spectrum_profile: str = "accurate") -> list[BenchmarkEngine]:
    return [
        SpectrumEngine(spectrum_profile),
        FaissEngine(),
        RawBM25Engine(),
        TfidfEngine(),
        ChromaEngine(),
        HybridSparseDenseEngine(),
    ]


def corpus_summary(paths: list[Path], docs: list[BenchDoc]) -> dict:
    raw_bytes = sum(len(doc.text.encode("utf-8")) for doc in docs)
    extensions = Counter(path.suffix.lower() for path in paths)
    return {
        "files": len(paths),
        "docs": len(docs),
        "raw_bytes": raw_bytes,
        "raw_label": format_bytes(raw_bytes),
        "extensions": dict(sorted(extensions.items())),
    }


def emit(event_type: str, payload: dict) -> dict:
    payload = dict(payload)
    payload["type"] = event_type
    payload["ts"] = time.time()
    return payload


def ranked_result_trace(result_ids: list[int], doc_by_id: dict[int, BenchDoc]) -> list[dict]:
    rows = []
    for rank, doc_id in enumerate(result_ids, start=1):
        doc = doc_by_id.get(doc_id)
        rows.append({
            "rank": rank,
            "doc_id": doc_id,
            "title": doc.title if doc else "",
            "source_path": doc.source_path if doc else "",
        })
    return rows


def doc_debug_terms(doc: BenchDoc | None) -> dict:
    if not doc:
        return {"path": "", "dir": "", "filename": "", "stem": "", "extension": "", "terms": []}
    path = Path(doc.source_path)
    terms = []
    for value in (*path.parts, path.stem, path.suffix.lstrip(".")):
        terms.extend(split_words(value))
    return {
        "path": doc.source_path,
        "dir": path.parent.as_posix(),
        "filename": path.name,
        "stem": path.stem.lower(),
        "extension": path.suffix.lower(),
        "terms": list(dict.fromkeys(terms)),
    }


def query_debug_terms(query: str) -> set[str]:
    terms = []
    for token in raw_tokens(query):
        terms.extend(split_words(token))
    return set(terms)


def is_generic_doc(path: str) -> bool:
    name = Path(path).name.lower()
    return name in {"changelog.md", "roadmap.md", "readme.md", "contributing.md"} or "security-advisories" in path.lower()


def is_config_or_doc(path: str) -> bool:
    name = Path(path).name.lower()
    suffix = Path(path).suffix.lower()
    return suffix in {".md", ".json", ".yaml", ".yml", ".toml"} or name in {
        "docker-compose.yml",
        "package.json",
        "plugin.json",
        "hooks.json",
        "hooks.codex.json",
        ".mcp.json",
    }


def rerank_explain_rows(
    query: str,
    candidate_ids: list[int],
    expected_ids: list[int],
    doc_by_id: dict[int, BenchDoc],
    reranker: CodeSignalReranker | None,
) -> list[dict]:
    if not reranker:
        return []
    ordered_ids = list(dict.fromkeys(candidate_ids + expected_ids))
    rows = []
    for doc_id in ordered_ids:
        doc = doc_by_id.get(doc_id)
        explanation = reranker.explain(doc_id, query)
        rows.append({
            "doc_id": doc_id,
            "title": doc.title if doc else "",
            "is_expected": doc_id in expected_ids,
            **explanation,
        })
    return rows


def spectrum_debug_passes(
    query: str,
    result_ids: list[int],
    expected_ids: list[int],
    doc_by_id: dict[int, BenchDoc],
    reranker: CodeSignalReranker | None,
) -> dict:
    query_terms = query_debug_terms(query)
    expected_docs = [doc_by_id[doc_id] for doc_id in expected_ids if doc_id in doc_by_id]
    top_doc = doc_by_id.get(result_ids[0]) if result_ids else None
    expected_primary = expected_docs[0] if expected_docs else None
    expected_info = doc_debug_terms(expected_primary)
    top_info = doc_debug_terms(top_doc)
    expected_path_terms = set(expected_info["terms"])
    top_path_terms = set(top_info["terms"])
    same_dir = bool(expected_info["dir"] and expected_info["dir"] == top_info["dir"])
    expected_stem_in_query = expected_info["stem"] in query_terms if expected_info["stem"] else False
    expected_filename_in_query = expected_info["filename"].lower() in query.lower() if expected_info["filename"] else False
    top_is_generic = is_generic_doc(top_info["path"])
    expected_is_config_or_doc = is_config_or_doc(expected_info["path"])
    rerank_rows = rerank_explain_rows(query, result_ids, expected_ids, doc_by_id, reranker)
    return {
        "debug_pass_order": [
            "exact_path_title_match",
            "config_doc_intent_boost",
            "generic_doc_crowding_penalty",
            "sibling_tie_break",
            "reranker_score_breakdown",
        ],
        "passes": [
            {
                "name": "exact_path_title_match",
                "triggered": bool(expected_path_terms & query_terms or expected_stem_in_query or expected_filename_in_query),
                "observation": "Expected path/title terms are present in the query but did not win rank 1.",
                "expected_path_terms_in_query": sorted(expected_path_terms & query_terms),
                "top_path_terms_in_query": sorted(top_path_terms & query_terms),
                "expected_filename_in_query": expected_filename_in_query,
                "expected_stem_in_query": expected_stem_in_query,
            },
            {
                "name": "config_doc_intent_boost",
                "triggered": expected_is_config_or_doc,
                "observation": "Expected target is a doc/config/metadata file that may need explicit path and file-type intent boosts.",
                "expected_extension": expected_info["extension"],
                "expected_filename": expected_info["filename"],
            },
            {
                "name": "generic_doc_crowding_penalty",
                "triggered": top_is_generic,
                "observation": "Top result is a broad repository document or advisory that may crowd out narrower targets.",
                "top_path": top_info["path"],
                "top_is_generic_doc": top_is_generic,
            },
            {
                "name": "sibling_tie_break",
                "triggered": same_dir,
                "observation": "Top result and expected result are in the same directory; a filename/stem tie-break may be needed.",
                "same_directory": same_dir,
                "expected_directory": expected_info["dir"],
                "top_directory": top_info["dir"],
            },
            {
                "name": "reranker_score_breakdown",
                "triggered": bool(rerank_rows),
                "observation": "Per-candidate CodeSignalReranker explanations for the returned candidates plus expected docs.",
                "candidates": rerank_rows,
            },
        ],
    }


def evaluate_engine(
    engine: BenchmarkEngine,
    queries: list[Query],
    docs: list[BenchDoc],
    top_k: int,
    build: EngineBuild,
    debug_failures: list[dict] | None = None,
    low_rank_cutoff: int = 1,
) -> Iterable[dict]:
    hit1 = 0
    recall = 0
    reciprocal_ranks = []
    latencies = []
    doc_by_id = {doc.id: doc for doc in docs}
    total = max(1, len(queries))
    reconstruction_rate = 1.0 if engine.reconstructable else 0.0
    for index, item in enumerate(queries, start=1):
        started = time.perf_counter()
        result_ids = engine.search(item.query, top_k)
        elapsed_ms = (time.perf_counter() - started) * 1000
        latencies.append(elapsed_ms)
        relevant = set(item.relevant_ids)
        rank = next((rank for rank, doc_id in enumerate(result_ids, start=1) if doc_id in relevant), None)
        if result_ids and result_ids[0] in relevant:
            hit1 += 1
        if relevant.intersection(result_ids):
            recall += 1
        reciprocal_ranks.append(1 / rank if rank else 0.0)
        top_doc = doc_by_id.get(result_ids[0]) if result_ids else None
        if debug_failures is not None and (rank is None or rank > low_rank_cutoff):
            expected_docs = [doc_by_id[doc_id] for doc_id in item.relevant_ids if doc_id in doc_by_id]
            debug_failures.append({
                "query_index": index,
                "failure_type": "miss" if rank is None else "low_rank",
                "query": item.query,
                "expected": item.title,
                "expected_ids": item.relevant_ids,
                "expected_titles": [doc.title for doc in expected_docs],
                "rank": rank,
                "top": top_doc.title if top_doc else "",
                "latency_ms": round(elapsed_ms, 4),
                "result_ids": result_ids,
                "results": ranked_result_trace(result_ids, doc_by_id),
                "debug": engine.debug_failure(item.query, result_ids, item.relevant_ids, doc_by_id),
            })
        metrics = {
            "hit1": round(hit1 / index, 4),
            "recall": round(recall / index, 4),
            "mrr": round(mean(reciprocal_ranks), 4),
            "avg_ms": round(mean(latencies), 4),
            "p95_ms": round(percentile(latencies, 95), 4),
            "queries_done": index,
            "queries_total": total,
            "size_bytes": build.size_bytes,
            "size_label": format_bytes(build.size_bytes),
            "reconstruction_rate": reconstruction_rate,
        }
        yield emit("metric", {
            "engine": engine.key,
            "label": engine.label,
            "metrics": metrics,
            "last": {
                "query": item.query,
                "expected": item.title,
                "rank": rank,
                "top": top_doc.title if top_doc else "",
                "latency_ms": round(elapsed_ms, 4),
                "result_ids": result_ids,
            },
        })
        time.sleep(0.018)
    yield emit("engine_done", {
        "engine": engine.key,
        "label": engine.label,
        "metrics": {
            "hit1": round(hit1 / total, 4),
            "recall": round(recall / total, 4),
            "mrr": round(mean(reciprocal_ranks) if reciprocal_ranks else 0.0, 4),
            "avg_ms": round(mean(latencies) if latencies else 0.0, 4),
            "p95_ms": round(percentile(latencies, 95), 4),
            "queries_done": len(queries),
            "queries_total": len(queries),
            "size_bytes": build.size_bytes,
            "size_label": format_bytes(build.size_bytes),
            "reconstruction_rate": reconstruction_rate,
        },
    })


def run_benchmark(
    preset_name: str,
    query_limit: int,
    top_k: int = 5,
    repo_url: str | None = None,
    spectrum_profile: str = "accurate",
) -> Iterable[dict]:
    if preset_name not in PRESETS:
        yield emit("error", {"message": f"Unknown preset: {preset_name}"})
        return
    spectrum_profile = spectrum_profile.lower()
    if spectrum_profile not in SPECTRUM_PROFILES:
        yield emit("error", {"message": f"Unknown Spectrum profile: {spectrum_profile}"})
        return
    run_id = time.strftime("%Y%m%d-%H%M%S") + "-" + uuid.uuid4().hex[:8]
    run_dir = RUNS_DIR / run_id
    run_dir.mkdir(parents=True, exist_ok=True)
    custom_root = None
    if preset_name == "custom":
        if not repo_url:
            yield emit("error", {"message": "Enter a GitHub repo before starting a custom run"})
            return
        yield emit("phase", {"message": "Cloning GitHub repository", "run_id": run_id})
        try:
            for event in clone_github_repo_events(repo_url, run_dir):
                if event["type"] == "_clone_done":
                    custom_root = event["path"]
                    continue
                yield event
        except Exception as exc:
            yield emit("error", {"message": str(exc), "preset": preset_name})
            return
    yield emit("phase", {"message": "Collecting corpus files", "run_id": run_id})
    paths = collect_files(preset_name, custom_root=custom_root)
    docs = make_docs(paths, preset_name, source_base=custom_root or ROOT)
    if not docs:
        yield emit("error", {"message": "No benchmarkable files found for preset", "preset": preset_name})
        return
    default_queries = int(PRESETS[preset_name]["default_queries"])
    query_limit = query_limit or default_queries
    queries = make_queries(docs, min(query_limit, max(1, len(docs))))
    summary = corpus_summary(paths, docs)
    repo_name = repo_display_name(preset_name, repo_url)
    spectrum_config = resolved_spectrum_config(spectrum_profile, preset_name, run_dir)
    spectrum_debug = {
        "description": "Spectrum queries where the expected document missed top-k or appeared below rank 1.",
        "debug_pass_order": [
            "exact_path_title_match",
            "config_doc_intent_boost",
            "generic_doc_crowding_penalty",
            "sibling_tie_break",
            "reranker_score_breakdown",
        ],
        "low_rank_cutoff": 1,
        "failure_count": 0,
        "miss_count": 0,
        "low_rank_count": 0,
        "artifact": rel_path(run_dir / "spectrum_debug.json"),
        "failures": [],
    }
    engine_list = engines(spectrum_profile)
    yield emit("run_start", {
        "run_id": run_id,
        "preset": preset_name,
        "preset_label": PRESETS[preset_name]["label"],
        "repo_name": repo_name,
        "spectrum_profile": spectrum_profile,
        "spectrum_profile_label": SPECTRUM_PROFILES[spectrum_profile],
        "source": repo_url or "",
        "top_k": top_k,
        "query_count": len(queries),
        "run_dir": rel_path(run_dir),
        "corpus": summary,
        "spectrum_config": spectrum_config,
        "engines": [{"key": engine.key, "label": engine.label} for engine in engine_list],
    })
    final_rows = []
    for engine in engine_list:
        yield emit("engine_start", {"engine": engine.key, "label": engine.label})
        build = engine.build(docs, run_dir)
        ratio = build.size_bytes / summary["raw_bytes"] if summary["raw_bytes"] and build.size_bytes else 0.0
        reconstruction_rate = 1.0 if build.status == "ok" and engine.reconstructable else 0.0 if build.status == "ok" else None
        yield emit("engine_built", {
            "engine": engine.key,
            "label": engine.label,
            "status": build.status,
            "build_ms": round(build.build_ms, 4),
            "size_bytes": build.size_bytes,
            "size_label": format_bytes(build.size_bytes),
            "compression_ratio": round(ratio, 4),
            "reconstruction_rate": reconstruction_rate,
            "error": build.error,
            "extra": build.extra or {},
        })
        if build.status != "ok":
            final_rows.append({
                "engine": engine.key,
                "label": engine.label,
                "status": build.status,
                "error": build.error,
                "build_ms": round(build.build_ms, 4),
                "size_bytes": build.size_bytes,
                "compression_ratio": round(ratio, 4),
                "reconstruction_rate": reconstruction_rate,
            })
            continue
        last_done = None
        debug_failures = spectrum_debug["failures"] if engine.key == "spectrum" else None
        for event in evaluate_engine(engine, queries, docs, top_k, build, debug_failures=debug_failures):
            if event["type"] == "engine_done":
                last_done = event["metrics"]
            yield event
        final_rows.append({
            "engine": engine.key,
            "label": engine.label,
            "status": build.status,
            "build_ms": round(build.build_ms, 4),
            "size_bytes": build.size_bytes,
            "size_label": format_bytes(build.size_bytes),
            "compression_ratio": round(ratio, 4),
            "reconstruction_rate": reconstruction_rate,
            **(last_done or {}),
        })
    spectrum_debug["failure_count"] = len(spectrum_debug["failures"])
    spectrum_debug["miss_count"] = sum(1 for item in spectrum_debug["failures"] if item["failure_type"] == "miss")
    spectrum_debug["low_rank_count"] = sum(1 for item in spectrum_debug["failures"] if item["failure_type"] == "low_rank")
    (run_dir / "spectrum_debug.json").write_text(json.dumps(spectrum_debug, indent=2), encoding="utf-8")
    report = {
        "format": "spectrum-benchmark-hud-run-v1",
        "run_id": run_id,
        "preset": preset_name,
        "preset_label": PRESETS[preset_name]["label"],
        "repo_name": repo_name,
        "spectrum_profile": spectrum_profile,
        "source": repo_url or "",
        "top_k": top_k,
        "query_count": len(queries),
        "corpus": summary,
        "spectrum_config": spectrum_config,
        "spectrum_debug": spectrum_debug,
        "results": final_rows,
    }
    (run_dir / "summary.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    yield emit(
        "run_complete",
        {
            "run_id": run_id,
            "run_dir": rel_path(run_dir),
            "preset": preset_name,
            "preset_label": PRESETS[preset_name]["label"],
            "repo_name": repo_name,
            "spectrum_profile": spectrum_profile,
            "spectrum_profile_label": SPECTRUM_PROFILES[spectrum_profile],
            "source": repo_url or "",
            "top_k": top_k,
            "query_count": len(queries),
            "corpus": summary,
            "spectrum_config": spectrum_config,
            "spectrum_debug": spectrum_debug,
            "results": final_rows,
        },
    )


def presets_payload() -> dict:
    payload = {
        key: {
            "label": value["label"],
            "default_queries": value["default_queries"],
            "max_files": value["max_files"],
            "roots": value["roots"],
        }
        for key, value in PRESETS.items()
    }
    payload["spectrum_profiles"] = SPECTRUM_PROFILES
    return payload


class HudHandler(SimpleHTTPRequestHandler):
    server_version = "SpectrumBenchmarkHUD/1.0"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(APP_DIR), **kwargs)

    def log_message(self, format: str, *args) -> None:
        sys.stderr.write("[benchmark-hud] " + format % args + "\n")

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path == "/api/presets":
            self.send_json(presets_payload())
            return
        if parsed.path == "/events":
            params = parse_qs(parsed.query)
            preset = params.get("preset", ["small"])[0]
            query_count = int(params.get("queries", ["0"])[0] or 0)
            top_k = int(params.get("top_k", ["5"])[0] or 5)
            repo_url = params.get("repo", [""])[0]
            spectrum_profile = params.get("profile", ["accurate"])[0]
            self.send_events(preset, query_count, top_k, repo_url, spectrum_profile)
            return
        if parsed.path == "/":
            self.path = "/index.html"
        return super().do_GET()

    def send_json(self, payload: dict) -> None:
        data = json.dumps(payload).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(data)

    def send_events(
        self,
        preset: str,
        query_count: int,
        top_k: int,
        repo_url: str = "",
        spectrum_profile: str = "accurate",
    ) -> None:
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Connection", "keep-alive")
        self.end_headers()
        try:
            for payload in run_benchmark(
                preset,
                query_count,
                top_k,
                repo_url=repo_url,
                spectrum_profile=spectrum_profile,
            ):
                message = f"event: {payload['type']}\ndata: {json.dumps(payload, separators=(',', ':'))}\n\n"
                self.wfile.write(message.encode("utf-8"))
                self.wfile.flush()
        except (BrokenPipeError, ConnectionResetError):
            return
        except Exception as exc:
            payload = emit("error", {"message": str(exc)})
            message = f"event: error\ndata: {json.dumps(payload, separators=(',', ':'))}\n\n"
            self.wfile.write(message.encode("utf-8"))
            self.wfile.flush()


def main() -> int:
    parser = argparse.ArgumentParser(description="Spectrum real-time benchmark HUD")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--once", choices=sorted(PRESETS), help="Run one benchmark to stdout instead of serving the HUD")
    parser.add_argument("--queries", type=int, default=8)
    parser.add_argument("--repo", help="GitHub repo for --once custom runs, as owner/name or https://github.com/owner/name")
    parser.add_argument(
        "--profile",
        choices=sorted(SPECTRUM_PROFILES),
        default="accurate",
        help="Spectrum rerank profile for HUD runs.",
    )
    args = parser.parse_args()

    if args.once:
        for payload in run_benchmark(args.once, args.queries, repo_url=args.repo, spectrum_profile=args.profile):
            print(json.dumps(payload, ensure_ascii=False))
        return 0

    mimetypes.add_type("text/css", ".css")
    mimetypes.add_type("application/javascript", ".js")
    server = ThreadingHTTPServer((args.host, args.port), HudHandler)
    print(f"Spectrum benchmark HUD: http://{args.host}:{args.port}")
    print(f"Run artifacts: {RUNS_DIR}")
    server.serve_forever()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
