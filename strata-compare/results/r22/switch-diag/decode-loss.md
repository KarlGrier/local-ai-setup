# Decode-speed loss, P021m (M, v0.2.1 + series) vs the v0.2.8 port (H, without PREFILL_V2 and GR_FORK)

Read-only study, 2026-10-30. Sources:
- gap 15 and gap 14 engine-log slices (`results/r22/gap1{4,5}/speed/*.englog`, `*.jsonl`, `*.startlog`);
- `logs/engine-r28h.log` and `logs/engine-r21n-candpm.log`;
- the exact7 profiles (`bringup/out/logs/prof/*-e7*-x-{p2000,32k,112k}.out`);
- `git log/diff v0.2.1..v0.2.8` in strata-r22p028.

Nothing was built, run or edited.

## Bottom line

- **H loses through slower steps, not through acceptance.** Per unit of verify work, H is **+3.5 % slower** in gap 15 (all 9 workloads slower, by +1.6 to +6.1 %).
  - H's tokens per window are **+2.6 % higher** (acceptance 72.6 → 74.0 %). That is text variance, and it hid part of the loss.
  - At equal acceptance, expect about **−3.5 %** decode, not −2.2 %.
- **The step-time loss is GR_FORK.**
  - Gap 14 (switches off on 0.2.7) gives the same per-work slowdown: **+3.9 %**.
  - The base changes are flat within about 1 %: 0.2.1 → 0.2.7 with both switches on: −0.7 %; 0.2.7 → 0.2.8 with both off: +0.3 %.
  - PREFILL_V2 is prompt-only in the code (`src/prefill/` only).
- **Unchanged between the builds:** expert cache, PCIe/peer traffic, helper-card waits, the cost gate and DRAFT_CUM decisions.
- **Recoverable:** about the whole loss, by bringing GR_FORK back once its sampling-check fix passes. Nothing else to recover on the decode side.

## How the breakdown works

Decode speed = (tokens per window) ÷ (ms per window). Each engine stats line gives, per request chunk:
- windows, drafted and accepted tokens;
- decode ms;
- expert hits and lookups, and PCIe/peer reads;
- CUDA1 staging and wait times.

A window's cost depends on its size (verified slots = 1 + drafts) and on the context length. I fitted one shared cost model to all 89 chunks of the four builds:

ms = 3.73 × windows + 4.02 × slots + 0.0087 × slots × context (k tokens); relative residual 5 %.

The split per workload:
- **"Δ from tok/window"**: acceptance and draft length;
- **"Δ from window size"**: the expected cost of longer or shorter windows;
- **"Δ from per-work speed"**: actual time ÷ the model's prediction, i.e. step speed at equal work.

The three columns multiply to the engine Δ.

## Gap 15: M → H (v0.2.8, both switches off)

| workload | client tok/s M | H | client Δ | engine Δ | tok/window M → H | Δ from tok/window | accept % M → H | slots/window M → H | Δ from window size | **Δ from per-work speed** | hit % M / H |
|---|---:|---:|---:|---:|---|---:|---|---|---:|---:|---|
| W1-think | 167.4 | 163.3 | −2.4 % | −2.4 % | 3.06 → 3.05 | −0.3 % | 71.0 → 71.8 | 3.91 → 3.87 | +0.9 % | **−3.0 %** | 87.1 / 87.6 |
| W2-code | 152.0 | 158.9 | +4.5 % | +4.7 % | 3.11 → 3.62 | +16.3 % | 65.1 → 70.2 | 4.24 → 4.73 | −8.6 % | **−1.5 %** | 82.3 / 83.1 |
| W3-research | 162.2 | 151.4 | −6.7 % | −6.7 % | 4.11 → 4.02 | −2.1 % | 76.9 → 75.7 | 5.04 → 4.99 | +0.8 % | **−5.5 %** | 77.8 / 77.2 |
| A-edit | 121.9 | 122.8 | +0.8 % | +0.6 % | 4.97 → 4.92 | −1.0 % | 79.5 → 82.9 | 6.05 → 5.74 | +4.7 % | **−2.9 %** | 47.3 / 47.5 |
| B-write | 173.6 | 159.0 | −8.4 % | −6.8 % | 3.86 → 3.65 | −5.4 % | 73.9 → 70.9 | 4.89 → 4.75 | +2.3 % | **−3.7 %** | 81.7 / 82.2 |
| R1-verify20k | 156.9 | 150.9 | −3.8 % | −3.8 % | 3.58 → 3.55 | −0.8 % | 78.1 → 78.5 | 4.31 → 4.26 | +1.0 % | **−3.9 %** | 79.7 / 79.8 |
| R2-report54k | 150.1 | 149.0 | −0.7 % | −0.6 % | 3.52 → 3.65 | +3.9 % | 70.4 → 72.5 | 4.58 → 4.66 | −1.5 % | **−2.8 %** | 80.7 / 81.3 |
| R3-extract5k | 174.9 | 173.0 | −1.1 % | −0.9 % | 4.60 → 4.93 | +7.2 % | 78.2 → 83.2 | 5.60 → 5.72 | −1.9 % | **−5.8 %** | 80.4 / 79.9 |
| R4-agent33k | 130.9 | 126.6 | −3.3 % | −3.4 % | 3.40 → 3.48 | +2.3 % | 66.2 → 68.8 | 4.66 → 4.67 | −0.1 % | **−5.5 %** | 73.2 / 72.1 |
| **all** | 154.4 | 150.5 | −2.4 % (geomean) | −1.8 % (pooled) | 3.52 → 3.61 | **+2.6 %** | 72.6 → 74.0 | 4.48 → 4.54 | −1.0 % | **−3.4 %** (time +3.5 %) | 81.0 / 81.5 |

Notes:
- **Step speed:** every workload is slower per unit of work: 9 of 9, mean −4.0 %, standard error 0.5. Short contexts (W1, W2, A, B) lose 2.3 %; long ones (W3, R1–R4) lose 4.5 %.
- **The tokens-per-window swings follow the text.** M1n's W2-code thought for 9,459 characters and hit the think cap. The other W2 runs thought for 2,100–3,900 characters, which explains W2's +16 % for H. Gap 14 shows the same pattern (below).
- **The expert/PCIe side is identical:**
  - PCIe/peer reads per window: 496.5 vs 497.1; 23.1 vs 22.8 % of routed experts;
  - CUDA1 staging: 546 vs 544 ms per 1,000 windows; CUDA1 wait: 624 vs 630;
  - KV read from RAM is similar;
  - pcie_frac settles at 0.40 in every arm.
- **Draft rule:** the share of windows with MTP drafts is 96.2 vs 95.0 %. The DRAFT_CUM threshold ends at 0.265 in most requests in both builds. Suffix drafts depend on the text (352 vs 463 windows).

## Gap 14: H27 (0.2.7, both switches on) → noboth (0.2.7, both off): GR_FORK's share

| workload | client tok/s H27 | noboth | client Δ | engine Δ | tok/window | Δ from tok/window | slots/window | Δ from window size | **Δ from per-work speed** |
|---|---:|---:|---:|---:|---|---:|---|---:|---:|
| W1-think | 179.4 | 170.3 | −5.0 % | −5.0 % | 3.49 → 3.58 | +2.5 % | 4.49 → 4.51 | −0.3 % | **−7.0 %** |
| W2-code | 153.4 | 157.6 | +2.8 % | +2.7 % | 3.17 → 3.65 | +14.9 % | 4.34 → 4.82 | −8.4 % | **−2.4 %** |
| W3-research | 157.8 | 154.5 | −2.1 % | −2.0 % | 4.12 → 4.20 | +1.9 % | 5.12 → 5.08 | +0.6 % | **−4.4 %** |
| A-edit (*) | 134.0 | 118.3 | −11.7 % | −13.0 % | 4.29 → 5.05 | +17.7 % | 5.30 → 5.94 | −9.3 % | −18.5 % (*) |
| B-write | 170.8 | 154.8 | −9.4 % | −5.3 % | 3.74 → 3.34 | −10.8 % | 4.87 → 4.37 | +9.3 % | **−2.8 %** |
| R1-verify20k | 154.1 | 147.0 | −4.6 % | −4.6 % | 3.34 → 3.31 | −0.8 % | 4.06 → 4.06 | −0.1 % | **−3.8 %** |
| R2-report54k | 150.8 | 148.5 | −1.5 % | −1.4 % | 3.46 → 3.69 | +6.6 % | 4.49 → 4.73 | −4.2 % | **−3.4 %** |
| R3-extract5k | 172.2 | 169.5 | −1.5 % | −1.6 % | 4.70 → 4.58 | −2.7 % | 5.67 → 5.46 | +3.3 % | **−2.2 %** |
| R4-agent33k | 136.4 | 132.9 | −2.6 % | −0.9 % | 3.35 → 3.78 | +12.9 % | 4.56 → 4.89 | −5.7 % | **−6.9 %** |
| **all** | 156.5 | 150.4 | −3.9 % | −2.0 % | 3.54 → 3.64 | **+2.8 %** | 4.54 → 4.60 | −1.0 % | **−3.7 %** (time +3.9 %; +4.2 % without A-edit) |

(*) A-edit is confounded by output length. H27 wrote 769 and 586 tokens; noboth wrote 195 and 330. The expert-cache hit rate is 63.4 vs 46.8 %, and the cost model has no hit-rate term.

Gap 14 looks like gap 15: the arm without the switches gains tokens per window (+2.8 %) and loses step speed (+3.9 % time per unit of work).

## Four builds on one scale (actual time ÷ pooled model; lower is faster)

| | M (0.2.1, switches on, g15) | H27 (0.2.7, on, g14) | noboth (0.2.7, off, g14) | H (0.2.8, off, g15) |
|---|---:|---:|---:|---:|
| all chunks | 0.996 | 0.990 | 1.028 | 1.031 |

Pair by pair:

| pair | per-work time |
|---|---:|
| M → H27 (base 0.2.1 → 0.2.7, switches on) | **−0.7 %** |
| noboth → H (0.2.7 → 0.2.8, switches off) | **+0.3 %** |
| H27 → noboth (switches off, same base, same gap) | **+3.9 %** |
| M → H (gap 15) | **+3.5 %** |

The two within-gap numbers (gap 14 and gap 15) agree. The two base steps add up to about 0. The cross-day pairs carry about ±1 % of day-to-day drift.

**Exact7 cross-check (same tokens, same window sizes, same expert hits, pin 2500).** M (r21ncandpm) and r27h (0.2.7 with all our patches, fork on):

| prompt | verify phases per round, M vs r27h (wait for rings + pool) | MTP per round |
|---|---|---|
| x-32k | 29.96 vs 29.83 ms | 2.68 vs 2.67 ms |
| p2000 | 26.58 vs 26.62 ms | – |
| x-112k | 25.01 vs 25.05 ms | – |

So the base's per-round work is equal.

The extra wall time of r27h (+34, +67 and +56 ms per 64 tokens) scales with the number of distinct window sizes (4, 7 and 6), about 9 ms each. That is a one-off on each size's first use (most likely graph capture). The CLI pays it; serve pays it in warm-up. So exact7's `ms/round` is not a step-speed measure across builds. Their round counts also differ, for example 18 vs 16 rounds at p2000.

## Upstream v0.2.1 → v0.2.8 decode path (1,438 commits; decode-relevant ones reviewed)

**Verify and MTP**
- The taps are off unless asked for and add no graph nodes: TAP_FILE, LOGITS_DUMP, DFlash2 (verify.cpp checks `tap_on_`).
- GRAPH_PRIO is opt-in.
- A window graph that runs out of memory now frees other window sizes (#3702). Neither build re-captured mid-run (2 capture lines in all englogs, both a first use of the 8-token window).
- 0.2.8's 16-row windows: CUDA stays at 8 (`STRATA_WINDOW_MAX_T` auto = 8). `fused_gr_read_multi` is now a wrapper over 8-row slices: one slice at ≤ 8 rows.
- The persistent HC read (`STRATA_HC_PERSIST`) now builds on CUDA; opt-in.
- `GR_UP_WIDE`: default on sm_120, off under DEFAULTS=026, and never used with v3 or the fork.
- `GR_V3`: default on with more than 13 GiB; both configs force it to 1 anyway.

**Sampler and speculation**
- The #3416 gated proposal (`SPEC_PROB`) is opt-in. Our SPEC_EXACT branch runs first.
- `SPEC_COST` is opt-in; we use COST_GATE + DRAFT_CUM.
- The faster spec-adapt start-up is the default on sm_86 only.
- The lookup policy change (ca17d0f5) is for gated requests only.
- The plain sampling chain is unchanged.

**Expert cache and adaptation**
- `ADAPT_ASYNC`: one CUDA GPU only (adapt_async_default.hpp), so it would not engage on our two cards. Pinned 0 anyway.
- `RAM_ADAPT`, `VRAM_FREE` (NVML) and `EXPERT_NIBBLE` (GP100) are opt-in.
- The NUMA pool is unchanged on one node. 0.2.8 prints the worker placement, and it is the same as M's: workers on 1–15, host on 0.
- The automatic cache reserve fix (#4474) left both builds at 4,585 + 3,300 slots.

**Decode kernels**
- `MMVQ_IL_89` (sm_89 tables, the 4060 Ti): on by default, but off under DEFAULTS=026, which is M's behaviour. The helper card's waits are unchanged.
- `MMVQ_IL_SM80` and `IL_PF`: other cards.
- MMVF wide: 16-row builds only.
- `SELECT_LONG` and `KVA`: opt-in. In 0.2.8 KVA needs `STRATA_KVA=1`, and no KVA line appears in either log.
- QFUSE rounding fix (#3948): QFUSE only. v3 and the fork both return without the q8_1 image.

**The pins against both configs**

| pin in H | 0.2.8 default and meaning | M (0.2.1) | decode effect |
|---|---|---|---|
| ADAPT_ASYNC=0 | measured async tier; serve, one CUDA GPU, arena only | none | none (it would not engage on two cards) |
| DEFAULTS=026 | all of 0.2.7's defaults back to 0.2.6's: GR_V3 auto, PROMPT_ATTN_IMMA, PREFILL_LAYER_MAJOR, ROUTE_PRIOR, PLE_AUTO_RAM, MMVQ_IL_89, GR_UP_WIDE, nv batch pipelining, sm_80/121 tables, 0.2.6 cache sizing | = 0.2.6 behaviour | none (GR_V3=1 set explicitly in both) |
| PLE_AUTO_RAM=0 | lock the 28.8 GB PLE table in RAM when table + arena (46.8 GB) + 8 GiB fit | direct reads | none; turning it on would leave about 2 GB MemAvailable (12 GB floor) |
| PREFILL_LAYER_MAJOR=0, PROMPT_ATTN_IMMA=0 | prompt paths | – | none (prompt only) |
| ROUTE_PRIOR=0 | 0.2.8's own default is 0 again (#4402); lossy | 0 | none |
| ROUTE_TAIL_SKIP=0 | lossy skip | start line says "=7 ON", but it never acts with a helper GPU (0 "route tail skip" lines in every M englog) | none |

**Unpinned new default, prompt side only.** The conversation cache is sized automatically since v0.2.3 (8,192 MiB). DEFAULTS=026 does not cover it. In H it parks synchronously at the next request's start (PARK_ASYNC is opt-in), on top of our `--chat-cache`:
- H's prompt ms on W1 and W2 is +50 and +48 ms, matching "parked … in 40.4 / 47.4 ms";
- A-edit TTFT is +119 ms against a 126 ms park.

That cost belongs to the prompt study (`--conversation-cache-mib 0` is lossless). It is not part of the decode loss.

## Ranked sources

1. **GR_FORK off: HC read on GR_V3 instead of the fork's read, in verify, the MTP draft reads and the final mixer.**
   - Size: about **3.5–4 % of decode time** at equal work.
     - Gap 14, same base: +3.9 % (+4.2 % without A-edit).
     - Gap 15: +3.5 %, with the base contributing ±1 %.
   - Earlier measurements agree: LEDGER round 11, fork vs GR_V3, −2.2 % per round; gap 2, fork + v3 unset, −4.0 % decode.
   - Recoverable: **yes, if the fork's fix passes the sampling check** (that study is running). The fork is another summation order: lossless by Karl's rule only once the KL rule and both distribution checks pass on 0.2.8.
   - Fallback if it cannot come back:
     - screen `STRATA_HC_PERSIST=1`: one persistent kernel, the down projection split over 80 blocks like the fork; unmeasured on sm_120, another summation order, so it needs the same gates;
     - `GR_V3=0` + `GR_UP_WIDE=1` (with UP75 / DOWN_TG, which are on by default on sm_120) is bitwise to the default read, but older gaps put it at or below v3. That one needs only a speed screen.
2. **Acceptance and draft length: no loss** (H +2.6 % tokens per window; gap 14's switch-off arm +2.8 %). This is text variance. Nothing to recover, but it means gap 15's −2.2 % understates the per-step gap.
3. **Expert cache, RAM→VRAM, helper GPU, pcie_frac, cost gate, DRAFT_CUM: no difference** within about 0.5 %. Nothing to recover.
4. **Upstream base 0.2.1 → 0.2.8: about 0 (±1 %).** No unpinned default changes per-step decode work on this config. The only new serve default (conversation cache) costs prompt time, not decode.

## Confidence

- **High:** the loss is per-step, not acceptance. Nine of nine workloads, both gaps.
- **High:** cache and PCIe are unchanged. The counters match.
- **Medium-high:** GR_FORK carries essentially the whole per-step loss.
  - Two within-gap estimates agree: 3.5 and 3.9 %.
  - The base steps are −0.7 / +0.3 %, but measured across days.
  - Exact7 shows equal per-round verify work for 0.2.1 and 0.2.7 with the fork.
  - PREFILL_V2's zero decode share comes from reading the code, not from a measurement: gap 14 had no speed arm with PREFILL_V2 on and GR_FORK off.
- **Size uncertainty:** ±1 point.
- **Cheapest confirmation if wanted:** in one gap, an A/B of r28h vs r28h + `STRATA_GR_FORK=1` (speed only, 2 passes). Expect about +3.5 % per unit of work.
