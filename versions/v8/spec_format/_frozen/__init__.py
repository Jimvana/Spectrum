"""
Spectrum Algo — Frozen Dictionary Snapshots
============================================
This package holds compact snapshots of SPEC_TOKENS for every historical
dictionary version.  The decoder uses these to correctly interpret .spec
files regardless of which version they were encoded with.

Design principle — append-only IDs:
  All Spectrum dictionary versions follow a strict rule: new tokens are only
  ever APPENDED to the end of TOKEN_TO_RGB, never inserted mid-list.  This
  means every historical SPEC_TOKENS list is a PREFIX of the current one.
  Storing a snapshot is therefore as cheap as storing a single integer (the
  token count), rather than repeating the full 234K-entry list.

  If a future version must break this rule (highly discouraged), a full frozen
  list must be stored instead of just a count.

Version history:
  v7  — Python, HTML, JS, CSS, English text           (234,702 tokens)
  v8  — adds TypeScript, SQL, Rust                    (234,830 tokens)  ← current

Adding a new version snapshot:
  1. Run: python -c "import dictionary as D; print(len(D.SPEC_TOKENS))"
     after bumping DICT_VERSION and adding new tokens.
  2. Verify zero mismatches:
       old = get_spec_tokens_for_version(prev_version)
       new = get_spec_tokens_for_version(curr_version)
       assert all(o == n for o, n in zip(old, new)), "ID order broken!"
  3. Add a new  vN.py  with  SPEC_TOKEN_COUNT = <value>.
  4. Register it in VERSION_COUNTS below.
"""

import sys
from pathlib import Path

# ---------------------------------------------------------------------------
# Registry: dict_version → SPEC_TOKEN_COUNT
# Each entry means "the first N tokens of the CURRENT dict == vX's full dict".
# ---------------------------------------------------------------------------
from spec_format._frozen.v7 import SPEC_TOKEN_COUNT as _V7_COUNT
from spec_format._frozen.v8 import SPEC_TOKEN_COUNT as _V8_COUNT

VERSION_COUNTS: dict[int, int] = {
    7: _V7_COUNT,
    8: _V8_COUNT,
}

# Minimum supported version for backward-compatible decoding
MIN_SUPPORTED_VERSION = 7


def get_spec_tokens_for_version(dict_version: int) -> list[str]:
    """
    Return the SPEC_TOKENS list that corresponds to the given dict version.

    For registered versions, returns the correctly-sized prefix of the current
    SPEC_TOKENS (exploiting the append-only guarantee).

    For unknown/future versions, returns the current full SPEC_TOKENS list
    with a warning — this is safe because future tokens would only ever extend
    the list, so current-dict IDs are always a valid subset.

    Raises ValueError for versions older than MIN_SUPPORTED_VERSION (v6 and
    earlier used uint16 token IDs and were fully re-encoded to v7 in 2026).
    """
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
    import dictionary as D

    if dict_version < MIN_SUPPORTED_VERSION:
        raise ValueError(
            f"Dict version {dict_version} is below the minimum supported "
            f"version ({MIN_SUPPORTED_VERSION}). "
            f"Files older than v{MIN_SUPPORTED_VERSION} cannot be decoded — "
            f"they used a different binary format (uint16 IDs). "
            f"Re-encode from the original source using the current encoder."
        )

    count = VERSION_COUNTS.get(dict_version)

    if count is None:
        # Unknown version — probably a newer dict; use current tokens and warn
        import warnings
        warnings.warn(
            f"No frozen snapshot for dict v{dict_version}. "
            f"Using current v{D.DICT_VERSION} tokens. "
            f"Decoding will succeed if v{dict_version} is a superset of "
            f"v{D.DICT_VERSION} (i.e., a future version reading current files).",
            UserWarning,
            stacklevel=2,
        )
        return list(D.SPEC_TOKENS)

    # Prefix slice — O(n) but only done once per decode call
    return list(D.SPEC_TOKENS[:count])


def get_id_to_token_for_version(dict_version: int) -> dict[int, str]:
    """
    Return a SPEC_ID_TO_TOKEN mapping for the given dict version.
    Convenience wrapper around get_spec_tokens_for_version.
    """
    tokens = get_spec_tokens_for_version(dict_version)
    return {i: tok for i, tok in enumerate(tokens)}


def get_ascii_base_for_version(dict_version: int) -> int:
    """Return the ASCII fallback base ID for the given dict version."""
    tokens = get_spec_tokens_for_version(dict_version)
    return len(tokens)
