"""Lossless JSON/YAML/TOML-style config tokenizer for Spectrum encoding."""

from __future__ import annotations

from tokenizers.code_tokenizer import tokenise_config_like


def tokenise_config(source: str) -> list[str]:
    return tokenise_config_like(source)
