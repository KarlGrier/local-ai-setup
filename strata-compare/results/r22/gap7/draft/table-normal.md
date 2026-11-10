| arm | workload | n | tokens | decode tok/s (client) | decode tok/s (engine) | accepted / drafted | expert-cache hit % | prompt tok/s | finish | drafts per window |
|---|---|---:|---:|---:|---:|---:|---:|---:|---|---:|
| dAn | W1-think | 2 | 3072.0 | 145.4 | 143.3 | 2818/3651 (77%) | 77.9 | 299.1 | length | 2.38 |
| dAn | W2-code | 2 | 3072.0 | 146.9 | 147.2 | 1912/2620 (73%) | 80.8 | 316.9 | length | 2.29 |
| dAn | W3-research | 2 | 2048.0 | 150.4 | 148.3 | 2442/3553 (69%) | 77.8 | 4187.8 | length | 2.57 |
| dBn | W1-think | 2 | 3072.0 | 156.3 | 150.0 | 3099/4587 (68%) | 77.5 | 317.2 | length | 3.65 |
| dBn | W2-code | 2 | 3072.0 | 148.4 | 153.9 | 2097/3263 (64%) | 81.4 | 319.9 | length | 3.41 |
| dBn | W3-research | 2 | 2048.0 | 146.3 | 152.8 | 2863/4337 (66%) | 75.3 | 3929.6 | length | 4.50 |
| dCn | W1-think | 2 | 3072.0 | 170.7 | 159.9 | 3040/4207 (72%) | 77.9 | 315.7 | length | 3.19 |
| dCn | W2-code | 2 | 3072.0 | 151.2 | 175.7 | 2253/3128 (72%) | 81.0 | 330.6 | length | 3.90 |
| dCn | W3-research | 2 | 2048.0 | 151.5 | 159.6 | 2703/3934 (69%) | 76.8 | 4188.4 | length | 3.49 |
| dDn | W1-think | 2 | 3072.0 | 156.5 | 163.1 | 2913/3638 (80%) | 78.5 | 316.8 | length | 2.51 |
| dDn | W2-code | 2 | 3072.0 | 160.7 | 158.1 | 1880/2493 (75%) | 81.1 | 332.9 | length | 2.11 |
| dDn | W3-research | 2 | 2048.0 | 161.2 | 165.4 | 2784/3732 (75%) | 76.6 | 4189.4 | length | 3.56 |

- dAn: experts in VRAM at start: 4365 slots / 8.33 GiB
- dBn: experts in VRAM at start: 4393 slots / 8.38 GiB
- dCn: experts in VRAM at start: 4393 slots / 8.38 GiB
- dDn: experts in VRAM at start: 4393 slots / 8.38 GiB
