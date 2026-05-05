"""
Spectrum Algo — JavaScript Tokenizer
Converts JavaScript source into a flat list of string tokens suitable for
Spectrum encoding.

The tokenizer uses a single-pass regex scanner. Token categories:

  - Whitespace:           ' ', '\\n', '\\t' etc.
  - Line comments:        // … \\n   (emitted char-by-char)
  - Block comments:       /* … */   (emitted char-by-char)
  - Template literals:    `…`       (emitted char-by-char)
  - Strings:              "…" '…'   (emitted char-by-char)
  - Numbers:              digits    (emitted as digit tokens + fallback)
  - Multi-char operators: ===, !==, =>, ++ etc. (dict lookup)
  - Single-char operators:(, ), etc. (dict lookup)
  - Identifiers/keywords: let, const, function, myVar etc. (dict lookup or fallback)

Round-trip guarantee: ''.join(tokens) == source
"""

import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import dictionary as D

# ---------------------------------------------------------------------------
# Master scanner regex  (order matters — longer patterns first)
# ---------------------------------------------------------------------------

_SCANNER = re.compile(r'''
    ( [ \t\r]+       )   # G1: horizontal whitespace
  | ( \n             )   # G2: newline
  | ( //[^\n]*       )   # G3: line comment
  | ( /\*.*?\*/      )   # G4: block comment  (non-greedy, DOTALL below)
  | ( `[^`\\]*(?:\\.[^`\\]*)*` )  # G5: template literal
  | ( " [^"\\]* (?: \\. [^"\\]* )* " )   # G6: double-quoted string
  | ( ' [^'\\]* (?: \\. [^'\\]* )* ' )   # G7: single-quoted string
  | ( 0[xX][0-9a-fA-F]+ )  # G8: hex number
  | ( \d+ \.? \d*   )   # G9: decimal number
  | ( ===|!==|=>|\?\.|\ ??|\+\+|--|<=|>=|&&|\|\| )  # G10: multi-char ops
  | ( [+\-*/%&|^~<>!?:;,.=\[\]{}()\\ ] )  # G11: single-char ops/punct
  | ( [a-zA-Z_$] [\w$]* )  # G12: identifier or keyword
  | ( .             )   # G13: fallback — any other character
''', re.VERBOSE | re.DOTALL)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _emit_chars(s: str, tokens: list[str]) -> None:
    """Emit string s character by character."""
    tokens.extend(s)


def _emit_whitespace(ws: str, tokens: list[str]) -> None:
    """Emit whitespace, using dictionary tokens for recognised chars."""
    for ch in ws:
        tokens.append(ch)   # ' ', '\t', '\r' — dict or fallback, same result


def _emit_token_or_chars(tok: str, tokens: list[str]) -> None:
    """Emit tok as a single dict token if known, else char-by-char."""
    if tok in D.TOKEN_TO_RGB:
        tokens.append(tok)
    else:
        _emit_chars(tok, tokens)


def _emit_number(num: str, tokens: list[str]) -> None:
    """Emit a numeric literal — digits get dict tokens, '.' is a symbol."""
    for ch in num:
        if ch in D.TOKEN_TO_RGB:
            tokens.append(ch)
        else:
            tokens.append(ch)


# ---------------------------------------------------------------------------
# Main tokeniser
# ---------------------------------------------------------------------------

def tokenise_js(source: str) -> list[str]:
    """
    Tokenise a JavaScript source string into a flat list of Spectrum tokens.

    Round-trip guarantee: ''.join(tokens) == source
    """
    tokens: list[str] = []

    for m in _SCANNER.finditer(source):
        g = m.lastindex
        val = m.group()

        if g == 1:   # horizontal whitespace
            _emit_whitespace(val, tokens)

        elif g == 2:  # newline
            tokens.append('\n')

        elif g in (3, 4):  # comments — emit verbatim
            _emit_chars(val, tokens)

        elif g in (5, 6, 7):  # template / string literals — verbatim
            _emit_chars(val, tokens)

        elif g in (8, 9):  # numbers
            _emit_number(val, tokens)

        elif g == 10:  # multi-char operators
            _emit_token_or_chars(val, tokens)

        elif g == 11:  # single-char operators / punctuation
            _emit_token_or_chars(val, tokens)

        elif g == 12:  # identifier or keyword
            _emit_token_or_chars(val, tokens)

        else:  # g == 13: anything else
            tokens.append(val)

    return tokens


# ---------------------------------------------------------------------------
# Verification
# ---------------------------------------------------------------------------

def verify_roundtrip(source: str) -> bool:
    tokens = tokenise_js(source)
    return ''.join(tokens) == source


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: js_tokenizer.py <file.js>")
        sys.exit(1)

    src = Path(sys.argv[1]).read_text(encoding="utf-8", errors="replace")
    tokens = tokenise_js(src)

    dict_hits = sum(1 for t in tokens if t in D.TOKEN_TO_RGB)
    total     = len(tokens)
    rt_ok     = verify_roundtrip(src)

    print(f"Tokens:       {total:,}")
    print(f"Dict hits:    {dict_hits:,}  ({100*dict_hits/total:.1f}%)")
    print(f"Fallback:     {total-dict_hits:,}  ({100*(total-dict_hits)/total:.1f}%)")
    print(f"Round-trip:   {'✓ OK' if rt_ok else '✗ FAIL'}")
