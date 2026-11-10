### 3. Item 1 — the engine oracle for next-layer expert staging (measured; no predictor built)

**What was built (measurement only, branch `r7-oracle`, never served).** The promoted build's source plus an
env-gated oracle (`src/core/oracle.cpp`):
* a run **records**, for every verify window and layer, the experts the CPU pool computed;
* a second run **replays** that record as the predictor. As soon as the host has released layer l to the GPU, it copies
  layer l+1's predicted experts into two VRAM staging banks on the copy engine, during the GPU phase that precedes
  layer l+1. The layer's plan then gives each staged expert to the GPU (upstream's existing "PCIe share" groups) if
  its copy has landed; otherwise the CPU computes it as before. The real router still decides.
* The staging VRAM is **charged to the expert cache**: `--vram-reserve-mib 882` instead of 800 for 2 × 16 slots
  (81 MiB), so the 5080 cache holds 4,518 instead of 4,560 experts. The recording for these arms is made at the same
  reserve.
* **Warming** the same way: the CPU threads read exactly the rows each of them will compute into their caches. This
  needs a static task → thread assignment (`STRATA_POOL_STATIC=1`, measured to cost nothing: −0.1 / −0.2 %). It can be
  capped at N experts per layer, with or without the host thread's share.
* **A degraded predictor**: each true expert kept with probability 0.6, plus wrong ones up to precision 0.46. Those are
  round 6's measured figures for the best causal predictor (next layer's router on the pre-MoE residual, K = 10).

**Method, and one thing that did not work as planned.** Your spec was greedy decoding with `--adapt-swaps 0
--suffix-draft 0`. For warming that works: warming does not change arithmetic, so the replay stays aligned (402/402 and
525/525 windows). **For staging it does not work.** A staged expert is computed on the GPU, which rounds differently
from the CPU, so a near-tied router choice flips and the greedy text drifts from its recording within the first window
or two (88 of 18,336 layer calls stayed aligned). The "perfect" predictor then became ~34 % recall. So staging was
measured on a **teacher-forced fixed text** instead: the math text, 1,536 tokens, through the same verify windows,
cache, CPU pool and helper GPU, in windows of 2, 3 and 4 tokens. With the token sequence fixed, the recorded predictor
covered **~98 % of the true CPU experts** (rare near-ties still flip a few ids). Window size 1 cannot be forced this way,
because the engine refuses `--spec 1` with a native pack. Per-window times come from the oracle's own log (graph
launch → the window's GPU work and copies done). Baseline repeats agree within 0.1–0.4 % (per-window sd 0.5–0.7 %).

**Results** (saving in time per window, + = faster; perfect predictor unless noted):

| arm | static tier (your spec): T2 / T3 / T4 | **adaptive tier (what C\*7 serves)**: T2 / T3 / T4 |
|---|---|---|
| CPU experts per window (baseline) | 516 / 669 / 798 | **142 / 214 / 286** |
| baseline window | 24.6 / 30.4 / 36.1 ms | **14.6 / 17.9 / 21.3 ms** |
| **staging ≤ 4 experts per layer** (what fits the ~200 µs GPU phase) | **+15.1 / +12.7 / +11.8 %** | **−0.2 / +1.6 / +2.5 %** |
| staging ≤ 6 | +13.6 / +13.9 / +14.0 % | −0.9 / +1.3 / +2.8 % |
| staging ≤ 8 | +8.2 / +9.8 / +11.1 % | – |
| staging ≤ 16 (landed copies only) | −3.6 / −7.3 / −6.5 % | – |
| staging ≤ 16, the GPU waits for every copy | T4 −34 % | – |
| **warming ≤ 6 experts**, host out | +13.9 / +11.0 / +10.3 % | **+8.1 / +9.9 / +9.4 %** |
| warming all | +1.3 / −4.6 / −7.1 % | – |
| **both: staging ≤ 4 + warming ≤ 4** | **+17.8 / +16.6 / +16.9 %** | +0.1 / +2.9 / +4.2 % |
| **~60 %-recall predictor**, staging ≤ 6 | +2.7 / +3.6 / +4.6 % | **−2.9 / −1.6 / −0.6 %** |
| **~60 %-recall predictor, warming ≤ 6** | +3.7 / +3.3 / +3.6 % | **+1.7 / +2.8 / +2.5 %** |

Greedy decode, static tier (T1–T4 mix, aligned): warming ≤ 6 experts **+10.3 % (math) / +11.7 % (code)**, ≤ 4 +8.0 /
+8.6 %, all −5.2 / +4.6 %; by window size, warming everything helps 1-token windows by 11–12 % and hurts 4-token
windows (math +9.5 % slower).

**The DMA's effect, measured:**
* *Its own bandwidth.* A layer's CPU experts are ~22–29 MB with the static tier. The copy engine moves ~53 GB/s,
  so staging all of them takes ~0.4–0.5 ms, twice the GPU phase. Copies still in flight during the pool phase read
  the same DRAM the CPU pool is reading (~77 GB/s shared), and both slow down. Staging more than fits (16 slots) is
  therefore slower than not staging at all. Making the GPU wait for the copies is far worse (−34 %).
* *On the GPU phase.* With staging ≤ 6 (T4, static tier; GPU stage profile), the GPU's own non-expert stages grow:
  hyper-connection read + router 1.68 → 2.03 ms, output projection 0.69 → 0.83 ms, copy + combine 0.42 → 0.85 ms per
  window. Then there is the added GPU expert work (the staged groups ~1.3 ms). The CPU wait falls 16.3 → 10.3 ms, and
  the net window time falls 36.2 → 31.4 ms.

**Answer to your questions:**
* **Is the measured ceiling at least ~15 %?**
  * Under the conditions you specified (static expert set), yes, just: staging alone 13.6–15.1 % at the best slot count,
    staging + capped warming 16.6–17.8 %.
  * **On the configuration you actually run (adaptive tier), no.** Staging gives 0–3 % per window, and the best oracle
    arm is warming at 8–10 %. The adaptive tier already holds most of the experts that staging would move, and what
    is left on the CPU is mostly hidden behind the GPU.
  * Round 6's 14.7 % was a model that assumed staging was free on the GPU side, and it was measured before the 4060 Ti
    helper, which serves ~5 % of the entries and hides more of the pool.
* **What a ~60 %-recall predictor would realistically keep:**
  * adaptive tier: **+1.7 to +2.8 %** with warming, and **a loss** with staging (−0.6 to −2.9 %; wrong experts cost copy
    bandwidth and GPU time);
  * static tier: +3–5 %.
* **Recommendation: do not build the predictor or staging track.** The best realistic figure on your configuration is
  ~2–3 %, below the noise of a served A/B. If this area is revisited, the target is CPU-cache warming, not PCIe
  staging, and it needs the pool's static task assignment plus a predictor that knows the pool's job order.
