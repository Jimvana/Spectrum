"""Lossless PowerShell tokenizer for Spectrum encoding."""

from __future__ import annotations

from tokenizers.code_tokenizer import tokenise_powershell_like


def tokenise_powershell(source: str) -> list[str]:
    return tokenise_powershell_like(source)
