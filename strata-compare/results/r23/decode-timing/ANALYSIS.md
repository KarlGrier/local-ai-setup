# Decode timing: where a window waits, and what the three candidate items can save (r23, 11-04)

Karl's item 3, part 1. Read-only analysis by a helper (saved by Claude: the helper's own write of .md files was refused).
Nothing was built, run or measured for it; every number comes from logs that already existed.
- **Scripts:** parsers in `work/r23/decode-timing/scratch/`: `trace.py`, `stats.py`, `serial.py`, `draftg.py`, `between.py`,
  `byT.py`, `g18.py`, `helper.py` - read the logs and the nsys SQLite files read-only, each under
  `nice -n 19 taskset -c 31 timeout 120`.

## 0. Summary

- **The window is a serial chain per layer.** The GPU runs the dense part of the next layer while the CPU pool idles;
  then the CPU pool runs the layer's missed experts while the GPU mostly idles. In the 10-21 traces the GPU sat in its
  wait for the CPU rows for **34 %** of the verify graph on two cards (5.4 of 16.1 ms) and **41 %** on one card (7.1 of
  17.4 ms). The 15 pool workers idle during the serial GPU part, the draft chain and the head: ~55 % of each cycle.
- **The serial GPU part has no slack:** 98-99 % GPU-busy, 1.5-3 us of launch gaps per layer; GDN mixer (~70 us), hc
  reads (~44 us), router + doorbell (~16 us). Only kernel work can shorten it, and kernel work changes rounding - also why
  gap 18 found PDL, GRAPH_PRIO and FUSE_WAIT gave nothing.
- **The three candidates, against the measured waits:**

| item | what it removes | upper bound per window | likely | verdict |
|---|---|---|---|---|
| GPU-side MoE planning (G4) | the host's plan (1.8 us / layer) and the GPU's wait for it (p50 1.5-1.8 us / layer) | ~0.15 ms (0.6 %) | 0-0.1 ms | **not written**: too small |
| one CPU-pool batch per layer (C3) | the gate/up barrier: the phase's tail, the host's quantization, one publish | ~0.85 ms solo / ~0.75 ms two-card (a fit; not measured) | 0.19-0.38 ms solo, 0.13-0.27 ms two-card | **written** as `STRATA_POOL_ONE_BATCH=1`, with a counter that measures the barrier |
| single-graph draft chain (G6) | host round trips between draft launches (12-35 us each, p50) | ~0.1-0.17 ms (0.4-0.7 %) | ~0.05-0.1 ms | **not written**: the chain is GPU-bound (409 of 417 us busy per step) |

- **One two-card wait the solo logs cannot show:** the helper GPU's staging and launches run on the host **before** the
  CPU pool starts: 0.55 ms per window (11.7 us per layer launch), measured in gap 18's two-card B arm (3 passes, 33
  requests, 16,255 windows); in the 10-21 two-card trace the CPU pool was the long pole in 69 % of layer-windows.
  **Written as item 1, `STRATA_REMOTE_LATE_LAUNCH=1`.** Upper bound 0.55 ms / window (+2.5 %), likely 0.25-0.45 ms
  (+1.1-2.0 %).
- **A two-card timing pass is needed** (config + command ready, section 7, not run, ~4 min): P028x's own two-card shares
  (the only per-layer two-card data is P021's 10-21 trace); what is in P028x's GPU-reach wait of 186 us / layer (solo;
  P021's serial part at a similar window width was ~141 us); the two-card baseline for items 1 and 2.

## 1. The sources, and what each can show

| source | build / form | what it has | what it lacks |
|---|---|---|---|
| gap 18 `engine-SOLOt.log` (11-03) | P028x on the 5080 alone (`x28h-solo-dtime.json`) | window split per request (GPU-reach wait, plan, CPU, draft) and entries per layer-window; 11 requests, 5,442 windows | values per window or per layer (only means); no GPU stage table (the vprof arm ran without DECODE_TIMING) |
| gap 18 `speed/B[123][nar].englog` | P028x on both cards (`x28h.json`) | per request: helper launches, host staging+launching ms, host waiting ms | no window split (DECODE_TIMING off) |
| gap 7 nsys traces, 10-21: `results/r22/profile/a-math-nsys.sqlite` (two cards), `a1-math-nsys.sqlite` (one card) | engine 0.1.46 with P021's flags (`--pcie-frac 0` then); math prompt, 512 sampled tokens | every kernel of every window: **per layer-window distributions** of the waits, the serial segment, the helper's kernels, the draft launches | an older build; no PCIe share; nsys node tracing inflates the verify graph's launch call (1.25 ms two-card, 0.39 ms one-card per launch) |
| gap 7 stats runs (`a-math-stats.log` and others) | the same, no profiler | the pool's phase split (gate/up, quantize, down) | per-layer values |
| r18 `prof-side.txt` (10-10) | C*14 | a GPU stage table (VERIFY_PROFILE + DECODE_TIMING) | an even older build |

No log has per-window distributions for P028x itself, and the two-card pass will again give per-request means. Per-layer
values for P028x would need nsys (distorts the launches) or `STRATA_VERIFY_TRACE` (the trace ring is only dumped on errors).

## 2. One window, measured (P028x, one card, gap 18)

Weighted by windows over the 11 requests, without the warm-up; p10 / p50 / p90 across requests, not windows.

| part | mean ms/window | p10 | p50 | p90 | per layer |
|---|---|---|---|---|---|
| window | 25.54 | 18.71 | 24.78 | 31.61 | |
| GPU-reach wait (host-measured, a layer's CPU rows -> the next doorbell) | 8.91 | 8.60 | 8.78 | 9.29 | 185.7 us |
| CPU experts (pool + finish) | 13.43 | 7.37 | 12.87 | 19.44 | 279.7 us |
| host plan | 0.08 | 0.07 | 0.08 | 0.10 | 1.76 us |
| drafting | 2.29 | 1.88 | 2.22 | 2.77 | |
| tail (head, sampling, launch) | 0.75 | 0.74 | 0.74 | 0.76 | |
| columns / tokens per window | 4.44 / 3.49 | 3.82 / 2.95 | 4.38 / 3.30 | 5.06 / 4.10 | |
| per layer-window: distinct CPU experts / PCIe experts / VRAM hit entries | 7.79 / 3.49 / 30.2 | | | | |

Fits over the 11 requests:
- **GPU-reach** = 6.81 + 0.44 x columns + 0.050 x PCIe experts per layer-window (ms / window; residual sd 0.18). Columns
  and PCIe experts correlate at 0.85, so the split between them is uncertain.
- **CPU** = 37.6 us per distinct CPU expert per layer, intercept -12.8 us per layer (no fixed per-layer cost in this
  fit; section 5.2 has one that shows one).
- **What varies:** the CPU part 7.4-19.8 ms across requests; GPU-reach, drafting and tail nearly flat.

## 3. Per layer-window, measured (the 10-21 traces: P021's flags, PCIe share 0)

Two cards = `a-math` (190 windows, 9,120 layer-windows); one card = `a1-math` (207 windows, 9,936 layer-windows).

| per layer-window (us) | two cards: mean | p10 | p50 | p90 | p99 | one card: mean | p50 | p90 | p99 |
|---|---|---|---|---|---|---|---|---|---|
| serial: layer l's CPU rows -> layer l+1's doorbell (GPU side) | 143.9 | 129.5 | 139.1 | 159.7 | 289.2 | 140.8 | 137.0 | 155.8 | 277.9 |
| host round: doorbell -> the GPU sees the CPU rows | 178.1 | 72.0 | 136.3 | 341.4 | 590.7 | 208.2 | 160.6 | 427.0 | 710.8 |
| waitA: the GPU waits for the host's plan | 4.96 | 1.47 | 1.57 | 2.21 | 6.82 | 1.93 | 1.82 | 2.18 | 6.82 |
| plan copy + VRAM hits | 52.3 | 35.8 | 52.3 | 68.2 | 80.7 | 51.3 | 50.8 | 66.9 | 80.3 |
| waitB + PCIe groups (empty at pcie 0) | 2.4 + 4.1 | | | | | 1.6 + 3.5 | | | |
| **waitC: the GPU idles waiting for the CPU rows** | **112.8** | 1.5 | 72.7 | 280.2 | 508.2 | **148.4** | 97.7 | 376.2 | 660.4 |
| helper's first kernel starts (after the doorbell) | 23.8 | 10.7 | 23.2 | 24.1 | 27.6 | - | | | |
| helper's last kernel ends (after the doorbell) | 89.5 | 56.6 | 80.8 | 121.4 | 191.4 | - | | | |
| helper's end -> CPU rows seen | 93.7 | 3.7 | 51.6 | 253.4 | 459.9 | - | | | |

**Per window** (sums of the rows above; two cards / one card): serial 6.76 / 6.62 ms; layer 0's lead 0.15 / 0.15; graph
tail (head + sampling) 0.63 / 0.63; host rounds 8.55 / 9.99; waitC 5.42 / 7.12; waitA 0.24 / 0.09.

**The long pole per layer-window:** the CPU pool 69 % (two cards) / 79 % (one card); the helper (rows seen < 8 us after
its last kernel) 20 % / -; the GPU's own branch (waitC < 3 us) 11 % / 21 %.

**By layer:** host round per layer 111-250 us (two cards), 112-380 us (one card); layers 0-7, 18, 22, 28, 38 heaviest;
layer 0's serial part 282 us (the PLE post-ops, ~140 us, run after its combine).

**Inside the serial segment, by kernel** (two cards; one card within 5 %): GDN mixer (qkv/out `mmvq_il`, conv, step
norm, a/b, quantize + interleave) 74 us; hc reads 45 us; router + doorbell 17 us; the shared expert's dense rows' unhidden
part 8 us; copy rows + hit add + combine 8 us; QSA ~5 us (averaged over all layers). The kernels' union covers 142.3 of
143.9 us -> launch gaps **1.5 us per layer** (3.2 us on one card).

## 4. Between windows: the draft chain (the 10-21 traces)

- **Between two windows:** one commit graph (5 kernels, 251-256 us), one MTP catch-up graph (57-61 kernels, 448-486 us;
  also makes the first draft), 1-2 MTP step graphs (52 kernels, 417 us each); 85 % of windows have 3 MTP launches.
- **Inside one step graph,** 409 of 417 us GPU-busy: draft head (Q6_K, 40,525 rows) 97 us; the draft layer's dense rows
  83 us; sampler (`sampler_split_part`, the exact proposal's draw) 75 us; hc reads 57 us; the draft layer's experts 13 us.
- **Host gaps** (two cards / one card): verify graph's end -> first draft launch p50 74 / 71 us (sync, accept, launch the
  commit); between draft launches p50 35 / 12 us, mean 43 / 23 us (p10 negative: commit and MTP graphs overlap on two
  streams).
- **Last draft launch -> next verify:** under nsys 1.49 / 0.60 ms (almost all the nsys-inflated launch call); in the
  stats runs (no profiler) 1.08 ms / window (two cards) and 0.94 ms (one card) fall outside the verify layers and the
  drafting: the launch, the head + sampling tail (~0.63 ms) and the commit.
- **P028x drafts more:** 2.8-5.2 drafts per MTP window (STRATA_DRAFT_CUM) vs ~2 in P021 -> 3-4 MTP launches per window;
  consistent with gap 18's 2.29 ms = 0.94 ms fixed + 0.39 ms per step.

## 5. The three items, priced on the waits

### 5.1 GPU-side MoE planning (G4): not written

- Would remove the host's plan (0.08 ms / window, 1.76 us / layer) and the GPU's wait for it before the hits (p50
  1.5-1.8 us / layer). The hits are off the critical path in 79-89 % of layer-windows, and the CPU pool still needs to
  know its own entries (the host would wait for the device's classification instead).
- **Upper bound** ~0.15 ms / window (0.6 %); likely 0-0.1 ms. Gap 18's FUSE_WAIT=2 (-0.87 %, within noise 2.6 %) agrees.
- On two cards the 0.6 ms "plan" column (P021 stats: 0.608 two-card vs 0.059 one-card) is the helper's staging, not
  planning - item 1 deals with it.

### 5.2 One CPU-pool batch per layer (C3): written as `STRATA_POOL_ONE_BATCH=1`

- **Today:** gate/up rows = 48 tasks on 16 threads (~3 per thread); then every worker parks while the host quantizes each
  expert's intermediate; then the down rows = another 48 tasks. In P021's stats gate/up is 61 % of the phase time; the
  host's quantization 0.05 ms / window (~1 us / layer).
- **The barrier was never measured, and two fits disagree:** P021's bench (6 runs): pool = 32 us / layer + 26.7 us per
  distinct expert (gate/up 21.6 + 15.7, down 10.1 + 10.9); gap 18's serve fit: -12.8 us / layer + 37.6 us per expert (no
  visible fixed cost).
- **Upper bound** (the fixed part of gate/up: start latency + tail): (21.6 + 1) us x the layers where the CPU is the long
  pole (79 % solo, 69 % two-card) -> ~0.85 ms solo (3.5 %), ~0.75 ms two-card (3.4 %). An overestimate: one batch cannot
  remove the start latency.
- **Likely:** 5-10 us per CPU-bound layer -> solo 0.19-0.38 ms / window (+0.8-1.5 %), two-card 0.13-0.27 ms (+0.6-1.2 %;
  smaller tasks there, so a smaller tail).
- **Measurement built in:** with STRATA_DECODE_TIMING the commit prints idle thread-ms per window at the end of the
  gate/up phases, the down phases and the one-batch layers, plus the host's quantization time - the gate's timing arms
  turn the estimate into a measurement.

### 5.3 Single-graph draft chain (G6): not written

- Would remove 2.5-3.5 host round trips between draft launches per window at 12-35 us each (0.03-0.12 ms); removing the
  verify -> draft trip (~70 us) too would need the device to decide the verify result - more than a chain graph.
- **Upper bound** ~0.1-0.17 ms (0.4-0.7 %). The steps are GPU work, 98 % busy: the Q6_K head reads 81 MB per step
  (bandwidth-bound), the sampler adds 75 us per step.
- **High exactness risk for the gain:** DRAFT_CUM's product threshold and the cost gate would move to the device bit for
  bit, and the item would need checks (1) and (2).
- **What could help drafting instead** (kernel work, not exact by construction): the sampler kernel, an evict-first head
  read.

## 6. Waits that point elsewhere (candidates, not written)

| candidate | the measured wait | bound | why not now |
|---|---|---|---|
| **H2:** the helper writes its rows straight into the layer's mapped rows, skipping the host copy in `RemoteExperts::finish` (after the pool, on the window's path) | ~355 helper entries / window x 10 KB = 3.6 MB of host memcpy per window (gap 18 B arm) | est. 0.15-0.35 ms / window | not timed; item 1 adds the counter (`strata decode timing: CUDA1 rows copied by the host`); write H2 if >= 0.15 ms / window |
| **P1:** run the PCIe groups beside the VRAM hits instead of after them on one stream | P028x's GPU-reach 186 us / layer solo vs P021's serial ~141 us; P028x's fit gives ~171 us at P021's window width; the fit's PCIe term explains only ~0.17 ms / window of the gap | 0.17 ms / window by the fit; up to ~1.5 ms if all the unexplained part is branch overhang | the two-card stage table decides: `t2_report.py` prints "GPU-reach minus the GPU serial stages"; write P1 if > ~0.4 ms / window |
| **G5a:** prefetch the next layer's dense weights into L2 during the CPU wait | the GPU idles 5.4 / 7.1 ms / window in waitC; the serial segment is 98-99 % busy, 80 % GDN mixer + hc reads | unknown (memory stalls; hardware counters need admin rights here) | needs a probe first; the hits stream ~50 MB / layer through the 64 MB L2 in the same window |

## 7. How the solo waits carry over to two cards, and the two-card pass

- **Same on both forms** (the 10-21 pair, same build): the serial GPU segment (143.9 vs 140.8 us / layer), the draft chain
  (1.51 vs 1.48 ms per round), the head tail -> G4, G6, P1, G5a would gain the same on two cards.
- **Different on two cards:** a smaller CPU part (the helper takes ~40 % of the misses: P021 4.64 vs 7.36 distinct CPU
  experts per layer-window; for P028x ~306 vs ~500 CPU entries per window, ~8.2 of 22.3 ms - inferred, not measured);
  fewer layers wait on the CPU (69 % vs 79 %; the helper is the long pole in 20 %); two waits that exist only on two cards:
  the helper's staging before the pool (0.55 ms / window, measured: item 1) and the host waiting for the helper (0.69 ms /
  window; 0.04-0.97 per request); a smaller per-layer saving from item 2 (smaller tasks), on the same layers.
- **A short two-card pass is needed:** P028x's two-card split was never logged; only the stage table tells whether 186 vs
  141 us / layer is kernels or branch overhang (decides P1); items 1 and 2 need a two-card baseline.
- **Ready, not run:**
  - `results/r23/decode-timing/x28h-t2dv.json` = `configs/x28h.json` (P028x's served form without vision, both cards) +
    `STRATA_DECODE_TIMING=1` + `STRATA_VERIFY_PROFILE=1` (the profile changes the graph - shared expert inline, fused waits
    off - so its rates come out ~2 % low). Optional: `x28h-t2d.json` with DECODE_TIMING alone, at served rates.
  - Inside an open gap (8080 down, the test lock held by the driver via `work/r22/port_gap4.sh begin`):
    `bash /home/USER/ai-speed-testing/strata-compare/results/r23/decode-timing/t2pass.sh dv` (~4 min; `both` adds the
    second arm, ~8 min). One 9-workload screen pass per arm through `bringup/lib/with_server.sh` + `work/r22/abarm.sh`
    (gap 18's solo-arm harness), the `p028x_env_check.sh` env check first (STRATA_ROUTE_TAIL_SKIP=0, 2 GPUs),
    `bringup/lib/kcheck.sh` after; output in `results/r23/decode-timing/t2/` (slices, `engine-T2dv.log`,
    `report-T2dv.txt`).
  - Parser `results/r23/decode-timing/t2_report.py` (tested on gap 18's SOLOt log and r18's profile): the window split,
    the helper's staging per window (item 1's bound), the GPU stage table, and "GPU-reach minus the GPU serial stages"
    (branch overhang; on r18's pcie-0 profile it reads 0.16 ms = the flag latencies).
