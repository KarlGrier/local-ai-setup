| arm | workload | n | tokens | decode tok/s (client) | decode tok/s (engine) | accepted / drafted | expert-cache hit % | prompt tok/s | finish | drafts per window |
|---|---|---:|---:|---:|---:|---:|---:|---:|---|---:|
| dAa | A-edit | 2 | 54.5 | 105.4 | 97.6 | 73/99 (74%) | 38.9 | 2519.5 | tool_calls | 2.48 |
| dAa | B-write | 2 | 58.0 | 130.7 | 120.8 | 81/104 (78%) | 56.4 | 1423.9 | tool_calls | 2.67 |
| dBa | A-edit | 2 | 51.0 | 106.4 | 98.7 | 78/97 (80%) | 34.6 | 2468.7 | tool_calls | 3.23 |
| dBa | B-write | 2 | 78.0 | 116.8 | 115.3 | 121/170 (71%) | 52.2 | 1370.2 | tool_calls | 4.59 |
| dCa | A-edit | 2 | 59.5 | 107.6 | 106.2 | 87/111 (78%) | 38.5 | 2523.8 | tool_calls | 3.08 |
| dCa | B-write | 2 | 59.5 | 121.4 | 120.0 | 88/123 (72%) | 53.8 | 1418.5 | tool_calls | 3.73 |
| dDa | A-edit | 2 | 68.0 | 109.1 | 107.8 | 87/107 (81%) | 43.5 | 2519.4 | tool_calls | 2.10 |
| dDa | B-write | 2 | 58.0 | 139.7 | 131.4 | 91/107 (85%) | 54.8 | 1420.3 | tool_calls | 3.69 |

- dAa: experts in VRAM at start: 4365 slots / 8.33 GiB
- dBa: experts in VRAM at start: 4393 slots / 8.38 GiB
- dCa: experts in VRAM at start: 4393 slots / 8.38 GiB
- dDa: experts in VRAM at start: 4393 slots / 8.38 GiB
