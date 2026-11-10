# Round 15 step 4 — file-tier options, q8-B (each alone, A B B A, greedy math 1,024 tokens, cold page cache)

| option | arm | decode tok/s | ms / round | file MB / round | file ms / round | fetch wait ms / round | pool ms / round | not in the page cache | min MemAvailable GiB | swap GiB |
|---|---|---|---|---|---|---|---|---|---|---|
| ub0:STRATA_UNBUFFERED_LOAD=0 | base-a | 10.3 | 262.4 | 713.2 | 405.8 | 0.0 | 242.2 | 0.27 | 18.5 | 3.99 |
| ub0:STRATA_UNBUFFERED_LOAD=0 | opt-a | 10.1 | 256.4 | 678.3 | 359.2 | 0.0 | 236.4 | 0.27 | 18.8 | 3.91 |
| ub0:STRATA_UNBUFFERED_LOAD=0 | opt-b | 10.7 | 227.5 | 591.4 | 308.7 | 0.0 | 207.5 | 0.28 | 18.7 | 4.02 |
| ub0:STRATA_UNBUFFERED_LOAD=0 | base-b | 10.3 | 252.7 | 678.2 | 359.4 | 0.0 | 233.1 | 0.28 | 18.5 | 3.95 |
| ub1:STRATA_UNBUFFERED_LOAD=1 | base-a | 9.2 | 284.8 | 717.0 | 435.8 | 0.0 | 265.1 | 0.28 | 18.6 | 3.74 |
| ub1:STRATA_UNBUFFERED_LOAD=1 | opt-a | 15.3 | 169.1 | 664.3 | 106.5 | 0.0 | 145.8 | 0.00 | 18.4 | 1.89 |
| ub1:STRATA_UNBUFFERED_LOAD=1 | opt-b | 16.3 | 161.2 | 664.1 | 100.7 | 0.0 | 139.6 | 0.00 | 17.5 | 1.88 |
| ub1:STRATA_UNBUFFERED_LOAD=1 | base-b | 12.2 | 207.7 | 583.8 | 265.2 | 0.0 | 188.1 | 0.28 | 18.5 | 4.03 |
| pf:STRATA_IO_PREFETCH=1 | base-a | 10.6 | 250.0 | 666.8 | 346.7 | 0.0 | 230.3 | 0.29 | 18.5 | 4.00 |
| pf:STRATA_IO_PREFETCH=1 | opt-a | 8.6 | 300.3 | 567.5 | 528.6 | 232.3 | 266.5 | 0.79 | 17.9 | 1.90 |
| pf:STRATA_IO_PREFETCH=1 | opt-b | 10.6 | 242.7 | 681.1 | 264.1 | 178.8 | 218.7 | 0.59 | 18.4 | 3.64 |
| pf:STRATA_IO_PREFETCH=1 | base-b | 10.4 | 245.9 | 664.8 | 343.3 | 0.0 | 226.2 | 0.27 | 18.7 | 4.03 |
| fetch16:STRATA_FETCH_THREADS=16 | base-a | 10.8 | 233.4 | 613.4 | 326.2 | 0.0 | 213.0 | 0.27 | 18.5 | 4.03 |
| fetch16:STRATA_FETCH_THREADS=16 | opt-a | 10.2 | 251.5 | 648.6 | 354.9 | 0.0 | 230.9 | 0.28 | 18.9 | 4.03 |
| fetch16:STRATA_FETCH_THREADS=16 | opt-b | 11.6 | 228.4 | 651.3 | 290.5 | 0.0 | 209.3 | 0.26 | 18.6 | 4.01 |
| fetch16:STRATA_FETCH_THREADS=16 | base-b | 11.2 | 235.7 | 673.7 | 327.9 | 0.0 | 216.7 | 0.27 | 18.6 | 3.95 |
| budget56:-:--resident-budget-gib=56 | base-a | 11.2 | 244.2 | 734.6 | 325.7 | 0.0 | 224.0 | 0.27 | 18.6 | 4.01 |
| budget56:-:--resident-budget-gib=56 | opt-a | 12.3 | 215.0 | 915.3 | 283.9 | 0.0 | 195.4 | 0.19 | 26.6 | 4.04 |
| budget56:-:--resident-budget-gib=56 | opt-b | 12.8 | 201.7 | 852.4 | 260.0 | 0.0 | 182.5 | 0.19 | 26.2 | 3.81 |
| budget56:-:--resident-budget-gib=56 | base-b | 9.9 | 259.6 | 676.4 | 361.7 | 0.0 | 239.0 | 0.29 | 18.9 | 4.03 |
| budget74:-:--resident-budget-gib=74 | base-a | 8.9 | 296.5 | 751.3 | 467.3 | 0.0 | 276.1 | 0.28 | 18.5 | 3.95 |
| budget74:-:--resident-budget-gib=74 | opt-a | 9.2 | 274.5 | 407.6 | 371.1 | 0.0 | 254.1 | 0.51 | 8.5 | 4.05 |
| budget74:-:--resident-budget-gib=74 | opt-b | 8.4 | 307.9 | 435.1 | 490.1 | 0.0 | 287.3 | 0.50 | 8.5 | 4.05 |
| budget74:-:--resident-budget-gib=74 | base-b | 12.9 | 200.8 | 619.9 | 251.6 | 0.0 | 181.4 | 0.27 | 18.6 | 4.03 |

| option | base tok/s | option tok/s | change | base arms' spread | >= +3 % |
|---|---|---|---|---|---|
| ub0:STRATA_UNBUFFERED_LOAD=0 | 10.31 | 10.39 | **+0.8 %** | 0.4 % | no |
| ub1:STRATA_UNBUFFERED_LOAD=1 | 10.69 | 15.79 | **+47.7 %** | 32.4 % | KEEP |
| pf:STRATA_IO_PREFETCH=1 | 10.48 | 9.57 | **-8.7 %** | 2.2 % | no |
| fetch16:STRATA_FETCH_THREADS=16 | 11.00 | 10.89 | **-1.0 %** | 3.0 % | no |
| budget56:-:--resident-budget-gib=56 | 10.52 | 12.56 | **+19.4 %** | 13.4 % | KEEP |
| budget74:-:--resident-budget-gib=74 | 10.88 | 8.78 | **-19.3 %** | 45.4 % | no |
