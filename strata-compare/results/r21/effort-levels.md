C\*18t (IQ3_S), suite quick, your sampling; effort through --extra-body. xhigh = Friday's c18-iq3s-quick (C\*18, same engine and weights).
Medium's long context = run 1 + the rerun (c18t-quick-medium-rr), pooled: 12 answers.

**Score %** (scored as the suite does: honesty items weighted; solved / answers in brackets)

| category | xhigh (10-15) | medium | low |
|---|---|---|---|
| Coding | 88.2 (22.0 / 25) | 98.8 (24.7 / 25) | 99.3 (24.8 / 25) |
| Agentic | 100.0 (3.0 / 3) | 100.0 (3.0 / 3) | 100.0 (3.0 / 3) |
| Math | 100.0 (20.0 / 20) | 95.0 (19.0 / 20) | 90.0 (18.0 / 20) |
| Instruction following | 95.0 (19.0 / 20) | 95.0 (19.0 / 20) | 100.0 (20.0 / 20) |
| Tool calls | 100.0 (10.0 / 10) | 100.0 (10.0 / 10) | 100.0 (10.0 / 10) |
| Long context | 83.3 (5.0 / 6) | 75.0 (9.0 / 12) | 63.3 (3.8 / 6) |
| Honesty | 73.3 (12.0 / 20) | 96.7 (19.0 / 20) | 100.0 (20.0 / 20) |
| Research | 85.7 (6.0 / 7) | 95.2 (6.7 / 7) | 78.6 (5.5 / 7) |
| **total** (mean of the 8) | **90.7** | **94.5** | **91.4** |

**Wall time (run 1 only), median reasoning tokens per answer, answers cut off**

| category | xhigh (10-15) wall | xhigh (10-15) reasoning | xhigh (10-15) cut | medium wall | medium reasoning | medium cut | low wall | low reasoning | low cut |
|---|---|---|---|---|---|---|---|---|---|
| Coding | 73 min | 12,437 | 1 token limit / 1 loop stop | 9 min | 1,659 | 0 | 16 min | 1,398 | 0 |
| Agentic | 2 min | 4,170 | 0 | 1 min | 2,364 | 0 | 1 min | 1,610 | 0 |
| Math | 22 min | 2,484 | 0 | 16 min | 2,262 | 0 | 13 min | 1,968 | 0 |
| Instruction following | 1 min | 244 | 0 | 1 min | 360 | 0 | 1 min | 300 | 0 |
| Tool calls | 0 min | 76 | 0 | 0 min | 56 | 0 | 0 min | 86 | 0 |
| Long context | 11 min | 20,266 | 1 token limit | 6 min | 6,650 | 0 | 5 min | 4,778 | 0 |
| Honesty | 29 min | 8,038 | 0 | 1 min | 262 | 0 | 1 min | 241 | 0 |
| Research | 4 min | 2,207 | 0 | 3 min | 1,515 | 0 | 3 min | 970 | 0 |
| Freshness (not scored) | 1 min | 6,013 | 0 | 0 min | 211 | 0 | 0 min | 70 | 0 |
| Visual (not scored) | 32 min | 30,491 | 0 | 11 min | 2,330 | 0 | 6 min | 1,326 | 0 |
| **all** | 2.93 h | 2,346 | 2 token limit / 1 loop stop | 0.82 h | 934 | 0 | 0.77 h | 783 | 0 |

**Paired by item** (difference in points, 95 % interval; verdict from `run.sh compare`)

| category | low vs xhigh | low vs medium (run 1) | medium vs xhigh |
|---|---|---|---|
| Coding | +11.1 (1.1 to 23.1; within noise) | +0.6 (0.0 to 1.7; within noise) | +10.6 (1.1 to 22.0; within noise) |
| Agentic | +0.0 (0.0 to 0.0; within noise) | +0.0 (0.0 to 0.0; within noise) | +0.0 (0.0 to 0.0; within noise) |
| Math | -10.0 (-25.0 to 0.0; within noise) | -5.0 (-15.0 to 0.0; within noise) | -5.0 (-15.0 to 0.0; within noise) |
| Instruction following | +5.0 (0.0 to 15.0; within noise) | +5.0 (0.0 to 15.0; within noise) | +0.0 (-15.0 to 15.0; within noise) |
| Tool calls | +0.0 (0.0 to 0.0; within noise) | +0.0 (0.0 to 0.0; within noise) | +0.0 (0.0 to 0.0; within noise) |
| Long context | -20.0 (-70.0 to 33.3; within noise) | -20.0 (-53.3 to 0.0; within noise) | +0.0 (-50.0 to 50.0; within noise) |
| Honesty | +26.7 (13.3 to 40.0; B higher) | +3.3 (0.0 to 10.0; within noise) | +23.3 (10.0 to 36.7; B higher) |
| Research | -7.1 (-21.4 to 0.0; within noise) | -16.7 (-38.1 to 0.0; within noise) | +9.5 (0.0 to 28.6; within noise) |

**Your rule** (low if it scores at least as well as medium in every category): low is below medium in Math 90.0 < 95.0; Long context 63.3 < 75.0; Research 78.6 < 95.2 -> **medium**

DEFAULT: medium
