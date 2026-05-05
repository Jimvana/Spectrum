"""Lossless shell/Bash tokenizer for Spectrum encoding."""

from __future__ import annotations

from tokenizers.code_tokenizer import tokenise_shell_like


def tokenise_shell(source: str) -> list[str]:
    return tokenise_shell_like(source)
