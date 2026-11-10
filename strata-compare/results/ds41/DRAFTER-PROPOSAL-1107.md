# DeepSeek C: the drafter, its acceptance, and a 1017-matched small drafter (proposal; desk only, 11-07)

Karl 11-07: "Make sure the drafter proposal covers my 11-04 idea: take the drafter made for 1017 (the DFlash one) and
quantize it to fit the 4060 Ti. Estimate its size at each quant and its likely acceptance vs the current one, and say what
it would mean for the best draft count." (The idea is in NOTES.md:9580, dated 11-03: "our 1017 DSpark Q8_0 requantized to
~Q4_K (fits the 4060 Ti; drafter-only rounding, output stays exact). Do not build it without Karl's OK.")
**Nothing was built, quantized, downloaded or run.** Headers were read with
`work/ds41/gate/scratch-drafter/gguf_table.py` (header only). Estimates come from `work/ds41/gate/scratch-drafter/draft_model.py`.

## 1. What C ran

- **Drafter:** `Lucebox/DeepSeek-V4.1-Flash-DSpark-GGUF` @11403d34 (MIT), `DeepSeek-V4.1-Flash-DSpark-draft-Q2K-Q4K.gguf`,
  4,923,041,440 B, sha256 5efffdb5ab47...
  - Architecture `deepseek41-dflash-draft`.
  - Per its model card, this is "the draft block DeepSeek ships inside the checkpoint (the `mtp.*` tensors: three stages,
    128 routed experts top-3, a block of five tokens)", converted from **the original `deepseek-ai/DeepSeek-V4.1-Flash`
    checkpoint, not the 1017 revision we run**.
  - Shape: 3 layers, 128 experts each (hidden 5120, n_ff 2304), 14.23 B parameters.
  - Quantization: routed experts Q2_K, dense projections Q4_K, the DSpark Markov head F16.
  - Lucebox built this Q2K-Q4K file for a 192 GB box where the drafter shares a GPU with hot experts. The card says it
    "drafts faster, with about the same acceptance" as Lucebox's own MXFP4-Q8 build of the same drafter.
- **Our conversion:** `work/ds41/gate/convert_lucebox_dspark.py` (11-03). It renames the tensors to unsloth's `dflash`
  layout, widens the confidence head F16 to F32, and converts the Markov embed F16 to BF16 (the only rounding). Metadata
  comes from the 1017 Q8_0. The result is packed into `models/DeepSeek-V4.1-Flash-1017-GSQ-RCO-GGUF/pack-ist-das-2.00bpw-lucebox-q2k`.
- **Placement (C0/C1/C2 start lines):**
  - The 4060 Ti holds only the drafter (layers 40-42): weights 0.34 GB, experts 4.47 GB, all 384 of 384 in VRAM, with
    1144 MiB free.
  - The trunk is on the 5080 (layers 0-39 + head, 693 experts in VRAM) and on the CPU lane (14,667 experts).
  - Settings: `--dspark-conf 0.65`, `--dspark-block` 1 (C1) or 2 (C2).

## 2. C1's and C2's acceptance (from the engines' per-request "drafts ... per position (kept / reached)" lines)

Scope: W1-W3 over 3 passes, the requests the decode numbers come from. "All requests" is in brackets.

| arm | verify rounds | drafts offered a round | position 1 kept / reached | position 2 kept / reached | all drafts kept / offered | tokens a verify round | decode tok/s (vs C0 27.96) |
|---|---|---|---|---|---|---|---|
| C1 (1 draft) | 10,466 | 1.00 | 8,728 / 10,466 = **83.4 %** [83.4] | - | 83.4 % | **1.83** | 29.00 (+3.7 %) |
| C2 (2 drafts) | 8,568 | 1.68 | 7,098 / 8,568 = **82.8 %** [82.9] | 4,562 / 5,205 = **87.6 %** [87.7] | 81.0 % | **2.36** | 30.75 (+10.0 %) |
| C1f (greedy, frozen placement) | 679 | 1.00 | 633 / 679 = 93.2 % | - | 93.2 % | 1.93 | - |

- "Reached" at position 2 means position 1 was kept and the confidence gate also offered a second draft.
- C2 offered a second draft in 68 % of rounds (5,834 of 8,568). The gate is `--dspark-conf 0.65`.
- Tokens a verify round = (kept + rounds) / rounds.

**The 1017 drafter on the same requests:**
- Runs: 10-24 dsp70 and the 10-25 dspark4060 + confirm runs.
- Setup: v0.2.4 engine, 5 drafts, the same conf 0.65 and sampling.
- W1-W3 are 97 % of those runs' drafts: overall keep rate 76.9-77.0 % on W1-W3 vs 76.9-77.1 % on all requests.

| run | position 1 | 2 | 3 | 4 | 5 | tokens a round at 5 |
|---|---|---|---|---|---|---|
| dsp70 (drafter on the 5080) | 81.7 % | 86.6 % | 88.3 % | 91.3 % | 90.8 % | 2.92 |
| dspark4060 | 81.7 % | 86.5 % | 87.9 % | 91.1 % | 90.4 % | 3.00 |
| conf-dspark4060 | 81.0 % | 86.5 % | 88.6 % | 90.6 % | 89.1 % | 2.94 |

So **the current Lucebox drafter keeps about as many drafts as the 1017 drafter at full precision, slightly more**:
position 1 82.8-83.4 % vs 81.0-81.7 %, position 2 87.6 % vs 86.5 %. The mismatch the 11-07 report worried about (base
checkpoint vs the 1017 trunk) does not show in these numbers.

One confound is open: the 1017 numbers come from the v0.2.4 engine (October), the Lucebox ones from v026p343. If the
engine's drafting changed in between, the comparison moves. Section 5 has the cheap check that settles it.

## 3. The 1017 drafter, and what fits the 4060 Ti

**Correction to the 11-03 note.** Unsloth's file `dspark-DeepSeek-V4.1-Flash-1017-Q8_0.gguf` (7,976,914,240 B,
architecture `dflash`, same 3 x 128-expert shape) is "Q8_0" only in its dense part.
- Its routed experts (13.59 B of its 14.23 B parameters, 7.22 GB of the 7.97 GB) are **MXFP4**, DeepSeek's native 4.25-bit
  format.
- Lucebox's card says the same of its own MXFP4-Q8 build: "Routed experts are repacked bit-exactly to MXFP4".
- So **"requantize to ~Q4_K" does not shrink it.** Q4_K is 4.5 bits a weight, more than MXFP4's 4.25. To fit, the
  experts have to go to about 2.6-3 bits, from a 4-bit source.

**The budget.** In C's placement the drafter has 0.34 + 4.47 = 4.81 GB and 1144 MiB free. The engine keeps ~570-600 MiB
free per card (every start line). That leaves about **5.39 GB for a drafter whose 384 experts all stay in VRAM**. Beyond
that the engine spills experts to the CPU lane, as on 10-25, when only 140 experts of the 4060 Ti's 4224 were in VRAM.

| experts | dense | drafter total | on the 4060 Ti |
|---|---|---|---|
| MXFP4 (as shipped) | Q8_0 (as shipped) | 7.97 GB | 138 of 384 experts spill to RAM |
| MXFP4 | Q4_K | 7.69 GB | 123 spill |
| Q4_K (the 11-03 idea) | Q4_K | 8.11 GB | 137 spill (bigger than as shipped) |
| Q3_K | Q4_K | 6.31 GB | 61 spill |
| IQ3_XXS | Q4_K | 5.67 GB | 21 spill |
| Q2_K gate/up + Q3_K down | Q4_K | 5.39 GB | fits, with no margin |
| **Q2_K gate/up + IQ3_XXS down** | Q4_K | **5.18 GB** | **fits** (~800 MiB free) |
| **Q2_K (Lucebox's recipe)** | Q4_K | **4.93 GB** | **fits** (as now; the formula gives Lucebox's 4.92 GB file to 0.2 %) |
| IQ2_S | Q4_K | 4.82 GB | fits |

**Likely acceptance of a 1017 Q2_K drafter: about 80-82 % at position 1, not above the current 82.8-83.4 %.**
- Start from the 1017 drafter's 81.0-81.7 % at full precision (section 2).
- Lucebox reports that Q2_K experts kept "about the same acceptance" as MXFP4 for this drafter. So a 1017 Q2_K should land
  at or a point below the 1017 MXFP4 numbers.
- The IQ3_XXS-down mix would be closer to MXFP4, but the same reasoning caps it at the 1017 drafter's own rate.
- On the evidence, a matched drafter is **not expected to beat the one C already has**. The only way it could is the
  engine confound in section 2.

## 4. What it means for the best draft count

Model:
- C0/C1/C2 give the cost of a verify round against the tokens it pushes through the target. C0 is 35.8 ms at 1 token,
  C1 63.2 ms at 2, C2 76.8 ms at 2.68 (fit: 35.8 + 27.5 x (w - 1)^0.77 ms).
- Each extra token routes to its own experts, mostly on the CPU lane, so a round costs far more than a single token but
  less with each step.
- The October 5-draft runs give the tokens a round at each cap, and how often the confidence gate offers each further
  slot: about 0.65 x the slot before. That matches C2's 68 % for slot 2.

| drafts | tokens a round (Lucebox, est.) | width | decode tok/s (est.) | vs C2 |
|---|---|---|---|---|
| 2 (C2, measured) | 2.36 | 2.68 | 30.75 | - |
| 3 (C3) | 2.69 | 3.07 | ~32.0 | ~+4 % |
| 4 (C4) | 2.90 | 3.35 | ~32.6 | ~+6 % |
| 5 | 3.03 | 3.53 | ~32.9 | ~+7 % |

- **Expected best: 3 or 4 drafts, with the gain flattening out.** C2's own pass-to-pass spread was 3.9 %. Under
  compare.py's rule (>= 3 % beyond the noise), C3 may not count as a gain over C2, and C4 is near the line.
- The gap measures this. The model rests on three points and on the gate behaving as it did in October.
- If the gate offered every slot, 3 and 4 drafts would be slower than 2 (-12 % / -19 %). That is why measuring matters.
- Lucebox's own engine defaults to 3 drafts ("the fastest on the Lucebox").
- **Drafter quality vs draft count:** each +1 % (relative) of acceptance at every position adds ~0.8 % decode at 2 drafts
  and ~1.3 % at 4. A matched drafter 1-3 % worse would cost ~1-2 % at C2 and ~2-4 % at C4, and would favor fewer drafts.
  It would not move the best count by more than one, and not upward.

## 5. Recommendation

1. **Don't build the 1017 requant now.** The numbers say it would not beat the current drafter.
2. **Optional, cheap (~7 min with 8080 down): an acceptance probe in the post-Phase-5 DeepSeek gap**, run only if at
   least 15 min remain before the gap's cap after the planned steps.
   - Arm: C2's config with the October pack `pack-ist-das-2.00bpw`, which holds unsloth's 1017 MXFP4-Q8 drafter
     unchanged. 138 of its experts would sit in RAM, so its speed is not judged.
   - Run: W1-W3, one pass.
   - What it gives: the 1017 drafter's per-position acceptance on today's engine, which removes the October confound.
   - **Rule, fixed now:** build the Q2_K requant (then gate it as its own arm) only if its position-1 rate beats C2's by
     >= 2 points. Otherwise close the idea.
3. **If Karl wants the requant built anyway**, the build would be:
   - Unsloth's llama.cpp build already knows this architecture (`~/.unsloth/llama.cpp`: `LLM_ARCH_DFLASH` in
     src/llama-arch.cpp:149; build/bin/llama-quantize). So the requant is one
     `llama-quantize --allow-requantize` run, with per-tensor type overrides: experts Q2_K (or the IQ3_XXS-down mix),
     dense Q4_K, the Markov head and norms kept as they are. Then our pack. It is not tried yet: whether it requantizes
     MXFP4 input for this architecture without changes is the first thing to check.
   - Cost: CPU only, under nice 19, outside a gap; +4.9-5.2 GB disk.
   - Checks before any gap: tensor-by-tensor shape and type check; a dequant-error spot check against the MXFP4 source.
   - The output stays exact in theory (the target verifies every draft), but it still needs the same near-tie and
     sampled-distribution checks as C.
   - **Not started: Karl's OK needed.**

## Karl's decision (11-07)

> "D2: the sampled-distribution test on the winner, plus the 7-minute 1017-drafter probe. Don't build the 1017 Q2_K
> drafter unless the probe shows clearly better acceptance than the current one."

The probe runs in D2 (results/ds41/GAP-C234-PLAN.md section 4). Build only if its position-1 keep rate is >= 2 points
above C2's (section 5's rule); otherwise close the idea.
