| arm | workload | n | tokens | decode tok/s (client) | decode tok/s (engine) | accepted / drafted | expert-cache hit % | prompt tok/s | finish | drafts per window |
|---|---|---:|---:|---:|---:|---:|---:|---:|---|---:|
| M1n | W1-think | 1 | 3072 | 167.7 | 167.5 | 2018/2854 (71%) | 89.2 | 381.1 | length | 2.75 |
| M1n | W2-code | 1 | 3072 | 162.1 | 162.0 | 2159/3195 (68%) | 84.6 | 391.7 | length | 3.49 |
| M1n | W3-research | 1 | 2048 | 161.1 | 160.9 | 1569/1998 (79%) | 83.9 | 4449.1 | length | 4.17 |
| M2n | W1-think | 1 | 3072 | 162.1 | 161.9 | 1976/2882 (69%) | 89.3 | 347.6 | length | 2.66 |
| M2n | W2-code | 1 | 3072 | 155.5 | 155.4 | 2091/3263 (64%) | 84.0 | 389.6 | length | 3.33 |
| M2n | W3-research | 1 | 2048 | 165.3 | 165.2 | 1585/1989 (80%) | 84.3 | 4456.4 | length | 4.28 |
| A1n | W1-think | 1 | 3072 | 161.7 | 161.6 | 2265/3701 (61%) | 88.0 | 337.9 | length | - |
| A1n | W2-code | 1 | 3072 | 143.7 | 143.6 | 2157/3715 (58%) | 85.0 | 343.9 | length | - |
| A1n | W3-research | 1 | 2048 | 151.1 | 151.0 | 1589/2261 (70%) | 82.6 | 4225.2 | length | - |
| A2n | W1-think | 1 | 3072 | 168.7 | 168.6 | 2336/3662 (64%) | 88.3 | 329.1 | length | - |
| A2n | W2-code | 1 | 3072 | 137.6 | 137.5 | 2141/3911 (55%) | 84.9 | 346.7 | length | - |
| A2n | W3-research | 1 | 2048 | 144.4 | 144.3 | 1543/2318 (67%) | 83.3 | 4223.8 | length | - |
| B1n | W1-think | 1 | 3072 | 147.4 | 147.2 | 2020/3542 (57%) | 90.4 | 336.1 | length | - |
| B1n | W2-code | 1 | 3072 | 134.2 | 134.2 | 2110/3940 (54%) | 82.4 | 329.1 | length | - |
| B1n | W3-research | 1 | 2048 | 138.9 | 138.8 | 1544/2452 (63%) | 83.0 | 4224.6 | length | - |
| B2n | W1-think | 1 | 3072 | 164.7 | 164.5 | 2296/3842 (60%) | 89.2 | 333.7 | length | - |
| B2n | W2-code | 1 | 3072 | 143.0 | 142.9 | 2188/3920 (56%) | 88.3 | 344.1 | length | - |
| B2n | W3-research | 1 | 2048 | 147.2 | 147.1 | 1594/2321 (69%) | 84.9 | 4220.0 | length | - |
| M1a | A-edit | 1 | 335 | 125.3 | 124.9 | 272/333 (82%) | 47.4 | 2639.0 | tool_calls | 5.20 |
| M1a | B-write | 1 | 1458 | 162.9 | 162.8 | 1053/1492 (71%) | 82.4 | 1604.2 | tool_calls | 3.68 |
| M2a | A-edit | 1 | 303 | 119.4 | 119.0 | 243/311 (78%) | 46.8 | 2630.0 | tool_calls | 5.02 |
| M2a | B-write | 1 | 1839 | 154.4 | 154.3 | 1269/1857 (68%) | 82.6 | 1604.1 | tool_calls | 3.26 |
| A1a | A-edit | 1 | 474 | 124.2 | 123.9 | 336/487 (69%) | 64.9 | 2342.3 | tool_calls | - |
| A1a | B-write | 1 | 1526 | 161.8 | 161.7 | 1135/1735 (65%) | 85.3 | 1545.3 | tool_calls | - |
| A2a | A-edit | 1 | 340 | 112.9 | 112.6 | 264/351 (75%) | 51.8 | 2353.6 | tool_calls | - |
| A2a | B-write | 1 | 2700 | 147.2 | 146.9 | 1915/3057 (63%) | 83.5 | 1519.7 | tool_calls | - |
| B1a | A-edit | 1 | 421 | 127.3 | 127.0 | 346/420 (82%) | 51.2 | 2341.0 | tool_calls | - |
| B1a | B-write | 1 | 1283 | 166.4 | 166.2 | 1003/1436 (70%) | 83.7 | 1510.7 | tool_calls | - |
| B2a | A-edit | 1 | 178 | 112.1 | 111.6 | 147/184 (80%) | 44.7 | 2340.4 | tool_calls | - |
| B2a | B-write | 1 | 1571 | 135.7 | 135.6 | 1110/2053 (54%) | 83.7 | 1499.9 | tool_calls | - |
| M1r | R1-verify20k | 1 | 3657 | 153.2 | 152.7 | 2552/3309 (77%) | 80.7 | 4411.1 | stop | 3.03 |
| M1r | R2-report54k | 1 | 3288 | 154.6 | 154.2 | 2363/3358 (70%) | 76.8 | 4520.1 | stop | 3.61 |
| M1r | R3-extract5k | 1 | 986 | 175.4 | 175.1 | 772/975 (79%) | 82.1 | 3499.1 | stop | 4.56 |
| M1r | R4-agent33k | 1 | 348 | 134.1 | 132.1 | 253/377 (67%) | 80.0 | 4290.9 | tool_calls | 3.73 |
| M2r | R1-verify20k | 1 | 3829 | 156.1 | 156.0 | 2713/3494 (78%) | 81.3 | 4416.6 | stop | 3.18 |
| M2r | R2-report54k | 1 | 3347 | 153.2 | 152.8 | 2397/3382 (71%) | 76.9 | 4527.0 | stop | 3.55 |
| M2r | R3-extract5k | 1 | 978 | 182.3 | 181.9 | 777/960 (81%) | 81.6 | 3506.7 | stop | 4.78 |
| M2r | R4-agent33k | 1 | 341 | 132.0 | 131.7 | 241/375 (64%) | 81.2 | 4283.8 | tool_calls | 3.68 |
| A1r | R1-verify20k | 1 | 3862 | 140.2 | 140.0 | 2639/3782 (70%) | 80.8 | 4192.3 | stop | - |
| A1r | R2-report54k | 1 | 2578 | 127.0 | 126.9 | 1792/3218 (56%) | 77.3 | 4271.5 | stop | - |
| A1r | R3-extract5k | 1 | 1108 | 168.5 | 168.2 | 877/1150 (76%) | 80.3 | 2980.9 | stop | - |
| A1r | R4-agent33k | 1 | 379 | 130.6 | 130.3 | 269/448 (60%) | 80.3 | 4073.5 | tool_calls | - |
| A2r | R1-verify20k | 1 | 3864 | 138.7 | 138.2 | 2646/3828 (69%) | 80.4 | 4178.6 | stop | - |
| A2r | R2-report54k | 1 | 2386 | 126.5 | 126.2 | 1621/2995 (54%) | 75.1 | 4268.4 | stop | - |
| A2r | R3-extract5k | 1 | 1200 | 159.8 | 159.6 | 935/1308 (71%) | 81.5 | 2948.0 | stop | - |
| A2r | R4-agent33k | 1 | 327 | 123.8 | 123.4 | 236/361 (65%) | 80.5 | 4074.6 | tool_calls | - |
| B1r | R1-verify20k | 1 | 3855 | 142.0 | 141.8 | 2706/3918 (69%) | 82.0 | 4190.5 | stop | - |
| B1r | R2-report54k | 1 | 3822 | 135.2 | 135.2 | 2775/4722 (59%) | 77.0 | 4269.9 | stop | - |
| B1r | R3-extract5k | 1 | 1333 | 164.9 | 164.7 | 1051/1401 (75%) | 82.2 | 2998.0 | stop | - |
| B1r | R4-agent33k | 1 | 413 | 107.1 | 106.9 | 281/537 (52%) | 81.4 | 4071.9 | tool_calls | - |
| B2r | R1-verify20k | 1 | 3634 | 139.9 | 139.7 | 2596/3798 (68%) | 80.3 | 4182.2 | stop | - |
| B2r | R2-report54k | 1 | 3311 | 127.9 | 127.8 | 2371/4335 (55%) | 75.0 | 4266.5 | stop | - |
| B2r | R3-extract5k | 1 | 849 | 144.9 | 144.7 | 617/936 (66%) | 81.7 | 2998.3 | stop | - |
| B2r | R4-agent33k | 1 | 326 | 113.4 | 113.2 | 233/455 (51%) | 81.4 | 4070.3 | tool_calls | - |

- M1n: experts in VRAM at start: 4585 slots / 8.75 GiB
- M2n: experts in VRAM at start: 4585 slots / 8.75 GiB
- A1n: experts in VRAM at start: 4586 slots / 8.75 GiB
- A2n: experts in VRAM at start: 4586 slots / 8.75 GiB
- B1n: experts in VRAM at start: 4585 slots / 8.75 GiB
- B2n: experts in VRAM at start: 4585 slots / 8.75 GiB
- M1a: experts in VRAM at start: 4585 slots / 8.75 GiB
- M2a: experts in VRAM at start: 4585 slots / 8.75 GiB
- A1a: experts in VRAM at start: 4586 slots / 8.75 GiB
- A2a: experts in VRAM at start: 4586 slots / 8.75 GiB
- B1a: experts in VRAM at start: 4585 slots / 8.75 GiB
- B2a: experts in VRAM at start: 4585 slots / 8.75 GiB
- M1r: experts in VRAM at start: 4585 slots / 8.75 GiB
- M2r: experts in VRAM at start: 4585 slots / 8.75 GiB
- A1r: experts in VRAM at start: 4586 slots / 8.75 GiB
- A2r: experts in VRAM at start: 4586 slots / 8.75 GiB
- B1r: experts in VRAM at start: 4585 slots / 8.75 GiB
- B2r: experts in VRAM at start: 4585 slots / 8.75 GiB
