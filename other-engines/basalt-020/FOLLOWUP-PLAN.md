# Basalt follow-up (Karl 11-02) - plan, before any GPU step

Karl's brief: after 7e, next to gap 17, about 1-1.5 h; tell him before 8080 goes down. No decision yet: he decides
with these numbers and with whether Basalt looks likely to support Qwen4.

## The gap (one, ~85-90 min with 8080 down; after 7e ends ~06:30 11-03; Karl told first)

Same safety as gaps 1-2: port_gap4.sh (hold, bench.lock, test lock, 8080 down), watch.py (MemAvailable 12 GiB, 5080
free >= 300 MiB, the swap rule, kcheck every 60 s), guard.py per step, kernel check after each step; every Basalt step
in `unshare -rn`, the 5080 alone. P028x back at the end (sha f4c4f654fb24 checked).

1. **Build the exact-head variant** (~4 min, offline, memory guard): a worktree basalt-020/src-exacthead of the
   basalt-pr90 clone at v0.2.0 + patches/exact-head.patch (sha256 72134e23; applies cleanly - `git apply --check`).
   Local only, nothing pushed. The stock build in src/ stays as it is.
2. **Basalt: exact head vs two-stage** (the same tests as gaps 1-2):
   - by hand, Basalt's fixtures (conv / struct / prose decode, 16K, 64K; a fresh engine per measurement): stock x3,
     exact head (BASALT_EXACT_HEAD=1) x3, and the patched build with the variable unset x1 (it must equal stock);
   - the 9-workload screen through basalt serve (131K, int8 KV, conversation cache off): stock x3, exact head x3.
   - Checks: the engine log's `BASALT_EXACT_HEAD=1` start line and its exit count "N windows: 0 two-stage, N exact";
     expert slots equal between arms. ~30 min.
3. **P028x: the helper's value** - x28h (P028x without vision, the 4060 Ti on: 3,300 helper slots) vs x28h-solo
   (the 5080 alone, configs/x28h-solo.json), 3 passes each in turned order, gap 16's harness:
   - the 9-workload screen (work/r22/abarm.sh, engine timings);
   - Basalt's fixtures, cold (work/r22/basalt-pr90/bp90_client.py: decode, 16K, 64K, a fresh engine each).
   - Before measuring the solo arm: its engine's environment must show STRATA_ROUTE_TAIL_SKIP=0 and one GPU
     (Strata's tail skip is on by default on CUDA without a helper; pinned off so the arm stays lossless). ~50 min.
4. P028x back on 8080.

The hyper-connection path is not changed (Karl): its cost is estimated below from the bytes it reads.

## Estimates (to be replaced by the gap's numbers where it measures them)

**Exact head** (EXACT-HEAD-NOTES.md): about +0.35-0.55 ms per verify window, i.e. decode -1.5 to -2.5 %; prompts
unchanged (the head runs once per prompt). Measured in step 2.

**BF16 hyper-connections in decode** (EXACT-HEAD-NOTES.md section 6; read once per verify window): 1,279.3 MB as BF16
vs 691.5 MB as int8 + scales = +587.7 MB per window -> +0.71 ms at the probe's 828 GB/s, +0.89-1.01 ms at 70-80 % of it;
the drafter adds 18.1 MB per draft step. Per token: Basalt's fixtures (~4.95 tokens per window) -3.5 to -5 %; our
workloads (~2.5 tokens per window) about -5 to -7 %. Not measurable today: Basalt has no BF16 decode switch (new kernel
work). Uncertain: whether such small reads reach full bandwidth; the drafter's part may sit in the 64 MB L2.

**The 4060 Ti as a Basalt expert tier** (HELPER-TIER-NOTES.md): the design already supports a second card (the peer
tier: no P2P needed, a slower peer takes the experts ranked after the main card's); what keeps the 4060 Ti out is the
sm_120-only build (CMake, `#error` in mmq_common.cuh) and the card check (gpu_select.cpp). Phase 1 = decode only,
medium work: sm_89 code for two kernel files (iq_kernels.cu, elementwise.cu), about six sm_90+ sites guarded, the checks
relaxed, the sm_120 code byte-identical (so Basalt-alone results do not move); bitwise parity tests across the two
architectures (`__expf`, FMA contraction); --peer-adapt-swaps capped (the default 96 swaps need ~30 ms of x4 link per
~17 ms window). A local patch only (Basalt's CONTRIBUTING.md rules out other architectures). Capacity: ~3,500-3,700
slots (2.046 MB average), 14-15 % of the experts; with the 5080, 34-35 % instead of 19.5 %. Basalt's own price model:
decode +8-9 % (optimistic: no link cost); prompts unchanged. Calibrated in step 3 by P028x's measured helper value,
carried over as milliseconds saved per token, not as a percentage.

| | P028x | Basalt today (two-stage head, int8 hc) | Basalt lossless (est.) | Basalt lossless + 4060 Ti tier (est.) |
|---|---|---|---|---|
| Basalt fixtures, decode blend | 198.4 | 217.2 (+9.5 %) | ~201-206 (+1 to +4 %) | ~217-225 (+10 to +13 %) |
| 9-workload screen, decode | 157.5 | 161.8 (+2.8 %) | ~147-151 (-4 to -7 %) | ~158-165 (+1 to +5 %) |
| 9-workload screen, prompt | 2,113.5 | 2,436.5 (+15.3 %) | the same | the same |
| cold 16K / 64K prompt | 3,827 / 4,383 | 5,064 / 5,440 (+32 / +24 %) | the same | the same |

Reading, before the gap: lossless Basalt alone would be about level with P028x on decode in our workloads (slightly
behind) and well ahead on prompts; with the 4060 Ti tier, slightly ahead on decode at the optimistic end. The decode
side rests on two estimates (hc bytes, the helper's real value); step 3 checks the second, and step 2 the head.

**Work behind "Basalt lossless + helper"**: the exact head (an env switch: done as a patch), a BF16 hyper-connection
decode path (new kernel work, not started), the sm_89 tier (medium), then our quality gate (a)-(d) (REPORT.md) and the
usual exactness tests - all local patches on an engine whose upstream does not take them. Qwen4 support: unknown.

## Decision rule (Karl 11-02, set BEFORE the gap's results)

Recompute "Basalt lossless + 4060 Ti" against P028x on the **9-workload screen, decode**, from: the measured exact-head
cost (step 2), the measured helper value (step 3) and the hyper-connection estimate.
- **+8 % or better on decode:** write a plan for a local Basalt branch; Karl decides.
- **Anything less:** no Basalt branch. Port Basalt's prompt path (exact parts) into Strata after gap 17, as already
  listed (results/r22/basalt-pr90/HEAD2HEAD-PLAN.md, catch-up list).
- **Either way:** revisit Basalt if it supports Qwen4 before Strata does.

The arithmetic, fixed now (scripts/followup_decide.py), all on the screen's client-clock decode, each arm's value =
the mean over its 3 passes of the per-pass geometric mean over the 9 workloads (gap 16's form), all arms from this gap:
1. Basalt lossless, ms per token = 1000 / D(Basalt exact head) + hc, where hc = the BF16 extra per verify window
   divided by the exact-head arm's tokens per window (from its stream timings: predicted_n / (predicted_n -
   draft_n_accepted), geometric mean over the workloads). hc per window: 0.95 ms central (0.89-1.01 ms = 70-80 % of
   828 GB/s for +587.7 MB); the drafter's +18.1 MB per draft step is left out of the central value (it may sit in L2)
   and in the range's upper end.
2. The helper's value on P028x, ms per token saved = 1000 / D(x28h-solo) - 1000 / D(x28h); carried over to Basalt as
   milliseconds, not as a percentage.
3. Basalt lossless + 4060 Ti = 1000 / (step 1 - step 2). Against D(x28h) (P028x without vision, the helper on, this gap).
4. The verdict uses the central value; the range (hc 0.89-1.01 ms + drafter, the passes' min / max) is reported beside
   it. If the central value is >= +8 % but the range's low end is below +8 %, that is reported as such - Karl decides.

## Result (the gap 11-03 05:03-06:18, 74 min with 8080 down; results/followup-decision.md, summary-followup.txt)

Screen decode (client clock, 3 passes each): Basalt stock 161.5, Basalt exact head 156.7 (-3.0 %; the fixtures' blend
-0.7 %, inside the spread: 217.5 vs 219.1), P028x x28h 154.8, P028x with the 4060 Ti off 134.5 (the helper +15.1 % on
the screen, +10.9 % on Basalt's fixtures: blend 199.9 vs 180.2; prompts 1 % faster without it). Every solo / on engine's
environment checked before it measured (24 of 24: STRATA_ROUTE_TAIL_SKIP=0, the right GPU count). Exact head proved
in the fixtures ("0 two-stage" counts); the patched build with the variable unset = stock (218.2). Kernel log clean.
**The rule: Basalt lossless + 4060 Ti = 174.9 tok/s = +13.0 % vs P028x 154.8 (range +6.2 to +17.6 %) -> the central
value clears +8 %, the range's low end does not: reported as such, Karl decides.**
