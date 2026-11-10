| comparison | text | ppl A | ppl B | B − A (nats/token) | tokens that changed |
|---|---|---|---|---|---|
| determinism: v0.1.12 base run 1 vs run 2 | math | 1.3370 | 1.3370 | +0.0000 ± 0.0000 | 0 of 1536 |
| determinism: v0.1.12 base run 1 vs run 2 | corpus | 1.4746 | 1.4746 | +0.0000 ± 0.0000 | 0 of 1536 |
| determinism: v0.1.12 base run 1 vs run 2 | long16k | 16.1942 | 16.1942 | +0.0000 ± 0.0000 | 0 of 1536 |
| determinism: C*3 run a vs run b | math | 1.3366 | 1.3366 | +0.0000 ± 0.0000 | 0 of 1536 |
| determinism: C*3 run a vs run b | corpus | 1.4766 | 1.4766 | +0.0000 ± 0.0000 | 0 of 1536 |
| determinism: C*3 run a vs run b | long16k | 14.3085 | 14.3085 | +0.0000 ± 0.0000 | 0 of 1536 |
| **C*3 vs v0.1.12 base** | math | 1.3370 | 1.3366 | -0.0003 ± 0.0006 | 1418 of 1536 |
| **C*3 vs v0.1.12 base** | corpus | 1.4746 | 1.4766 | +0.0013 ± 0.0016 | 1478 of 1536 |
| **C*3 vs v0.1.12 base** | long16k | 16.1942 | 14.3085 | -0.1238 ± 0.0267 | 1529 of 1536 |
| **C*3 vs v0.1.12 base** | long24k | 31.1768 | 23.0973 | -0.3000 ± 0.0309 | 1536 of 1536 |
| C*3 with the old per-token PLE vs base (isolates patch 0003) | long16k | 16.1942 | 16.1942 | +0.0000 ± 0.0000 | 0 of 1536 |
| C*3 with the old per-token PLE vs base (isolates patch 0003) | long24k | 31.1768 | 31.1768 | +0.0000 ± 0.0000 | 0 of 1536 |
| sensitivity: base, --prefill 4096 vs 8192 (a rounding change accepted in round 2) | long16k | 16.1942 | 15.3014 | -0.0567 ± 0.0225 | 1526 of 1536 |
| sensitivity: base, --prefill 4096 vs 8192 (a rounding change accepted in round 2) | long24k | 31.1768 | 21.7156 | -0.3616 ± 0.0284 | 1533 of 1536 |
| sensitivity: C*3, --prefill 4096 vs 8192 | long16k | 14.3085 | 25.5158 | +0.5784 ± 0.0363 | 1534 of 1536 |
| sensitivity: C*3, --prefill 4096 vs 8192 | long24k | 23.0973 | 35.7257 | +0.4362 ± 0.0336 | 1535 of 1536 |
