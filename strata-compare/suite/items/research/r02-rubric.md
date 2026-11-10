# r02 rubric: "What is the best model I can run on this hardware?" (approved by Karl 11-01)

**The question's date:** 12 Oct 2026, the date of the frozen web snapshot.

**The PC, as the models were told:** RTX 5080 16 GB + RTX 4060 Ti 8 GB, Ryzen 9 9950X3D, 96 GB DDR5-6000, fast NVMe,
Linux.

## Facts to judge against

These come from the suite's key; "measured" means measured on this PC.

- **What fits:** the model at its quantization must be at most 110 GiB in all (RAM + VRAM, leaving room for the OS and
  cache). Anything over 120 GiB cannot run.
- **Qwen3.8-Flash-Next (178B MoE):**
  - IQ3_S, 78 GiB: ~145 tok/s, measured on both cards + RAM.
  - Q4_K_XL, 104 GiB: ~70 tok/s, measured on the 5080 + RAM.
- **Qwen3.8-27B (dense):** Q4_K_M is ~16-17.5 GiB and fits in the two cards' VRAM. Not measured here; ~25-45 tok/s
  is a plausible estimate from memory bandwidth.
- **Other current big MoE models that run here from RAM:**
  - GLM-5.3-Flash UD-Q2_K_XL: 102 GiB, ~16 tok/s measured.
  - MiMo-V2.6-Flash BPW2.5: 91 GiB, ~20 tok/s measured.
  - Signal-3.8-Flash-Next Q4_K_XL: 95 GiB, not measured.
- **Cannot run:**
  - Qwen3.8-2.4T-A95B is too big.
  - Qwen3.8-Max and Qwen3.8-Omni-Flash have closed weights.

## Which top picks count as reasonable

- **Best:** Qwen3.8-Flash-Next, at a quantization that fits. Only this pick can earn a 5: on this PC it is both faster
  and stronger.
- **Reasonable** (at most 4):
  - Qwen3.8-27B (Karl, 11-01).
  - GLM-5.3-Flash, MiMo-V2.6-Flash or Signal-3.8-Flash-Next, at a quantization that fits. They're bigger, but much
    slower here.
- **Dated but workable:** any earlier-generation model that fits:
  - gpt-oss-120b or gpt-oss-20b;
  - Qwen3, 3.5 or 3.6 models from 14B to 35B, including 35B-A3B;
  - Gemma 4 (12B, 26B-A4B or 31B);
  - GLM-4.7-Flash;
  - Qwen3-Coder-30B-A3B.

  They run, but they aren't the best available in October 2026, and most leave the 96 GB of RAM unused.

## The scale

Judge the top pick first, then the rest of the answer.

- **5:** the best top pick (Qwen3.8-Flash-Next) at a quantization that fits, with a believable speed and reasons
  that fit this PC. No real errors.
- **4:** a reasonable top pick with no real errors, or the best top pick with one real flaw. A real flaw is:
  - a speed off by more than about 2x;
  - a size or quantization slip;
  - thin reasons;
  - telling the user to avoid something that runs well here: Flash-Next, Qwen3.8-27B, experts in RAM, or splitting a
    model across both cards.
- **3:** a dated-but-workable top pick with a correct fit and sound reasons; a reasonable top pick with one real
  flaw; or the best top pick with two or more real flaws.
- **2:** a dated top pick with real errors (wrong sizes or speeds, or treating the PC as 24 GB only and ruling out
  RAM), or a top pick that doesn't fit as stated.
- **1:** no usable pick: none given, one that can't fit (over 120 GiB), closed weights, or wrong throughout.

## Two adjustments

- **Alternatives:** if the top pick is dated but the alternatives name a best or reasonable model with a correct fit,
  go up one level, to at most 4.
- **Cut off:** if the answer stops early, rate what it says before it stops.

**Karl, 11-01:** a flawless Qwen3.8-27B answer tops out at 4; a 5 is only for Flash-Next at a size that fits.

**When it is used:** at the Qwen4 round (or when more models are tested), Karl re-rates ALL r02 answers, old and new,
on one shuffled page with the labels hidden, against this rubric. His first ratings stay on file next to the new ones.
Until then r02 ratings are provisional.
