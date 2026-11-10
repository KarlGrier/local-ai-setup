| arm | workload | n | tokens | decode tok/s (client) | decode tok/s (engine) | accepted / drafted | expert-cache hit % | prompt tok/s | finish | drafts per window |
|---|---|---:|---:|---:|---:|---:|---:|---:|---|---:|
| H1n | W1-think | 1 | 3072 | 188.8 | 188.7 | 2290/3213 (71%) | 88.9 | 331.8 | length | 4.21 |
| H1n | W2-code | 1 | 3072 | 155.7 | 155.6 | 2107/3194 (66%) | 86.0 | 346.7 | length | 3.30 |
| H1n | W3-research | 1 | 2048 | 152.7 | 152.6 | 1533/2063 (74%) | 83.3 | 4417.5 | length | 3.99 |
| H2n | W1-think | 1 | 3072 | 169.9 | 169.8 | 2070/2898 (71%) | 89.5 | 304.2 | length | 2.94 |
| H2n | W2-code | 1 | 3072 | 151.0 | 151.0 | 2106/3273 (64%) | 81.8 | 337.0 | length | 3.38 |
| H2n | W3-research | 1 | 2048 | 162.9 | 162.8 | 1570/2034 (77%) | 81.9 | 4423.0 | length | 4.26 |
| noboth1n | W1-think | 1 | 3072 | 161.9 | 161.7 | 2046/2905 (70%) | 89.5 | 304.7 | length | 2.86 |
| noboth1n | W2-code | 1 | 3072 | 152.8 | 152.7 | 2188/3255 (67%) | 82.4 | 337.2 | length | 3.68 |
| noboth1n | W3-research | 1 | 2048 | 157.5 | 157.4 | 1557/1958 (80%) | 82.6 | 4213.5 | length | 3.99 |
| noboth2n | W1-think | 1 | 3072 | 178.8 | 178.8 | 2370/3084 (77%) | 86.4 | 332.5 | length | 4.46 |
| noboth2n | W2-code | 1 | 3072 | 162.4 | 162.4 | 2273/3189 (71%) | 82.5 | 316.5 | length | 3.99 |
| noboth2n | W3-research | 1 | 2048 | 151.5 | 151.4 | 1564/2028 (77%) | 82.9 | 4219.3 | length | 4.18 |
| H1a | A-edit | 1 | 769 | 138.3 | 138.1 | 588/759 (77%) | 65.2 | 2361.0 | tool_calls | 4.19 |
| H1a | B-write | 1 | 2461 | 155.9 | 155.8 | 1744/2557 (68%) | 82.4 | 1536.6 | tool_calls | 3.55 |
| H2a | A-edit | 1 | 586 | 129.8 | 129.5 | 452/600 (75%) | 61.0 | 2334.4 | tool_calls | 4.44 |
| H2a | B-write | 1 | 993 | 185.7 | 185.4 | 796/1012 (79%) | 82.6 | 1514.0 | tool_calls | 5.01 |
| noboth1a | A-edit | 1 | 195 | 122.2 | 121.5 | 157/185 (85%) | 46.2 | 2312.9 | tool_calls | 4.87 |
| noboth1a | B-write | 1 | 2455 | 155.6 | 155.5 | 1729/2447 (71%) | 83.9 | 1475.8 | tool_calls | 3.35 |
| noboth2a | A-edit | 1 | 330 | 114.5 | 114.2 | 266/329 (81%) | 47.1 | 2319.0 | tool_calls | 4.98 |
| noboth2a | B-write | 1 | 2177 | 153.9 | 153.9 | 1523/2235 (68%) | 84.5 | 1509.2 | tool_calls | 3.40 |
| H1r | R1-verify20k | 1 | 3595 | 155.2 | 154.7 | 2524/3267 (77%) | 81.3 | 4367.2 | stop | 3.09 |
| H1r | R2-report54k | 1 | 3540 | 150.9 | 150.8 | 2522/3554 (71%) | 76.8 | 4477.4 | stop | 3.48 |
| H1r | R3-extract5k | 1 | 840 | 169.7 | 169.3 | 660/846 (78%) | 81.3 | 3112.4 | stop | 4.70 |
| H1r | R4-agent33k | 1 | 345 | 145.9 | 145.5 | 261/345 (76%) | 78.4 | 4260.6 | tool_calls | 3.88 |
| H2r | R1-verify20k | 1 | 3654 | 153.0 | 152.9 | 2538/3343 (76%) | 82.0 | 4373.9 | stop | 3.03 |
| H2r | R2-report54k | 1 | 3746 | 150.7 | 150.4 | 2664/3805 (70%) | 77.2 | 4477.3 | stop | 3.50 |
| H2r | R3-extract5k | 1 | 1013 | 174.7 | 174.3 | 799/995 (80%) | 81.4 | 3111.6 | stop | 4.65 |
| H2r | R4-agent33k | 1 | 429 | 127.0 | 125.4 | 292/477 (61%) | 79.2 | 4258.8 | tool_calls | 3.36 |
| noboth1r | R1-verify20k | 1 | 3884 | 146.9 | 146.5 | 2707/3583 (76%) | 81.6 | 4176.8 | stop | 3.08 |
| noboth1r | R2-report54k | 1 | 2900 | 148.7 | 148.6 | 2099/2904 (72%) | 74.9 | 4268.5 | stop | 3.61 |
| noboth1r | R3-extract5k | 1 | 1205 | 168.5 | 168.3 | 941/1174 (80%) | 80.7 | 2901.3 | stop | 4.45 |
| noboth1r | R4-agent33k | 1 | 348 | 131.3 | 131.0 | 254/364 (70%) | 80.3 | 4065.5 | tool_calls | 3.87 |
| noboth2r | R1-verify20k | 1 | 3689 | 147.1 | 146.9 | 2562/3384 (76%) | 81.1 | 4173.9 | stop | 3.04 |
| noboth2r | R2-report54k | 1 | 3771 | 148.4 | 148.3 | 2770/3844 (72%) | 77.0 | 4260.1 | stop | 3.82 |
| noboth2r | R3-extract5k | 1 | 1116 | 170.5 | 170.2 | 873/1087 (80%) | 80.7 | 2938.2 | stop | 4.47 |
| noboth2r | R4-agent33k | 1 | 295 | 134.6 | 134.1 | 220/297 (74%) | 81.2 | 4071.4 | tool_calls | 3.91 |

- H1n: experts in VRAM at start: 4585 slots / 8.75 GiB
- H2n: experts in VRAM at start: 4585 slots / 8.75 GiB
- noboth1n: experts in VRAM at start: 4585 slots / 8.75 GiB
- noboth2n: experts in VRAM at start: 4585 slots / 8.75 GiB
- H1a: experts in VRAM at start: 4585 slots / 8.75 GiB
- H2a: experts in VRAM at start: 4585 slots / 8.75 GiB
- noboth1a: experts in VRAM at start: 4585 slots / 8.75 GiB
- noboth2a: experts in VRAM at start: 4585 slots / 8.75 GiB
- H1r: experts in VRAM at start: 4585 slots / 8.75 GiB
- H2r: experts in VRAM at start: 4585 slots / 8.75 GiB
- noboth1r: experts in VRAM at start: 4585 slots / 8.75 GiB
- noboth2r: experts in VRAM at start: 4585 slots / 8.75 GiB
