# r17 — Q8_0 stand-in, placement B, stock v0.1.41: read rule vs forced unbuffered (A B B A)

| arm | file tier (engine line) | decode tok/s | ms / round | file MB / round | file ms / round | not in the page cache | min MemAvailable GiB | max swap GiB |
|---|---|---|---|---|---|---|---|---|
| rule-a | through the file cache (re-checked with the RAM copy built (64.00 GiB): 20.2 GiB available, 0.0 GiB of it still to be taken by the RAM copy, 55.5 GiB of experts read from the files: the file cache can | 12.0 | 204.7 | 595.0 | 283.5 | 0.29 | 17.6 | 5.51 |
| ub1-a | unbuffered (STRATA_UNBUFFERED_LOAD=1) | 15.3 | 156.0 | 598.8 | 95.8 | 0.00 | 16.4 | 3.36 |
| ub1-b | unbuffered (STRATA_UNBUFFERED_LOAD=1) | 15.6 | 153.7 | 617.9 | 95.3 | 0.00 | 16.2 | 3.35 |
| rule-b | through the file cache (re-checked with the RAM copy built (64.00 GiB): 20.4 GiB available, 0.0 GiB of it still to be taken by the RAM copy, 55.5 GiB of experts read from the files: the file cache can | 10.7 | 222.6 | 594.0 | 329.1 | 0.30 | 18.3 | 5.63 |

rule 11.33 tok/s (arms 11.97, 10.69), forced unbuffered 15.43 (arms 15.26, 15.61): **+36.2 %**
