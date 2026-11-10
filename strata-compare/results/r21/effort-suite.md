Suite quick, your sampling (T 1.0 / 0.95 / 20 / min-p 0.05, sent by the suite); effort through --extra-body.
IQ3_S = C*18t (10-17) / C*18 (10-15 xhigh); NVFP4 = the GPTQ pack, configs/r20-nv18.json (10-16 xhigh, 10-17 medium).

**Score % (8 scored categories; total = their mean, 95 % interval)**

| category | IQ3_S xhigh (10-15) | IQ3_S medium | IQ3_S low | NVFP4 xhigh (10-16) | NVFP4 medium |
|---|---|---|---|---|---|
| Coding | 88.2 | 98.8 | 99.3 | 77.1 | 96.0 |
| Agentic | 100.0 | 100.0 | 100.0 | 100.0 | 100.0 |
| Math | 100.0 | 95.0 | 90.0 | 100.0 | 95.0 |
| Instruction following | 95.0 | 95.0 | 100.0 | 95.0 | 100.0 |
| Tool calls | 100.0 | 100.0 | 100.0 | 100.0 | 100.0 |
| Long context | 83.3 | 83.3 | 63.3 | 63.3 | 63.3 |
| Honesty | 73.3 | 96.7 | 100.0 | 73.3 | 96.7 |
| Research | 85.7 | 95.2 | 78.6 | 85.7 | 95.2 |
| Freshness (not scored) | not scored | not scored | not scored | not scored | not scored |
| Visual (not scored) | not scored | not scored | not scored | not scored | not scored |
| **all** | **90.7** [84.8-95.6] | **95.5** [90.7-99.1] | **91.4** [85.3-96.9] | **86.8** [80.2-92.7] | **93.3** [88.2-97.9] |

**Wall time**

| category | IQ3_S xhigh (10-15) | IQ3_S medium | IQ3_S low | NVFP4 xhigh (10-16) | NVFP4 medium |
|---|---|---|---|---|---|
| Coding | 73 min | 9 min | 16 min | 108 min | 15 min |
| Agentic | 2 min | 1 min | 1 min | 3 min | 2 min |
| Math | 22 min | 16 min | 13 min | 41 min | 21 min |
| Instruction following | 1 min | 1 min | 1 min | 2 min | 2 min |
| Tool calls | 0 min | 0 min | 0 min | 0 min | 0 min |
| Long context | 11 min | 6 min | 5 min | 16 min | 5 min |
| Honesty | 29 min | 1 min | 1 min | 43 min | 1 min |
| Research | 4 min | 3 min | 3 min | 5 min | 5 min |
| Freshness (not scored) | 1 min | 0 min | 0 min | 2 min | 0 min |
| Visual (not scored) | 32 min | 11 min | 6 min | 58 min | 8 min |
| **all** | 2.93 h | 0.82 h | 0.77 h | 4.61 h | 0.99 h |

**Median reasoning tokens per answer**

| category | IQ3_S xhigh (10-15) | IQ3_S medium | IQ3_S low | NVFP4 xhigh (10-16) | NVFP4 medium |
|---|---|---|---|---|---|
| Coding | 12,437 | 1,659 | 1,398 | 15,042 | 1,771 |
| Agentic | 4,170 | 2,364 | 1,610 | 4,000 | 2,150 |
| Math | 2,484 | 2,262 | 1,968 | 2,104 | 2,214 |
| Instruction following | 244 | 360 | 300 | 296 | 378 |
| Tool calls | 76 | 56 | 86 | 76 | 61 |
| Long context | 20,266 | 9,042 | 4,778 | 17,088 | 3,868 |
| Honesty | 8,038 | 262 | 241 | 3,478 | 303 |
| Research | 2,207 | 1,515 | 970 | 2,736 | 1,192 |
| Freshness (not scored) | 6,013 | 211 | 70 | 11,355 | 52 |
| Visual (not scored) | 30,491 | 2,330 | 1,326 | 35,748 | 2,945 |
| **all** | 2,346 | 934 | 783 | 2,168 | 934 |

**Answers cut off (token limit = max_tokens 81,920; loop stop = one token repeated 256 times)**

| category | IQ3_S xhigh (10-15) | IQ3_S medium | IQ3_S low | NVFP4 xhigh (10-16) | NVFP4 medium |
|---|---|---|---|---|---|
| Coding | 1 token limit / 1 loop stop | 0 | 0 | 2 token limit / 4 loop stop | 0 |
| Agentic | 0 | 0 | 0 | 0 | 0 |
| Math | 0 | 0 | 0 | 0 | 0 |
| Instruction following | 0 | 0 | 0 | 0 | 0 |
| Tool calls | 0 | 0 | 0 | 0 | 0 |
| Long context | 1 token limit | 0 | 0 | 1 token limit | 0 |
| Honesty | 0 | 0 | 0 | 0 | 0 |
| Research | 0 | 0 | 0 | 0 | 0 |
| Freshness (not scored) | 0 | 0 | 0 | 0 | 0 |
| Visual (not scored) | 0 | 0 | 0 | 0 | 0 |
| **all** | 2 token limit / 1 loop stop | 0 | 0 | 3 token limit / 4 loop stop | 0 |

**Against the same model's xhigh run** (paired by item: difference in points, 95 % interval; verdict)

| category | IQ3_S medium vs xhigh | IQ3_S low vs xhigh | NVFP4 medium vs xhigh | NVFP4 medium vs IQ3_S medium |
|---|---|---|---|---|
| Coding | +10.6 (1.1 to 22.0; within noise) | +11.1 (1.1 to 23.1; within noise) | +18.9 (4.0 to 34.9; within noise) | -2.8 (-10.0 to 1.7; within noise) |
| Agentic | +0.0 (0.0 to 0.0; within noise) | +0.0 (0.0 to 0.0; within noise) | +0.0 (0.0 to 0.0; within noise) | +0.0 (0.0 to 0.0; within noise) |
| Math | -5.0 (-15.0 to 0.0; within noise) | -10.0 (-25.0 to 0.0; within noise) | -5.0 (-15.0 to 0.0; within noise) | +0.0 (0.0 to 0.0; within noise) |
| Instruction following | +0.0 (-15.0 to 15.0; within noise) | +5.0 (0.0 to 15.0; within noise) | +5.0 (0.0 to 15.0; within noise) | +5.0 (0.0 to 15.0; within noise) |
| Tool calls | +0.0 (0.0 to 0.0; within noise) | +0.0 (0.0 to 0.0; within noise) | +0.0 (0.0 to 0.0; within noise) | +0.0 (0.0 to 0.0; within noise) |
| Long context | +0.0 (-50.0 to 50.0; within noise) | -20.0 (-70.0 to 33.3; within noise) | +0.0 (0.0 to 0.0; within noise) | -20.0 (-53.3 to 0.0; within noise) |
| Honesty | +23.3 (10.0 to 36.7; B higher) | +26.7 (13.3 to 40.0; B higher) | +23.3 (10.0 to 36.7; B higher) | +0.0 (0.0 to 0.0; within noise) |
| Research | +9.5 (0.0 to 28.6; within noise) | -7.1 (-21.4 to 0.0; within noise) | +9.5 (0.0 to 28.6; within noise) | +0.0 (0.0 to 0.0; within noise) |

**Category reruns (IQ3_S and NVFP4 at medium differed by more than one item): run 1 + rerun, solved items**

| category | IQ3_S medium run 1 | rerun | NVFP4 medium run 1 | rerun |
|---|---|---|---|---|
| longctx | 5.0 / 6 (83.3 %) | 4.0 / 6 (66.7 %) | 3.8 / 6 (63.3 %) | 4.8 / 6 (80.0 %) |
