"""
Wikimedia / MediaWiki tokenization helpers.

This tokenizer preserves the source exactly while promoting repeated XML and
MediaWiki syntax markers to extension-library token IDs.
"""

from __future__ import annotations

import re

import dictionary as D
from tokenizers.text_tokenizer import tokenize_text

_CORE_WIKI_LITERALS = sorted(
    set(D.XML_TOKENS) | set(D.MEDIAWIKI_TOKENS) | {"'''", "===", "=="},
    key=len,
    reverse=True,
)

_WIKI_RE = re.compile("|".join(re.escape(literal) for literal in _CORE_WIKI_LITERALS))


def tokenize_wiki_source(source: str) -> list[str]:
    tokens: list[str] = []
    last_end = 0

    for match in _WIKI_RE.finditer(source):
        if match.start() > last_end:
            tokens.extend(tokenize_text(source[last_end:match.start()]))
        tokens.append(match.group(0))
        last_end = match.end()

    if last_end < len(source):
        tokens.extend(tokenize_text(source[last_end:]))

    return tokens
