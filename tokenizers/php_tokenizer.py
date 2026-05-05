"""
Spectrum Algo — PHP Tokenizer
Converts PHP source into a flat list of string tokens suitable for Spectrum
encoding.

The tokenizer uses a single-pass regex scanner.  Token categories:

  - PHP open/close tags: <?php  <?=  ?>   (emitted char-by-char as fallback;
    '<', '?', 'p', 'h', 'p' are all individual chars or dict tokens)
  - Line comments:   //  …\n   #  …\n    (emitted char-by-char)
  - Block comments:  /* … */              (emitted char-by-char)
  - Heredoc / Nowdoc: <<<EOT…EOT;        (emitted char-by-char — complex,
    treated as a single opaque block)
  - Double-quoted strings: "…"  "$var"   (emitted char-by-char)
  - Single-quoted strings: '…'           (emitted char-by-char)
  - Numbers: integers, hex, octal,
    binary, floats                        (emitted char-by-char)
  - Variables: $varname                  ($ + identifier separately)
  - Multi-char operators: ?->  ===  !==  =>  ??  ||  &&  ++  --  <=  >=
                          **  <<  >>  +=  -=  .=  and more  (dict lookup)
  - Single-char operators: standard      (dict lookup or char)
  - Identifiers / keywords: dict lookup  (PHP keywords hit the dict)

Round-trip guarantee: ''.join(tokens) == source
"""

import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import dictionary as D

# ---------------------------------------------------------------------------
# Master scanner regex  (order matters — longest patterns first)
# ---------------------------------------------------------------------------

_SCANNER = re.compile(r'''
    # PHP open/close tags (emit char-by-char via fallback group)
    ( <\?(?:php|=)?  )          # G1:  PHP open tag  <?php  <?=  <?
  | ( \?>            )          # G2:  PHP close tag  ?>

    # Comments
  | ( //[^\n]*       )          # G3:  line comment  //
  | ( \#[^\n]*       )          # G4:  line comment  #
  | ( /\*.*?\*/      )          # G5:  block comment

    # Heredoc / Nowdoc (treat entire block as opaque)
  | ( <<<['"']?\w+['"']?\r?\n .*? \r?\n\w+;? )  # G6: heredoc/nowdoc

    # String literals
  | ( " [^"\\$]* (?: (?:\\.|(?=\$)) [^"\\$]* )* "  )  # G7: double-quoted
  | ( ' [^'\\]* (?: \\. [^'\\]* )* '               )  # G8: single-quoted
  | ( ` [^`\\]* (?: \\. [^`\\]* )* `               )  # G9: backtick string

    # Numbers
  | ( 0[xX][0-9a-fA-F_]+  )    # G10: hex
  | ( 0[bB][01_]+          )    # G11: binary
  | ( 0[oO][0-7_]+         )    # G12: octal
  | ( \d[\d_]* \.? [\d_]* (?: [eE][+-]?\d+ )? )  # G13: int / float

    # PHP variables — emit $ then the name separately
  | ( \$[a-zA-Z_]\w*       )    # G14: variable  $varName  $this

    # Multi-char operators (longest first)
  | ( \?->|===|!==|<=>|\.=|\*\*|<<=|>>=|&&|\|\||<=|>=|==|!=|=>|\?\?|\+\+|--|->|::|<<|>>|\+=|-=|\*=|/=|%=|&=|\|=|\^= )
                                 # G15: multi-char operators
    # Whitespace
  | ( \n             )          # G16: newline
  | ( [ \t\r]+       )          # G17: horizontal whitespace

    # Identifiers / keywords
  | ( [a-zA-Z_\x80-\xff][\w\x80-\xff]* )  # G18: PHP identifier (supports
                                            #   extended ASCII for mb identifiers)
    # Everything else
  | ( .              )          # G19: fallback
''', re.VERBOSE | re.DOTALL)

# PHP variables: emit $ as a char then the bare name as a token
_VAR_RE = re.compile(r'^\$([a-zA-Z_]\w*)$')


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

def tokenise_php(source: str) -> list[str]:
    """
    Tokenise a PHP source string into a flat list of Spectrum tokens.

    Round-trip guarantee: ''.join(tokens) == source
    """
    tokens: list[str] = []

    for m in _SCANNER.finditer(source):
        g   = m.lastindex
        val = m.group()

        if g in (1, 2):         # PHP open / close tags — char-by-char
            _emit_chars(val, tokens)

        elif g in (3, 4, 5):    # line comments (#  //), block comment
            _emit_chars(val, tokens)

        elif g == 6:            # heredoc / nowdoc — opaque block
            _emit_chars(val, tokens)

        elif g in (7, 8, 9):    # string literals
            _emit_chars(val, tokens)

        elif g in (10, 11, 12, 13):  # numbers
            _emit_chars(val, tokens)

        elif g == 14:           # $variable — emit '$' then the name
            m2 = _VAR_RE.match(val)
            if m2:
                tokens.append('$')
                _emit_token_or_chars(m2.group(1), tokens)
            else:
                _emit_chars(val, tokens)

        elif g == 15:           # multi-char operators
            _emit_token_or_chars(val, tokens)

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
    tokens = tokenise_php(source)
    return ''.join(tokens) == source


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: php_tokenizer.py <file.php>")
        sys.exit(1)

    src    = Path(sys.argv[1]).read_text(encoding="utf-8", errors="replace")
    tokens = tokenise_php(src)

    dict_hits    = sum(1 for t in tokens if t in D.TOKEN_TO_RGB)
    total        = len(tokens)
    rt_ok        = verify_roundtrip(src)
    php_kw_hits  = sum(1 for t in tokens if t in D.PHP_KEYWORDS)
    php_fn_hits  = sum(1 for t in tokens if t in D.PHP_FUNCTIONS)

    print(f"Tokens:        {total:,}")
    print(f"Dict hits:     {dict_hits:,}  ({100*dict_hits/total:.1f}%)")
    print(f"PHP kw hits:   {php_kw_hits:,}")
    print(f"PHP fn hits:   {php_fn_hits:,}")
    print(f"Fallback:      {total-dict_hits:,}  ({100*(total-dict_hits)/total:.1f}%)")
    print(f"Round-trip:    {'✓ OK' if rt_ok else '✗ FAIL'}")
