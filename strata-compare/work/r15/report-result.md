### Result

Two stand-ins for a much bigger Qwen4 Flash, measured on this PC with your config, your sampling and your 6 GiB floor
(the chat cache at 2 GiB), on v0.1.40.2 + our 27 patches. **Q8_0** of Flash-Next has 119.5 GiB of routed experts — about
what a 300B model has at IQ3_S. **The splice** (UD-Q5_K_XL's 91.6 GiB of experts with IQ3_S's other tensors; UD-Q5_K_XL
itself does not load) is about a 300B model at IQ3_XXS. Today's Flash-Next on IQ3_S (C\*14) for scale: ~140 tok/s,
120K prompt in 30 s.

**Q8_0 stand-in (119.5 GiB of experts)** — served; full sets at 71 GiB, the largest RAM budget that held your floor over a
full run; direct (unbuffered) reads

| placement | decode tok/s (decode screen / LDR) | TTFT 8K / 32K / 64K / 120K (s) | where a decode round goes (CLI, warm) | what failed |
|---|---|---|---|---|
| **D** 5080 + 4060 Ti as peer tier + 71 GiB RAM | **18.1 / 14.0** (64K context: +6–9 %) | 6.5 / 19.4 / 31.3 / 50.4 | ~140 ms = GPU ~22 + CPU on RAM experts ~37 + **reading the SSD ~82–85** (0.4–0.7 GiB a round; the drive streamed 3.7 GB/s for an hour, 58 °C) | one 64K prompt read hung at 73 GiB (watchdog restart); 74 / 73 / 72 GiB broke your floor in full runs |
| B 5080 + 71 GiB RAM | 15.9 / 12.1 | 6.5 / 19.3 / 31.3 / 50.7 | 127 ms = GPU 20 + RAM 38 + SSD 68 | – |
| C layer split | probe 21.1 (74 GiB) | 32K: 228 s | – | auto split did not start; needed 1,613 MiB reserve; 1,024-token prompt chunks |
| A both GPUs + page cache | probe 12.3 (with read-ahead) | – | – | slowest once the budgets read directly |
| E --resident-experts | – | – | – | sizes its own RAM copy past your floor; no flag to size it |

Needle at 120K: 6/6 on D and B.

**The splice (91.6 GiB of experts)** — served; full sets at 72 GiB

| placement | decode tok/s (decode screen / LDR) | TTFT 8K / 32K / 64K / 120K (s) | where the time goes | what failed |
|---|---|---|---|---|
| **C** layer split (layers 0–46 on the 5080, 47 + head on the 4060 Ti) + 72 GiB | 45.2 / 41.4; **saved config (--adapt-swaps 48, --pcie-frac 0.2, 64K cap): 50.7 / 43.1** | 16.5 / 63.8 / 127.0 / 237.1 (saved config: ~20 % faster, chunk 1,280) | decode window 47 ms = GPU reach 8 + CPU experts 20 + other host 7 + draft 3; **prompt: the 8 GB 4060 Ti caps the chunk at 1,024 tokens, so every chunk re-reads the experts outside RAM — 1.28 TB from the SSD for a 120K prompt; uploads are half the read** | one session answered degenerately from a 120K prompt on (not reproduced in 8 fresh sessions) → 64K cap as a precaution |
| B 5080 + 72 GiB | 40.1 / 33.3 | **5.1 / 12.4 / 20.6 / 39.4** | round 56 ms = GPU 16 + RAM 25 + SSD 14.5 (80 MB) | one 0.2-s dip to 5.67 GiB → saved at 71 |
| D peer tier | probe ~51 (greedy) | 32K: 11 s | – | – |
| A | probe 24.6 (64 GiB era) | – | – | – |
| E | – | – | – | over your floor |

Needle at 120K: 6/6 on B and on C (C: 0/6 in the one failing session).

**Three lines**
1. **A 300B-class Qwen4 Flash on this PC today:** at IQ3_S size **~14 tok/s on research answers, ~18 on short ones**, a 120K
   prompt in ~50 s (placement D); at IQ3_XXS size **~43 / ~51 tok/s** with 1,024-token prompt chunks (C, 64K cap), or
   ~33 / ~40 with 5x faster prompt reads (B, 120K in 39 s).
2. **With enough RAM for every expert (an ESTIMATE from the measured time split, not a measurement):** ~32 tok/s at
   IQ3_S size (D, ~123 GiB of RAM needed), ~46 at IQ3_XXS size (B, ~101 GiB).
3. **What the runbook and the planner got wrong:** the inspector's format list was v0.1.39's and nothing checked a file
   against the engine's own reader (UD-Q5_K_XL refused); the planner assumed 10 GiB of other use and sized from probes —
   **neither its default nor my starting budget used your 6 GiB margin**, and 74 GiB passed every probe but no full run;
   it cannot size placement E, and it did not foresee C's 1,024-token chunk on the 8 GB card; v0.1.40.2's own read rule
   picked the page cache here (direct reads +15 % / +48 %).

**Step 8 — C\*15 = v0.1.40.2 + 27 patches.** Upstream's new drafting (STRATA_SPEC_PROB) lost to our exact sampling (−2.7 %;
±0.6 % under our cost gate) → C\*14's flags. **Against C\*14: LDR −2.8 %, decode −3.1 %, full −2.3 %** with identical
outputs (exact7 7/7 = C\*14's hashes). Your hour-long search (each changed default back to its old value on C\*15, one at a
time) found nothing that restores the speed: **the ~3 % is unexplained by any setting**. Gates as C\*14's, acceptance suite
11 pass / 0 fail. SOAK_RESULT **PROMOTE_RESULT** — for the fixes that reach your server: a Stop or closed tab during a
long prompt read cancels it (#1182), a refused request answers at once instead of after 300 s (#1059), a hung engine
start times out (#1317), restart fixes. Rollback: stop 8080, `STRATA_CONFIG=configs/Cstar14.json ./switch-model.sh strata`.

