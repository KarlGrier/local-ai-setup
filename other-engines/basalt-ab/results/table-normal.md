| arm | workload | n | tokens | decode tok/s (client) | decode tok/s (engine) | accepted / drafted | expert-cache hit % | prompt tok/s | finish |
|---|---|---:|---:|---:|---:|---:|---:|---:|---|
| a | W1-think | 2 | 3072.0 | 175.1 | 175.0 | 3978/5270 (75%) | 85.5 | 295.1 | length |
| a | W2-code | 2 | 3072.0 | 153.8 | 153.8 | 4064/5457 (74%) | 76.1 | 328.6 | length |
| a | W3-research | 2 | 2048.0 | 152.3 | 152.2 | 2842/3509 (81%) | 71.8 | 4258.8 | length |
| a | W4-prefill32k-0 | 2 | 32.0 | 102.6 | 100.5 | 42/59 (71%) | 42.8 | 4307.4 | length |
| a | W4-prefill32k-1 | 2 | 32.0 | 111.8 | 110.2 | 39/64 (61%) | 65.2 | 4354.5 | length |
| a1 | W1-think | 2 | 3072.0 | 147.6 | 147.5 | 3746/5226 (72%) | 80.2 | 287.1 | length |
| a1 | W2-code | 2 | 3072.0 | 139.5 | 139.4 | 4072/5462 (75%) | 71.9 | 322.2 | length |
| a1 | W3-research | 2 | 2048.0 | 126.7 | 126.7 | 2821/3525 (80%) | 63.0 | 4250.1 | length |
| a1 | W4-prefill32k-0 | 2 | 32.0 | 88.3 | 86.2 | 41/59 (69%) | 31.0 | 4301.6 | length |
| a1 | W4-prefill32k-1 | 2 | 32.0 | 104.6 | 102.4 | 41/57 (72%) | 53.4 | 4347.4 | length |
| b4 | W1-think | 2 | 3072.0 | 178.3 | 178.1 | 4134/5213 (79%) | 83.5 | 291.6 | length |
| b4 | W2-code | 2 | 3072.0 | 155.5 | 155.4 | 4036/5516 (73%) | 77.4 | 331.0 | length |
| b4 | W3-research | 2 | 2048.0 | 152.3 | 152.2 | 2863/3409 (84%) | 70.0 | 4255.4 | length |
| b4 | W4-prefill32k-0 | 2 | 32.0 | 107.0 | 104.3 | 42/59 (71%) | 42.0 | 4305.6 | length |
| b4 | W4-prefill32k-1 | 2 | 32.0 | 138.6 | 134.5 | 43/55 (78%) | 66.8 | 4351.6 | length |
| b5 | W1-think | 2 | 3072.0 | 166.4 | 166.4 | 3894/5298 (73%) | 85.5 | 289.5 | length |
| b5 | W2-code | 2 | 3072.0 | 149.5 | 149.4 | 4011/5604 (72%) | 76.5 | 328.9 | length |
| b5 | W3-research | 2 | 2048.0 | 149.5 | 149.4 | 2828/3481 (81%) | 71.7 | 4258.6 | length |
| b5 | W4-prefill32k-0 | 2 | 32.0 | 118.2 | 114.6 | 42/50 (84%) | 43.9 | 4302.8 | length |
| b5 | W4-prefill32k-1 | 2 | 32.0 | 136.4 | 132.8 | 47/54 (87%) | 64.5 | 4350.5 | length |
| b7 | W1-think | 2 | 3072.0 | 182.9 | 182.9 | 4315/5173 (83%) | 82.7 | 294.3 | length |
| b7 | W2-code | 2 | 3072.0 | 152.2 | 152.1 | 4084/5491 (74%) | 76.2 | 324.6 | length |
| b7 | W3-research | 2 | 2048.0 | 152.5 | 152.4 | 2889/3419 (84%) | 70.7 | 4249.2 | length |
| b7 | W4-prefill32k-0 | 2 | 32.0 | 106.3 | 103.6 | 41/53 (77%) | 36.5 | 4302.6 | length |
| b7 | W4-prefill32k-1 | 2 | 32.0 | 110.9 | 109.2 | 42/61 (69%) | 61.8 | 4350.5 | length |
| b7v | W1-think | 1 | 3072 | 165.7 | 165.6 | 1984/2674 (74%) | 85.7 | 311.8 | length |
| b7v | W2-code | 1 | 3072 | 147.5 | 147.5 | 1957/2829 (69%) | 79.8 | 334.4 | length |
| b7v | W3-research | 1 | 2048 | 152.1 | 152.0 | 1449/1703 (85%) | 71.8 | 4188.8 | length |
| b7v | W4-prefill32k-0 | 1 | 32 | 113.8 | 110.8 | 22/26 (85%) | 40.3 | 4245.9 | length |
| b7v | W4-prefill32k-1 | 1 | 32 | 136.9 | 133.6 | 21/22 (95%) | 60.8 | 4347.4 | length |
| vcpu | W1-think | 2 | 3072.0 | 160.9 | - | - | - | 305.0 | length |
| vcpu | W2-code | 2 | 3072.0 | 157.7 | - | - | - | 328.8 | length |
| vgpu | W1-think | 2 | 3072.0 | 159.0 | - | - | - | 306.4 | length |
| vgpu | W2-code | 2 | 3072.0 | 154.2 | - | - | - | 327.1 | length |
| c1 | W1-think | 2 | 3072.0 | 156.8 | - | - | - | 381.5 | length |
| c1 | W2-code | 2 | 3072.0 | 135.4 | - | - | - | 396.5 | length |
| c1 | W3-research | 2 | 2048.0 | 129.8 | - | - | - | 4927.9 | length |
| c1 | W4-prefill32k-0 | 2 | 32.0 | 80.4 | - | - | - | 4896.2 | length |
| c1 | W4-prefill32k-1 | 2 | 32.0 | 93.3 | - | - | - | 4967.4 | length |

- a: experts in VRAM at start: 4433 slots / 8.46 GiB
- a1: experts in VRAM at start: 4433 slots / 8.46 GiB
- b4: experts in VRAM at start: 4433 slots / 8.46 GiB
- b5: experts in VRAM at start: 4433 slots / 8.46 GiB
- b7: experts in VRAM at start: 4433 slots / 8.46 GiB
- b7v: experts in VRAM at start: 4365 slots / 8.33 GiB
- vcpu: experts in VRAM at start: 4433 slots / 8.46 GiB
- vgpu: experts in VRAM at start: 4429 slots / 8.45 GiB
- c1: experts in VRAM at start: -
