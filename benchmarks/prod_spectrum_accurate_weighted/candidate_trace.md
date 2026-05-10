# Spectrum Accurate Weighted Candidate Trace

- Docs: 72,601
- Queries: 80
- Policy: graded_weighting=True, min_candidate_weight=0.05, min_strong_matches=0.35, max_precandidates=2000
- Accuracy: Hit@1=0.7375, MRR=0.7438, Recall@5=0.75

## Summary

| Metric | Avg | P95 | Max | Min |
|---|---:|---:|---:|---:|
| raw_postings_matches | 72601 | 72601 | 72601 | 72601 |
| initial_postings_matches | 1483.4 | 2000 | 2000 | 0 |
| reranker_in | 43.75 | 50 | 50 | 0 |
| hydrated | 4.375 | 5 | 5 | 0 |
| retrieval_ms | 2.9331 | 5.6488 | 6.8469 | 0.1066 |
| rerank_ms | 0.3081 | 0.5092 | 0.6186 | 0.0099 |
| hydrate_ms | 3.9564 | 5.2746 | 124.4589 | 0.0006 |
| e2e_ms | 7.1975 | 9.1235 | 126.2436 | 0.1173 |

## Queries

### 01. clippy

- raw_postings_matches: 72,601
- weighted_candidates_after_policy: 0
- reranker_in: 0
- hydrated: 0
- time_ms: retrieval=0.1395, rerank=0.0114, hydrate=0.0009, e2e=0.1518
- hit_rank: -

| token | df | df ratio | postings length | token type | candidate weight | action |
|---|---:|---:|---:|---|---:|---|
| `CTRL:BEGIN_WORD` | 72601 | 1.000000 | 72601 | common | 0.000000 | rerank_only |
| `CTRL:END_WORD` | 72601 | 1.000000 | 72601 | common | 0.000000 | rerank_only |

### 02. rustfmt

- raw_postings_matches: 72,601
- weighted_candidates_after_policy: 0
- reranker_in: 0
- hydrated: 0
- time_ms: retrieval=0.1066, rerank=0.0099, hydrate=0.0008, e2e=0.1173
- hit_rank: -

| token | df | df ratio | postings length | token type | candidate weight | action |
|---|---:|---:|---:|---|---:|---|
| `CTRL:BEGIN_WORD` | 72601 | 1.000000 | 72601 | common | 0.000000 | rerank_only |
| `CTRL:END_WORD` | 72601 | 1.000000 | 72601 | common | 0.000000 | rerank_only |

### 03. renames documentation

- raw_postings_matches: 72,601
- weighted_candidates_after_policy: 709
- reranker_in: 50
- hydrated: 5
- time_ms: retrieval=1.7098, rerank=0.2172, hydrate=51.7749, e2e=53.7019
- hit_rank: -

| token | df | df ratio | postings length | token type | candidate weight | action |
|---|---:|---:|---:|---|---:|---|
| `CTRL:BEGIN_WORD` | 72601 | 1.000000 | 72601 | common | 0.000001 | rerank_only |
| `CTRL:END_WORD` | 72601 | 1.000000 | 72601 | common | 0.000001 | rerank_only |
| ` ` | 72601 | 1.000000 | 72601 | common | 0.000001 | rerank_only |
| `documentation` | 12615 | 0.173758 | 12615 | common | 0.156357 | generate |
| `rename` | 709 | 0.009766 | 709 | rare | 0.413499 | generate |

### 04. rtfp documentation rcu

- raw_postings_matches: 72,601
- weighted_candidates_after_policy: 0
- reranker_in: 0
- hydrated: 0
- time_ms: retrieval=0.5188, rerank=0.0127, hydrate=0.0035, e2e=0.5350
- hit_rank: -

| token | df | df ratio | postings length | token type | candidate weight | action |
|---|---:|---:|---:|---|---:|---|
| `CTRL:BEGIN_WORD` | 72601 | 1.000000 | 72601 | common | 0.000000 | rerank_only |
| `CTRL:END_WORD` | 72601 | 1.000000 | 72601 | common | 0.000000 | rerank_only |
| ` ` | 72601 | 1.000000 | 72601 | common | 0.000000 | rerank_only |
| `documentation` | 12615 | 0.173758 | 12615 | common | 0.000000 | generate |

### 05. autoload documentation admin guide aoe

- raw_postings_matches: 72,601
- weighted_candidates_after_policy: 359
- reranker_in: 50
- hydrated: 5
- time_ms: retrieval=1.5012, rerank=0.2835, hydrate=124.4589, e2e=126.2436
- hit_rank: 1

| token | df | df ratio | postings length | token type | candidate weight | action |
|---|---:|---:|---:|---|---:|---|
| `CTRL:BEGIN_WORD` | 72601 | 1.000000 | 72601 | common | 0.000001 | rerank_only |
| `CTRL:END_WORD` | 72601 | 1.000000 | 72601 | common | 0.000001 | rerank_only |
| ` ` | 72601 | 1.000000 | 72601 | common | 0.000001 | rerank_only |
| `documentation` | 12615 | 0.173758 | 12615 | common | 0.156357 | generate |
| `guide` | 359 | 0.004945 | 359 | rare | 0.474239 | generate |

### 06. status documentation admin guide aoe

- raw_postings_matches: 72,601
- weighted_candidates_after_policy: 359
- reranker_in: 50
- hydrated: 5
- time_ms: retrieval=2.0530, rerank=0.5231, hydrate=0.0209, e2e=2.5970
- hit_rank: 1

| token | df | df ratio | postings length | token type | candidate weight | action |
|---|---:|---:|---:|---|---:|---|
| `status` | 18645 | 0.256815 | 18645 | common | 0.121453 | generate |
| ` ` | 72601 | 1.000000 | 72601 | common | 0.000001 | rerank_only |
| `documentation` | 12615 | 0.173758 | 12615 | common | 0.156357 | generate |
| `CTRL:BEGIN_WORD` | 72601 | 1.000000 | 72601 | common | 0.000001 | rerank_only |
| `CTRL:END_WORD` | 72601 | 1.000000 | 72601 | common | 0.000001 | rerank_only |
| `guide` | 359 | 0.004945 | 359 | rare | 0.474239 | generate |

### 07. udev install documentation admin guide aoe

- raw_postings_matches: 72,601
- weighted_candidates_after_policy: 2,000
- reranker_in: 50
- hydrated: 5
- time_ms: retrieval=2.2538, rerank=0.2959, hydrate=23.4042, e2e=25.9539
- hit_rank: 1

| token | df | df ratio | postings length | token type | candidate weight | action |
|---|---:|---:|---:|---|---:|---|
| `CTRL:BEGIN_WORD` | 72601 | 1.000000 | 72601 | common | 0.000001 | rerank_only |
| `CTRL:END_WORD` | 72601 | 1.000000 | 72601 | common | 0.000001 | rerank_only |
| ` ` | 72601 | 1.000000 | 72601 | common | 0.000001 | rerank_only |
| `install` | 1771 | 0.024394 | 1771 | rare | 0.350000 | generate |
| `documentation` | 12615 | 0.173758 | 12615 | common | 0.156357 | generate |
| `guide` | 359 | 0.004945 | 359 | rare | 0.474239 | generate |

### 08. udev documentation admin guide aoe

- raw_postings_matches: 72,601
- weighted_candidates_after_policy: 359
- reranker_in: 50
- hydrated: 5
- time_ms: retrieval=1.4247, rerank=0.2868, hydrate=0.0184, e2e=1.7299
- hit_rank: 1

| token | df | df ratio | postings length | token type | candidate weight | action |
|---|---:|---:|---:|---|---:|---|
| `CTRL:BEGIN_WORD` | 72601 | 1.000000 | 72601 | common | 0.000001 | rerank_only |
| `CTRL:END_WORD` | 72601 | 1.000000 | 72601 | common | 0.000001 | rerank_only |
| ` ` | 72601 | 1.000000 | 72601 | common | 0.000001 | rerank_only |
| `documentation` | 12615 | 0.173758 | 12615 | common | 0.156357 | generate |
| `guide` | 359 | 0.004945 | 359 | rare | 0.474239 | generate |

### 09. devices documentation admin guide

- raw_postings_matches: 72,601
- weighted_candidates_after_policy: 359
- reranker_in: 50
- hydrated: 5
- time_ms: retrieval=2.8507, rerank=0.2769, hydrate=44.7141, e2e=47.8417
- hit_rank: 1

| token | df | df ratio | postings length | token type | candidate weight | action |
|---|---:|---:|---:|---|---:|---|
| `CTRL:BEGIN_WORD` | 72601 | 1.000000 | 72601 | common | 0.000001 | rerank_only |
| `CTRL:END_WORD` | 72601 | 1.000000 | 72601 | common | 0.000001 | rerank_only |
| ` ` | 72601 | 1.000000 | 72601 | common | 0.000001 | rerank_only |
| `documentation` | 12615 | 0.173758 | 12615 | common | 0.156357 | generate |
| `guide` | 359 | 0.004945 | 359 | rare | 0.474239 | generate |
| `device` | 35573 | 0.489979 | 35573 | common | 0.063737 | generate |

### 10. gdbmacros documentation admin guide kdump

- raw_postings_matches: 72,601
- weighted_candidates_after_policy: 359
- reranker_in: 50
- hydrated: 5
- time_ms: retrieval=1.8339, rerank=0.2868, hydrate=3.6686, e2e=5.7893
- hit_rank: 1

| token | df | df ratio | postings length | token type | candidate weight | action |
|---|---:|---:|---:|---|---:|---|
| `CTRL:BEGIN_WORD` | 72601 | 1.000000 | 72601 | common | 0.000001 | rerank_only |
| `CTRL:END_WORD` | 72601 | 1.000000 | 72601 | common | 0.000001 | rerank_only |
| ` ` | 72601 | 1.000000 | 72601 | common | 0.000001 | rerank_only |
| `documentation` | 12615 | 0.173758 | 12615 | common | 0.156357 | generate |
| `guide` | 359 | 0.004945 | 359 | rare | 0.474239 | generate |

### 11. kernel parameters documentation admin guide

- raw_postings_matches: 72,601
- weighted_candidates_after_policy: 359
- reranker_in: 50
- hydrated: 5
- time_ms: retrieval=2.6804, rerank=0.2937, hydrate=0.0184, e2e=2.9925
- hit_rank: 1

| token | df | df ratio | postings length | token type | candidate weight | action |
|---|---:|---:|---:|---|---:|---|
| `kernel` | 28111 | 0.387199 | 28111 | common | 0.084770 | generate |
| ` ` | 72601 | 1.000000 | 72601 | common | 0.000001 | rerank_only |
| `CTRL:BEGIN_WORD` | 72601 | 1.000000 | 72601 | common | 0.000001 | rerank_only |
| `CTRL:END_WORD` | 72601 | 1.000000 | 72601 | common | 0.000001 | rerank_only |
| `documentation` | 12615 | 0.173758 | 12615 | common | 0.156357 | generate |
| `guide` | 359 | 0.004945 | 359 | rare | 0.474239 | generate |
| `parameter` | 7513 | 0.103483 | 7513 | common | 0.202657 | generate |

### 12. spkguide documentation admin guide

- raw_postings_matches: 72,601
- weighted_candidates_after_policy: 359
- reranker_in: 50
- hydrated: 5
- time_ms: retrieval=1.4342, rerank=0.2642, hydrate=0.0179, e2e=1.7163
- hit_rank: 1

| token | df | df ratio | postings length | token type | candidate weight | action |
|---|---:|---:|---:|---|---:|---|
| `CTRL:BEGIN_WORD` | 72601 | 1.000000 | 72601 | common | 0.000001 | rerank_only |
| `CTRL:END_WORD` | 72601 | 1.000000 | 72601 | common | 0.000001 | rerank_only |
| ` ` | 72601 | 1.000000 | 72601 | common | 0.000001 | rerank_only |
| `documentation` | 12615 | 0.173758 | 12615 | common | 0.156357 | generate |
| `guide` | 359 | 0.004945 | 359 | rare | 0.474239 | generate |

### 13. kasan offsets documentation arch arm64

- raw_postings_matches: 72,601
- weighted_candidates_after_policy: 2,000
- reranker_in: 50
- hydrated: 5
- time_ms: retrieval=4.6164, rerank=0.3548, hydrate=3.5899, e2e=8.5611
- hit_rank: 1

| token | df | df ratio | postings length | token type | candidate weight | action |
|---|---:|---:|---:|---|---:|---|
| `CTRL:BEGIN_WORD` | 72601 | 1.000000 | 72601 | common | 0.000001 | rerank_only |
| `CTRL:END_WORD` | 72601 | 1.000000 | 72601 | common | 0.000001 | rerank_only |
| ` ` | 72601 | 1.000000 | 72601 | common | 0.000001 | rerank_only |
| `documentation` | 12615 | 0.173758 | 12615 | common | 0.156357 | generate |
| `arch` | 13130 | 0.180852 | 13130 | common | 0.152782 | generate |
| `arm` | 6315 | 0.086982 | 6315 | identifier/path | 0.350000 | generate |
| `6` | 54632 | 0.752497 | 54632 | common | 0.025406 | rerank_only |
| `CTRL:NUM_SEP` | 60437 | 0.832454 | 60437 | common | 0.016384 | rerank_only |
| `4` | 56023 | 0.771656 | 56023 | common | 0.023160 | rerank_only |
| `offset` | 19974 | 0.275120 | 19974 | common | 0.115301 | generate |

### 14. kasan documentation arch powerpc

- raw_postings_matches: 72,601
- weighted_candidates_after_policy: 0
- reranker_in: 0
- hydrated: 0
- time_ms: retrieval=0.7524, rerank=0.0172, hydrate=0.0037, e2e=0.7733
- hit_rank: -

| token | df | df ratio | postings length | token type | candidate weight | action |
|---|---:|---:|---:|---|---:|---|
| `CTRL:BEGIN_WORD` | 72601 | 1.000000 | 72601 | common | 0.000000 | rerank_only |
| `CTRL:END_WORD` | 72601 | 1.000000 | 72601 | common | 0.000000 | rerank_only |
| ` ` | 72601 | 1.000000 | 72601 | common | 0.000000 | rerank_only |
| `documentation` | 12615 | 0.173758 | 12615 | common | 0.000000 | generate |
| `arch` | 13130 | 0.180852 | 13130 | common | 0.000000 | generate |

### 15. config3270 documentation arch s390

- raw_postings_matches: 72,601
- weighted_candidates_after_policy: 0
- reranker_in: 0
- hydrated: 0
- time_ms: retrieval=0.5994, rerank=0.0145, hydrate=0.0007, e2e=0.6146
- hit_rank: -

| token | df | df ratio | postings length | token type | candidate weight | action |
|---|---:|---:|---:|---|---:|---|
| `CTRL:BEGIN_WORD` | 72601 | 1.000000 | 72601 | common | 0.000000 | rerank_only |
| `CTRL:END_WORD` | 72601 | 1.000000 | 72601 | common | 0.000000 | rerank_only |
| `3` | 58661 | 0.807992 | 58661 | common | 0.000000 | rerank_only |
| `CTRL:NUM_SEP` | 60437 | 0.832454 | 60437 | common | 0.000000 | rerank_only |
| `2` | 71667 | 0.987135 | 71667 | common | 0.000000 | rerank_only |
| `7` | 38264 | 0.527045 | 38264 | common | 0.000000 | generate |
| `0` | 71675 | 0.987245 | 71675 | common | 0.000000 | rerank_only |
| ` ` | 72601 | 1.000000 | 72601 | common | 0.000000 | rerank_only |
| `documentation` | 12615 | 0.173758 | 12615 | common | 0.000000 | generate |
| `arch` | 13130 | 0.180852 | 13130 | common | 0.000000 | generate |
| `9` | 37927 | 0.522403 | 37927 | common | 0.000000 | generate |

### 16. dax hv api documentation arch sparc oradax

- raw_postings_matches: 72,601
- weighted_candidates_after_policy: 0
- reranker_in: 0
- hydrated: 0
- time_ms: retrieval=0.7061, rerank=0.0162, hydrate=0.0008, e2e=0.7231
- hit_rank: -

| token | df | df ratio | postings length | token type | candidate weight | action |
|---|---:|---:|---:|---|---:|---|
| `CTRL:BEGIN_WORD` | 72601 | 1.000000 | 72601 | common | 0.000000 | rerank_only |
| `CTRL:END_WORD` | 72601 | 1.000000 | 72601 | common | 0.000000 | rerank_only |
| ` ` | 72601 | 1.000000 | 72601 | common | 0.000000 | rerank_only |
| `documentation` | 12615 | 0.173758 | 12615 | common | 0.000000 | generate |
| `arch` | 13130 | 0.180852 | 13130 | common | 0.000000 | generate |

### 17. atomic bitops documentation

- raw_postings_matches: 72,601
- weighted_candidates_after_policy: 0
- reranker_in: 0
- hydrated: 0
- time_ms: retrieval=0.5911, rerank=0.0128, hydrate=0.0009, e2e=0.6048
- hit_rank: -

| token | df | df ratio | postings length | token type | candidate weight | action |
|---|---:|---:|---:|---|---:|---|
| `atomic` | 8621 | 0.118745 | 8621 | common | 0.000000 | generate |
| ` ` | 72601 | 1.000000 | 72601 | common | 0.000000 | rerank_only |
| `CTRL:BEGIN_WORD` | 72601 | 1.000000 | 72601 | common | 0.000000 | rerank_only |
| `CTRL:END_WORD` | 72601 | 1.000000 | 72601 | common | 0.000000 | rerank_only |
| `documentation` | 12615 | 0.173758 | 12615 | common | 0.000000 | generate |

### 18. atomic documentation

- raw_postings_matches: 72,601
- weighted_candidates_after_policy: 0
- reranker_in: 0
- hydrated: 0
- time_ms: retrieval=0.4904, rerank=0.0112, hydrate=0.0006, e2e=0.5022
- hit_rank: -

| token | df | df ratio | postings length | token type | candidate weight | action |
|---|---:|---:|---:|---|---:|---|
| `atomic` | 8621 | 0.118745 | 8621 | common | 0.000000 | generate |
| ` ` | 72601 | 1.000000 | 72601 | common | 0.000000 | rerank_only |
| `documentation` | 12615 | 0.173758 | 12615 | common | 0.000000 | generate |

### 19. conf documentation

- raw_postings_matches: 72,601
- weighted_candidates_after_policy: 0
- reranker_in: 0
- hydrated: 0
- time_ms: retrieval=0.5732, rerank=0.0114, hydrate=0.0006, e2e=0.5852
- hit_rank: -

| token | df | df ratio | postings length | token type | candidate weight | action |
|---|---:|---:|---:|---|---:|---|
| `CTRL:BEGIN_WORD` | 72601 | 1.000000 | 72601 | common | 0.000000 | rerank_only |
| `CTRL:END_WORD` | 72601 | 1.000000 | 72601 | common | 0.000000 | rerank_only |
| ` ` | 72601 | 1.000000 | 72601 | common | 0.000000 | rerank_only |
| `documentation` | 12615 | 0.173758 | 12615 | common | 0.000000 | generate |

### 20. access controllers documentation devicetree bindings access

- raw_postings_matches: 72,601
- weighted_candidates_after_policy: 0
- reranker_in: 0
- hydrated: 0
- time_ms: retrieval=0.6659, rerank=0.0169, hydrate=0.0007, e2e=0.6835
- hit_rank: -

| token | df | df ratio | postings length | token type | candidate weight | action |
|---|---:|---:|---:|---|---:|---|
| `access` | 12103 | 0.166706 | 12103 | common | 0.000000 | generate |
| ` ` | 72601 | 1.000000 | 72601 | common | 0.000000 | rerank_only |
| `CTRL:BEGIN_WORD` | 72601 | 1.000000 | 72601 | common | 0.000000 | rerank_only |
| `CTRL:END_WORD` | 72601 | 1.000000 | 72601 | common | 0.000000 | rerank_only |
| `documentation` | 12615 | 0.173758 | 12615 | common | 0.000000 | generate |
| `controller` | 10921 | 0.150425 | 10921 | common | 0.000000 | generate |
| `binding` | 9619 | 0.132491 | 9619 | common | 0.000000 | generate |

### 21. axs101 documentation devicetree bindings arc

- raw_postings_matches: 72,601
- weighted_candidates_after_policy: 575
- reranker_in: 50
- hydrated: 5
- time_ms: retrieval=2.1118, rerank=0.2916, hydrate=1.7819, e2e=4.1853
- hit_rank: 1

| token | df | df ratio | postings length | token type | candidate weight | action |
|---|---:|---:|---:|---|---:|---|
| `CTRL:BEGIN_WORD` | 72601 | 1.000000 | 72601 | common | 0.000001 | rerank_only |
| `CTRL:END_WORD` | 72601 | 1.000000 | 72601 | common | 0.000001 | rerank_only |
| `1` | 66053 | 0.909808 | 66053 | common | 0.008445 | rerank_only |
| `CTRL:NUM_SEP` | 60437 | 0.832454 | 60437 | common | 0.016384 | rerank_only |
| `0` | 71675 | 0.987245 | 71675 | common | 0.001147 | rerank_only |
| ` ` | 72601 | 1.000000 | 72601 | common | 0.000001 | rerank_only |
| `documentation` | 12615 | 0.173758 | 12615 | common | 0.156357 | generate |
| `arc` | 575 | 0.007920 | 575 | rare | 0.432200 | generate |
| `binding` | 9619 | 0.132491 | 9619 | common | 0.180581 | generate |

### 22. axs103 documentation devicetree bindings arc

- raw_postings_matches: 72,601
- weighted_candidates_after_policy: 575
- reranker_in: 50
- hydrated: 5
- time_ms: retrieval=2.1027, rerank=0.2829, hydrate=0.4791, e2e=2.8647
- hit_rank: 1

| token | df | df ratio | postings length | token type | candidate weight | action |
|---|---:|---:|---:|---|---:|---|
| `CTRL:BEGIN_WORD` | 72601 | 1.000000 | 72601 | common | 0.000001 | rerank_only |
| `CTRL:END_WORD` | 72601 | 1.000000 | 72601 | common | 0.000001 | rerank_only |
| `1` | 66053 | 0.909808 | 66053 | common | 0.008445 | rerank_only |
| `CTRL:NUM_SEP` | 60437 | 0.832454 | 60437 | common | 0.016384 | rerank_only |
| `0` | 71675 | 0.987245 | 71675 | common | 0.001147 | rerank_only |
| `3` | 58661 | 0.807992 | 58661 | common | 0.019049 | rerank_only |
| ` ` | 72601 | 1.000000 | 72601 | common | 0.000001 | rerank_only |
| `documentation` | 12615 | 0.173758 | 12615 | common | 0.156357 | generate |
| `arc` | 575 | 0.007920 | 575 | rare | 0.432200 | generate |
| `binding` | 9619 | 0.132491 | 9619 | common | 0.180581 | generate |

### 23. eznps documentation devicetree bindings arc

- raw_postings_matches: 72,601
- weighted_candidates_after_policy: 575
- reranker_in: 50
- hydrated: 5
- time_ms: retrieval=2.1046, rerank=0.2946, hydrate=0.1777, e2e=2.5769
- hit_rank: 1

| token | df | df ratio | postings length | token type | candidate weight | action |
|---|---:|---:|---:|---|---:|---|
| `CTRL:BEGIN_WORD` | 72601 | 1.000000 | 72601 | common | 0.000001 | rerank_only |
| `CTRL:END_WORD` | 72601 | 1.000000 | 72601 | common | 0.000001 | rerank_only |
| ` ` | 72601 | 1.000000 | 72601 | common | 0.000001 | rerank_only |
| `documentation` | 12615 | 0.173758 | 12615 | common | 0.156357 | generate |
| `arc` | 575 | 0.007920 | 575 | rare | 0.432200 | generate |
| `binding` | 9619 | 0.132491 | 9619 | common | 0.180581 | generate |

### 24. hsdk documentation devicetree bindings arc

- raw_postings_matches: 72,601
- weighted_candidates_after_policy: 575
- reranker_in: 50
- hydrated: 5
- time_ms: retrieval=2.1009, rerank=0.2840, hydrate=0.1962, e2e=2.5811
- hit_rank: 1

| token | df | df ratio | postings length | token type | candidate weight | action |
|---|---:|---:|---:|---|---:|---|
| `CTRL:BEGIN_WORD` | 72601 | 1.000000 | 72601 | common | 0.000001 | rerank_only |
| `CTRL:END_WORD` | 72601 | 1.000000 | 72601 | common | 0.000001 | rerank_only |
| ` ` | 72601 | 1.000000 | 72601 | common | 0.000001 | rerank_only |
| `documentation` | 12615 | 0.173758 | 12615 | common | 0.156357 | generate |
| `arc` | 575 | 0.007920 | 575 | rare | 0.432200 | generate |
| `binding` | 9619 | 0.132491 | 9619 | common | 0.180581 | generate |

### 25. pct documentation devicetree bindings arc

- raw_postings_matches: 72,601
- weighted_candidates_after_policy: 575
- reranker_in: 50
- hydrated: 5
- time_ms: retrieval=2.0427, rerank=0.2787, hydrate=0.5657, e2e=2.8871
- hit_rank: 1

| token | df | df ratio | postings length | token type | candidate weight | action |
|---|---:|---:|---:|---|---:|---|
| `CTRL:BEGIN_WORD` | 72601 | 1.000000 | 72601 | common | 0.000001 | rerank_only |
| `CTRL:END_WORD` | 72601 | 1.000000 | 72601 | common | 0.000001 | rerank_only |
| ` ` | 72601 | 1.000000 | 72601 | common | 0.000001 | rerank_only |
| `documentation` | 12615 | 0.173758 | 12615 | common | 0.156357 | generate |
| `arc` | 575 | 0.007920 | 575 | rare | 0.432200 | generate |
| `binding` | 9619 | 0.132491 | 9619 | common | 0.180581 | generate |

### 26. snps,archs pct documentation devicetree bindings arc

- raw_postings_matches: 72,601
- weighted_candidates_after_policy: 575
- reranker_in: 50
- hydrated: 5
- time_ms: retrieval=2.8979, rerank=0.3001, hydrate=0.9825, e2e=4.1805
- hit_rank: 1

| token | df | df ratio | postings length | token type | candidate weight | action |
|---|---:|---:|---:|---|---:|---|
| `CTRL:BEGIN_WORD` | 72601 | 1.000000 | 72601 | common | 0.000001 | rerank_only |
| `CTRL:END_WORD` | 72601 | 1.000000 | 72601 | common | 0.000001 | rerank_only |
| `,` | 67976 | 0.936296 | 67976 | common | 0.005882 | rerank_only |
| ` ` | 72601 | 1.000000 | 72601 | common | 0.000001 | rerank_only |
| `documentation` | 12615 | 0.173758 | 12615 | common | 0.156357 | generate |
| `arc` | 575 | 0.007920 | 575 | rare | 0.432200 | generate |
| `arch` | 13130 | 0.180852 | 13130 | common | 0.152782 | generate |
| `binding` | 9619 | 0.132491 | 9619 | common | 0.180581 | generate |

### 27. actions documentation devicetree bindings arm

- raw_postings_matches: 72,601
- weighted_candidates_after_policy: 2,000
- reranker_in: 50
- hydrated: 5
- time_ms: retrieval=3.5859, rerank=0.2959, hydrate=1.7458, e2e=5.6276
- hit_rank: 1

| token | df | df ratio | postings length | token type | candidate weight | action |
|---|---:|---:|---:|---|---:|---|
| `CTRL:BEGIN_WORD` | 72601 | 1.000000 | 72601 | common | 0.000001 | rerank_only |
| `CTRL:END_WORD` | 72601 | 1.000000 | 72601 | common | 0.000001 | rerank_only |
| ` ` | 72601 | 1.000000 | 72601 | common | 0.000001 | rerank_only |
| `documentation` | 12615 | 0.173758 | 12615 | common | 0.156357 | generate |
| `arm` | 6315 | 0.086982 | 6315 | identifier/path | 0.350000 | generate |
| `action` | 9346 | 0.128731 | 9346 | common | 0.183153 | generate |
| `binding` | 9619 | 0.132491 | 9619 | common | 0.180581 | generate |

### 28. airoha,en7581 chip scu documentation devicetree bindings arm

- raw_postings_matches: 72,601
- weighted_candidates_after_policy: 2,000
- reranker_in: 50
- hydrated: 5
- time_ms: retrieval=5.8701, rerank=0.6186, hydrate=0.8726, e2e=7.3613
- hit_rank: 1

| token | df | df ratio | postings length | token type | candidate weight | action |
|---|---:|---:|---:|---|---:|---|
| `CTRL:BEGIN_WORD` | 72601 | 1.000000 | 72601 | common | 0.000001 | rerank_only |
| `CTRL:END_WORD` | 72601 | 1.000000 | 72601 | common | 0.000001 | rerank_only |
| `,` | 67976 | 0.936296 | 67976 | common | 0.005882 | rerank_only |
| `en` | 9582 | 0.131982 | 9582 | common | 0.180926 | generate |
| `7` | 38264 | 0.527045 | 38264 | common | 0.057222 | generate |
| `CTRL:NUM_SEP` | 60437 | 0.832454 | 60437 | common | 0.016384 | rerank_only |
| `5` | 47367 | 0.652429 | 47367 | common | 0.038155 | rerank_only |
| `8` | 51787 | 0.713310 | 51787 | common | 0.030184 | rerank_only |
| `1` | 66053 | 0.909808 | 66053 | common | 0.008445 | rerank_only |
| ` ` | 72601 | 1.000000 | 72601 | common | 0.000001 | rerank_only |
| `chip` | 8765 | 0.120728 | 8765 | common | 0.188887 | generate |
| `documentation` | 12615 | 0.173758 | 12615 | common | 0.156357 | generate |
| `arm` | 6315 | 0.086982 | 6315 | identifier/path | 0.350000 | generate |
| `binding` | 9619 | 0.132491 | 9619 | common | 0.180581 | generate |

### 29. airoha documentation devicetree bindings arm

- raw_postings_matches: 72,601
- weighted_candidates_after_policy: 2,000
- reranker_in: 50
- hydrated: 5
- time_ms: retrieval=3.4317, rerank=0.3151, hydrate=0.0203, e2e=3.7671
- hit_rank: 1

| token | df | df ratio | postings length | token type | candidate weight | action |
|---|---:|---:|---:|---|---:|---|
| `CTRL:BEGIN_WORD` | 72601 | 1.000000 | 72601 | common | 0.000001 | rerank_only |
| `CTRL:END_WORD` | 72601 | 1.000000 | 72601 | common | 0.000001 | rerank_only |
| ` ` | 72601 | 1.000000 | 72601 | common | 0.000001 | rerank_only |
| `documentation` | 12615 | 0.173758 | 12615 | common | 0.156357 | generate |
| `arm` | 6315 | 0.086982 | 6315 | identifier/path | 0.350000 | generate |
| `binding` | 9619 | 0.132491 | 9619 | common | 0.180581 | generate |

### 30. altera documentation devicetree bindings arm

- raw_postings_matches: 72,601
- weighted_candidates_after_policy: 2,000
- reranker_in: 50
- hydrated: 5
- time_ms: retrieval=3.6619, rerank=0.3199, hydrate=0.3390, e2e=4.3208
- hit_rank: -

| token | df | df ratio | postings length | token type | candidate weight | action |
|---|---:|---:|---:|---|---:|---|
| `CTRL:BEGIN_WORD` | 72601 | 1.000000 | 72601 | common | 0.000001 | rerank_only |
| `CTRL:END_WORD` | 72601 | 1.000000 | 72601 | common | 0.000001 | rerank_only |
| ` ` | 72601 | 1.000000 | 72601 | common | 0.000001 | rerank_only |
| `documentation` | 12615 | 0.173758 | 12615 | common | 0.156357 | generate |
| `arm` | 6315 | 0.086982 | 6315 | identifier/path | 0.350000 | generate |
| `binding` | 9619 | 0.132491 | 9619 | common | 0.180581 | generate |

### 31. socfpga clk manager documentation devicetree bindings arm altera

- raw_postings_matches: 72,601
- weighted_candidates_after_policy: 2,000
- reranker_in: 50
- hydrated: 5
- time_ms: retrieval=3.6721, rerank=0.4564, hydrate=4.4119, e2e=8.5404
- hit_rank: 1

| token | df | df ratio | postings length | token type | candidate weight | action |
|---|---:|---:|---:|---|---:|---|
| `CTRL:BEGIN_WORD` | 72601 | 1.000000 | 72601 | common | 0.000001 | rerank_only |
| `CTRL:END_WORD` | 72601 | 1.000000 | 72601 | common | 0.000001 | rerank_only |
| ` ` | 72601 | 1.000000 | 72601 | common | 0.000001 | rerank_only |
| `manager` | 1396 | 0.019228 | 1396 | rare | 0.352999 | generate |
| `documentation` | 12615 | 0.173758 | 12615 | common | 0.156357 | generate |
| `arm` | 6315 | 0.086982 | 6315 | identifier/path | 0.350000 | generate |
| `binding` | 9619 | 0.132491 | 9619 | common | 0.180581 | generate |

### 32. amazon,al documentation devicetree bindings arm

- raw_postings_matches: 72,601
- weighted_candidates_after_policy: 2,000
- reranker_in: 50
- hydrated: 5
- time_ms: retrieval=3.1320, rerank=0.3326, hydrate=1.9521, e2e=5.4167
- hit_rank: 1

| token | df | df ratio | postings length | token type | candidate weight | action |
|---|---:|---:|---:|---|---:|---|
| `amazon` | 121 | 0.001667 | 121 | rare | 0.571159 | generate |
| `,` | 67976 | 0.936296 | 67976 | common | 0.005882 | rerank_only |
| `al` | 718 | 0.009890 | 718 | rare | 0.412373 | generate |
| ` ` | 72601 | 1.000000 | 72601 | common | 0.000001 | rerank_only |
| `documentation` | 12615 | 0.173758 | 12615 | common | 0.156357 | generate |
| `CTRL:BEGIN_WORD` | 72601 | 1.000000 | 72601 | common | 0.000001 | rerank_only |
| `CTRL:END_WORD` | 72601 | 1.000000 | 72601 | common | 0.000001 | rerank_only |
| `arm` | 6315 | 0.086982 | 6315 | identifier/path | 0.350000 | generate |
| `binding` | 9619 | 0.132491 | 9619 | common | 0.180581 | generate |

### 33. amd,pensando documentation devicetree bindings arm

- raw_postings_matches: 72,601
- weighted_candidates_after_policy: 2,000
- reranker_in: 50
- hydrated: 5
- time_ms: retrieval=3.0170, rerank=0.3107, hydrate=0.3907, e2e=3.7184
- hit_rank: 1

| token | df | df ratio | postings length | token type | candidate weight | action |
|---|---:|---:|---:|---|---:|---|
| `CTRL:BEGIN_WORD` | 72601 | 1.000000 | 72601 | common | 0.000001 | rerank_only |
| `CTRL:END_WORD` | 72601 | 1.000000 | 72601 | common | 0.000001 | rerank_only |
| `,` | 67976 | 0.936296 | 67976 | common | 0.005882 | rerank_only |
| ` ` | 72601 | 1.000000 | 72601 | common | 0.000001 | rerank_only |
| `documentation` | 12615 | 0.173758 | 12615 | common | 0.156357 | generate |
| `arm` | 6315 | 0.086982 | 6315 | identifier/path | 0.350000 | generate |
| `binding` | 9619 | 0.132491 | 9619 | common | 0.180581 | generate |

### 34. amd,seattle documentation devicetree bindings arm

- raw_postings_matches: 72,601
- weighted_candidates_after_policy: 2,000
- reranker_in: 50
- hydrated: 5
- time_ms: retrieval=3.1794, rerank=0.4203, hydrate=0.0196, e2e=3.6193
- hit_rank: 1

| token | df | df ratio | postings length | token type | candidate weight | action |
|---|---:|---:|---:|---|---:|---|
| `CTRL:BEGIN_WORD` | 72601 | 1.000000 | 72601 | common | 0.000001 | rerank_only |
| `CTRL:END_WORD` | 72601 | 1.000000 | 72601 | common | 0.000001 | rerank_only |
| `,` | 67976 | 0.936296 | 67976 | common | 0.005882 | rerank_only |
| ` ` | 72601 | 1.000000 | 72601 | common | 0.000001 | rerank_only |
| `documentation` | 12615 | 0.173758 | 12615 | common | 0.156357 | generate |
| `arm` | 6315 | 0.086982 | 6315 | identifier/path | 0.350000 | generate |
| `binding` | 9619 | 0.132491 | 9619 | common | 0.180581 | generate |

### 35. amlogic documentation devicetree bindings arm

- raw_postings_matches: 72,601
- weighted_candidates_after_policy: 2,000
- reranker_in: 50
- hydrated: 5
- time_ms: retrieval=3.1900, rerank=0.3462, hydrate=0.0213, e2e=3.5575
- hit_rank: -

| token | df | df ratio | postings length | token type | candidate weight | action |
|---|---:|---:|---:|---|---:|---|
| `CTRL:BEGIN_WORD` | 72601 | 1.000000 | 72601 | common | 0.000001 | rerank_only |
| `CTRL:END_WORD` | 72601 | 1.000000 | 72601 | common | 0.000001 | rerank_only |
| ` ` | 72601 | 1.000000 | 72601 | common | 0.000001 | rerank_only |
| `documentation` | 12615 | 0.173758 | 12615 | common | 0.156357 | generate |
| `arm` | 6315 | 0.086982 | 6315 | identifier/path | 0.350000 | generate |
| `binding` | 9619 | 0.132491 | 9619 | common | 0.180581 | generate |

### 36. amlogic,meson gx ao secure documentation devicetree bindings arm amlogic

- raw_postings_matches: 72,601
- weighted_candidates_after_policy: 2,000
- reranker_in: 50
- hydrated: 5
- time_ms: retrieval=3.9551, rerank=0.4259, hydrate=3.6257, e2e=8.0067
- hit_rank: 1

| token | df | df ratio | postings length | token type | candidate weight | action |
|---|---:|---:|---:|---|---:|---|
| `CTRL:BEGIN_WORD` | 72601 | 1.000000 | 72601 | common | 0.000001 | rerank_only |
| `CTRL:END_WORD` | 72601 | 1.000000 | 72601 | common | 0.000001 | rerank_only |
| `,` | 67976 | 0.936296 | 67976 | common | 0.005882 | rerank_only |
| `meson` | 335 | 0.004614 | 335 | rare | 0.480412 | generate |
| ` ` | 72601 | 1.000000 | 72601 | common | 0.000001 | rerank_only |
| `ao` | 562 | 0.007741 | 562 | rare | 0.434242 | generate |
| `secure` | 1370 | 0.018870 | 1370 | rare | 0.354678 | generate |
| `documentation` | 12615 | 0.173758 | 12615 | common | 0.156357 | generate |
| `arm` | 6315 | 0.086982 | 6315 | identifier/path | 0.350000 | generate |
| `binding` | 9619 | 0.132491 | 9619 | common | 0.180581 | generate |

### 37. amlogic,meson mx secbus2 documentation devicetree bindings arm amlogic

- raw_postings_matches: 72,601
- weighted_candidates_after_policy: 2,000
- reranker_in: 50
- hydrated: 5
- time_ms: retrieval=3.1595, rerank=0.4126, hydrate=1.5755, e2e=5.1476
- hit_rank: 1

| token | df | df ratio | postings length | token type | candidate weight | action |
|---|---:|---:|---:|---|---:|---|
| `CTRL:BEGIN_WORD` | 72601 | 1.000000 | 72601 | common | 0.000001 | rerank_only |
| `CTRL:END_WORD` | 72601 | 1.000000 | 72601 | common | 0.000001 | rerank_only |
| `,` | 67976 | 0.936296 | 67976 | common | 0.005882 | rerank_only |
| `meson` | 335 | 0.004614 | 335 | rare | 0.480412 | generate |
| ` ` | 72601 | 1.000000 | 72601 | common | 0.000001 | rerank_only |
| `2` | 71667 | 0.987135 | 71667 | common | 0.001157 | rerank_only |
| `documentation` | 12615 | 0.173758 | 12615 | common | 0.156357 | generate |
| `arm` | 6315 | 0.086982 | 6315 | identifier/path | 0.350000 | generate |
| `binding` | 9619 | 0.132491 | 9619 | common | 0.180581 | generate |

### 38. apm documentation devicetree bindings arm

- raw_postings_matches: 72,601
- weighted_candidates_after_policy: 2,000
- reranker_in: 50
- hydrated: 5
- time_ms: retrieval=2.9358, rerank=0.3019, hydrate=0.2535, e2e=3.4912
- hit_rank: 1

| token | df | df ratio | postings length | token type | candidate weight | action |
|---|---:|---:|---:|---|---:|---|
| `CTRL:BEGIN_WORD` | 72601 | 1.000000 | 72601 | common | 0.000001 | rerank_only |
| `CTRL:END_WORD` | 72601 | 1.000000 | 72601 | common | 0.000001 | rerank_only |
| ` ` | 72601 | 1.000000 | 72601 | common | 0.000001 | rerank_only |
| `documentation` | 12615 | 0.173758 | 12615 | common | 0.156357 | generate |
| `arm` | 6315 | 0.086982 | 6315 | identifier/path | 0.350000 | generate |
| `binding` | 9619 | 0.132491 | 9619 | common | 0.180581 | generate |

### 39. apple documentation devicetree bindings arm

- raw_postings_matches: 72,601
- weighted_candidates_after_policy: 2,000
- reranker_in: 50
- hydrated: 5
- time_ms: retrieval=3.0889, rerank=0.5661, hydrate=5.2746, e2e=8.9296
- hit_rank: 2

| token | df | df ratio | postings length | token type | candidate weight | action |
|---|---:|---:|---:|---|---:|---|
| `apple` | 377 | 0.005193 | 377 | rare | 0.469874 | generate |
| ` ` | 72601 | 1.000000 | 72601 | common | 0.000001 | rerank_only |
| `documentation` | 12615 | 0.173758 | 12615 | common | 0.156357 | generate |
| `CTRL:BEGIN_WORD` | 72601 | 1.000000 | 72601 | common | 0.000001 | rerank_only |
| `CTRL:END_WORD` | 72601 | 1.000000 | 72601 | common | 0.000001 | rerank_only |
| `arm` | 6315 | 0.086982 | 6315 | identifier/path | 0.350000 | generate |
| `binding` | 9619 | 0.132491 | 9619 | common | 0.180581 | generate |

### 40. apple,pmgr documentation devicetree bindings arm apple

- raw_postings_matches: 72,601
- weighted_candidates_after_policy: 2,000
- reranker_in: 50
- hydrated: 5
- time_ms: retrieval=3.0712, rerank=0.3659, hydrate=0.6599, e2e=4.0970
- hit_rank: 1

| token | df | df ratio | postings length | token type | candidate weight | action |
|---|---:|---:|---:|---|---:|---|
| `apple` | 377 | 0.005193 | 377 | rare | 0.469874 | generate |
| `,` | 67976 | 0.936296 | 67976 | common | 0.005882 | rerank_only |
| `CTRL:BEGIN_WORD` | 72601 | 1.000000 | 72601 | common | 0.000001 | rerank_only |
| `CTRL:END_WORD` | 72601 | 1.000000 | 72601 | common | 0.000001 | rerank_only |
| ` ` | 72601 | 1.000000 | 72601 | common | 0.000001 | rerank_only |
| `documentation` | 12615 | 0.173758 | 12615 | common | 0.156357 | generate |
| `arm` | 6315 | 0.086982 | 6315 | identifier/path | 0.350000 | generate |
| `binding` | 9619 | 0.132491 | 9619 | common | 0.180581 | generate |

### 41. arm,cci documentation devicetree bindings arm

- raw_postings_matches: 72,601
- weighted_candidates_after_policy: 2,000
- reranker_in: 50
- hydrated: 5
- time_ms: retrieval=3.2206, rerank=0.3113, hydrate=0.2852, e2e=3.8171
- hit_rank: -

| token | df | df ratio | postings length | token type | candidate weight | action |
|---|---:|---:|---:|---|---:|---|
| `arm` | 6315 | 0.086982 | 6315 | identifier/path | 0.350000 | generate |
| `,` | 67976 | 0.936296 | 67976 | common | 0.005882 | rerank_only |
| `CTRL:BEGIN_WORD` | 72601 | 1.000000 | 72601 | common | 0.000001 | rerank_only |
| `CTRL:END_WORD` | 72601 | 1.000000 | 72601 | common | 0.000001 | rerank_only |
| ` ` | 72601 | 1.000000 | 72601 | common | 0.000001 | rerank_only |
| `documentation` | 12615 | 0.173758 | 12615 | common | 0.156357 | generate |
| `binding` | 9619 | 0.132491 | 9619 | common | 0.180581 | generate |

### 42. arm,coresight catu documentation devicetree bindings arm

- raw_postings_matches: 72,601
- weighted_candidates_after_policy: 2,000
- reranker_in: 50
- hydrated: 5
- time_ms: retrieval=2.9829, rerank=0.3183, hydrate=3.2136, e2e=6.5148
- hit_rank: 1

| token | df | df ratio | postings length | token type | candidate weight | action |
|---|---:|---:|---:|---|---:|---|
| `arm` | 6315 | 0.086982 | 6315 | identifier/path | 0.350000 | generate |
| `,` | 67976 | 0.936296 | 67976 | common | 0.005882 | rerank_only |
| `CTRL:BEGIN_WORD` | 72601 | 1.000000 | 72601 | common | 0.000001 | rerank_only |
| `CTRL:END_WORD` | 72601 | 1.000000 | 72601 | common | 0.000001 | rerank_only |
| ` ` | 72601 | 1.000000 | 72601 | common | 0.000001 | rerank_only |
| `documentation` | 12615 | 0.173758 | 12615 | common | 0.156357 | generate |
| `binding` | 9619 | 0.132491 | 9619 | common | 0.180581 | generate |

### 43. arm,coresight cpu debug documentation devicetree bindings arm

- raw_postings_matches: 72,601
- weighted_candidates_after_policy: 2,000
- reranker_in: 50
- hydrated: 5
- time_ms: retrieval=3.4076, rerank=0.3379, hydrate=2.5541, e2e=6.2996
- hit_rank: 1

| token | df | df ratio | postings length | token type | candidate weight | action |
|---|---:|---:|---:|---|---:|---|
| `arm` | 6315 | 0.086982 | 6315 | identifier/path | 0.350000 | generate |
| `,` | 67976 | 0.936296 | 67976 | common | 0.005882 | rerank_only |
| `CTRL:BEGIN_WORD` | 72601 | 1.000000 | 72601 | common | 0.000001 | rerank_only |
| `CTRL:END_WORD` | 72601 | 1.000000 | 72601 | common | 0.000001 | rerank_only |
| ` ` | 72601 | 1.000000 | 72601 | common | 0.000001 | rerank_only |
| `documentation` | 12615 | 0.173758 | 12615 | common | 0.156357 | generate |
| `binding` | 9619 | 0.132491 | 9619 | common | 0.180581 | generate |

### 44. arm,coresight cti documentation devicetree bindings arm

- raw_postings_matches: 72,601
- weighted_candidates_after_policy: 2,000
- reranker_in: 50
- hydrated: 5
- time_ms: retrieval=3.0839, rerank=0.3219, hydrate=0.0178, e2e=3.4236
- hit_rank: 1

| token | df | df ratio | postings length | token type | candidate weight | action |
|---|---:|---:|---:|---|---:|---|
| `arm` | 6315 | 0.086982 | 6315 | identifier/path | 0.350000 | generate |
| `,` | 67976 | 0.936296 | 67976 | common | 0.005882 | rerank_only |
| `CTRL:BEGIN_WORD` | 72601 | 1.000000 | 72601 | common | 0.000001 | rerank_only |
| `CTRL:END_WORD` | 72601 | 1.000000 | 72601 | common | 0.000001 | rerank_only |
| ` ` | 72601 | 1.000000 | 72601 | common | 0.000001 | rerank_only |
| `documentation` | 12615 | 0.173758 | 12615 | common | 0.156357 | generate |
| `binding` | 9619 | 0.132491 | 9619 | common | 0.180581 | generate |

### 45. arm,coresight dummy sink documentation devicetree bindings arm

- raw_postings_matches: 72,601
- weighted_candidates_after_policy: 2,000
- reranker_in: 50
- hydrated: 5
- time_ms: retrieval=3.6030, rerank=0.3608, hydrate=2.0467, e2e=6.0105
- hit_rank: 1

| token | df | df ratio | postings length | token type | candidate weight | action |
|---|---:|---:|---:|---|---:|---|
| `arm` | 6315 | 0.086982 | 6315 | identifier/path | 0.350000 | generate |
| `,` | 67976 | 0.936296 | 67976 | common | 0.005882 | rerank_only |
| `CTRL:BEGIN_WORD` | 72601 | 1.000000 | 72601 | common | 0.000001 | rerank_only |
| `CTRL:END_WORD` | 72601 | 1.000000 | 72601 | common | 0.000001 | rerank_only |
| ` ` | 72601 | 1.000000 | 72601 | common | 0.000001 | rerank_only |
| `dummy` | 3426 | 0.047189 | 3426 | rare | 0.350000 | generate |
| `sink` | 1102 | 0.015179 | 1102 | rare | 0.374118 | generate |
| `documentation` | 12615 | 0.173758 | 12615 | common | 0.156357 | generate |
| `binding` | 9619 | 0.132491 | 9619 | common | 0.180581 | generate |

### 46. arm,coresight dummy source documentation devicetree bindings arm

- raw_postings_matches: 72,601
- weighted_candidates_after_policy: 2,000
- reranker_in: 50
- hydrated: 5
- time_ms: retrieval=4.4188, rerank=0.3579, hydrate=2.0418, e2e=6.8185
- hit_rank: 1

| token | df | df ratio | postings length | token type | candidate weight | action |
|---|---:|---:|---:|---|---:|---|
| `arm` | 6315 | 0.086982 | 6315 | identifier/path | 0.350000 | generate |
| `,` | 67976 | 0.936296 | 67976 | common | 0.005882 | rerank_only |
| `CTRL:BEGIN_WORD` | 72601 | 1.000000 | 72601 | common | 0.000001 | rerank_only |
| `CTRL:END_WORD` | 72601 | 1.000000 | 72601 | common | 0.000001 | rerank_only |
| ` ` | 72601 | 1.000000 | 72601 | common | 0.000001 | rerank_only |
| `dummy` | 3426 | 0.047189 | 3426 | rare | 0.350000 | generate |
| `source` | 10659 | 0.146816 | 10659 | common | 0.171409 | generate |
| `documentation` | 12615 | 0.173758 | 12615 | common | 0.156357 | generate |
| `binding` | 9619 | 0.132491 | 9619 | common | 0.180581 | generate |

### 47. arm,coresight dynamic funnel documentation devicetree bindings arm

- raw_postings_matches: 72,601
- weighted_candidates_after_policy: 2,000
- reranker_in: 50
- hydrated: 5
- time_ms: retrieval=3.3045, rerank=0.3551, hydrate=1.4086, e2e=5.0682
- hit_rank: 1

| token | df | df ratio | postings length | token type | candidate weight | action |
|---|---:|---:|---:|---|---:|---|
| `arm` | 6315 | 0.086982 | 6315 | identifier/path | 0.350000 | generate |
| `,` | 67976 | 0.936296 | 67976 | common | 0.005882 | rerank_only |
| `CTRL:BEGIN_WORD` | 72601 | 1.000000 | 72601 | common | 0.000001 | rerank_only |
| `CTRL:END_WORD` | 72601 | 1.000000 | 72601 | common | 0.000001 | rerank_only |
| ` ` | 72601 | 1.000000 | 72601 | common | 0.000001 | rerank_only |
| `dynamic` | 3001 | 0.041336 | 3001 | rare | 0.350000 | generate |
| `funnel` | 58 | 0.000799 | 58 | rare | 0.636459 | generate |
| `documentation` | 12615 | 0.173758 | 12615 | common | 0.156357 | generate |
| `binding` | 9619 | 0.132491 | 9619 | common | 0.180581 | generate |

### 48. arm,coresight dynamic replicator documentation devicetree bindings arm

- raw_postings_matches: 72,601
- weighted_candidates_after_policy: 2,000
- reranker_in: 50
- hydrated: 5
- time_ms: retrieval=3.5132, rerank=0.3597, hydrate=2.8057, e2e=6.6786
- hit_rank: 1

| token | df | df ratio | postings length | token type | candidate weight | action |
|---|---:|---:|---:|---|---:|---|
| `arm` | 6315 | 0.086982 | 6315 | identifier/path | 0.350000 | generate |
| `,` | 67976 | 0.936296 | 67976 | common | 0.005882 | rerank_only |
| `CTRL:BEGIN_WORD` | 72601 | 1.000000 | 72601 | common | 0.000001 | rerank_only |
| `CTRL:END_WORD` | 72601 | 1.000000 | 72601 | common | 0.000001 | rerank_only |
| ` ` | 72601 | 1.000000 | 72601 | common | 0.000001 | rerank_only |
| `dynamic` | 3001 | 0.041336 | 3001 | rare | 0.350000 | generate |
| `documentation` | 12615 | 0.173758 | 12615 | common | 0.156357 | generate |
| `binding` | 9619 | 0.132491 | 9619 | common | 0.180581 | generate |

### 49. arm,coresight etb10 documentation devicetree bindings arm

- raw_postings_matches: 72,601
- weighted_candidates_after_policy: 2,000
- reranker_in: 50
- hydrated: 5
- time_ms: retrieval=3.2549, rerank=0.3203, hydrate=0.0192, e2e=3.5944
- hit_rank: 1

| token | df | df ratio | postings length | token type | candidate weight | action |
|---|---:|---:|---:|---|---:|---|
| `arm` | 6315 | 0.086982 | 6315 | identifier/path | 0.350000 | generate |
| `,` | 67976 | 0.936296 | 67976 | common | 0.005882 | rerank_only |
| `CTRL:BEGIN_WORD` | 72601 | 1.000000 | 72601 | common | 0.000001 | rerank_only |
| `CTRL:END_WORD` | 72601 | 1.000000 | 72601 | common | 0.000001 | rerank_only |
| ` ` | 72601 | 1.000000 | 72601 | common | 0.000001 | rerank_only |
| `1` | 66053 | 0.909808 | 66053 | common | 0.008445 | rerank_only |
| `CTRL:NUM_SEP` | 60437 | 0.832454 | 60437 | common | 0.016384 | rerank_only |
| `0` | 71675 | 0.987245 | 71675 | common | 0.001147 | rerank_only |
| `documentation` | 12615 | 0.173758 | 12615 | common | 0.156357 | generate |
| `binding` | 9619 | 0.132491 | 9619 | common | 0.180581 | generate |

### 50. arm,coresight etm documentation devicetree bindings arm

- raw_postings_matches: 72,601
- weighted_candidates_after_policy: 2,000
- reranker_in: 50
- hydrated: 5
- time_ms: retrieval=3.0829, rerank=0.3245, hydrate=1.2365, e2e=4.6439
- hit_rank: 1

| token | df | df ratio | postings length | token type | candidate weight | action |
|---|---:|---:|---:|---|---:|---|
| `arm` | 6315 | 0.086982 | 6315 | identifier/path | 0.350000 | generate |
| `,` | 67976 | 0.936296 | 67976 | common | 0.005882 | rerank_only |
| `CTRL:BEGIN_WORD` | 72601 | 1.000000 | 72601 | common | 0.000001 | rerank_only |
| `CTRL:END_WORD` | 72601 | 1.000000 | 72601 | common | 0.000001 | rerank_only |
| ` ` | 72601 | 1.000000 | 72601 | common | 0.000001 | rerank_only |
| `documentation` | 12615 | 0.173758 | 12615 | common | 0.156357 | generate |
| `binding` | 9619 | 0.132491 | 9619 | common | 0.180581 | generate |

### 51. arm,coresight static funnel documentation devicetree bindings arm

- raw_postings_matches: 72,601
- weighted_candidates_after_policy: 2,000
- reranker_in: 50
- hydrated: 5
- time_ms: retrieval=3.4071, rerank=0.3446, hydrate=0.8680, e2e=4.6197
- hit_rank: 1

| token | df | df ratio | postings length | token type | candidate weight | action |
|---|---:|---:|---:|---|---:|---|
| `arm` | 6315 | 0.086982 | 6315 | identifier/path | 0.350000 | generate |
| `,` | 67976 | 0.936296 | 67976 | common | 0.005882 | rerank_only |
| `CTRL:BEGIN_WORD` | 72601 | 1.000000 | 72601 | common | 0.000001 | rerank_only |
| `CTRL:END_WORD` | 72601 | 1.000000 | 72601 | common | 0.000001 | rerank_only |
| ` ` | 72601 | 1.000000 | 72601 | common | 0.000001 | rerank_only |
| `static` | 42102 | 0.579909 | 42102 | common | 0.048682 | rerank_only |
| `funnel` | 58 | 0.000799 | 58 | rare | 0.636459 | generate |
| `documentation` | 12615 | 0.173758 | 12615 | common | 0.156357 | generate |
| `binding` | 9619 | 0.132491 | 9619 | common | 0.180581 | generate |

### 52. arm,coresight static replicator documentation devicetree bindings arm

- raw_postings_matches: 72,601
- weighted_candidates_after_policy: 2,000
- reranker_in: 50
- hydrated: 5
- time_ms: retrieval=2.9754, rerank=0.3430, hydrate=0.0208, e2e=3.3392
- hit_rank: -

| token | df | df ratio | postings length | token type | candidate weight | action |
|---|---:|---:|---:|---|---:|---|
| `arm` | 6315 | 0.086982 | 6315 | identifier/path | 0.350000 | generate |
| `,` | 67976 | 0.936296 | 67976 | common | 0.005882 | rerank_only |
| `CTRL:BEGIN_WORD` | 72601 | 1.000000 | 72601 | common | 0.000001 | rerank_only |
| `CTRL:END_WORD` | 72601 | 1.000000 | 72601 | common | 0.000001 | rerank_only |
| ` ` | 72601 | 1.000000 | 72601 | common | 0.000001 | rerank_only |
| `static` | 42102 | 0.579909 | 42102 | common | 0.048682 | rerank_only |
| `documentation` | 12615 | 0.173758 | 12615 | common | 0.156357 | generate |
| `binding` | 9619 | 0.132491 | 9619 | common | 0.180581 | generate |

### 53. arm,coresight stm documentation devicetree bindings arm

- raw_postings_matches: 72,601
- weighted_candidates_after_policy: 2,000
- reranker_in: 50
- hydrated: 5
- time_ms: retrieval=3.1830, rerank=0.3200, hydrate=0.0183, e2e=3.5213
- hit_rank: 1

| token | df | df ratio | postings length | token type | candidate weight | action |
|---|---:|---:|---:|---|---:|---|
| `arm` | 6315 | 0.086982 | 6315 | identifier/path | 0.350000 | generate |
| `,` | 67976 | 0.936296 | 67976 | common | 0.005882 | rerank_only |
| `CTRL:BEGIN_WORD` | 72601 | 1.000000 | 72601 | common | 0.000001 | rerank_only |
| `CTRL:END_WORD` | 72601 | 1.000000 | 72601 | common | 0.000001 | rerank_only |
| ` ` | 72601 | 1.000000 | 72601 | common | 0.000001 | rerank_only |
| `documentation` | 12615 | 0.173758 | 12615 | common | 0.156357 | generate |
| `binding` | 9619 | 0.132491 | 9619 | common | 0.180581 | generate |

### 54. arm,coresight tmc documentation devicetree bindings arm

- raw_postings_matches: 72,601
- weighted_candidates_after_policy: 2,000
- reranker_in: 50
- hydrated: 5
- time_ms: retrieval=3.1238, rerank=0.4011, hydrate=0.0232, e2e=3.5481
- hit_rank: -

| token | df | df ratio | postings length | token type | candidate weight | action |
|---|---:|---:|---:|---|---:|---|
| `arm` | 6315 | 0.086982 | 6315 | identifier/path | 0.350000 | generate |
| `,` | 67976 | 0.936296 | 67976 | common | 0.005882 | rerank_only |
| `CTRL:BEGIN_WORD` | 72601 | 1.000000 | 72601 | common | 0.000001 | rerank_only |
| `CTRL:END_WORD` | 72601 | 1.000000 | 72601 | common | 0.000001 | rerank_only |
| ` ` | 72601 | 1.000000 | 72601 | common | 0.000001 | rerank_only |
| `documentation` | 12615 | 0.173758 | 12615 | common | 0.156357 | generate |
| `binding` | 9619 | 0.132491 | 9619 | common | 0.180581 | generate |

### 55. arm,coresight tpiu documentation devicetree bindings arm

- raw_postings_matches: 72,601
- weighted_candidates_after_policy: 2,000
- reranker_in: 50
- hydrated: 5
- time_ms: retrieval=3.6417, rerank=0.3700, hydrate=0.0196, e2e=4.0313
- hit_rank: 1

| token | df | df ratio | postings length | token type | candidate weight | action |
|---|---:|---:|---:|---|---:|---|
| `arm` | 6315 | 0.086982 | 6315 | identifier/path | 0.350000 | generate |
| `,` | 67976 | 0.936296 | 67976 | common | 0.005882 | rerank_only |
| `CTRL:BEGIN_WORD` | 72601 | 1.000000 | 72601 | common | 0.000001 | rerank_only |
| `CTRL:END_WORD` | 72601 | 1.000000 | 72601 | common | 0.000001 | rerank_only |
| ` ` | 72601 | 1.000000 | 72601 | common | 0.000001 | rerank_only |
| `documentation` | 12615 | 0.173758 | 12615 | common | 0.156357 | generate |
| `binding` | 9619 | 0.132491 | 9619 | common | 0.180581 | generate |

### 56. arm,corstone1000 documentation devicetree bindings arm

- raw_postings_matches: 72,601
- weighted_candidates_after_policy: 2,000
- reranker_in: 50
- hydrated: 5
- time_ms: retrieval=2.9800, rerank=0.3055, hydrate=0.7711, e2e=4.0566
- hit_rank: 1

| token | df | df ratio | postings length | token type | candidate weight | action |
|---|---:|---:|---:|---|---:|---|
| `arm` | 6315 | 0.086982 | 6315 | identifier/path | 0.350000 | generate |
| `,` | 67976 | 0.936296 | 67976 | common | 0.005882 | rerank_only |
| `CTRL:BEGIN_WORD` | 72601 | 1.000000 | 72601 | common | 0.000001 | rerank_only |
| `CTRL:END_WORD` | 72601 | 1.000000 | 72601 | common | 0.000001 | rerank_only |
| `1` | 66053 | 0.909808 | 66053 | common | 0.008445 | rerank_only |
| `CTRL:NUM_SEP` | 60437 | 0.832454 | 60437 | common | 0.016384 | rerank_only |
| `0` | 71675 | 0.987245 | 71675 | common | 0.001147 | rerank_only |
| ` ` | 72601 | 1.000000 | 72601 | common | 0.000001 | rerank_only |
| `documentation` | 12615 | 0.173758 | 12615 | common | 0.156357 | generate |
| `binding` | 9619 | 0.132491 | 9619 | common | 0.180581 | generate |

### 57. arm,embedded trace extension documentation devicetree bindings arm

- raw_postings_matches: 72,601
- weighted_candidates_after_policy: 2,000
- reranker_in: 50
- hydrated: 5
- time_ms: retrieval=4.2899, rerank=0.3638, hydrate=1.4283, e2e=6.0820
- hit_rank: 1

| token | df | df ratio | postings length | token type | candidate weight | action |
|---|---:|---:|---:|---|---:|---|
| `arm` | 6315 | 0.086982 | 6315 | identifier/path | 0.350000 | generate |
| `,` | 67976 | 0.936296 | 67976 | common | 0.005882 | rerank_only |
| `CTRL:BEGIN_WORD` | 72601 | 1.000000 | 72601 | common | 0.000001 | rerank_only |
| `CTRL:END_WORD` | 72601 | 1.000000 | 72601 | common | 0.000001 | rerank_only |
| ` ` | 72601 | 1.000000 | 72601 | common | 0.000001 | rerank_only |
| `trace` | 5473 | 0.075385 | 5473 | identifier/path | 0.350000 | generate |
| `extension` | 2009 | 0.027672 | 2009 | rare | 0.350000 | generate |
| `documentation` | 12615 | 0.173758 | 12615 | common | 0.156357 | generate |
| `binding` | 9619 | 0.132491 | 9619 | common | 0.180581 | generate |

### 58. arm,integrator documentation devicetree bindings arm

- raw_postings_matches: 72,601
- weighted_candidates_after_policy: 2,000
- reranker_in: 50
- hydrated: 5
- time_ms: retrieval=2.9381, rerank=0.3236, hydrate=1.5431, e2e=4.8048
- hit_rank: 1

| token | df | df ratio | postings length | token type | candidate weight | action |
|---|---:|---:|---:|---|---:|---|
| `arm` | 6315 | 0.086982 | 6315 | identifier/path | 0.350000 | generate |
| `,` | 67976 | 0.936296 | 67976 | common | 0.005882 | rerank_only |
| `integrator` | 51 | 0.000702 | 51 | rare | 0.647845 | generate |
| ` ` | 72601 | 1.000000 | 72601 | common | 0.000001 | rerank_only |
| `documentation` | 12615 | 0.173758 | 12615 | common | 0.156357 | generate |
| `CTRL:BEGIN_WORD` | 72601 | 1.000000 | 72601 | common | 0.000001 | rerank_only |
| `CTRL:END_WORD` | 72601 | 1.000000 | 72601 | common | 0.000001 | rerank_only |
| `binding` | 9619 | 0.132491 | 9619 | common | 0.180581 | generate |

### 59. arm,juno fpga apb regs documentation devicetree bindings arm

- raw_postings_matches: 72,601
- weighted_candidates_after_policy: 2,000
- reranker_in: 50
- hydrated: 5
- time_ms: retrieval=4.3862, rerank=0.3611, hydrate=3.5264, e2e=8.2737
- hit_rank: 1

| token | df | df ratio | postings length | token type | candidate weight | action |
|---|---:|---:|---:|---|---:|---|
| `arm` | 6315 | 0.086982 | 6315 | identifier/path | 0.350000 | generate |
| `,` | 67976 | 0.936296 | 67976 | common | 0.005882 | rerank_only |
| `juno` | 9 | 0.000124 | 9 | rare | 0.798862 | generate |
| ` ` | 72601 | 1.000000 | 72601 | common | 0.000001 | rerank_only |
| `CTRL:BEGIN_WORD` | 72601 | 1.000000 | 72601 | common | 0.000001 | rerank_only |
| `CTRL:END_WORD` | 72601 | 1.000000 | 72601 | common | 0.000001 | rerank_only |
| `documentation` | 12615 | 0.173758 | 12615 | common | 0.156357 | generate |
| `reg` | 27314 | 0.376221 | 27314 | common | 0.087340 | generate |
| `binding` | 9619 | 0.132491 | 9619 | common | 0.180581 | generate |

### 60. arm,morello documentation devicetree bindings arm

- raw_postings_matches: 72,601
- weighted_candidates_after_policy: 2,000
- reranker_in: 50
- hydrated: 5
- time_ms: retrieval=3.3398, rerank=0.3095, hydrate=0.0187, e2e=3.6680
- hit_rank: 1

| token | df | df ratio | postings length | token type | candidate weight | action |
|---|---:|---:|---:|---|---:|---|
| `arm` | 6315 | 0.086982 | 6315 | identifier/path | 0.350000 | generate |
| `,` | 67976 | 0.936296 | 67976 | common | 0.005882 | rerank_only |
| `morello` | 1 | 0.000014 | 1 | rare | 0.963774 | generate |
| ` ` | 72601 | 1.000000 | 72601 | common | 0.000001 | rerank_only |
| `documentation` | 12615 | 0.173758 | 12615 | common | 0.156357 | generate |
| `CTRL:BEGIN_WORD` | 72601 | 1.000000 | 72601 | common | 0.000001 | rerank_only |
| `CTRL:END_WORD` | 72601 | 1.000000 | 72601 | common | 0.000001 | rerank_only |
| `binding` | 9619 | 0.132491 | 9619 | common | 0.180581 | generate |

### 61. arm,realview documentation devicetree bindings arm

- raw_postings_matches: 72,601
- weighted_candidates_after_policy: 2,000
- reranker_in: 50
- hydrated: 5
- time_ms: retrieval=2.9524, rerank=0.3033, hydrate=0.7012, e2e=3.9569
- hit_rank: 1

| token | df | df ratio | postings length | token type | candidate weight | action |
|---|---:|---:|---:|---|---:|---|
| `arm` | 6315 | 0.086982 | 6315 | identifier/path | 0.350000 | generate |
| `,` | 67976 | 0.936296 | 67976 | common | 0.005882 | rerank_only |
| `CTRL:BEGIN_WORD` | 72601 | 1.000000 | 72601 | common | 0.000001 | rerank_only |
| `CTRL:END_WORD` | 72601 | 1.000000 | 72601 | common | 0.000001 | rerank_only |
| ` ` | 72601 | 1.000000 | 72601 | common | 0.000001 | rerank_only |
| `documentation` | 12615 | 0.173758 | 12615 | common | 0.156357 | generate |
| `binding` | 9619 | 0.132491 | 9619 | common | 0.180581 | generate |

### 62. arm,scu documentation devicetree bindings arm

- raw_postings_matches: 72,601
- weighted_candidates_after_policy: 2,000
- reranker_in: 50
- hydrated: 5
- time_ms: retrieval=3.0518, rerank=0.3009, hydrate=0.0181, e2e=3.3708
- hit_rank: 1

| token | df | df ratio | postings length | token type | candidate weight | action |
|---|---:|---:|---:|---|---:|---|
| `arm` | 6315 | 0.086982 | 6315 | identifier/path | 0.350000 | generate |
| `,` | 67976 | 0.936296 | 67976 | common | 0.005882 | rerank_only |
| `CTRL:BEGIN_WORD` | 72601 | 1.000000 | 72601 | common | 0.000001 | rerank_only |
| `CTRL:END_WORD` | 72601 | 1.000000 | 72601 | common | 0.000001 | rerank_only |
| ` ` | 72601 | 1.000000 | 72601 | common | 0.000001 | rerank_only |
| `documentation` | 12615 | 0.173758 | 12615 | common | 0.156357 | generate |
| `binding` | 9619 | 0.132491 | 9619 | common | 0.180581 | generate |

### 63. arm,trace buffer extension documentation devicetree bindings arm

- raw_postings_matches: 72,601
- weighted_candidates_after_policy: 2,000
- reranker_in: 50
- hydrated: 5
- time_ms: retrieval=4.4609, rerank=0.4661, hydrate=0.4733, e2e=5.4003
- hit_rank: 1

| token | df | df ratio | postings length | token type | candidate weight | action |
|---|---:|---:|---:|---|---:|---|
| `arm` | 6315 | 0.086982 | 6315 | identifier/path | 0.350000 | generate |
| `,` | 67976 | 0.936296 | 67976 | common | 0.005882 | rerank_only |
| `trace` | 5473 | 0.075385 | 5473 | identifier/path | 0.350000 | generate |
| ` ` | 72601 | 1.000000 | 72601 | common | 0.000001 | rerank_only |
| `buffer` | 14739 | 0.203014 | 14739 | common | 0.142455 | generate |
| `extension` | 2009 | 0.027672 | 2009 | rare | 0.350000 | generate |
| `documentation` | 12615 | 0.173758 | 12615 | common | 0.156357 | generate |
| `CTRL:BEGIN_WORD` | 72601 | 1.000000 | 72601 | common | 0.000001 | rerank_only |
| `CTRL:END_WORD` | 72601 | 1.000000 | 72601 | common | 0.000001 | rerank_only |
| `binding` | 9619 | 0.132491 | 9619 | common | 0.180581 | generate |

### 64. arm,versatile sysreg documentation devicetree bindings arm

- raw_postings_matches: 72,601
- weighted_candidates_after_policy: 2,000
- reranker_in: 50
- hydrated: 5
- time_ms: retrieval=3.4852, rerank=0.3561, hydrate=1.3283, e2e=5.1696
- hit_rank: 1

| token | df | df ratio | postings length | token type | candidate weight | action |
|---|---:|---:|---:|---|---:|---|
| `arm` | 6315 | 0.086982 | 6315 | identifier/path | 0.350000 | generate |
| `,` | 67976 | 0.936296 | 67976 | common | 0.005882 | rerank_only |
| `versatile` | 97 | 0.001336 | 97 | rare | 0.590820 | generate |
| ` ` | 72601 | 1.000000 | 72601 | common | 0.000001 | rerank_only |
| `CTRL:BEGIN_WORD` | 72601 | 1.000000 | 72601 | common | 0.000001 | rerank_only |
| `CTRL:END_WORD` | 72601 | 1.000000 | 72601 | common | 0.000001 | rerank_only |
| `documentation` | 12615 | 0.173758 | 12615 | common | 0.156357 | generate |
| `binding` | 9619 | 0.132491 | 9619 | common | 0.180581 | generate |

### 65. arm,versatile documentation devicetree bindings arm

- raw_postings_matches: 72,601
- weighted_candidates_after_policy: 2,000
- reranker_in: 50
- hydrated: 5
- time_ms: retrieval=2.9852, rerank=0.3340, hydrate=0.3286, e2e=3.6478
- hit_rank: 1

| token | df | df ratio | postings length | token type | candidate weight | action |
|---|---:|---:|---:|---|---:|---|
| `arm` | 6315 | 0.086982 | 6315 | identifier/path | 0.350000 | generate |
| `,` | 67976 | 0.936296 | 67976 | common | 0.005882 | rerank_only |
| `versatile` | 97 | 0.001336 | 97 | rare | 0.590820 | generate |
| ` ` | 72601 | 1.000000 | 72601 | common | 0.000001 | rerank_only |
| `documentation` | 12615 | 0.173758 | 12615 | common | 0.156357 | generate |
| `CTRL:BEGIN_WORD` | 72601 | 1.000000 | 72601 | common | 0.000001 | rerank_only |
| `CTRL:END_WORD` | 72601 | 1.000000 | 72601 | common | 0.000001 | rerank_only |
| `binding` | 9619 | 0.132491 | 9619 | common | 0.180581 | generate |

### 66. arm,vexpress juno documentation devicetree bindings arm

- raw_postings_matches: 72,601
- weighted_candidates_after_policy: 2,000
- reranker_in: 50
- hydrated: 5
- time_ms: retrieval=3.0948, rerank=0.5773, hydrate=0.0212, e2e=3.6933
- hit_rank: 1

| token | df | df ratio | postings length | token type | candidate weight | action |
|---|---:|---:|---:|---|---:|---|
| `arm` | 6315 | 0.086982 | 6315 | identifier/path | 0.350000 | generate |
| `,` | 67976 | 0.936296 | 67976 | common | 0.005882 | rerank_only |
| `CTRL:BEGIN_WORD` | 72601 | 1.000000 | 72601 | common | 0.000001 | rerank_only |
| `CTRL:END_WORD` | 72601 | 1.000000 | 72601 | common | 0.000001 | rerank_only |
| ` ` | 72601 | 1.000000 | 72601 | common | 0.000001 | rerank_only |
| `juno` | 9 | 0.000124 | 9 | rare | 0.798862 | generate |
| `documentation` | 12615 | 0.173758 | 12615 | common | 0.156357 | generate |
| `binding` | 9619 | 0.132491 | 9619 | common | 0.180581 | generate |

### 67. arm,vexpress scc documentation devicetree bindings arm

- raw_postings_matches: 72,601
- weighted_candidates_after_policy: 2,000
- reranker_in: 50
- hydrated: 5
- time_ms: retrieval=3.2364, rerank=0.3187, hydrate=0.0194, e2e=3.5745
- hit_rank: 1

| token | df | df ratio | postings length | token type | candidate weight | action |
|---|---:|---:|---:|---|---:|---|
| `arm` | 6315 | 0.086982 | 6315 | identifier/path | 0.350000 | generate |
| `,` | 67976 | 0.936296 | 67976 | common | 0.005882 | rerank_only |
| `CTRL:BEGIN_WORD` | 72601 | 1.000000 | 72601 | common | 0.000001 | rerank_only |
| `CTRL:END_WORD` | 72601 | 1.000000 | 72601 | common | 0.000001 | rerank_only |
| ` ` | 72601 | 1.000000 | 72601 | common | 0.000001 | rerank_only |
| `documentation` | 12615 | 0.173758 | 12615 | common | 0.156357 | generate |
| `binding` | 9619 | 0.132491 | 9619 | common | 0.180581 | generate |

### 68. aspeed,sbc documentation devicetree bindings arm aspeed

- raw_postings_matches: 72,601
- weighted_candidates_after_policy: 2,000
- reranker_in: 50
- hydrated: 5
- time_ms: retrieval=3.4246, rerank=0.5092, hydrate=0.0184, e2e=3.9522
- hit_rank: -

| token | df | df ratio | postings length | token type | candidate weight | action |
|---|---:|---:|---:|---|---:|---|
| `CTRL:BEGIN_WORD` | 72601 | 1.000000 | 72601 | common | 0.000001 | rerank_only |
| `CTRL:END_WORD` | 72601 | 1.000000 | 72601 | common | 0.000001 | rerank_only |
| `,` | 67976 | 0.936296 | 67976 | common | 0.005882 | rerank_only |
| ` ` | 72601 | 1.000000 | 72601 | common | 0.000001 | rerank_only |
| `documentation` | 12615 | 0.173758 | 12615 | common | 0.156357 | generate |
| `arm` | 6315 | 0.086982 | 6315 | identifier/path | 0.350000 | generate |
| `binding` | 9619 | 0.132491 | 9619 | common | 0.180581 | generate |

### 69. aspeed documentation devicetree bindings arm aspeed

- raw_postings_matches: 72,601
- weighted_candidates_after_policy: 2,000
- reranker_in: 50
- hydrated: 5
- time_ms: retrieval=3.1730, rerank=0.4530, hydrate=0.0217, e2e=3.6477
- hit_rank: -

| token | df | df ratio | postings length | token type | candidate weight | action |
|---|---:|---:|---:|---|---:|---|
| `CTRL:BEGIN_WORD` | 72601 | 1.000000 | 72601 | common | 0.000001 | rerank_only |
| `CTRL:END_WORD` | 72601 | 1.000000 | 72601 | common | 0.000001 | rerank_only |
| ` ` | 72601 | 1.000000 | 72601 | common | 0.000001 | rerank_only |
| `documentation` | 12615 | 0.173758 | 12615 | common | 0.156357 | generate |
| `arm` | 6315 | 0.086982 | 6315 | identifier/path | 0.350000 | generate |
| `binding` | 9619 | 0.132491 | 9619 | common | 0.180581 | generate |

### 70. atmel,at91rm9200 sdramc documentation devicetree bindings arm

- raw_postings_matches: 72,601
- weighted_candidates_after_policy: 2,000
- reranker_in: 50
- hydrated: 5
- time_ms: retrieval=6.8469, rerank=0.3819, hydrate=1.8947, e2e=9.1235
- hit_rank: 1

| token | df | df ratio | postings length | token type | candidate weight | action |
|---|---:|---:|---:|---|---:|---|
| `CTRL:BEGIN_WORD` | 72601 | 1.000000 | 72601 | common | 0.000001 | rerank_only |
| `CTRL:END_WORD` | 72601 | 1.000000 | 72601 | common | 0.000001 | rerank_only |
| `,` | 67976 | 0.936296 | 67976 | common | 0.005882 | rerank_only |
| `at` | 18820 | 0.259225 | 18820 | common | 0.120618 | generate |
| `9` | 37927 | 0.522403 | 37927 | common | 0.058012 | generate |
| `CTRL:NUM_SEP` | 60437 | 0.832454 | 60437 | common | 0.016384 | rerank_only |
| `1` | 66053 | 0.909808 | 66053 | common | 0.008445 | rerank_only |
| `rm` | 1545 | 0.021281 | 1545 | rare | 0.350000 | generate |
| `2` | 71667 | 0.987135 | 71667 | common | 0.001157 | rerank_only |
| `0` | 71675 | 0.987245 | 71675 | common | 0.001147 | rerank_only |
| ` ` | 72601 | 1.000000 | 72601 | common | 0.000001 | rerank_only |
| `documentation` | 12615 | 0.173758 | 12615 | common | 0.156357 | generate |
| `arm` | 6315 | 0.086982 | 6315 | identifier/path | 0.350000 | generate |
| `binding` | 9619 | 0.132491 | 9619 | common | 0.180581 | generate |

### 71. atmel,at91rm9200 st documentation devicetree bindings arm

- raw_postings_matches: 72,601
- weighted_candidates_after_policy: 2,000
- reranker_in: 50
- hydrated: 5
- time_ms: retrieval=6.2563, rerank=0.3826, hydrate=1.0050, e2e=7.6439
- hit_rank: 1

| token | df | df ratio | postings length | token type | candidate weight | action |
|---|---:|---:|---:|---|---:|---|
| `CTRL:BEGIN_WORD` | 72601 | 1.000000 | 72601 | common | 0.000001 | rerank_only |
| `CTRL:END_WORD` | 72601 | 1.000000 | 72601 | common | 0.000001 | rerank_only |
| `,` | 67976 | 0.936296 | 67976 | common | 0.005882 | rerank_only |
| `at` | 18820 | 0.259225 | 18820 | common | 0.120618 | generate |
| `9` | 37927 | 0.522403 | 37927 | common | 0.058012 | generate |
| `CTRL:NUM_SEP` | 60437 | 0.832454 | 60437 | common | 0.016384 | rerank_only |
| `1` | 66053 | 0.909808 | 66053 | common | 0.008445 | rerank_only |
| `rm` | 1545 | 0.021281 | 1545 | rare | 0.350000 | generate |
| `2` | 71667 | 0.987135 | 71667 | common | 0.001157 | rerank_only |
| `0` | 71675 | 0.987245 | 71675 | common | 0.001147 | rerank_only |
| ` ` | 72601 | 1.000000 | 72601 | common | 0.000001 | rerank_only |
| `st` | 5319 | 0.073263 | 5319 | identifier/path | 0.350000 | generate |
| `documentation` | 12615 | 0.173758 | 12615 | common | 0.156357 | generate |
| `arm` | 6315 | 0.086982 | 6315 | identifier/path | 0.350000 | generate |
| `binding` | 9619 | 0.132491 | 9619 | common | 0.180581 | generate |

### 72. atmel,at91sam9260 pit documentation devicetree bindings arm

- raw_postings_matches: 72,601
- weighted_candidates_after_policy: 2,000
- reranker_in: 50
- hydrated: 5
- time_ms: retrieval=6.0531, rerank=0.3937, hydrate=1.9444, e2e=8.3912
- hit_rank: 1

| token | df | df ratio | postings length | token type | candidate weight | action |
|---|---:|---:|---:|---|---:|---|
| `CTRL:BEGIN_WORD` | 72601 | 1.000000 | 72601 | common | 0.000001 | rerank_only |
| `CTRL:END_WORD` | 72601 | 1.000000 | 72601 | common | 0.000001 | rerank_only |
| `,` | 67976 | 0.936296 | 67976 | common | 0.005882 | rerank_only |
| `at` | 18820 | 0.259225 | 18820 | common | 0.120618 | generate |
| `9` | 37927 | 0.522403 | 37927 | common | 0.058012 | generate |
| `CTRL:NUM_SEP` | 60437 | 0.832454 | 60437 | common | 0.016384 | rerank_only |
| `1` | 66053 | 0.909808 | 66053 | common | 0.008445 | rerank_only |
| `sam` | 535 | 0.007369 | 535 | rare | 0.438636 | generate |
| `2` | 71667 | 0.987135 | 71667 | common | 0.001157 | rerank_only |
| `6` | 54632 | 0.752497 | 54632 | common | 0.025406 | rerank_only |
| `0` | 71675 | 0.987245 | 71675 | common | 0.001147 | rerank_only |
| ` ` | 72601 | 1.000000 | 72601 | common | 0.000001 | rerank_only |
| `pit` | 109 | 0.001501 | 109 | rare | 0.580449 | generate |
| `documentation` | 12615 | 0.173758 | 12615 | common | 0.156357 | generate |
| `arm` | 6315 | 0.086982 | 6315 | identifier/path | 0.350000 | generate |
| `binding` | 9619 | 0.132491 | 9619 | common | 0.180581 | generate |

### 73. atmel,sama5d2 secumod documentation devicetree bindings arm

- raw_postings_matches: 72,601
- weighted_candidates_after_policy: 2,000
- reranker_in: 50
- hydrated: 5
- time_ms: retrieval=3.0374, rerank=0.3235, hydrate=0.0203, e2e=3.3812
- hit_rank: -

| token | df | df ratio | postings length | token type | candidate weight | action |
|---|---:|---:|---:|---|---:|---|
| `CTRL:BEGIN_WORD` | 72601 | 1.000000 | 72601 | common | 0.000001 | rerank_only |
| `CTRL:END_WORD` | 72601 | 1.000000 | 72601 | common | 0.000001 | rerank_only |
| `,` | 67976 | 0.936296 | 67976 | common | 0.005882 | rerank_only |
| `5` | 47367 | 0.652429 | 47367 | common | 0.038155 | rerank_only |
| `2` | 71667 | 0.987135 | 71667 | common | 0.001157 | rerank_only |
| ` ` | 72601 | 1.000000 | 72601 | common | 0.000001 | rerank_only |
| `documentation` | 12615 | 0.173758 | 12615 | common | 0.156357 | generate |
| `arm` | 6315 | 0.086982 | 6315 | identifier/path | 0.350000 | generate |
| `binding` | 9619 | 0.132491 | 9619 | common | 0.180581 | generate |

### 74. atmel at91 documentation devicetree bindings arm

- raw_postings_matches: 72,601
- weighted_candidates_after_policy: 2,000
- reranker_in: 50
- hydrated: 5
- time_ms: retrieval=5.6488, rerank=0.3293, hydrate=2.1485, e2e=8.1266
- hit_rank: 1

| token | df | df ratio | postings length | token type | candidate weight | action |
|---|---:|---:|---:|---|---:|---|
| `CTRL:BEGIN_WORD` | 72601 | 1.000000 | 72601 | common | 0.000001 | rerank_only |
| `CTRL:END_WORD` | 72601 | 1.000000 | 72601 | common | 0.000001 | rerank_only |
| ` ` | 72601 | 1.000000 | 72601 | common | 0.000001 | rerank_only |
| `at` | 18820 | 0.259225 | 18820 | common | 0.120618 | generate |
| `9` | 37927 | 0.522403 | 37927 | common | 0.058012 | generate |
| `CTRL:NUM_SEP` | 60437 | 0.832454 | 60437 | common | 0.016384 | rerank_only |
| `1` | 66053 | 0.909808 | 66053 | common | 0.008445 | rerank_only |
| `documentation` | 12615 | 0.173758 | 12615 | common | 0.156357 | generate |
| `arm` | 6315 | 0.086982 | 6315 | identifier/path | 0.350000 | generate |
| `binding` | 9619 | 0.132491 | 9619 | common | 0.180581 | generate |

### 75. axiado documentation devicetree bindings arm

- raw_postings_matches: 72,601
- weighted_candidates_after_policy: 2,000
- reranker_in: 50
- hydrated: 5
- time_ms: retrieval=2.9898, rerank=0.3066, hydrate=0.2261, e2e=3.5225
- hit_rank: 1

| token | df | df ratio | postings length | token type | candidate weight | action |
|---|---:|---:|---:|---|---:|---|
| `CTRL:BEGIN_WORD` | 72601 | 1.000000 | 72601 | common | 0.000001 | rerank_only |
| `CTRL:END_WORD` | 72601 | 1.000000 | 72601 | common | 0.000001 | rerank_only |
| ` ` | 72601 | 1.000000 | 72601 | common | 0.000001 | rerank_only |
| `documentation` | 12615 | 0.173758 | 12615 | common | 0.156357 | generate |
| `arm` | 6315 | 0.086982 | 6315 | identifier/path | 0.350000 | generate |
| `binding` | 9619 | 0.132491 | 9619 | common | 0.180581 | generate |

### 76. axis documentation devicetree bindings arm

- raw_postings_matches: 72,601
- weighted_candidates_after_policy: 2,000
- reranker_in: 50
- hydrated: 5
- time_ms: retrieval=2.9512, rerank=0.3256, hydrate=3.5816, e2e=6.8584
- hit_rank: 1

| token | df | df ratio | postings length | token type | candidate weight | action |
|---|---:|---:|---:|---|---:|---|
| `axis` | 490 | 0.006749 | 490 | rare | 0.446479 | generate |
| ` ` | 72601 | 1.000000 | 72601 | common | 0.000001 | rerank_only |
| `documentation` | 12615 | 0.173758 | 12615 | common | 0.156357 | generate |
| `CTRL:BEGIN_WORD` | 72601 | 1.000000 | 72601 | common | 0.000001 | rerank_only |
| `CTRL:END_WORD` | 72601 | 1.000000 | 72601 | common | 0.000001 | rerank_only |
| `arm` | 6315 | 0.086982 | 6315 | identifier/path | 0.350000 | generate |
| `binding` | 9619 | 0.132491 | 9619 | common | 0.180581 | generate |

### 77. axxia documentation devicetree bindings arm

- raw_postings_matches: 72,601
- weighted_candidates_after_policy: 2,000
- reranker_in: 50
- hydrated: 5
- time_ms: retrieval=2.9199, rerank=0.3103, hydrate=0.1945, e2e=3.4247
- hit_rank: 1

| token | df | df ratio | postings length | token type | candidate weight | action |
|---|---:|---:|---:|---|---:|---|
| `CTRL:BEGIN_WORD` | 72601 | 1.000000 | 72601 | common | 0.000001 | rerank_only |
| `CTRL:END_WORD` | 72601 | 1.000000 | 72601 | common | 0.000001 | rerank_only |
| ` ` | 72601 | 1.000000 | 72601 | common | 0.000001 | rerank_only |
| `documentation` | 12615 | 0.173758 | 12615 | common | 0.156357 | generate |
| `arm` | 6315 | 0.086982 | 6315 | identifier/path | 0.350000 | generate |
| `binding` | 9619 | 0.132491 | 9619 | common | 0.180581 | generate |

### 78. bcm2835 documentation devicetree bindings arm bcm

- raw_postings_matches: 72,601
- weighted_candidates_after_policy: 2,000
- reranker_in: 50
- hydrated: 5
- time_ms: retrieval=3.0063, rerank=0.3377, hydrate=1.6130, e2e=4.9570
- hit_rank: -

| token | df | df ratio | postings length | token type | candidate weight | action |
|---|---:|---:|---:|---|---:|---|
| `CTRL:BEGIN_WORD` | 72601 | 1.000000 | 72601 | common | 0.000001 | rerank_only |
| `CTRL:END_WORD` | 72601 | 1.000000 | 72601 | common | 0.000001 | rerank_only |
| `2` | 71667 | 0.987135 | 71667 | common | 0.001157 | rerank_only |
| `CTRL:NUM_SEP` | 60437 | 0.832454 | 60437 | common | 0.016384 | rerank_only |
| `8` | 51787 | 0.713310 | 51787 | common | 0.030184 | rerank_only |
| `3` | 58661 | 0.807992 | 58661 | common | 0.019049 | rerank_only |
| `5` | 47367 | 0.652429 | 47367 | common | 0.038155 | rerank_only |
| ` ` | 72601 | 1.000000 | 72601 | common | 0.000001 | rerank_only |
| `documentation` | 12615 | 0.173758 | 12615 | common | 0.156357 | generate |
| `arm` | 6315 | 0.086982 | 6315 | identifier/path | 0.350000 | generate |
| `binding` | 9619 | 0.132491 | 9619 | common | 0.180581 | generate |

### 79. brcm,bcm11351 documentation devicetree bindings arm bcm

- raw_postings_matches: 72,601
- weighted_candidates_after_policy: 2,000
- reranker_in: 50
- hydrated: 5
- time_ms: retrieval=3.8158, rerank=0.3469, hydrate=0.0183, e2e=4.1810
- hit_rank: 1

| token | df | df ratio | postings length | token type | candidate weight | action |
|---|---:|---:|---:|---|---:|---|
| `CTRL:BEGIN_WORD` | 72601 | 1.000000 | 72601 | common | 0.000001 | rerank_only |
| `CTRL:END_WORD` | 72601 | 1.000000 | 72601 | common | 0.000001 | rerank_only |
| `,` | 67976 | 0.936296 | 67976 | common | 0.005882 | rerank_only |
| `1` | 66053 | 0.909808 | 66053 | common | 0.008445 | rerank_only |
| `CTRL:NUM_SEP` | 60437 | 0.832454 | 60437 | common | 0.016384 | rerank_only |
| `3` | 58661 | 0.807992 | 58661 | common | 0.019049 | rerank_only |
| `5` | 47367 | 0.652429 | 47367 | common | 0.038155 | rerank_only |
| ` ` | 72601 | 1.000000 | 72601 | common | 0.000001 | rerank_only |
| `documentation` | 12615 | 0.173758 | 12615 | common | 0.156357 | generate |
| `arm` | 6315 | 0.086982 | 6315 | identifier/path | 0.350000 | generate |
| `binding` | 9619 | 0.132491 | 9619 | common | 0.180581 | generate |

### 80. brcm,bcm21664 documentation devicetree bindings arm bcm

- raw_postings_matches: 72,601
- weighted_candidates_after_policy: 2,000
- reranker_in: 50
- hydrated: 5
- time_ms: retrieval=3.3053, rerank=0.3434, hydrate=0.0225, e2e=3.6712
- hit_rank: 1

| token | df | df ratio | postings length | token type | candidate weight | action |
|---|---:|---:|---:|---|---:|---|
| `CTRL:BEGIN_WORD` | 72601 | 1.000000 | 72601 | common | 0.000001 | rerank_only |
| `CTRL:END_WORD` | 72601 | 1.000000 | 72601 | common | 0.000001 | rerank_only |
| `,` | 67976 | 0.936296 | 67976 | common | 0.005882 | rerank_only |
| `2` | 71667 | 0.987135 | 71667 | common | 0.001157 | rerank_only |
| `CTRL:NUM_SEP` | 60437 | 0.832454 | 60437 | common | 0.016384 | rerank_only |
| `1` | 66053 | 0.909808 | 66053 | common | 0.008445 | rerank_only |
| `6` | 54632 | 0.752497 | 54632 | common | 0.025406 | rerank_only |
| `4` | 56023 | 0.771656 | 56023 | common | 0.023160 | rerank_only |
| ` ` | 72601 | 1.000000 | 72601 | common | 0.000001 | rerank_only |
| `documentation` | 12615 | 0.173758 | 12615 | common | 0.156357 | generate |
| `arm` | 6315 | 0.086982 | 6315 | identifier/path | 0.350000 | generate |
| `binding` | 9619 | 0.132491 | 9619 | common | 0.180581 | generate |
