"""
Spectrum Algo — HTML Tokenizer
Converts HTML source into a flat list of string tokens suitable for
Spectrum encoding.

Token types emitted:
  - Tag-open marker:   '<'  (already in SYMBOLS)
  - Tag-close marker:  '>'  (already in SYMBOLS)
  - Self-close marker: '/>' (already in SYMBOLS)
  - End-tag slash:     '/'  (already in SYMBOLS)
  - Tag names:         'div', 'span', etc. (HTML_TAGS or fallback)
  - Attribute names:   'href', 'class', etc. (HTML_ATTRS / KEYWORDS / fallback)
  - '=' separator:     '='  (already in SYMBOLS)
  - Attribute values:  emitted char-by-char (they're usually unique strings)
  - Whitespace:        ' ', '\\n', '\\t' (WHITESPACE)
  - Text content:      emitted char-by-char
  - Comment open:      '<!--' → '<', '!', '-', '-'  (char-by-char)
  - DOCTYPE:           emitted as identifier tokens where possible

Design principle: we tokenise at the level that maps naturally to the
Spectrum dictionary. Tag names and attribute names get single-token
treatment; free text and attribute values fall back to char-by-char.
"""

import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import dictionary as D

# ---------------------------------------------------------------------------
# Regex patterns
# ---------------------------------------------------------------------------

# Matches an HTML comment
_RE_COMMENT = re.compile(r'<!--.*?-->', re.DOTALL)

# Matches <!DOCTYPE ...>
_RE_DOCTYPE = re.compile(r'<!DOCTYPE[^>]*>', re.IGNORECASE)

# Matches a complete opening or closing tag: <tagname attrs...> or </tagname>
# Capture groups:
#   1: '/' if closing tag
#   2: tag name
#   3: attribute string (everything between tag name and >)
#   4: '/' if self-closing (/> end)
_RE_TAG = re.compile(
    r'<(/?)(\s*[a-zA-Z][a-zA-Z0-9_:-]*)([^>]*?)(/?)>',
    re.DOTALL
)

# Within an attribute string, match name="value" or name='value' or bare name
_RE_ATTR = re.compile(
    r'''([\w:-]+)           # attribute name
        (?:
          \s*=\s*
          (?:
            "([^"]*)"       # double-quoted value
          | '([^']*)'       # single-quoted value
          | (\S+)           # unquoted value
          )
        )?
    ''',
    re.VERBOSE
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _emit_string(s: str, tokens: list[str]) -> None:
    """Emit a string as individual characters (fallback encoding)."""
    tokens.extend(s)


def _emit_token_or_chars(tok: str, tokens: list[str]) -> None:
    """Emit tok as a single dictionary token if known, else char-by-char."""
    if tok in D.TOKEN_TO_RGB:
        tokens.append(tok)
    else:
        _emit_string(tok, tokens)


def _emit_whitespace(ws: str, tokens: list[str]) -> None:
    """Emit a whitespace string, using WHITESPACE tokens where possible."""
    for ch in ws:
        if ch in D.TOKEN_TO_RGB:
            tokens.append(ch)
        else:
            tokens.append(ch)


def _tokenise_attrs(attr_string: str, tokens: list[str]) -> None:
    """Tokenise an attribute string like: href="..." class="foo" disabled."""
    pos = 0
    while pos < len(attr_string):
        # Skip whitespace
        ws_match = re.match(r'\s+', attr_string[pos:])
        if ws_match:
            _emit_whitespace(ws_match.group(), tokens)
            pos += ws_match.end()
            continue

        attr_match = _RE_ATTR.match(attr_string, pos)
        if attr_match:
            attr_name  = attr_match.group(1)
            attr_value = (attr_match.group(2) or
                          attr_match.group(3) or
                          attr_match.group(4))

            # Emit attribute name
            _emit_token_or_chars(attr_name, tokens)

            if attr_value is not None:
                # Emit '=' and quote char
                tokens.append('=')
                # Determine which quote was used
                eq_pos = attr_string.find('=', pos + len(attr_name))
                after_eq = attr_string[eq_pos + 1:].lstrip()
                quote = after_eq[0] if after_eq and after_eq[0] in ('"', "'") else ''
                if quote:
                    tokens.append(quote)
                _emit_string(attr_value, tokens)
                if quote:
                    tokens.append(quote)

            pos = attr_match.end()
        else:
            # Unrecognised character — emit as-is
            tokens.append(attr_string[pos])
            pos += 1


# ---------------------------------------------------------------------------
# Main tokeniser
# ---------------------------------------------------------------------------

def tokenise_html(source: str) -> list[str]:
    """
    Tokenise an HTML source string into a flat list of Spectrum tokens.

    Round-trip guarantee: ''.join(tokens) == source
    """
    tokens: list[str] = []
    pos = 0
    n = len(source)

    while pos < n:
        # Try comment first (before tag matching)
        comment_match = _RE_COMMENT.match(source, pos)
        if comment_match:
            _emit_string(comment_match.group(), tokens)
            pos = comment_match.end()
            continue

        # Try DOCTYPE
        doctype_match = _RE_DOCTYPE.match(source, pos)
        if doctype_match:
            _emit_string(doctype_match.group(), tokens)
            pos = doctype_match.end()
            continue

        # Try a full tag
        tag_match = _RE_TAG.match(source, pos)
        if tag_match:
            slash_open  = tag_match.group(1)   # '/' if </tag
            tag_name    = tag_match.group(2).strip()
            attr_string = tag_match.group(3)
            slash_close = tag_match.group(4)   # '/' if />

            tokens.append('<')
            if slash_open:
                tokens.append('/')
            _emit_token_or_chars(tag_name.lower(), tokens)
            if attr_string.strip():
                _tokenise_attrs(attr_string, tokens)
            elif attr_string:
                _emit_whitespace(attr_string, tokens)
            if slash_close:
                tokens.append('/')
            tokens.append('>')

            pos = tag_match.end()
            continue

        # Plain text / anything else
        # Advance to next '<' or end
        next_tag = source.find('<', pos + 1)
        if next_tag == -1:
            _emit_string(source[pos:], tokens)
            break
        else:
            _emit_string(source[pos:next_tag], tokens)
            pos = next_tag

    return tokens


# ---------------------------------------------------------------------------
# Verification
# ---------------------------------------------------------------------------

def verify_roundtrip(source: str) -> bool:
    tokens = tokenise_html(source)
    return ''.join(tokens) == source


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import sys
    if len(sys.argv) < 2:
        print("Usage: html_tokenizer.py <file.html>")
        sys.exit(1)

    src = Path(sys.argv[1]).read_text(encoding="utf-8", errors="replace")
    tokens = tokenise_html(src)

    dict_hits  = sum(1 for t in tokens if t in D.TOKEN_TO_RGB)
    total      = len(tokens)
    rt_ok      = verify_roundtrip(src)

    print(f"Tokens:       {total:,}")
    print(f"Dict hits:    {dict_hits:,}  ({100*dict_hits/total:.1f}%)")
    print(f"Fallback:     {total-dict_hits:,}  ({100*(total-dict_hits)/total:.1f}%)")
    print(f"Round-trip:   {'✓ OK' if rt_ok else '✗ FAIL'}")
