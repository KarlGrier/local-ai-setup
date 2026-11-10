# Round 21 summary: the 10-16 morning queue → C\*18t on 8080, your sampling everywhere, NVFP4 vs IQ3_S, reasoning effort

2026-10-16 06:50 → 10-17 13:30. Desktop on the iGPU for every run. Details: REPORT.md "Round 21", NOTES.md
(2026-10-16 / 10-17 entries); raw results in results/r21/.

## What is on 8080

**C\*18t** = C\*18 + the think-tag fix (one server commit), same engine and settings (`configs/Cstar18t.json`). Since
10-16 21:53 the config's fallback and OpenCode both use your sampling: T 1.0, top-p 0.95, top-k 20, min-p 0.05.
Rollback: stop 8080, `STRATA_CONFIG=configs/Cstar18.json ./switch-model.sh strata`.

## Queue items

| item | result |
|---|---|
| 1 health | display on the iGPU; only Xorg (4 MiB) on each NVIDIA card; RAM 91.96 GiB, 88.1 available idle; kernel clean |
| 2 reserve | the desktop's ~0.2 GiB went to the expert cache by itself (4,463 → 4,586 slots). Reserve 512: decode −5.0 / −1.9 %, 5080 under the 300 MiB floor → **kept at 713** |
| 3 guard | warn60: warns at once, stops Strata after 60 s under the floor; follows restarts. No warning since |
| 4 think fix | 7 lost calls recovered, 0 other changes in 503 turns; bug-fix task 4/4 green → **C\*18t promoted** |
| 5 issue | posted: Niko1221/Strata#2794 |
| 6 small items | Jan shell tool off; tmp/usability deleted; no /usr/bin/rg |
| 7 FP4-Local | exact conversion; not better than GPTQ (see below); Q5 deleted, Q8_0 kept |

## NVFP4 vs IQ3_S (A B B A, T 1.0)

| | C\*18t IQ3_S | GPTQ NVFP4 |
|---|---|---|
| decode | 143-144 tok/s | 100 tok/s (−30 %) |
| TTFT 32K / 64K / 120K | 7.7 / 15.4 / 29.8 s | 9.3 / 17.1 / 31.6 s |
| yardstick top-1 vs Q8_0 | 87.4 % | 91.7 % (FP4-Local 91.2; UD-Q4_K_XL 92.4) |
| suite quick | 90.7 | 86.8 (FP4-Local 91.0; all within noise) |

**IQ3_S stays the daily model.**

## Reasoning effort (C\*18t, 3 samples each)

| | xhigh (default; "high" = xhigh) | medium |
|---|---|---|
| honesty h03 / h05 / h07 / h12 | 4 of 12 UNKNOWN | **12 of 12** |
| c14 (hidden tests) | 2 of 3 | **3 of 3** |
| reasoning per honesty answer | 13-52K tokens | 0.2-1K tokens |
| time for 15 answers | 53 min | 3 min |

The hosted Flash run also ran at xhigh (OpenRouter doesn't pass the effort on; the model's default is xhigh). Five
items only: a suite run at medium would show what it costs elsewhere. Nothing changed.

## Harness at T 1.0 (OpenCode vs dsh Minimal)

The real bug-fix task, 2 runs each at T 1.0 and xhigh:

| | OpenCode | dsh Minimal |
|---|---|---|
| green | 2/2 | 2/2 |
| steps (r5 / r6) | 114 / 59 | 49 / 89 |
| model time, both runs | 607 s | 599 s |
| refused requests (context full) | 1 (r5) | 1 (r6) |

No lost calls, bad arguments or early ends. OpenCode stays the daily pick.

## The whole suite at medium and low (10-17)

"High" was dropped (it is xhigh in Strata). Suite quick, your sampling; long context at medium = 2 runs pooled.

| | IQ3_S xhigh | IQ3_S medium | IQ3_S low | NVFP4 xhigh | NVFP4 medium |
|---|---|---|---|---|---|
| total | 90.7 | **94.5** | 91.4 | 86.8 | **94.3** |
| coding | 88.2 | 98.8 | 99.3 | 77.1 | 96.0 |
| math | 100 | 95.0 | 90.0 | 100 | 95.0 |
| long context | 83.3 | 75.0 | 63.3 | 63.3 | 71.7 |
| honesty | 73.3 | 96.7 | 100 | 73.3 | 96.7 |
| research | 85.7 | 95.2 | 78.6 | 85.7 | 95.2 |
| wall time | 2.93 h | 0.82 h | 0.77 h | 4.61 h | 0.99 h |
| answers cut off | 3 | 0 | 0 | 7 | 0 |

Agentic, tool calls and instruction following: 95-100 everywhere. Only honesty is a significant gain (p = 0.016).
Low is below medium in math, research and long context → **medium is now the default on every path** (8080's
fallback, OpenCode, Codex, dsh, Jan). xhigh on request still gets xhigh (checked). Switch the chat page's own Thinking
level in its drawer. Hosted Flash ignores the effort, so no hosted medium run ($0.04 probe).

The Q8_0 honesty run was dropped (your call: the effort test answered it).

## Your decisions (all settled 10-17)

1. Reasoning effort: done, medium everywhere. Only the chat page's drawer setting is yours to switch.
2. Xorg config: skipped (your call).
3. `fit_max_tokens`: stays off (your call); both harnesses had one request refused on the long task.
4. Disk: Q8_0 shards (175 GiB) and both FP4-Local packs (66 GiB) deleted → **412 GiB free** (was 172).
