# B (the 5080 alone) vs A (daily): teacher-forced KL check

Verdict: **FAIL**

- cand-B vs base (A): 2040 positions, KL mean 0.00717, p90 0.01359, max 1.535, KL>1 1, top-1 agree 2002
- R1-chunk4096 vs base (A): 2040 positions, KL mean 0.00667, p90 0.01259, max 1.386, KL>1 1, top-1 agree 2009
- R2-cpu-share vs base (A): 2040 positions, KL mean 0.00722, p90 0.01226, max 2.003, KL>1 1, top-1 agree 2006
- changed top-1 picks [38, 31, 34] (B, R1, R2; bound 37.4); text NLL [0.665, 0.6614, 0.66, 0.658] (B, R1, R2, A; B above A 0.007, bound 0.0037)
- ok   KL mean <= 1.10 x the larger reference
- ok   KL p90 <= 1.10 x the larger reference
- ok   KL>1 count <= the worse reference's + 1
- FAIL changed top-1 picks <= 1.10 x the larger reference's
- FAIL text NLL above the base's <= 1.10 x the larger reference's distance

Prompt-skip engine lines (8 segments each): {"base": 8, "cand-B": 8, "R1-chunk4096": 8, "R2-cpu-share": 8}
B's one-device layer-major prompt path (DS4_FLOW_STATS lines "(layer-major, N chunks"): 8 of 8 segments

Run times: base: rc 0, 317 s, lowest MemAvailable 28.5 GB (8 engine runs, one segment each); cand-B: rc 0, 275 s, lowest MemAvailable 28.4 GB (8 engine runs, one segment each); R1-chunk4096: rc 0, 324 s, lowest MemAvailable 30.3 GB (8 engine runs, one segment each); R2-cpu-share: rc 0, 322 s, lowest MemAvailable 28.8 GB (8 engine runs, one segment each)
- report only, A vs stock v0.2.6 (teacher/final-base, its stored references): PASS; 2040 positions, KL mean 0.00660, p90 0.01265, max 1.584, KL>1 1, top-1 agree 2011; changed picks [29, 30, 29]
- report only, B vs stock v0.2.6 (teacher/final-base, its stored references): PASS; 2040 positions, KL mean 0.00544, p90 0.01392, max 0.311, KL>1 0, top-1 agree 2018; changed picks [22, 30, 29]
