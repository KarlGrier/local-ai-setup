# F1 item 3: Infernix's per-size expert frame pools, checked against our Strata fork (11-04)

**Verdict: no design needed. Strata already packs mixed-size experts byte-exactly on both cards.** Per-size pools
would add **0 experts on the 5080 and 0 on the 4060 Ti**, so there is no decode gain to price. Study only: no code,
builds or GPU runs.

## How Strata allocates (served tree strata-r22p028x; the port base strata-r22p0210 is the same)

- **5080 arena** (`ExpertCache::open_sized`, src/core/expert_cache.cpp:652):
  - One cudaMalloc holds slots of each pair's own blob size, back to back, with 256-byte strides. Every blob here is
    already a multiple of 256, and the served config adds no STRATA_MMQ_DIRECT guard.
  - A "slot" is one expert of its layer's size. The per-slot offsets go to the kernels.
- **Sizing** (src/program/generate.cpp:7020-7085):
  - `auto` first counts uniform slots of the largest blob from free VRAM minus the reserve: 713 MiB + 89 MiB for the
    draft head, which gives 3,526.
  - That count x 2.66 MB is the byte budget, capped by free VRAM. The profile's pairs fill it in rank order at their
    own sizes.
  - `--expert-cache N` is the same budget, N x the largest blob.
- **Swaps:**
  - The adaptive tier pairs a candidate and a victim within one layer only (generate.cpp:11460-11480), and every expert
    of a layer has one size.
  - So a swap never changes a slot's size, and the arena has no fragmentation.
  - Each layer's slot count stays where the profile put it: 78-116 per layer on the 5080.
- **4060 Ti helper** (`RemoteExperts::open`, src/core/remote_experts.cpp:136):
  - Exact sizes too (`open_sized`), but sized by a **count** (`--expert-cache-device1 3300`), not a byte budget.
  - It is filled once with the next ranks (4,583-7,882) and stays static: `--remote-expert-opt` is off.
- **0.2.10** changes only an "all experts fit" no-borrow case, which does not apply to us.

## Measured sizes (served pack r20a, Qwen3.8-Flash-Next GSQ-RCO IQ3_S, 48 x 512 experts)

| gate/up / down | blob | x largest | layers |
|---|---|---|---|
| IQ2_S / Q2_0 | 1,510,400 B | 0.567 | 5 |
| IQ3_XXS / Q2_0 | 1,715,200 | 0.644 | 3 |
| IQ3_S / Q2_0 | 1,868,800 | 0.702 | 1 |
| IQ2_S / IQ4_NL | 1,971,200 | 0.740 | 15 |
| IQ3_XXS / IQ4_NL | 2,176,000 | 0.817 | 14 |
| IQ3_S / IQ4_NL | 2,329,600 | 0.875 | 9 |
| IQ4_XS / IQ4_NL | 2,662,400 | 1.000 | 1 |

In total: 46.84 GiB of experts, mean 2.046 MB. Infernix's doc gives "mean 1.95 MiB, largest 2.54 MiB", which is the
same file.

## Experts that fit

Strata's fill was recomputed from the pack index and the profile (work/catchup/scratch-f1/sizes.py), and it matches
the logs exactly:

| card | uniform largest-blob slots | Strata (sized) | ideal byte-packed / per-size pools | logged |
|---|---|---|---|---|
| 5080 served (`auto`) | 3,526 | **4,583 (1.300x)**, 8.742 GiB | 4,583 (unused: 0.84 MB, a third of one blob; first-fit to the end: +0) | 4,583 slots, 8.74 GiB (engine-P028x.log) |
| 5080 exact7 pin 2500 | 2,500 | 3,238 (1.295x) | 3,239 | 3,238, 6.20 GiB (prof/g17-*.err) |
| 4060 Ti (3,300 by count) | 2,502 in the same bytes | **3,300 (1.319x)**, 6.206 GiB | 3,300 | 3,300, 6.21-6.22 GiB |

**Infernix measured the same gain on its 5090:** 13,008 frames against 10,206 of the largest frame size (1.275x). Its
own replay shows a byte-exact global LFRU as the bound of its pools: 6.23 % misses against 6.37 % for static
classes (design §19.3.25). Strata's arena is that byte-exact form.

**Side note on helper headroom (a count setting, not packing):**
- With 3,300 experts the 4060 Ti still has 1,285 MiB free at its minimum (srv-* logs, 10-16 to 10-21). Keeping the
  engine's 512 MiB, about **396 more** experts would fit (~3,700).
- The UPGRADE-ESTIMATE §6.5 Flash-Next model prices that at **+0.5-1.1 % decode**. Inputs: miss −0.4 to −0.7 points;
  c = 14.4-17.2 µs per miss entry, 613 routed per token, against today's 6.29 ms.
- Round 11 measured 3,500 at +0.8 %, which was within noise (NOTES 4124). That was while the desktop still used the
  4060 Ti.
- If wanted, this is a config A/B, not a code change.

## Infernix's policy (F1 item 4, for later; read only, clone at infernix-review/Infernix 944ff1f)

- **Pools:**
  - One pool per record stride, each with its own VMM arena and controller.
  - `resize(n)` gives every layer n/layers frames to start with (src/runtime/expert_offload/expert_residency.h:9-14).
- **Adaptive tier** (Basalt's rule; expert_residency.cpp:809-905): decay 0.85, candidate floor **1**, margin 1.5,
  96 swaps per round (cap x4 when there are many candidates).
  - Candidates and residents are paired **across all layers of a pool**. Because the frames of a pool share one
    stride, each swap stays in place.
- **Their claims** (5090, about 53 % of experts in VRAM):
  - Floor 1: +1.5 % decode after a 16K prompt, +2.7-5.4 % on their fixtures.
  - Cross-layer pairing: +1.1 % on struct, flat at 16K.
- **Ours:**
  - Floor 2.0 is hard-coded (generate.cpp:11468, 11743, 18510).
  - `--adapt-min-gain` 1.5, `--adapt-decay` 0.7, `--adapt-swaps` 96, every 4 rounds; same layer only; the helper is
    static.
  - Each size class here has one type pair, so a cross-layer pairing within a class would need no new allocator.
    That is the only thing these pools have that we lack. It is a hit-rate question, not capacity.
- **Gate if it is ever tried:** it changes placement, so judge it by the KL yardstick rule as for cache-size changes,
  not exact7.
