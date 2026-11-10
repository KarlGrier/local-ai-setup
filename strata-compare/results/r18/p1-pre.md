# r18-pre: C*14 vs C*16, CLI fixed computation, greedy 1,024 tokens, A B B A per state

| state | item | C*14 arms ms/round | C*16 arms ms/round | C*14 mean | C*16 mean | C*16 vs C*14 | outputs |
|---|---|---|---|---|---|---|---|
| as served | math | 32.49 / 32.47 | 32.91 / 32.95 | 32.48 | 32.93 | +1.4 % | identical |
| as served | code | 23.80 / 23.76 | 24.39 / 24.27 | 23.78 | 24.33 | +2.3 % | identical |
| STRATA_MMVQ_IL=0 (B.3 / F4 off) | math | 32.90 / 32.84 | 33.33 / 33.19 | 32.87 | 33.26 | +1.2 % | identical |
| STRATA_MMVQ_IL=0 (B.3 / F4 off) | code | 24.24 / 24.05 | 24.40 / 24.51 | 24.14 | 24.46 | +1.3 % | identical |
| STRATA_SIDE_MIXER=0 | math | 28.68 / 28.66 | 28.91 / 28.97 | 28.67 | 28.94 | +1.0 % | identical |
| STRATA_SIDE_MIXER=0 | code | 21.67 / 21.64 | 21.90 / 21.99 | 21.65 | 21.94 | +1.3 % | identical |

| state | item | GPU wait (wait for rings) C*14 mean | C*16 mean | difference | CPU pool C*14 / C*16 |
|---|---|---|---|---|---|
| as served | math | 6.83 | 7.38 | +0.55 ms | 23.72 / 23.62 |
| as served | code | 6.64 | 7.09 | +0.45 ms | 15.32 / 15.40 |
| STRATA_MMVQ_IL=0 (B.3 / F4 off) | math | 7.29 | 7.58 | +0.29 ms | 23.53 / 23.58 |
| STRATA_MMVQ_IL=0 (B.3 / F4 off) | code | 6.98 | 7.20 | +0.23 ms | 15.26 / 15.29 |
| STRATA_SIDE_MIXER=0 | math | 7.26 | 7.55 | +0.29 ms | 19.50 / 19.47 |
| STRATA_SIDE_MIXER=0 | code | 7.07 | 7.33 | +0.26 ms | 12.78 / 12.79 |

| switch | item | effect on C*14 (ms/round, % vs on) | effect on C*16 |
|---|---|---|---|
| STRATA_MMVQ_IL=0 (B.3 / F4 off) | math | +0.39 (+1.2 %) | +0.33 (+1.0 %) |
| STRATA_MMVQ_IL=0 (B.3 / F4 off) | code | +0.36 (+1.5 %) | +0.13 (+0.5 %) |
| STRATA_SIDE_MIXER=0 | math | -3.81 (-11.7 %) | -3.99 (-12.1 %) |
| STRATA_SIDE_MIXER=0 | code | -2.12 (-8.9 %) | -2.39 (-9.8 %) |
