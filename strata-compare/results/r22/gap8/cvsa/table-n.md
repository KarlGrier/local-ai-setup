| arm | workload | n | tokens | decode tok/s (client) | decode tok/s (engine) | accepted / drafted | expert-cache hit % | prompt tok/s | finish | drafts per window |
|---|---|---:|---:|---:|---:|---:|---:|---:|---|---:|
| An | W1-think | 4 | 3072.0 | 167.9 | 172.1 | 8090/10492 (77%) | 74.9 | 316.0 | length | 2.54 |
| An | W2-code | 4 | 3072.0 | 157.1 | 156.9 | 8171/10985 (74%) | 79.1 | 332.1 | length | 2.67 |
| An | W3-research | 4 | 2048.0 | 150.0 | 149.9 | 5631/7015 (80%) | 75.8 | 4177.5 | length | 2.73 |
| Cn | W1-think | 4 | 3072.0 | 177.3 | 186.7 | 8982/12299 (73%) | 78.7 | 315.1 | length | 3.79 |
| Cn | W2-code | 4 | 3072.0 | 156.9 | 156.8 | 8742/12899 (68%) | 79.7 | 335.4 | length | 3.63 |
| Cn | W3-research | 4 | 2048.0 | 155.6 | 155.5 | 6289/7958 (79%) | 76.1 | 4180.3 | length | 4.17 |
| PAn | W1-think | 4 | 3072.0 | 164.3 | 165.1 | 7869/10599 (74%) | 81.3 | 320.5 | length | 2.43 |
| PAn | W2-code | 4 | 3072.0 | 158.0 | 157.9 | 8025/11291 (71%) | 83.4 | 337.4 | length | 2.64 |
| PAn | W3-research | 4 | 2048.0 | 156.6 | 156.4 | 5690/6930 (82%) | 83.3 | 4182.4 | length | 2.76 |
| PCn | W1-think | 4 | 3072.0 | 167.5 | 167.4 | 8471/11689 (72%) | 81.3 | 318.1 | length | 3.11 |
| PCn | W2-code | 4 | 3072.0 | 162.2 | 162.1 | 8944/12642 (71%) | 80.8 | 333.9 | length | 3.77 |
| PCn | W3-research | 4 | 2048.0 | 158.4 | 158.2 | 6268/8090 (77%) | 83.6 | 4183.4 | length | 4.19 |

- An: experts in VRAM at start: 4484 slots / 8.55 GiB
- Cn: experts in VRAM at start: 4482 slots / 8.55 GiB
- PAn: experts in VRAM at start: 4484 slots / 8.55 GiB
- PCn: experts in VRAM at start: 4482 slots / 8.55 GiB
