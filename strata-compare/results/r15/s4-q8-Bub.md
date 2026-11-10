# Round 15 step 4 — file-tier options, q8-Bub (each alone, A B B A, greedy math 1,024 tokens, cold page cache)

| option | arm | decode tok/s | ms / round | file MB / round | file ms / round | fetch wait ms / round | pool ms / round | not in the page cache | min MemAvailable GiB | swap GiB |
|---|---|---|---|---|---|---|---|---|---|---|
| budget56:-:--resident-budget-gib=56 | base-a | 16.1 | 161.9 | 667.6 | 101.1 | 0.0 | 140.3 | 0.00 | 18.2 | 1.89 |
| budget56:-:--resident-budget-gib=56 | opt-a | 13.1 | 199.7 | 919.8 | 138.9 | 0.0 | 176.8 | 0.00 | 26.0 | 1.88 |
| budget56:-:--resident-budget-gib=56 | opt-b | 13.1 | 200.6 | 920.2 | 138.5 | 0.0 | 177.2 | 0.00 | 25.6 | 1.88 |
| budget56:-:--resident-budget-gib=56 | base-b | 15.3 | 168.8 | 669.0 | 106.6 | 0.0 | 145.2 | 0.00 | 18.3 | 1.88 |
| budget74:-:--resident-budget-gib=74 | base-a | 15.8 | 163.8 | 663.5 | 102.1 | 0.0 | 140.9 | 0.00 | 17.8 | 1.87 |
| budget74:-:--resident-budget-gib=74 | opt-a | 20.2 | 133.7 | 458.8 | 73.9 | 0.0 | 112.9 | 0.00 | 7.9 | 3.00 |
| budget74:-:--resident-budget-gib=74 | opt-b | 19.5 | 134.9 | 480.6 | 74.0 | 0.0 | 114.2 | 0.00 | 8.1 | 1.89 |
| budget74:-:--resident-budget-gib=74 | base-b | 15.3 | 167.0 | 644.1 | 103.0 | 0.0 | 143.6 | 0.00 | 18.3 | 1.88 |

| option | base tok/s | option tok/s | change | base arms' spread | >= +3 % |
|---|---|---|---|---|---|
| budget56:-:--resident-budget-gib=56 | 15.67 | 13.09 | **-16.5 %** | 5.1 % | no |
| budget74:-:--resident-budget-gib=74 | 15.57 | 19.85 | **+27.5 %** | 3.1 % | KEEP |
