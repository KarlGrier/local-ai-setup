# Round 15 step 4 — file-tier options, q5s-B (each alone, A B B A, greedy math 1,024 tokens, cold page cache)

| option | arm | decode tok/s | ms / round | file MB / round | file ms / round | fetch wait ms / round | pool ms / round | not in the page cache | min MemAvailable GiB | swap GiB |
|---|---|---|---|---|---|---|---|---|---|---|
| ub0:STRATA_UNBUFFERED_LOAD=0 | base-a | 30.9 | 88.1 | 196.4 | 58.8 | 0.0 | 71.5 | 0.34 | 19.4 | 3.62 |
| ub0:STRATA_UNBUFFERED_LOAD=0 | opt-a | 24.6 | 104.9 | 184.3 | 76.3 | 0.0 | 87.4 | 0.23 | 18.9 | 3.34 |
| ub0:STRATA_UNBUFFERED_LOAD=0 | opt-b | 32.4 | 84.8 | 185.7 | 52.0 | 0.0 | 67.7 | 0.24 | 19.0 | 3.46 |
| ub0:STRATA_UNBUFFERED_LOAD=0 | base-b | 31.3 | 85.2 | 177.8 | 50.6 | 0.0 | 68.1 | 0.23 | 19.1 | 3.40 |
| ub1:STRATA_UNBUFFERED_LOAD=1 | base-a | 30.2 | 90.5 | 181.1 | 59.5 | 0.0 | 73.5 | 0.24 | 19.1 | 3.56 |
| ub1:STRATA_UNBUFFERED_LOAD=1 | opt-a | 35.0 | 72.2 | 164.9 | 29.7 | 0.0 | 54.8 | 0.00 | 19.3 | 1.89 |
| ub1:STRATA_UNBUFFERED_LOAD=1 | opt-b | 35.7 | 77.3 | 185.6 | 33.4 | 0.0 | 59.6 | 0.00 | 18.6 | 1.89 |
| ub1:STRATA_UNBUFFERED_LOAD=1 | base-b | 31.2 | 84.2 | 171.6 | 51.4 | 0.0 | 67.4 | 0.24 | 19.4 | 3.34 |
| pf:STRATA_IO_PREFETCH=1 | base-a | 32.4 | 82.9 | 181.4 | 50.4 | 0.0 | 65.9 | 0.23 | 19.5 | 3.41 |
| pf:STRATA_IO_PREFETCH=1 | opt-a | 37.0 | 73.2 | 180.4 | 29.0 | 30.7 | 56.8 | 0.43 | 18.9 | 3.27 |
| pf:STRATA_IO_PREFETCH=1 | opt-b | 25.8 | 102.1 | 150.0 | 84.5 | 60.0 | 84.4 | 0.69 | 18.6 | 1.88 |
| pf:STRATA_IO_PREFETCH=1 | base-b | 23.4 | 109.5 | 171.9 | 84.0 | 0.0 | 92.2 | 0.30 | 19.0 | 3.73 |
| fetch16:STRATA_FETCH_THREADS=16 | base-a | 28.5 | 94.0 | 182.4 | 63.8 | 0.0 | 77.0 | 0.24 | 19.5 | 3.65 |
| fetch16:STRATA_FETCH_THREADS=16 | opt-a | 28.8 | 91.4 | 168.0 | 58.8 | 0.0 | 74.3 | 0.24 | 19.1 | 3.65 |
| fetch16:STRATA_FETCH_THREADS=16 | opt-b | 29.7 | 87.9 | 175.9 | 55.2 | 0.0 | 71.0 | 0.23 | 19.3 | 3.43 |
| fetch16:STRATA_FETCH_THREADS=16 | base-b | 29.4 | 87.9 | 169.9 | 55.2 | 0.0 | 70.8 | 0.24 | 19.3 | 3.47 |
| budget56:-:--resident-budget-gib=56 | base-a | 29.6 | 90.1 | 180.2 | 56.1 | 0.0 | 72.9 | 0.22 | 19.4 | 3.36 |
| budget56:-:--resident-budget-gib=56 | opt-a | 24.6 | 108.7 | 295.9 | 85.4 | 0.0 | 92.0 | 0.17 | 26.9 | 2.44 |
| budget56:-:--resident-budget-gib=56 | opt-b | 24.2 | 111.4 | 292.1 | 84.6 | 0.0 | 94.8 | 0.17 | 26.9 | 2.43 |
| budget56:-:--resident-budget-gib=56 | base-b | 28.6 | 86.8 | 155.7 | 53.5 | 0.0 | 69.8 | 0.23 | 19.3 | 3.36 |
| budget74:-:--resident-budget-gib=74 | base-a | 30.3 | 87.4 | 178.3 | 52.9 | 0.0 | 70.6 | 0.22 | 19.5 | 3.40 |
| budget74:-:--resident-budget-gib=74 | opt-a | 37.1 | 74.1 | 67.6 | 34.9 | 0.0 | 56.7 | 0.58 | 9.3 | 3.55 |
| budget74:-:--resident-budget-gib=74 | opt-b | 36.6 | 72.5 | 64.6 | 32.7 | 0.0 | 55.2 | 0.51 | 9.4 | 3.47 |
| budget74:-:--resident-budget-gib=74 | base-b | 30.3 | 86.8 | 170.5 | 51.5 | 0.0 | 70.1 | 0.23 | 19.5 | 3.45 |

| option | base tok/s | option tok/s | change | base arms' spread | >= +3 % |
|---|---|---|---|---|---|
| ub0:STRATA_UNBUFFERED_LOAD=0 | 31.10 | 28.52 | **-8.3 %** | 1.5 % | no |
| ub1:STRATA_UNBUFFERED_LOAD=1 | 30.71 | 35.38 | **+15.2 %** | 3.6 % | KEEP |
| pf:STRATA_IO_PREFETCH=1 | 27.91 | 31.39 | **+12.5 %** | 38.7 % | KEEP |
| fetch16:STRATA_FETCH_THREADS=16 | 28.98 | 29.23 | **+0.9 %** | 3.3 % | no |
| budget56:-:--resident-budget-gib=56 | 29.09 | 24.41 | **-16.1 %** | 3.7 % | no |
| budget74:-:--resident-budget-gib=74 | 30.31 | 36.83 | **+21.5 %** | 0.0 % | KEEP |
