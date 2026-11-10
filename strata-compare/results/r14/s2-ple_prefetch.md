| metric | without: r14-s2-ple_prefetch-A-a / r14-s2-ple_prefetch-A-b → mean | with: r14-s2-ple_prefetch-B-a / r14-s2-ple_prefetch-B-b → mean | B vs A |
|---|---|---|---|
| decode (tok/s) | 136.6 / 137.1 → **136.9** | 138.5 / 138.1 → **138.3** | +1.0 % |
| ms per verify round | 15.34 / 14.84 → **15.09** | 15.01 / 15.26 → **15.13** | +0.3 % |
| tokens per round | 2.095 / 2.035 → **2.065** | 2.078 / 2.107 → **2.093** | +1.3 % |
| acceptance | 0.697 / 0.698 → **0.698** | 0.692 / 0.705 → **0.698** | +0.1 % |
| long reasoning math (tok/s) | 155.5 / 158.2 → **156.9** | 156.6 / 161.8 → **159.2** | +1.5 % |
| long reasoning code (tok/s) | 126.1 / 124.8 → **125.5** | 127.6 / 125.8 → **126.7** | +0.9 % |
| TTFT 32K (s) | 7.77 / 7.77 → **7.77** | 7.78 / 7.77 → **7.77** | +0.0 % |
| all requests, total time (s) | 88.9 / 86.5 → **87.7** | 84.8 / 86.0 → **85.4** | -2.7 % |
