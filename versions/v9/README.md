# Spectrum Algo — Dictionary v9 Snapshot

**Date captured:** 2026-04-16  
**Dict version:** 9  
**SPEC_TOKEN_COUNT:** 234,893  
**Languages covered:** Python, HTML, JS, CSS, Text, TypeScript, SQL, Rust, PHP  

## Contents

This directory is a read-only snapshot of the core encoding logic as it existed at dictionary version 9.  It is provided for reference, auditing, and comparison across versions.

### Files included

- `decoder/__init__.py`
- `decoder/decoder.py`
- `dictionary.py`
- `encoder/__init__.py`
- `encoder/encoder.py`
- `spec_format/__init__.py`
- `spec_format/_frozen/__init__.py`
- `spec_format/_frozen/v7.py`
- `spec_format/_frozen/v8.py`
- `spec_format/_frozen/v9.py`
- `spec_format/spec_decoder.py`
- `spec_format/spec_encoder.py`
- `spec_format/spec_migrate.py`
- `tokenizers/__init__.py`
- `tokenizers/css_tokenizer.py`
- `tokenizers/html_tokenizer.py`
- `tokenizers/js_tokenizer.py`
- `tokenizers/php_tokenizer.py`
- `tokenizers/rust_tokenizer.py`
- `tokenizers/sql_tokenizer.py`
- `tokenizers/text_tokenizer.py`
- `tokenizers/ts_tokenizer.py`

### Files NOT included

- `english_tokens.py` — 234K-line generated word list, identical across all versions; lives at the project root.
- `test_sources/`, `results/`, `spec_format/output/` — test data.
- `gui/`, `chrome-extension/`, `Website/`, `rag/` — tooling / UI.

## Append-only ID guarantee

Every Spectrum dictionary version only ever APPENDS new tokens to the end of `SPEC_TOKENS`.  This means the token IDs for all previous versions are stable subsets of this version's ID space.  See `spec_format/_frozen/` for the compact snapshots the decoder uses to read files from any older version.