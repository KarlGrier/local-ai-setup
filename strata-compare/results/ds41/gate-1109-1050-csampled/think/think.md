# C's sampled test, thinking-on arm (INFO only, never part of the verdict): **INSIDE the noise bound**

Rule: think-rule.txt (sampled.py THINK_RULE). Folder: `/home/USER/ai-speed-testing/strata-compare/results/ds41/gate-1109-1050-csampled/think`.

- D2(TX, TR1) 11.285 <= c 11.345 (INFO only; the least favourable top-1 shift seen with 80% is 0.0374)
- d2_x_r1: 11.2848
- bound: 11.3449
- d2_r1_scorer: 11.085
- mde_top1: 0.03742

| arm | samples (valid) | sampled tokens | wrap-up tokens left out | top-1 rate / expected | drafted share | acceptance | D2 vs scorer | problems |
|---|---|---|---|---|---|---|---|---|
| TR1 | 4 (4) | 1980 | 68 | 0.80505 / 0.82609 | 0.0 | None | 11.085 | - |
| TX | 4 (4) | 1980 | 68 | 0.85354 / 0.85241 | 0.46 | 0.8355 | 3.594 | - |
