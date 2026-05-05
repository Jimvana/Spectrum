"""
Spectrum Algo — TypeScript Tokenizer
Converts TypeScript source into a flat list of string tokens suitable for
Spectrum encoding.

TypeScript is a strict superset of JavaScript, so this tokenizer reuses the
same single-pass regex scanner as the JS tokenizer.  The extra TS-specific
keywords (interface, enum, namespace, declare, readonly, abstract, implements,
keyof, infer, never, unknown, override, satisfies, asserts, accessor, using)
are handled purely through dictionary look-up — they are identifiers to the
scanner and either resolve to a known dict colour or fall through char-by-char.

Additional TS syntax notes:
  - Generic type params `<T>` → `<` and `>` are already in SYMBOLS
  - Non-null assertion `!` → already in TEXT_PUNCTUATION
  - Optional chaining `?.` and nullish coalescing `??` → already in JS_OPERATORS
  - Type assertion `as` → already in Python KEYWORDS
  - Decorators `@Foo` → `@` already in SYMBOLS; identifier is handled normally
  - Triple-slash directives `/// <reference ...>` → emitted char-by-char
    (treated as line comments by the scanner)

Round-trip guarantee: ''.join(tokens) == source
"""

import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import dictionary as D

# ---------------------------------------------------------------------------
# Master scanner regex  (identical to JS scanner — TS is a JS superset)
# Order matters — longer / more specific patterns first.
# ---------------------------------------------------------------------------

_SCANNER = re.compile(r'''
    ( [ \t\r]+       )   # G1:  horizontal whitespace
  | ( \n             )   # G2:  newline
  | ( //[^\n]*       )   # G3:  line comment  (incl. /// TS directives)
  | ( /\*.*?\*/      )   # G4:  block comment
  | ( `[^`\\]*(?:\\.[^`\\]*)*` )  # G5: template literal
  | ( " [^"\\]* (?: \\. [^"\\]* )* " )   # G6: double-quoted string
  | ( ' [^'\\]* (?: \\. [^'\\]* )* ' )   # G7: single-quoted string
  | ( 0[xX][0-9a-fA-F]+  )  # G8:  hex literal
  | ( \d+ \.? \d*        )  # G9:  decimal number
  | ( ===|!==|=>|\?\.|\ ??|\+\+|--|<=|>=|&&|\|\| )  # G10: multi-char ops
  | ( [+\-*/%&|^~<>!?:;,.=\[\]{}()\\ ] )  # G11: single-char ops / punct
  | ( [a-zA-Z_$] [\w$]* )   # G12: identifier or keyword
  | ( .              )   # G13: fallback — any other character
''', re.VERBOSE | re.DOTALL)


# ---------------------------------------------------------------------------
# Helpers  (same as JS tokenizer)
# ---------------------------------------------------------------------------

def _emit_chars(s: str, tokens: list[str]) -> None:
    tokens.extend(s)


def _emit_token_or_chars(tok: str, tokens: list[str]) -> None:
    if tok in D.TOKEN_TO_RGB:
        tokens.append(tok)
    else:
        _emit_chars(tok, tokens)


# ---------------------------------------------------------------------------
# Main tokeniser
# ---------------------------------------------------------------------------

def tokenise_ts(source: str) -> list[str]:
    """
    Tokenise a TypeScript source string into a flat list of Spectrum tokens.

    Round-trip guarantee: ''.join(tokens) == source
    """
    tokens: list[str] = []

    for m in _SCANNER.finditer(source):
        g   = m.lastindex
        val = m.group()

        if g == 1:          # horizontal whitespace
            for ch in val:
                tokens.append(ch)

        elif g == 2:        # newline
            tokens.append('\n')

        elif g in (3, 4):   # line / block comments (incl. /// directives)
            _emit_chars(val, tokens)

        elif g in (5, 6, 7):  # template literals / strings
            _emit_chars(val, tokens)

        elif g in (8, 9):   # numbers
            for ch in val:
                tokens.append(ch)

        elif g == 10:       # multi-char operators
            _emit_token_or_chars(val, tokens)

        elif g == 11:       # single-char operators / punctuation
            _emit_token_or_chars(val, tokens)

        elif g == 12:       # identifier or keyword (TS keywords hit the dict)
            _emit_token_or_chars(val, tokens)

        else:               # g == 13: fallback
            tokens.append(val)

    return tokens


# ---------------------------------------------------------------------------
# Verification
# ---------------------------------------------------------------------------

def verify_roundtrip(source: str) -> bool:
    tokens = tokenise_ts(source)
    return ''.join(tokens) == source


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: ts_tokenizer.py <file.ts>")
        sys.exit(1)

    src    = Path(sys.argv[1]).read_text(encoding="utf-8", errors="replace")
    tokens = tokenise_ts(src)

    dict_hits = sum(1 for t in tokens if t in D.TOKEN_TO_RGB)
    total     = len(tokens)
    rt_ok     = verify_roundtrip(src)

    print(f"Tokens:       {total:,}")
    print(f"Dict hits:    {dict_hits:,}  ({100*dict_hits/total:.1f}%)")
    print(f"Fallback:     {total-dict_hits:,}  ({100*(total-dict_hits)/total:.1f}%)")
    print(f"Round-trip:   {'✓ OK' if rt_ok else '✗ FAIL'}")
