# Round 20 summary: v0.1.44.1 → C\*18 (on 8080), the NVFP4 trial (stopped at the 20 GiB floor), the suite and concurrency on C\*18

2026-10-15 09:06 → 18:47 (no tag newer than v0.1.44.1 by 09:00). Monitor on the 5080, asleep, the same for every speed
arm. Details: REPORT.md "Round 20", NOTES.md (2026-10-15 entries); raw results in results/r20/.

## What is on 8080

**C\*18 since 15:04** = Strata v0.1.44.1 + C\*17.1's 29 commits, C\*17.1's settings (`configs/Cstar18.json`).

| vs C\*17.1 | result |
|---|---|
| outputs | identical (exact7 7/7 at two cache sizes; repeats 7/7) |
| decode, A B B A | LDR −0.5 %, decode screen +0.9 %, full screen −0.9 % (full screen total time +1.5 %) |
| prompt reads | equal (32K 7.8 s, 64K 15.5 s, 120K 30.0 s) |
| gates / acceptance / soak | all pass / 11 of 11 / 440 requests, 0 errors, MemAvailable ≥ 23.1 GB |
| r04 (literal tool tags) | fixed: 6/6 (C\*17.1 1/6) |

Rollback: stop 8080, `STRATA_CONFIG=configs/Cstar171.json ./switch-model.sh strata`. Your launchers work as before.
New defaults: only `STRATA_COMMIT_BATCH` could change outputs here, and it is bitwise → kept. `STRATA_HC_Q8` off; tail
skip 0 in every one-GPU config. #2028 and #1896 have not landed. Nothing posted.

## NVFP4

Loads, 5/5 sanity, accuracy on human text = IQ3_S. With every expert in RAM it idles at 20.0 GiB free; the first speed
server fell to **19.7 GiB** → stopped per your rule. No speed or suite numbers.

## Suite quick on C\*18 IQ3_S: 90.7 %

C\*17.1 quick 86.0, C\*17.1 full 89.1, hosted Flash 93.4; every category within noise of C\*17.1. Coding 88.2 (Flash 98.0;
one answer cut by the repeat guard, '0' x 256), honesty 73.3 (declines 7 of 15 unknowables; Flash ~11 of 15).

## Concurrency (one request at a time; others queue)

| N at once | decode total tok/s C\*17.1 / C\*18 | agent set (27.7K prompts) wall C\*17.1 / C\*18 |
|---|---|---|
| 1 | 159.2 / 158.2 | 7.1 / 7.8 s |
| 2 | 146.4 / 146.6 | 14.8 / 14.6 s |
| 4 | 143.2 / 139.7 | 33.3 / 34.8 s |
| 8 | 137.2 / 137.5 | 61.2 / 73.1 s (answer length; prompt reads identical) |

## Recommendation

Daily model: **IQ3_S on C\*18**. Agents: **one at a time, two at most** (more only adds waiting).
