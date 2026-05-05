"""
Spectrum Algo — Version Snapshot Tool
=======================================
Creates a versioned snapshot of the core encoding logic under versions/vN/.

Run this script AFTER bumping DICT_VERSION in dictionary.py and adding the
new language support.  It captures the exact state of all encoding-relevant
files so that any historical version can be inspected or diffed later.

Usage:
  python make_snapshot.py           # snapshot current DICT_VERSION
  python make_snapshot.py --version 8  # snapshot a specific version number
  python make_snapshot.py --list    # list existing snapshots

What gets snapshotted (core logic only — not test data or generated files):
  dictionary.py
  tokenizers/
    __init__.py  +  all *_tokenizer.py files
  spec_format/
    spec_encoder.py  spec_decoder.py  spec_migrate.py  __init__.py
    _frozen/  __init__.py  v*.py
  encoder/
    __init__.py  encoder.py
  decoder/
    __init__.py  decoder.py

NOT included (large or generated, identical across versions):
  english_tokens.py  (234K lines, shared across all versions)
  generate_english_dict.py
  test_sources/  results/  spec_format/output/
  gui/  chrome-extension/  Website/  rag/  benchmark_results.json

A README.md is written into each snapshot summarising the version.
"""

import sys
import argparse
from pathlib import Path
from datetime import date

# ---------------------------------------------------------------------------
# Files / directories to include in every snapshot
# ---------------------------------------------------------------------------
_CORE_FILES = [
    "dictionary.py",
    "tokenizers/__init__.py",
    "spec_format/__init__.py",
    "spec_format/spec_encoder.py",
    "spec_format/spec_decoder.py",
    "spec_format/spec_migrate.py",
    "encoder/__init__.py",
    "encoder/encoder.py",
    "decoder/__init__.py",
    "decoder/decoder.py",
]

_GLOB_PATTERNS = [
    ("tokenizers", "*_tokenizer.py"),
    ("spec_format/_frozen", "*.py"),
]


def _collect_files(root: Path) -> list[tuple[Path, Path]]:
    """Return list of (src_absolute, dst_relative) pairs."""
    pairs = []
    for rel in _CORE_FILES:
        src = root / rel
        if src.exists():
            pairs.append((src, Path(rel)))

    for subdir, pattern in _GLOB_PATTERNS:
        for src in sorted((root / subdir).glob(pattern)):
            rel = src.relative_to(root)
            pairs.append((src, rel))

    # Deduplicate (some files may match both _CORE_FILES and glob patterns)
    seen = set()
    deduped = []
    for src, rel in pairs:
        key = str(rel)
        if key not in seen:
            seen.add(key)
            deduped.append((src, rel))

    return deduped


def _write_readme(dest_dir: Path, version: int, token_count: int,
                  languages: list[str], files: list[Path]) -> None:
    lines = [
        f"# Spectrum Algo — Dictionary v{version} Snapshot",
        "",
        f"**Date captured:** {date.today().isoformat()}  ",
        f"**Dict version:** {version}  ",
        f"**SPEC_TOKEN_COUNT:** {token_count:,}  ",
        f"**Languages covered:** {', '.join(languages)}  ",
        "",
        "## Contents",
        "",
        "This directory is a read-only snapshot of the core encoding logic "
        f"as it existed at dictionary version {version}.  It is provided for "
        "reference, auditing, and comparison across versions.",
        "",
        "### Files included",
        "",
    ]
    for f in sorted(files):
        lines.append(f"- `{f}`")

    lines += [
        "",
        "### Files NOT included",
        "",
        "- `english_tokens.py` — 234K-line generated word list, identical "
        "across all versions; lives at the project root.",
        "- `test_sources/`, `results/`, `spec_format/output/` — test data.",
        "- `gui/`, `chrome-extension/`, `Website/`, `rag/` — tooling / UI.",
        "",
        "## Append-only ID guarantee",
        "",
        "Every Spectrum dictionary version only ever APPENDS new tokens to "
        "the end of `SPEC_TOKENS`.  This means the token IDs for all previous "
        "versions are stable subsets of this version's ID space.  "
        "See `spec_format/_frozen/` for the compact snapshots the decoder "
        "uses to read files from any older version.",
    ]

    (dest_dir / "README.md").write_text("\n".join(lines), encoding="utf-8")


def make_snapshot(root: Path, version: int | None = None) -> Path:
    """
    Create a snapshot of the current codebase under versions/vN/.

    Returns the destination directory.
    """
    sys.path.insert(0, str(root))
    import dictionary as D

    if version is None:
        version = D.DICT_VERSION

    token_count = len(D.SPEC_TOKENS)

    # Detect languages from DICT_VERSION description (heuristic via lang names)
    from spec_format.spec_encoder import _LANG_NAMES
    languages = list(_LANG_NAMES.values())

    dest_dir = root / "versions" / f"v{version}"
    if dest_dir.exists():
        overwrite = input(
            f"Snapshot versions/v{version}/ already exists. Overwrite? [y/N] "
        ).strip().lower()
        if overwrite != "y":
            print("Aborted.")
            return dest_dir
        # Remove existing files individually so we don't hit permission issues
        # with shutil.rmtree on read-only files created by a previous copy2 run.
        for f in dest_dir.rglob("*"):
            if f.is_file():
                f.chmod(0o644)
                f.unlink()
        for d in sorted(dest_dir.rglob("*"), reverse=True):
            if d.is_dir():
                d.rmdir()
        dest_dir.rmdir()

    dest_dir.mkdir(parents=True)

    pairs = _collect_files(root)
    copied = []
    skipped = []

    for src, rel in pairs:
        dst = dest_dir / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        # Write content directly (not shutil.copy2) so the destination files
        # are created fresh with normal permissions, not inheriting any
        # read-only / immutable attributes from the source.
        content = src.read_bytes()
        dst.write_bytes(content)
        copied.append(rel)

    _write_readme(dest_dir, version, token_count, languages,
                  [p for _, p in pairs])

    print(f"✓  Snapshot created: versions/v{version}/")
    print(f"   {len(copied)} file(s) copied")
    print(f"   Token count: {token_count:,}")
    print(f"   Languages:   {', '.join(languages)}")

    return dest_dir


def list_snapshots(root: Path) -> None:
    versions_dir = root / "versions"
    if not versions_dir.exists():
        print("No snapshots yet (versions/ directory does not exist).")
        return

    snapshots = sorted(versions_dir.iterdir())
    if not snapshots:
        print("No snapshots found in versions/.")
        return

    print(f"{'Version':<10} {'Token count':<16} {'Date':<14} Languages")
    print("─" * 70)

    for snap in snapshots:
        if not snap.is_dir():
            continue
        readme = snap / "README.md"
        token_count = "?"
        captured = "?"
        langs = "?"
        if readme.exists():
            for line in readme.read_text(encoding="utf-8").splitlines():
                # Lines are formatted as: **Key:** value
                # Split on the first ":** " to extract the value part.
                if "SPEC_TOKEN_COUNT:**" in line:
                    token_count = line.split(":**", 1)[-1].strip()
                if "Date captured:**" in line:
                    captured = line.split(":**", 1)[-1].strip()
                if "Languages covered:**" in line:
                    langs = line.split(":**", 1)[-1].strip()
        print(f"{snap.name:<10} {token_count:<16} {captured:<14} {langs}")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main() -> None:
    root = Path(__file__).resolve().parent

    parser = argparse.ArgumentParser(
        description="Spectrum Algo version snapshot tool."
    )
    parser.add_argument(
        "--version", type=int, default=None,
        help="Dict version to snapshot (default: current DICT_VERSION).",
    )
    parser.add_argument(
        "--list", action="store_true",
        help="List existing snapshots and exit.",
    )
    args = parser.parse_args()

    if args.list:
        list_snapshots(root)
        return

    make_snapshot(root, version=args.version)


if __name__ == "__main__":
    main()
