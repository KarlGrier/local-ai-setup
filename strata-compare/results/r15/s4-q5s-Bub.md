# Round 15 step 4 — file-tier options, q5s-Bub (each alone, A B B A, greedy math 1,024 tokens, cold page cache)

| option | arm | decode tok/s | ms / round | file MB / round | file ms / round | fetch wait ms / round | pool ms / round | not in the page cache | min MemAvailable GiB | swap GiB |
|---|---|---|---|---|---|---|---|---|---|---|
| budget56:-:--resident-budget-gib=56 | base-a | 34.5 | 74.8 | 170.9 | 30.8 | 0.0 | 57.3 | 0.00 | 18.4 | 1.87 |
| budget56:-:--resident-budget-gib=56 | opt-a | 29.0 | 93.9 | 300.1 | 50.2 | 0.0 | 75.4 | 0.00 | 26.7 | 1.87 |
| budget56:-:--resident-budget-gib=56 | opt-b | 29.0 | 93.9 | 301.5 | 50.5 | 0.0 | 75.6 | 0.00 | 26.5 | 1.87 |
| budget56:-:--resident-budget-gib=56 | base-b | 36.2 | 74.1 | 171.8 | 31.2 | 0.0 | 56.5 | 0.00 | 18.6 | 1.87 |
| budget74:-:--resident-budget-gib=74 | base-a | 36.8 | 72.9 | 167.1 | 30.0 | 0.0 | 55.5 | 0.00 | 18.3 | 1.87 |
| budget74:-:--resident-budget-gib=74 | opt-a | 49.4 | 50.2 | 56.2 | 10.5 | 0.0 | 33.9 | 0.00 | 9.0 | 1.87 |
| budget74:-:--resident-budget-gib=74 | opt-b | 48.6 | 57.4 | 68.3 | 13.2 | 0.0 | 40.1 | 0.00 | 9.0 | 1.87 |
| budget74:-:--resident-budget-gib=74 | base-b | 36.8 | 70.3 | 166.4 | 28.7 | 0.0 | 53.6 | 0.00 | 18.4 | 1.87 |

| option | base tok/s | option tok/s | change | base arms' spread | >= +3 % |
|---|---|---|---|---|---|
| budget56:-:--resident-budget-gib=56 | 35.33 | 28.98 | **-18.0 %** | 4.9 % | no |
| budget74:-:--resident-budget-gib=74 | 36.80 | 49.00 | **+33.2 %** | 0.2 % | KEEP |
