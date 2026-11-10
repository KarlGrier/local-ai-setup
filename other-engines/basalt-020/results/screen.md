# 9-workload speed screen: Basalt 0.2.0 (defaults, basalt serve) vs P028x (gap 16 X arm)

Workloads (9): A-edit, B-write, R1-verify20k, R2-report54k, R3-extract5k, R4-agent33k, W1-think, W2-code, W3-research. Each pass: the geometric mean over the workloads; cells: the mean of the passes' geometric means (min-max, spread).

| arm | passes | decode (client clock) | prompt (client clock) | decode (server timings) | prompt (server timings) |
|---|---|---|---|---|---|
| P028x (gap 16 X) | 3 | 157.5 (156.1-159.0, 1.9 %) | 2,113.5 (2,108.4-2,116.8, 0.4 %) | 157.2 (155.9-158.8, 1.9 %) | 2,091.9 (2,086.9-2,097.8, 0.5 %) |
| Basalt 0.2.0 defaults | 3 | 161.8 (158.7-164.2, 3.5 %) | 2,436.5 (2,425.3-2,443.8, 0.8 %) | 162.4 (159.9-164.9, 3.1 %) | - |

Basalt vs P028x: decode +2.8 %, prompt +15.3 %, decode_server +3.3 %

| workload | prompt tok | P028x decode | Basalt decode | diff | P028x prompt | Basalt prompt | diff | completion tok P028x / Basalt |
|---|---|---|---|---|---|---|---|---|
| A-edit | 2678 | 129.3 | 159.5 | +23.4 % | 2,641 | 2,641 | +0.0 % | [436, 588, 177] / [282, 365, 492] |
| B-write | 1369 | 170.2 | 172.6 | +1.4 % | 1,620 | 1,901 | +17.3 % | [1540, 928, 2059] / [1056, 2686, 4096] |
| R1-verify20k | 24241 | 155.9 | 153.0 | -1.9 % | 4,389 | 5,395 | +22.9 % | [3803, 3631, 3879] / [3610, 3731, 3678] |
| R2-report54k | 54071 | 153.6 | 148.1 | -3.6 % | 4,502 | 5,448 | +21.0 % | [2858, 2864, 4096] / [4096, 2828, 3179] |
| R3-extract5k | 5011 | 179.8 | 179.3 | -0.3 % | 3,501 | 3,673 | +4.9 % | [1080, 1085, 1033] / [1090, 1094, 1421] |
| R4-agent33k | 33415 | 134.6 | 131.6 | -2.2 % | 4,272 | 5,403 | +26.5 % | [315, 263, 282] / [226, 259, 249] |
| W1-think | 109 | 176.5 | 183.0 | +3.7 % | 379 | 423 | +11.4 % | [3072, 3072, 3072] / [3072, 3072, 3072] |
| W2-code | 125 | 161.8 | 169.9 | +5.0 % | 395 | 450 | +14.0 % | [3072, 3072, 3072] / [3072, 3072, 3072] |
| W3-research | 26728 | 164.4 | 167.8 | +2.1 % | 4,443 | 5,437 | +22.4 % | [2048, 2048, 2048] / [2048, 2048, 2048] |
