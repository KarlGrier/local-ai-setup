# r18-cnd: CLI fixed computation, greedy 1,024 tokens

| arm | item | ms/round a / b | GPU wait a / b | GPU wait mean | vs first (ms) | CPU pool a / b | outputs |
|---|---|---|---|---|---|---|---|
| C*16 | math | 28.44 / 28.42 | 7.365 / 7.356 | 7.361 | +0.000 | 19.1 / 19.1 | 8872fb65 |
| candidate C*16.1 | math | 27.99 / 27.97 | 6.928 / 6.923 | 6.925 | -0.435 | 19.2 / 19.1 | 8872fb65 |
| C*16 | code | 21.40 / 21.43 | 7.083 / 7.081 | 7.082 | +0.000 | 12.5 / 12.5 | 8c88ce05 |
| candidate C*16.1 | code | 21.13 / 21.12 | 6.764 / 6.764 | 6.764 | -0.318 | 12.6 / 12.6 | 8c88ce05 |
