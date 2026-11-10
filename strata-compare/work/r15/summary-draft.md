# Round 15 — summary

**Status (STEP8_STATUS)**

**What a much bigger Qwen4 Flash would do on this PC — measured with two stand-in files of Flash-Next** (Q8_0: 119.5 GiB
of experts ≈ a 300B model at IQ3_S; the splice: UD-Q5_K_XL's 91.6 GiB of experts with IQ3_S's other tensors ≈ 300B at
IQ3_XXS — UD-Q5_K_XL itself does not load: its first shard is 6 bytes short of the engine's aligned data section). Your
config, your sampling, the 6 GiB floor; all served numbers on v0.1.40.2 + our 27 patches.

### Q8_0 stand-in (119.5 GiB of experts: ~40 GiB more than the PC's RAM can hold beside everything else)

| placement | decode screen tok/s | LDR tok/s | TTFT 8K / 32K / 64K / 120K (s) | needle 120K | where a decode round goes | what failed |
|---|---|---|---|---|---|---|
| **D: 5080 + 4060 Ti as peer tier + 71 GiB RAM, direct reads** | **18.1** | **14.0** | 6.5 / 19.4 / 31.3 / 50.4 | 6/6 | 140 ms = GPU 22 + RAM experts 37 + **SSD 82** (0.4–0.7 GiB per round) | 64K prompt hung once at 73 GiB (watchdog restart); 74/73/72 GiB broke your floor over a full run |
| B: 5080 + 71 GiB RAM | 15.9 | 12.1 | 6.5 / 19.3 / 31.3 / 50.7 | 6/6 | 127 ms = GPU 20 + RAM 38 + SSD 68 | – |
| A: both GPUs + page cache (no budget) | probe 15.5 (64 GiB era) | – | – | – | – | slower once budgets read directly |
| C: layer split | probe 21.1 | – | 32K: 228 s | – | – | auto split did not start; needed 1,613 MiB reserve; prompt reads 10x slower |
| E: --resident-experts | – | – | – | – | – | sizes its own copy past your floor (no flag to size it) |

Step 5 kept --max-context 65536 (+6.3 %, +9.2 % re-checked); configs/r15-q8.json (64K) and r15-q8-131k.json.

### The splice (91.6 GiB of experts)

| placement | decode screen tok/s | LDR tok/s | TTFT 8K / 32K / 64K / 120K (s) | needle 120K | where the time goes | what failed |
|---|---|---|---|---|---|---|
| **C: layer split (0–46 on the 5080, 47 + head on the 4060 Ti) + 72 GiB** | **45.2** (+14.5 % with --adapt-swaps 48) | **41.4** | 16.5 / 63.8 / 127.0 / 237.1 | 6/6 (re-run) | prompt: 1,024-token chunks (the 8 GB 4060 Ti), expert uploads 50 %, 1.28 TB from the SSD per 120K prompt | one session gave degenerate answers from a 120K prompt on; not reproduced in 8 fresh sessions |
| B: 5080 + 71–72 GiB | 40.1 | 33.3 | **5.1 / 12.4 / 20.6 / 39.4** | 6/6 | round 56 ms = GPU 16 + RAM 25 + SSD 14.5 | one 0.2-s dip to 5.67 GiB at 72 |
| D: peer tier + budget | probe ~51 | – | – | – | – | – |
| A | probe 24.6 (64 GiB era) | – | – | – | – | – |
| E | – | – | – | – | – | over your floor |

Step 5 kept --adapt-swaps 48 (+14.5 %) and --pcie-frac 0.2 (+3.5 %) on C; no split point or chunk size cut C's prompt read.
configs/r15-q5s-C.json (64K cap as a precaution) and r15-q5s-B.json.

**Three lines:**
1. **A 300B-class Qwen4 Flash today on this PC:** at IQ3_S size (≈ the Q8_0 stand-in) **~14 tok/s on research answers,
   ~18 on short ones**, 120K prompts in ~50 s; at IQ3_XXS size (≈ the splice) **~41 / 45 tok/s** (40 / 33 with B's 5x
   faster prompt reads). Today's 35B-class IQ3_S: ~140.
2. **With enough RAM (an ESTIMATE from the measured split, not a measurement):** every expert in RAM would take the
   Q8_0-size model to **~32 tok/s** served (needs ~123 GiB of RAM), the splice-size to **~46** (~101 GiB).
3. **What the runbook / planner got wrong:** it did not know the engine's own file reader (UD-Q5_K_XL refused), carried an
   old format list, sized RAM for 10 GiB of other use (not your 6 GiB margin) and from probes rather than full runs
   (74 GiB passed probes, failed every full run); v0.1.40.2's read rule chose the page cache (direct reads +15–48 %).

### Step 8 — C\*15

STEP8_TABLE
