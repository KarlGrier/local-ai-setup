

## Round 6 — experimental engine work (2026-09-29 11:58 → 17:25, stopped early on your request)

**Status: candidate C\*6 passed every check that ran, but it is NOT promoted.** The 2-hour soak was stopped after
43 minutes on your request (133 requests, 0 errors so far) and is recorded as incomplete. **C\*5 (round 5) is on
8080**, unchanged: engine `engine-cstar5/strata` sha256 `3ee92c9a…`, `configs/Cstar5.json`. It answered a test question
at 17:21. Nothing of mine is running.

**Left to do (nothing else is open):**
1. **the soak:** a full 2-hour soak of C\*6 on 8080 (`work/r6/soak.sh 120`); 43 of 120 minutes ran;
2. **the promotion decision** (after the soak): if it passes, point the launchers at `configs/Cstar6.json` (prepared:
   `work/r6/run-strata.sh.new`, `work/r6/switch-model.sh.new`), run `work/r6/rollback_test.sh`, leave C\*6 on 8080,
   write patches/PR (already drafted) as final;
3. **the 48-hour passive uptime monitor** (`work/r6/uptime_monitor.py`, tested dry): not started, as you asked.

**To try the candidate on 8080** (stop the running C\*5 first — `switch-model.sh` keeps whatever Strata already runs):
`STRATA_PORT=8080 ./run-strata.sh stop && STRATA_CONFIG=configs/Cstar6.json ./switch-model.sh strata`
**Back to C\*5:** `STRATA_PORT=8080 ./run-strata.sh stop && ./switch-model.sh strata` (the default is still C\*5).

| (4 alternating A/B pairs, fresh server each, your settings T 1.0) | C\*5 (on 8080) | **C\*6 (candidate)** |
|---|---|---|
| decode, all 768+-token requests | 89.9 tok/s | **93.6 tok/s (+4.1 %, runs do not overlap)** |
| time per generated token | 11.13 ms | **10.69 ms (−3.9 %)** |
| long reasoning 8K: math / code | 101.2 / 83.1 tok/s | **103.9 / 86.5 tok/s** |
| 32K / 64K / 120K prompt (uncached, cold page cache) | 10.0 / 19.4 / 36.6 s | 10.0 / 19.4 / 36.6 s (=) |
| GPUs | RTX 5080 | RTX 5080 + RTX 4060 Ti as helper (~6.5 GB of it; the desktop kept ≥ 535 MiB in the soak) |

C\*6 = Strata v0.1.24 + `patches/r6/0001–0012` (C\*5's 9 patches + 3 new) + the RTX 4060 Ti holding 3,300 more
experts. If the 4060 Ti lacks memory at start, the launcher starts the same build on the 5080 alone (tested).

**What was found:**
* **Round 5's verdict on the second GPU was wrong for Linux, and the reason is one line of upstream code.** With a
  helper GPU, upstream pins only 8 GiB of the 47 GB expert arena. The comment calls it a Windows (WDDM) workaround,
  but it applies on Linux too. With the whole arena pinned, the 4060 Ti helper makes verify windows 2–3.5 % faster
  instead of 2–9 % slower, and prompts are as fast as on the 5080 alone (32K: 10.9 s instead of 12.6 s).
* **An exact 1–4 % from the n-gram table.** The table is read from the SSD. Each verify window used to wait for its
  first token's rows, 0.61 ms per window. They are now requested one window early, while the window commits and the
  drafter runs. The output is bit-identical.
* **`--dump-routing` double-counted** 14.9 % of its rows (rejected drafts). Fixed and verified against the engine's
  own counters.
* **Where the time goes.** In decode, the GPU waits for the CPU experts 16 % of each window, most of it in layers 0–7.
  In a 32K prompt, weight movement is only 4 %. The time is in underfilled MMQ expert products (21 %), a per-expert
  group copy (10 %), and the GDN (25 %) and QSA (14 %) mixers.
* **Predicting and prefetching the next layer's experts: not built.** The perfect-prediction ceiling is 14.7 % of a
  window (model; your bar for a large track was ~15 % measured). Realistic estimates:
  * cache warming 5 %;
  * PCIe staging ~10 %, as a model that leaves out the DMA's effect on the GPU.

  This is Round 7's first item.
* **Dropped with numbers:**
  * per-layer cache budgets (~1 %);
  * using the helper only for some layers or window sizes (noise);
  * reading the n-gram rows beside layer 0 (the wait moved to the GPU);
  * the host's activation quantization overlap (≤ 1 %).

**Things that went wrong, all caught:**
* **Compile during a measurement:** I once compiled while a measurement ran. That run was redone, and builds then went
  through the queue.
* **Test-server stop bug:** my test-server stop script left one server running, so a baseline screen was not fresh. I
  added a fourth A/B pair.
* **Memory guard stop:** my memory guard correctly stopped a VRAM-grab test that goes below your 300 MiB floor. That
  failure mode can't be tested within the floor.
* **Sampler-test false alarm:** the sampler test first looked failed. The cause was its reference drifting with the
  adaptive expert tier. With placement frozen, the samples match (p 0.34 / 0.63).
* **Missed release alerts:** I did not read the tag watcher's log during the round. **Strata v0.1.25 (13:18) and v0.1.26
  (15:18) were released** after the Phase B freeze (12:40). Per your rule they are Round 7 backlog, not reviewed yet.

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

### C. Verification (Phase C, 13:14 →)

Candidate **C\*6** = Strata v0.1.24 + `patches/r6/0001–0012` (C\*5's 9 patches unchanged + 3 new) + the RTX 4060 Ti as a
helper GPU (`--expert-cache-device1 3300`), built from a clean clone (`work/r6/build-cstar6.sh`, sm_89 + sm_120).
Baseline = C\*5 exactly (`engine-cstar5/strata`, `configs/Cstar5.json`). Both with your chat settings (the configs'
shared-settings file: temperature 1.0, top_p 0.95, top_k 20, min_p 0.05). Every test server ran under the memory guard.

| build record | C\*5 (reference / rollback) | **C\*6** |
|---|---|---|
| source | v0.1.24 `3ce2523` + patches/r5 0001–0009, tree 455b7a68 | v0.1.24 `3ce2523` + patches/r6 0001–0012, tree d70695dc (= branch r6-cand) |
| engine sha256 | `3ee92c9a…` (sm_120) | `a56a444b…` (sm_89 + sm_120) |
| config sha256 | `3255d7b2…` configs/Cstar5.json | `b9bd8eb2…` configs/Cstar6.json (fallback configs/Cstar6-single.json `69ff0885…`) |
| sampling / template | 0.6/0.95/20/0.05 in the config + your shared settings (1.0/0.95/20; min_p 0.05 from the config); template unchanged since round 1 | identical (shared-settings file copied unchanged) |
| GPUs | RTX 5080 (4,560 cached experts) | RTX 5080 (4,560) + RTX 4060 Ti (3,300) |

**The promotion gate (fixed before the runs):** a reproducible improvement larger than the measured noise, no
unexplained material regression in any workload, no new correctness or stability failure, no required check missing.

**1. A/B speed** (`results/r6/ab-c5-c6.md`; 4 alternating pairs, fresh server and cold page cache each; the first C\*5
screen ran on a not-fresh C\*5 server because of my stop-script bug, so a 4th pair was added):

| | C\*5 (4 runs) | **C\*6 (4 runs)** | change |
|---|---|---|---|
| time to first token, 68–87-token prompts | 0.45–0.46 s | 0.45–0.47 s | = |
| 1K prompt | 0.97–1.00 s | 0.96–0.98 s | = |
| 32K prompt (uncached, cold page cache) | 10.01–10.03 s | 10.00–10.02 s | = |
| 64K prompt | 19.37–19.42 s | 19.35–19.42 s | = |
| 120K prompt | 36.55–36.59 s | 36.54–36.63 s | = |
| **decode, all 768+-token requests** | 89.3 / 90.1 / 90.6 / 89.7 tok/s (mean **89.9**) | 91.9 / 93.8 / 93.2 / 95.4 (mean **93.6**) | **+4.1 %**, no overlap |
| ms per generated token (ms per verify round ÷ tokens per round) | 11.19 / 11.13 / 11.03 / 11.15 | 10.88 / 10.66 / 10.72 / 10.50 | **−3.9 %** |
| long reasoning 8K, math | 100.1 / 102.0 / 102.1 / 100.6 (101.2) | 100.9 / 105.4 / 103.8 / 105.3 (103.9) | +2.6 % |
| long reasoning 8K, code | 82.6 / 82.7 / 83.4 / 83.6 (83.1) | 85.6 / 86.3 / 85.8 / 88.2 (86.5) | +4.1 % |
| decode after 32K / 64K / 120K (single sampled runs, ±7 %) | 83–89 / 80–84 / 84–97 | 86–98 / 83–92 / 93–98 | ≥ |
| draft acceptance | 0.63–0.66 | 0.63–0.66 | = |
| peak VRAM 5080 / min MemAvailable / peak RSS | 15,416 MiB / 29.0 GB / 57.3 GB | 15,418 MiB / 28.7 GB / 57.5 GB | = (4060 Ti ≥ 1,043 MiB free) |

Prompt time and decode are reported separately above; "uncached" = no conversation reuse (fresh server, first
request of that size). First start and cold filesystem cache: every screen starts a fresh engine (load 14–15 s) with
the model files evicted from the page cache; the launcher's warm-up prompt (9,657 tokens, 3.5 s) absorbs the first
start's kernel loading for your requests.

**2. Other workloads** (all on C\*6 unless marked):

| check | result |
|---|---|
| **web-replay chat** (a fixed 4-turn chat whose first turn carries saved kernel.org / endoflife.date tool results, replayed without live searches; `results/r6/webreplay.jsonl`) | 16/16 turns answered and checked OK in both arms, no tool calls, identical reuse (5,889 / 6,259 / 6,330 cached tokens); turn 1 (5.9K tokens, fresh server) TTFT 2.19–2.20 s C\*5 vs 2.23–2.24 s C\*6 (+2 %), later turns equal; decode per turn 97.0 vs 104.4 tok/s |
| teacher-forced accuracy (7 texts, clipped at 5 nats) | one GPU = C\*5 bit for bit; helper vs C\*5: short +0.0005 / −0.0001, long −0.017 … +0.117 (round-5 spread); vs llama.cpp mean −0.016 (C\*5 −0.039) |
| **harder needle set** (12 documents × 6 questions, 32K/64K/120K) | **72/72** (C\*5 and llama.cpp 72/72); first token 10 / 19 / 37 s |
| **quality set** (5 prompts, 1 run, 32K cap) | 5/5 finished, 89–93 tok/s; objective checks 27/29 as scored = 28/29 in fact (one regex false negative: the answer re-adds the VLAN-10 deny after the permit, i.e. keeps the restriction) — round 5's C\*5-era run 28/29 |
| chat-cache round trip (park / resume / edit, helper on, static placement) | exact: 0 of 1,536 tokens changed, all NLLs identical, drafter 0 of 385, session state identical |
| **sampler-distribution test** (9,000 requests + attribution runs) | no bias — see below |
| Stop during a 120K read | server idle 1.0 s after Stop, next request 0.69 s, back to the parked chat 0.36 s |
| overflow, context ceiling, two requests at once, idle CPU | all pass (HTTP 400 in 0.2 s; finish "length" at ~126K; both answered; 0.12 % of one core idle) |
| VRAM taken after start | **not testable within your 300 MiB floor** (a second process's CUDA context alone takes ~266 MiB of the ~500 MiB free; my guard stopped the one attempt that went to 32 MiB); round 5 verified the warm-up protection on the same code |
| **headless-Chrome browser test incl. the Web search switch** | **54 of 56 pass**; the 2 are round 5's non-bugs (a 110-token chat is not parked by design; `/favicon.ico` 404). Web: switch shown / off by default / on, answer with 3 tool cards and a cited URL, cards survive a reload, follow-up, Stop during a tool call 0.01 s, off |
| launcher fallback | 4060 Ti short of memory (another process holds 1 GiB) → `run-strata.sh` starts the 5080-alone config and serves; memory back → the helper config |

**The sampler test in detail.** 9,000 sampled requests through the measurement build with C\*6's flags, at the three
round-1 near-ties, drawn either as a plain first token (j0) or inside a speculative window after three accepted drafts
(j3). No sample ever fell outside the allowed set. Against Strata's own forced log-probabilities, arith and code
passed, but the science tie failed at j3 (p < 0.001). Attribution:
* The forced reference itself moves while the adaptive expert tier re-places experts. Within one run its three
  repeats flip the order of ',' and ';' (0.419 vs 0.393 in the first repeat, 0.376 vs 0.427 in the next two). The
  samples, however, were drawn over thousands of requests while the placement changed.
* With placement ON, the failing case moves around: C\*6 one GPU fails j0 (p < 0.001) and passes j3 (p 0.39); a
  v0.1.24 C\*5-era build passes both (p 0.42 / 0.58).
* **With placement frozen (`--adapt-swaps 0`) on C\*6 with the helper,** the reference is identical in every repeat, and
  the samples match it: **j0 p 0.34, j3 p 0.63.** So the sampler and the speculative accept rule are unbiased.
  A chi-square against a drifting reference is not a valid test when the adaptive tier is on. That is a lesson for
  the test, not a defect in C\*6.


**3. Soak — INCOMPLETE (stopped at 43 of 120 minutes on your request; pending).** C\*6 on 8080 as you use it
(`switch-model.sh`, warm-up, SearXNG, both GPUs), round 5's big-chat traffic, your settings, memory guard watching:
* **Traffic:** **133 requests from 16:37 to 17:20, 0 errors**, including:
  * 20 new chats with a pasted 32K/64K/120K document and 28 returns to an earlier big chat;
  * 17 web-search chats and 8 returns to them;
  * 16 follow-ups, 16 short chats, 6 long-reasoning requests and 4 regenerates;
  * Stop pressed 52 times.
* **Back to a big chat that was still parked:** median 0.66 s, max 3.6 s. Back to one the chat cache had dropped: median
  19.5 s (read again). The 32K probe read in 9.94–10.01 s, or 0.2–0.3 s once reused, with decode 82–97 tok/s.
* **Memory:**
  * MemAvailable never below 25.4 GB (round 5's soak minimum was 26.0 GB); engine RSS 50.4–60.5 GB.
  * The chat cache peaked at 10,466 of 16,384 MiB. The soak summary's "53,867 MiB" summed the shared engine log of all
    of today's C\*6 servers and is wrong.
  * 5080 VRAM 15,382–15,406 MiB used (≥ 476 MiB free); 4060 Ti ≥ 535 MiB free, while your desktop used more of it
    from ~17:00.
  * Swap 0.28 GiB, left over from before the round.
* **Engine log:** no engine errors. The 35 error lines in the soak's server log are all `fetch_page` refusals or failed
  page downloads, as in round 5 (`web_search` 146 ok).

### D. Files, state, what is left

**Running now:** C\*5 on http://127.0.0.1:8080 (`./switch-model.sh strata`, 17:21; verified: engine sha `3ee92c9a…`,
answers correctly) and SearXNG on 127.0.0.1:8888 (started with it). No queue, test server, soak, guard, monitor, tag
watcher or uptime monitor of mine is running. The launchers still default to C\*5 (not changed).

| what | where |
|---|---|
| candidate C\*6 config (+ its 5080-alone fallback) | `configs/Cstar6.json`, `configs/Cstar6-single.json` (+ `.shared-settings.json` copies of yours) |
| C\*6 engine / server + page | `engine-cstar6/strata` (sha256 `a56a444b…`, sm_89 + sm_120), `strata-cstar6/serve/` |
| rebuild C\*6 from scratch | `work/r6/build-cstar6.sh` (clean clone of v0.1.24, `git am patches/r6/0*.patch`, tree check) |
| patch series / PR drafts | `patches/r6/` (12), `pr-drafts/patches-r6/`, `pr-drafts/21–25` + README "Round 6 update" |
| launcher change for the promotion (prepared, NOT applied) | `work/r6/run-strata.sh.new`, `work/r6/switch-model.sh.new`; the helper-memory check with fallback IS already in `run-strata.sh` (only acts on configs that use a helper; old copy `work/r6/run-strata.sh.before-r6`) |
| remaining steps | `work/r6/soak.sh 120`, `work/r6/rollback_test.sh`, `work/r6/uptime_monitor.py` (passive: GET /health /status /metrics only; stop with `kill $(cat logs/r6/uptime/monitor.pid)`) |
| measurement build + tools | branch `r6-meas` (strata-r6), `r6-cand-meas` (strata-r6cm); `work/r6/` (guard.py, run.sh, srv.sh, screen.sh, route_parse.py, ceiling.py, predictor.py, cache_replay.py, cachewarm.cpp, …) |
| results | `results/r6/` (A/B table `ab-c5-c6.md`, route verification, microbench, ceilings, predictors, replay, TF, sampler, browser, round trip, web replay), `results/round6-summary.md`, day log `NOTES.md` "ROUND 6", `results/tuning-log.md` #71–79 |

### Round 7 backlog (ranked by expected gain × confidence ÷ cost)

| # | item | expected | risk / cost | first step |
|---|---|---|---|---|
| 0 | **Strata v0.1.25 (released 13:18) and v0.1.26 (15:18)** — appeared after the Phase B freeze; not reviewed | ? | – | review the diffs, fold in, measure on their own (upstream + our patches) before anything else |
| 1 | **Next-layer expert staging to VRAM** (predict layer l+1's CPU experts with router(l+1) on layer l's router input, computed on the GPU during the pool phase; DMA the predicted non-resident experts into a staging ring during the GPU phase; the real router still decides) | model: ~10 % realistic (pre-MoE, K=10), 14.7 % oracle with warming | high (graph + host + DMA ring; GPU arithmetic → TF) | an **engine oracle run** first: greedy, `--adapt-swaps 0 --suffix-draft 0`, replay a recorded trace as the oracle, measure the real ceiling incl. the DMA's effect on the GPU phase's VRAM bandwidth; go only if ≥ 15 % |
| 2 | **Prompt: MMQ reads experts through a pointer table** (no per-expert copy into the 16-expert group buffer) | ≤ 10 % of prompt GPU time (exact) | high: ggml MMQ template change; the tail read past a matrix (why `MMQ_TAIL` zero-pads) needs a padded or bounds-checked source | a parity test of one layer (bit-exact outputs) with padded ring slots |
| 3 | **Prompt: underfilled MMQ** (~160 rows per expert per chunk; 21 % at ~1.4 TFLOPS) | unknown, possibly large | high (kernel work) | profile MMQ tile occupancy per expert size; try tile sizes for 64–256 rows |
| 4 | **Deterministic draft policy switch** (`DraftPolicy` uses measured round times) | exact A/B tests without `--suffix-draft 0` | low | upstream suggestion (PR draft 24) |
| 5 | **Adaptive draft length** (item 9, not attempted) | unknown | med | replay candidates from the v2 trace (missing counterfactuals = unknown), confirm with real runs |
| 6 | Helper expert choice by exposure (put the 4060 Ti's 3,300 experts on the layers where the CPU is on the critical path) | ~1 % (the per-layer budget replay gave +1.1–1.4 % for the 5080's cache) | med | replay first |
| 7 | Decode n-gram reads: the drafts' rows (only token 0 is prefetched now); SSD power-state latency in decode (p50 ~450 µs vs ~110 µs in prompts) | ≤ 1 % | low | prefetch each draft's rows as the MTP produces it |
| 8 | The host's activation quantization before the pool (6.9 µs/layer, serial) | ≤ 1 % | low | parallel over tokens / workers, exactness test |
| 9 | Carried from round 5: v0.1.23's batched window not bit-identical at T=6 (corpus text); EAGER VRAM (draft 12); first long prompt allocates GPU memory (draft 15; warm-up covers it); setup.py moves `strata*` folders (draft 11); page min-p (draft 08) | – | – | upstream |

