| arm | workload | n | tokens | decode tok/s (client) | decode tok/s (engine) | accepted / drafted | expert-cache hit % | prompt tok/s | finish | drafts per window |
|---|---|---:|---:|---:|---:|---:|---:|---:|---|---:|
| B1r | R2-report54k | 2 | 3656.5 | 150.2 | 149.9 | 5210/7499 (69%) | 81.5 | 4509.7 | stop | 3.55 |
| B1r | R3-extract5k | 2 | 1045.5 | 169.8 | 168.9 | 1607/2100 (77%) | 80.2 | 3573.2 | stop | 4.34 |
| B2r | R2-report54k | 2 | 3218.5 | 149.2 | 148.9 | 4570/6589 (69%) | 81.2 | 4509.0 | stop | 3.52 |
| B2r | R3-extract5k | 2 | 1287.0 | 180.9 | 180.2 | 2044/2534 (81%) | 81.0 | 3583.1 | stop | 4.75 |
| B3r | R2-report54k | 2 | 3565.0 | 153.8 | 153.8 | 5124/7103 (72%) | 81.5 | 4508.1 | stop | 3.53 |
| B3r | R3-extract5k | 2 | 1151.0 | 180.5 | 180.2 | 1848/2254 (82%) | 79.7 | 3585.3 | stop | 4.96 |
| B4r | R2-report54k | 2 | 3075.5 | 158.0 | 157.6 | 4522/6222 (73%) | 81.4 | 4509.1 | stop | 3.80 |
| B4r | R3-extract5k | 2 | 1277.5 | 180.5 | 180.2 | 1999/2500 (80%) | 82.0 | 3530.9 | stop | 4.50 |
| Boff1r | R2-report54k | 2 | 2688.5 | 148.0 | 147.9 | 3861/5544 (70%) | 80.3 | 4510.5 | stop | 3.64 |
| Boff1r | R3-extract5k | 2 | 1192.0 | 184.2 | 183.9 | 1902/2312 (82%) | 81.2 | 3854.3 | stop | 4.80 |
| Boff2r | R2-report54k | 2 | 3568.0 | 154.4 | 154.1 | 5208/7249 (72%) | 80.8 | 4512.1 | stop | 3.75 |
| Boff2r | R3-extract5k | 2 | 1161.0 | 174.7 | 174.4 | 1824/2318 (79%) | 80.2 | 3858.1 | stop | 4.65 |
| P1r | R2-report54k | 2 | 3061.0 | 149.7 | 149.7 | 4376/6252 (70%) | 80.8 | 4510.8 | stop | 3.57 |
| P1r | R3-extract5k | 2 | 983.0 | 173.3 | 172.9 | 1548/1931 (80%) | 78.8 | 3528.0 | stop | 4.61 |
| P2r | R2-report54k | 2 | 2533.0 | 147.9 | 147.8 | 3646/5238 (70%) | 79.8 | 4506.9 | stop | 3.67 |
| P2r | R3-extract5k | 2 | 989.0 | 175.6 | 175.2 | 1562/1943 (80%) | 79.6 | 3520.4 | stop | 4.63 |
| P3r | R2-report54k | 2 | 4058.5 | 153.6 | 153.6 | 6003/8294 (72%) | 80.2 | 4508.5 | length,stop | 3.95 |
| P3r | R3-extract5k | 2 | 1115.5 | 178.9 | 178.6 | 1772/2174 (82%) | 79.2 | 3549.8 | stop | 4.74 |
| P4r | R2-report54k | 2 | 3444.0 | 150.3 | 150.1 | 4993/7075 (71%) | 80.4 | 4511.5 | stop | 3.72 |
| P4r | R3-extract5k | 2 | 1039.0 | 176.7 | 176.4 | 1632/2055 (79%) | 80.7 | 3536.2 | stop | 4.61 |
| Poff1r | R2-report54k | 2 | 2703.0 | 145.7 | 145.6 | 3799/5578 (68%) | 80.9 | 4514.0 | stop | 3.46 |
| Poff1r | R3-extract5k | 2 | 1073.0 | 173.7 | 173.4 | 1670/2134 (78%) | 80.8 | 3864.8 | stop | 4.48 |
| Poff2r | R2-report54k | 2 | 2959.5 | 148.0 | 147.8 | 4242/6233 (68%) | 81.0 | 4511.6 | stop | 3.70 |
| Poff2r | R3-extract5k | 2 | 1078.0 | 179.5 | 179.2 | 1721/2115 (81%) | 80.2 | 3865.3 | stop | 4.86 |

- B1r: experts in VRAM at start: 4585 slots / 8.75 GiB
- B2r: experts in VRAM at start: 4585 slots / 8.75 GiB
- B3r: experts in VRAM at start: 4585 slots / 8.75 GiB
- B4r: experts in VRAM at start: 4585 slots / 8.75 GiB
- Boff1r: experts in VRAM at start: 4585 slots / 8.75 GiB
- Boff2r: experts in VRAM at start: 4585 slots / 8.75 GiB
- P1r: experts in VRAM at start: 4585 slots / 8.75 GiB
- P2r: experts in VRAM at start: 4585 slots / 8.75 GiB
- P3r: experts in VRAM at start: 4585 slots / 8.75 GiB
- P4r: experts in VRAM at start: 4585 slots / 8.75 GiB
- Poff1r: experts in VRAM at start: 4585 slots / 8.75 GiB
- Poff2r: experts in VRAM at start: 4585 slots / 8.75 GiB
