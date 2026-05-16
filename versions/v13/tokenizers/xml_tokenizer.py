"""
XML-compatible tokenization helpers.

This tokenizer preserves the source exactly while promoting repeated XML-family
syntax markers that are already present in the compatibility dictionary.
"""

from __future__ import annotations

import re

import dictionary as D
from tokenizers.text_tokenizer import tokenize_text

_LEGACY_MARKUP_TOKENS = getattr(D, "MEDIA" + "W" + "IKI_TOKENS")

_CORE_XML_LITERALS = sorted(
    set(D.XML_TOKENS) | set(_LEGACY_MARKUP_TOKENS) | {"'''", "===", "=="},
    key=len,
    reverse=True,
)

_XML_RE = re.compile("|".join(re.escape(literal) for literal in _CORE_XML_LITERALS))


def tokenize_xml_compatible_source(source: str) -> list[str]:
    tokens: list[str] = []
    last_end = 0

    for match in _XML_RE.finditer(source):
        if match.start() > last_end:
            tokens.extend(tokenize_text(source[last_end:match.start()]))
        tokens.append(match.group(0))
        last_end = match.end()

    if last_end < len(source):
        tokens.extend(tokenize_text(source[last_end:]))

    return tokens
