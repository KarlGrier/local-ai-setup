| metric | R4-c3a | R4-c3b | R4-upa | R4-upb |
|---|---|---|---|---|
| TTFT 1K prompt, median of 3 (s) | 1.38 | 1.37 | 1.13 | 1.14 |
| TTFT 32K prompt (s) | 17.53 | 17.51 | 15.74 | 15.72 |
| TTFT 64K prompt (s) | 35.17 | 35.19 | 31.64 | 31.63 |
| TTFT 120K prompt (s) | 68.52 | 68.53 | 61.95 | 61.88 |
| decode after 1K, median of 3 (tok/s) | 86.3 | 86.6 | 84.4 | 82.4 |
| decode after 32K (tok/s) | 80.0 | 89.0 | 77.0 | 79.5 |
| decode after 64K (tok/s) | 78.6 | 75.0 | 73.5 | 78.7 |
| decode after 120K (tok/s) | 85.4 | 77.9 | 85.5 | 84.4 |
| long reasoning math, 8,192 tokens (tok/s) | 99.4 | 100.6 | 100.9 | 100.3 |
| long reasoning code, 8,192 tokens (tok/s) | 83.4 | 81.9 | 84.4 | 83.3 |
| decode, all 768+ token requests (engine tok/s) | 88.8 | 88.3 | 89.3 | 88.7 |
| ms per verify round / tokens per round | 24.65 / 2.19 | 24.40 / 2.16 | 24.55 / 2.19 | 24.86 / 2.21 |
| draft acceptance | 0.692 | 0.691 | 0.706 | 0.706 |
| correctness decode, median of 5 (tok/s) | 74.6 | 79.2 | 78.0 | 78.8 |
| peak GPU used (MiB) / min MemAvailable (GB) / peak RSS (GB) | 15379 / 28.3 / 57.3 | 15378 / 30.6 / 55.0 | 15407 / 28.3 / 57.4 | 15406 / 30.6 / 55.0 |
