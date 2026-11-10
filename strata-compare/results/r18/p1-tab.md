# r18-tab: CLI fixed computation, greedy 1,024 tokens

| arm | item | ms/round a / b | GPU wait a / b | GPU wait mean | vs first (ms) | CPU pool a / b | outputs |
|---|---|---|---|---|---|---|---|
| side fixes, F4 shared table | math | 32.59 / 28.44 | 7.064 / 7.045 | 7.054 | +0.000 | 23.6 / 19.5 | 8872fb65 |
| side fixes + table measured on this 5080 | math | 28.29 / 28.31 | 6.930 / 6.926 | 6.928 | -0.127 | 19.5 / 19.5 | 8872fb65 |
| side fixes + B.3's table | math | 28.34 / 28.32 | 6.919 / 6.918 | 6.918 | -0.136 | 19.5 / 19.5 | 8872fb65 |
| C*14 | math | 28.19 / 28.20 | 6.810 / 6.809 | 6.809 | -0.245 | 19.5 / 19.5 | 8872fb65 |
| side fixes, F4 shared table | code | 21.43 / 21.45 | 6.841 / 6.838 | 6.840 | +0.000 | 12.8 / 12.8 | 8c88ce05 |
| side fixes + table measured on this 5080 | code | 21.34 / 21.34 | 6.766 / 6.762 | 6.764 | -0.076 | 12.8 / 12.8 | 8c88ce05 |
| side fixes + B.3's table | code | 21.33 / 21.32 | 6.747 / 6.745 | 6.746 | -0.093 | 12.8 / 12.8 | 8c88ce05 |
| C*14 | code | 21.19 / 21.15 | 6.627 / 6.627 | 6.627 | -0.213 | 12.8 / 12.7 | 8c88ce05 |
