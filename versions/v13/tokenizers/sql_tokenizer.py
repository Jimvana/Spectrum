"""
Spectrum Algo — SQL Tokenizer
Converts SQL source into a flat list of string tokens suitable for Spectrum
encoding.

The tokenizer uses a single-pass regex scanner.  Token categories:

  - Line comments:    -- … \n   (emitted char-by-char)
  - Block comments:   /* … */   (emitted char-by-char)
  - Strings:          '…'  "…"  $$…$$  (emitted char-by-char)
  - Quoted identifiers: `…`  […]  "…"  (emitted char-by-char)
  - Numbers:          integers, decimals, hex (emitted char-by-char)
  - Multi-char ops:   <>, !=, <=, >=, ||, ::  (dict lookup or char-by-char)
  - Single-char ops:  = < > ( ) , ; . * + - /  (dict lookup or char)
  - Keywords:         SELECT, FROM, WHERE, … (UPPERCASE dict lookup)
    SQL is case-insensitive, so the tokenizer normalises keywords to
    UPPERCASE for the dict lookup.  To preserve round-trip fidelity the
    ORIGINAL characters are emitted — but as a single token whose identity
    is the uppercase form.  Internally, for multi-char keywords that match
    exactly as-written (already uppercase), we emit the token directly.
    For mixed / lowercase keywords we fall back to char-by-char so the
    original casing is faithfully preserved.
  - Identifiers:      table and column names (dict lookup then char-by-char)

Round-trip guarantee: ''.join(tokens) == source

Strategy for case normalisation:
  When a word-token is found:
    1. Try exact match in TOKEN_TO_RGB (covers uppercase SQL keywords).
    2. Try uppercase match (if uppercase is in dict, still emit ORIGINAL string
       char-by-char — we do NOT change the source).
  This means uppercase SQL keywords get dict hits; lowercase / mixed-case fall
  back to char-by-char.  This is intentional — it rewards correct SQL style
  (uppercase keywords) with better compression while keeping round-trip clean.
"""

import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import dictionary as D

# ---------------------------------------------------------------------------
# Master scanner regex
# ---------------------------------------------------------------------------

_SCANNER = re.compile(r'''
    ( --[^\n]*         )   # G1:  line comment
  | ( /\*.*?\*/        )   # G2:  block comment (non-greedy, DOTALL)
  | ( \$\$.*?\$\$      )   # G3:  PostgreSQL dollar-quoted string
  | ( ' [^'\\]* (?: ''  [^'\\]* )* ' )  # G4: single-quoted string (SQL escapes '')
  | ( " [^"\\]* (?: \\" [^"\\]* )* " )  # G5: double-quoted string / identifier
  | ( `[^`]*`          )   # G6:  MySQL backtick identifier
  | ( \[[^\]]*\]       )   # G7:  SQL Server bracket identifier
  | ( 0[xX][0-9a-fA-F]+ )  # G8:  hex number
  | ( \d+ \.? \d*      )   # G9:  decimal number
  | ( <> | != | <= | >= | \|\| | ::  )  # G10: multi-char operators
  | ( [=<>()+\-*/%,;.] )   # G11: single-char operators / punctuation
  | ( \n               )   # G12: newline
  | ( [ \t\r]+         )   # G13: horizontal whitespace
  | ( [a-zA-Z_] [\w]*  )   # G14: identifier or keyword
  | ( .                )   # G15: fallback
''', re.VERBOSE | re.DOTALL)

# SQL multi-char operators not already in the dictionary
_SQL_OPS = {"<>", "!=", "<=", ">=", "||", "::"}


# ---------------------------------------------------------------------------
# Helpers
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

def tokenise_sql(source: str) -> list[str]:
    """
    Tokenise a SQL source string into a flat list of Spectrum tokens.

    Round-trip guarantee: ''.join(tokens) == source
    """
    tokens: list[str] = []

    for m in _SCANNER.finditer(source):
        g   = m.lastindex
        val = m.group()

        if g in (1, 2, 3):     # line comment, block comment, $$ string
            _emit_chars(val, tokens)

        elif g in (4, 5, 6, 7):  # string literals / quoted identifiers
            _emit_chars(val, tokens)

        elif g in (8, 9):       # numbers
            _emit_chars(val, tokens)

        elif g == 10:           # multi-char SQL operators
            # Some are already in the dict (<=, >=, ||), some are SQL-only (<>)
            _emit_token_or_chars(val, tokens)

        elif g == 11:           # single-char operators / punctuation
            _emit_token_or_chars(val, tokens)

        elif g == 12:           # newline
            tokens.append('\n')

        elif g == 13:           # horizontal whitespace
            for ch in val:
                tokens.append(ch)

        elif g == 14:           # identifier or keyword
            upper = val.upper()
            if upper in D.TOKEN_TO_RGB:
                # It's a recognised SQL keyword — emit exact source text as
                # single dict token IF the source is already uppercase,
                # otherwise emit char-by-char to preserve original casing.
                if val == upper:
                    tokens.append(val)   # uppercase source → single dict token
                else:
                    _emit_chars(val, tokens)  # lowercase/mixed → char-by-char
            else:
                # Not a SQL keyword — regular identifier, emit via dict or chars
                _emit_token_or_chars(val, tokens)

        else:                   # g == 15: fallback
            tokens.append(val)

    return tokens


# ---------------------------------------------------------------------------
# Verification
# ---------------------------------------------------------------------------

def verify_roundtrip(source: str) -> bool:
    tokens = tokenise_sql(source)
    return ''.join(tokens) == source


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: sql_tokenizer.py <file.sql>")
        sys.exit(1)

    src    = Path(sys.argv[1]).read_text(encoding="utf-8", errors="replace")
    tokens = tokenise_sql(src)

    dict_hits = sum(1 for t in tokens if t in D.TOKEN_TO_RGB)
    total     = len(tokens)
    rt_ok     = verify_roundtrip(src)

    # Show keyword hit rate separately
    kw_tokens = [t for t in tokens if t in D.SQL_KEYWORDS or t in D.SQL_FUNCTIONS]

    print(f"Tokens:       {total:,}")
    print(f"Dict hits:    {dict_hits:,}  ({100*dict_hits/total:.1f}%)")
    print(f"SQL kw hits:  {len(kw_tokens):,}")
    print(f"Fallback:     {total-dict_hits:,}  ({100*(total-dict_hits)/total:.1f}%)")
    print(f"Round-trip:   {'✓ OK' if rt_ok else '✗ FAIL'}")
