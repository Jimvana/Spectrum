# Ranking Profiles vs Competition

Hydrate limit is 1: result-list snippets for `spectrum_snippet_sidecar`, and one selected full payload for `spectrum_serving_pipeline`.
Size is measured persisted bytes where the runner exposes them. `raw_tfidf_sklearn` uses the conventional persisted store from the source benchmark; `raw_bm25_python` is an in-process baseline, so the table uses raw payload bytes as its lower-bound footprint.

## java

| Profile | Engine | Hit@1 | MRR | Recall@5 | Search ms | E2E ms | P95 E2E ms | Size bytes |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| competition | dense_lsa_numpy | 0.1664 | 0.2311 | 0.3485 | 10.785 | 10.808 | 11.401 | 1,169,408 |
| competition | raw_bm25_python | 0.2837 | 0.3915 | 0.5692 | 1.343 | 1.345 | 1.672 | 9,418,591 |
| competition | raw_tfidf_sklearn | 0.1629 | 0.2354 | 0.3660 | 0.621 | 0.624 | 0.652 | 10,496,085 |
| off | hybrid_spectrum_dense_rrf | 0.2872 | 0.4103 | 0.6235 | 12.775 | 14.627 | 18.231 | 3,772,846 |
| off | spectrum_serving_pipeline | 0.5692 | 0.6717 | 0.8231 | 1.792 | 3.104 | 7.440 | 2,958,855 |
| off | spectrum_snippet_sidecar | 0.5692 | 0.6717 | 0.8231 | 1.839 | 1.842 | 2.272 | 2,945,660 |
| fast | hybrid_spectrum_dense_rrf | 0.3800 | 0.4834 | 0.6673 | 13.156 | 15.556 | 19.625 | 3,772,846 |
| fast | spectrum_serving_pipeline | 0.7846 | 0.8264 | 0.8792 | 1.937 | 4.011 | 11.085 | 2,958,855 |
| fast | spectrum_snippet_sidecar | 0.7846 | 0.8261 | 0.8792 | 1.923 | 1.926 | 2.360 | 2,945,660 |
| balanced | hybrid_spectrum_dense_rrf | 0.3800 | 0.4834 | 0.6673 | 13.516 | 15.945 | 19.852 | 3,772,846 |
| balanced | spectrum_serving_pipeline | 0.8196 | 0.8655 | 0.9247 | 2.009 | 4.157 | 11.242 | 2,958,855 |
| balanced | spectrum_snippet_sidecar | 0.8179 | 0.8644 | 0.9247 | 2.100 | 2.104 | 2.545 | 2,945,660 |
| accurate | hybrid_spectrum_dense_rrf | 0.3800 | 0.4834 | 0.6673 | 13.316 | 15.713 | 19.845 | 3,772,846 |
| accurate | spectrum_serving_pipeline | 0.8284 | 0.8758 | 0.9370 | 2.115 | 4.394 | 11.882 | 2,958,855 |
| accurate | spectrum_snippet_sidecar | 0.8266 | 0.8746 | 0.9370 | 2.332 | 2.336 | 2.834 | 2,945,660 |

## self

| Profile | Engine | Hit@1 | MRR | Recall@5 | Search ms | E2E ms | P95 E2E ms | Size bytes |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| competition | dense_lsa_numpy | 0.1857 | 0.2523 | 0.3821 | 6.825 | 6.848 | 7.446 | 573,440 |
| competition | raw_bm25_python | 0.2679 | 0.3950 | 0.6071 | 0.182 | 0.184 | 0.370 | 3,704,368 |
| competition | raw_tfidf_sklearn | 0.1857 | 0.2505 | 0.3786 | 0.476 | 0.479 | 0.659 | 4,290,279 |
| off | hybrid_spectrum_dense_rrf | 0.2429 | 0.3302 | 0.4607 | 7.365 | 8.477 | 10.608 | 2,117,124 |
| off | spectrum_serving_pipeline | 0.3107 | 0.3780 | 0.4964 | 0.510 | 1.116 | 3.209 | 1,696,839 |
| off | spectrum_snippet_sidecar | 0.3107 | 0.3780 | 0.4964 | 0.473 | 0.475 | 0.654 | 1,688,693 |
| fast | hybrid_spectrum_dense_rrf | 0.4107 | 0.4993 | 0.6536 | 7.831 | 9.269 | 11.262 | 2,117,124 |
| fast | spectrum_serving_pipeline | 0.6036 | 0.6202 | 0.6429 | 0.543 | 2.098 | 4.982 | 1,696,839 |
| fast | spectrum_snippet_sidecar | 0.5679 | 0.5971 | 0.6429 | 0.541 | 0.544 | 0.746 | 1,688,693 |
| balanced | hybrid_spectrum_dense_rrf | 0.4107 | 0.4993 | 0.6536 | 8.646 | 10.067 | 12.206 | 2,117,124 |
| balanced | spectrum_serving_pipeline | 0.8071 | 0.8310 | 0.8607 | 0.628 | 2.723 | 7.646 | 1,696,839 |
| balanced | spectrum_snippet_sidecar | 0.7429 | 0.7876 | 0.8500 | 0.630 | 0.633 | 0.858 | 1,688,693 |
| accurate | hybrid_spectrum_dense_rrf | 0.4107 | 0.4993 | 0.6536 | 7.766 | 9.192 | 11.029 | 2,117,124 |
| accurate | spectrum_serving_pipeline | 0.8679 | 0.8979 | 0.9357 | 0.694 | 3.369 | 8.971 | 1,696,839 |
| accurate | spectrum_snippet_sidecar | 0.7857 | 0.8396 | 0.9179 | 0.717 | 0.720 | 0.989 | 1,688,693 |

## Takeaways

- java: accurate Spectrum snippet sidecar Hit@1/MRR/Recall@5 = 0.8266/0.8746/0.9370, E2E 2.336 ms, size 2,945,660 bytes.
- java: raw BM25 Hit@1/MRR/Recall@5 = 0.2837/0.3915/0.5692, E2E 1.345 ms; TF-IDF E2E 0.624 ms.
- java: profile Hit@1 lift on Spectrum snippet sidecar, off -> fast -> accurate = 0.5692 -> 0.7846 -> 0.8266.
- self: accurate Spectrum snippet sidecar Hit@1/MRR/Recall@5 = 0.7857/0.8396/0.9179, E2E 0.720 ms, size 1,688,693 bytes.
- self: raw BM25 Hit@1/MRR/Recall@5 = 0.2679/0.3950/0.6071, E2E 0.184 ms; TF-IDF E2E 0.479 ms.
- self: profile Hit@1 lift on Spectrum snippet sidecar, off -> fast -> accurate = 0.3107 -> 0.5679 -> 0.7857.
