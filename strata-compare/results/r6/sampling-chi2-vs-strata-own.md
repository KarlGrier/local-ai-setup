| case | samples | on path (expected share) | tie: observed vs expected (llama.cpp probabilities through the chain) | chi-square (dof) | p-value | outside the allowed set |
|---|---|---|---|---|---|---|
| arith-j3 T=0.6 | 1000 | 949 (0.947) | '=': 495 vs 499.6, ' ': 454 vs 449.4 | 0.09 (1) | 0.764 | 0 |
| code-j3 T=0.6 | 1000 | 149 (0.137) | ' enough': 53 vs 52.3, ' complete': 43 vs 45.2, ' include': 31 vs 29.5, ' with': 19 vs 15.0, 'rest': 3 vs 7.0 | 3.55 (4) | 0.470 | 0 |
| science-j3 T=0.6 | 1000 | 790 (0.811) | ';': 318 vs 393.5, ',': 407 vs 320.6, '.': 57 vs 64.7, '...': 8 vs 11.2 | 39.63 (3) | 0.000 | 0 |
| arith-j0 T=1.0 | 1000 | 1000 (1.000) | '=': 515 vs 512.4, ' ': 485 vs 487.6 | 0.03 (1) | 0.868 | 0 |
| arith-j3 T=1.0 | 1000 | 871 (0.850) | '=': 439 vs 449.3, ' ': 432 vs 421.7 | 0.49 (1) | 0.483 | 0 |
| code-j0 T=1.0 | 1000 | 1000 (1.000) | ' complete': 272 vs 272.9, ' enough': 243 vs 247.0, ' include': 192 vs 201.4, ' with': 133 vs 122.6, ' sufficient': 32 vs 34.9, ' includes': 34 vs 32.5, ' detailed': 32 vs 32.3, ' maybe': 41 vs 29.0, ' thorough': 21 vs 27.6 | 8.27 (8) | 0.408 | 0 |
| code-j3 T=1.0 | 1000 | 133 (0.120) | ' enough': 24 vs 36.3, ' complete': 39 vs 33.3, ' include': 34 vs 25.7, ' with': 16 vs 17.1, 'rest': 20 vs 20.6 | 7.91 (4) | 0.095 | 0 |
| science-j0 T=1.0 | 1000 | 1000 (1.000) | ',': 424 vs 430.9, ';': 379 vs 390.5, '.': 152 vs 130.6, '...': 45 vs 48.0 | 4.15 (3) | 0.246 | 0 |
| science-j3 T=1.0 | 1000 | 548 (0.588) | ';': 210 vs 234.1, ',': 243 vs 207.0, '.': 77 vs 79.2, '...': 18 vs 27.7 | 12.21 (3) | 0.007 | 0 |
