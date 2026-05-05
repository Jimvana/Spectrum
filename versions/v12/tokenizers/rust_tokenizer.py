"""
Spectrum Algo — Rust Tokenizer
Converts Rust source into a flat list of string tokens suitable for Spectrum
encoding.

The tokenizer uses a single-pass regex scanner.  Token categories:

  - Line comments:       //  …  \n   (emitted char-by-char)
    Doc comments:        ///  //!   (also line-comment pattern — char-by-char)
  - Block comments:      /* … */    (emitted char-by-char, non-nested)
  - Raw strings:         r"…"  r#"…"#  r##"…"##  (char-by-char)
  - Byte strings:        b"…"  b'…'    (char-by-char)
  - Normal strings:      "…"          (char-by-char)
  - Char / lifetime:     'x'  '\n'  'a  (see below)
    Lifetime annotations ('a, 'static, '_) are emitted char-by-char because
    they include the leading apostrophe which is part of their identity.
  - Numbers:             1_000  0x1F  0o17  0b101  1.5f64  (char-by-char)
  - Path separator:      ::  (dict lookup — RUST_KEYWORDS entry)
  - Multi-char ops:      ->  =>  <=  >=  !=  ==  +=  -=  *=  /=  ..  ...
                         ..=  <<  >>  &&  ||  (dict lookup or char-by-char)
  - Single-char ops:     standard punctuation (dict lookup or char)
  - Attributes:          #[…]  #![…]  (emitted char-by-char as part of scan)
  - Identifiers/keywords (dict lookup; Rust keywords in dictionary get colour;
                          user identifiers fall back char-by-char if not found)
  - Macro invocations:   name!  → `name` as identifier, then `!` separately

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
    # Comments
    ( //[^\n]*             )   # G1:  line comment (incl. /// doc comments)
  | ( /\*.*?\*/            )   # G2:  block comment (non-greedy, DOTALL)

    # Raw strings: r"", r#""#, r##""## etc.
  | ( r\#{0,6}".*?"\#{0,6} )   # G3:  raw string

    # Byte / normal strings
  | ( b"[^"\\]*(?:\\.[^"\\]*)*"  )  # G4: byte string
  | ( b'[^'\\]*(?:\\.[^'\\]*)*'  )  # G5: byte char
  | ( "[^"\\]*(?:\\.[^"\\]*)*"   )  # G6: normal string

    # Char literals vs lifetime annotations:
    # Char: single char or escape followed by closing '
    # Lifetime: ' followed by identifier (no closing ' immediately after)
  | ( ' (?: [^'\\] | \\. ) '    )  # G7:  char literal  e.g. 'a'  '\n'
  | ( ' [a-zA-Z_] \w*            )  # G8:  lifetime annotation  e.g. 'a  'static

    # Numbers (allow _ separators and type suffixes)
  | ( 0[xX][0-9a-fA-F_]+[a-z0-9]* )  # G9:  hex number
  | ( 0[oO][0-7_]+[a-z0-9]*         )  # G10: octal number
  | ( 0[bB][01_]+[a-z0-9]*          )  # G11: binary number
  | ( \d[\d_]* \.? [\d_]* [a-z]*    )  # G12: decimal / float

    # Multi-char operators (longest first)
  | ( \.\.\.|\.\.=|\.\.  )   # G13: ranges: ...  ..=  ..
  | ( ->|=>|==|!=|<=|>=|\+=|-=|\*=|/=|%=|&=|\|=|\^=|<<=|>>=|<<|>>|&&|\|\|  )
                              # G14: other multi-char operators
  | ( ::                 )   # G15: path separator (dict entry in RUST_KEYWORDS)

    # Whitespace
  | ( \n                 )   # G16: newline
  | ( [ \t\r]+           )   # G17: horizontal whitespace

    # Identifiers and keywords
  | ( [a-zA-Z_] \w*      )   # G18: identifier or keyword

    # Everything else
  | ( .                  )   # G19: fallback — any single character
''', re.VERBOSE | re.DOTALL)


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

def tokenise_rust(source: str) -> list[str]:
    """
    Tokenise a Rust source string into a flat list of Spectrum tokens.

    Round-trip guarantee: ''.join(tokens) == source
    """
    tokens: list[str] = []

    for m in _SCANNER.finditer(source):
        g   = m.lastindex
        val = m.group()

        if g in (1, 2):         # line / block comments
            _emit_chars(val, tokens)

        elif g == 3:            # raw string   r"…" r#"…"#
            _emit_chars(val, tokens)

        elif g in (4, 5, 6):    # byte string, byte char, normal string
            _emit_chars(val, tokens)

        elif g in (7, 8):       # char literal or lifetime annotation
            _emit_chars(val, tokens)

        elif g in (9, 10, 11, 12):  # numbers (hex / octal / binary / decimal)
            _emit_chars(val, tokens)

        elif g == 13:           # range operators  ...  ..=  ..
            _emit_token_or_chars(val, tokens)

        elif g == 14:           # other multi-char operators
            _emit_token_or_chars(val, tokens)

        elif g == 15:           # ::  path separator — dict token
            tokens.append(val)  # always in dict

        elif g == 16:           # newline
            tokens.append('\n')

        elif g == 17:           # horizontal whitespace
            for ch in val:
                tokens.append(ch)

        elif g == 18:           # identifier or keyword
            _emit_token_or_chars(val, tokens)

        else:                   # g == 19: fallback
            tokens.append(val)

    return tokens


# ---------------------------------------------------------------------------
# Verification
# ---------------------------------------------------------------------------

def verify_roundtrip(source: str) -> bool:
    tokens = tokenise_rust(source)
    return ''.join(tokens) == source


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: rust_tokenizer.py <file.rs>")
        sys.exit(1)

    src    = Path(sys.argv[1]).read_text(encoding="utf-8", errors="replace")
    tokens = tokenise_rust(src)

    dict_hits = sum(1 for t in tokens if t in D.TOKEN_TO_RGB)
    total     = len(tokens)
    rt_ok     = verify_roundtrip(src)

    rust_kw_hits = sum(1 for t in tokens if t in D.RUST_KEYWORDS)

    print(f"Tokens:       {total:,}")
    print(f"Dict hits:    {dict_hits:,}  ({100*dict_hits/total:.1f}%)")
    print(f"Rust kw hits: {rust_kw_hits:,}")
    print(f"Fallback:     {total-dict_hits:,}  ({100*(total-dict_hits)/total:.1f}%)")
    print(f"Round-trip:   {'✓ OK' if rt_ok else '✗ FAIL'}")
