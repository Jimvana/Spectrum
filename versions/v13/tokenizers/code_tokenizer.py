"""
Shared lossless tokenizers for C-like languages, shell scripts, and config
formats.

These scanners are intentionally lexical. They promote dictionary-known
identifiers and operators while preserving exact reconstruction with
``"".join(tokens) == source``.
"""

from __future__ import annotations

import re

import dictionary as D


_C_LIKE_SCANNER = re.compile(r'''
    ( //[^\n]*             )   # G1: line comment
  | ( /\*.*?\*/            )   # G2: block comment
  | ( R"\([^)]*\).*?\)"    )   # G3: simple C++ raw string
  | ( "[^"\\]*(?:\\.[^"\\]*)*" )  # G4: double-quoted string
  | ( '[^'\\]*(?:\\.[^'\\]*)*' )  # G5: char / single-quoted literal
  | ( 0[xX][0-9a-fA-F_']+[a-zA-Z0-9_]* )  # G6: hex number
  | ( 0[bB][01_']+[a-zA-Z0-9_]*          )  # G7: binary number
  | ( \d[\d_']*\.?[\d_']*[a-zA-Z0-9_]*   )  # G8: decimal / float
  | ( ::|->\*|->|<<=|>>=|==|!=|<=|>=|\+=|-=|\*=|/=|%=|&=|\|=|\^=|&&|\|\||\+\+|--|<<|>> )
  | ( \n                  )   # G10: newline
  | ( [ \t\r]+            )   # G11: horizontal whitespace
  | ( [A-Za-z_][A-Za-z0-9_]* ) # G12: identifier / keyword
  | ( .                   )   # G13: fallback char
''', re.VERBOSE | re.DOTALL)


_SHELL_SCANNER = re.compile(r'''
    ( \#[^\n]*             )   # G1: comment
  | ( \$\{[^}]*\}          )   # G2: braced variable
  | ( \$[A-Za-z_][A-Za-z0-9_]* ) # G3: simple variable
  | ( "(?:\\.|[^"\\])*"   )   # G4: double-quoted string
  | ( '(?:\\.|[^'\\])*'   )   # G5: single-quoted string
  | ( \d+                  )   # G6: number
  | ( &&|\|\||;;|;&|;;&|<<-|<<|>>|[|&;(){}<>=] ) # G7: shell operators
  | ( \n                  )   # G8: newline
  | ( [ \t\r]+            )   # G9: horizontal whitespace
  | ( [A-Za-z_][A-Za-z0-9_-]* ) # G10: word
  | ( .                   )   # G11: fallback char
''', re.VERBOSE | re.DOTALL)


_POWERSHELL_SCANNER = re.compile(r'''
    ( \#[^\n]*             )   # G1: comment
  | ( \$\{[^}]*\}          )   # G2: braced variable
  | ( \$_                  )   # G3: current pipeline item
  | ( \$[A-Za-z_][A-Za-z0-9_:]* ) # G4: variable / scoped variable
  | ( @"(?:.|\n)*?"@       )   # G5: double-quoted here-string
  | ( @'(?:.|\n)*?'@       )   # G6: single-quoted here-string
  | ( "(?:`.|[^"`])*"     )   # G7: double-quoted string
  | ( '(?:''|[^'])*'       )   # G8: single-quoted string
  | ( -[A-Za-z][A-Za-z0-9]* ) # G9: comparison/logical/operator token
  | ( [A-Za-z][A-Za-z0-9]*-(?:[A-Za-z][A-Za-z0-9]*-?)* ) # G10: cmdlet
  | ( \d+(?:\.\d+)?        )   # G11: number
  | ( \|\||&&|::|=>|[|&;(){}\[\]<>=,.] ) # G12: operators/punctuation
  | ( \n                   )   # G13: newline
  | ( [ \t\r]+             )   # G14: horizontal whitespace
  | ( [A-Za-z_][A-Za-z0-9_]* ) # G15: keyword / identifier
  | ( .                    )   # G16: fallback char
''', re.VERBOSE | re.DOTALL)


_CONFIG_SCANNER = re.compile(r'''
    ( \#[^\n]*|//[^\n]*    )   # G1: comment
  | ( "(?:\\.|[^"\\])*"   )   # G2: double-quoted string
  | ( '(?:\\.|[^'\\])*'   )   # G3: single-quoted string
  | ( \d+(?:\.\d+)?       )   # G4: number
  | ( [{}\[\](),:=]       )   # G5: common config punctuation
  | ( \n                  )   # G6: newline
  | ( [ \t\r]+            )   # G7: horizontal whitespace
  | ( [A-Za-z_][A-Za-z0-9_-]* ) # G8: bare key / literal
  | ( .                   )   # G9: fallback char
''', re.VERBOSE | re.DOTALL)


def _emit_token_or_chars(value: str, tokens: list[str]) -> None:
    if value in D.TOKEN_TO_RGB:
        tokens.append(value)
    else:
        tokens.extend(value)


def _emit_chars(value: str, tokens: list[str]) -> None:
    tokens.extend(value)


def _emit_config_string(value: str, tokens: list[str]) -> None:
    inner = value[1:-1]
    if re.fullmatch(r"[A-Za-z_][A-Za-z0-9_-]*", inner) and inner in D.TOKEN_TO_RGB:
        tokens.append(value[0])
        tokens.append(inner)
        tokens.append(value[-1])
    else:
        _emit_chars(value, tokens)


def tokenise_c_like(source: str) -> list[str]:
    tokens: list[str] = []
    for match in _C_LIKE_SCANNER.finditer(source):
        group = match.lastindex
        value = match.group()
        if group in (1, 2, 3, 4, 5, 6, 7, 8):
            _emit_chars(value, tokens)
        elif group in (9, 12):
            _emit_token_or_chars(value, tokens)
        elif group in (10, 11):
            tokens.extend(value)
        else:
            tokens.append(value)
    return tokens


def tokenise_shell_like(source: str) -> list[str]:
    tokens: list[str] = []
    for match in _SHELL_SCANNER.finditer(source):
        group = match.lastindex
        value = match.group()
        if group in (1, 2, 3, 4, 5, 6):
            _emit_chars(value, tokens)
        elif group in (7, 10):
            _emit_token_or_chars(value, tokens)
        elif group in (8, 9):
            tokens.extend(value)
        else:
            tokens.append(value)
    return tokens


def tokenise_powershell_like(source: str) -> list[str]:
    tokens: list[str] = []
    for match in _POWERSHELL_SCANNER.finditer(source):
        group = match.lastindex
        value = match.group()
        if group in (1, 2, 4, 5, 6, 7, 8, 11):
            _emit_chars(value, tokens)
        elif group in (3, 9, 10, 12, 15):
            _emit_token_or_chars(value, tokens)
        elif group in (13, 14):
            tokens.extend(value)
        else:
            tokens.append(value)
    return tokens


def tokenise_config_like(source: str) -> list[str]:
    tokens: list[str] = []
    for match in _CONFIG_SCANNER.finditer(source):
        group = match.lastindex
        value = match.group()
        if group == 1:
            _emit_chars(value, tokens)
        elif group in (2, 3):
            _emit_config_string(value, tokens)
        elif group == 4:
            _emit_chars(value, tokens)
        elif group in (5, 8):
            _emit_token_or_chars(value, tokens)
        elif group in (6, 7):
            tokens.extend(value)
        else:
            tokens.append(value)
    return tokens
