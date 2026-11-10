## Phase D A/B — v0.1.31 + PR245 (R9p, = C*10's tree) vs C*9
### decode screens ABBA
| metric | D9pd-a | C9d3-a | C9d3-b | D9pd-b |
|---|---|---|---|---|
| TTFT 1K prompt, median of 3 (s) | – | – | – | – |
| TTFT short prompts 68-87 tokens, median of 5 (s) | 0.46 | 0.45 | 0.44 | 0.47 |
| TTFT 32K prompt (s) | 9.29 | 9.27 | 9.27 | 9.28 |
| TTFT 64K prompt (s) | – | – | – | – |
| TTFT 120K prompt (s) | – | – | – | – |
| decode after 1K, median of 3 (tok/s) | – | – | – | – |
| decode after 32K (tok/s) | 100.9 | 99.4 | 105.1 | 107.4 |
| decode after 64K (tok/s) | – | – | – | – |
| decode after 120K (tok/s) | – | – | – | – |
| long reasoning math, 8,192 tokens (tok/s) | 121.3 | 122.9 | 126.2 | 126.2 |
| long reasoning code, 8,192 tokens (tok/s) | 103.1 | 103.4 | 103.0 | 100.4 |
| decode, all 768+ token requests (engine tok/s) | 110.3 | 110.9 | 112.4 | 111.3 |
| ms per verify round / tokens per round | 17.52 / 1.93 | 17.77 / 1.97 | 17.62 / 1.98 | 17.42 / 1.94 |
| draft acceptance | 0.635 | 0.639 | 0.665 | 0.647 |
| correctness decode, median of 5 (tok/s) | 99.8 | 100.4 | 99.6 | 103.4 |
| peak GPU used (MiB) / min MemAvailable (GB) / peak RSS (GB) | 15402 / 35.4 / 50.7 | 15402 / 34.2 / 50.6 | 15402 / 35.3 / 50.7 | 15402 / 35.3 / 50.7 |

### full screens ABBA
| metric | D9p-a | C9s-a | C9s-b | D9p-b |
|---|---|---|---|---|
| TTFT 1K prompt, median of 3 (s) | 0.98 | 0.98 | 0.98 | 1.01 |
| TTFT short prompts 68-87 tokens, median of 5 (s) | 0.45 | 0.45 | 0.44 | 0.45 |
| TTFT 32K prompt (s) | 9.26 | 9.26 | 9.24 | 9.23 |
| TTFT 64K prompt (s) | 17.90 | 17.89 | 17.88 | 17.87 |
| TTFT 120K prompt (s) | 33.82 | 33.76 | 33.80 | 33.80 |
| decode after 1K, median of 3 (tok/s) | 109.0 | 110.6 | 107.5 | 104.9 |
| decode after 32K (tok/s) | 106.4 | 104.5 | 103.1 | 105.2 |
| decode after 64K (tok/s) | 100.9 | 102.2 | 99.0 | 101.0 |
| decode after 120K (tok/s) | 114.5 | 107.4 | 112.8 | 108.8 |
| long reasoning math, 8,192 tokens (tok/s) | 120.7 | 121.5 | 122.5 | 124.8 |
| long reasoning code, 8,192 tokens (tok/s) | 101.3 | 105.0 | 100.4 | 102.2 |
| decode, all 768+ token requests (engine tok/s) | 109.6 | 111.5 | 109.0 | 110.9 |
| ms per verify round / tokens per round | 18.22 / 2.00 | 18.29 / 2.04 | 17.76 / 1.94 | 17.79 / 1.97 |
| draft acceptance | 0.642 | 0.659 | 0.632 | 0.648 |
| correctness decode, median of 5 (tok/s) | 97.9 | 98.4 | 99.4 | 92.1 |
| peak GPU used (MiB) / min MemAvailable (GB) / peak RSS (GB) | 15416 / 27.6 / 57.5 | 15417 / 27.8 / 57.5 | 15416 / 27.8 / 57.5 | 15416 / 27.8 / 57.5 |

### plain v0.1.31 (no PR245), one decode screen
| metric | D9d-a |
|---|---|
| TTFT 1K prompt, median of 3 (s) | – |
| TTFT short prompts 68-87 tokens, median of 5 (s) | 0.45 |
| TTFT 32K prompt (s) | 9.29 |
| TTFT 64K prompt (s) | – |
| TTFT 120K prompt (s) | – |
| decode after 1K, median of 3 (tok/s) | – |
| decode after 32K (tok/s) | 94.9 |
| decode after 64K (tok/s) | – |
| decode after 120K (tok/s) | – |
| long reasoning math, 8,192 tokens (tok/s) | 117.9 |
| long reasoning code, 8,192 tokens (tok/s) | 101.4 |
| decode, all 768+ token requests (engine tok/s) | 107.5 |
| ms per verify round / tokens per round | 18.23 / 1.96 |
| draft acceptance | 0.634 |
| correctness decode, median of 5 (tok/s) | 98.5 |
| peak GPU used (MiB) / min MemAvailable (GB) / peak RSS (GB) | 15404 / 35.3 / 50.7 |
