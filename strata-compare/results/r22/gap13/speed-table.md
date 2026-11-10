| arm | workload | n | tokens | decode tok/s (client) | decode tok/s (engine) | accepted / drafted | expert-cache hit % | prompt tok/s | finish | drafts per window |
|---|---|---:|---:|---:|---:|---:|---:|---:|---|---:|
| M1n | W1-think | 1 | 3072 | 170.3 | 170.3 | 2085/2876 (72%) | 88.7 | 382.6 | length | 2.96 |
| M1n | W2-code | 1 | 3072 | 165.2 | 165.1 | 2228/3140 (71%) | 83.0 | 330.6 | length | 3.70 |
| M1n | W3-research | 1 | 2048 | 157.6 | 157.5 | 1532/2019 (76%) | 82.7 | 4451.7 | length | 3.90 |
| M2n | W1-think | 1 | 3072 | 198.3 | 198.2 | 2312/3103 (75%) | 89.5 | 356.8 | length | 4.17 |
| M2n | W2-code | 1 | 3072 | 160.2 | 160.2 | 2169/3138 (69%) | 87.1 | 397.7 | length | 3.48 |
| M2n | W3-research | 1 | 2048 | 173.1 | 173.0 | 1608/1970 (82%) | 82.3 | 4455.4 | length | 4.46 |
| H1n | W1-think | 1 | 3072 | 166.9 | 166.8 | 2025/2973 (68%) | 90.0 | 333.8 | length | 2.88 |
| H1n | W2-code | 1 | 3072 | 162.8 | 162.8 | 2187/3180 (69%) | 83.4 | 341.8 | length | 3.59 |
| H1n | W3-research | 1 | 2048 | 165.8 | 165.7 | 1598/2031 (79%) | 83.2 | 4393.4 | length | 4.47 |
| H2n | W1-think | 1 | 3072 | 165.0 | 164.9 | 2003/2843 (70%) | 89.8 | 329.5 | length | 2.70 |
| H2n | W2-code | 1 | 3072 | 163.2 | 163.2 | 2193/3139 (70%) | 81.0 | 313.0 | length | 3.57 |
| H2n | W3-research | 1 | 2048 | 161.4 | 161.2 | 1579/2011 (79%) | 82.7 | 4428.5 | length | 4.28 |
| M1a | A-edit | 1 | 331 | 121.2 | 120.9 | 266/334 (80%) | 47.7 | 2638.2 | tool_calls | 4.99 |
| M1a | B-write | 1 | 4096 | 150.6 | 150.3 | 2738/4070 (67%) | 85.2 | 1601.4 | length | 3.01 |
| M2a | A-edit | 1 | 295 | 134.4 | 131.5 | 229/280 (82%) | 55.3 | 2629.6 | tool_calls | 3.94 |
| M2a | B-write | 1 | 3113 | 157.6 | 157.5 | 2176/3109 (70%) | 82.9 | 1607.9 | tool_calls | 3.31 |
| H1a | A-edit | 1 | 733 | 141.0 | 140.7 | 572/696 (82%) | 62.2 | 2327.2 | tool_calls | 4.24 |
| H1a | B-write | 1 | 3459 | 154.3 | 154.3 | 2407/3452 (70%) | 81.8 | 1525.0 | tool_calls | 3.28 |
| H2a | A-edit | 1 | 422 | 127.5 | 127.2 | 319/426 (75%) | 59.7 | 2336.9 | tool_calls | 4.10 |
| H2a | B-write | 1 | 1408 | 177.8 | 177.6 | 1079/1409 (77%) | 82.9 | 1484.9 | tool_calls | 4.22 |
| M1r | R1-verify20k | 1 | 3640 | 154.8 | 154.6 | 2601/3399 (77%) | 80.6 | 4409.2 | stop | 3.30 |
| M1r | R2-report54k | 1 | 3748 | 155.8 | 155.7 | 2701/3760 (72%) | 76.5 | 4522.2 | stop | 3.59 |
| M1r | R3-extract5k | 1 | 1236 | 183.5 | 183.2 | 994/1198 (83%) | 82.1 | 3539.1 | stop | 4.95 |
| M1r | R4-agent33k | 1 | 185 | 119.6 | 119.1 | 131/209 (63%) | 79.8 | 4271.9 | tool_calls | 3.67 |
| M2r | R1-verify20k | 1 | 3850 | 155.0 | 154.8 | 2766/3590 (77%) | 80.6 | 4407.5 | stop | 3.36 |
| M2r | R2-report54k | 1 | 2597 | 145.8 | 145.3 | 1833/2645 (69%) | 73.1 | 4524.1 | stop | 3.44 |
| M2r | R3-extract5k | 1 | 1270 | 173.9 | 173.6 | 977/1256 (78%) | 80.1 | 3541.3 | stop | 4.29 |
| M2r | R4-agent33k | 1 | 370 | 132.9 | 132.6 | 267/394 (68%) | 81.3 | 4271.8 | tool_calls | 3.75 |
| H1r | R1-verify20k | 1 | 3770 | 153.2 | 153.0 | 2612/3466 (75%) | 82.1 | 4370.7 | stop | 3.03 |
| H1r | R2-report54k | 1 | 2761 | 149.3 | 149.3 | 1956/2859 (68%) | 75.7 | 4478.8 | stop | 3.53 |
| H1r | R3-extract5k | 1 | 1248 | 179.1 | 178.8 | 985/1227 (80%) | 81.5 | 3126.8 | stop | 4.65 |
| H1r | R4-agent33k | 1 | 349 | 133.7 | 131.6 | 256/375 (68%) | 80.4 | 4226.4 | tool_calls | 3.83 |
| H2r | R1-verify20k | 1 | 3612 | 153.1 | 152.9 | 2542/3385 (75%) | 81.1 | 4380.1 | stop | 3.21 |
| H2r | R2-report54k | 1 | 3052 | 149.7 | 149.6 | 2183/3129 (70%) | 77.0 | 4461.1 | stop | 3.58 |
| H2r | R3-extract5k | 1 | 1003 | 179.0 | 178.6 | 788/981 (80%) | 80.9 | 2928.6 | stop | 4.56 |
| H2r | R4-agent33k | 1 | 344 | 129.9 | 129.6 | 243/366 (66%) | 80.6 | 4262.4 | tool_calls | 3.55 |

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
