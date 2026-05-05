# Byte-Prism Decode Benchmark

| Rank | Engine | Mean E2E ms | Mean search ms | Mean hydrate ms | Per-corpus E2E ms |
|---:|---|---:|---:|---:|---|
| 1 | Spectrum snippet sidecar | 0.372 | 0.372 | 0.001 | 0.066, 0.069, 0.983 |
| 2 | Raw BM25 | 2.289 | 2.288 | 0.001 | 0.025, 0.048, 6.793 |
| 3 | Spectrum byte-prism cached | 9.928 | 0.393 | 9.534 | 10.315, 4.120, 15.348 |
| 4 | Spectrum byte-prism decode | 52.062 | 0.424 | 51.638 | 94.341, 32.571, 29.274 |
| 5 | Spectrum original decode | 137.158 | 0.475 | 136.683 | 155.115, 137.389, 118.972 |

## Lift

- Byte-prism vs original Spectrum: 2.63x faster E2E.
- Byte-prism cached vs original Spectrum: 13.82x faster E2E.
