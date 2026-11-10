# Round 15 step 3 — probes of every placement, q5s (engine level, greedy math 1,024, warmed; the number = the mean of two consecutive warm probes whose decode agrees within 3 %; your rule of 10-07 ~14:10)

| placement | started (context) | probes / agreed | decode tok/s | ms / round | tokens / round | acceptance (greedy) | 5080 share | helper share | CPU share | CPU pool ms / round | file-tier reading ms / round (MB) | fetch wait ms / round | not in the page cache | 5080 slots | min MemAvailable GiB | swap GiB | 5080 min free MiB | 32K prompt read s |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| A | 131072 | 3 / yes | **24.55** | 109.8 | 2.70 | 0.748 | 0.694 | 0.068 | 0.238 | 93.7 | 90.3 (1588) | 0.0 | 0.00 | 2359 | 84.1 | 1.88 | 458 | 29.8 |
| B | 131072 | 2 / yes | **30.95** | 86.9 | 2.69 | 0.743 | 0.676 | 0.000 | 0.324 | 70.0 | 54.3 (183) | 0.0 | 0.22 | 2333 | 19.1 | 3.41 | 420 | 32.7 |
| C | 131072 | 4 / NO | **44.60** | 59.4 | 2.65 | 0.738 | 0.736 | 0.000 | 0.264 | – | – (–) | – | – | 2719 | 17.4 | 4.32 | 428 | 78.2 |
| D | 131072 | 4 / NO | **31.42** | 84.1 | 2.64 | 0.712 | 0.698 | 0.000 | 0.302 | 66.3 | 52.0 (169) | 0.0 | 0.21 | 2331 | 18.7 | 3.62 | 424 | 29.7 |
| E | **no**: 131072: FileExpertSource: RAM budget 77.38 GiB: 20754 of the 82.92 GiB of experts the GPU cache does not hold, by profile rank; the rest are read from the files strata ; 65536: FileExpertSource: RAM budget 78.32 GiB: 21006 of the 82.81 GiB of experts the GPU cache does not hold, by profile rank; the rest are read from the files strata ; 32768: FileExpertSource: RAM budget 79.29 GiB: 21267 of the 82.76 GiB of experts the GPU cache does not hold, by profile rank; the rest are read from the files strata  | | | | | | | | | | | | | | | | | | |

ranking by decode: C 44.60 > D 31.42 > B 30.95 > A 24.55
FULL SET ON: C B  (the best; the runner-up when within 10 % of it; placement B)
