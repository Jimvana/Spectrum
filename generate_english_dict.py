"""
Spectrum Algo — English Dictionary Generator
=============================================
Reads the NLTK words corpus (~236K words), adds contractions and ordinals,
assigns unique RGB values to each (skipping existing code token colours),
and writes english_tokens.py ready to be imported by dictionary.py.

Usage:
    python3 generate_english_dict.py

Output:
    english_tokens.py  (same directory as this script)
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import dictionary as D


# ─────────────────────────────────────────────────────────────────────────────
# Contractions (stored as lowercase — capitalisation handled by control tokens)
# ─────────────────────────────────────────────────────────────────────────────
CONTRACTIONS = [
    "i'm", "i've", "i'll", "i'd",
    "you're", "you've", "you'll", "you'd",
    "he's", "he'd", "he'll",
    "she's", "she'd", "she'll",
    "it's",
    "we're", "we've", "we'll", "we'd",
    "they're", "they've", "they'll", "they'd",
    "that's", "that'll", "what's", "what'll", "what've", "what'd",
    "where's", "where'll",
    "who's", "who'll", "who'd",
    "when's", "how's", "why's", "there's", "here's",
    "don't", "doesn't", "didn't",
    "isn't", "aren't", "wasn't", "weren't",
    "won't", "wouldn't",
    "can't", "cannot", "couldn't",
    "shouldn't", "shan't",
    "haven't", "hasn't", "hadn't",
    "mustn't", "needn't",
    "let's",
    "could've", "would've", "should've", "might've", "must've",
    "i'd've", "you'd've", "we'd've",
    "ain't",
    "y'all", "y'all'd", "y'all'll",
    "ma'am", "o'clock",
    "ne'er", "e'er", "o'er",
]


# ─────────────────────────────────────────────────────────────────────────────
# Ordinals  1st–31st  (and a few larger common ones)
# ─────────────────────────────────────────────────────────────────────────────
def ordinal(n: int) -> str:
    if n % 100 in (11, 12, 13):
        suffix = "th"
    elif n % 10 == 1:
        suffix = "st"
    elif n % 10 == 2:
        suffix = "nd"
    elif n % 10 == 3:
        suffix = "rd"
    else:
        suffix = "th"
    return f"{n}{suffix}"


ORDINALS = [ordinal(n) for n in list(range(1, 32)) + [100, 1000]]


# ─────────────────────────────────────────────────────────────────────────────
# RGB generator
# Iterates sequentially through (R, G, B) space starting at R=3,
# skipping any values already used by existing dictionary tokens.
# Avoids R=0–2 (fallback/builtin range), R=253 (RLE marker).
# ─────────────────────────────────────────────────────────────────────────────
def make_rgb_generator(used: set):
    for r in range(3, 253):          # skip 0-2 and RLE marker 253
        for g in range(256):
            for b in range(256):
                rgb = (r, g, b)
                if rgb not in used:
                    yield rgb


# ─────────────────────────────────────────────────────────────────────────────
# Load NLTK words corpus
# ─────────────────────────────────────────────────────────────────────────────
def load_nltk_words() -> list[str]:
    try:
        import nltk
        try:
            from nltk.corpus import words as nltk_words
            nltk_words.words()  # test if already downloaded
        except LookupError:
            print("[gen] Downloading NLTK words corpus...")
            nltk.download("words", quiet=True)
            from nltk.corpus import words as nltk_words
        word_list = nltk_words.words()
        print(f"[gen] NLTK corpus loaded: {len(word_list):,} entries")
        return word_list
    except ImportError:
        print("[gen] NLTK not available. Install with: pip install nltk --break-system-packages")
        sys.exit(1)


# ─────────────────────────────────────────────────────────────────────────────
# Main
# ─────────────────────────────────────────────────────────────────────────────
def main():
    # Existing used RGB values (code tokens + control tokens we're about to add)
    used_rgb = set(D.TOKEN_TO_RGB.values())
    # Also reserve the control token RGBs defined in ENGLISH_CONTROL
    # (they're already in TOKEN_TO_RGB after dictionary.py is updated,
    #  but if running before that update, reserve them manually)
    control_reserved = {(1,0,1),(1,0,2),(1,0,3),(1,0,4),(1,0,5),(1,1,0),(1,2,0)}
    used_rgb |= control_reserved

    gen = make_rgb_generator(used_rgb)

    # Load NLTK word list
    raw_words = load_nltk_words()

    # Normalise: lowercase, alphabetic only (no digits, no spaces)
    # We handle contractions/ordinals separately
    clean_words = []
    seen = set()
    for w in raw_words:
        w_low = w.lower()
        if w_low.isalpha() and len(w_low) > 1 and w_low not in seen:
            clean_words.append(w_low)
            seen.add(w_low)

    print(f"[gen] Clean alphabetic words: {len(clean_words):,}")

    # Build combined list: contractions first, ordinals second, then corpus words
    # Skip anything already in the existing code dictionary
    existing_tokens = set(D.TOKEN_TO_RGB.keys())
    all_words = []
    assigned = set()

    for word in CONTRACTIONS + ORDINALS + clean_words:
        if word not in assigned and word not in existing_tokens:
            all_words.append(word)
            assigned.add(word)

    print(f"[gen] Total new English tokens to assign: {len(all_words):,}")

    # Assign RGB values
    english_dict: dict[str, tuple] = {}
    for word in all_words:
        rgb = next(gen)
        english_dict[word] = rgb

    print(f"[gen] RGB assigned. Range: {list(english_dict.values())[0]} → "
          f"{list(english_dict.values())[-1]}")

    # Verify no collisions with original dictionary
    original_rgbs = set(D.TOKEN_TO_RGB.values())
    new_rgbs = set(english_dict.values())
    collisions = original_rgbs & new_rgbs
    if collisions:
        print(f"[gen] WARNING: {len(collisions)} RGB collision(s)! This should not happen.")
    else:
        print("[gen] ✓ Zero RGB collisions with existing code tokens")

    # Write english_tokens.py
    out_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "english_tokens.py")
    with open(out_path, "w", encoding="utf-8") as f:
        f.write('"""\n')
        f.write('Spectrum Algo — English Token Dictionary (auto-generated)\n')
        f.write('Do NOT edit manually. Regenerate with: python3 generate_english_dict.py\n')
        f.write(f'Total entries: {len(english_dict):,}\n')
        f.write('Includes: NLTK word corpus (~236K words), contractions, ordinals (1st–31st).\n')
        f.write('"""\n\n')
        f.write(f'# {len(english_dict):,} English tokens — assigned sequentially from RGB (3,0,0)\n')
        f.write('ENGLISH_WORDS: dict[str, tuple[int, int, int]] = {\n')
        for word, rgb in english_dict.items():
            # Escape backslashes and single quotes
            escaped = word.replace("\\", "\\\\").replace("'", "\\'")
            f.write(f"    '{escaped}': {rgb},\n")
        f.write('}\n')

    size_kb = os.path.getsize(out_path) / 1024
    print(f"[gen] Written: {out_path}  ({size_kb:.0f} KB)")
    print(f"[gen] Done — {len(english_dict):,} tokens ready for dictionary v7")


if __name__ == "__main__":
    main()
