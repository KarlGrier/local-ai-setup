# C's sampled-distribution test: **PASS**

Rule: rule.txt (sampled.py). Folder: `/home/USER/ai-speed-testing/strata-compare/results/ds41/gate-1109-1050-csampled`.

- D2(X, R1) 2.440 <= the noise bound 11.345 (band >= it whatever R2 gives)
- d2_x_r1: 2.4403
- band: 11.3449
- d2_r1_scorer: 6.872
- mde_top1: 0.01662

| arm | samples (valid) | tokens | top-1 rate / expected | drafted share | acceptance | D2 vs scorer | problems |
|---|---|---|---|---|---|---|---|
| R1 | 16 (16) | 8192 | 0.87622 / 0.87677 | 0.0 | None | 6.872 | - |
| X | 16 (16) | 8192 | 0.86877 / 0.87551 | 0.4818 | 0.8351 | 9.469 | - |
