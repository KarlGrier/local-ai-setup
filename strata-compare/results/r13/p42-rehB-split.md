| metric | stock_one_gpu_budget: rb-rehB-D-stockbudget-a / rb-rehB-D-stockbudget-b → mean | tuned: rb-rehB-D-cand-a / rb-rehB-D-cand-b → mean | B vs A |
|---|---|---|---|
| decode (tok/s) | 44.0 / 45.4 → **44.7** | 47.7 / 47.2 → **47.4** | +6.1 % |
| ms per verify round | 45.39 / 42.39 → **43.89** | 43.74 / 44.40 → **44.07** | +0.4 % |
| tokens per round | 1.995 / 1.925 → **1.960** | 2.085 / 2.096 → **2.090** | +6.6 % |
| acceptance | 0.656 / 0.636 → **0.646** | 0.689 / 0.706 → **0.697** | +8.0 % |
| long reasoning math (tok/s) | 53.2 / 53.5 → **53.3** | 51.9 / 55.7 → **53.8** | +0.8 % |
| long reasoning code (tok/s) | 40.4 / 42.4 → **41.4** | 47.3 / 44.3 → **45.8** | +10.7 % |
| TTFT 32K (s) | 14.72 / 21.40 → **18.06** | 15.65 / 15.44 → **15.54** | -14.0 % |
| all requests, total time (s) | 260.7 / 252.3 → **256.5** | 245.1 / 246.1 → **245.6** | -4.2 % |
