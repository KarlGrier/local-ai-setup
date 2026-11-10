| metric | without: r14-s2-adapt_helper-A-a / r14-s2-adapt_helper-A-b → mean | with: r14-s2-adapt_helper-B-a / r14-s2-adapt_helper-B-b → mean | B vs A |
|---|---|---|---|
| decode, all requests (tok/s) | 112.6 / 114.5 → **113.6** | 119.5 / 119.6 → **119.6** | +5.3 % |
| ms per verify round | 19.13 / 19.06 → **19.09** | 18.20 / 18.29 → **18.24** | -4.5 % |
| tokens per round | 2.154 / 2.183 → **2.169** | 2.175 / 2.187 → **2.181** | +0.6 % |
| acceptance | 0.671 / 0.681 → **0.676** | 0.670 / 0.674 → **0.672** | -0.6 % |
| decode, queries (tok/s) | 104.8 / 108.0 → **106.4** | 115.6 / 113.8 → **114.7** | +7.8 % |
| decode, triage (tok/s) | 109.8 / 109.0 → **109.4** | 112.7 / 114.2 → **113.5** | +3.7 % |
| decode, toolcall (tok/s) | 94.3 / 91.7 → **93.0** | 114.7 / 105.8 → **110.2** | +18.5 % |
| decode, analysis (tok/s) | 110.4 / 112.7 → **111.5** | 118.8 / 118.3 → **118.6** | +6.3 % |
| decode, synthesis (tok/s) | 113.7 / 115.1 → **114.4** | 119.8 / 119.9 → **119.8** | +4.7 % |
| decode, followup (tok/s) | 118.2 / 125.0 → **121.6** | 129.0 / 130.1 → **129.5** | +6.5 % |
| decode, copy (tok/s) | – / – → **–** | – / – → **–** |
| decode, quote (tok/s) | – / – → **–** | – / – → **–** |
| decode, chat (tok/s) | – / – → **–** | – / – → **–** |
| TTFT prompts < 4K, mean (s) | 0.85 / 0.84 → **0.84** | 0.85 / 0.84 → **0.85** | +0.1 % |
| TTFT prompts 4–16K, mean (s) | 2.30 / 2.30 → **2.30** | 2.32 / 2.30 → **2.31** | +0.4 % |
| TTFT prompts ≥ 16K, mean (s) | 5.35 / 5.35 → **5.35** | 5.35 / 5.35 → **5.35** | +0.0 % |
| output tokens, all requests | 45527 / 45335 → **45431** | 46000 / 45876 → **45938** | +1.1 % |
| all requests, total time (s) | 436.1 / 427.8 → **432.0** | 416.9 / 415.6 → **416.3** | -3.6 % |
| desktop on the 4060 Ti, graphics SM % (round 11) | – / – → **–** | – / – → **–** |
