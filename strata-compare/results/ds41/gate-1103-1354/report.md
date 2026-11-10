# DeepSeek V4.1 Flash gate: A (daily) vs B (the 5080 alone) vs C (+ Lucebox DSpark on the 4060 Ti)

Run folder: `/home/USER/ai-speed-testing/strata-compare/results/ds41/gate-1103-1354`. Profile snapshot: every arm started from a fresh copy of the gap's `logs/ds41/daily-profile.bin`.

## 1. Speed (3 passes; spread = half the range, % of the mean)

| arm | VRAM experts (per card) | decode tok/s (spread; pass means) | P4K (spread) | P20K (spread) | P20K SSD GB | SSD GB / token | lowest MemAvailable | peak RSS GB | peak VRAM MiB 5080 / 4060 Ti | experts / word | stops |
|---|---|---|---|---|---|---|---|---|---|---|---|
| A | 451 (CUDA0 [0,7]) + 857 (CUDA1 [8,39]) | 28.05 (0.28 %; [27.95, 28.11, 28.09]) | 345.8 (4.66 %) | 692.4 (0.94 %) | 112.7 | 0.0777 | 17.1 | 68.8 | [15422, 7375] | 6 | - |
| B | 711 (CUDA0 [0,39]) | 28.12 (0.63 %; [27.89, 28.25, 28.23]) | 462.5 (4.06 %) | 732.2 (0.79 %) | 63.4 | 0.0749 | 16.4 | 70.1 | [15438, 15] | 6 | - |
| C0 | not run | | | | | | | | | | |
| C1 | not run | | | | | | | | | | |
| C2 | not run | | | | | | | | | | |

Against (compare.py's rule: noise = the larger spread; decode counts at >= 3 % beyond it, prompts at >= 5 %):

- B vs A: decode 0.25 % (noise 0.63), P4K 33.75 % (4.66), P20K 5.75 % (0.94) -> prompt gain beyond noise (P4K), decode not lower beyond noise

## 2. Long prompts (own arms: a warm-up, one P20K, then ~64K and ~97K; MemAvailable every 0.5 s)

| arm | prompt | tokens | read tok/s (engine) | TTFT s | decode at length tok/s | MemAvailable before / lowest / after GB | dip GB | engine RSS before / after GB | vs 14 / 13 / 12 GB |
|---|---|---|---|---|---|---|---|---|---|
| AL | not run | | | | | | | | |
| BL | not run | | | | | | | | |

AL / BL ran with the daily services' memory load ("everything up", as ctx128.py's 97K run: SearXNG 8889/8890 up, ballast.py holding LDR's 3.54 GiB and SearXNG 8889's 1.74 GiB less what they held), so these lows are the real ones (A's 10-27 97K run with everything up: lowest 18.9 GB). Services (svcmem.py):

## 3. C's exactness: greedy, placement frozen (--no-expert-cache)

- **C stopped: the conversion failed (/home/USER/ai-speed-testing/strata-compare/results/ds41/gate-1103-1354/prep/convert.log)**
- not run (C0f did not run)

## 4. The drafter's acceptance

| run | requests | drafts kept / offered | kept % | position 1 kept % | positions 1-2 kept % | verify rounds | tokens a verify round | if every round offered k drafts (k = 1 / 2) |
|---|---|---|---|---|---|---|---|---|
| Q8_0 1017: 10-24 dsp70 (NOTES.md:8401; drafter on the 5080, v0.2.4) | all requests (block 5) | 8762 / 11399 | 76.9 | 81.7 | 83.4 | 4567 | 2.92 | 1.82 / 2.52 |
| Q8_0 1017: 10-25 dspark4060 (drafter on the 4060 Ti, v0.2.4) | all requests (block 5) | 4744 / 6160 | 77.0 | 81.7 | 83.5 | 2369 | 3.0 | 1.82 / 2.52 |
| Q8_0 1017: 10-25 conf-dspark4060 (its confirm run) | all requests (block 5) | 14271 / 18503 | 77.1 | 81.0 | 83.0 | 7354 | 2.94 | 1.81 / 2.51 |

The 77 % (NOTES.md:8401) is drafts kept / offered over every request of that arm, up to 5 drafts a round. C1 keeps at most position 1, C2 positions 1-2: compare their "kept %" with the reference's position-matched columns. Lucebox's drafter was converted from DeepSeek's V4.1 Flash checkpoint, the trunk here is the 1017 revision: a lower position-1 rate than the Q8_0 1017 drafter's points at that mismatch.

## 5. B vs A, teacher-forced KL (the round's skipcheck form)

- verdict: **FAIL**
  - cand-B vs A: KL mean 0.00717, p90 0.01359, max 1.535, KL>1 1, top-1 agree 2002 of 2040
  - R1-chunk4096 vs A: KL mean 0.00667, p90 0.01259, max 1.386, KL>1 1, top-1 agree 2009 of 2040
  - R2-cpu-share vs A: KL mean 0.00722, p90 0.01226, max 2.003, KL>1 1, top-1 agree 2006 of 2040
  - changed top-1 picks [38, 31, 34] (B, R1, R2; bound 37.4); text NLL [0.665, 0.6614, 0.66, 0.658] (B, R1, R2, A)
  - ok   KL mean <= 1.10 x the larger reference
  - ok   KL p90 <= 1.10 x the larger reference
  - ok   KL>1 count <= the worse reference's + 1
  - FAIL changed top-1 picks <= 1.10 x the larger reference's
  - FAIL text NLL above the base's <= 1.10 x the larger reference's distance
  - prompt-skip lines {'base': 8, 'cand-B': 8, 'R1-chunk4096': 8, 'R2-cpu-share': 8}; run times {'base': 'rc 0, 317 s, lowest MemAvailable 28.5 GB (8 engine runs, one segment each)', 'cand-B': 'rc 0, 275 s, lowest MemAvailable 28.4 GB (8 engine runs, one segment each)', 'R1-chunk4096': 'rc 0, 324 s, lowest MemAvailable 30.3 GB (8 engine runs, one segment each)', 'R2-cpu-share': 'rc 0, 322 s, lowest MemAvailable 28.8 GB (8 engine runs, one segment each)'}
  - B's one-device layer-major prompt path inside the check: 8 of 8 segments
  - report only: A vs stock v0.2.6 (stored teacher/final-*): PASS, changed picks [29, 30, 29]
  - report only: B vs stock v0.2.6 (stored teacher/final-*): PASS, changed picks [22, 30, 29]

## Placement (engine start lines)

- A (`/home/USER/ai-speed-testing/strata-compare/results/ds41/tuning/gate-A-1103-1645`): ds4: DSpark not loaded: the routed experts (132 GB) are far more than the GPU holds (23 GB), where its verify rounds read 3.3x a token's bytes and gain nothing (--dspark  / ds4: CUDA0 layers [0, 7]: weights 1.14 GB, experts 3.59 GB (451 of 3072 in VRAM), caches 0.02 GB, 590 MiB free / ds4: CUDA1 layers [8, 39] + head: weights 4.72 GB, experts 7.83 GB (857 of 12288 in VRAM), caches 0.10 GB, 586 MiB free / ds4: 14052 routed experts on the CPU lane (121.4 GB, in place in the model's files), 16 threads
- B (`/home/USER/ai-speed-testing/strata-compare/results/ds41/tuning/gate-B-1103-1706`): ds4: DSpark not loaded: the routed experts (132 GB) are far more than the GPU holds (16 GB), where its verify rounds read 3.3x a token's bytes and gain nothing (--dspark  / ds4: CUDA0 layers [0, 39] + head: weights 5.86 GB, experts 6.45 GB (711 of 15360 in VRAM), caches 0.12 GB, 574 MiB free / ds4: 14649 routed experts on the CPU lane (126.3 GB, in place in the model's files), 16 threads
