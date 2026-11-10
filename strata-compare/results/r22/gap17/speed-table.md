| arm | workload | n | tokens | decode tok/s (client) | decode tok/s (engine) | accepted / drafted | expert-cache hit % | prompt tok/s | finish | drafts per window |
|---|---|---:|---:|---:|---:|---:|---:|---:|---|---:|
| B1a | A-edit | 1 | 336 | 118.8 | 118.5 | 270/347 (78%) | 46.8 | 2635.8 | tool_calls | 5.10 |
| B1a | B-write | 1 | 1120 | 184.7 | 184.4 | 889/1152 (77%) | 82.6 | 1608.2 | tool_calls | 4.90 |
| B1e | E1-rewrite | 1 | 2330 | 165.8 | 165.7 | 1829/2224 (82%) | 76.7 | 1634.1 | stop | 4.40 |
| B1e | E2-rewrite-nothink | 1 | 1483 | 194.6 | 194.3 | 1237/1367 (90%) | 78.7 | 1791.9 | stop | 5.47 |
| B1n | W1-think | 1 | 3072 | 169.9 | 169.7 | 2080/2894 (72%) | 89.1 | 372.3 | length | 2.97 |
| B1n | W2-code | 1 | 3072 | 171.1 | 171.0 | 2277/3138 (73%) | 82.2 | 390.3 | length | 3.95 |
| B1n | W3-research | 1 | 2048 | 163.1 | 163.0 | 1560/2049 (76%) | 83.1 | 4432.7 | length | 4.16 |
| B1r | R1-verify20k | 1 | 3723 | 153.8 | 153.6 | 2678/3491 (77%) | 79.8 | 4383.5 | stop | 3.38 |
| B1r | R2-report54k | 1 | 2764 | 145.2 | 145.1 | 1931/2845 (68%) | 76.0 | 4498.1 | stop | 3.41 |
| B1r | R3-extract5k | 1 | 1081 | 178.1 | 177.8 | 858/1062 (81%) | 80.6 | 3461.1 | stop | 4.76 |
| B1r | R4-agent33k | 1 | 367 | 133.6 | 133.2 | 265/383 (69%) | 79.2 | 4267.0 | tool_calls | 3.72 |
| B2a | A-edit | 1 | 170 | 127.2 | 126.4 | 143/160 (89%) | 41.2 | 2634.5 | tool_calls | 5.00 |
| B2a | B-write | 1 | 2677 | 156.7 | 156.6 | 1875/2730 (69%) | 82.6 | 1602.7 | tool_calls | 3.38 |
| B2e | E1-rewrite | 1 | 3604 | 168.6 | 168.5 | 2769/3491 (79%) | 79.4 | 1637.7 | stop | 4.18 |
| B2e | E2-rewrite-nothink | 1 | 1385 | 195.3 | 195.0 | 1172/1301 (90%) | 78.1 | 1793.5 | stop | 6.00 |
| B2n | W1-think | 1 | 3072 | 187.5 | 187.4 | 2313/3203 (72%) | 87.7 | 373.3 | length | 4.31 |
| B2n | W2-code | 1 | 3072 | 156.7 | 156.6 | 2151/3253 (66%) | 85.1 | 400.5 | length | 3.53 |
| B2n | W3-research | 1 | 2048 | 159.1 | 158.9 | 1548/2049 (76%) | 82.3 | 4432.7 | length | 4.10 |
| B2r | R1-verify20k | 1 | 3815 | 156.2 | 156.0 | 2728/3577 (76%) | 81.6 | 4381.3 | stop | 3.33 |
| B2r | R2-report54k | 1 | 3208 | 149.6 | 149.6 | 2306/3307 (70%) | 75.9 | 4501.1 | stop | 3.66 |
| B2r | R3-extract5k | 1 | 1328 | 177.0 | 176.7 | 1044/1342 (78%) | 80.3 | 3534.9 | stop | 4.68 |
| B2r | R4-agent33k | 1 | 383 | 130.3 | 130.0 | 269/411 (65%) | 81.5 | 4267.6 | tool_calls | 3.61 |
| B3a | A-edit | 1 | 502 | 129.7 | 129.4 | 373/488 (76%) | 61.9 | 2653.3 | tool_calls | 3.75 |
| B3a | B-write | 1 | 2555 | 156.7 | 156.7 | 1827/2612 (70%) | 81.3 | 1632.7 | tool_calls | 3.58 |
| B3e | E1-rewrite | 1 | 3739 | 170.4 | 170.3 | 2832/3545 (80%) | 80.5 | 1636.8 | stop | 3.89 |
| B3e | E2-rewrite-nothink | 1 | 1398 | 193.8 | 193.5 | 1170/1286 (91%) | 78.2 | 1785.2 | stop | 5.54 |
| B3n | W1-think | 1 | 3072 | 164.5 | 164.4 | 2019/2892 (70%) | 89.1 | 350.2 | length | 2.79 |
| B3n | W2-code | 1 | 3072 | 155.0 | 154.9 | 2128/3242 (66%) | 82.3 | 402.6 | length | 3.42 |
| B3n | W3-research | 1 | 2048 | 178.4 | 178.4 | 1622/1971 (82%) | 82.6 | 4433.4 | length | 4.76 |
| B3r | R1-verify20k | 1 | 3805 | 156.4 | 156.3 | 2715/3493 (78%) | 81.0 | 4377.5 | stop | 3.25 |
| B3r | R2-report54k | 1 | 2431 | 144.2 | 144.2 | 1678/2482 (68%) | 75.7 | 4499.6 | stop | 3.30 |
| B3r | R3-extract5k | 1 | 1306 | 184.0 | 183.7 | 1042/1280 (81%) | 80.8 | 3467.8 | stop | 4.85 |
| B3r | R4-agent33k | 1 | 366 | 129.4 | 129.1 | 263/400 (66%) | 80.9 | 4269.4 | tool_calls | 3.81 |
| F1a | A-edit | 1 | 799 | 140.6 | 140.4 | 619/791 (78%) | 67.4 | 2649.8 | tool_calls | 4.32 |
| F1a | B-write | 1 | 2417 | 159.4 | 159.3 | 1682/2480 (68%) | 84.6 | 1512.2 | tool_calls | 3.37 |
| F1e | E1-rewrite | 1 | 3090 | 169.3 | 169.2 | 2392/2901 (82%) | 78.1 | 1638.9 | stop | 4.16 |
| F1e | E2-rewrite-nothink | 1 | 1381 | 196.7 | 196.4 | 1162/1260 (92%) | 78.5 | 1791.0 | stop | 5.65 |
| F1n | W1-think | 1 | 3072 | 169.1 | 169.0 | 2081/2932 (71%) | 89.2 | 391.2 | length | 3.00 |
| F1n | W2-code | 1 | 3072 | 155.1 | 154.8 | 2044/3169 (64%) | 81.6 | 393.3 | length | 3.13 |
| F1n | W3-research | 1 | 2048 | 164.0 | 163.8 | 1584/1997 (79%) | 85.7 | 4427.7 | length | 4.28 |
| F1r | R1-verify20k | 1 | 3907 | 152.7 | 152.4 | 2752/3641 (76%) | 81.4 | 4382.8 | stop | 3.20 |
| F1r | R2-report54k | 1 | 3152 | 145.6 | 145.5 | 2206/3218 (69%) | 74.6 | 4498.2 | stop | 3.39 |
| F1r | R3-extract5k | 1 | 1313 | 186.4 | 186.1 | 1037/1248 (83%) | 80.4 | 3513.7 | stop | 4.52 |
| F1r | R4-agent33k | 1 | 360 | 125.2 | 124.9 | 257/392 (66%) | 81.8 | 4264.8 | tool_calls | 3.63 |
| F2a | A-edit | 1 | 170 | 131.4 | 130.7 | 143/158 (91%) | 45.0 | 2633.1 | tool_calls | 4.94 |
| F2a | B-write | 1 | 1593 | 170.8 | 170.7 | 1188/1630 (73%) | 83.3 | 1588.9 | tool_calls | 4.00 |
| F2e | E1-rewrite | 1 | 3344 | 162.8 | 162.7 | 2520/3226 (78%) | 78.9 | 1634.0 | stop | 3.90 |
| F2e | E2-rewrite-nothink | 1 | 1386 | 191.6 | 191.3 | 1162/1291 (90%) | 77.9 | 1791.1 | stop | 5.66 |
| F2n | W1-think | 1 | 3072 | 164.4 | 164.2 | 1976/2871 (69%) | 89.9 | 378.8 | length | 2.66 |
| F2n | W2-code | 1 | 3072 | 159.1 | 159.0 | 2183/3142 (69%) | 83.1 | 388.6 | length | 3.51 |
| F2n | W3-research | 1 | 2048 | 163.4 | 163.3 | 1579/1993 (79%) | 81.7 | 4431.7 | length | 4.25 |
| F2r | R1-verify20k | 1 | 3919 | 157.5 | 157.1 | 2831/3609 (78%) | 80.2 | 4386.0 | stop | 3.36 |
| F2r | R2-report54k | 1 | 2887 | 152.9 | 152.4 | 2110/2937 (72%) | 77.3 | 4501.3 | stop | 3.76 |
| F2r | R3-extract5k | 1 | 1271 | 186.2 | 186.0 | 1021/1226 (83%) | 79.8 | 3459.3 | stop | 4.90 |
| F2r | R4-agent33k | 1 | 378 | 136.7 | 136.4 | 276/378 (73%) | 80.9 | 4265.2 | tool_calls | 3.60 |
| F3a | A-edit | 1 | 803 | 147.0 | 146.8 | 628/780 (81%) | 68.2 | 2640.5 | tool_calls | 4.38 |
| F3a | B-write | 1 | 2895 | 164.7 | 164.6 | 2174/3068 (71%) | 82.6 | 1607.4 | tool_calls | 4.23 |
| F3e | E1-rewrite | 1 | 3337 | 167.8 | 167.8 | 2588/3147 (82%) | 77.6 | 1641.7 | stop | 4.20 |
| F3e | E2-rewrite-nothink | 1 | 1384 | 192.3 | 192.0 | 1163/1272 (91%) | 77.4 | 1775.4 | stop | 5.65 |
| F3n | W1-think | 1 | 3072 | 187.4 | 187.3 | 2309/3116 (74%) | 87.3 | 369.5 | length | 4.17 |
| F3n | W2-code | 1 | 3072 | 165.2 | 165.1 | 2197/3158 (70%) | 86.3 | 400.2 | length | 3.61 |
| F3n | W3-research | 1 | 2048 | 158.8 | 158.6 | 1550/2076 (75%) | 83.1 | 4401.1 | length | 4.17 |
| F3r | R1-verify20k | 1 | 3567 | 155.0 | 154.8 | 2556/3319 (77%) | 80.4 | 4384.5 | stop | 3.34 |
| F3r | R2-report54k | 1 | 3142 | 147.1 | 147.1 | 2218/3270 (68%) | 75.3 | 4499.5 | stop | 3.52 |
| F3r | R3-extract5k | 1 | 1236 | 178.7 | 178.4 | 966/1202 (80%) | 81.5 | 3448.3 | stop | 4.45 |
| F3r | R4-agent33k | 1 | 331 | 132.5 | 132.1 | 241/350 (69%) | 81.2 | 4265.2 | tool_calls | 3.76 |
| L1a | A-edit | 1 | 1446 | 152.2 | 152.1 | 1076/1407 (76%) | 75.5 | 2614.6 | tool_calls | 3.77 |
| L1a | B-write | 1 | 3180 | 154.2 | 154.2 | 2177/3253 (67%) | 83.9 | 1606.8 | tool_calls | 3.24 |
| L1e | E1-rewrite | 1 | 3720 | 163.7 | 163.6 | 2896/3621 (80%) | 77.0 | 1634.2 | stop | 4.37 |
| L1e | E2-rewrite-nothink | 1 | 1394 | 194.2 | 193.9 | 1191/1324 (90%) | 78.6 | 1792.9 | stop | 6.40 |
| L1n | W1-think | 1 | 3072 | 187.2 | 187.1 | 2285/3152 (72%) | 88.6 | 382.8 | length | 4.09 |
| L1n | W2-code | 1 | 3072 | 153.7 | 153.6 | 2086/3323 (63%) | 85.7 | 401.9 | length | 3.37 |
| L1n | W3-research | 1 | 2048 | 167.2 | 167.1 | 1567/1957 (80%) | 84.3 | 4431.9 | length | 4.07 |
| L1r | R1-verify20k | 1 | 3558 | 155.5 | 155.3 | 2535/3279 (77%) | 80.3 | 4382.9 | stop | 3.26 |
| L1r | R2-report54k | 1 | 2885 | 145.0 | 144.9 | 2018/2977 (68%) | 76.9 | 4500.7 | stop | 3.42 |
| L1r | R3-extract5k | 1 | 927 | 173.2 | 172.8 | 733/921 (80%) | 80.7 | 3459.3 | stop | 4.75 |
| L1r | R4-agent33k | 1 | 280 | 138.2 | 137.7 | 208/287 (72%) | 79.3 | 4264.2 | tool_calls | 3.83 |
| L2a | A-edit | 1 | 171 | 126.5 | 125.7 | 138/156 (88%) | 41.9 | 2647.4 | tool_calls | 4.73 |
| L2a | B-write | 1 | 1343 | 172.8 | 172.7 | 1046/1423 (74%) | 81.8 | 1588.0 | tool_calls | 4.79 |
| L2e | E1-rewrite | 1 | 3007 | 167.6 | 167.6 | 2333/2874 (81%) | 77.8 | 1645.6 | stop | 4.26 |
| L2e | E2-rewrite-nothink | 1 | 1373 | 195.7 | 195.3 | 1157/1252 (92%) | 78.1 | 1793.7 | stop | 5.69 |
| L2n | W1-think | 1 | 3072 | 164.8 | 164.7 | 2022/2914 (69%) | 89.4 | 358.1 | length | 2.81 |
| L2n | W2-code | 1 | 3072 | 159.1 | 158.8 | 2064/3123 (66%) | 82.5 | 388.5 | length | 3.15 |
| L2n | W3-research | 1 | 2048 | 159.4 | 159.3 | 1559/2034 (77%) | 86.5 | 4442.4 | length | 4.11 |
| L2r | R1-verify20k | 1 | 3902 | 156.6 | 156.1 | 2798/3593 (78%) | 80.8 | 4389.6 | stop | 3.29 |
| L2r | R2-report54k | 1 | 3882 | 148.4 | 148.1 | 2706/4034 (67%) | 76.2 | 4499.2 | stop | 3.42 |
| L2r | R3-extract5k | 1 | 1160 | 184.7 | 183.9 | 923/1135 (81%) | 82.5 | 3466.0 | stop | 4.79 |
| L2r | R4-agent33k | 1 | 275 | 124.8 | 124.4 | 194/298 (65%) | 81.6 | 4265.9 | tool_calls | 3.55 |
| L3a | A-edit | 1 | 178 | 129.1 | 128.3 | 149/169 (88%) | 42.7 | 2634.1 | tool_calls | 4.97 |
| L3a | B-write | 1 | 1532 | 166.1 | 166.0 | 1148/1593 (72%) | 81.8 | 1582.0 | tool_calls | 4.15 |
| L3e | E1-rewrite | 1 | 2213 | 166.1 | 166.0 | 1808/2163 (84%) | 74.5 | 1635.2 | stop | 5.34 |
| L3e | E2-rewrite-nothink | 1 | 1384 | 191.0 | 190.8 | 1174/1323 (89%) | 78.9 | 1798.8 | stop | 6.18 |
| L3n | W1-think | 1 | 3072 | 168.6 | 168.4 | 2078/2927 (71%) | 89.3 | 381.2 | length | 3.00 |
| L3n | W2-code | 1 | 3072 | 152.8 | 152.7 | 2150/3396 (63%) | 81.0 | 385.8 | length | 3.68 |
| L3n | W3-research | 1 | 2048 | 168.1 | 167.9 | 1596/1974 (81%) | 82.9 | 4429.2 | length | 4.36 |
| L3r | R1-verify20k | 1 | 3626 | 156.5 | 156.2 | 2536/3235 (78%) | 82.1 | 4384.3 | stop | 3.01 |
| L3r | R2-report54k | 1 | 2603 | 148.2 | 148.1 | 1847/2642 (70%) | 74.1 | 4499.4 | stop | 3.49 |
| L3r | R3-extract5k | 1 | 1027 | 175.0 | 173.7 | 814/1027 (79%) | 80.3 | 3443.7 | stop | 4.73 |
| L3r | R4-agent33k | 1 | 289 | 125.8 | 125.4 | 206/313 (66%) | 80.5 | 4262.7 | tool_calls | 3.56 |
| P1a | A-edit | 1 | 418 | 139.4 | 139.0 | 344/391 (88%) | 54.7 | 2629.2 | tool_calls | 5.14 |
| P1a | B-write | 1 | 1723 | 165.1 | 165.0 | 1295/1750 (74%) | 80.5 | 1609.4 | tool_calls | 4.06 |
| P1e | E1-rewrite | 1 | 2955 | 164.2 | 164.1 | 2250/2852 (79%) | 78.6 | 1639.8 | stop | 4.02 |
| P1e | E2-rewrite-nothink | 1 | 1374 | 195.1 | 194.8 | 1156/1259 (92%) | 78.3 | 1786.1 | stop | 5.67 |
| P1n | W1-think | 1 | 3072 | 184.3 | 184.3 | 2296/3274 (70%) | 88.7 | 389.2 | length | 4.29 |
| P1n | W2-code | 1 | 3072 | 165.2 | 165.1 | 2199/3205 (69%) | 84.5 | 393.6 | length | 3.66 |
| P1n | W3-research | 1 | 2048 | 163.4 | 163.3 | 1566/2055 (76%) | 83.9 | 4442.9 | length | 4.24 |
| P1r | R1-verify20k | 1 | 3842 | 153.7 | 153.3 | 2682/3496 (77%) | 81.7 | 4385.7 | stop | 3.04 |
| P1r | R2-report54k | 1 | 2065 | 151.1 | 150.5 | 1492/2100 (71%) | 75.6 | 4500.6 | stop | 3.64 |
| P1r | R3-extract5k | 1 | 948 | 176.7 | 176.3 | 739/938 (79%) | 80.2 | 3439.8 | stop | 4.49 |
| P1r | R4-agent33k | 1 | 263 | 123.5 | 123.2 | 192/296 (65%) | 81.3 | 4251.9 | tool_calls | 3.89 |
| P2a | A-edit | 1 | 178 | 126.2 | 125.6 | 141/169 (83%) | 45.5 | 2631.8 | tool_calls | 4.57 |
| P2a | B-write | 1 | 1156 | 180.8 | 180.6 | 936/1151 (81%) | 79.3 | 1585.8 | tool_calls | 5.12 |
| P2e | E1-rewrite | 1 | 3159 | 167.6 | 167.6 | 2465/2942 (84%) | 76.5 | 1643.0 | stop | 4.24 |
| P2e | E2-rewrite-nothink | 1 | 1382 | 192.2 | 191.9 | 1159/1277 (91%) | 78.0 | 1793.0 | stop | 5.63 |
| P2n | W1-think | 1 | 3072 | 166.9 | 166.8 | 2045/2936 (70%) | 89.6 | 374.2 | length | 2.91 |
| P2n | W2-code | 1 | 3072 | 154.9 | 154.9 | 2156/3354 (64%) | 82.2 | 390.4 | length | 3.65 |
| P2n | W3-research | 1 | 2048 | 156.2 | 156.1 | 1546/2032 (76%) | 82.9 | 4425.4 | length | 4.03 |
| P2r | R1-verify20k | 1 | 3611 | 155.3 | 155.1 | 2534/3307 (77%) | 81.6 | 4382.2 | stop | 3.11 |
| P2r | R2-report54k | 1 | 3168 | 150.3 | 149.9 | 2280/3220 (71%) | 79.9 | 4500.3 | stop | 3.61 |
| P2r | R3-extract5k | 1 | 1083 | 171.7 | 171.4 | 828/1067 (78%) | 80.7 | 3473.2 | stop | 4.18 |
| P2r | R4-agent33k | 1 | 430 | 142.7 | 142.4 | 311/457 (68%) | 81.4 | 4263.9 | tool_calls | 3.78 |
| P3a | A-edit | 1 | 340 | 120.4 | 120.1 | 273/337 (81%) | 47.5 | 2637.0 | tool_calls | 4.96 |
| P3a | B-write | 1 | 76 | 134.9 | 133.7 | 60/74 (81%) | 67.0 | 1584.4 | tool_calls | 3.52 |
| P3e | E1-rewrite | 1 | 2954 | 166.2 | 166.1 | 2295/2796 (82%) | 77.4 | 1639.3 | stop | 4.22 |
| P3e | E2-rewrite-nothink | 1 | 1404 | 190.1 | 189.8 | 1172/1306 (90%) | 78.0 | 1799.6 | stop | 5.53 |
| P3n | W1-think | 1 | 3072 | 162.9 | 162.8 | 2003/2911 (69%) | 89.3 | 379.3 | length | 2.75 |
| P3n | W2-code | 1 | 3072 | 152.5 | 152.5 | 2097/3301 (64%) | 82.3 | 393.7 | length | 3.39 |
| P3n | W3-research | 1 | 2048 | 158.9 | 158.8 | 1570/2013 (78%) | 83.0 | 4429.7 | length | 4.19 |
| P3r | R1-verify20k | 1 | 3820 | 156.7 | 156.5 | 2669/3451 (77%) | 82.8 | 4395.5 | stop | 3.04 |
| P3r | R2-report54k | 1 | 2243 | 144.5 | 144.4 | 1576/2310 (68%) | 75.6 | 4498.7 | stop | 3.44 |
| P3r | R3-extract5k | 1 | 1237 | 171.9 | 171.6 | 971/1261 (77%) | 80.2 | 3467.8 | stop | 4.74 |
| P3r | R4-agent33k | 1 | 378 | 142.4 | 141.9 | 285/369 (77%) | 80.3 | 4255.9 | tool_calls | 3.93 |
| R2a | A-edit | 1 | 175 | 133.0 | 132.2 | 143/163 (88%) | 44.2 | 2656.4 | tool_calls | 5.09 |
| R2a | B-write | 1 | 2242 | 159.1 | 159.0 | 1582/2268 (70%) | 82.6 | 1618.1 | tool_calls | 3.43 |
| R2e | E1-rewrite | 1 | 3656 | 161.7 | 161.6 | 2684/3538 (76%) | 80.7 | 1645.7 | stop | 3.64 |
| R2e | E2-rewrite-nothink | 1 | 1383 | 191.6 | 191.3 | 1159/1288 (90%) | 78.2 | 1811.0 | stop | 5.65 |
| R2n | W1-think | 1 | 3072 | 169.2 | 170.6 | 1507/2134 (71%) | 89.1 | 369.9 | length | 2.67 |
| R2n | W2-code | 1 | 3072 | 157.3 | 164.6 | 541/744 (73%) | 92.1 | 394.3 | length | 3.56 |
| R2n | W3-research | 1 | 2048 | 162.2 | 157.2 | 2092/3105 (67%) | 83.0 | 4451.6 | length | 3.17 |
| R2r | R1-verify20k | 1 | 3690 | 154.6 | 154.5 | 2549/3321 (77%) | 82.5 | 4401.7 | stop | 2.93 |
| R2r | R2-report54k | 1 | 4096 | 158.2 | 158.1 | 3084/4160 (74%) | 77.0 | 4509.1 | length | 4.10 |
| R2r | R3-extract5k | 1 | 1080 | 181.1 | 180.2 | 863/1086 (79%) | 80.0 | 3491.4 | stop | 5.00 |
| R2r | R4-agent33k | 1 | 341 | 121.9 | 121.6 | 228/408 (56%) | 81.0 | 4278.4 | tool_calls | 3.58 |

- B1a: experts in VRAM at start: 4585 slots / 8.75 GiB
- B1e: experts in VRAM at start: 4585 slots / 8.75 GiB
- B1n: experts in VRAM at start: 4585 slots / 8.75 GiB
- B1r: experts in VRAM at start: 4585 slots / 8.75 GiB
- B2a: experts in VRAM at start: 4585 slots / 8.75 GiB
- B2e: experts in VRAM at start: 4585 slots / 8.75 GiB
- B2n: experts in VRAM at start: 4585 slots / 8.75 GiB
- B2r: experts in VRAM at start: 4585 slots / 8.75 GiB
- B3a: experts in VRAM at start: 4585 slots / 8.75 GiB
- B3e: experts in VRAM at start: 4585 slots / 8.75 GiB
- B3n: experts in VRAM at start: 4585 slots / 8.75 GiB
- B3r: experts in VRAM at start: 4585 slots / 8.75 GiB
- F1a: experts in VRAM at start: 4585 slots / 8.75 GiB
- F1e: experts in VRAM at start: 4585 slots / 8.75 GiB
- F1n: experts in VRAM at start: 4585 slots / 8.75 GiB
- F1r: experts in VRAM at start: 4585 slots / 8.75 GiB
- F2a: experts in VRAM at start: 4585 slots / 8.75 GiB
- F2e: experts in VRAM at start: 4585 slots / 8.75 GiB
- F2n: experts in VRAM at start: 4585 slots / 8.75 GiB
- F2r: experts in VRAM at start: 4585 slots / 8.75 GiB
- F3a: experts in VRAM at start: 4585 slots / 8.75 GiB
- F3e: experts in VRAM at start: 4585 slots / 8.75 GiB
- F3n: experts in VRAM at start: 4585 slots / 8.75 GiB
- F3r: experts in VRAM at start: 4585 slots / 8.75 GiB
- L1a: experts in VRAM at start: 4585 slots / 8.75 GiB
- L1e: experts in VRAM at start: 4585 slots / 8.75 GiB
- L1n: experts in VRAM at start: 4585 slots / 8.75 GiB
- L1r: experts in VRAM at start: 4585 slots / 8.75 GiB
- L2a: experts in VRAM at start: 4585 slots / 8.75 GiB
- L2e: experts in VRAM at start: 4585 slots / 8.75 GiB
- L2n: experts in VRAM at start: 4585 slots / 8.75 GiB
- L2r: experts in VRAM at start: 4585 slots / 8.75 GiB
- L3a: experts in VRAM at start: 4585 slots / 8.75 GiB
- L3e: experts in VRAM at start: 4585 slots / 8.75 GiB
- L3n: experts in VRAM at start: 4585 slots / 8.75 GiB
- L3r: experts in VRAM at start: 4585 slots / 8.75 GiB
- P1a: experts in VRAM at start: 4585 slots / 8.75 GiB
- P1e: experts in VRAM at start: 4585 slots / 8.75 GiB
- P1n: experts in VRAM at start: 4585 slots / 8.75 GiB
- P1r: experts in VRAM at start: 4585 slots / 8.75 GiB
- P2a: experts in VRAM at start: 4585 slots / 8.75 GiB
- P2e: experts in VRAM at start: 4585 slots / 8.75 GiB
- P2n: experts in VRAM at start: 4585 slots / 8.75 GiB
- P2r: experts in VRAM at start: 4585 slots / 8.75 GiB
- P3a: experts in VRAM at start: 4585 slots / 8.75 GiB
- P3e: experts in VRAM at start: 4585 slots / 8.75 GiB
- P3n: experts in VRAM at start: 4585 slots / 8.75 GiB
- P3r: experts in VRAM at start: 4585 slots / 8.75 GiB
- R2a: experts in VRAM at start: 4585 slots / 8.75 GiB
- R2e: experts in VRAM at start: 4585 slots / 8.75 GiB
- R2n: experts in VRAM at start: 4585 slots / 8.75 GiB
- R2r: experts in VRAM at start: 4585 slots / 8.75 GiB
