| size | arm | ms per verify round, per run (a / b) | pooled ms/round | tokens per round | pooled decode tok/s |
|---|---|---|---|---|---|
| 1k | cluster off | 16.91 17.98 17.27 18.80 17.44 18.19 | **17.71** | 2.028 | 114.5 |
| 1k | cluster on | 17.38 31.99 17.72 19.13 17.71 17.69 | **19.03** | 2.241 | 117.7 |
| 4k | cluster off | 17.34 17.80 18.59 17.12 16.97 20.87 | **17.99** | 1.986 | 110.4 |
| 4k | cluster on | 17.08 19.84 18.96 17.47 18.61 20.94 | **18.70** | 2.083 | 111.4 |
| 32k | cluster off | 22.13 22.44 20.82 22.94 | **22.04** | 2.419 | 109.8 |
| 32k | cluster on | 20.94 20.70 22.11 20.45 | **21.02** | 2.336 | 111.1 |
| 120k | cluster off | 22.66 23.61 20.89 22.73 | **22.42** | 2.621 | 116.9 |
| 120k | cluster on | 22.25 23.05 20.45 23.06 | **22.09** | 2.699 | 122.2 |

- 1k: ms per round, cluster on vs off: +7.4 %
- 4k: ms per round, cluster on vs off: +3.9 %
- 32k: ms per round, cluster on vs off: -4.6 %
- 120k: ms per round, cluster on vs off: -1.5 %
