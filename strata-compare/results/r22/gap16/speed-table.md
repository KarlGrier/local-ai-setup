| arm | workload | n | tokens | decode tok/s (client) | decode tok/s (engine) | accepted / drafted | expert-cache hit % | prompt tok/s | finish | drafts per window |
|---|---|---:|---:|---:|---:|---:|---:|---:|---|---:|
| M1n | W1-think | 1 | 3072 | 164.1 | 163.9 | 1985/2868 (69%) | 90.2 | 372.4 | length | 2.67 |
| M1n | W2-code | 1 | 3072 | 153.8 | 153.4 | 1992/3197 (62%) | 82.3 | 397.8 | length | 2.99 |
| M1n | W3-research | 1 | 2048 | 164.8 | 164.7 | 1563/1980 (79%) | 88.1 | 4456.5 | length | 4.05 |
| M2n | W1-think | 1 | 3072 | 172.3 | 172.1 | 2116/2878 (74%) | 88.8 | 379.0 | length | 3.05 |
| M2n | W2-code | 1 | 3072 | 154.9 | 154.8 | 2140/3257 (66%) | 81.4 | 389.1 | length | 3.49 |
| M2n | W3-research | 1 | 2048 | 167.3 | 167.2 | 1611/2011 (80%) | 82.1 | 4455.8 | length | 4.55 |
| M3n | W1-think | 1 | 3072 | 186.8 | 186.8 | 2258/3156 (72%) | 88.9 | 373.6 | length | 3.93 |
| M3n | W2-code | 1 | 3072 | 157.1 | 157.0 | 2090/3233 (65%) | 86.3 | 401.4 | length | 3.29 |
| M3n | W3-research | 1 | 2048 | 163.3 | 163.2 | 1566/2018 (78%) | 84.2 | 4449.5 | length | 4.18 |
| X1n | W1-think | 1 | 3072 | 191.0 | 190.9 | 2302/3065 (75%) | 87.7 | 378.4 | length | 4.08 |
| X1n | W2-code | 1 | 3072 | 167.2 | 167.1 | 2253/3201 (70%) | 85.7 | 399.0 | length | 3.90 |
| X1n | W3-research | 1 | 2048 | 156.8 | 156.6 | 1537/2058 (75%) | 82.9 | 4440.9 | length | 4.01 |
| X2n | W1-think | 1 | 3072 | 168.9 | 168.8 | 2042/2857 (71%) | 89.3 | 381.0 | length | 2.81 |
| X2n | W2-code | 1 | 3072 | 163.0 | 162.9 | 2221/3158 (70%) | 82.7 | 394.1 | length | 3.71 |
| X2n | W3-research | 1 | 2048 | 166.6 | 166.4 | 1591/1972 (81%) | 81.8 | 4446.1 | length | 4.30 |
| X3n | W1-think | 1 | 3072 | 169.5 | 169.4 | 2034/2828 (72%) | 89.7 | 378.9 | length | 2.76 |
| X3n | W2-code | 1 | 3072 | 155.1 | 155.0 | 2095/3284 (64%) | 82.4 | 391.2 | length | 3.35 |
| X3n | W3-research | 1 | 2048 | 169.9 | 169.7 | 1611/1994 (81%) | 83.7 | 4442.2 | length | 4.52 |
| Xc1n | W1-think | 1 | 3072 | 188.7 | 188.6 | 2230/3083 (72%) | 89.7 | 320.5 | length | 3.74 |
| Xc1n | W2-code | 1 | 3072 | 167.9 | 167.9 | 2241/3158 (71%) | 86.2 | 349.5 | length | 3.80 |
| Xc1n | W3-research | 1 | 2048 | 158.8 | 158.7 | 1558/2025 (77%) | 83.0 | 4409.1 | length | 4.12 |
| Xc2n | W1-think | 1 | 3072 | 190.0 | 189.9 | 2342/3071 (76%) | 86.9 | 328.4 | length | 4.29 |
| Xc2n | W2-code | 1 | 3072 | 159.9 | 159.9 | 2144/3220 (67%) | 83.3 | 346.8 | length | 3.46 |
| Xc2n | W3-research | 1 | 2048 | 163.0 | 162.9 | 1578/2035 (78%) | 83.8 | 4410.2 | length | 4.28 |
| Xc3n | W1-think | 1 | 3072 | 166.5 | 166.3 | 2021/2941 (69%) | 89.8 | 317.4 | length | 2.84 |
| Xc3n | W2-code | 1 | 3072 | 148.2 | 148.1 | 2026/3254 (62%) | 83.2 | 340.7 | length | 3.10 |
| Xc3n | W3-research | 1 | 2048 | 154.8 | 154.7 | 1512/2019 (75%) | 83.1 | 4408.3 | length | 3.77 |
| M1a | A-edit | 1 | 1148 | 145.5 | 145.4 | 865/1152 (75%) | 71.0 | 2634.4 | tool_calls | 4.06 |
| M1a | B-write | 1 | 3323 | 157.9 | 157.9 | 2326/3350 (69%) | 83.3 | 1622.7 | tool_calls | 3.36 |
| M2a | A-edit | 1 | 416 | 140.3 | 139.9 | 342/382 (90%) | 52.7 | 2637.3 | tool_calls | 5.16 |
| M2a | B-write | 1 | 2064 | 163.1 | 162.5 | 1463/2056 (71%) | 83.4 | 1604.9 | tool_calls | 3.40 |
| M3a | A-edit | 1 | 613 | 132.7 | 131.5 | 466/604 (77%) | 61.0 | 2633.3 | tool_calls | 4.11 |
| M3a | B-write | 1 | 1462 | 186.1 | 185.9 | 1140/1528 (75%) | 84.3 | 1642.0 | tool_calls | 4.73 |
| X1a | A-edit | 1 | 436 | 129.4 | 129.1 | 325/441 (74%) | 63.0 | 2642.9 | tool_calls | 3.94 |
| X1a | B-write | 1 | 1540 | 170.5 | 169.7 | 1149/1624 (71%) | 83.3 | 1631.9 | tool_calls | 4.10 |
| X2a | A-edit | 1 | 588 | 130.9 | 130.7 | 427/590 (72%) | 66.4 | 2638.7 | tool_calls | 3.58 |
| X2a | B-write | 1 | 928 | 181.7 | 181.5 | 725/968 (75%) | 83.5 | 1614.6 | tool_calls | 4.77 |
| X3a | A-edit | 1 | 177 | 127.5 | 126.8 | 147/173 (85%) | 44.4 | 2640.1 | tool_calls | 4.94 |
| X3a | B-write | 1 | 2059 | 158.4 | 158.3 | 1434/2148 (67%) | 83.9 | 1614.3 | tool_calls | 3.43 |
| Xc1a | A-edit | 1 | 331 | 120.1 | 119.7 | 265/334 (79%) | 47.3 | 2347.3 | tool_calls | 4.91 |
| Xc1a | B-write | 1 | 2468 | 157.7 | 157.6 | 1687/2429 (69%) | 84.0 | 1518.9 | tool_calls | 3.09 |
| Xc2a | A-edit | 1 | 474 | 126.0 | 125.8 | 345/480 (72%) | 63.1 | 2351.5 | tool_calls | 3.69 |
| Xc2a | B-write | 1 | 2608 | 161.2 | 161.2 | 1845/2622 (70%) | 83.2 | 1526.1 | tool_calls | 3.43 |
| Xc3a | A-edit | 1 | 419 | 133.2 | 132.9 | 341/401 (85%) | 51.8 | 2344.5 | tool_calls | 5.14 |
| Xc3a | B-write | 1 | 1728 | 159.4 | 159.4 | 1207/1748 (69%) | 83.7 | 1523.5 | tool_calls | 3.32 |
| M1r | R1-verify20k | 1 | 3703 | 150.5 | 150.2 | 2524/3379 (75%) | 82.0 | 4412.7 | stop | 2.90 |
| M1r | R2-report54k | 1 | 2514 | 141.6 | 141.6 | 1734/2622 (66%) | 76.8 | 4524.1 | stop | 3.34 |
| M1r | R3-extract5k | 1 | 1071 | 183.0 | 182.7 | 855/1038 (82%) | 80.5 | 3500.0 | stop | 4.81 |
| M1r | R4-agent33k | 1 | 274 | 130.9 | 128.4 | 200/297 (67%) | 80.5 | 4284.6 | tool_calls | 3.76 |
| M2r | R1-verify20k | 1 | 3461 | 150.9 | 150.7 | 2386/3222 (74%) | 81.9 | 4404.8 | stop | 3.03 |
| M2r | R2-report54k | 1 | 3434 | 156.1 | 156.1 | 2489/3459 (72%) | 74.0 | 4523.7 | stop | 3.66 |
| M2r | R3-extract5k | 1 | 1146 | 172.4 | 172.1 | 879/1130 (78%) | 81.7 | 3489.8 | stop | 4.23 |
| M2r | R4-agent33k | 1 | 393 | 128.2 | 127.9 | 279/435 (64%) | 80.9 | 4281.3 | tool_calls | 3.72 |
| M3r | R1-verify20k | 1 | 3578 | 153.7 | 153.5 | 2487/3286 (76%) | 81.3 | 4406.5 | stop | 3.05 |
| M3r | R2-report54k | 1 | 2600 | 148.1 | 148.1 | 1836/2637 (70%) | 78.6 | 4525.4 | stop | 3.43 |
| M3r | R3-extract5k | 1 | 1522 | 180.3 | 180.1 | 1192/1523 (78%) | 80.5 | 3489.9 | stop | 4.62 |
| M3r | R4-agent33k | 1 | 374 | 127.6 | 127.3 | 261/397 (66%) | 81.5 | 4271.9 | tool_calls | 3.42 |
| X1r | R1-verify20k | 1 | 3803 | 156.5 | 156.3 | 2694/3441 (78%) | 80.7 | 4395.7 | stop | 3.15 |
| X1r | R2-report54k | 1 | 2858 | 142.3 | 141.9 | 1951/2923 (67%) | 76.2 | 4504.5 | stop | 3.21 |
| X1r | R3-extract5k | 1 | 1080 | 178.4 | 177.6 | 840/1066 (79%) | 80.6 | 3485.4 | stop | 4.44 |
| X1r | R4-agent33k | 1 | 315 | 133.7 | 133.2 | 227/333 (68%) | 81.3 | 4275.7 | tool_calls | 3.78 |
| X2r | R1-verify20k | 1 | 3631 | 153.0 | 152.8 | 2540/3358 (76%) | 81.2 | 4381.2 | stop | 3.12 |
| X2r | R2-report54k | 1 | 2864 | 154.2 | 154.1 | 2083/2937 (71%) | 77.4 | 4496.5 | stop | 3.74 |
| X2r | R3-extract5k | 1 | 1085 | 182.7 | 182.4 | 864/1043 (83%) | 81.2 | 3543.9 | stop | 4.72 |
| X2r | R4-agent33k | 1 | 263 | 138.3 | 137.8 | 198/257 (77%) | 80.6 | 4270.2 | tool_calls | 3.84 |
| X3r | R1-verify20k | 1 | 3879 | 158.3 | 158.1 | 2819/3572 (79%) | 80.1 | 4389.4 | stop | 3.41 |
| X3r | R2-report54k | 1 | 4096 | 164.3 | 164.2 | 3089/4114 (75%) | 75.3 | 4504.9 | length | 4.08 |
| X3r | R3-extract5k | 1 | 1033 | 178.2 | 177.9 | 814/1026 (79%) | 81.5 | 3474.7 | stop | 4.68 |
| X3r | R4-agent33k | 1 | 282 | 131.8 | 131.4 | 208/301 (69%) | 80.6 | 4269.5 | tool_calls | 3.91 |
| Xc1r | R1-verify20k | 1 | 3588 | 154.8 | 154.6 | 2521/3307 (76%) | 81.3 | 4362.9 | stop | 3.15 |
| Xc1r | R2-report54k | 1 | 3690 | 154.1 | 154.0 | 2677/3740 (72%) | 78.5 | 4460.0 | stop | 3.69 |
| Xc1r | R3-extract5k | 1 | 1027 | 179.4 | 179.0 | 824/1019 (81%) | 80.9 | 3047.3 | stop | 4.92 |
| Xc1r | R4-agent33k | 1 | 337 | 131.9 | 131.5 | 242/357 (68%) | 79.6 | 4244.0 | tool_calls | 3.57 |
| Xc2r | R1-verify20k | 1 | 3844 | 157.0 | 156.5 | 2768/3552 (78%) | 80.0 | 4352.1 | stop | 3.33 |
| Xc2r | R2-report54k | 1 | 4096 | 155.7 | 155.7 | 2983/4160 (72%) | 77.6 | 4456.7 | length | 3.72 |
| Xc2r | R3-extract5k | 1 | 1039 | 179.2 | 178.8 | 820/1040 (79%) | 81.4 | 3107.1 | stop | 4.75 |
| Xc2r | R4-agent33k | 1 | 402 | 140.4 | 140.0 | 284/403 (70%) | 80.9 | 4242.2 | tool_calls | 3.42 |
| Xc3r | R1-verify20k | 1 | 3717 | 154.9 | 154.7 | 2661/3467 (77%) | 80.6 | 4356.1 | stop | 3.33 |
| Xc3r | R2-report54k | 1 | 3884 | 150.3 | 150.2 | 2762/4070 (68%) | 75.4 | 4459.9 | stop | 3.61 |
| Xc3r | R3-extract5k | 1 | 1165 | 174.3 | 174.0 | 903/1157 (78%) | 82.1 | 3102.9 | stop | 4.42 |
| Xc3r | R4-agent33k | 1 | 539 | 136.9 | 136.7 | 382/588 (65%) | 81.2 | 4237.5 | tool_calls | 3.67 |

- M1n: experts in VRAM at start: 4585 slots / 8.75 GiB
- M2n: experts in VRAM at start: 4585 slots / 8.75 GiB
- M3n: experts in VRAM at start: 4585 slots / 8.75 GiB
- X1n: experts in VRAM at start: 4585 slots / 8.75 GiB
- X2n: experts in VRAM at start: 4585 slots / 8.75 GiB
- X3n: experts in VRAM at start: 4585 slots / 8.75 GiB
- Xc1n: experts in VRAM at start: 4585 slots / 8.75 GiB
- Xc2n: experts in VRAM at start: 4585 slots / 8.75 GiB
- Xc3n: experts in VRAM at start: 4585 slots / 8.75 GiB
- M1a: experts in VRAM at start: 4585 slots / 8.75 GiB
- M2a: experts in VRAM at start: 4585 slots / 8.75 GiB
- M3a: experts in VRAM at start: 4585 slots / 8.75 GiB
- X1a: experts in VRAM at start: 4585 slots / 8.75 GiB
- X2a: experts in VRAM at start: 4585 slots / 8.75 GiB
- X3a: experts in VRAM at start: 4585 slots / 8.75 GiB
- Xc1a: experts in VRAM at start: 4585 slots / 8.75 GiB
- Xc2a: experts in VRAM at start: 4585 slots / 8.75 GiB
- Xc3a: experts in VRAM at start: 4585 slots / 8.75 GiB
- M1r: experts in VRAM at start: 4585 slots / 8.75 GiB
- M2r: experts in VRAM at start: 4585 slots / 8.75 GiB
- M3r: experts in VRAM at start: 4585 slots / 8.75 GiB
- X1r: experts in VRAM at start: 4585 slots / 8.75 GiB
- X2r: experts in VRAM at start: 4585 slots / 8.75 GiB
- X3r: experts in VRAM at start: 4585 slots / 8.75 GiB
- Xc1r: experts in VRAM at start: 4585 slots / 8.75 GiB
- Xc2r: experts in VRAM at start: 4585 slots / 8.75 GiB
- Xc3r: experts in VRAM at start: 4585 slots / 8.75 GiB
