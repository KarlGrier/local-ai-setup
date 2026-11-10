| arm | workload | n | tokens | decode tok/s (client) | decode tok/s (engine) | accepted / drafted | expert-cache hit % | prompt tok/s | finish | drafts per window |
|---|---|---:|---:|---:|---:|---:|---:|---:|---|---:|
| Bs3a | A-edit | 1 | 496 | 119.7 | 119.4 | 367/462 (79%) | 57.0 | 2502.5 | tool_calls | 3.53 |
| Bs3a | B-write | 1 | 2805 | 139.5 | 139.4 | 2009/2795 (72%) | 74.9 | 1637.3 | tool_calls | 3.50 |
| Bs3n | W1-think | 1 | 3072 | 154.3 | 154.3 | 2046/2878 (71%) | 85.3 | 365.8 | length | 2.86 |
| Bs3n | W2-code | 1 | 3072 | 132.8 | 132.7 | 2109/3174 (66%) | 78.2 | 383.7 | length | 3.29 |
| Bs3n | W3-research | 1 | 2048 | 144.9 | 144.8 | 1595/1948 (82%) | 74.7 | 4424.5 | length | 4.30 |
| Bs3r | R1-verify20k | 1 | 3615 | 133.4 | 133.2 | 2536/3330 (76%) | 73.3 | 4376.3 | stop | 3.13 |
| Bs3r | R2-report54k | 1 | 3806 | 131.7 | 131.4 | 2796/3829 (73%) | 72.2 | 4497.6 | stop | 3.78 |
| Bs3r | R3-extract5k | 1 | 1065 | 150.8 | 150.2 | 843/1042 (81%) | 72.3 | 3430.5 | stop | 4.69 |
| Bs3r | R4-agent33k | 1 | 286 | 114.1 | 113.8 | 206/300 (69%) | 72.1 | 4262.1 | tool_calls | 3.70 |
| L3a | A-edit | 1 | 191 | 123.9 | 123.4 | 150/188 (80%) | 45.6 | 2649.8 | tool_calls | 4.59 |
| L3a | B-write | 1 | 1983 | 144.9 | 144.9 | 1233/2011 (61%) | 84.6 | 1617.5 | tool_calls | 2.67 |
| L3n | W1-think | 1 | 3072 | 172.4 | 172.2 | 2054/2878 (71%) | 89.7 | 371.2 | length | 2.87 |
| L3n | W2-code | 1 | 3072 | 150.9 | 150.9 | 2075/3299 (63%) | 81.6 | 383.2 | length | 3.31 |
| L3n | W3-research | 1 | 2048 | 160.3 | 160.2 | 1552/2019 (77%) | 81.9 | 4430.9 | length | 4.05 |
| L3r | R1-verify20k | 1 | 3638 | 157.2 | 157.1 | 2570/3336 (77%) | 81.3 | 4398.7 | stop | 3.17 |
| L3r | R2-report54k | 1 | 2949 | 147.7 | 147.7 | 2078/3007 (69%) | 71.7 | 4499.1 | stop | 3.44 |
| L3r | R3-extract5k | 1 | 947 | 174.6 | 174.3 | 742/969 (77%) | 79.7 | 3473.5 | stop | 4.73 |
| L3r | R4-agent33k | 1 | 279 | 141.4 | 140.9 | 210/286 (73%) | 79.6 | 4265.9 | tool_calls | 4.03 |
| LO3a | A-edit | 1 | 358 | 125.5 | 125.2 | 284/369 (77%) | 52.0 | 2636.3 | tool_calls | 4.92 |
| LO3a | B-write | 1 | 2204 | 162.1 | 162.1 | 1608/2308 (70%) | 82.3 | 1627.6 | tool_calls | 3.85 |
| LO3n | W1-think | 1 | 3072 | 172.9 | 172.7 | 2056/2798 (73%) | 89.8 | 350.6 | length | 2.80 |
| LO3n | W2-code | 1 | 3072 | 170.5 | 170.4 | 2253/3177 (71%) | 82.3 | 383.3 | length | 3.86 |
| LO3n | W3-research | 1 | 2048 | 166.6 | 166.4 | 1591/1960 (81%) | 83.6 | 4425.6 | length | 4.29 |
| LO3r | R1-verify20k | 1 | 3552 | 156.6 | 156.1 | 2535/3285 (77%) | 80.0 | 4381.2 | stop | 3.28 |
| LO3r | R2-report54k | 1 | 2830 | 155.2 | 155.1 | 2044/2849 (72%) | 77.7 | 4501.4 | stop | 3.62 |
| LO3r | R3-extract5k | 1 | 968 | 174.1 | 173.8 | 745/966 (77%) | 81.1 | 3468.7 | stop | 4.33 |
| LO3r | R4-agent33k | 1 | 413 | 135.6 | 135.3 | 294/441 (67%) | 81.3 | 4264.5 | tool_calls | 3.64 |

- Bs3a: experts in VRAM at start: 4585 slots / 8.75 GiB
- Bs3n: experts in VRAM at start: 4585 slots / 8.75 GiB
- Bs3r: experts in VRAM at start: 4585 slots / 8.75 GiB
- L3a: experts in VRAM at start: 4585 slots / 8.75 GiB
- L3n: experts in VRAM at start: 4585 slots / 8.75 GiB
- L3r: experts in VRAM at start: 4585 slots / 8.75 GiB
- LO3a: experts in VRAM at start: 4585 slots / 8.75 GiB
- LO3n: experts in VRAM at start: 4585 slots / 8.75 GiB
- LO3r: experts in VRAM at start: 4585 slots / 8.75 GiB
