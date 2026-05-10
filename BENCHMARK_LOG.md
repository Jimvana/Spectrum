# Spectrum Benchmark Log

Cumulative benchmark history for the active Spectrum retrieval/storage path.

Older corpus-specific benchmark notes have been removed from the active repo
surface. New entries should focus on repeatable code, structured-text, JSONL,
or mixed-document corpora and should include:

- corpus source and size
- raw bytes and stored Spectrum bytes
- index format
- build wall/CPU time
- query latency
- decode latency
- Hit@1, MRR, and Recall@k
- fidelity result
- change note explaining what moved since the prior run

Use `rag/storage_benchmark.py` with `--append-log` or add concise manually
reviewed entries here.
