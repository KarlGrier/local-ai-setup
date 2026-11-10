| earlier builds (from REPORT, not re-run; methods and sampling changed between rounds) | decode, long answers (tok/s) | TTFT 32K / 120K (s) | measured with |
|---|---|---|---|
| A: llama.cpp + Signal AP-Q4_K_XL (Round 1; a different model, your daily server then) | 33.5 (after a 1K prompt) | 39.9 / 143.4 | T 0.6 |
| B: llama.cpp 53b1389 + the same IQ3_S file (Round 1) | 35.9 (after 1K) | 33.3 / 140.5 | greedy |
| C0: Strata v0.1.6 defaults (+ reserve 1000 to start at all) (Round 1) | 47.9 (after 1K) | 35.6 / 135.4 | greedy |
| C\* (Round 1: v0.1.11 + 2 patches + 3 flags) | 87.2 (after 1K) | 22.5 / 88.2 | T 0.6 |
| C\*2 (Round 2: + 3 settings) | 82.0 (1K + 32K requests) | 19.4 / 75.8 | T 0.6 |
| C\*3 (Round 3: v0.1.12 + 8 patches) | 91.6–93.5 (all requests) | 17.5 / 68.3 | T 0.6 |
| C\*4 (Round 4: v0.1.15 + 6 patches) | 88.7–89.3 (all long requests) | 15.7 / 61.9 | T 0.6 |
| C\*5 (Round 5: v0.1.24 + 9 patches) | 89.9 (Round 6's A/B, all 768+ answers) | 10.0 / 36.6 | T 1.0 |
| C\*6 (Round 6: + the 4060 Ti helper, Linux pinning, n-gram prefetch) | 93.6 | 10.0 / 36.6 | T 1.0 |
| C\*7 (Round 7: v0.1.27 + 13 patches) | 93.7 | 9.65 / 35.2 | T 1.0 |
| C\*8 (Round 8: v0.1.30 + 12 patches) | 105.8 | 9.52 / 34.8 | T 1.0 |
| C\*9 (Round 8: + PR245 + prompt MMQ offsets) | 110.1–110.8 | 9.26 / 33.75 | T 1.0 |
| C\*10 (Round 8: the same on v0.1.31) | 110.3–111.3 (decode screens) | 9.23–9.26 / 33.8 | T 1.0 |
