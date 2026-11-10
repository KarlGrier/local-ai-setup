| arm | workload | n | tokens | decode tok/s (client) | decode tok/s (engine) | accepted / drafted | expert-cache hit % | prompt tok/s | finish | drafts per window |
|---|---|---:|---:|---:|---:|---:|---:|---:|---|---:|
| Ar | R1-verify20k | 4 | 3746.0 | 146.1 | 149.7 | 10043/12283 (82%) | 73.2 | 4148.4 | stop | 2.44 |
| Cr | R1-verify20k | 4 | 3793.5 | 146.4 | 148.8 | 10571/13839 (76%) | 71.4 | 4152.6 | stop | 3.08 |
| PAr | R1-verify20k | 4 | 3798.0 | 151.1 | 150.8 | 9974/12398 (80%) | 78.7 | 4153.3 | stop | 2.39 |
| PCr | R1-verify20k | 4 | 3695.0 | 151.6 | 154.7 | 10608/13745 (77%) | 78.5 | 4153.5 | stop | 3.16 |

- Ar: experts in VRAM at start: 4484 slots / 8.55 GiB
- Cr: experts in VRAM at start: 4482 slots / 8.55 GiB
- PAr: experts in VRAM at start: 4484 slots / 8.55 GiB
- PCr: experts in VRAM at start: 4482 slots / 8.55 GiB
