# Local Changes Parked

These local changes were present after pulling `origin/main` on 2026-05-05 and were removed so the checkout matches the live GitHub version.

## CLI Tool/bin/spec.js

The local edit hardened the Node wrapper for Windows/Python environments:

- set `PYTHONIOENCODING=utf-8`
- set `PYTHONUTF8=1`
- tried `python3`, `python`, and on Windows `py -3`
- captured stderr so the Windows Store Python alias message could be skipped

This may still be useful, but it should be reapplied against the current repo layout rather than kept as local drift.

## versions/v10/decoder/decoder.py

The local edit changed decoded output writing from:

```python
output_path.write_text(source, encoding="utf-8")
```

to:

```python
with output_path.open("w", encoding="utf-8", newline="") as f:
    f.write(source)
```

The goal was to avoid platform newline conversion.

## versions/v11/spec_format/spec_decoder.py

The same newline-preserving write change was present here.

## package-lock.json

An untracked root `package-lock.json` existed for `@jimvana/spectrum` version `0.4.1`, with `spec` pointing to `bin/spec.js`. The current GitHub layout has moved the CLI under `CLI Tool/`, so this looked stale.
