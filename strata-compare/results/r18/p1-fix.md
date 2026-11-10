# r18-fix: CLI fixed computation, greedy 1,024 tokens, A B B A

| arm | item | ms/round a / b | mean | vs off | GPU wait mean | vs off (ms) | CPU pool mean | outputs |
|---|---|---|---|---|---|---|---|---|
| r18 build, switches off (= C*16) | math | 32.04 / 28.76 | 30.40 | +0.0 % | 7.37 | +0.00 | 21.11 | 8872fb65 |
| STRATA_SIDE_IL=1 | math | 28.53 / 28.48 | 28.51 | -6.2 % | 7.10 | -0.28 | 19.49 | 8872fb65 |
| STRATA_QUANT_IL=1 | math | 28.67 / 28.81 | 28.74 | -5.4 % | 7.34 | -0.03 | 19.48 | 8872fb65 |
| both | math | 28.49 / 28.47 | 28.48 | -6.3 % | 7.07 | -0.30 | 19.49 | 8872fb65 |
| C*14 (reference) | math | 32.26 / 32.31 | 32.28 | +6.2 % | 6.83 | -0.54 | 23.53 | 8872fb65 |
| r18 build, switches off (= C*16) | code | 21.71 / 21.65 | 21.68 | +0.0 % | 7.08 | +0.00 | 12.77 | 8c88ce05 |
| STRATA_SIDE_IL=1 | code | 21.45 / 21.51 | 21.48 | -0.9 % | 6.89 | -0.19 | 12.76 | 8c88ce05 |
| STRATA_QUANT_IL=1 | code | 21.62 / 21.62 | 21.62 | -0.3 % | 7.05 | -0.03 | 12.74 | 8c88ce05 |
| both | code | 21.42 / 21.45 | 21.43 | -1.1 % | 6.86 | -0.22 | 12.75 | 8c88ce05 |
| C*14 (reference) | code | 23.83 / 21.20 | 22.51 | +3.8 % | 6.63 | -0.45 | 14.07 | 8c88ce05 |
