A1R: 69 requests, 30 LDR topics -> fit 15, held-out 15
table: 1633008 fit layer-rows; held-out windows 52706

## recall at <= 2x the true bytes (all tokens of the window)
| layer | true CPU experts / window | recall (count) | predicted / true bytes |
|---|---|---|---|
| 0 | 5.88 | 72.2 % | 2.00 |
| 1 | 4.17 | 50.3 % | 2.00 |
| 2 | 4.90 | 54.7 % | 2.00 |
| 3 | 4.11 | 37.2 % | 2.00 |
| 4 | 3.54 | 42.3 % | 2.00 |
| 5 | 3.74 | 44.5 % | 2.00 |
| 6 | 3.92 | 46.9 % | 2.00 |
| 7 | 4.49 | 51.3 % | 2.00 |
| 8 | 4.07 | 32.4 % | 2.00 |
| 9 | 3.35 | 28.6 % | 2.00 |
| 10 | 4.63 | 33.4 % | 2.00 |
| 11 | 3.22 | 28.7 % | 2.00 |

## recall at <= 2x the true bytes (token 0 only)
| layer | true CPU experts / window | recall (count) | predicted / true bytes |
|---|---|---|---|
| 0 | 5.88 | 40.1 % | 2.00 |
| 1 | 4.17 | 33.5 % | 2.00 |
| 2 | 4.90 | 36.3 % | 2.00 |
| 3 | 4.11 | 26.9 % | 2.00 |
| 4 | 3.54 | 30.1 % | 2.00 |
| 5 | 3.74 | 32.5 % | 2.00 |
| 6 | 3.92 | 33.6 % | 2.00 |
| 7 | 4.49 | 36.3 % | 2.00 |
| 8 | 4.07 | 25.5 % | 2.00 |
| 9 | 3.35 | 22.5 % | 2.00 |
| 10 | 4.63 | 26.5 % | 2.00 |
| 11 | 3.22 | 22.9 % | 2.00 |

held-out windows: 52706; true CPU-side experts in layers 0-11 per window: 50.03 (94.8 MB)
