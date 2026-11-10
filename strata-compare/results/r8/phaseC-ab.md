## Phase C A/B — full screens (ABBA; C92-a2 replaces C92-a, which ran with 16 chat slots)
| metric | C92-a2 | C82-a | C82-b | C92-b |
|---|---|---|---|---|
| TTFT 1K prompt, median of 3 (s) | 0.98 | 1.00 | 0.99 | 1.00 |
| TTFT short prompts 68-87 tokens, median of 5 (s) | 0.45 | 0.46 | 0.49 | 0.45 |
| TTFT 32K prompt (s) | 9.26 | 9.52 | 9.53 | 9.28 |
| TTFT 64K prompt (s) | 17.89 | 18.43 | 18.45 | 17.84 |
| TTFT 120K prompt (s) | 33.75 | 34.78 | 34.80 | 33.84 |
| decode after 1K, median of 3 (tok/s) | 104.6 | 100.6 | 95.1 | 105.0 |
| decode after 32K (tok/s) | 104.0 | 111.1 | 107.9 | 110.9 |
| decode after 64K (tok/s) | 101.2 | 95.8 | 96.3 | 103.1 |
| decode after 120K (tok/s) | 111.8 | 119.8 | 103.5 | 92.9 |
| long reasoning math, 8,192 tokens (tok/s) | 125.6 | 116.6 | 118.0 | 123.6 |
| long reasoning code, 8,192 tokens (tok/s) | 102.7 | 97.1 | 98.4 | 102.9 |
| decode, all 768+ token requests (engine tok/s) | 110.8 | 105.3 | 105.9 | 110.1 |
| ms per verify round / tokens per round | 18.10 / 2.01 | 18.49 / 1.95 | 18.68 / 1.98 | 17.76 / 1.96 |
| draft acceptance | 0.666 | 0.646 | 0.654 | 0.645 |
| correctness decode, median of 5 (tok/s) | 100.7 | 95.2 | 93.4 | 101.5 |
| peak GPU used (MiB) / min MemAvailable (GB) / peak RSS (GB) | 15416 / 28.5 / 57.5 | 15418 / 28.5 / 57.5 | 15418 / 28.5 / 57.5 | 15416 / 28.5 / 57.5 |

## Decode screens (ABBA)
| metric | C92d-a | C82d-a | C82d-b | C92d-b |
|---|---|---|---|---|
| TTFT 1K prompt, median of 3 (s) | – | – | – | – |
| TTFT short prompts 68-87 tokens, median of 5 (s) | 0.44 | 0.47 | 0.46 | 0.46 |
| TTFT 32K prompt (s) | 9.27 | 9.56 | 9.53 | 9.25 |
| TTFT 64K prompt (s) | – | – | – | – |
| TTFT 120K prompt (s) | – | – | – | – |
| decode after 1K, median of 3 (tok/s) | – | – | – | – |
| decode after 32K (tok/s) | 101.8 | 96.4 | 95.7 | 108.2 |
| decode after 64K (tok/s) | – | – | – | – |
| decode after 120K (tok/s) | – | – | – | – |
| long reasoning math, 8,192 tokens (tok/s) | 123.0 | 118.4 | 117.1 | 124.5 |
| long reasoning code, 8,192 tokens (tok/s) | 101.0 | 102.1 | 97.7 | 104.0 |
| decode, all 768+ token requests (engine tok/s) | 109.9 | 108.2 | 105.4 | 112.7 |
| ms per verify round / tokens per round | 17.29 / 1.90 | 18.45 / 2.00 | 18.58 / 1.96 | 17.43 / 1.96 |
| draft acceptance | 0.629 | 0.656 | 0.641 | 0.654 |
| correctness decode, median of 5 (tok/s) | 98.5 | 98.7 | 96.1 | 107.3 |
| peak GPU used (MiB) / min MemAvailable (GB) / peak RSS (GB) | 15402 / 35.4 / 50.7 | 15404 / 35.4 / 50.7 | 15410 / 35.4 / 50.7 | 15402 / 35.4 / 50.7 |

## Fresh holdout (ABBA; work/r8/holdout.py)
| run | decode tok/s (engine, 4 long answers + doc) | tokens | TTFT doc 28K (s) | TTFT short, median (s) | all 8 requests, total (s) |
|---|---|---|---|---|---|
| H9-a | 103.9 | 15607 | 10.18 | 0.53 | 164.4 (8 requests) |
| H8-a | 98.4 | 15787 | 10.47 | 0.55 | 174.1 (8 requests) |
| H8-b | 99.5 | 15578 | 10.48 | 0.49 | 170.9 (8 requests) |
| H9-b | 103.6 | 15614 | 10.19 | 0.54 | 165.1 (8 requests) |
