from __future__ import annotations

import os
import sys
from pathlib import Path


def find_repo_root(start: Path | None = None) -> Path:
    """Find the Spectrum checkout that contains the current algorithm modules."""
    candidates: list[Path] = []
    env_root = os.environ.get("SPECTRUM_REPO_ROOT")
    if env_root:
        candidates.append(Path(env_root).expanduser())

    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        bundle_root = Path(sys._MEIPASS)
        candidates.extend(
            [
                bundle_root / "spectrum_runtime",
                bundle_root / "CLI Tool" / "vendor" / "spectrum_algo",
            ]
        )

    here = start or Path(__file__).resolve()
    candidates.extend([here, *here.parents, Path.cwd(), *Path.cwd().parents])

    for candidate in candidates:
        if candidate.is_file():
            candidate = candidate.parent
        if (candidate / "dictionary.py").exists() and (candidate / "spec_format" / "spec_encoder.py").exists():
            return candidate.resolve()

    raise RuntimeError(
        "Could not locate the Spectrum repository root. Set SPECTRUM_REPO_ROOT "
        "to the checkout that contains dictionary.py and spec_format/."
    )


REPO_ROOT = find_repo_root()

if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))
