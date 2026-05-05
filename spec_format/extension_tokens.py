"""
Reserved global token ranges for Spectrum extension libraries.

Option A: each domain library owns a stable uint32 ID range. Extension tokens
are addressed by their global IDs, so the existing .spec body format can carry
them without changing the 16-byte header.
"""

from __future__ import annotations

EXTENSION_ID_BASE = 1_000_000
EXTENSION_RANGE_SIZE = 100_000

WIKIMEDIA_XML_BASE = EXTENSION_ID_BASE
MEDIAWIKI_BASE = EXTENSION_ID_BASE + EXTENSION_RANGE_SIZE

EXT_TOKEN_PREFIX = "__EXT__:"


def ext_name(library: str, literal: str) -> str:
    return f"{EXT_TOKEN_PREFIX}{library}:{literal}"


WIKIMEDIA_XML_LITERALS = [
    "<mediawiki",
    "</mediawiki>",
    "<siteinfo>",
    "</siteinfo>",
    "<page>",
    "</page>",
    "<title>",
    "</title>",
    "<ns>",
    "</ns>",
    "<id>",
    "</id>",
    "<redirect",
    "<revision>",
    "</revision>",
    "<parentid>",
    "</parentid>",
    "<timestamp>",
    "</timestamp>",
    "<contributor>",
    "</contributor>",
    "<username>",
    "</username>",
    "<ip>",
    "</ip>",
    "<comment>",
    "</comment>",
    "<model>",
    "</model>",
    "<format>",
    "</format>",
    "<text",
    "</text>",
    "<sha1>",
    "</sha1>",
]

MEDIAWIKI_LITERALS = [
    "{{",
    "}}",
    "{{{",
    "}}}",
    "[[",
    "]]",
    "[[File:",
    "[[Image:",
    "[[Media:",
    "[[Category:",
    "<ref",
    "</ref>",
    "<ref />",
    "<br />",
    "<br/>",
    "<nowiki>",
    "</nowiki>",
    "<math>",
    "</math>",
    "{|",
    "|}",
    "|-",
    "!",
    "||",
    "!!",
    "'''",
    "''",
    "====",
    "===",
    "==",
    "#REDIRECT",
    "#redirect",
]


def _build_map(base: int, library: str, literals: list[str]) -> dict[str, int]:
    return {ext_name(library, literal): base + i for i, literal in enumerate(literals)}


TOKEN_TO_EXTENSION_ID: dict[str, int] = {}
TOKEN_TO_EXTENSION_ID.update(_build_map(WIKIMEDIA_XML_BASE, "wikimedia-xml", WIKIMEDIA_XML_LITERALS))
TOKEN_TO_EXTENSION_ID.update(_build_map(MEDIAWIKI_BASE, "mediawiki", MEDIAWIKI_LITERALS))

EXTENSION_ID_TO_LITERAL: dict[int, str] = {}
for literal_index, literal in enumerate(WIKIMEDIA_XML_LITERALS):
    EXTENSION_ID_TO_LITERAL[WIKIMEDIA_XML_BASE + literal_index] = literal
for literal_index, literal in enumerate(MEDIAWIKI_LITERALS):
    EXTENSION_ID_TO_LITERAL[MEDIAWIKI_BASE + literal_index] = literal

EXTENSION_LITERAL_TO_TOKEN: dict[str, str] = {}
for token in TOKEN_TO_EXTENSION_ID:
    _, library, literal = token.split(":", 2)
    EXTENSION_LITERAL_TO_TOKEN[literal] = token

EXTENSION_MATCH_LITERALS = sorted(EXTENSION_LITERAL_TO_TOKEN, key=len, reverse=True)


def extension_token_to_id(token: str) -> int | None:
    return TOKEN_TO_EXTENSION_ID.get(token)


def extension_id_to_literal(token_id: int) -> str | None:
    return EXTENSION_ID_TO_LITERAL.get(token_id)
