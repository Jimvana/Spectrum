# Spectrum Accurate Candidate Trace

- Docs: 72,601
- Queries: 80
- Policy: max_df_ratio=0.1, rare_df_ratio=0.05, max_precandidates=2000
- Accuracy: Hit@1=0.5875, MRR=0.5938, Recall@5=0.6

## Summary

| Metric | Avg | P95 | Max | Min |
|---|---:|---:|---:|---:|
| raw_postings_matches | 72601 | 72601 | 72601 | 72601 |
| initial_postings_matches | 1483.4 | 2000 | 2000 | 0 |
| reranker_in | 43.75 | 50 | 50 | 0 |
| hydrated | 4.375 | 5 | 5 | 0 |
| retrieval_ms | 1.4732 | 2.1706 | 2.5034 | 0.1049 |
| rerank_ms | 0.2815 | 0.3907 | 0.4886 | 0.0098 |
| hydrate_ms | 3.9701 | 5.625 | 119.0778 | 0.0005 |
| e2e_ms | 5.7247 | 8.0399 | 119.9563 | 0.1166 |

## Queries

### 01. clippy

- raw_postings_matches: 72,601
- initial_postings_matches_after_policy: 0
- reranker_in: 0
- hydrated: 0
- time_ms: retrieval=0.1279, rerank=0.0110, hydrate=0.0005, e2e=0.1394
- hit_rank: -

| token | df | df ratio | postings length | token type | action |
|---|---:|---:|---:|---|---|
| `CTRL:BEGIN_WORD` | 72601 | 1.000000 | 72601 | common | rerank_only |
| `CTRL:END_WORD` | 72601 | 1.000000 | 72601 | common | rerank_only |

### 02. rustfmt

- raw_postings_matches: 72,601
- initial_postings_matches_after_policy: 0
- reranker_in: 0
- hydrated: 0
- time_ms: retrieval=0.1049, rerank=0.0106, hydrate=0.0011, e2e=0.1166
- hit_rank: -

| token | df | df ratio | postings length | token type | action |
|---|---:|---:|---:|---|---|
| `CTRL:BEGIN_WORD` | 72601 | 1.000000 | 72601 | common | rerank_only |
| `CTRL:END_WORD` | 72601 | 1.000000 | 72601 | common | rerank_only |

### 03. renames documentation

- raw_postings_matches: 72,601
- initial_postings_matches_after_policy: 709
- reranker_in: 50
- hydrated: 5
- time_ms: retrieval=0.9318, rerank=0.2272, hydrate=103.6296, e2e=104.7886
- hit_rank: -

| token | df | df ratio | postings length | token type | action |
|---|---:|---:|---:|---|---|
| `CTRL:BEGIN_WORD` | 72601 | 1.000000 | 72601 | common | rerank_only |
| `CTRL:END_WORD` | 72601 | 1.000000 | 72601 | common | rerank_only |
| ` ` | 72601 | 1.000000 | 72601 | common | rerank_only |
| `documentation` | 12615 | 0.173758 | 12615 | common | rerank_only |
| `rename` | 709 | 0.009766 | 709 | rare | generate |

### 04. rtfp documentation rcu

- raw_postings_matches: 72,601
- initial_postings_matches_after_policy: 0
- reranker_in: 0
- hydrated: 0
- time_ms: retrieval=0.1534, rerank=0.0123, hydrate=0.0052, e2e=0.1709
- hit_rank: -

| token | df | df ratio | postings length | token type | action |
|---|---:|---:|---:|---|---|
| `CTRL:BEGIN_WORD` | 72601 | 1.000000 | 72601 | common | rerank_only |
| `CTRL:END_WORD` | 72601 | 1.000000 | 72601 | common | rerank_only |
| ` ` | 72601 | 1.000000 | 72601 | common | rerank_only |
| `documentation` | 12615 | 0.173758 | 12615 | common | rerank_only |

### 05. autoload documentation admin guide aoe

- raw_postings_matches: 72,601
- initial_postings_matches_after_policy: 359
- reranker_in: 50
- hydrated: 5
- time_ms: retrieval=0.5725, rerank=0.2850, hydrate=4.8599, e2e=5.7174
- hit_rank: 1

| token | df | df ratio | postings length | token type | action |
|---|---:|---:|---:|---|---|
| `CTRL:BEGIN_WORD` | 72601 | 1.000000 | 72601 | common | rerank_only |
| `CTRL:END_WORD` | 72601 | 1.000000 | 72601 | common | rerank_only |
| ` ` | 72601 | 1.000000 | 72601 | common | rerank_only |
| `documentation` | 12615 | 0.173758 | 12615 | common | rerank_only |
| `guide` | 359 | 0.004945 | 359 | rare | generate |

### 06. status documentation admin guide aoe

- raw_postings_matches: 72,601
- initial_postings_matches_after_policy: 359
- reranker_in: 50
- hydrated: 5
- time_ms: retrieval=0.5388, rerank=0.2850, hydrate=0.0200, e2e=0.8438
- hit_rank: 1

| token | df | df ratio | postings length | token type | action |
|---|---:|---:|---:|---|---|
| `status` | 18645 | 0.256815 | 18645 | common | rerank_only |
| ` ` | 72601 | 1.000000 | 72601 | common | rerank_only |
| `documentation` | 12615 | 0.173758 | 12615 | common | rerank_only |
| `CTRL:BEGIN_WORD` | 72601 | 1.000000 | 72601 | common | rerank_only |
| `CTRL:END_WORD` | 72601 | 1.000000 | 72601 | common | rerank_only |
| `guide` | 359 | 0.004945 | 359 | rare | generate |

### 07. udev install documentation admin guide aoe

- raw_postings_matches: 72,601
- initial_postings_matches_after_policy: 2,000
- reranker_in: 50
- hydrated: 5
- time_ms: retrieval=1.5724, rerank=0.3121, hydrate=22.9178, e2e=24.8023
- hit_rank: 1

| token | df | df ratio | postings length | token type | action |
|---|---:|---:|---:|---|---|
| `CTRL:BEGIN_WORD` | 72601 | 1.000000 | 72601 | common | rerank_only |
| `CTRL:END_WORD` | 72601 | 1.000000 | 72601 | common | rerank_only |
| ` ` | 72601 | 1.000000 | 72601 | common | rerank_only |
| `install` | 1771 | 0.024394 | 1771 | rare | generate |
| `documentation` | 12615 | 0.173758 | 12615 | common | rerank_only |
| `guide` | 359 | 0.004945 | 359 | rare | generate |

### 08. udev documentation admin guide aoe

- raw_postings_matches: 72,601
- initial_postings_matches_after_policy: 359
- reranker_in: 50
- hydrated: 5
- time_ms: retrieval=0.6465, rerank=0.2816, hydrate=0.0189, e2e=0.9470
- hit_rank: 1

| token | df | df ratio | postings length | token type | action |
|---|---:|---:|---:|---|---|
| `CTRL:BEGIN_WORD` | 72601 | 1.000000 | 72601 | common | rerank_only |
| `CTRL:END_WORD` | 72601 | 1.000000 | 72601 | common | rerank_only |
| ` ` | 72601 | 1.000000 | 72601 | common | rerank_only |
| `documentation` | 12615 | 0.173758 | 12615 | common | rerank_only |
| `guide` | 359 | 0.004945 | 359 | rare | generate |

### 09. devices documentation admin guide

- raw_postings_matches: 72,601
- initial_postings_matches_after_policy: 359
- reranker_in: 50
- hydrated: 5
- time_ms: retrieval=0.5506, rerank=0.2739, hydrate=0.0191, e2e=0.8436
- hit_rank: -

| token | df | df ratio | postings length | token type | action |
|---|---:|---:|---:|---|---|
| `CTRL:BEGIN_WORD` | 72601 | 1.000000 | 72601 | common | rerank_only |
| `CTRL:END_WORD` | 72601 | 1.000000 | 72601 | common | rerank_only |
| ` ` | 72601 | 1.000000 | 72601 | common | rerank_only |
| `documentation` | 12615 | 0.173758 | 12615 | common | rerank_only |
| `guide` | 359 | 0.004945 | 359 | rare | generate |
| `device` | 35573 | 0.489979 | 35573 | common | rerank_only |

### 10. gdbmacros documentation admin guide kdump

- raw_postings_matches: 72,601
- initial_postings_matches_after_policy: 359
- reranker_in: 50
- hydrated: 5
- time_ms: retrieval=0.5593, rerank=0.2744, hydrate=0.0174, e2e=0.8511
- hit_rank: 1

| token | df | df ratio | postings length | token type | action |
|---|---:|---:|---:|---|---|
| `CTRL:BEGIN_WORD` | 72601 | 1.000000 | 72601 | common | rerank_only |
| `CTRL:END_WORD` | 72601 | 1.000000 | 72601 | common | rerank_only |
| ` ` | 72601 | 1.000000 | 72601 | common | rerank_only |
| `documentation` | 12615 | 0.173758 | 12615 | common | rerank_only |
| `guide` | 359 | 0.004945 | 359 | rare | generate |

### 11. kernel parameters documentation admin guide

- raw_postings_matches: 72,601
- initial_postings_matches_after_policy: 359
- reranker_in: 50
- hydrated: 5
- time_ms: retrieval=0.5855, rerank=0.2930, hydrate=119.0778, e2e=119.9563
- hit_rank: 1

| token | df | df ratio | postings length | token type | action |
|---|---:|---:|---:|---|---|
| `kernel` | 28111 | 0.387199 | 28111 | common | rerank_only |
| ` ` | 72601 | 1.000000 | 72601 | common | rerank_only |
| `CTRL:BEGIN_WORD` | 72601 | 1.000000 | 72601 | common | rerank_only |
| `CTRL:END_WORD` | 72601 | 1.000000 | 72601 | common | rerank_only |
| `documentation` | 12615 | 0.173758 | 12615 | common | rerank_only |
| `guide` | 359 | 0.004945 | 359 | rare | generate |
| `parameter` | 7513 | 0.103483 | 7513 | common | rerank_only |

### 12. spkguide documentation admin guide

- raw_postings_matches: 72,601
- initial_postings_matches_after_policy: 359
- reranker_in: 50
- hydrated: 5
- time_ms: retrieval=0.5500, rerank=0.2698, hydrate=0.0181, e2e=0.8379
- hit_rank: -

| token | df | df ratio | postings length | token type | action |
|---|---:|---:|---:|---|---|
| `CTRL:BEGIN_WORD` | 72601 | 1.000000 | 72601 | common | rerank_only |
| `CTRL:END_WORD` | 72601 | 1.000000 | 72601 | common | rerank_only |
| ` ` | 72601 | 1.000000 | 72601 | common | rerank_only |
| `documentation` | 12615 | 0.173758 | 12615 | common | rerank_only |
| `guide` | 359 | 0.004945 | 359 | rare | generate |

### 13. kasan offsets documentation arch arm64

- raw_postings_matches: 72,601
- initial_postings_matches_after_policy: 2,000
- reranker_in: 50
- hydrated: 5
- time_ms: retrieval=1.7760, rerank=0.2153, hydrate=7.5472, e2e=9.5385
- hit_rank: -

| token | df | df ratio | postings length | token type | action |
|---|---:|---:|---:|---|---|
| `CTRL:BEGIN_WORD` | 72601 | 1.000000 | 72601 | common | rerank_only |
| `CTRL:END_WORD` | 72601 | 1.000000 | 72601 | common | rerank_only |
| ` ` | 72601 | 1.000000 | 72601 | common | rerank_only |
| `documentation` | 12615 | 0.173758 | 12615 | common | rerank_only |
| `arch` | 13130 | 0.180852 | 13130 | common | rerank_only |
| `arm` | 6315 | 0.086982 | 6315 | identifier/path | generate |
| `6` | 54632 | 0.752497 | 54632 | common | rerank_only |
| `CTRL:NUM_SEP` | 60437 | 0.832454 | 60437 | common | rerank_only |
| `4` | 56023 | 0.771656 | 56023 | common | rerank_only |
| `offset` | 19974 | 0.275120 | 19974 | common | rerank_only |

### 14. kasan documentation arch powerpc

- raw_postings_matches: 72,601
- initial_postings_matches_after_policy: 0
- reranker_in: 0
- hydrated: 0
- time_ms: retrieval=0.1993, rerank=0.0129, hydrate=0.0029, e2e=0.2151
- hit_rank: -

| token | df | df ratio | postings length | token type | action |
|---|---:|---:|---:|---|---|
| `CTRL:BEGIN_WORD` | 72601 | 1.000000 | 72601 | common | rerank_only |
| `CTRL:END_WORD` | 72601 | 1.000000 | 72601 | common | rerank_only |
| ` ` | 72601 | 1.000000 | 72601 | common | rerank_only |
| `documentation` | 12615 | 0.173758 | 12615 | common | rerank_only |
| `arch` | 13130 | 0.180852 | 13130 | common | rerank_only |

### 15. config3270 documentation arch s390

- raw_postings_matches: 72,601
- initial_postings_matches_after_policy: 0
- reranker_in: 0
- hydrated: 0
- time_ms: retrieval=0.2024, rerank=0.0130, hydrate=0.0008, e2e=0.2162
- hit_rank: -

| token | df | df ratio | postings length | token type | action |
|---|---:|---:|---:|---|---|
| `CTRL:BEGIN_WORD` | 72601 | 1.000000 | 72601 | common | rerank_only |
| `CTRL:END_WORD` | 72601 | 1.000000 | 72601 | common | rerank_only |
| `3` | 58661 | 0.807992 | 58661 | common | rerank_only |
| `CTRL:NUM_SEP` | 60437 | 0.832454 | 60437 | common | rerank_only |
| `2` | 71667 | 0.987135 | 71667 | common | rerank_only |
| `7` | 38264 | 0.527045 | 38264 | common | rerank_only |
| `0` | 71675 | 0.987245 | 71675 | common | rerank_only |
| ` ` | 72601 | 1.000000 | 72601 | common | rerank_only |
| `documentation` | 12615 | 0.173758 | 12615 | common | rerank_only |
| `arch` | 13130 | 0.180852 | 13130 | common | rerank_only |
| `9` | 37927 | 0.522403 | 37927 | common | rerank_only |

### 16. dax hv api documentation arch sparc oradax

- raw_postings_matches: 72,601
- initial_postings_matches_after_policy: 0
- reranker_in: 0
- hydrated: 0
- time_ms: retrieval=0.3114, rerank=0.0190, hydrate=0.0008, e2e=0.3312
- hit_rank: -

| token | df | df ratio | postings length | token type | action |
|---|---:|---:|---:|---|---|
| `CTRL:BEGIN_WORD` | 72601 | 1.000000 | 72601 | common | rerank_only |
| `CTRL:END_WORD` | 72601 | 1.000000 | 72601 | common | rerank_only |
| ` ` | 72601 | 1.000000 | 72601 | common | rerank_only |
| `documentation` | 12615 | 0.173758 | 12615 | common | rerank_only |
| `arch` | 13130 | 0.180852 | 13130 | common | rerank_only |

### 17. atomic bitops documentation

- raw_postings_matches: 72,601
- initial_postings_matches_after_policy: 0
- reranker_in: 0
- hydrated: 0
- time_ms: retrieval=0.1691, rerank=0.0119, hydrate=0.0006, e2e=0.1816
- hit_rank: -

| token | df | df ratio | postings length | token type | action |
|---|---:|---:|---:|---|---|
| `atomic` | 8621 | 0.118745 | 8621 | common | rerank_only |
| ` ` | 72601 | 1.000000 | 72601 | common | rerank_only |
| `CTRL:BEGIN_WORD` | 72601 | 1.000000 | 72601 | common | rerank_only |
| `CTRL:END_WORD` | 72601 | 1.000000 | 72601 | common | rerank_only |
| `documentation` | 12615 | 0.173758 | 12615 | common | rerank_only |

### 18. atomic documentation

- raw_postings_matches: 72,601
- initial_postings_matches_after_policy: 0
- reranker_in: 0
- hydrated: 0
- time_ms: retrieval=0.1219, rerank=0.0098, hydrate=0.0008, e2e=0.1325
- hit_rank: -

| token | df | df ratio | postings length | token type | action |
|---|---:|---:|---:|---|---|
| `atomic` | 8621 | 0.118745 | 8621 | common | rerank_only |
| ` ` | 72601 | 1.000000 | 72601 | common | rerank_only |
| `documentation` | 12615 | 0.173758 | 12615 | common | rerank_only |

### 19. conf documentation

- raw_postings_matches: 72,601
- initial_postings_matches_after_policy: 0
- reranker_in: 0
- hydrated: 0
- time_ms: retrieval=0.1431, rerank=0.0116, hydrate=0.0008, e2e=0.1555
- hit_rank: -

| token | df | df ratio | postings length | token type | action |
|---|---:|---:|---:|---|---|
| `CTRL:BEGIN_WORD` | 72601 | 1.000000 | 72601 | common | rerank_only |
| `CTRL:END_WORD` | 72601 | 1.000000 | 72601 | common | rerank_only |
| ` ` | 72601 | 1.000000 | 72601 | common | rerank_only |
| `documentation` | 12615 | 0.173758 | 12615 | common | rerank_only |

### 20. access controllers documentation devicetree bindings access

- raw_postings_matches: 72,601
- initial_postings_matches_after_policy: 0
- reranker_in: 0
- hydrated: 0
- time_ms: retrieval=0.2777, rerank=0.0153, hydrate=0.0006, e2e=0.2936
- hit_rank: -

| token | df | df ratio | postings length | token type | action |
|---|---:|---:|---:|---|---|
| `access` | 12103 | 0.166706 | 12103 | common | rerank_only |
| ` ` | 72601 | 1.000000 | 72601 | common | rerank_only |
| `CTRL:BEGIN_WORD` | 72601 | 1.000000 | 72601 | common | rerank_only |
| `CTRL:END_WORD` | 72601 | 1.000000 | 72601 | common | rerank_only |
| `documentation` | 12615 | 0.173758 | 12615 | common | rerank_only |
| `controller` | 10921 | 0.150425 | 10921 | common | rerank_only |
| `binding` | 9619 | 0.132491 | 9619 | common | rerank_only |

### 21. axs101 documentation devicetree bindings arc

- raw_postings_matches: 72,601
- initial_postings_matches_after_policy: 575
- reranker_in: 50
- hydrated: 5
- time_ms: retrieval=0.7301, rerank=0.2764, hydrate=1.5644, e2e=2.5709
- hit_rank: 1

| token | df | df ratio | postings length | token type | action |
|---|---:|---:|---:|---|---|
| `CTRL:BEGIN_WORD` | 72601 | 1.000000 | 72601 | common | rerank_only |
| `CTRL:END_WORD` | 72601 | 1.000000 | 72601 | common | rerank_only |
| `1` | 66053 | 0.909808 | 66053 | common | rerank_only |
| `CTRL:NUM_SEP` | 60437 | 0.832454 | 60437 | common | rerank_only |
| `0` | 71675 | 0.987245 | 71675 | common | rerank_only |
| ` ` | 72601 | 1.000000 | 72601 | common | rerank_only |
| `documentation` | 12615 | 0.173758 | 12615 | common | rerank_only |
| `arc` | 575 | 0.007920 | 575 | rare | generate |
| `binding` | 9619 | 0.132491 | 9619 | common | rerank_only |

### 22. axs103 documentation devicetree bindings arc

- raw_postings_matches: 72,601
- initial_postings_matches_after_policy: 575
- reranker_in: 50
- hydrated: 5
- time_ms: retrieval=0.7042, rerank=0.2803, hydrate=0.2391, e2e=1.2236
- hit_rank: 1

| token | df | df ratio | postings length | token type | action |
|---|---:|---:|---:|---|---|
| `CTRL:BEGIN_WORD` | 72601 | 1.000000 | 72601 | common | rerank_only |
| `CTRL:END_WORD` | 72601 | 1.000000 | 72601 | common | rerank_only |
| `1` | 66053 | 0.909808 | 66053 | common | rerank_only |
| `CTRL:NUM_SEP` | 60437 | 0.832454 | 60437 | common | rerank_only |
| `0` | 71675 | 0.987245 | 71675 | common | rerank_only |
| `3` | 58661 | 0.807992 | 58661 | common | rerank_only |
| ` ` | 72601 | 1.000000 | 72601 | common | rerank_only |
| `documentation` | 12615 | 0.173758 | 12615 | common | rerank_only |
| `arc` | 575 | 0.007920 | 575 | rare | generate |
| `binding` | 9619 | 0.132491 | 9619 | common | rerank_only |

### 23. eznps documentation devicetree bindings arc

- raw_postings_matches: 72,601
- initial_postings_matches_after_policy: 575
- reranker_in: 50
- hydrated: 5
- time_ms: retrieval=0.6859, rerank=0.2695, hydrate=0.1759, e2e=1.1313
- hit_rank: 1

| token | df | df ratio | postings length | token type | action |
|---|---:|---:|---:|---|---|
| `CTRL:BEGIN_WORD` | 72601 | 1.000000 | 72601 | common | rerank_only |
| `CTRL:END_WORD` | 72601 | 1.000000 | 72601 | common | rerank_only |
| ` ` | 72601 | 1.000000 | 72601 | common | rerank_only |
| `documentation` | 12615 | 0.173758 | 12615 | common | rerank_only |
| `arc` | 575 | 0.007920 | 575 | rare | generate |
| `binding` | 9619 | 0.132491 | 9619 | common | rerank_only |

### 24. hsdk documentation devicetree bindings arc

- raw_postings_matches: 72,601
- initial_postings_matches_after_policy: 575
- reranker_in: 50
- hydrated: 5
- time_ms: retrieval=0.6879, rerank=0.2728, hydrate=0.0191, e2e=0.9798
- hit_rank: 1

| token | df | df ratio | postings length | token type | action |
|---|---:|---:|---:|---|---|
| `CTRL:BEGIN_WORD` | 72601 | 1.000000 | 72601 | common | rerank_only |
| `CTRL:END_WORD` | 72601 | 1.000000 | 72601 | common | rerank_only |
| ` ` | 72601 | 1.000000 | 72601 | common | rerank_only |
| `documentation` | 12615 | 0.173758 | 12615 | common | rerank_only |
| `arc` | 575 | 0.007920 | 575 | rare | generate |
| `binding` | 9619 | 0.132491 | 9619 | common | rerank_only |

### 25. pct documentation devicetree bindings arc

- raw_postings_matches: 72,601
- initial_postings_matches_after_policy: 575
- reranker_in: 50
- hydrated: 5
- time_ms: retrieval=0.6708, rerank=0.2847, hydrate=0.0198, e2e=0.9753
- hit_rank: 1

| token | df | df ratio | postings length | token type | action |
|---|---:|---:|---:|---|---|
| `CTRL:BEGIN_WORD` | 72601 | 1.000000 | 72601 | common | rerank_only |
| `CTRL:END_WORD` | 72601 | 1.000000 | 72601 | common | rerank_only |
| ` ` | 72601 | 1.000000 | 72601 | common | rerank_only |
| `documentation` | 12615 | 0.173758 | 12615 | common | rerank_only |
| `arc` | 575 | 0.007920 | 575 | rare | generate |
| `binding` | 9619 | 0.132491 | 9619 | common | rerank_only |

### 26. snps,archs pct documentation devicetree bindings arc

- raw_postings_matches: 72,601
- initial_postings_matches_after_policy: 575
- reranker_in: 50
- hydrated: 5
- time_ms: retrieval=0.7303, rerank=0.2973, hydrate=0.0192, e2e=1.0468
- hit_rank: -

| token | df | df ratio | postings length | token type | action |
|---|---:|---:|---:|---|---|
| `CTRL:BEGIN_WORD` | 72601 | 1.000000 | 72601 | common | rerank_only |
| `CTRL:END_WORD` | 72601 | 1.000000 | 72601 | common | rerank_only |
| `,` | 67976 | 0.936296 | 67976 | common | rerank_only |
| ` ` | 72601 | 1.000000 | 72601 | common | rerank_only |
| `documentation` | 12615 | 0.173758 | 12615 | common | rerank_only |
| `arc` | 575 | 0.007920 | 575 | rare | generate |
| `arch` | 13130 | 0.180852 | 13130 | common | rerank_only |
| `binding` | 9619 | 0.132491 | 9619 | common | rerank_only |

### 27. actions documentation devicetree bindings arm

- raw_postings_matches: 72,601
- initial_postings_matches_after_policy: 2,000
- reranker_in: 50
- hydrated: 5
- time_ms: retrieval=1.8581, rerank=0.3106, hydrate=1.8336, e2e=4.0023
- hit_rank: -

| token | df | df ratio | postings length | token type | action |
|---|---:|---:|---:|---|---|
| `CTRL:BEGIN_WORD` | 72601 | 1.000000 | 72601 | common | rerank_only |
| `CTRL:END_WORD` | 72601 | 1.000000 | 72601 | common | rerank_only |
| ` ` | 72601 | 1.000000 | 72601 | common | rerank_only |
| `documentation` | 12615 | 0.173758 | 12615 | common | rerank_only |
| `arm` | 6315 | 0.086982 | 6315 | identifier/path | generate |
| `action` | 9346 | 0.128731 | 9346 | common | rerank_only |
| `binding` | 9619 | 0.132491 | 9619 | common | rerank_only |

### 28. airoha,en7581 chip scu documentation devicetree bindings arm

- raw_postings_matches: 72,601
- initial_postings_matches_after_policy: 2,000
- reranker_in: 50
- hydrated: 5
- time_ms: retrieval=1.9251, rerank=0.3630, hydrate=0.7059, e2e=2.9940
- hit_rank: -

| token | df | df ratio | postings length | token type | action |
|---|---:|---:|---:|---|---|
| `CTRL:BEGIN_WORD` | 72601 | 1.000000 | 72601 | common | rerank_only |
| `CTRL:END_WORD` | 72601 | 1.000000 | 72601 | common | rerank_only |
| `,` | 67976 | 0.936296 | 67976 | common | rerank_only |
| `en` | 9582 | 0.131982 | 9582 | common | rerank_only |
| `7` | 38264 | 0.527045 | 38264 | common | rerank_only |
| `CTRL:NUM_SEP` | 60437 | 0.832454 | 60437 | common | rerank_only |
| `5` | 47367 | 0.652429 | 47367 | common | rerank_only |
| `8` | 51787 | 0.713310 | 51787 | common | rerank_only |
| `1` | 66053 | 0.909808 | 66053 | common | rerank_only |
| ` ` | 72601 | 1.000000 | 72601 | common | rerank_only |
| `chip` | 8765 | 0.120728 | 8765 | common | rerank_only |
| `documentation` | 12615 | 0.173758 | 12615 | common | rerank_only |
| `arm` | 6315 | 0.086982 | 6315 | identifier/path | generate |
| `binding` | 9619 | 0.132491 | 9619 | common | rerank_only |

### 29. airoha documentation devicetree bindings arm

- raw_postings_matches: 72,601
- initial_postings_matches_after_policy: 2,000
- reranker_in: 50
- hydrated: 5
- time_ms: retrieval=1.7742, rerank=0.3250, hydrate=0.0217, e2e=2.1209
- hit_rank: -

| token | df | df ratio | postings length | token type | action |
|---|---:|---:|---:|---|---|
| `CTRL:BEGIN_WORD` | 72601 | 1.000000 | 72601 | common | rerank_only |
| `CTRL:END_WORD` | 72601 | 1.000000 | 72601 | common | rerank_only |
| ` ` | 72601 | 1.000000 | 72601 | common | rerank_only |
| `documentation` | 12615 | 0.173758 | 12615 | common | rerank_only |
| `arm` | 6315 | 0.086982 | 6315 | identifier/path | generate |
| `binding` | 9619 | 0.132491 | 9619 | common | rerank_only |

### 30. altera documentation devicetree bindings arm

- raw_postings_matches: 72,601
- initial_postings_matches_after_policy: 2,000
- reranker_in: 50
- hydrated: 5
- time_ms: retrieval=1.7528, rerank=0.3191, hydrate=0.0188, e2e=2.0907
- hit_rank: -

| token | df | df ratio | postings length | token type | action |
|---|---:|---:|---:|---|---|
| `CTRL:BEGIN_WORD` | 72601 | 1.000000 | 72601 | common | rerank_only |
| `CTRL:END_WORD` | 72601 | 1.000000 | 72601 | common | rerank_only |
| ` ` | 72601 | 1.000000 | 72601 | common | rerank_only |
| `documentation` | 12615 | 0.173758 | 12615 | common | rerank_only |
| `arm` | 6315 | 0.086982 | 6315 | identifier/path | generate |
| `binding` | 9619 | 0.132491 | 9619 | common | rerank_only |

### 31. socfpga clk manager documentation devicetree bindings arm altera

- raw_postings_matches: 72,601
- initial_postings_matches_after_policy: 2,000
- reranker_in: 50
- hydrated: 5
- time_ms: retrieval=2.0384, rerank=0.3772, hydrate=4.6245, e2e=7.0401
- hit_rank: 1

| token | df | df ratio | postings length | token type | action |
|---|---:|---:|---:|---|---|
| `CTRL:BEGIN_WORD` | 72601 | 1.000000 | 72601 | common | rerank_only |
| `CTRL:END_WORD` | 72601 | 1.000000 | 72601 | common | rerank_only |
| ` ` | 72601 | 1.000000 | 72601 | common | rerank_only |
| `manager` | 1396 | 0.019228 | 1396 | rare | generate |
| `documentation` | 12615 | 0.173758 | 12615 | common | rerank_only |
| `arm` | 6315 | 0.086982 | 6315 | identifier/path | generate |
| `binding` | 9619 | 0.132491 | 9619 | common | rerank_only |

### 32. amazon,al documentation devicetree bindings arm

- raw_postings_matches: 72,601
- initial_postings_matches_after_policy: 2,000
- reranker_in: 50
- hydrated: 5
- time_ms: retrieval=2.0353, rerank=0.3188, hydrate=1.6772, e2e=4.0313
- hit_rank: 1

| token | df | df ratio | postings length | token type | action |
|---|---:|---:|---:|---|---|
| `amazon` | 121 | 0.001667 | 121 | rare | generate |
| `,` | 67976 | 0.936296 | 67976 | common | rerank_only |
| `al` | 718 | 0.009890 | 718 | rare | generate |
| ` ` | 72601 | 1.000000 | 72601 | common | rerank_only |
| `documentation` | 12615 | 0.173758 | 12615 | common | rerank_only |
| `CTRL:BEGIN_WORD` | 72601 | 1.000000 | 72601 | common | rerank_only |
| `CTRL:END_WORD` | 72601 | 1.000000 | 72601 | common | rerank_only |
| `arm` | 6315 | 0.086982 | 6315 | identifier/path | generate |
| `binding` | 9619 | 0.132491 | 9619 | common | rerank_only |

### 33. amd,pensando documentation devicetree bindings arm

- raw_postings_matches: 72,601
- initial_postings_matches_after_policy: 2,000
- reranker_in: 50
- hydrated: 5
- time_ms: retrieval=1.7785, rerank=0.3075, hydrate=0.0205, e2e=2.1065
- hit_rank: -

| token | df | df ratio | postings length | token type | action |
|---|---:|---:|---:|---|---|
| `CTRL:BEGIN_WORD` | 72601 | 1.000000 | 72601 | common | rerank_only |
| `CTRL:END_WORD` | 72601 | 1.000000 | 72601 | common | rerank_only |
| `,` | 67976 | 0.936296 | 67976 | common | rerank_only |
| ` ` | 72601 | 1.000000 | 72601 | common | rerank_only |
| `documentation` | 12615 | 0.173758 | 12615 | common | rerank_only |
| `arm` | 6315 | 0.086982 | 6315 | identifier/path | generate |
| `binding` | 9619 | 0.132491 | 9619 | common | rerank_only |

### 34. amd,seattle documentation devicetree bindings arm

- raw_postings_matches: 72,601
- initial_postings_matches_after_policy: 2,000
- reranker_in: 50
- hydrated: 5
- time_ms: retrieval=1.7850, rerank=0.3134, hydrate=0.0185, e2e=2.1169
- hit_rank: -

| token | df | df ratio | postings length | token type | action |
|---|---:|---:|---:|---|---|
| `CTRL:BEGIN_WORD` | 72601 | 1.000000 | 72601 | common | rerank_only |
| `CTRL:END_WORD` | 72601 | 1.000000 | 72601 | common | rerank_only |
| `,` | 67976 | 0.936296 | 67976 | common | rerank_only |
| ` ` | 72601 | 1.000000 | 72601 | common | rerank_only |
| `documentation` | 12615 | 0.173758 | 12615 | common | rerank_only |
| `arm` | 6315 | 0.086982 | 6315 | identifier/path | generate |
| `binding` | 9619 | 0.132491 | 9619 | common | rerank_only |

### 35. amlogic documentation devicetree bindings arm

- raw_postings_matches: 72,601
- initial_postings_matches_after_policy: 2,000
- reranker_in: 50
- hydrated: 5
- time_ms: retrieval=1.8273, rerank=0.2989, hydrate=0.0191, e2e=2.1453
- hit_rank: -

| token | df | df ratio | postings length | token type | action |
|---|---:|---:|---:|---|---|
| `CTRL:BEGIN_WORD` | 72601 | 1.000000 | 72601 | common | rerank_only |
| `CTRL:END_WORD` | 72601 | 1.000000 | 72601 | common | rerank_only |
| ` ` | 72601 | 1.000000 | 72601 | common | rerank_only |
| `documentation` | 12615 | 0.173758 | 12615 | common | rerank_only |
| `arm` | 6315 | 0.086982 | 6315 | identifier/path | generate |
| `binding` | 9619 | 0.132491 | 9619 | common | rerank_only |

### 36. amlogic,meson gx ao secure documentation devicetree bindings arm amlogic

- raw_postings_matches: 72,601
- initial_postings_matches_after_policy: 2,000
- reranker_in: 50
- hydrated: 5
- time_ms: retrieval=2.1346, rerank=0.4081, hydrate=2.7227, e2e=5.2654
- hit_rank: 1

| token | df | df ratio | postings length | token type | action |
|---|---:|---:|---:|---|---|
| `CTRL:BEGIN_WORD` | 72601 | 1.000000 | 72601 | common | rerank_only |
| `CTRL:END_WORD` | 72601 | 1.000000 | 72601 | common | rerank_only |
| `,` | 67976 | 0.936296 | 67976 | common | rerank_only |
| `meson` | 335 | 0.004614 | 335 | rare | generate |
| ` ` | 72601 | 1.000000 | 72601 | common | rerank_only |
| `ao` | 562 | 0.007741 | 562 | rare | generate |
| `secure` | 1370 | 0.018870 | 1370 | rare | generate |
| `documentation` | 12615 | 0.173758 | 12615 | common | rerank_only |
| `arm` | 6315 | 0.086982 | 6315 | identifier/path | generate |
| `binding` | 9619 | 0.132491 | 9619 | common | rerank_only |

### 37. amlogic,meson mx secbus2 documentation devicetree bindings arm amlogic

- raw_postings_matches: 72,601
- initial_postings_matches_after_policy: 2,000
- reranker_in: 50
- hydrated: 5
- time_ms: retrieval=2.0023, rerank=0.3907, hydrate=1.5605, e2e=3.9535
- hit_rank: 1

| token | df | df ratio | postings length | token type | action |
|---|---:|---:|---:|---|---|
| `CTRL:BEGIN_WORD` | 72601 | 1.000000 | 72601 | common | rerank_only |
| `CTRL:END_WORD` | 72601 | 1.000000 | 72601 | common | rerank_only |
| `,` | 67976 | 0.936296 | 67976 | common | rerank_only |
| `meson` | 335 | 0.004614 | 335 | rare | generate |
| ` ` | 72601 | 1.000000 | 72601 | common | rerank_only |
| `2` | 71667 | 0.987135 | 71667 | common | rerank_only |
| `documentation` | 12615 | 0.173758 | 12615 | common | rerank_only |
| `arm` | 6315 | 0.086982 | 6315 | identifier/path | generate |
| `binding` | 9619 | 0.132491 | 9619 | common | rerank_only |

### 38. apm documentation devicetree bindings arm

- raw_postings_matches: 72,601
- initial_postings_matches_after_policy: 2,000
- reranker_in: 50
- hydrated: 5
- time_ms: retrieval=1.7590, rerank=0.2930, hydrate=0.0211, e2e=2.0731
- hit_rank: -

| token | df | df ratio | postings length | token type | action |
|---|---:|---:|---:|---|---|
| `CTRL:BEGIN_WORD` | 72601 | 1.000000 | 72601 | common | rerank_only |
| `CTRL:END_WORD` | 72601 | 1.000000 | 72601 | common | rerank_only |
| ` ` | 72601 | 1.000000 | 72601 | common | rerank_only |
| `documentation` | 12615 | 0.173758 | 12615 | common | rerank_only |
| `arm` | 6315 | 0.086982 | 6315 | identifier/path | generate |
| `binding` | 9619 | 0.132491 | 9619 | common | rerank_only |

### 39. apple documentation devicetree bindings arm

- raw_postings_matches: 72,601
- initial_postings_matches_after_policy: 2,000
- reranker_in: 50
- hydrated: 5
- time_ms: retrieval=1.8772, rerank=0.3524, hydrate=5.6250, e2e=7.8546
- hit_rank: 2

| token | df | df ratio | postings length | token type | action |
|---|---:|---:|---:|---|---|
| `apple` | 377 | 0.005193 | 377 | rare | generate |
| ` ` | 72601 | 1.000000 | 72601 | common | rerank_only |
| `documentation` | 12615 | 0.173758 | 12615 | common | rerank_only |
| `CTRL:BEGIN_WORD` | 72601 | 1.000000 | 72601 | common | rerank_only |
| `CTRL:END_WORD` | 72601 | 1.000000 | 72601 | common | rerank_only |
| `arm` | 6315 | 0.086982 | 6315 | identifier/path | generate |
| `binding` | 9619 | 0.132491 | 9619 | common | rerank_only |

### 40. apple,pmgr documentation devicetree bindings arm apple

- raw_postings_matches: 72,601
- initial_postings_matches_after_policy: 2,000
- reranker_in: 50
- hydrated: 5
- time_ms: retrieval=2.1706, rerank=0.3775, hydrate=0.6677, e2e=3.2158
- hit_rank: 1

| token | df | df ratio | postings length | token type | action |
|---|---:|---:|---:|---|---|
| `apple` | 377 | 0.005193 | 377 | rare | generate |
| `,` | 67976 | 0.936296 | 67976 | common | rerank_only |
| `CTRL:BEGIN_WORD` | 72601 | 1.000000 | 72601 | common | rerank_only |
| `CTRL:END_WORD` | 72601 | 1.000000 | 72601 | common | rerank_only |
| ` ` | 72601 | 1.000000 | 72601 | common | rerank_only |
| `documentation` | 12615 | 0.173758 | 12615 | common | rerank_only |
| `arm` | 6315 | 0.086982 | 6315 | identifier/path | generate |
| `binding` | 9619 | 0.132491 | 9619 | common | rerank_only |

### 41. arm,cci documentation devicetree bindings arm

- raw_postings_matches: 72,601
- initial_postings_matches_after_policy: 2,000
- reranker_in: 50
- hydrated: 5
- time_ms: retrieval=1.7700, rerank=0.3006, hydrate=1.3808, e2e=3.4514
- hit_rank: 1

| token | df | df ratio | postings length | token type | action |
|---|---:|---:|---:|---|---|
| `arm` | 6315 | 0.086982 | 6315 | identifier/path | generate |
| `,` | 67976 | 0.936296 | 67976 | common | rerank_only |
| `CTRL:BEGIN_WORD` | 72601 | 1.000000 | 72601 | common | rerank_only |
| `CTRL:END_WORD` | 72601 | 1.000000 | 72601 | common | rerank_only |
| ` ` | 72601 | 1.000000 | 72601 | common | rerank_only |
| `documentation` | 12615 | 0.173758 | 12615 | common | rerank_only |
| `binding` | 9619 | 0.132491 | 9619 | common | rerank_only |

### 42. arm,coresight catu documentation devicetree bindings arm

- raw_postings_matches: 72,601
- initial_postings_matches_after_policy: 2,000
- reranker_in: 50
- hydrated: 5
- time_ms: retrieval=1.8378, rerank=0.3107, hydrate=1.2905, e2e=3.4390
- hit_rank: 1

| token | df | df ratio | postings length | token type | action |
|---|---:|---:|---:|---|---|
| `arm` | 6315 | 0.086982 | 6315 | identifier/path | generate |
| `,` | 67976 | 0.936296 | 67976 | common | rerank_only |
| `CTRL:BEGIN_WORD` | 72601 | 1.000000 | 72601 | common | rerank_only |
| `CTRL:END_WORD` | 72601 | 1.000000 | 72601 | common | rerank_only |
| ` ` | 72601 | 1.000000 | 72601 | common | rerank_only |
| `documentation` | 12615 | 0.173758 | 12615 | common | rerank_only |
| `binding` | 9619 | 0.132491 | 9619 | common | rerank_only |

### 43. arm,coresight cpu debug documentation devicetree bindings arm

- raw_postings_matches: 72,601
- initial_postings_matches_after_policy: 2,000
- reranker_in: 50
- hydrated: 5
- time_ms: retrieval=1.8228, rerank=0.3292, hydrate=0.6493, e2e=2.8013
- hit_rank: 1

| token | df | df ratio | postings length | token type | action |
|---|---:|---:|---:|---|---|
| `arm` | 6315 | 0.086982 | 6315 | identifier/path | generate |
| `,` | 67976 | 0.936296 | 67976 | common | rerank_only |
| `CTRL:BEGIN_WORD` | 72601 | 1.000000 | 72601 | common | rerank_only |
| `CTRL:END_WORD` | 72601 | 1.000000 | 72601 | common | rerank_only |
| ` ` | 72601 | 1.000000 | 72601 | common | rerank_only |
| `documentation` | 12615 | 0.173758 | 12615 | common | rerank_only |
| `binding` | 9619 | 0.132491 | 9619 | common | rerank_only |

### 44. arm,coresight cti documentation devicetree bindings arm

- raw_postings_matches: 72,601
- initial_postings_matches_after_policy: 2,000
- reranker_in: 50
- hydrated: 5
- time_ms: retrieval=1.7982, rerank=0.3137, hydrate=0.0178, e2e=2.1297
- hit_rank: 1

| token | df | df ratio | postings length | token type | action |
|---|---:|---:|---:|---|---|
| `arm` | 6315 | 0.086982 | 6315 | identifier/path | generate |
| `,` | 67976 | 0.936296 | 67976 | common | rerank_only |
| `CTRL:BEGIN_WORD` | 72601 | 1.000000 | 72601 | common | rerank_only |
| `CTRL:END_WORD` | 72601 | 1.000000 | 72601 | common | rerank_only |
| ` ` | 72601 | 1.000000 | 72601 | common | rerank_only |
| `documentation` | 12615 | 0.173758 | 12615 | common | rerank_only |
| `binding` | 9619 | 0.132491 | 9619 | common | rerank_only |

### 45. arm,coresight dummy sink documentation devicetree bindings arm

- raw_postings_matches: 72,601
- initial_postings_matches_after_policy: 2,000
- reranker_in: 50
- hydrated: 5
- time_ms: retrieval=2.0460, rerank=0.3412, hydrate=2.8388, e2e=5.2260
- hit_rank: 1

| token | df | df ratio | postings length | token type | action |
|---|---:|---:|---:|---|---|
| `arm` | 6315 | 0.086982 | 6315 | identifier/path | generate |
| `,` | 67976 | 0.936296 | 67976 | common | rerank_only |
| `CTRL:BEGIN_WORD` | 72601 | 1.000000 | 72601 | common | rerank_only |
| `CTRL:END_WORD` | 72601 | 1.000000 | 72601 | common | rerank_only |
| ` ` | 72601 | 1.000000 | 72601 | common | rerank_only |
| `dummy` | 3426 | 0.047189 | 3426 | rare | generate |
| `sink` | 1102 | 0.015179 | 1102 | rare | generate |
| `documentation` | 12615 | 0.173758 | 12615 | common | rerank_only |
| `binding` | 9619 | 0.132491 | 9619 | common | rerank_only |

### 46. arm,coresight dummy source documentation devicetree bindings arm

- raw_postings_matches: 72,601
- initial_postings_matches_after_policy: 2,000
- reranker_in: 50
- hydrated: 5
- time_ms: retrieval=2.2167, rerank=0.3623, hydrate=2.7600, e2e=5.3390
- hit_rank: 1

| token | df | df ratio | postings length | token type | action |
|---|---:|---:|---:|---|---|
| `arm` | 6315 | 0.086982 | 6315 | identifier/path | generate |
| `,` | 67976 | 0.936296 | 67976 | common | rerank_only |
| `CTRL:BEGIN_WORD` | 72601 | 1.000000 | 72601 | common | rerank_only |
| `CTRL:END_WORD` | 72601 | 1.000000 | 72601 | common | rerank_only |
| ` ` | 72601 | 1.000000 | 72601 | common | rerank_only |
| `dummy` | 3426 | 0.047189 | 3426 | rare | generate |
| `source` | 10659 | 0.146816 | 10659 | common | rerank_only |
| `documentation` | 12615 | 0.173758 | 12615 | common | rerank_only |
| `binding` | 9619 | 0.132491 | 9619 | common | rerank_only |

### 47. arm,coresight dynamic funnel documentation devicetree bindings arm

- raw_postings_matches: 72,601
- initial_postings_matches_after_policy: 2,000
- reranker_in: 50
- hydrated: 5
- time_ms: retrieval=2.0733, rerank=0.3483, hydrate=1.4223, e2e=3.8439
- hit_rank: 1

| token | df | df ratio | postings length | token type | action |
|---|---:|---:|---:|---|---|
| `arm` | 6315 | 0.086982 | 6315 | identifier/path | generate |
| `,` | 67976 | 0.936296 | 67976 | common | rerank_only |
| `CTRL:BEGIN_WORD` | 72601 | 1.000000 | 72601 | common | rerank_only |
| `CTRL:END_WORD` | 72601 | 1.000000 | 72601 | common | rerank_only |
| ` ` | 72601 | 1.000000 | 72601 | common | rerank_only |
| `dynamic` | 3001 | 0.041336 | 3001 | rare | generate |
| `funnel` | 58 | 0.000799 | 58 | rare | generate |
| `documentation` | 12615 | 0.173758 | 12615 | common | rerank_only |
| `binding` | 9619 | 0.132491 | 9619 | common | rerank_only |

### 48. arm,coresight dynamic replicator documentation devicetree bindings arm

- raw_postings_matches: 72,601
- initial_postings_matches_after_policy: 2,000
- reranker_in: 50
- hydrated: 5
- time_ms: retrieval=1.9604, rerank=0.3404, hydrate=2.2797, e2e=4.5805
- hit_rank: 1

| token | df | df ratio | postings length | token type | action |
|---|---:|---:|---:|---|---|
| `arm` | 6315 | 0.086982 | 6315 | identifier/path | generate |
| `,` | 67976 | 0.936296 | 67976 | common | rerank_only |
| `CTRL:BEGIN_WORD` | 72601 | 1.000000 | 72601 | common | rerank_only |
| `CTRL:END_WORD` | 72601 | 1.000000 | 72601 | common | rerank_only |
| ` ` | 72601 | 1.000000 | 72601 | common | rerank_only |
| `dynamic` | 3001 | 0.041336 | 3001 | rare | generate |
| `documentation` | 12615 | 0.173758 | 12615 | common | rerank_only |
| `binding` | 9619 | 0.132491 | 9619 | common | rerank_only |

### 49. arm,coresight etb10 documentation devicetree bindings arm

- raw_postings_matches: 72,601
- initial_postings_matches_after_policy: 2,000
- reranker_in: 50
- hydrated: 5
- time_ms: retrieval=1.8536, rerank=0.3177, hydrate=0.0201, e2e=2.1914
- hit_rank: 1

| token | df | df ratio | postings length | token type | action |
|---|---:|---:|---:|---|---|
| `arm` | 6315 | 0.086982 | 6315 | identifier/path | generate |
| `,` | 67976 | 0.936296 | 67976 | common | rerank_only |
| `CTRL:BEGIN_WORD` | 72601 | 1.000000 | 72601 | common | rerank_only |
| `CTRL:END_WORD` | 72601 | 1.000000 | 72601 | common | rerank_only |
| ` ` | 72601 | 1.000000 | 72601 | common | rerank_only |
| `1` | 66053 | 0.909808 | 66053 | common | rerank_only |
| `CTRL:NUM_SEP` | 60437 | 0.832454 | 60437 | common | rerank_only |
| `0` | 71675 | 0.987245 | 71675 | common | rerank_only |
| `documentation` | 12615 | 0.173758 | 12615 | common | rerank_only |
| `binding` | 9619 | 0.132491 | 9619 | common | rerank_only |

### 50. arm,coresight etm documentation devicetree bindings arm

- raw_postings_matches: 72,601
- initial_postings_matches_after_policy: 2,000
- reranker_in: 50
- hydrated: 5
- time_ms: retrieval=1.7898, rerank=0.3212, hydrate=0.0179, e2e=2.1289
- hit_rank: 1

| token | df | df ratio | postings length | token type | action |
|---|---:|---:|---:|---|---|
| `arm` | 6315 | 0.086982 | 6315 | identifier/path | generate |
| `,` | 67976 | 0.936296 | 67976 | common | rerank_only |
| `CTRL:BEGIN_WORD` | 72601 | 1.000000 | 72601 | common | rerank_only |
| `CTRL:END_WORD` | 72601 | 1.000000 | 72601 | common | rerank_only |
| ` ` | 72601 | 1.000000 | 72601 | common | rerank_only |
| `documentation` | 12615 | 0.173758 | 12615 | common | rerank_only |
| `binding` | 9619 | 0.132491 | 9619 | common | rerank_only |

### 51. arm,coresight static funnel documentation devicetree bindings arm

- raw_postings_matches: 72,601
- initial_postings_matches_after_policy: 2,000
- reranker_in: 50
- hydrated: 5
- time_ms: retrieval=1.8837, rerank=0.3517, hydrate=0.0200, e2e=2.2554
- hit_rank: 1

| token | df | df ratio | postings length | token type | action |
|---|---:|---:|---:|---|---|
| `arm` | 6315 | 0.086982 | 6315 | identifier/path | generate |
| `,` | 67976 | 0.936296 | 67976 | common | rerank_only |
| `CTRL:BEGIN_WORD` | 72601 | 1.000000 | 72601 | common | rerank_only |
| `CTRL:END_WORD` | 72601 | 1.000000 | 72601 | common | rerank_only |
| ` ` | 72601 | 1.000000 | 72601 | common | rerank_only |
| `static` | 42102 | 0.579909 | 42102 | common | rerank_only |
| `funnel` | 58 | 0.000799 | 58 | rare | generate |
| `documentation` | 12615 | 0.173758 | 12615 | common | rerank_only |
| `binding` | 9619 | 0.132491 | 9619 | common | rerank_only |

### 52. arm,coresight static replicator documentation devicetree bindings arm

- raw_postings_matches: 72,601
- initial_postings_matches_after_policy: 2,000
- reranker_in: 50
- hydrated: 5
- time_ms: retrieval=1.8500, rerank=0.3297, hydrate=0.0198, e2e=2.1995
- hit_rank: 1

| token | df | df ratio | postings length | token type | action |
|---|---:|---:|---:|---|---|
| `arm` | 6315 | 0.086982 | 6315 | identifier/path | generate |
| `,` | 67976 | 0.936296 | 67976 | common | rerank_only |
| `CTRL:BEGIN_WORD` | 72601 | 1.000000 | 72601 | common | rerank_only |
| `CTRL:END_WORD` | 72601 | 1.000000 | 72601 | common | rerank_only |
| ` ` | 72601 | 1.000000 | 72601 | common | rerank_only |
| `static` | 42102 | 0.579909 | 42102 | common | rerank_only |
| `documentation` | 12615 | 0.173758 | 12615 | common | rerank_only |
| `binding` | 9619 | 0.132491 | 9619 | common | rerank_only |

### 53. arm,coresight stm documentation devicetree bindings arm

- raw_postings_matches: 72,601
- initial_postings_matches_after_policy: 2,000
- reranker_in: 50
- hydrated: 5
- time_ms: retrieval=1.8840, rerank=0.3110, hydrate=0.6983, e2e=2.8933
- hit_rank: 1

| token | df | df ratio | postings length | token type | action |
|---|---:|---:|---:|---|---|
| `arm` | 6315 | 0.086982 | 6315 | identifier/path | generate |
| `,` | 67976 | 0.936296 | 67976 | common | rerank_only |
| `CTRL:BEGIN_WORD` | 72601 | 1.000000 | 72601 | common | rerank_only |
| `CTRL:END_WORD` | 72601 | 1.000000 | 72601 | common | rerank_only |
| ` ` | 72601 | 1.000000 | 72601 | common | rerank_only |
| `documentation` | 12615 | 0.173758 | 12615 | common | rerank_only |
| `binding` | 9619 | 0.132491 | 9619 | common | rerank_only |

### 54. arm,coresight tmc documentation devicetree bindings arm

- raw_postings_matches: 72,601
- initial_postings_matches_after_policy: 2,000
- reranker_in: 50
- hydrated: 5
- time_ms: retrieval=1.8778, rerank=0.3205, hydrate=1.1376, e2e=3.3359
- hit_rank: 1

| token | df | df ratio | postings length | token type | action |
|---|---:|---:|---:|---|---|
| `arm` | 6315 | 0.086982 | 6315 | identifier/path | generate |
| `,` | 67976 | 0.936296 | 67976 | common | rerank_only |
| `CTRL:BEGIN_WORD` | 72601 | 1.000000 | 72601 | common | rerank_only |
| `CTRL:END_WORD` | 72601 | 1.000000 | 72601 | common | rerank_only |
| ` ` | 72601 | 1.000000 | 72601 | common | rerank_only |
| `documentation` | 12615 | 0.173758 | 12615 | common | rerank_only |
| `binding` | 9619 | 0.132491 | 9619 | common | rerank_only |

### 55. arm,coresight tpiu documentation devicetree bindings arm

- raw_postings_matches: 72,601
- initial_postings_matches_after_policy: 2,000
- reranker_in: 50
- hydrated: 5
- time_ms: retrieval=1.8741, rerank=0.3981, hydrate=0.0217, e2e=2.2939
- hit_rank: 1

| token | df | df ratio | postings length | token type | action |
|---|---:|---:|---:|---|---|
| `arm` | 6315 | 0.086982 | 6315 | identifier/path | generate |
| `,` | 67976 | 0.936296 | 67976 | common | rerank_only |
| `CTRL:BEGIN_WORD` | 72601 | 1.000000 | 72601 | common | rerank_only |
| `CTRL:END_WORD` | 72601 | 1.000000 | 72601 | common | rerank_only |
| ` ` | 72601 | 1.000000 | 72601 | common | rerank_only |
| `documentation` | 12615 | 0.173758 | 12615 | common | rerank_only |
| `binding` | 9619 | 0.132491 | 9619 | common | rerank_only |

### 56. arm,corstone1000 documentation devicetree bindings arm

- raw_postings_matches: 72,601
- initial_postings_matches_after_policy: 2,000
- reranker_in: 50
- hydrated: 5
- time_ms: retrieval=1.8240, rerank=0.3000, hydrate=0.6088, e2e=2.7328
- hit_rank: 1

| token | df | df ratio | postings length | token type | action |
|---|---:|---:|---:|---|---|
| `arm` | 6315 | 0.086982 | 6315 | identifier/path | generate |
| `,` | 67976 | 0.936296 | 67976 | common | rerank_only |
| `CTRL:BEGIN_WORD` | 72601 | 1.000000 | 72601 | common | rerank_only |
| `CTRL:END_WORD` | 72601 | 1.000000 | 72601 | common | rerank_only |
| `1` | 66053 | 0.909808 | 66053 | common | rerank_only |
| `CTRL:NUM_SEP` | 60437 | 0.832454 | 60437 | common | rerank_only |
| `0` | 71675 | 0.987245 | 71675 | common | rerank_only |
| ` ` | 72601 | 1.000000 | 72601 | common | rerank_only |
| `documentation` | 12615 | 0.173758 | 12615 | common | rerank_only |
| `binding` | 9619 | 0.132491 | 9619 | common | rerank_only |

### 57. arm,embedded trace extension documentation devicetree bindings arm

- raw_postings_matches: 72,601
- initial_postings_matches_after_policy: 2,000
- reranker_in: 50
- hydrated: 5
- time_ms: retrieval=2.3350, rerank=0.3387, hydrate=1.7473, e2e=4.4210
- hit_rank: 1

| token | df | df ratio | postings length | token type | action |
|---|---:|---:|---:|---|---|
| `arm` | 6315 | 0.086982 | 6315 | identifier/path | generate |
| `,` | 67976 | 0.936296 | 67976 | common | rerank_only |
| `CTRL:BEGIN_WORD` | 72601 | 1.000000 | 72601 | common | rerank_only |
| `CTRL:END_WORD` | 72601 | 1.000000 | 72601 | common | rerank_only |
| ` ` | 72601 | 1.000000 | 72601 | common | rerank_only |
| `trace` | 5473 | 0.075385 | 5473 | identifier/path | generate |
| `extension` | 2009 | 0.027672 | 2009 | rare | generate |
| `documentation` | 12615 | 0.173758 | 12615 | common | rerank_only |
| `binding` | 9619 | 0.132491 | 9619 | common | rerank_only |

### 58. arm,integrator documentation devicetree bindings arm

- raw_postings_matches: 72,601
- initial_postings_matches_after_policy: 2,000
- reranker_in: 50
- hydrated: 5
- time_ms: retrieval=1.7948, rerank=0.3185, hydrate=1.5980, e2e=3.7113
- hit_rank: 1

| token | df | df ratio | postings length | token type | action |
|---|---:|---:|---:|---|---|
| `arm` | 6315 | 0.086982 | 6315 | identifier/path | generate |
| `,` | 67976 | 0.936296 | 67976 | common | rerank_only |
| `integrator` | 51 | 0.000702 | 51 | rare | generate |
| ` ` | 72601 | 1.000000 | 72601 | common | rerank_only |
| `documentation` | 12615 | 0.173758 | 12615 | common | rerank_only |
| `CTRL:BEGIN_WORD` | 72601 | 1.000000 | 72601 | common | rerank_only |
| `CTRL:END_WORD` | 72601 | 1.000000 | 72601 | common | rerank_only |
| `binding` | 9619 | 0.132491 | 9619 | common | rerank_only |

### 59. arm,juno fpga apb regs documentation devicetree bindings arm

- raw_postings_matches: 72,601
- initial_postings_matches_after_policy: 2,000
- reranker_in: 50
- hydrated: 5
- time_ms: retrieval=1.9657, rerank=0.3395, hydrate=2.9013, e2e=5.2065
- hit_rank: 1

| token | df | df ratio | postings length | token type | action |
|---|---:|---:|---:|---|---|
| `arm` | 6315 | 0.086982 | 6315 | identifier/path | generate |
| `,` | 67976 | 0.936296 | 67976 | common | rerank_only |
| `juno` | 9 | 0.000124 | 9 | rare | generate |
| ` ` | 72601 | 1.000000 | 72601 | common | rerank_only |
| `CTRL:BEGIN_WORD` | 72601 | 1.000000 | 72601 | common | rerank_only |
| `CTRL:END_WORD` | 72601 | 1.000000 | 72601 | common | rerank_only |
| `documentation` | 12615 | 0.173758 | 12615 | common | rerank_only |
| `reg` | 27314 | 0.376221 | 27314 | common | rerank_only |
| `binding` | 9619 | 0.132491 | 9619 | common | rerank_only |

### 60. arm,morello documentation devicetree bindings arm

- raw_postings_matches: 72,601
- initial_postings_matches_after_policy: 2,000
- reranker_in: 50
- hydrated: 5
- time_ms: retrieval=1.7612, rerank=0.3002, hydrate=0.0185, e2e=2.0799
- hit_rank: 1

| token | df | df ratio | postings length | token type | action |
|---|---:|---:|---:|---|---|
| `arm` | 6315 | 0.086982 | 6315 | identifier/path | generate |
| `,` | 67976 | 0.936296 | 67976 | common | rerank_only |
| `morello` | 1 | 0.000014 | 1 | rare | generate |
| ` ` | 72601 | 1.000000 | 72601 | common | rerank_only |
| `documentation` | 12615 | 0.173758 | 12615 | common | rerank_only |
| `CTRL:BEGIN_WORD` | 72601 | 1.000000 | 72601 | common | rerank_only |
| `CTRL:END_WORD` | 72601 | 1.000000 | 72601 | common | rerank_only |
| `binding` | 9619 | 0.132491 | 9619 | common | rerank_only |

### 61. arm,realview documentation devicetree bindings arm

- raw_postings_matches: 72,601
- initial_postings_matches_after_policy: 2,000
- reranker_in: 50
- hydrated: 5
- time_ms: retrieval=1.7823, rerank=0.2895, hydrate=0.0179, e2e=2.0897
- hit_rank: 1

| token | df | df ratio | postings length | token type | action |
|---|---:|---:|---:|---|---|
| `arm` | 6315 | 0.086982 | 6315 | identifier/path | generate |
| `,` | 67976 | 0.936296 | 67976 | common | rerank_only |
| `CTRL:BEGIN_WORD` | 72601 | 1.000000 | 72601 | common | rerank_only |
| `CTRL:END_WORD` | 72601 | 1.000000 | 72601 | common | rerank_only |
| ` ` | 72601 | 1.000000 | 72601 | common | rerank_only |
| `documentation` | 12615 | 0.173758 | 12615 | common | rerank_only |
| `binding` | 9619 | 0.132491 | 9619 | common | rerank_only |

### 62. arm,scu documentation devicetree bindings arm

- raw_postings_matches: 72,601
- initial_postings_matches_after_policy: 2,000
- reranker_in: 50
- hydrated: 5
- time_ms: retrieval=1.7544, rerank=0.2881, hydrate=0.0185, e2e=2.0610
- hit_rank: 1

| token | df | df ratio | postings length | token type | action |
|---|---:|---:|---:|---|---|
| `arm` | 6315 | 0.086982 | 6315 | identifier/path | generate |
| `,` | 67976 | 0.936296 | 67976 | common | rerank_only |
| `CTRL:BEGIN_WORD` | 72601 | 1.000000 | 72601 | common | rerank_only |
| `CTRL:END_WORD` | 72601 | 1.000000 | 72601 | common | rerank_only |
| ` ` | 72601 | 1.000000 | 72601 | common | rerank_only |
| `documentation` | 12615 | 0.173758 | 12615 | common | rerank_only |
| `binding` | 9619 | 0.132491 | 9619 | common | rerank_only |

### 63. arm,trace buffer extension documentation devicetree bindings arm

- raw_postings_matches: 72,601
- initial_postings_matches_after_policy: 2,000
- reranker_in: 50
- hydrated: 5
- time_ms: retrieval=2.3289, rerank=0.3577, hydrate=0.3651, e2e=3.0517
- hit_rank: 1

| token | df | df ratio | postings length | token type | action |
|---|---:|---:|---:|---|---|
| `arm` | 6315 | 0.086982 | 6315 | identifier/path | generate |
| `,` | 67976 | 0.936296 | 67976 | common | rerank_only |
| `trace` | 5473 | 0.075385 | 5473 | identifier/path | generate |
| ` ` | 72601 | 1.000000 | 72601 | common | rerank_only |
| `buffer` | 14739 | 0.203014 | 14739 | common | rerank_only |
| `extension` | 2009 | 0.027672 | 2009 | rare | generate |
| `documentation` | 12615 | 0.173758 | 12615 | common | rerank_only |
| `CTRL:BEGIN_WORD` | 72601 | 1.000000 | 72601 | common | rerank_only |
| `CTRL:END_WORD` | 72601 | 1.000000 | 72601 | common | rerank_only |
| `binding` | 9619 | 0.132491 | 9619 | common | rerank_only |

### 64. arm,versatile sysreg documentation devicetree bindings arm

- raw_postings_matches: 72,601
- initial_postings_matches_after_policy: 2,000
- reranker_in: 50
- hydrated: 5
- time_ms: retrieval=1.9229, rerank=0.3474, hydrate=1.5428, e2e=3.8131
- hit_rank: 1

| token | df | df ratio | postings length | token type | action |
|---|---:|---:|---:|---|---|
| `arm` | 6315 | 0.086982 | 6315 | identifier/path | generate |
| `,` | 67976 | 0.936296 | 67976 | common | rerank_only |
| `versatile` | 97 | 0.001336 | 97 | rare | generate |
| ` ` | 72601 | 1.000000 | 72601 | common | rerank_only |
| `CTRL:BEGIN_WORD` | 72601 | 1.000000 | 72601 | common | rerank_only |
| `CTRL:END_WORD` | 72601 | 1.000000 | 72601 | common | rerank_only |
| `documentation` | 12615 | 0.173758 | 12615 | common | rerank_only |
| `binding` | 9619 | 0.132491 | 9619 | common | rerank_only |

### 65. arm,versatile documentation devicetree bindings arm

- raw_postings_matches: 72,601
- initial_postings_matches_after_policy: 2,000
- reranker_in: 50
- hydrated: 5
- time_ms: retrieval=1.8110, rerank=0.3288, hydrate=0.3277, e2e=2.4675
- hit_rank: 1

| token | df | df ratio | postings length | token type | action |
|---|---:|---:|---:|---|---|
| `arm` | 6315 | 0.086982 | 6315 | identifier/path | generate |
| `,` | 67976 | 0.936296 | 67976 | common | rerank_only |
| `versatile` | 97 | 0.001336 | 97 | rare | generate |
| ` ` | 72601 | 1.000000 | 72601 | common | rerank_only |
| `documentation` | 12615 | 0.173758 | 12615 | common | rerank_only |
| `CTRL:BEGIN_WORD` | 72601 | 1.000000 | 72601 | common | rerank_only |
| `CTRL:END_WORD` | 72601 | 1.000000 | 72601 | common | rerank_only |
| `binding` | 9619 | 0.132491 | 9619 | common | rerank_only |

### 66. arm,vexpress juno documentation devicetree bindings arm

- raw_postings_matches: 72,601
- initial_postings_matches_after_policy: 2,000
- reranker_in: 50
- hydrated: 5
- time_ms: retrieval=1.8545, rerank=0.4009, hydrate=0.0282, e2e=2.2836
- hit_rank: 1

| token | df | df ratio | postings length | token type | action |
|---|---:|---:|---:|---|---|
| `arm` | 6315 | 0.086982 | 6315 | identifier/path | generate |
| `,` | 67976 | 0.936296 | 67976 | common | rerank_only |
| `CTRL:BEGIN_WORD` | 72601 | 1.000000 | 72601 | common | rerank_only |
| `CTRL:END_WORD` | 72601 | 1.000000 | 72601 | common | rerank_only |
| ` ` | 72601 | 1.000000 | 72601 | common | rerank_only |
| `juno` | 9 | 0.000124 | 9 | rare | generate |
| `documentation` | 12615 | 0.173758 | 12615 | common | rerank_only |
| `binding` | 9619 | 0.132491 | 9619 | common | rerank_only |

### 67. arm,vexpress scc documentation devicetree bindings arm

- raw_postings_matches: 72,601
- initial_postings_matches_after_policy: 2,000
- reranker_in: 50
- hydrated: 5
- time_ms: retrieval=1.9420, rerank=0.3399, hydrate=0.0207, e2e=2.3026
- hit_rank: 1

| token | df | df ratio | postings length | token type | action |
|---|---:|---:|---:|---|---|
| `arm` | 6315 | 0.086982 | 6315 | identifier/path | generate |
| `,` | 67976 | 0.936296 | 67976 | common | rerank_only |
| `CTRL:BEGIN_WORD` | 72601 | 1.000000 | 72601 | common | rerank_only |
| `CTRL:END_WORD` | 72601 | 1.000000 | 72601 | common | rerank_only |
| ` ` | 72601 | 1.000000 | 72601 | common | rerank_only |
| `documentation` | 12615 | 0.173758 | 12615 | common | rerank_only |
| `binding` | 9619 | 0.132491 | 9619 | common | rerank_only |

### 68. aspeed,sbc documentation devicetree bindings arm aspeed

- raw_postings_matches: 72,601
- initial_postings_matches_after_policy: 2,000
- reranker_in: 50
- hydrated: 5
- time_ms: retrieval=1.9051, rerank=0.3048, hydrate=0.0191, e2e=2.2290
- hit_rank: -

| token | df | df ratio | postings length | token type | action |
|---|---:|---:|---:|---|---|
| `CTRL:BEGIN_WORD` | 72601 | 1.000000 | 72601 | common | rerank_only |
| `CTRL:END_WORD` | 72601 | 1.000000 | 72601 | common | rerank_only |
| `,` | 67976 | 0.936296 | 67976 | common | rerank_only |
| ` ` | 72601 | 1.000000 | 72601 | common | rerank_only |
| `documentation` | 12615 | 0.173758 | 12615 | common | rerank_only |
| `arm` | 6315 | 0.086982 | 6315 | identifier/path | generate |
| `binding` | 9619 | 0.132491 | 9619 | common | rerank_only |

### 69. aspeed documentation devicetree bindings arm aspeed

- raw_postings_matches: 72,601
- initial_postings_matches_after_policy: 2,000
- reranker_in: 50
- hydrated: 5
- time_ms: retrieval=1.8385, rerank=0.4886, hydrate=0.0267, e2e=2.3538
- hit_rank: -

| token | df | df ratio | postings length | token type | action |
|---|---:|---:|---:|---|---|
| `CTRL:BEGIN_WORD` | 72601 | 1.000000 | 72601 | common | rerank_only |
| `CTRL:END_WORD` | 72601 | 1.000000 | 72601 | common | rerank_only |
| ` ` | 72601 | 1.000000 | 72601 | common | rerank_only |
| `documentation` | 12615 | 0.173758 | 12615 | common | rerank_only |
| `arm` | 6315 | 0.086982 | 6315 | identifier/path | generate |
| `binding` | 9619 | 0.132491 | 9619 | common | rerank_only |

### 70. atmel,at91rm9200 sdramc documentation devicetree bindings arm

- raw_postings_matches: 72,601
- initial_postings_matches_after_policy: 2,000
- reranker_in: 50
- hydrated: 5
- time_ms: retrieval=2.0473, rerank=0.3562, hydrate=2.5699, e2e=4.9734
- hit_rank: 1

| token | df | df ratio | postings length | token type | action |
|---|---:|---:|---:|---|---|
| `CTRL:BEGIN_WORD` | 72601 | 1.000000 | 72601 | common | rerank_only |
| `CTRL:END_WORD` | 72601 | 1.000000 | 72601 | common | rerank_only |
| `,` | 67976 | 0.936296 | 67976 | common | rerank_only |
| `at` | 18820 | 0.259225 | 18820 | common | rerank_only |
| `9` | 37927 | 0.522403 | 37927 | common | rerank_only |
| `CTRL:NUM_SEP` | 60437 | 0.832454 | 60437 | common | rerank_only |
| `1` | 66053 | 0.909808 | 66053 | common | rerank_only |
| `rm` | 1545 | 0.021281 | 1545 | rare | generate |
| `2` | 71667 | 0.987135 | 71667 | common | rerank_only |
| `0` | 71675 | 0.987245 | 71675 | common | rerank_only |
| ` ` | 72601 | 1.000000 | 72601 | common | rerank_only |
| `documentation` | 12615 | 0.173758 | 12615 | common | rerank_only |
| `arm` | 6315 | 0.086982 | 6315 | identifier/path | generate |
| `binding` | 9619 | 0.132491 | 9619 | common | rerank_only |

### 71. atmel,at91rm9200 st documentation devicetree bindings arm

- raw_postings_matches: 72,601
- initial_postings_matches_after_policy: 2,000
- reranker_in: 50
- hydrated: 5
- time_ms: retrieval=2.5034, rerank=0.3218, hydrate=5.2147, e2e=8.0399
- hit_rank: 1

| token | df | df ratio | postings length | token type | action |
|---|---:|---:|---:|---|---|
| `CTRL:BEGIN_WORD` | 72601 | 1.000000 | 72601 | common | rerank_only |
| `CTRL:END_WORD` | 72601 | 1.000000 | 72601 | common | rerank_only |
| `,` | 67976 | 0.936296 | 67976 | common | rerank_only |
| `at` | 18820 | 0.259225 | 18820 | common | rerank_only |
| `9` | 37927 | 0.522403 | 37927 | common | rerank_only |
| `CTRL:NUM_SEP` | 60437 | 0.832454 | 60437 | common | rerank_only |
| `1` | 66053 | 0.909808 | 66053 | common | rerank_only |
| `rm` | 1545 | 0.021281 | 1545 | rare | generate |
| `2` | 71667 | 0.987135 | 71667 | common | rerank_only |
| `0` | 71675 | 0.987245 | 71675 | common | rerank_only |
| ` ` | 72601 | 1.000000 | 72601 | common | rerank_only |
| `st` | 5319 | 0.073263 | 5319 | identifier/path | generate |
| `documentation` | 12615 | 0.173758 | 12615 | common | rerank_only |
| `arm` | 6315 | 0.086982 | 6315 | identifier/path | generate |
| `binding` | 9619 | 0.132491 | 9619 | common | rerank_only |

### 72. atmel,at91sam9260 pit documentation devicetree bindings arm

- raw_postings_matches: 72,601
- initial_postings_matches_after_policy: 2,000
- reranker_in: 50
- hydrated: 5
- time_ms: retrieval=2.0004, rerank=0.3276, hydrate=1.4342, e2e=3.7622
- hit_rank: 1

| token | df | df ratio | postings length | token type | action |
|---|---:|---:|---:|---|---|
| `CTRL:BEGIN_WORD` | 72601 | 1.000000 | 72601 | common | rerank_only |
| `CTRL:END_WORD` | 72601 | 1.000000 | 72601 | common | rerank_only |
| `,` | 67976 | 0.936296 | 67976 | common | rerank_only |
| `at` | 18820 | 0.259225 | 18820 | common | rerank_only |
| `9` | 37927 | 0.522403 | 37927 | common | rerank_only |
| `CTRL:NUM_SEP` | 60437 | 0.832454 | 60437 | common | rerank_only |
| `1` | 66053 | 0.909808 | 66053 | common | rerank_only |
| `sam` | 535 | 0.007369 | 535 | rare | generate |
| `2` | 71667 | 0.987135 | 71667 | common | rerank_only |
| `6` | 54632 | 0.752497 | 54632 | common | rerank_only |
| `0` | 71675 | 0.987245 | 71675 | common | rerank_only |
| ` ` | 72601 | 1.000000 | 72601 | common | rerank_only |
| `pit` | 109 | 0.001501 | 109 | rare | generate |
| `documentation` | 12615 | 0.173758 | 12615 | common | rerank_only |
| `arm` | 6315 | 0.086982 | 6315 | identifier/path | generate |
| `binding` | 9619 | 0.132491 | 9619 | common | rerank_only |

### 73. atmel,sama5d2 secumod documentation devicetree bindings arm

- raw_postings_matches: 72,601
- initial_postings_matches_after_policy: 2,000
- reranker_in: 50
- hydrated: 5
- time_ms: retrieval=2.0794, rerank=0.3498, hydrate=0.0227, e2e=2.4519
- hit_rank: -

| token | df | df ratio | postings length | token type | action |
|---|---:|---:|---:|---|---|
| `CTRL:BEGIN_WORD` | 72601 | 1.000000 | 72601 | common | rerank_only |
| `CTRL:END_WORD` | 72601 | 1.000000 | 72601 | common | rerank_only |
| `,` | 67976 | 0.936296 | 67976 | common | rerank_only |
| `5` | 47367 | 0.652429 | 47367 | common | rerank_only |
| `2` | 71667 | 0.987135 | 71667 | common | rerank_only |
| ` ` | 72601 | 1.000000 | 72601 | common | rerank_only |
| `documentation` | 12615 | 0.173758 | 12615 | common | rerank_only |
| `arm` | 6315 | 0.086982 | 6315 | identifier/path | generate |
| `binding` | 9619 | 0.132491 | 9619 | common | rerank_only |

### 74. atmel at91 documentation devicetree bindings arm

- raw_postings_matches: 72,601
- initial_postings_matches_after_policy: 2,000
- reranker_in: 50
- hydrated: 5
- time_ms: retrieval=1.8734, rerank=0.3032, hydrate=0.0191, e2e=2.1957
- hit_rank: -

| token | df | df ratio | postings length | token type | action |
|---|---:|---:|---:|---|---|
| `CTRL:BEGIN_WORD` | 72601 | 1.000000 | 72601 | common | rerank_only |
| `CTRL:END_WORD` | 72601 | 1.000000 | 72601 | common | rerank_only |
| ` ` | 72601 | 1.000000 | 72601 | common | rerank_only |
| `at` | 18820 | 0.259225 | 18820 | common | rerank_only |
| `9` | 37927 | 0.522403 | 37927 | common | rerank_only |
| `CTRL:NUM_SEP` | 60437 | 0.832454 | 60437 | common | rerank_only |
| `1` | 66053 | 0.909808 | 66053 | common | rerank_only |
| `documentation` | 12615 | 0.173758 | 12615 | common | rerank_only |
| `arm` | 6315 | 0.086982 | 6315 | identifier/path | generate |
| `binding` | 9619 | 0.132491 | 9619 | common | rerank_only |

### 75. axiado documentation devicetree bindings arm

- raw_postings_matches: 72,601
- initial_postings_matches_after_policy: 2,000
- reranker_in: 50
- hydrated: 5
- time_ms: retrieval=1.7955, rerank=0.2998, hydrate=0.0179, e2e=2.1132
- hit_rank: -

| token | df | df ratio | postings length | token type | action |
|---|---:|---:|---:|---|---|
| `CTRL:BEGIN_WORD` | 72601 | 1.000000 | 72601 | common | rerank_only |
| `CTRL:END_WORD` | 72601 | 1.000000 | 72601 | common | rerank_only |
| ` ` | 72601 | 1.000000 | 72601 | common | rerank_only |
| `documentation` | 12615 | 0.173758 | 12615 | common | rerank_only |
| `arm` | 6315 | 0.086982 | 6315 | identifier/path | generate |
| `binding` | 9619 | 0.132491 | 9619 | common | rerank_only |

### 76. axis documentation devicetree bindings arm

- raw_postings_matches: 72,601
- initial_postings_matches_after_policy: 2,000
- reranker_in: 50
- hydrated: 5
- time_ms: retrieval=1.8368, rerank=0.3130, hydrate=3.6888, e2e=5.8386
- hit_rank: 1

| token | df | df ratio | postings length | token type | action |
|---|---:|---:|---:|---|---|
| `axis` | 490 | 0.006749 | 490 | rare | generate |
| ` ` | 72601 | 1.000000 | 72601 | common | rerank_only |
| `documentation` | 12615 | 0.173758 | 12615 | common | rerank_only |
| `CTRL:BEGIN_WORD` | 72601 | 1.000000 | 72601 | common | rerank_only |
| `CTRL:END_WORD` | 72601 | 1.000000 | 72601 | common | rerank_only |
| `arm` | 6315 | 0.086982 | 6315 | identifier/path | generate |
| `binding` | 9619 | 0.132491 | 9619 | common | rerank_only |

### 77. axxia documentation devicetree bindings arm

- raw_postings_matches: 72,601
- initial_postings_matches_after_policy: 2,000
- reranker_in: 50
- hydrated: 5
- time_ms: retrieval=1.8778, rerank=0.2972, hydrate=0.0201, e2e=2.1951
- hit_rank: -

| token | df | df ratio | postings length | token type | action |
|---|---:|---:|---:|---|---|
| `CTRL:BEGIN_WORD` | 72601 | 1.000000 | 72601 | common | rerank_only |
| `CTRL:END_WORD` | 72601 | 1.000000 | 72601 | common | rerank_only |
| ` ` | 72601 | 1.000000 | 72601 | common | rerank_only |
| `documentation` | 12615 | 0.173758 | 12615 | common | rerank_only |
| `arm` | 6315 | 0.086982 | 6315 | identifier/path | generate |
| `binding` | 9619 | 0.132491 | 9619 | common | rerank_only |

### 78. bcm2835 documentation devicetree bindings arm bcm

- raw_postings_matches: 72,601
- initial_postings_matches_after_policy: 2,000
- reranker_in: 50
- hydrated: 5
- time_ms: retrieval=1.7968, rerank=0.3069, hydrate=1.0527, e2e=3.1564
- hit_rank: -

| token | df | df ratio | postings length | token type | action |
|---|---:|---:|---:|---|---|
| `CTRL:BEGIN_WORD` | 72601 | 1.000000 | 72601 | common | rerank_only |
| `CTRL:END_WORD` | 72601 | 1.000000 | 72601 | common | rerank_only |
| `2` | 71667 | 0.987135 | 71667 | common | rerank_only |
| `CTRL:NUM_SEP` | 60437 | 0.832454 | 60437 | common | rerank_only |
| `8` | 51787 | 0.713310 | 51787 | common | rerank_only |
| `3` | 58661 | 0.807992 | 58661 | common | rerank_only |
| `5` | 47367 | 0.652429 | 47367 | common | rerank_only |
| ` ` | 72601 | 1.000000 | 72601 | common | rerank_only |
| `documentation` | 12615 | 0.173758 | 12615 | common | rerank_only |
| `arm` | 6315 | 0.086982 | 6315 | identifier/path | generate |
| `binding` | 9619 | 0.132491 | 9619 | common | rerank_only |

### 79. brcm,bcm11351 documentation devicetree bindings arm bcm

- raw_postings_matches: 72,601
- initial_postings_matches_after_policy: 2,000
- reranker_in: 50
- hydrated: 5
- time_ms: retrieval=1.8256, rerank=0.3126, hydrate=0.0185, e2e=2.1567
- hit_rank: -

| token | df | df ratio | postings length | token type | action |
|---|---:|---:|---:|---|---|
| `CTRL:BEGIN_WORD` | 72601 | 1.000000 | 72601 | common | rerank_only |
| `CTRL:END_WORD` | 72601 | 1.000000 | 72601 | common | rerank_only |
| `,` | 67976 | 0.936296 | 67976 | common | rerank_only |
| `1` | 66053 | 0.909808 | 66053 | common | rerank_only |
| `CTRL:NUM_SEP` | 60437 | 0.832454 | 60437 | common | rerank_only |
| `3` | 58661 | 0.807992 | 58661 | common | rerank_only |
| `5` | 47367 | 0.652429 | 47367 | common | rerank_only |
| ` ` | 72601 | 1.000000 | 72601 | common | rerank_only |
| `documentation` | 12615 | 0.173758 | 12615 | common | rerank_only |
| `arm` | 6315 | 0.086982 | 6315 | identifier/path | generate |
| `binding` | 9619 | 0.132491 | 9619 | common | rerank_only |

### 80. brcm,bcm21664 documentation devicetree bindings arm bcm

- raw_postings_matches: 72,601
- initial_postings_matches_after_policy: 2,000
- reranker_in: 50
- hydrated: 5
- time_ms: retrieval=1.8352, rerank=0.3119, hydrate=0.0187, e2e=2.1658
- hit_rank: -

| token | df | df ratio | postings length | token type | action |
|---|---:|---:|---:|---|---|
| `CTRL:BEGIN_WORD` | 72601 | 1.000000 | 72601 | common | rerank_only |
| `CTRL:END_WORD` | 72601 | 1.000000 | 72601 | common | rerank_only |
| `,` | 67976 | 0.936296 | 67976 | common | rerank_only |
| `2` | 71667 | 0.987135 | 71667 | common | rerank_only |
| `CTRL:NUM_SEP` | 60437 | 0.832454 | 60437 | common | rerank_only |
| `1` | 66053 | 0.909808 | 66053 | common | rerank_only |
| `6` | 54632 | 0.752497 | 54632 | common | rerank_only |
| `4` | 56023 | 0.771656 | 56023 | common | rerank_only |
| ` ` | 72601 | 1.000000 | 72601 | common | rerank_only |
| `documentation` | 12615 | 0.173758 | 12615 | common | rerank_only |
| `arm` | 6315 | 0.086982 | 6315 | identifier/path | generate |
| `binding` | 9619 | 0.132491 | 9619 | common | rerank_only |
