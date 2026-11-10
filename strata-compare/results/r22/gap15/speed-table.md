| arm | workload | n | tokens | decode tok/s (client) | decode tok/s (engine) | accepted / drafted | expert-cache hit % | prompt tok/s | finish | drafts per window |
|---|---|---:|---:|---:|---:|---:|---:|---:|---|---:|
| M1n | W1-think | 1 | 3072 | 166.6 | 166.4 | 2042/2904 (70%) | 88.8 | 380.8 | length | 2.86 |
| M1n | W2-code | 1 | 3072 | 149.5 | 149.1 | 2012/3137 (64%) | 82.6 | 390.9 | length | 3.01 |
| M1n | W3-research | 1 | 2048 | 161.7 | 161.6 | 1546/2038 (76%) | 83.7 | 4457.1 | length | 4.04 |
| M2n | W1-think | 1 | 3072 | 168.2 | 168.1 | 2077/2896 (72%) | 88.7 | 377.0 | length | 2.95 |
| M2n | W2-code | 1 | 3072 | 154.6 | 154.5 | 2144/3246 (66%) | 80.5 | 376.2 | length | 3.50 |
| M2n | W3-research | 1 | 2048 | 162.8 | 162.6 | 1555/1992 (78%) | 82.2 | 4446.5 | length | 4.04 |
| H1n | W1-think | 1 | 3072 | 161.8 | 161.8 | 2025/2862 (71%) | 89.1 | 323.7 | length | 2.78 |
| H1n | W2-code | 1 | 3072 | 157.9 | 157.8 | 2192/3152 (70%) | 82.7 | 343.1 | length | 3.58 |
| H1n | W3-research | 1 | 2048 | 149.4 | 149.3 | 1519/2043 (74%) | 83.5 | 4225.0 | length | 3.86 |
| H2n | W1-think | 1 | 3072 | 164.7 | 164.7 | 2091/2871 (73%) | 89.0 | 331.2 | length | 2.96 |
| H2n | W2-code | 1 | 3072 | 159.9 | 159.9 | 2254/3178 (71%) | 83.0 | 337.8 | length | 3.89 |
| H2n | W3-research | 1 | 2048 | 153.3 | 153.2 | 1560/2023 (77%) | 82.7 | 4223.5 | length | 4.14 |
| M1a | A-edit | 1 | 337 | 120.9 | 118.8 | 272/347 (78%) | 48.1 | 2626.7 | tool_calls | 4.96 |
| M1a | B-write | 1 | 1193 | 187.1 | 185.5 | 944/1215 (78%) | 82.9 | 1623.9 | tool_calls | 4.78 |
| M2a | A-edit | 1 | 334 | 122.8 | 122.5 | 270/335 (81%) | 46.5 | 2634.2 | tool_calls | 5.15 |
| M2a | B-write | 1 | 3021 | 160.1 | 159.7 | 2188/3024 (72%) | 81.2 | 1591.1 | tool_calls | 3.61 |
| H1a | A-edit | 1 | 369 | 120.1 | 119.8 | 293/357 (82%) | 48.6 | 2351.9 | tool_calls | 4.64 |
| H1a | B-write | 1 | 3089 | 151.8 | 151.8 | 2197/3143 (70%) | 82.5 | 1516.3 | tool_calls | 3.51 |
| H2a | A-edit | 1 | 177 | 125.5 | 124.8 | 143/169 (85%) | 45.1 | 2323.2 | tool_calls | 4.97 |
| H2a | B-write | 1 | 968 | 166.2 | 166.0 | 755/1023 (74%) | 81.2 | 1499.6 | tool_calls | 4.78 |
| M1r | R1-verify20k | 1 | 3632 | 155.5 | 155.0 | 2569/3334 (77%) | 80.8 | 4407.8 | stop | 3.18 |
| M1r | R2-report54k | 1 | 2890 | 148.4 | 148.3 | 2045/2966 (69%) | 76.4 | 4525.9 | stop | 3.51 |
| M1r | R3-extract5k | 1 | 1092 | 175.0 | 174.7 | 849/1087 (78%) | 80.9 | 3487.4 | stop | 4.47 |
| M1r | R4-agent33k | 1 | 361 | 129.6 | 129.3 | 256/391 (65%) | 81.0 | 4283.1 | tool_calls | 3.62 |
| M2r | R1-verify20k | 1 | 3956 | 158.2 | 158.1 | 2878/3641 (79%) | 80.0 | 4405.8 | stop | 3.43 |
| M2r | R2-report54k | 1 | 4096 | 151.7 | 151.7 | 2957/4139 (71%) | 76.4 | 4508.1 | length | 3.63 |
| M2r | R3-extract5k | 1 | 1037 | 174.8 | 174.4 | 817/1043 (78%) | 80.5 | 3485.4 | stop | 4.74 |
| M2r | R4-agent33k | 1 | 363 | 132.3 | 131.9 | 260/389 (67%) | 79.7 | 4280.8 | tool_calls | 3.70 |
| H1r | R1-verify20k | 1 | 3635 | 152.0 | 151.9 | 2610/3323 (79%) | 80.8 | 4190.1 | stop | 3.28 |
| H1r | R2-report54k | 1 | 2585 | 145.7 | 145.7 | 1853/2590 (72%) | 77.0 | 4272.4 | stop | 3.52 |
| H1r | R3-extract5k | 1 | 1042 | 168.6 | 168.3 | 818/1008 (81%) | 80.7 | 2999.1 | stop | 4.50 |
| H1r | R4-agent33k | 1 | 329 | 131.1 | 130.7 | 238/345 (69%) | 79.7 | 4073.4 | tool_calls | 3.59 |
| H2r | R1-verify20k | 1 | 3862 | 149.7 | 149.5 | 2761/3522 (78%) | 80.4 | 4179.6 | stop | 3.24 |
| H2r | R2-report54k | 1 | 3451 | 152.3 | 152.2 | 2538/3464 (73%) | 75.3 | 4272.7 | stop | 3.78 |
| H2r | R3-extract5k | 1 | 1289 | 177.3 | 177.1 | 1040/1226 (85%) | 81.8 | 2947.6 | stop | 4.92 |
| H2r | R4-agent33k | 1 | 318 | 122.1 | 121.8 | 231/337 (69%) | 80.0 | 4072.3 | tool_calls | 3.74 |

- M1n: experts in VRAM at start: 4585 slots / 8.75 GiB
- M2n: experts in VRAM at start: 4585 slots / 8.75 GiB
- H1n: experts in VRAM at start: 4585 slots / 8.75 GiB
- H2n: experts in VRAM at start: 4585 slots / 8.75 GiB
- M1a: experts in VRAM at start: 4585 slots / 8.75 GiB
- M2a: experts in VRAM at start: 4585 slots / 8.75 GiB
- H1a: experts in VRAM at start: 4585 slots / 8.75 GiB
- H2a: experts in VRAM at start: 4585 slots / 8.75 GiB
- M1r: experts in VRAM at start: 4585 slots / 8.75 GiB
- M2r: experts in VRAM at start: 4585 slots / 8.75 GiB
- H1r: experts in VRAM at start: 4585 slots / 8.75 GiB
- H2r: experts in VRAM at start: 4585 slots / 8.75 GiB
