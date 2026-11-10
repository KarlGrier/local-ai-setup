# Round 20 item 4 (2026-10-15 18:10-18:47): concurrency, served configs only (C*17.1 again, then C*18), 8081, 2 reps

base = D's C*17.1 served arm of 10-14 (monitor on the iGPU then; on the 5080, asleep, now). Medians of 2 reps.

base (decode):
| N | total tok/s | per request tok/s | TTFT median / worst s (median of reps) | wall s (median of reps) | min MemAvailable GiB |
|---|---|---|---|---|---|
| 1 | 156.2 | 159.2 | 0.49 / 0.49 | 26.2 | 37.3 |
| 2 | 142.6 | 146.4 | 13.20 / 26.01 | 57.5 | 37.3 |
| 4 | 141.5 | 138.4 | 41.10 / 70.48 | 99.8 | 37.3 |
| 8 | 137.3 | 136.8 | 84.42 / 180.68 | 209.4 | 36.0 |

r20-c171 (decode):
| N | total tok/s | per request tok/s | TTFT median / worst s (median of reps) | wall s (median of reps) | min MemAvailable GiB |
|---|---|---|---|---|---|
| 1 | 159.2 | 162.3 | 0.49 / 0.49 | 25.7 | 37.1 |
| 2 | 146.4 | 149.7 | 15.57 / 30.71 | 56.0 | 37.1 |
| 4 | 143.2 | 139.8 | 35.92 / 63.52 | 92.3 | 37.1 |
| 8 | 137.2 | 136.0 | 78.48 / 180.07 | 210.2 | 37.2 |

r20-c18 (decode):
| N | total tok/s | per request tok/s | TTFT median / worst s (median of reps) | wall s (median of reps) | min MemAvailable GiB |
|---|---|---|---|---|---|
| 1 | 158.2 | 161.1 | 0.48 / 0.48 | 25.9 | 37.1 |
| 2 | 146.6 | 150.0 | 14.33 / 28.28 | 55.9 | 37.1 |
| 4 | 139.7 | 137.6 | 41.92 / 77.57 | 106.9 | 37.1 |
| 8 | 137.5 | 136.5 | 93.66 / 189.00 | 218.6 | 37.2 |

base (agent):
| N | total tok/s | per request tok/s | TTFT median / worst s (median of reps) | wall s (median of reps) | min MemAvailable GiB |
|---|---|---|---|---|---|
| 1 | 17.8 | 128.9 | 6.53 / 6.53 | 7.6 | 27.2 |
| 2 | 12.9 | 139.4 | 9.96 / 13.49 | 14.2 | 27.2 |
| 4 | 20.3 | 146.2 | 18.29 / 30.02 | 30.6 | 27.2 |
| 8 | 43.0 | 141.8 | 31.36 / 75.75 | 76.4 | 27.2 |

r20-c171 (agent):
| N | total tok/s | per request tok/s | TTFT median / worst s (median of reps) | wall s (median of reps) | min MemAvailable GiB |
|---|---|---|---|---|---|
| 1 | 10.7 | 132.9 | 6.53 / 6.53 | 7.1 | 27.2 |
| 2 | 17.8 | 143.7 | 10.38 / 14.27 | 14.8 | 27.0 |
| 4 | 30.4 | 141.5 | 18.86 / 32.98 | 33.3 | 27.0 |
| 8 | 20.5 | 141.4 | 31.09 / 58.89 | 61.2 | 27.0 |

r20-c18 (agent):
| N | total tok/s | per request tok/s | TTFT median / worst s (median of reps) | wall s (median of reps) | min MemAvailable GiB |
|---|---|---|---|---|---|
| 1 | 17.6 | 131.8 | 6.53 / 6.53 | 7.8 | 27.2 |
| 2 | 16.2 | 143.2 | 9.93 / 13.45 | 14.6 | 27.2 |
| 4 | 33.7 | 146.6 | 17.36 / 33.85 | 34.8 | 27.2 |
| 8 | 39.7 | 139.5 | 45.09 / 72.80 | 73.1 | 27.0 |

Engine side (logs/r20/engine-conc-{c171,c18}.log): the 30 agent prompts (27.2-27.7K tokens, 0 reused) were read in
192.4 s (C*17.1) and 192.4 s (C*18) in total - identical; the agent sets' wall-time differences are the answers' length
(T 1.0: the tool-call answers' generation summed 38.9 s vs 66.4 s; a few C*18 answers reasoned 1,500-2,200 tokens before
the call). Decode requests: median engine decode 137.2 tok/s in both arms.
