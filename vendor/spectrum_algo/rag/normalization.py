"""
Shared retrieval normalization for Spectrum RAG.

This module does not change `.spec` payload bytes. It only adds searchable
alias token IDs for retrieval indexes and queries, so lossless decoding remains
owned by the core codec.
"""

from __future__ import annotations

import html
import re
import unicodedata

import dictionary as D
from spec_format.spec_encoder import tokens_to_ids
from tokenizers.text_tokenizer import tokenize_text


_CAMEL_ACRONYM_RE = re.compile(r"(?<=[A-Z])(?=[A-Z][a-z])")
_CAMEL_BOUNDARY_RE = re.compile(r"(?<=[a-z])(?=[A-Z])")
_LETTER_DIGIT_RE = re.compile(r"(?<=[A-Za-z])(?=\d)|(?<=\d)(?=[A-Za-z])")
_SEPARATOR_RE = re.compile(r"[_\-/]+")
_APOSTROPHE_RE = re.compile(r"[’`]")
_POSSESSIVE_RE = re.compile(r"\b([A-Za-z]+)'s\b", re.IGNORECASE)
_CONTRACTION_RE = re.compile(r"(?<=\w)'(?=\w)")
_MULTISPACE_RE = re.compile(r"\s+")
_WORD_RE = re.compile(r"\b[A-Za-z]{4,}\b")
_CANDIDATE_RE = re.compile(
    r"\b[A-Za-z]+(?:[A-Z][a-z]+)+\b"
    r"|\b[A-Za-z0-9]+(?:[_\-/][A-Za-z0-9]+)+\b"
    r"|\b[A-Za-z]+[’'][A-Za-z]+\b"
    r"|[A-Za-z]+&[A-Za-z]+;[A-Za-z]*"
)


def _word_aliases(word: str) -> list[str]:
    """Return conservative retrieval aliases for simple English inflections."""
    lower = word.lower()
    aliases: list[str] = []

    def add(value: str) -> None:
        if value and value != lower and value in D.TOKEN_TO_SPEC_ID and value not in aliases:
            aliases.append(value)

    if lower.endswith("ies") and len(lower) > 4:
        add(lower[:-3] + "y")
    if lower.endswith("ers") and len(lower) > 4:
        add(lower[:-1])
    if lower.endswith("s") and not lower.endswith("ss") and len(lower) > 4:
        add(lower[:-1])
    if lower.endswith("ing") and len(lower) > 5:
        stem = lower[:-3]
        add(stem)
        if len(stem) > 2 and stem[-1] == stem[-2]:
            add(stem[:-1])
        add(stem + "e")
    if lower.endswith("ed") and len(lower) > 4:
        stem = lower[:-2]
        add(stem)
        add(stem + "e")
    return aliases


def dict_token_ids_from_text(text: str) -> list[int]:
    """Return dictionary token IDs from the plain-text Spectrum tokenizer."""
    return [
        token_id for token_id in tokens_to_ids(tokenize_text(text))
        if token_id < D.SPEC_ID_ASCII_BASE
    ]


def _is_meaningful_alias_id(token_id: int) -> bool:
    token = D.SPEC_ID_TO_TOKEN.get(token_id, "")
    if not token or token.startswith("CTRL:"):
        return False
    if token.isspace():
        return False
    return any(ch.isalnum() for ch in token)


def normalized_text_variants(text: str) -> list[str]:
    """Return retrieval-only text variants for common query/document mismatches."""
    variants: list[str] = []
    seen: set[str] = set()

    def add(value: str) -> None:
        value = _MULTISPACE_RE.sub(" ", value).strip()
        if value and value != text and value not in seen:
            seen.add(value)
            variants.append(value)

    unescaped = html.unescape(text)
    add(unescaped)

    folded = unicodedata.normalize("NFKD", unescaped).encode("ascii", "ignore").decode("ascii")
    add(folded)

    apostrophe_normalized = _APOSTROPHE_RE.sub("'", folded)
    add(apostrophe_normalized)

    possessive_split = _POSSESSIVE_RE.sub(r"\1", apostrophe_normalized)
    add(possessive_split)

    contraction_joined = _CONTRACTION_RE.sub("", possessive_split)
    add(contraction_joined)

    separated = _SEPARATOR_RE.sub(" ", contraction_joined)
    separated = _CAMEL_ACRONYM_RE.sub(" ", separated)
    separated = _CAMEL_BOUNDARY_RE.sub(" ", separated)
    separated = _LETTER_DIGIT_RE.sub(" ", separated)
    add(separated)

    lower = separated.lower()
    add(lower)

    return variants


def retrieval_token_ids(text: str, include_aliases: bool = True) -> list[int]:
    """
    Return token IDs used for retrieval.

    The base IDs preserve the current Spectrum tokenizer output. Alias IDs are
    added once each, after the base stream, to avoid over-weighting normalized
    variants while still making mismatched forms searchable.
    """
    ids = dict_token_ids_from_text(text)
    if not include_aliases:
        return ids

    seen = set(ids)
    spans = _CANDIDATE_RE.findall(text)
    spans.extend(_WORD_RE.findall(text))
    if len(text) <= 256:
        spans.append(text)

    for span in dict.fromkeys(spans):
        for alias in _word_aliases(span):
            for token_id in dict_token_ids_from_text(alias):
                if token_id not in seen and _is_meaningful_alias_id(token_id):
                    ids.append(token_id)
                    seen.add(token_id)
        for variant in normalized_text_variants(span):
            for token_id in dict_token_ids_from_text(variant):
                if token_id not in seen and _is_meaningful_alias_id(token_id):
                    ids.append(token_id)
                    seen.add(token_id)
        for token_id in dict_token_ids_from_text(span):
            if token_id not in seen and _is_meaningful_alias_id(token_id):
                ids.append(token_id)
                seen.add(token_id)
    return ids
