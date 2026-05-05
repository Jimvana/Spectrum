"""
Spectrum Algo — CSS Tokenizer
Converts CSS source into a flat list of string tokens suitable for
Spectrum encoding.

The tokenizer uses a single-pass regex scanner. Token categories:

  - Block comments:      /* … */     (emitted char-by-char)
  - Strings:             "…" '…'     (emitted char-by-char)
  - At-rule keywords:    @media etc. (dict lookup as full "@word" token)
  - CSS identifiers:     font-size, background-color, -webkit-transform etc.
                         (dict lookup; char-by-char fallback if not found)
  - CSS custom props:    --variable-name  (char-by-char — unique per project)
  - Numbers + units:     10px, 1.5em, 100%  (digits + unit chars individually)
  - Whitespace/newline:  ' ', '\\t', '\\n'  (dict tokens)
  - Punctuation:         { } : ; , ( ) etc.  (dict lookup or single char)
  - Anything else:       single char

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
    ( /\*.*?\*/                    )   # G1: block comment (non-greedy, DOTALL)
  | ( "(?:[^"\\]|\\.)*"            )   # G2: double-quoted string
  | ( '(?:[^'\\]|\\.)*'            )   # G3: single-quoted string
  | ( @[\w-]+                      )   # G4: at-rule keyword (@media, @keyframes …)
  | ( --[\w-]+                     )   # G5: CSS custom property (--var-name)
  | ( -?[a-zA-Z_][\w-]*            )   # G6: CSS identifier (may contain hyphens)
  | ( \d+\.?\d*[a-zA-Z%]*          )   # G7: number with optional unit (10px, 1.5em, 100%)
  | ( \n                           )   # G8: newline
  | ( [ \t\r]+                     )   # G9: horizontal whitespace
  | ( .                            )   # G10: anything else (single char)
''', re.VERBOSE | re.DOTALL)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _emit_chars(s: str, tokens: list[str]) -> None:
    """Emit every character of s individually."""
    tokens.extend(s)


def _emit_token_or_chars(tok: str, tokens: list[str]) -> None:
    """Emit tok as a single dict token if known, else char-by-char."""
    if tok in D.TOKEN_TO_RGB:
        tokens.append(tok)
    else:
        _emit_chars(tok, tokens)


def _emit_number(num: str, tokens: list[str]) -> None:
    """
    Emit a CSS number+unit like '10px', '1.5em', '100%'.
    Digits and '.' use dict tokens where available; unit letters are fallback.
    """
    for ch in num:
        tokens.append(ch)  # digits → dict token; letters/% → fallback char


# ---------------------------------------------------------------------------
# Main tokeniser
# ---------------------------------------------------------------------------

def tokenise_css(source: str) -> list[str]:
    """
    Tokenise a CSS source string into a flat list of Spectrum tokens.

    Round-trip guarantee: ''.join(tokens) == source
    """
    tokens: list[str] = []

    for m in _SCANNER.finditer(source):
        g   = m.lastindex
        val = m.group()

        if g in (1,):          # block comment — char by char
            _emit_chars(val, tokens)

        elif g in (2, 3):      # string literals — char by char
            _emit_chars(val, tokens)

        elif g == 4:           # at-rule keyword: "@media", "@keyframes", …
            _emit_token_or_chars(val, tokens)

        elif g == 5:           # CSS custom property: --primary-color (char by char)
            _emit_chars(val, tokens)

        elif g == 6:           # CSS identifier (possibly hyphenated)
            _emit_token_or_chars(val, tokens)

        elif g == 7:           # number with optional unit
            _emit_number(val, tokens)

        elif g == 8:           # newline
            tokens.append('\n')

        elif g == 9:           # horizontal whitespace
            for ch in val:
                tokens.append(ch)

        else:                  # g == 10: punctuation or any other char
            tokens.append(val)

    return tokens


# ---------------------------------------------------------------------------
# Verification
# ---------------------------------------------------------------------------

def verify_roundtrip(source: str) -> bool:
    tokens = tokenise_css(source)
    return ''.join(tokens) == source


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: css_tokenizer.py <file.css>")
        sys.exit(1)

    src   = Path(sys.argv[1]).read_text(encoding="utf-8", errors="replace")
    tokens = tokenise_css(src)

    dict_hits = sum(1 for t in tokens if t in D.TOKEN_TO_RGB)
    total     = len(tokens)
    rt_ok     = verify_roundtrip(src)

    print(f"Tokens:       {total:,}")
    print(f"Dict hits:    {dict_hits:,}  ({100*dict_hits/total:.1f}%)")
    print(f"Fallback:     {total-dict_hits:,}  ({100*(total-dict_hits)/total:.1f}%)")
    print(f"Round-trip:   {'✓ OK' if rt_ok else '✗ FAIL'}")
