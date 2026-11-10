| metric | without: r14-s2-qsa_split_attn-A-a / r14-s2-qsa_split_attn-A-b → mean | with: r14-s2-qsa_split_attn-B-a / r14-s2-qsa_split_attn-B-b → mean | B vs A |
|---|---|---|---|
| decode, all requests (tok/s) | 119.9 / 120.8 → **120.4** | 124.5 / 123.6 → **124.0** | +3.0 % |
| ms per verify round | 18.42 / 18.33 → **18.37** | 17.65 / 17.40 → **17.53** | -4.6 % |
| tokens per round | 2.210 / 2.214 → **2.212** | 2.197 / 2.150 → **2.173** | -1.7 % |
| acceptance | 0.671 / 0.678 → **0.674** | 0.675 / 0.666 → **0.670** | -0.6 % |
| decode, queries (tok/s) | 107.2 / 106.5 → **106.9** | 112.9 / 108.5 → **110.7** | +3.6 % |
| decode, triage (tok/s) | 114.3 / 114.9 → **114.6** | 118.0 / 114.3 → **116.2** | +1.3 % |
| decode, toolcall (tok/s) | 108.4 / 108.8 → **108.6** | 102.1 / 110.2 → **106.2** | -2.2 % |
| decode, analysis (tok/s) | 116.4 / 118.5 → **117.5** | 122.1 / 122.8 → **122.4** | +4.2 % |
| decode, synthesis (tok/s) | 121.3 / 121.0 → **121.1** | 125.6 / 124.5 → **125.1** | +3.2 % |
| decode, followup (tok/s) | 133.4 / 137.7 → **135.5** | 134.9 / 136.4 → **135.7** | +0.1 % |
| decode, copy (tok/s) | – / – → **–** | – / – → **–** |
| decode, quote (tok/s) | – / – → **–** | – / – → **–** |
| decode, chat (tok/s) | – / – → **–** | – / – → **–** |
| TTFT prompts < 4K, mean (s) | 0.85 / 0.84 → **0.85** | 0.85 / 0.85 → **0.85** | +0.2 % |
| TTFT prompts 4–16K, mean (s) | 2.30 / 2.30 → **2.30** | 2.30 / 2.29 → **2.30** | -0.1 % |
| TTFT prompts ≥ 16K, mean (s) | 5.34 / 5.34 → **5.34** | 5.35 / 5.35 → **5.35** | +0.1 % |
| output tokens, all requests | 46017 / 44614 → **45316** | 45599 / 46060 → **45830** | +1.1 % |
| all requests, total time (s) | 415.7 / 401.2 → **408.5** | 398.3 / 404.8 → **401.5** | -1.7 % |
| desktop on the 4060 Ti, graphics SM % (round 11) | – / – → **–** | – / – → **–** |
