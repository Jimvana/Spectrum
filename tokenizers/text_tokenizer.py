"""
Spectrum Algo — Plain English Text Tokenizer
=============================================
Tokenizes plain English text (.txt files) into a stream of .spec tokens,
using the English word dictionary plus control tokens for capitalisation,
word-spelling, and number separation.

TOKEN STREAM DESIGN
───────────────────
Each element in the returned list is a token string that maps to a spec ID
in dictionary.TOKEN_TO_SPEC_ID.  The text decoder (in spec_decoder.py)
reconstructs the original text by interpreting the stream as follows:

  Word tokens          — dictionary entry (lowercase); written as-is
  CTRL:CAP_FIRST       — capitalise first letter of next word/spelled-word
  CTRL:CAP_ALL         — capitalise entire next word/spelled-word
  CTRL:BEGIN_WORD      — start of a spelled-out word (unknown to dictionary)
  CTRL:END_WORD        — end of a spelled-out word
  CTRL:NUM_SEP         — explicit space between two adjacent digit groups
  Digit tokens ("0"–"9") — concatenated into numbers by the decoder
  Whitespace tokens    — " ", "\\t", "\\n", "\\r" (explicit, preserved exactly)
  Punctuation tokens   — from SYMBOLS or TEXT_PUNCTUATION in dictionary
  ASCII fallback chars — anything else, passed through as single characters

CAPITALISATION RULES
────────────────────
  all-lowercase  → no cap token, word token
  First-capital  → CTRL:CAP_FIRST, word token (lowercased)
  ALL-CAPS       → CTRL:CAP_ALL,   word token (lowercased)
  Mixed (iPhone) → characters emitted individually (ASCII fallback)

WORD BOUNDARIES
───────────────
Apostrophes mid-word are included so contractions ("don't", "it's") are
matched as whole tokens. Leading/trailing apostrophes are treated as
punctuation, not part of the word.

NUMBERS
───────
Digit characters are emitted individually. The decoder concatenates
consecutive digit tokens automatically. CTRL:NUM_SEP is only emitted
when two digit groups appear directly adjacent with no whitespace or
punctuation between them (rare in natural text but handled correctly).
"""

import sys
import unicodedata
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import dictionary as D

# ── Control token strings (must match ENGLISH_CONTROL keys in dictionary.py) ─
T_CAP_FIRST  = "CTRL:CAP_FIRST"
T_CAP_ALL    = "CTRL:CAP_ALL"
T_BEGIN_WORD = "CTRL:BEGIN_WORD"
T_END_WORD   = "CTRL:END_WORD"
T_NUM_SEP    = "CTRL:NUM_SEP"

# Pre-build a set of known 2-char punctuation tokens for fast lookup
_TWO_CHAR_PUNCT = {tok for tok in D.TOKEN_TO_SPEC_ID if len(tok) == 2
                   and not tok[0].isalnum() and not tok[0] == '_'}


def _word_case(word: str):
    """
    Return a (cap_token, lowercased_word) pair, or None if mixed-case.

    Returns:
      (None,         word)        — already lowercase
      (T_CAP_FIRST,  lower)       — first letter uppercase, rest lower
      (T_CAP_ALL,    lower)       — all uppercase (2+ chars)
      None                        — mixed case (e.g. iPhone, macOS)
    """
    if word == word.lower():
        return (None, word)
    lower = word.lower()
    if word == word.upper() and len(word) > 1 and lower.upper() == word:
        return (T_CAP_ALL, lower)
    # First-cap: first char upper, remainder lower
    if (
        word[0].isupper()
        and word[1:] == word[1:].lower()
        and _apply_cap(lower, 'first') == word
    ):
        return (T_CAP_FIRST, lower)
    # Everything else is mixed-case — caller handles char-by-char
    return None


def tokenize_text(source: str) -> list[str]:
    """
    Tokenize a plain English string into a .spec token stream.

    Parameters
    ----------
    source : str
        The full text content to encode.

    Returns
    -------
    list[str]
        Ordered list of token strings, each present in D.TOKEN_TO_SPEC_ID
        or representable as an ASCII/Unicode fallback.
    """
    tokens: list[str] = []
    append = tokens.append
    extend = tokens.extend
    token_map = D.TOKEN_TO_SPEC_ID
    i = 0
    n = len(source)
    prev_was_digit = False   # tracks whether last emitted token was a digit

    while i < n:
        ch = source[i]

        # ── Whitespace ───────────────────────────────────────────────────────
        if ch in (' ', '\t', '\n', '\r'):
            append(ch)
            prev_was_digit = False
            i += 1
            continue

        # ── Digit ────────────────────────────────────────────────────────────
        if ch.isdigit():
            if prev_was_digit:
                # Two digit groups directly adjacent (no whitespace) — insert sep
                append(T_NUM_SEP)
            append(ch)
            prev_was_digit = True
            i += 1
            continue

        # Reset digit tracking for any non-digit, non-whitespace character
        prev_was_digit = False

        # ── Word (letters, possibly with mid-word apostrophe) ────────────────
        if ch.isalpha():
            # Scan to end of word: letters + apostrophe-then-letter (contractions)
            j = i + 1
            while j < n:
                c = source[j]
                if c.isalpha():
                    j += 1
                elif c == "'" and j + 1 < n and source[j + 1].isalpha():
                    j += 2   # include apostrophe + following letter
                else:
                    break
            word = source[i:j]
            i = j

            # Determine capitalisation
            case_result = _word_case(word)

            if case_result is None:
                # Mixed-case (iPhone, macOS, etc.) — emit char-by-char
                extend(word)
                continue

            cap_tok, word_lower = case_result

            # Try dictionary lookup (whole word, lowercase)
            if word_lower in token_map:
                if cap_tok:
                    append(cap_tok)
                append(word_lower)
            else:
                # Spell it out letter by letter between BEGIN/END markers
                if cap_tok:
                    append(cap_tok)
                append(T_BEGIN_WORD)
                extend(word_lower)
                append(T_END_WORD)
            continue

        # ── Punctuation / symbols ────────────────────────────────────────────
        # Try 3-char match first (e.g. "..." ellipsis, "===" JS strict equal)
        if i + 2 < n and source[i:i+3] in token_map:
            append(source[i:i+3])
            i += 3
            continue

        # Try 2-char match
        if i + 1 < n and source[i:i+2] in token_map:
            append(source[i:i+2])
            i += 2
            continue

        # Single character — dictionary or ASCII fallback
        append(ch)
        i += 1

    return tokens


# ── Reconstruction (used by the decoder) ────────────────────────────────────

def reconstruct_text(tokens: list[str]) -> str:
    """
    Reconstruct plain English text from a decoded token stream.

    Interprets CTRL:* control tokens as state changes rather than
    literal output characters.

    This is the inverse of tokenize_text().
    """
    result: list[str] = []
    cap_mode: str | None = None      # None | 'first' | 'all'
    spelling: list[str] = []
    in_spelled_word = False
    prev_was_digit = False

    for tok in tokens:

        # ── Control tokens ────────────────────────────────────────────────
        if tok == T_CAP_FIRST:
            cap_mode = 'first'
            continue
        if tok == T_CAP_ALL:
            cap_mode = 'all'
            continue
        if tok == T_BEGIN_WORD:
            in_spelled_word = True
            spelling = []
            prev_was_digit = False
            continue
        if tok == T_END_WORD:
            word = ''.join(spelling)
            result.append(_apply_cap(word, cap_mode))
            cap_mode = None
            in_spelled_word = False
            spelling = []
            prev_was_digit = False
            continue
        if tok == T_NUM_SEP:
            # Explicit separator between two adjacent digit groups
            # (In natural text this is almost always a space, but we emit
            #  the separator token without adding a space — the original
            #  text had none.  The encoder only fires NUM_SEP when digits
            #  directly abut, so on decode we simply mark the boundary
            #  by doing nothing — the previous digits are already committed.)
            prev_was_digit = False
            continue

        # ── Inside a spelled-out word ─────────────────────────────────────
        if in_spelled_word:
            spelling.append(tok)
            continue

        # ── Digit tokens ─────────────────────────────────────────────────
        if tok in ('0','1','2','3','4','5','6','7','8','9'):
            result.append(tok)
            prev_was_digit = True
            continue

        # ── Regular token (word, whitespace, punctuation) ─────────────────
        prev_was_digit = False
        out = _apply_cap(tok, cap_mode)
        cap_mode = None
        result.append(out)

    return ''.join(result)


def _apply_cap(word: str, cap_mode: str | None) -> str:
    """Apply capitalisation mode to a word string."""
    if not word or cap_mode is None:
        return word
    if cap_mode == 'first':
        return unicodedata.normalize("NFC", word[0].upper() + word[1:])
    if cap_mode == 'all':
        return unicodedata.normalize("NFC", word.upper())
    return word


# ── CLI smoke-test ───────────────────────────────────────────────────────────

if __name__ == "__main__":
    import sys
    sample = (
        "Hello, World! The quick brown fox jumps over the 42 lazy dogs.\n"
        "It's a beautiful day — don't you think? I'd say NASA and the BBC\n"
        "are 2 of the world's most recognised organisations.\n"
        "She said: \"We're ready.\" He replied: 'Are you sure?'\n"
        "Version 3.14 released on 1st January 2026.\n"
    )

    if len(sys.argv) > 1:
        sample = Path(sys.argv[1]).read_text(encoding="utf-8", errors="replace")

    toks = tokenize_text(sample)
    reconstructed = reconstruct_text(toks)

    # Stats
    dict_hits = sum(1 for t in toks if t in D.TOKEN_TO_SPEC_ID
                    and not t.startswith("CTRL:"))
    ctrl_toks  = sum(1 for t in toks if t.startswith("CTRL:"))
    fallback   = sum(1 for t in toks if t not in D.TOKEN_TO_SPEC_ID)

    print(f"Tokens:      {len(toks):,}")
    print(f"  dict hits: {dict_hits:,}")
    print(f"  ctrl:      {ctrl_toks:,}")
    print(f"  fallback:  {fallback:,}")
    print(f"Round-trip: {'✓ perfect' if reconstructed == sample else '✗ MISMATCH'}")
    if reconstructed != sample:
        # Show first difference
        for idx, (a, b) in enumerate(zip(sample, reconstructed)):
            if a != b:
                print(f"  First diff at char {idx}: "
                      f"original={a!r} decoded={b!r}")
                print(f"  Context: {sample[max(0,idx-20):idx+20]!r}")
                break
        if len(reconstructed) != len(sample):
            print(f"  Length: original={len(sample)} decoded={len(reconstructed)}")
