| config | prompt | gen tokens | finish | decode tok/s (whole) | first→last window tok/s | answer chars | tail repeats 32-gram / 8-gram | tail zlib ratio | loop? |
|---|---|---|---|---|---|---|---|---|---|
| A | code | 32768 | length | 31.35 | 33.64 → 29.36 | 0 | 0.005 / 0.026 | 0.363 | no |
| A | math | 32768 | length | 31.4 | 33.93 → 29.25 | 3657 | 0.0 / 0.075 | 0.412 | no |
| A | puzzle | 23929 | stop | 31.81 | 33.44 → 30.31 | 6741 | 0.0 / 0.038 | 0.328 | no |
| A | 01_security_incident | 30202 | stop | 31.32 | – | 27251 | 0.0 / 0.049 | 0.401 | no |
| A | 02_network_troubleshooting | 25891 | stop | 31.72 | – | 11677 | 0.067 / 0.276 | 0.365 | no |
| A | 03_ccna_tutor | 10434 | stop | 33.0 | – | 9504 | 0.022 / 0.247 | 0.35 | no |
| A | 04_local_ai_performance | 32768 | length | 31.15 | – | 12793 | 0.014 / 0.142 | 0.409 | no |
| A | 05_patch_policy_constraints | 8202 | stop | 32.96 | – | 4194 | 0.069 / 0.159 | 0.407 | no |
| B | code | 32768 | length | 33.11 | 35.87 → 31.26 | 0 | 0.0 / 0.047 | 0.316 | no |
| B | math | 32768 | length | 32.98 | 35.58 → 30.94 | 0 | 0.0 / 0.008 | 0.47 | no |
| B | puzzle | 26110 | stop | 33.7 | 36.08 → 32.04 | 2875 | 0.003 / 0.125 | 0.355 | no |
| C0 | code | 32768 | length | 44.34 | 47.7 → 42.37 | 0 | 0.005 / 0.068 | 0.307 | no |
| C0 | math | 32768 | length | 56.0 | 58.91 → 50.77 | 0 | 0.0 / 0.042 | 0.488 | no |
| C0 | puzzle | 26929 | stop | 43.92 | 46.2 → 41.56 | 3250 | 0.001 / 0.083 | 0.363 | no |
| C0 | 01_security_incident | 26516 | stop | 48.66 | – | 22643 | 0.0 / 0.061 | 0.393 | no |
| C0 | 02_network_troubleshooting | 32768 | length | 50.77 | – | 0 | 0.008 / 0.367 | 0.186 | LOOP |
| C0 | 03_ccna_tutor | 15943 | stop | 50.22 | – | 10810 | 0.018 / 0.245 | 0.357 | no |
| C0 | 04_local_ai_performance | 22997 | stop | 50.81 | – | 20007 | 0.0 / 0.031 | 0.394 | no |
| C0 | 05_patch_policy_constraints | 16580 | stop | 51.08 | – | 8529 | 0.075 / 0.221 | 0.381 | no |
