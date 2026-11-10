| context | arm | output hash per run | ms per verify round per run | mean | decode tok/s mean |
|---|---|---|---|---|---|
| short | cluster off | cdb03dd8 cdb03dd8 f1d42c41 | 19.16 / 19.18 / 18.46 | **18.93** | 133.5 |
| short | cluster on | f1d42c41 c52cd17f cdb03dd8 | 18.49 / 19.10 / 19.15 | **18.91** | 131.3 |
| 32k | cluster off | fc9f8d6d f7a23e99 cbef7f28 | 23.85 / 21.97 / 20.88 | **22.24** | 118.8 |
| 32k | cluster on | f7a23e99 00f14070 f7a23e99 | 21.88 / 22.12 / 21.84 | **21.95** | 114.7 |
| 112k | cluster off | 9a244089 9a244089 9a244089 | 22.15 / 22.22 / 22.24 | **22.20** | 106.8 |
| 112k | cluster on | 9a244089 9a244089 9a244089 | 21.58 / 21.59 / 21.57 | **21.58** | 110.4 |

- short: ms per verify round, cluster on vs off: -0.12 %
- 32k: ms per verify round, cluster on vs off: -1.31 %
- 112k: ms per verify round, cluster on vs off: -2.81 %
