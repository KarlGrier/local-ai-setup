# Round 15 step 3 — probes of every placement, q8 (engine level, greedy math 1,024, warmed; the number = the mean of two consecutive warm probes whose decode agrees within 3 %; your rule of 10-07 ~14:10)

| placement | started (context) | probes / agreed | decode tok/s | ms / round | tokens / round | acceptance (greedy) | 5080 share | helper share | CPU share | CPU pool ms / round | file-tier reading ms / round (MB) | fetch wait ms / round | not in the page cache | 5080 slots | min MemAvailable GiB | swap GiB | 5080 min free MiB | 32K prompt read s |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| A | 131072 | 4 / yes | **12.98** | 203.4 | 2.64 | 0.729 | 0.610 | 0.058 | 0.332 | 185.2 | 250.5 (2564) | 0.0 | 0.03 | 1609 | 83.4 | 2.72 | 444 | 73.9 |
| B | 131072 | 2 / yes | **10.82** | 235.8 | 2.55 | 0.713 | 0.588 | 0.000 | 0.412 | 215.8 | 314.8 (650) | 0.0 | 0.26 | 1589 | 18.7 | 4.01 | 416 | 67.4 |
| C | **no**:  | | | | | | | | | | | | | | | | | | |
| D | 131072 | 4 / yes | **11.36** | 241.4 | 2.74 | 0.750 | 0.620 | 0.000 | 0.380 | 219.0 | 342.0 (700) | 0.0 | 0.25 | 1589 | 17.4 | 4.09 | 414 | 67.3 |
| E | **no**: 131072: FileExpertSource: RAM budget 76.87 GiB: 15804 of the 111.80 GiB of experts the GPU cache does not hold, by profile rank; the rest are read from the files strata; 65536: FileExpertSource: RAM budget 77.26 GiB: 15885 of the 111.69 GiB of experts the GPU cache does not hold, by profile rank; the rest are read from the files strata; 32768: FileExpertSource: RAM budget 78.53 GiB: 16147 of the 111.64 GiB of experts the GPU cache does not hold, by profile rank; the rest are read from the files strata | | | | | | | | | | | | | | | | | | |

ranking by decode: A 12.98 > D 11.36 > B 10.82
FULL SET ON: A B  (the best; the runner-up when within 10 % of it; placement B)
