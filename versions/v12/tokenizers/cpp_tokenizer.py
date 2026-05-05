"""Lossless C++ tokenizer for Spectrum encoding."""

from __future__ import annotations

from tokenizers.code_tokenizer import tokenise_c_like


def tokenise_cpp(source: str) -> list[str]:
    return tokenise_c_like(source)
