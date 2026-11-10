| arm | workload | n | tokens | decode tok/s (client) | decode tok/s (engine) | accepted / drafted | expert-cache hit % | prompt tok/s | finish | drafts per window |
|---|---|---:|---:|---:|---:|---:|---:|---:|---|---:|
| B1a | A-edit | 1 | 300 | 132.9 | 132.4 | 231/280 (82%) | 57.5 | 2616.4 | tool_calls | 3.78 |
| B1a | B-write | 1 | 2025 | 166.9 | 166.8 | 1462/2041 (72%) | 83.9 | 1628.0 | tool_calls | 3.61 |
| B1n | W1-think | 1 | 3072 | 167.8 | 167.6 | 2061/2915 (71%) | 89.3 | 379.1 | length | 2.92 |
| B1n | W2-code | 1 | 3072 | 153.5 | 153.5 | 2078/3217 (65%) | 82.5 | 388.2 | length | 3.23 |
| B1n | W3-research | 1 | 2048 | 152.1 | 152.0 | 1507/2090 (72%) | 83.7 | 4433.6 | length | 3.86 |
| B1r | R1-verify20k | 1 | 3821 | 159.1 | 159.0 | 2787/3528 (79%) | 80.2 | 4379.6 | stop | 3.46 |
| B1r | R2-report54k | 1 | 3364 | 153.6 | 153.5 | 2445/3409 (72%) | 79.0 | 4502.6 | stop | 3.71 |
| B1r | R3-extract5k | 1 | 1182 | 174.5 | 174.2 | 916/1186 (77%) | 81.0 | 3534.5 | stop | 4.46 |
| B1r | R4-agent33k | 1 | 249 | 137.1 | 136.5 | 191/249 (77%) | 81.8 | 4267.2 | tool_calls | 3.95 |
| B2a | A-edit | 1 | 320 | 119.3 | 119.0 | 261/330 (79%) | 47.2 | 2645.3 | tool_calls | 5.16 |
| B2a | B-write | 1 | 1492 | 170.3 | 170.2 | 1115/1548 (72%) | 82.8 | 1616.1 | tool_calls | 4.08 |
| B2n | W1-think | 1 | 3072 | 186.0 | 185.9 | 2298/3187 (72%) | 87.6 | 373.0 | length | 4.20 |
| B2n | W2-code | 1 | 3072 | 169.3 | 169.2 | 2240/3180 (70%) | 85.0 | 400.4 | length | 3.82 |
| B2n | W3-research | 1 | 2048 | 162.4 | 162.3 | 1593/2043 (78%) | 83.7 | 4431.6 | length | 4.46 |
| B2r | R1-verify20k | 1 | 3646 | 154.9 | 154.7 | 2583/3353 (77%) | 81.1 | 4376.0 | stop | 3.20 |
| B2r | R2-report54k | 1 | 3377 | 154.4 | 154.3 | 2448/3313 (74%) | 76.4 | 4499.0 | stop | 3.55 |
| B2r | R3-extract5k | 1 | 1162 | 173.8 | 173.5 | 915/1164 (79%) | 80.5 | 3533.6 | stop | 4.71 |
| B2r | R4-agent33k | 1 | 267 | 126.5 | 126.1 | 193/288 (67%) | 79.6 | 4268.1 | tool_calls | 3.74 |
| B3a | A-edit | 1 | 648 | 135.3 | 134.1 | 468/639 (73%) | 68.7 | 2639.6 | tool_calls | 3.55 |
| B3a | B-write | 1 | 1560 | 168.1 | 168.0 | 1152/1631 (71%) | 83.7 | 1485.4 | tool_calls | 4.00 |
| B3n | W1-think | 1 | 3072 | 169.9 | 169.8 | 2086/2872 (73%) | 89.2 | 376.1 | length | 2.95 |
| B3n | W2-code | 1 | 3072 | 162.7 | 162.6 | 2231/3222 (69%) | 79.9 | 386.7 | length | 3.81 |
| B3n | W3-research | 1 | 2048 | 151.8 | 151.7 | 1511/2074 (73%) | 82.6 | 4428.4 | length | 3.86 |
| B3r | R1-verify20k | 1 | 3673 | 156.0 | 155.8 | 2634/3354 (79%) | 80.5 | 4378.4 | stop | 3.28 |
| B3r | R2-report54k | 1 | 3682 | 155.1 | 155.1 | 2648/3613 (73%) | 74.5 | 4498.3 | stop | 3.48 |
| B3r | R3-extract5k | 1 | 1133 | 181.1 | 180.8 | 897/1102 (81%) | 81.4 | 3541.0 | stop | 4.67 |
| B3r | R4-agent33k | 1 | 315 | 128.1 | 127.7 | 226/338 (67%) | 80.6 | 4264.9 | tool_calls | 3.71 |
| P1a | A-edit | 1 | 727 | 143.0 | 142.7 | 576/697 (83%) | 63.7 | 2643.8 | tool_calls | 4.56 |
| P1a | B-write | 1 | 1775 | 157.7 | 157.6 | 1237/1819 (68%) | 83.5 | 1633.5 | tool_calls | 3.38 |
| P1n | W1-think | 1 | 3072 | 160.8 | 160.7 | 1989/2918 (68%) | 89.1 | 380.4 | length | 2.74 |
| P1n | W2-code | 1 | 3072 | 169.4 | 169.3 | 2231/3164 (71%) | 80.8 | 403.0 | length | 3.75 |
| P1n | W3-research | 1 | 2048 | 160.4 | 160.3 | 1573/1989 (79%) | 84.0 | 4429.9 | length | 4.19 |
| P1r | R1-verify20k | 1 | 3972 | 156.5 | 156.1 | 2812/3611 (78%) | 81.7 | 4382.8 | stop | 3.14 |
| P1r | R2-report54k | 1 | 2699 | 147.9 | 147.9 | 1909/2693 (71%) | 75.8 | 4501.3 | stop | 3.39 |
| P1r | R3-extract5k | 1 | 1329 | 178.5 | 178.2 | 1053/1330 (79%) | 80.1 | 3486.2 | stop | 4.82 |
| P1r | R4-agent33k | 1 | 375 | 128.9 | 128.6 | 265/419 (63%) | 80.7 | 4253.5 | tool_calls | 3.71 |
| P2a | A-edit | 1 | 304 | 126.1 | 125.7 | 249/299 (83%) | 45.8 | 2642.6 | tool_calls | 5.34 |
| P2a | B-write | 1 | 1550 | 171.6 | 171.5 | 1153/1545 (75%) | 82.9 | 1616.4 | tool_calls | 3.88 |
| P2n | W1-think | 1 | 3072 | 192.6 | 192.5 | 2336/3013 (78%) | 87.8 | 384.5 | length | 4.17 |
| P2n | W2-code | 1 | 3072 | 159.9 | 159.9 | 2123/3191 (67%) | 83.3 | 390.3 | length | 3.36 |
| P2n | W3-research | 1 | 2048 | 161.7 | 161.6 | 1579/2028 (78%) | 84.2 | 4430.2 | length | 4.31 |
| P2r | R1-verify20k | 1 | 3760 | 150.7 | 150.5 | 2595/3472 (75%) | 81.4 | 4386.0 | stop | 3.01 |
| P2r | R2-report54k | 1 | 3817 | 157.2 | 157.1 | 2803/3817 (73%) | 78.1 | 4498.8 | stop | 3.75 |
| P2r | R3-extract5k | 1 | 1124 | 175.8 | 175.4 | 879/1124 (78%) | 81.3 | 3487.8 | stop | 4.59 |
| P2r | R4-agent33k | 1 | 311 | 134.3 | 133.9 | 229/340 (67%) | 81.0 | 4254.2 | tool_calls | 4.05 |
| P3a | A-edit | 1 | 335 | 135.9 | 135.5 | 266/319 (83%) | 56.2 | 2633.5 | tool_calls | 4.43 |
| P3a | B-write | 1 | 2063 | 160.7 | 160.6 | 1423/2109 (67%) | 85.7 | 1633.2 | tool_calls | 3.27 |
| P3n | W1-think | 1 | 3072 | 199.4 | 199.4 | 2350/3146 (75%) | 89.3 | 383.0 | length | 4.46 |
| P3n | W2-code | 1 | 3072 | 167.6 | 167.5 | 2246/3170 (71%) | 85.9 | 398.1 | length | 3.84 |
| P3n | W3-research | 1 | 2048 | 161.3 | 161.1 | 1554/1970 (79%) | 83.2 | 4430.7 | length | 3.99 |
| P3r | R1-verify20k | 1 | 3590 | 157.0 | 156.8 | 2590/3348 (77%) | 80.5 | 4385.6 | stop | 3.41 |
| P3r | R2-report54k | 1 | 3887 | 156.8 | 156.4 | 2830/3961 (71%) | 77.1 | 4497.2 | stop | 3.73 |
| P3r | R3-extract5k | 1 | 1222 | 181.0 | 180.7 | 969/1198 (81%) | 82.1 | 3481.4 | stop | 4.72 |
| P3r | R4-agent33k | 1 | 348 | 128.5 | 128.1 | 246/378 (65%) | 81.2 | 4255.7 | tool_calls | 3.60 |

- B1a: experts in VRAM at start: 4585 slots / 8.75 GiB
- B1n: experts in VRAM at start: 4585 slots / 8.75 GiB
- B1r: experts in VRAM at start: 4585 slots / 8.75 GiB
- B2a: experts in VRAM at start: 4585 slots / 8.75 GiB
- B2n: experts in VRAM at start: 4585 slots / 8.75 GiB
- B2r: experts in VRAM at start: 4585 slots / 8.75 GiB
- B3a: experts in VRAM at start: 4585 slots / 8.75 GiB
- B3n: experts in VRAM at start: 4585 slots / 8.75 GiB
- B3r: experts in VRAM at start: 4585 slots / 8.75 GiB
- P1a: experts in VRAM at start: 4585 slots / 8.75 GiB
- P1n: experts in VRAM at start: 4585 slots / 8.75 GiB
- P1r: experts in VRAM at start: 4585 slots / 8.75 GiB
- P2a: experts in VRAM at start: 4585 slots / 8.75 GiB
- P2n: experts in VRAM at start: 4585 slots / 8.75 GiB
- P2r: experts in VRAM at start: 4585 slots / 8.75 GiB
- P3a: experts in VRAM at start: 4585 slots / 8.75 GiB
- P3n: experts in VRAM at start: 4585 slots / 8.75 GiB
- P3r: experts in VRAM at start: 4585 slots / 8.75 GiB
