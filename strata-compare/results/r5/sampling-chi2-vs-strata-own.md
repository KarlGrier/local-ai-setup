| case | samples | on path (expected share) | tie: observed vs expected (llama.cpp probabilities through the chain) | chi-square (dof) | p-value | outside the allowed set |
|---|---|---|---|---|---|---|
| arith-j3 T=0.6 | 1000 | 954 (0.947) | '=': 501 vs 515.6, ' ': 453 vs 438.4 | 0.90 (1) | 0.344 | 0 |
| code-j3 T=0.6 | 1000 | 125 (0.137) | ' enough': 46 vs 45.8, ' complete': 37 vs 36.6, ' include': 24 vs 24.4, ' with': 11 vs 12.3, 'rest': 7 vs 6.0 | 0.31 (4) | 0.989 | 0 |
| science-j3 T=0.6 | 1000 | 782 (0.811) | ',': 368 vs 362.2, ';': 342 vs 351.2, '.': 63 vs 58.2, '...': 9 vs 10.5 | 0.94 (3) | 0.815 | 0 |
| arith-j0 T=1.0 | 1000 | 1000 (1.000) | '=': 516 vs 525.3, ' ': 484 vs 474.7 | 0.35 (1) | 0.555 | 0 |
| arith-j3 T=1.0 | 1000 | 871 (0.850) | '=': 439 vs 456.7, ' ': 432 vs 414.3 | 1.44 (1) | 0.231 | 0 |
| code-j0 T=1.0 | 1000 | 1000 (1.000) | ' complete': 237 vs 261.1, ' enough': 296 vs 256.0, ' include': 179 vs 203.8, ' with': 138 vs 124.0, ' sufficient': 44 vs 34.3, ' maybe': 30 vs 31.7, ' includes': 26 vs 31.7, ' detailed': 21 vs 29.6, ' thorough': 29 vs 27.8 | 19.43 (8) | 0.013 | 0 |
| code-j3 T=1.0 | 1000 | 128 (0.120) | ' enough': 34 vs 35.8, ' complete': 32 vs 31.3, ' include': 29 vs 24.5, ' with': 16 vs 16.3, 'rest': 17 vs 20.1 | 1.39 (4) | 0.846 | 0 |
| science-j0 T=1.0 | 1000 | 1000 (1.000) | ',': 433 vs 409.1, ';': 403 vs 404.9, '.': 110 vs 139.1, '...': 54 vs 46.9 | 8.56 (3) | 0.036 | 0 |
| science-j3 T=1.0 | 1000 | 573 (0.588) | ',': 223 vs 235.3, ';': 263 vs 231.0, '.': 67 vs 78.6, '...': 20 vs 28.1 | 9.10 (3) | 0.028 | 0 |
