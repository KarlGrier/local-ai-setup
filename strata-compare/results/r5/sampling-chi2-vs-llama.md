| case | samples | on path (expected share) | tie: observed vs expected (llama.cpp probabilities through the chain) | chi-square (dof) | p-value | outside the allowed set |
|---|---|---|---|---|---|---|
| arith-j3 T=0.6 | 1000 | 954 (0.947) | '=': 501 vs 503.0, ' ': 453 vs 451.0 | 0.02 (1) | 0.898 | 0 |
| code-j3 T=0.6 | 1000 | 125 (0.137) | ' complete': 37 vs 42.9, ' enough': 46 vs 38.7, ' include': 24 vs 25.8, ' with': 11 vs 11.6, 'rest': 7 vs 6.0 | 2.49 (4) | 0.646 | 0 |
| science-j3 T=0.6 | 1000 | 782 (0.811) | ';': 342 vs 390.1, ',': 368 vs 317.0, '.': 63 vs 64.9, '...': 9 vs 10.0 | 14.29 (3) | 0.003 | 0 |
| arith-j0 T=1.0 | 1000 | 1000 (1.000) | '=': 516 vs 516.3, ' ': 484 vs 483.7 | 0.00 (1) | 0.983 | 0 |
| arith-j3 T=1.0 | 1000 | 871 (0.850) | '=': 439 vs 449.7, ' ': 432 vs 421.3 | 0.53 (1) | 0.467 | 0 |
| code-j0 T=1.0 | 1000 | 1000 (1.000) | ' complete': 237 vs 269.0, ' enough': 296 vs 253.0, ' include': 179 vs 198.4, ' with': 138 vs 122.6, ' detailed': 21 vs 34.5, ' includes': 26 vs 33.8, ' sufficient': 44 vs 33.3, ' maybe': 30 vs 29.3, ' thorough': 29 vs 26.2 | 25.81 (8) | 0.001 | 0 |
| code-j3 T=1.0 | 1000 | 128 (0.120) | ' complete': 32 vs 34.4, ' enough': 34 vs 32.4, ' include': 29 vs 25.4, ' with': 16 vs 15.7, 'rest': 17 vs 20.1 | 1.25 (4) | 0.869 | 0 |
| science-j0 T=1.0 | 1000 | 1000 (1.000) | ';': 403 vs 428.2, ',': 433 vs 378.1, '.': 110 vs 146.0, '...': 54 vs 47.7 | 19.16 (3) | 0.000 | 0 |
| science-j3 T=1.0 | 1000 | 573 (0.588) | ';': 263 vs 245.4, ',': 223 vs 216.7, '.': 67 vs 83.7, '...': 20 vs 27.3 | 6.73 (3) | 0.081 | 0 |
