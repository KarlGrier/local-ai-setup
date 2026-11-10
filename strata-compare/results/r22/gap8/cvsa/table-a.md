| arm | workload | n | tokens | decode tok/s (client) | decode tok/s (engine) | accepted / drafted | expert-cache hit % | prompt tok/s | finish | drafts per window |
|---|---|---:|---:|---:|---:|---:|---:|---:|---|---:|
| Aa | A-edit | 4 | 330.5 | 116.1 | 114.2 | 939/1153 (81%) | 44.9 | 2613.0 | tool_calls | 2.79 |
| Aa | B-write | 4 | 1685.0 | 161.0 | 160.4 | 5064/6718 (75%) | 78.8 | 1522.0 | tool_calls | 2.59 |
| Ca | A-edit | 4 | 235.5 | 122.0 | 121.2 | 1034/1319 (78%) | 37.3 | 2617.9 | tool_calls | 4.31 |
| Ca | B-write | 4 | 2170.5 | 156.1 | 155.8 | 6511/9172 (71%) | 75.8 | 1498.7 | tool_calls | 3.66 |
| PAa | A-edit | 4 | 308.5 | 130.7 | 128.7 | 918/1005 (91%) | 55.0 | 2622.9 | tool_calls | 2.90 |
| PAa | B-write | 4 | 2672.0 | 154.5 | 154.2 | 6816/9077 (75%) | 81.9 | 1509.0 | tool_calls | 2.58 |
| PCa | A-edit | 4 | 499.0 | 130.6 | 128.5 | 1291/1670 (77%) | 58.8 | 2609.6 | tool_calls | 4.14 |
| PCa | B-write | 4 | 2892.0 | 159.0 | 158.7 | 8032/11481 (70%) | 82.5 | 1520.0 | tool_calls | 3.59 |

- Aa: experts in VRAM at start: 4484 slots / 8.55 GiB
- Ca: experts in VRAM at start: 4482 slots / 8.55 GiB
- PAa: experts in VRAM at start: 4484 slots / 8.55 GiB
- PCa: experts in VRAM at start: 4482 slots / 8.55 GiB
