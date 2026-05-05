"""
Lossless Java tokenizer for Spectrum encoding.

This is intentionally lexical rather than parser-based. It avoids treating Java
as Python source while preserving exact reconstruction via ``"".join(tokens)``.
"""

from __future__ import annotations

import re


TOKEN_RE = re.compile(
    r"[A-Za-z_$][A-Za-z0-9_$]*"
    r"|\d+(?:\.\d+)?(?:[eE][+-]?\d+)?[A-Za-z]*"
    r"|[ \t\r\n]+"
    r"|.",
    re.DOTALL,
)


def tokenise_java(source: str) -> list[str]:
    return TOKEN_RE.findall(source)
