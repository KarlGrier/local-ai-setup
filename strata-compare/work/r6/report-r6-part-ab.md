### A. Feasibility (Phase A, 11:58–12:55): where the time goes, and what can be recovered

All numbers below are software-counted (no hardware counters without root) and measured on this PC: RTX 5080 (Gen5 x16),
RTX 4060 Ti 8 GB (Gen4 x4, drives the desktop), Ryzen 9 9950X3D, 94 GB DDR5 (~77 GB/s). Model = the same IQ3_S file.
Decode profiles are exact (greedy `strata generate --stats`, 1,024 tokens of the math prompt) unless marked "sampled";
"oracle" = the next layer's experts known in advance (an upper bound, not something the engine can do).

**Measurement tools built for this (branch `r6-meas`, never served):** NVTX ranges + an nsys capture window by decode
round or by prompt chunk; a **routing trace v2** (`STRATA_R6_ROUTE`: per window its id, position, tokens and accepted
length; per layer the routed ids, the router's weights, where each entry ran — VRAM / CPU / helper — and the host's
timings); residual dumps for the predictor study; `STRATA_PIN_LIMIT_GIB`; helper gates by layer / window size. A
memory guard (`work/r6/guard.py`) ran around every experimental load: MemAvailable ≥ 20 GiB and ≥ 300 MiB free on the
5080, sampled every 0.2 s from before the load. Lowest values seen in any run: MemAvailable 35.1 GiB, 5080 472 MiB free,
4060 Ti 1,043 MiB free (with the helper). No run was stopped by the guard.

**1. Profiles of the C\*5 build**

*Decode* (nsys, node-level graph trace, 120 windows): a verify window is 48 × (GPU phase + CPU pool) + tail + commit +
drafting. Per layer the CPU pool takes 140 µs, of which the GPU works beside it for 72.5 µs (the VRAM-cached experts and
the shared expert); the GPU phase from the pool's end to the next layer's router is 187 µs into a GDN layer and 222 µs
into a QSA layer. **The GPU waits for the CPU 3.16 ms per window (16 % of the 17.9 ms traced window)** — that is the
ceiling for every CPU-side idea. It is very uneven: layers 0–7 carry 1.36 of the 3.25 ms (layer 0's pool is 439 µs),
layers 15–37 are mostly hidden behind the GPU. Outside the layers: tail (last layer + head + sampler) 0.84 ms, commit
0.52 ms, MTP drafting 1.12 ms.

*Prompts — what upstream already does (v0.1.24, read in `src/prefill/prefill.cpp`):* 8,192-token chunks that borrow
expert-cache slots; every non-resident expert of every layer streamed in a fixed order through a 384-slot DMA ring while
the attention halves run; MMQ grouped expert GEMMs directly on the GGUF blocks (16 experts per launch, all 48 layers of
this model); batched layer-1 PLE with next-chunk n-gram read-ahead on a 64-thread reader; tensor-core QSA attention and
selection; one host sync per MoE layer for the token grouping.

*A cold, uncached 32K prompt* (untraced, upstream's `STRATA_PREFILL_TIMING`; a fresh process, so the first chunk carries
~0.55 s of first-use kernel loading; the served C\*5 reads 32K in 10.0 s after its warm-up): GPU busy 10.74 of 10.91 s.

| part of a 32K prompt | share | reading |
|---|---|---|
| MMQ expert products (gate/up + down) | 21 % | ≈ 1.4 TFLOPS: ~160 rows per expert per 8,192-token chunk — underfilled |
| copying each expert into the MMQ group buffer | 9.9 % | (the timer calls it "dequant") |
| combine, router + shared expert, grouping, gather | 7.4 % | |
| **waiting for streamed experts = weight movement** | **3.9 %** | the copy engine keeps up |
| GDN mixer | 24.5 % | |
| QSA projections, selection, attention | 14 % | selection 2.2 % at 32K, 5.6 % at 112K |
| hyper-connection reads | 12 % | |

A 112K prompt (14 chunks) has the same shares; an nsys capture of two chunks at depth (chunks 11–12 of 112K) shows the
same kernels (nsys inflates the prompt path: 17.2 s traced vs 11.0 s for 32K).

**2. Router → CPU start (exact).** No sync or readback delay: the doorbell kernel runs right after the router's top-10
and writes ids, weights and the activations into mapped host memory; the host spin-polls it. Between the doorbell and
the first expert row the host does 10.7 µs of serial work per layer (plan 1.0, activation quantization 6.9, job list
2.8 µs) = 0.51 ms per window, at most ~0.25 ms of it recoverable where the pool is exposed → not pursued (≤ 1 %).
A related exact loss was found and fixed (Phase B): the window's **n-gram rows** were read from the SSD synchronously
before the launch, 0.61 ms per window (decode reads p50 ~450 µs: the SSD idles between windows).

**3. The RTX 4060 Ti helper.** Per layer (routing trace): launching the helper 5–8 µs, the CPU pool 136 µs instead of
166 µs (the 4060 Ti computes ~5 % of the routed entries), waiting for the helper after the pool 4–9 µs.
**The pin cap was the whole problem.** Upstream caps the pinned expert arena at 8 GiB whenever a helper is on — its
comment calls it a WDDM (Windows) workaround, but it applies on Linux too, leaving ~40 GB of the arena neither pinned
nor locked. Same build, greedy windows by size:

| | 5080 alone | helper, 8 GiB cap (upstream) | helper, whole arena pinned |
|---|---|---|---|
| 32K cold prompt | 11.02 s | 12.56 s (only 15,120 of 88,032 streamed experts by DMA) | **10.88 s** |
| 1-token window | 13.39 / 13.36 ms | 14.11 ms | **13.11 / 13.10 ms (−2 %)** |
| 4-token window | 24.57 / 24.20 ms | 25.16 ms | **23.55 / 23.50 ms (−3.5 %)** |
| 4060 Ti free VRAM | – | 1,119 MiB | 1,043 MiB |

Is it safe? The whole arena is registered PORTABLE exactly as with one GPU (MemAvailable unchanged, min 36.4 GiB); the
4060 Ti's mapping of it costs ~76 MiB of its VRAM; no errors. Selective use (skip 1-token windows: 4-token 23.38 ms;
only the layers where the CPU is exposed: 23.83 ms; helper loaded but bypassed: 24.39 ms = one GPU) did not beat the
noise → the helper is used as upstream uses it. Round 5's "helper is 4–5 % slower" came from the cap.

**4. CPU-cache warming microbenchmark** (`work/r6/cachewarm.cpp`: the engine's own CPU expert kernels, 1,024 real
experts of layers 14/16, 16 threads placed like the pool, 7 experts = 15.2 MB per layer, tasks assigned statically):

| tokens per expert | cold DRAM | warmed by the same thread (0–200 µs before, ± 16/64 MB of competing reads) |
|---|---|---|
| 1 | 204 µs (74.7 GB/s = the engine's pool rate) | 129–131 µs (**−36 %**) |
| 2 / 3 / 4 | 229 / 248 / 257 µs | 178–181 / 206–209 / 228–231 µs (−22 / −17 / −11 %) |

The warm-up itself needs 193 µs for 15 MB — about the GPU phase in which DRAM idles. One expert on one core is
compute-bound (266 vs 262 µs): warming only helps when all cores are bandwidth-bound together.

**5. Routing trace.** Upstream's `--dump-routing` (0.1.23, #118) does record the verify window, but one row per drafted
token: a rejected draft's row is written and its position written again by the next window. **8,592 of 57,840 rows
(14.9 %) were double counts** on the math run. Fixed (patch 0010: rows buffered per window, only the accepted ones
written at commit) and a v2 trace added for this study. **Verified on a controlled run** against the engine's own
counters: 393 windows = rounds; window ids 0..392; 48 layer records each; positions contiguous (pos0 of the next window =
pos0 + accepted length); accepted length recomputed from tokens and outputs; drafts offered/accepted/rejected
812/633/179 = `--stats`; window-size and acceptance histograms equal; VRAM-hit entries 451,358 of 578,400 = the cache
counter; CPU experts per layer 5.72 distinct / 6.73 routed = `--stats`; pool, activation, plan and doorbell-wait
times within 1 %; router weights present; the fixed dump = 49,248 accepted rows, identical ids.

**6. Perfect-prediction ceiling (ORACLE estimates, replayed on the real trace with the measured costs).** Each layer's
real CPU experts are prefetched within the real lead time (the GPU phase before that layer: ~187–222 µs), alongside the
real GPU work; the pool cannot drop below the GPU's own work beside it (38 µs + 2.2 µs per VRAM expert).

| oracle method | saving per window |
|---|---|
| (a) CPU-cache warming (the computing thread warms its own rows; fixed, CCD-aware task assignment) | 1.75 ms = **8.3 %** |
| (b) staging to VRAM over PCIe (55 GB/s; the GPU computes them; staging VRAM ~32 slots) | 2.88 ms = **13.6 %** |
| (a+b) best split of the lead (they compete for the same ~15 MB of DRAM time per layer) | 3.11 ms = **14.7 %** |
| (no lead limit, for reference) | (a) 11.7 %, (b) 22.3 % |

Staging beats warming per byte (it removes CPU work instead of making it ~1/3 faster).

**7. Causal predictors** (the model's own next-layer router applied to information available at decision time; no
training, so every prompt is held out; K chosen on math, reported on code / puzzle):

| predictor | byte recall | byte precision | (a) warming | (b) staging |
|---|---|---|---|---|
| router(l+1) on layer l's pre-MoE residual, K = 10 | 0.58–0.60 | 0.46–0.47 | 4.9–5.0 % | 10.4–10.6 % |
| same, K = 14 / 20 | 0.69–0.71 / 0.78–0.80 | 0.36 / 0.26 | 5.1–5.2 % | 10.4–10.5 % |
| router(l+1) on the post-MoE residual (as read by l+1), K = 10–20 | 0.55–0.79 | 0.23–0.41 | 3.2–3.6 % | 6.3–6.8 % |

The post-MoE residual is not more accurate here (hyper-connections) and leaves less lead (120 / 169 µs vs 187 / 222 µs).
Per layer, recall is lowest where it matters most (layer 1: 0.39–0.40, layers 22/38: 0.38–0.47).

**8. Expert-cache admission replay** (the engine's adaptive tier reproduced exactly — its placement agrees with the
engine's on 99.24 % of entries): per-layer budgets chosen by time saved per byte (capped by the GPU's slack), at the
same 8.70 GiB: +2.0 % on the training trace, **+1.1 / +1.4 / −0.6 % on held-out** code / puzzle / 1K → dropped.

**9. FreeToken** (15 min of reading): its model table says "Qwen3.8-Flash-Next keeps a 47.7 GiB PLE n-gram table pinned
in host RAM" — yes, by default; its v0.1.3 added an opt-in `--ple-backend disk` to stream it. Adaptive draft length
was not attempted (backlog).

**Decision point (12:45).** Phase C estimated from round 5's job times at ~5 h → Phase B cutoff 22:00.
The large track (prediction + staging) needed a measured ceiling ≥ ~15 % and a realistic ≥ ~8 %: the oracle is 14.7 %
(model), the realistic 10.4–10.6 % is a model that leaves out the ~10 MB/layer DMA's effect on the GPU phase — **not
started** (Round 7, beginning with an engine oracle run). Phase B = the sure things.

| rank | opportunity | recoverable (measured unless noted) | risk | validation | decision |
|---|---|---|---|---|---|
| 1 | helper GPU with the arena fully pinned (Linux) | −3.5 % 4-token windows, −2 % 1-token; prompts = one GPU | low–med | TF, A/B, soak | **built** |
| 2 | next window's n-gram rows read during commit + drafting (exact) | −1.0 … −3.7 % per window size | low | exactness, A/B | **built** |
| 3 | prediction + PCIe staging | ~10 % (model), 14.7 % oracle | high | heavy | Round 7 |
| 4 | cache warming with a predictor | 4–5 % (model) | high | heavy | no |
| 5 | overlap of the host's activation quantization | ≤ 1 % | low | exactness | no (noise) |
| 6 | per-layer cache budgets | ~1 % (model) | med | TF | no |
| 7 | prompt: MMQ reading ring/cache slots through a pointer table (no group copy) | ≤ 10 % of prompt GPU time | high | parity + TF | Round 7 |
| 8 | prompt: underfilled MMQ | ? | high | – | Round 7 |

### B. Build (Phase B, 12:40–13:15)

* **n-gram rows, first try — read beside layer 0** (reads issued before the launch, collected on a thread, layer 1 waits
  on a mapped flag): the host's 0.6 ms became a GPU wait of 0.35–0.58 ms at layer 1 → no net gain, dropped.
* **n-gram rows, kept — prefetch at commit** (patch 0012): the next window's first token is the window's output
  n_keep − 1; its 16 rows are requested at commit and arrive during commit + drafting. Staging 0.61 → 0.28 ms per window;
  same greedy trajectory: 1-token windows 13.40 → 12.90 ms (−3.7 %), 2-token −1.2 %, 3-token −1.0 %, 4-token 24.41 →
  24.02 ms (−1.6 %); repeats of the old build vary ±0.4–0.6 %.
* **Pin cap** (patch 0011): Linux registers the whole arena with a helper, as with one GPU; `STRATA_PIN_LIMIT_GIB`
  overrides on either system.
* **`--dump-routing`** (patch 0010): accepted rows only.
* Correctness gates:
  * *Exactness of the prefetch:* with `--adapt-swaps 0` the old build is **not** reproducible run to run (two outputs
    alternate) — the draft policy picks MTP or prompt-lookup windows from **measured** round times, so any timing change
    changes the windows (PR draft 24). With `--adapt-swaps 0 --suffix-draft 0`: prefetch off = on = a deliberately wrong
    prefetch (another token's rows), bit for bit, on one GPU (math) and with the helper (code).
  * *Accuracy (teacher-forced NLL, 7 texts, clipped at 5 nats):* the C\*6 engine on one GPU = C\*5 bit for bit (1,536 /
    1,536 tokens on every text). With the helper vs C\*5: math +0.0005 ± 0.0006, corpus −0.0001 ± 0.0013 nats/token;
    long texts +0.117 / −0.017 / −0.010 / +0.014 / +0.010 — within round 5's last-bit spread (v5 moved them −0.121 …
    +0.013); vs llama.cpp on the same file mean −0.016 (C\*5 −0.039). Bypassed layers (helper only on 24–47): +0.0017 /
    +0.136 / +0.044, fine; helper bypassed for 6-token windows or switched off: = C\*5 bit for bit.
  * The launcher: with the helper, `run-strata.sh` checks the 4060 Ti's free memory first and starts the same flags on
    the 5080 alone (`configs/Cstar6-single.json`) if the desktop card is short, instead of failing.
