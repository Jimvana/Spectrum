"""
Spectrum Algo — .spec Migration Tool
=====================================
Upgrades .spec files from an older dictionary version to the current one.

How it works:
  1. Decode the source .spec file using the appropriate frozen SPEC_TOKENS
     for its encoded dict version (guaranteeing correct decoding).
  2. Re-encode the recovered source text using the current encoder and
     current dictionary.
  3. Write the upgraded .spec file (in-place or to a new path).

The migrated file benefits from:
  - Any new dictionary tokens added in the upgrade (better dict hit rate)
  - Current compression settings
  - Updated header with current DICT_VERSION

Usage:
  # Migrate a single file (in-place, original backed up as .spec.bak)
  python spec_format/spec_migrate.py myfile.spec

  # Migrate a single file to a new path
  python spec_format/spec_migrate.py myfile.spec --out myfile_v8.spec

  # Migrate all .spec files in a directory
  python spec_format/spec_migrate.py spec_format/output/

  # Dry run — show what would change without writing anything
  python spec_format/spec_migrate.py spec_format/output/ --dry-run

  # Skip files already on the current dict version
  python spec_format/spec_migrate.py spec_format/output/ --skip-current
"""

import sys
import struct
import tempfile
import shutil
import argparse
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import dictionary as D
from spec_format.spec_encoder import encode_file, _EXT_TO_LANG, _LANG_NAMES
from spec_format.spec_decoder import decode_file, parse_header, HEADER_SIZE
from spec_format._frozen import MIN_SUPPORTED_VERSION


# ─────────────────────────────────────────────────────────────────────────────
# Language ID → source file extension (for temp file naming)
# ─────────────────────────────────────────────────────────────────────────────
_LANG_TO_EXT = {v: k for k, v in _EXT_TO_LANG.items()}
# Use the shortest/most canonical extension per language
_LANG_TO_EXT_CANONICAL = {
    0: ".py",
    1: ".html",
    2: ".js",
    3: ".css",
    4: ".txt",
    5: ".ts",
    6: ".sql",
    7: ".rs",
}


# ─────────────────────────────────────────────────────────────────────────────
# Core migration logic
# ─────────────────────────────────────────────────────────────────────────────

def migrate_file(
    spec_path: str | Path,
    output_path: str | Path | None = None,
    dry_run: bool = False,
    skip_current: bool = False,
    backup: bool = True,
    zlib_level: int = 9,
    use_rle: bool = True,
) -> dict:
    """
    Migrate a single .spec file to the current dictionary version.

    Returns a result dict with keys:
      spec_path       — input path
      output_path     — output path (same as input for in-place)
      source_version  — dict version the file was encoded with
      target_version  — dict version after migration (current)
      original_size   — input file size in bytes
      migrated_size   — output file size in bytes
      size_delta      — migrated_size - original_size (negative = smaller)
      skipped         — True if file was already current version
      dry_run         — True if no files were written
      fidelity        — '✓ perfect' or '✗ mismatch'
    """
    spec_path = Path(spec_path)
    in_place  = (output_path is None)
    if in_place:
        output_path = spec_path
    else:
        output_path = Path(output_path)

    # Read header to check version
    raw = spec_path.read_bytes()
    if len(raw) < HEADER_SIZE:
        raise ValueError(f"{spec_path.name}: file too short to be a valid .spec")
    if raw[:4] != b'SPEC':
        raise ValueError(f"{spec_path.name}: not a .spec file (bad magic)")

    meta = parse_header(raw)
    source_version = meta["dict_version"]
    language_id    = meta["language_id"]
    lang_name      = _LANG_NAMES.get(language_id, f"lang{language_id}")

    result = {
        "spec_path":      str(spec_path),
        "output_path":    str(output_path),
        "source_version": source_version,
        "target_version": D.DICT_VERSION,
        "original_size":  len(raw),
        "migrated_size":  len(raw),   # updated below if migration runs
        "size_delta":     0,
        "skipped":        False,
        "dry_run":        dry_run,
        "fidelity":       "n/a",
        "lang":           lang_name,
    }

    # Skip if already on current version
    if skip_current and source_version == D.DICT_VERSION:
        result["skipped"] = True
        print(f"  [skip] {spec_path.name}  (already v{D.DICT_VERSION})")
        return result

    if source_version < MIN_SUPPORTED_VERSION:
        raise ValueError(
            f"{spec_path.name}: dict v{source_version} is below minimum "
            f"supported version ({MIN_SUPPORTED_VERSION})."
        )

    if dry_run:
        print(f"  [dry-run] {spec_path.name}  "
              f"v{source_version} → v{D.DICT_VERSION}  [{lang_name}]")
        return result

    # ── Step 1: Decode using frozen dict for source_version ──────────────────
    ext = _LANG_TO_EXT_CANONICAL.get(language_id, ".txt")
    with (tempfile.NamedTemporaryFile(suffix=ext, delete=False, mode='w') as src_f,
          tempfile.NamedTemporaryFile(suffix=".spec", delete=False) as out_f):
        decoded_path = Path(src_f.name)
        reencoded_path = Path(out_f.name)

    try:
        dec_result = decode_file(str(spec_path), str(decoded_path))
        if not (dec_result["length_ok"] and dec_result["checksum_ok"]):
            raise ValueError(
                f"{spec_path.name}: decode failed — "
                f"fidelity={dec_result['fidelity']}"
            )

        result["fidelity"] = dec_result["fidelity"]

        # ── Step 2: Re-encode with current dict ──────────────────────────────
        encode_file(
            str(decoded_path),
            str(reencoded_path),
            use_rle=use_rle,
            language_id=language_id,
            zlib_level=zlib_level,
        )

        migrated_bytes = reencoded_path.read_bytes()
        result["migrated_size"] = len(migrated_bytes)
        result["size_delta"]    = len(migrated_bytes) - len(raw)

        # ── Step 3: Write output ─────────────────────────────────────────────
        if in_place and backup:
            bak = spec_path.with_suffix(".spec.bak")
            shutil.copy2(spec_path, bak)

        output_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(reencoded_path, output_path)

        delta_str = (f"{result['size_delta']:+,} B "
                     f"({'smaller' if result['size_delta'] < 0 else 'larger'})")
        print(f"  [migrated] {spec_path.name}  "
              f"v{source_version} → v{D.DICT_VERSION}  "
              f"{len(raw):,} B → {len(migrated_bytes):,} B  ({delta_str})  "
              f"[{lang_name}]  {result['fidelity']}")

    finally:
        decoded_path.unlink(missing_ok=True)
        reencoded_path.unlink(missing_ok=True)

    return result


def migrate_directory(
    directory: str | Path,
    dry_run: bool = False,
    skip_current: bool = False,
    backup: bool = True,
    recursive: bool = False,
    zlib_level: int = 9,
    use_rle: bool = True,
) -> list[dict]:
    """
    Migrate all .spec files in a directory.

    Returns a list of result dicts (one per file).
    """
    directory = Path(directory)
    pattern   = "**/*.spec" if recursive else "*.spec"
    spec_files = sorted(directory.glob(pattern))

    if not spec_files:
        print(f"No .spec files found in {directory}")
        return []

    print(f"Found {len(spec_files)} .spec file(s) in {directory}")
    if dry_run:
        print("(dry-run — no files will be written)")
    print()

    results = []
    for sf in spec_files:
        try:
            r = migrate_file(
                sf,
                dry_run=dry_run,
                skip_current=skip_current,
                backup=backup,
                zlib_level=zlib_level,
                use_rle=use_rle,
            )
            results.append(r)
        except Exception as e:
            print(f"  [ERROR] {sf.name}: {e}")
            results.append({"spec_path": str(sf), "error": str(e)})

    return results


def print_summary(results: list[dict]) -> None:
    """Print a migration summary table."""
    migrated  = [r for r in results if not r.get("skipped") and not r.get("dry_run") and "error" not in r]
    skipped   = [r for r in results if r.get("skipped")]
    errors    = [r for r in results if "error" in r]
    dry_runs  = [r for r in results if r.get("dry_run") and "error" not in r]

    total_before = sum(r.get("original_size", 0) for r in migrated)
    total_after  = sum(r.get("migrated_size",  0) for r in migrated)
    total_delta  = total_after - total_before

    print()
    print("─" * 60)
    print(f"Migration complete")
    print(f"  Migrated:  {len(migrated)} file(s)")
    if skipped:
        print(f"  Skipped:   {len(skipped)} (already current version)")
    if dry_runs:
        print(f"  Dry-run:   {len(dry_runs)} file(s)")
    if errors:
        print(f"  Errors:    {len(errors)} file(s)")
    if migrated:
        delta_str = f"{total_delta:+,} B ({'smaller' if total_delta < 0 else 'larger'})"
        print(f"  Size:      {total_before:,} B → {total_after:,} B  ({delta_str})")
    print("─" * 60)


# ─────────────────────────────────────────────────────────────────────────────
# CLI
# ─────────────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description=(
            "Spectrum Algo .spec Migration Tool — "
            "upgrade .spec files to the current dictionary version."
        )
    )
    parser.add_argument(
        "target",
        help="Path to a .spec file or a directory containing .spec files.",
    )
    parser.add_argument(
        "--out",
        default=None,
        help="Output path for single-file migration (default: in-place).",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be migrated without writing any files.",
    )
    parser.add_argument(
        "--skip-current",
        action="store_true",
        help=f"Skip files already encoded with the current dict (v{D.DICT_VERSION}).",
    )
    parser.add_argument(
        "--no-backup",
        action="store_true",
        help="Don't create .spec.bak backup files on in-place migration.",
    )
    parser.add_argument(
        "--recursive",
        action="store_true",
        help="Recursively migrate .spec files in subdirectories.",
    )
    parser.add_argument(
        "--zlib-level",
        type=int,
        default=9,
        help="zlib compression level 1–9 (default: 9).",
    )
    parser.add_argument(
        "--no-rle",
        action="store_true",
        help="Disable RLE compression in migrated files.",
    )
    args = parser.parse_args()

    target = Path(args.target)
    if not target.exists():
        print(f"Error: {target} not found", file=sys.stderr)
        sys.exit(1)

    print(f"Spectrum Algo .spec Migration Tool")
    print(f"Current dict version: v{D.DICT_VERSION}")
    print()

    if target.is_file():
        try:
            result = migrate_file(
                target,
                output_path=args.out,
                dry_run=args.dry_run,
                skip_current=args.skip_current,
                backup=not args.no_backup,
                zlib_level=args.zlib_level,
                use_rle=not args.no_rle,
            )
            print_summary([result])
        except Exception as e:
            print(f"Error: {e}", file=sys.stderr)
            sys.exit(1)

    elif target.is_dir():
        if args.out:
            print("Error: --out cannot be used with directory migration.", file=sys.stderr)
            sys.exit(1)
        results = migrate_directory(
            target,
            dry_run=args.dry_run,
            skip_current=args.skip_current,
            backup=not args.no_backup,
            recursive=args.recursive,
            zlib_level=args.zlib_level,
            use_rle=not args.no_rle,
        )
        print_summary(results)
        if any("error" in r for r in results):
            sys.exit(1)


if __name__ == "__main__":
    main()
