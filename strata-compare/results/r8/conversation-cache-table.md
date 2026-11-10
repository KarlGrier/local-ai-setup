17:36
| run | switch: A8 after B / A9 after 64K / A10 after D / B2 / C2 / A11 (TTFT s) | switching requests B1 / C1 / D1 TTFT | many r1 back (median TTFT, reused>0 count) | many r2 back | peak RSS GB / min MemAvail GB |
|---|---|---|---|---|---|
| CC-ours6-a | 0.55 / 0.49 / 0.36 / 0.63 / 0.41 / 0.46 | 0.51 / 18.29 / 0.58 | 1.54 s, 0/8 reused | 0.25 s, 7/8 reused | 53.8 / 32.3 |
| CC-up6-a | 0.59 / 0.71 / 0.36 / 0.61 / 0.39 / 0.41 | 0.69 / 18.39 / 0.63 | 1.55 s, 0/8 reused | 0.21 s, 7/8 reused | 57.3 / 28.6 |
| CC-ours8 | 0.56 / 0.75 / 0.36 / 0.68 / 0.40 / 0.47 | 0.52 / 18.31 / 0.58 | 0.19 s, 8/8 reused | 0.21 s, 8/8 reused | 54.7 / 31.3 |
| CC-up8 | 0.57 / 0.78 / 0.36 / 0.59 / 0.40 / 0.41 | 0.67 / 18.45 / 0.64 | 0.20 s, 8/8 reused | 0.24 s, 8/8 reused | 58.4 / 27.4 |
| CC-up6-b | 0.59 / 0.62 / 0.36 / 0.57 / 0.40 / 0.41 | 0.67 / 18.39 / 0.63 | 1.54 s, 0/8 reused | 0.21 s, 7/8 reused | 57.3 / 28.5 |
| CC-ours6-b | 0.56 / 0.67 / 0.38 / 0.66 / 0.43 / 0.46 | 0.52 / 18.29 / 0.57 | 1.55 s, 0/8 reused | 0.23 s, 7/8 reused | 53.8 / 32.2 |

[exited with code 0]
