# r18-fix2: CLI fixed computation, greedy 1,024 tokens, A B B A

| arm | item | ms/round a / b | mean | vs off | GPU wait mean | vs off (ms) | CPU pool mean | outputs |
|---|---|---|---|---|---|---|---|---|
| r18 build, switches off (= C*16) | math | 30.72 / 28.75 | 29.73 | +0.0 % | 7.36 | +0.00 | 20.45 | 8872fb65 |
| STRATA_SIDE_IL=1 | math | 32.59 / 28.51 | 30.55 | +2.8 % | 7.11 | -0.26 | 21.52 | 8872fb65 |
| SIDE_IL + SIDE_QKV_FIRST | math | 32.76 / 28.44 | 30.60 | +2.9 % | 7.06 | -0.31 | 21.61 | 8872fb65 |
| C*14 (reference) | math | 28.25 / 28.19 | 28.22 | -5.1 % | 6.81 | -0.56 | 19.50 | 8872fb65 |
| r18 build, switches off (= C*16) | code | 21.66 / 21.64 | 21.65 | +0.0 % | 7.08 | +0.00 | 12.74 | 8c88ce05 |
| STRATA_SIDE_IL=1 | code | 23.94 / 21.52 | 22.73 | +5.0 % | 6.89 | -0.19 | 14.00 | 8c88ce05 |
| SIDE_IL + SIDE_QKV_FIRST | code | 23.99 / 21.40 | 22.70 | +4.8 % | 6.85 | -0.23 | 14.02 | 8c88ce05 |
| C*14 (reference) | code | 21.21 / 21.17 | 21.19 | -2.1 % | 6.63 | -0.46 | 12.76 | 8c88ce05 |
