| case | samples | on path (expected share) | tie: observed vs expected (llama.cpp probabilities through the chain) | chi-square (dof) | p-value | outside the allowed set |
|---|---|---|---|---|---|---|
| arith-j3 T=0.6 | 1000 | 949 (0.947) | '=': 495 vs 500.3, ' ': 454 vs 448.7 | 0.12 (1) | 0.729 | 0 |
| code-j3 T=0.6 | 1000 | 149 (0.137) | ' complete': 43 vs 51.1, ' enough': 53 vs 46.2, ' include': 31 vs 30.8, ' with': 19 vs 13.8, 'rest': 3 vs 7.2 | 6.70 (4) | 0.152 | 0 |
| science-j3 T=0.6 | 1000 | 790 (0.811) | ';': 318 vs 394.0, ',': 407 vs 320.2, '.': 57 vs 65.6, '...': 8 vs 10.2 | 39.75 (3) | 0.000 | 0 |
| arith-j0 T=1.0 | 1000 | 1000 (1.000) | '=': 515 vs 516.3, ' ': 485 vs 483.7 | 0.01 (1) | 0.932 | 0 |
| arith-j3 T=1.0 | 1000 | 871 (0.850) | '=': 439 vs 449.7, ' ': 432 vs 421.3 | 0.53 (1) | 0.467 | 0 |
| code-j0 T=1.0 | 1000 | 1000 (1.000) | ' complete': 272 vs 269.0, ' enough': 243 vs 253.0, ' include': 192 vs 198.4, ' with': 133 vs 122.6, ' detailed': 32 vs 34.5, ' includes': 34 vs 33.8, ' sufficient': 32 vs 33.3, ' maybe': 41 vs 29.3, ' thorough': 21 vs 26.2 | 7.48 (8) | 0.486 | 0 |
| code-j3 T=1.0 | 1000 | 133 (0.120) | ' complete': 39 vs 35.8, ' enough': 24 vs 33.6, ' include': 34 vs 26.4, ' with': 16 vs 16.3, 'rest': 20 vs 20.9 | 5.30 (4) | 0.258 | 0 |
| science-j0 T=1.0 | 1000 | 1000 (1.000) | ';': 379 vs 428.2, ',': 424 vs 378.1, '.': 152 vs 146.0, '...': 45 vs 47.7 | 11.62 (3) | 0.009 | 0 |
| science-j3 T=1.0 | 1000 | 548 (0.588) | ';': 210 vs 234.7, ',': 243 vs 207.2, '.': 77 vs 80.0, '...': 18 vs 26.1 | 11.41 (3) | 0.010 | 0 |
