"""
Spectrum Algo — Dictionary v7 Frozen Snapshot
==============================================
Covers: Python, HTML, JavaScript, CSS, English text.
Token count verified on 2026-04-16.

Because all Spectrum dictionaries follow the append-only rule, the full v7
SPEC_TOKENS list is simply the first SPEC_TOKEN_COUNT entries of the current
(v8+) SPEC_TOKENS.  No large data file needed.

Verification command (run from project root):
    python -c "
    import sys; sys.path.insert(0,'.')
    import dictionary as D
    from spec_format._frozen.v7 import SPEC_TOKEN_COUNT
    v7 = {
        **D.KEYWORDS, **D.SYMBOLS, **D.DIGITS, **D.WHITESPACE,
        **D.BUILTINS_FUNCS, **D.BUILTINS_TYPES, **D.CORE_IDENTIFIERS,
        **D.DUNDERS, **D.EXCEPTIONS, **D.COMMON_METHODS, **D.STDLIB_MODULES,
        **D.HTML_TAGS, **D.HTML_ATTRS, **D.JS_KEYWORDS, **D.JS_OPERATORS,
        **D.JS_IDENTIFIERS, **D.CSS_AT_RULES, **D.CSS_PROPERTIES,
        **D.CSS_VALUE_KEYWORDS, **D.SPECIAL, **D.ENGLISH_CONTROL,
        **D.TEXT_PUNCTUATION, **D.ENGLISH_WORDS,
    }
    rebuilt = [t for t in v7 if not t.startswith('__')]
    assert len(rebuilt) == SPEC_TOKEN_COUNT, 'count mismatch'
    assert rebuilt == list(D.SPEC_TOKENS[:SPEC_TOKEN_COUNT]), 'order mismatch'
    print('v7 snapshot OK')
    "
"""

# The number of tokens in the v7 dictionary.
# v7 SPEC_TOKENS == current SPEC_TOKENS[:SPEC_TOKEN_COUNT]  (append-only guarantee)
SPEC_TOKEN_COUNT: int = 234_702
