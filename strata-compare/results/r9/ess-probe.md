| case | samples | on path (expected share) | tie: observed vs expected (llama.cpp probabilities through the chain) | chi-square (dof) | p-value | outside the allowed set |
|---|---|---|---|---|---|---|
| arith-j0 T=1.0 | 1500 | 1500 (1.000) | '=': 772 vs 767.2, ' ': 728 vs 732.8 | 0.06 (1) | 0.803 | 0 |
| arith-j3 T=1.0 | 1500 | 1319 (0.850) | '=': 686 vs 679.8, ' ': 633 vs 639.2 | 0.12 (1) | 0.731 | 0 |
| code-j0 T=1.0 | 1500 | 1500 (1.000) | ' enough': 403 vs 418.1, ' complete': 394 vs 381.1, ' include': 279 vs 288.4, ' with': 198 vs 184.5, ' sufficient': 53 vs 54.6, ' maybe': 52 vs 50.4, ' includes': 34 vs 42.8, ' detailed': 48 vs 41.7, ' thorough': 39 vs 38.3 | 5.12 (8) | 0.744 | 0 |
| code-j3 T=1.0 | 1500 | 165 (0.120) | ' complete': 44 vs 42.5, ' enough': 36 vs 40.6, ' include': 39 vs 34.7, ' with': 16 vs 20.7, ' sufficient': 6 vs 5.8, ' includes': 6 vs 5.7, ' detailed': 6 vs 5.2, ' maybe': 7 vs 5.2, 'rest': 5 vs 4.6 | 2.96 (8) | 0.937 | 0 |
| science-j0 T=1.0 | 1500 | 1500 (1.000) | ',': 638 vs 637.2, ';': 614 vs 582.8, '.': 189 vs 200.6, '...': 59 vs 79.5 | 7.60 (3) | 0.055 | 0 |
| science-j3 T=1.0 | 1500 | 821 (0.588) | ',': 356 vs 356.6, ';': 306 vs 305.6, '.': 106 vs 115.9, '...': 53 vs 43.0 | 3.19 (3) | 0.363 | 0 |
