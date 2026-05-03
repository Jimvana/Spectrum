"""
Spectrum extension library manifest helpers.

The current .spec binary header stores a single core dictionary version. Larger
corpora need a second layer: a manifest that declares which domain libraries are
needed to interpret the token stream and preprocessing profile.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from typing import Iterable

import dictionary as D
from spec_format.extension_tokens import MEDIAWIKI_BASE, WIKIMEDIA_XML_BASE


@dataclass(frozen=True)
class SpecLibrary:
    name: str
    version: int
    role: str
    description: str
    provides: tuple[str, ...]
    hash: str

    def to_manifest(self) -> dict:
        return asdict(self)


def stable_library_hash(
    name: str,
    version: int,
    role: str,
    provides: Iterable[str],
) -> str:
    payload = {
        "name": name,
        "version": version,
        "role": role,
        "provides": list(provides),
    }
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def make_library(
    name: str,
    version: int,
    role: str,
    description: str,
    provides: Iterable[str],
) -> SpecLibrary:
    provides_tuple = tuple(provides)
    return SpecLibrary(
        name=name,
        version=version,
        role=role,
        description=description,
        provides=provides_tuple,
        hash=stable_library_hash(name, version, role, provides_tuple),
    )


CORE_LIBRARY = make_library(
    name="spectrum-core",
    version=D.DICT_VERSION,
    role="core-dictionary",
    description="Core Spectrum dictionary and .spec ID stream semantics.",
    provides=(
        "spec-header-v1",
        "uint32-token-stream",
        "ascii-fallback",
        "unicode-fallback",
        "rle-marker",
        "zlib-body",
    ),
)

ENGLISH_TEXT_LIBRARY = make_library(
    name="english-text",
    version=1,
    role="tokenizer-library",
    description="Plain English tokenizer, word dictionary controls, and text reconstruction.",
    provides=(
        "language:text",
        "english-word-tokens",
        "capitalisation-controls",
        "spelled-word-controls",
        "digit-controls",
    ),
)

WIKIMEDIA_CLEAN_TEXT_LIBRARY = make_library(
    name="wikimedia-clean-text",
    version=1,
    role="preprocessing-library",
    description=(
        "Wikimedia pages-articles XML stream parser plus lossy clean-text article "
        "extraction profile."
    ),
    provides=(
        "wikimedia-pages-articles-bz2",
        "namespace-0-articles",
        "redirect-skip-default",
        "clean-wikitext",
        "article-record-title-heading",
    ),
)

WIKIMEDIA_RAW_WIKITEXT_LIBRARY = make_library(
    name="wikimedia-raw-wikitext",
    version=1,
    role="preprocessing-tokenizer-library",
    description=(
        "Wikimedia pages-articles XML stream parser preserving article source "
        "wikitext records and promoting MediaWiki syntax markers to extension IDs."
    ),
    provides=(
        "wikimedia-pages-articles-bz2",
        "namespace-0-articles",
        "redirect-skip-default",
        "raw-wikitext",
        "article-record-title-heading",
        f"mediawiki-token-range:{MEDIAWIKI_BASE}-{MEDIAWIKI_BASE + 99999}",
    ),
)

WIKIMEDIA_XML_LIBRARY = make_library(
    name="wikimedia-xml",
    version=1,
    role="tokenizer-library",
    description=(
        "Wikimedia XML and MediaWiki syntax extension tokens using reserved "
        "global ID ranges."
    ),
    provides=(
        f"xml-token-range:{WIKIMEDIA_XML_BASE}-{WIKIMEDIA_XML_BASE + 99999}",
        f"mediawiki-token-range:{MEDIAWIKI_BASE}-{MEDIAWIKI_BASE + 99999}",
        "xml-page-elements",
        "revision-metadata",
        "mediawiki-templates",
        "mediawiki-links",
        "mediawiki-tables",
        "mediawiki-refs",
    ),
)


def wikipedia_libraries(mode: str) -> list[dict]:
    if mode == "clean-text":
        libraries = [CORE_LIBRARY, ENGLISH_TEXT_LIBRARY, WIKIMEDIA_CLEAN_TEXT_LIBRARY]
    elif mode == "raw-wikitext":
        libraries = [
            CORE_LIBRARY,
            ENGLISH_TEXT_LIBRARY,
            WIKIMEDIA_XML_LIBRARY,
            WIKIMEDIA_RAW_WIKITEXT_LIBRARY,
        ]
    elif mode == "full-xml":
        libraries = [CORE_LIBRARY, ENGLISH_TEXT_LIBRARY, WIKIMEDIA_XML_LIBRARY]
    else:
        raise ValueError(f"Unsupported Wikipedia mode: {mode}")
    return [library.to_manifest() for library in libraries]


def planned_wikipedia_lossless_libraries() -> list[dict]:
    return [
        CORE_LIBRARY.to_manifest(),
        ENGLISH_TEXT_LIBRARY.to_manifest(),
        WIKIMEDIA_XML_LIBRARY.to_manifest(),
    ]
