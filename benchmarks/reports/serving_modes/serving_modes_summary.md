# Spectrum Serving Modes Summary

## Hydrate top-k full payloads

| Rank | Engine | Mean E2E ms | Mean search ms | Mean hydrate ms | Per-corpus E2E ms |
|---:|---|---:|---:|---:|---|
| 1 | Spectrum snippet sidecar | 0.370 | 0.369 | 0.001 | 0.058, 0.071, 0.982 |
| 2 | Raw TF-IDF | 0.873 | 0.872 | 0.001 | 0.252, 0.265, 2.103 |
| 3 | Raw BM25 | 2.317 | 2.316 | 0.001 | 0.026, 0.047, 6.878 |
| 4 | FAISS vector | 4.075 | 4.071 | 0.004 | 1.065, 2.225, 8.934 |
| 5 | Chroma vector DB | 4.934 | 4.930 | 0.004 | 2.583, 2.477, 9.743 |
| 6 | Spectrum cached decode | 32.967 | 0.417 | 32.551 | 28.595, 21.370, 48.937 |
| 7 | Spectrum full decode | 134.221 | 0.472 | 133.749 | 153.928, 131.605, 117.130 |

## Hydrate final/first result only

| Rank | Engine | Mean E2E ms | Mean search ms | Mean hydrate ms | Per-corpus E2E ms |
|---:|---|---:|---:|---:|---|
| 1 | Spectrum snippet sidecar | 0.377 | 0.377 | 0.001 | 0.068, 0.072, 0.992 |
| 2 | Raw TF-IDF | 0.857 | 0.856 | 0.001 | 0.251, 0.258, 2.063 |
| 3 | Raw BM25 | 2.308 | 2.307 | 0.001 | 0.025, 0.050, 6.849 |
| 4 | FAISS vector | 4.206 | 4.203 | 0.003 | 1.316, 2.335, 8.967 |
| 5 | Chroma vector DB | 5.002 | 4.999 | 0.004 | 2.496, 2.459, 10.052 |
| 6 | Spectrum cached decode | 11.582 | 0.414 | 11.168 | 10.726, 9.680, 14.341 |
| 7 | Spectrum full decode | 30.757 | 0.479 | 30.277 | 31.655, 28.033, 32.582 |

## Spectrum Variants Only

| Mode | Variant | Mean E2E ms | Mean hydrate ms |
|---|---|---:|---:|
| first | Spectrum snippet sidecar | 0.377 | 0.001 |
| first | Spectrum cached decode | 11.582 | 11.168 |
| first | Spectrum full decode | 30.757 | 30.277 |
| full | Spectrum snippet sidecar | 0.370 | 0.001 |
| full | Spectrum cached decode | 32.967 | 32.551 |
| full | Spectrum full decode | 134.221 | 133.749 |
