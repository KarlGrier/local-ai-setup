# The 1017-drafter acceptance probe: **CLOSED**

Rule: rule-probe.txt (fixed before the gap). Nothing is built.

- position 1: probe 2097 / 2587 = 81.06 % vs D1's C2 6809 / 8269 = 82.34 %: -1.28 points (needed >= +2.0; standard error of the difference ~0.877 points)
- the probe per position (W1-W3, 1 pass): 1: 2097 / 2587 = 81.06 %; 2: 1283 / 1470 = 87.28 %; tokens a verify round 2.307
- placement: ds4: CUDA0 layers [40, 42]: weights 0.62 GB, experts 4.76 GB (252 of 384 in VRAM), caches 0.00 GB, 608 MiB free / ds4: CUDA1 layers [0, 39] + head: weights 5.99 GB, experts 6.31 GB (693 of 15360 in VRAM), caches 0.12 GB, 571 MiB free / ds4: 14799 routed experts on the CPU lane (129.0 GB, in place in the model's files), 16 threads
