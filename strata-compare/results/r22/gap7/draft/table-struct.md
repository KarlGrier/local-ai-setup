| arm | workload | n | tokens | decode tok/s (client) | decode tok/s (engine) | accepted / drafted | expert-cache hit % | prompt tok/s | finish | drafts per window |
|---|---|---:|---:|---:|---:|---:|---:|---:|---|---:|
| dAst | C-struct | 1 | 7230 | 190.6 | 190.5 | 5360/5606 (96%) | 79.1 | 273.3 | stop | 3.00 |
| dBst | C-struct | 1 | 7230 | 210.6 | 210.6 | 6124/6513 (94%) | 78.7 | 265.0 | stop | 5.87 |
| dCst | C-struct | 1 | 7230 | 224.9 | 224.5 | 6159/6367 (97%) | 79.0 | 275.5 | stop | 5.92 |
| dDst | C-struct | 1 | 7230 | 224.8 | 224.8 | 6107/6232 (98%) | 79.3 | 275.4 | stop | 5.54 |

- dAst: experts in VRAM at start: 4365 slots / 8.33 GiB
- dBst: experts in VRAM at start: 4393 slots / 8.38 GiB
- dCst: experts in VRAM at start: 4393 slots / 8.38 GiB
- dDst: experts in VRAM at start: 4393 slots / 8.38 GiB
