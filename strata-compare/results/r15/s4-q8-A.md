# Round 15 step 4 — file-tier options, q8-A (each alone, A B B A, greedy math 1,024 tokens, cold page cache)

| option | arm | decode tok/s | ms / round | file MB / round | file ms / round | fetch wait ms / round | pool ms / round | not in the page cache | min MemAvailable GiB | swap GiB |
|---|---|---|---|---|---|---|---|---|---|---|
| pf:STRATA_IO_PREFETCH=1 | base-a | 11.6 | 241.1 | 2593.7 | 365.6 | 0.0 | 222.2 | 0.10 | 83.4 | 1.88 |
| pf:STRATA_IO_PREFETCH=1 | opt-a | 12.5 | 209.1 | 2400.1 | 246.6 | 174.8 | 191.2 | 0.13 | 83.6 | 1.88 |
| pf:STRATA_IO_PREFETCH=1 | opt-b | 12.1 | 209.4 | 2407.7 | 244.9 | 174.0 | 190.9 | 0.13 | 83.6 | 1.87 |
| pf:STRATA_IO_PREFETCH=1 | base-b | 12.1 | 226.6 | 2561.7 | 315.1 | 0.0 | 208.5 | 0.10 | 83.4 | 1.87 |
| fetch16:STRATA_FETCH_THREADS=16 | base-a | 12.1 | 228.1 | 2589.7 | 318.8 | 0.0 | 209.1 | 0.09 | 83.4 | 2.16 |
| fetch16:STRATA_FETCH_THREADS=16 | opt-a | 11.0 | 231.3 | 2539.0 | 340.5 | 0.0 | 213.3 | 0.09 | 83.3 | 1.86 |
| fetch16:STRATA_FETCH_THREADS=16 | opt-b | 11.2 | 241.0 | 2639.2 | 351.3 | 0.0 | 221.8 | 0.09 | 83.3 | 1.86 |
| fetch16:STRATA_FETCH_THREADS=16 | base-b | 12.2 | 227.2 | 2596.8 | 313.2 | 0.0 | 208.2 | 0.09 | 83.5 | 1.86 |

| option | base tok/s | option tok/s | change | base arms' spread | >= +3 % |
|---|---|---|---|---|---|
| pf:STRATA_IO_PREFETCH=1 | 11.83 | 12.33 | **+4.2 %** | 4.5 % | KEEP |
| fetch16:STRATA_FETCH_THREADS=16 | 12.12 | 11.07 | **-8.7 %** | 0.4 % | no |
