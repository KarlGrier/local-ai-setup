# r19 — #1682 on stock v0.1.42 (STRATA_ROUTE_TAIL_SKIP=0): Q8_0, the 5080 + 64 GiB budget, read rule vs forced unbuffered (A B B A per thread setting)

| STRATA_IO_THREADS | arm | file tier (engine line) | decode tok/s | ms / round | file MB / round | file ms / round | not in the page cache | min MemAvailable GiB | max swap GiB | tail-skip ON line |
|---|---|---|---|---|---|---|---|---|---|---|
| unset (default) | rule-a | through the file cache (re-checked with the RAM copy built (64.00 GiB): 20.4 GiB available… | – | – | – | – | – | 17.8 | 4.02 | no | GUARD-STOP
| unset (default) | ub1-a | unbuffered (STRATA_UNBUFFERED_LOAD=1) | 16.57 | 152.7 | 618.8 | 94.0 | 0.00 | 15.4 | 0.00 | no |
| unset (default) | ub1-b | unbuffered (STRATA_UNBUFFERED_LOAD=1) | 15.30 | 162.7 | 673.2 | 102.4 | 0.00 | 16.2 | 2.11 | no |
| unset (default) | rule-b | through the file cache (re-checked with the RAM copy built (64.00 GiB): 20.8 GiB available… | 12.08 | 207.0 | 646.9 | 295.2 | 0.25 | 18.5 | 4.27 | no |
| 16 | rule-a | through the file cache (re-checked with the RAM copy built (64.00 GiB): 21.2 GiB available… | 12.99 | 188.6 | 622.5 | 263.6 | 0.25 | 18.8 | 4.32 | no |
| 16 | ub1-a | unbuffered (STRATA_UNBUFFERED_LOAD=1) | 16.37 | 149.1 | 598.4 | 91.1 | 0.00 | 16.2 | 2.11 | no |
| 16 | ub1-b | unbuffered (STRATA_UNBUFFERED_LOAD=1) | 15.49 | 160.7 | 674.5 | 102.4 | 0.00 | 16.6 | 2.19 | no |
| 16 | rule-b | through the file cache (re-checked with the RAM copy built (64.00 GiB): 21.4 GiB available… | 12.34 | 193.7 | 634.3 | 246.3 | 0.25 | 18.7 | 4.38 | no |
| 64 | rule-a | through the file cache (re-checked with the RAM copy built (64.00 GiB): 21.1 GiB available… | 13.28 | 176.2 | 542.5 | 212.7 | 0.24 | 18.9 | 4.37 | no |
| 64 | ub1-a | unbuffered (STRATA_UNBUFFERED_LOAD=1) | 16.64 | 149.6 | 605.9 | 92.0 | 0.00 | 16.2 | 2.19 | no |
| 64 | ub1-b | unbuffered (STRATA_UNBUFFERED_LOAD=1) | 15.76 | 159.9 | 647.4 | 99.1 | 0.00 | 16.5 | 2.23 | no |
| 64 | rule-b | through the file cache (re-checked with the RAM copy built (64.00 GiB): 21.1 GiB available… | 12.81 | 197.5 | 629.5 | 247.6 | 0.24 | 18.6 | 4.38 | no |
| unset (default), repeated | rule-a | through the file cache (re-checked with the RAM copy built (64.00 GiB): 21.0 GiB available… | 12.64 | 201.7 | 668.8 | 271.7 | 0.24 | 18.7 | 4.39 | no |
| unset (default), repeated | ub1-a | unbuffered (STRATA_UNBUFFERED_LOAD=1) | 15.68 | 160.7 | 661.6 | 100.5 | 0.00 | 17.2 | 2.26 | no |
| unset (default), repeated | ub1-b | unbuffered (STRATA_UNBUFFERED_LOAD=1) | 16.61 | 149.9 | 605.9 | 92.2 | 0.00 | 16.6 | 2.25 | no |
| unset (default), repeated | rule-b | through the file cache (re-checked with the RAM copy built (64.00 GiB): 21.0 GiB available… | 13.91 | 179.0 | 613.7 | 201.5 | 0.23 | 18.8 | 4.38 | no |

- STRATA_IO_THREADS unset: rule 12.08 tok/s (arms 12.08), forced unbuffered 15.94 (arms 16.57, 15.30): **+31.9 %**
- STRATA_IO_THREADS 16: rule 12.66 tok/s (arms 12.99, 12.34), forced unbuffered 15.93 (arms 16.37, 15.49): **+25.8 %**
- STRATA_IO_THREADS 64: rule 13.04 tok/s (arms 13.28, 12.81), forced unbuffered 16.20 (arms 16.64, 15.76): **+24.2 %**
- STRATA_IO_THREADS unset, repeated: rule 13.28 tok/s (arms 12.64, 13.91), forced unbuffered 16.14 (arms 15.68, 16.61): **+21.6 %**
