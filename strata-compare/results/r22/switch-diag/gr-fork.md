# GR_FORK on v0.2.7 / v0.2.8: why distribution check (2) fails (read-only code study, 2026-10-30)

Nothing was built, run or edited in the worktrees. The study used git reads, greps, file reads, the gap 12-14
result files and the gap 14 engine logs (STATE_HASH lines).

## Verdict

- **I found no defect in the port.** The fork's kernels, its scratch, its callers and its guard are byte for byte
  P021m's. None of upstream's v0.2.1 -> v0.2.7 changes touch the fork's inputs, its scratch or its call sites.
- **Main cause (most likely): check (2) compares two different window shapes, and the engine is not
  window-shape invariant, with or without GR_FORK.**
  - With speculation off, the sampler draws the arith-j3 tie after four 1-token windows.
  - `strata_logp` scores the same tie in row 2 of a 3-token window ("1 token first, then S_mtp").
  - The two computations end in different session states even with GR_FORK off (STATE_HASH).
  - At this near-tie, the rounding-level gap is amplified.
  - GR_FORK uses a different summation order, so it moves where that gap lands. On v0.2.7 it lands at +0.12 in the
    '=' / ' ' log-ratio: 55.3 % expected, 52.96 % drawn. Without the fork it lands at -0.005.
- **The clean fix is in the measurement, not in the engine.** Score the reference in the windows the sampler uses
  (T = 1 for the speculation-off arm). This is a change to the MEASUREMENT twin only. The served engine is
  unchanged, so exact7 is untouched. The distribution with GR_FORK stays what the KL rule already passed
  (mean 0.086).
- **Confidence: about 75 %** that this is the whole story. Test step 2 below settles it in a few minutes on the GPU.

## 1. The GR_FORK commits in both trees (task step 1)

| P021m (v0.2.1) | r22p027 (v0.2.7) | r22p028 (v0.2.8) | difference |
|---|---|---|---|
| 7d841abf fork read | 3f8c84a6 | 455489c7 | Hunk offsets and context lines only. In 0.2.7 the fork kernels sit after the new `gr_v3_default_on()` helper, and the fork branch comes before 0.2.7's `v3_env` rule instead of the old opt-in `v3` line. |
| cf8183ac own scratch (grfk_) | b0641739 | bf8760cb | Offsets only. |
| 40497567 guard | 3a8e17e8 | 0f8fa8f9 | Identical. |

- **Kernel section:** `fused_gr.cu` P021m lines 2205-2463 equal r22p027 lines 2336-2594, which equal r22p028
  lines 2336-2594 (diff empty). `xor_scatter.cuh` has the same md5 in all three trees.
- **v0.2.8 placement:** upstream split `fused_gr_read_multi` into `fused_gr_read_multi_slice` (r22p028
  fused_gr.cu:2599) plus a wrapper (2752). The fork block is in the slice function (2634), after the q8 branch and
  before v3, the same order as before.
- **Callers, the same in all trees:**
  - verify.cpp `grfk_` allocation: 811 / 993 / 970, in the zeroed arena.
  - The layer reads pass `grfk_ + grp * kGrForkScratchFloats`: 1300 / 1516 / 1493.
  - The head reads use `grfk_`: 2210, 2225 / 2469, 2484 / 2446, 2461.
  - The drafter's own `xn_` is `max(T*HC*N, kGrForkScratchMin)`: mtp.cpp 401 / 436 / 437.

## 2. What upstream changed in what the fork depends on (task step 2)

- **fused_gr.cu, v0.2.1..v0.2.7:**
  - Commits: 54d9363c (GR_V3 on by default on 12.0 cards), d18d8ba0 and d39e2a75 (GR_UP_WIDE, on by default on
    sm_120), 2395c8a5 and f1dadd17 (the persistent read on CUDA, opt-in STRATA_HC_PERSIST), 7d1016f3 (#3948
    `q81_div` in the QFUSE tails).
  - All of these sit in `launch_multi`, the v3 path, the persistent path or the QFUSE path. With GR_FORK the
    function returns before every one of them (r22p027 fused_gr.cu:2632-2641). `fused_gr_read_persist` returns
    false without STRATA_HC_PERSIST (3489).
  - `FusedGrArgs`, `GrMulti` and the constants (N 2560, HC 4, LR 320, THREADS 256, UPM_COLS 16) are unchanged.
  - No compile-flag change for fused_gr.cu.
- **Scratch:**
  - `grfk_` has no other user, and the arena is still memset to 0 (r22p027 verify.cpp:1035).
  - The `xn_` users (batched PLE keys 1420, DF_PLE postops 1465, PLE projected 1481) are the same as on 0.2.1. The
    fork no longer touches `xn_`.
- **Window structure:**
  - `G = (split_ && T >= 2 && !batch_rec_) ? 2 : 1` (1268). `split_` is opt-in (`--spec-split`, verify.hpp:684),
    so every window here is one group: region 0, one stream.
  - PDL stays opt-in (`STRATA_DF_PDL`, verify_kernels.cu:1653).
  - STRATA_GRAPH_PRIO is opt-in.
  - The side-mixer fork points are after the read, as on 0.2.1 (branch at 1580 / 1597 after the read at 1521).
  - QFUSE / QFUSE_HC are off on CUDA (201-215), so `qcnt_` is null and the fork's `return false` changes nothing.
- **One-token self-commit:** 789d8390 is the #3948 commit fix, and it applies only with QFUSE. T = 1 windows
  self-commit in both builds (1270).
- **Sampler:** the plain `sample_tokens` is unchanged. The sampler.cu diff only adds the `sample_tokens_proposal` /
  Augmented spec paths (#3416).
- **How strata_logp computes its numbers** (twin generate.cpp:16185-16245): it runs the same `ver.run`, copies
  `head_logits()` and takes a double-precision log-softmax on the host. This is the same graph family as sampling,
  with no sampler in between, but **in different windows**:
  - The forced loop uses `T = first_window ? 1 : S_mtp` (16187).
  - For arith-j3 that means a 1-token window, then a 3-token window (log: "capturing the 3-token window", then
    FORCE 1/2/3).
  - Speculation-off sampling runs four 1-token windows. The log says "4 generated ..., 4 windows" and "drafts
    accepted 0 of 0".
  - The prompt tail (37 or 40 tokens) goes through 7-token verify windows in both cases: short reads of 64 tokens
    or fewer use `read_windows` (848, 15000, 15123).

## 3. Findings, ranked

### F1 (about 75 %): a window-shape mismatch between the reference and the sampler, exposed by engine-wide non-invariance

Evidence:

1. **The final states differ for the same 111 tokens, with GR_FORK on and with it off.** The table below uses the
   gap 14 engine logs and STATE_HASH=1. It pairs each sampled request with its ids and keeps the steady state.

   | build | sampled, on path [17, 13, 7860] (T = 1 windows) | forced arith-j3 (T = 1, then T = 3) |
   |---|---|---|
   | GR_FORK on (nov2) | gdn=a737f025... (3799 of 3834) | gdn=b9feffe6... (90 / 90) |
   | GR_FORK off (nofork) | gdn=43d3a31e... (3789 of 3822) | gdn=ed935705... (90 / 90) |

   Neither build computes the 3-token window bitwise like three 1-token windows. The non-invariance does not come
   from the fork.

2. **One known non-bitwise mechanism that depends on the window shape.**
   - expert_source.cpp:4861-4912 (P021m 4540-4591): "the last pcie_num/256 of the missed ones go to the GPU",
     counted over the window's distinct misses in routing order. Every other miss goes to the CPU pool.
   - The engine log says it itself: "the GPU computes the experts in the cache; it rounds differently from the CPU".
   - A 3-token window has a different miss list than a 1-token window, so a given (token, expert) can change device.
   - The gap 12-14 check configs leave `--pcie-frac` at auto: 0.55, then 0.40, then 0.35 (log lines 127 and 296).
     Round 19 and C*17 / C*18 ran with `--pcie-frac 0`.
   - Other T-dependent paths exist too, each documented as bitwise: batched PLE for n > 1, `gr_write_multi` for
     n > 1, MMVQ_IL for 2-4 columns. The hashes show the total is not bitwise.

3. **Own probabilities for the same token sequence in different window shapes.**
   - j0 puts the path in the prompt and scores the tie in a 1-token window.
   - j3 scores it in row 2 of a 3-token window.
   - The sampled column is the steady-state '=' frequency at T 0.6, which is the 1-token-window path.

   | build | '=' j0 (P) | '=' sampled (W1) | '=' j3 (W3) | j3 - j0 log-ratio shift: arith / code / science |
   |---|---|---|---|---|
   | v0.2.7 + GR_FORK (gap 14 nov2) | 50.2 % | 52.96 % | **55.3 %** | +0.123 / +0.097 / +0.040 |
   | v0.2.7, fork off (gap 14 nofork; gap 12 r27a identical) | 52.8 % | 52.1 % | 52.6 % | -0.005 / +0.025 / +0.001 |
   | v0.1.43 stock, no fork, pcie 0 (r19 sp-v43) | 56.6 % | 52.9 % | 54.3 % | -0.056 / +0.016 / -0.098 |
   | twin17 + GR_FORK, pcie 0 (r19 sp-recheck) | 54.5 % | 52.3 % | 51.6 % | -0.069 / +0.337 / -0.016 |

   - A spread of 3-5 points across window shapes is normal at this tie, with and without the fork.
   - v0.2.7 without the fork is the unusually quiet build, not the fork the unusually loud one.
   - The sampled column agrees across builds (52-53 %). The outlier is the fork's 3-token-window reference.

4. **This is not sampling noise and not the PcieAuto start-up phase.**
   - Gap 13 (fork + PREFILL_V2) and gap 14 nov2 (fork only) give identical own probabilities to 4 digits. The fork
     arm's outcome is deterministic and reproducible.
   - With only the steady-state samples (dominant hash), the fork arm draws '=' 2012 of 3799 = 52.96 % against
     55.26 % expected: z -2.85, p 0.004. The first 35 samples, drawn while the PCIe share was still changing, are
     not the cause.

5. **PREFILL_V2 plays no part in check (2).**
   - nofork and noboth give identical own probabilities in all 6 cases.
   - Gap 13 and gap 14 nov2 are identical too.
   - The arith prompt tails are read through verify windows, never through the prompt kernels.
   - Gap 13's "PREFILL_V2 and / or GR_FORK" suspicion for check (2) is GR_FORK's rounding alone. The KL failure is
     a separate PREFILL_V2 matter: nov2 passes KL, nofork fails p90.

6. **"Passed every check" on v0.2.1 does not cover this check.**
   - I found no check-(2) run on P021m with GR_FORK in the gap 13 form (4,000 speculation-off samples against own
     probabilities, p >= 0.05). There are no result files between 10-15 and 10-28.
   - The earlier passes are the acceptance tables: about 200 samples a case, rule p >= 0.01.
   - acc-c18 (GR_FORK on, pcie 0) had min p 0.027, which fails the new rule.
   - acc-c17 (GR_FORK on) failed arith-j3 at p 0.001-0.003.
   - So "it regressed in the port" is not established.

7. **The fork kernel is window-invariant by construction.** I re-checked it line by line:
   - The down projection keeps per-token accumulators.
   - `xor_scatter<P>` gives each value exactly the 16-8-4-2-1 butterfly sum for any P.
   - The sums of squares are per token in a fixed order.
   - Windows above 4 tokens run `down` in sequential launches.
   - In `up`, `RW` and `NV` change with TT, but every value is still the butterfly sum, and the epilogue order is
     fixed.
   - The counters are reset by each quarter's last block, and the region is private.

   The fork therefore adds no window dependence of its own; it only rounds differently.

### F2 (about 10 %): a fork-specific window dependence that code reading cannot see

For example, codegen differences between template instantiations that break the invariance argued in F1.7. I see no
mechanism for it. Test step 4 below rules it in or out.

### F3 (about 5 %): the PcieAuto share changing during the run

It is real, since the first ~35 samples ran at other shares, but it is too small: the steady-state samples alone
still fail. Pinning `--pcie-frac` in the check configs removes it anyway.

### F4 (about 5 %): another v0.2.7 interaction (drafter, side streams, graph eviction)

I checked each one: the drafter has its own scratch, the side-stream fork points are after the read, and graph
eviction only re-records the same graph. I found nothing.

### Latent issue (not the cause; v0.2.8 only)

- The new wrapper reads windows above 8 tokens in slices and passes `xn_scratch + c0 * D` to each slice
  (r22p028 fused_gr.cu:2765). With GR_FORK on, `xn_scratch` is `grfk_`, which holds 52,736 floats.
- The second slice would then put its counters 81,920 floats in, inside `xq_` / `sh_xq_`. That is a
  write-out-of-bounds and a counter misfire.
- It is not reached at `--spec 7` (windows of 7 tokens or fewer, "window up to 7 tokens"). The port note already
  flags it.

## 4. The fix

### A. The measurement (the clean fix, twin only)

In strata-r22p027m and strata-r22p028m `src/program/generate.cpp` (16187 / 16262), the forced loop's window size:

```diff
-                const int T = (int) std::min<int64_t>(first_window ? 1 : S_mtp, (int64_t) forced.size() - i0);
+                // MEASUREMENT: STRATA_FORCE_T1=1 scores every forced token in a 1-token window, as speculation-off
+                // decode draws it (the default "1, then S_mtp" matches a speculative arm's windows, not plain decode)
+                static const bool force_t1 = [] { const char* v = std::getenv("STRATA_FORCE_T1"); return v != nullptr && std::atoi(v) != 0; }();
+                const int T = (int) std::min<int64_t>(first_window || force_t1 ? 1 : S_mtp, (int64_t) forced.size() - i0);
```

Then:

- The speculation-off check-(2) arms get `"STRATA_FORCE_T1": "1"`.
- Pin `--pcie-frac 0.35` (the steady value the auto rule reaches) in every check-(2) config, or drop the first 50
  samples, so the share does not change during the run.
- The speculative arm draws from mixed window shapes, so no single reference is bitwise its own. Check (1) (spec
  against spec-off frequencies) stays its exactness test. For its check (2), the T = 1 reference is the right target
  (plain decode), but a residual window-shape gap can remain there. That is worth telling Karl before reading a
  spec-arm p near 0.05 as a sampler defect.

There is no engine change: GR_FORK stays as ported. exact7 is not affected, and r27h is already 7/7 MATCHED at pin
2500. The distribution is the same as without the fork up to rounding: the KL rule passes, mean 0.086.

### B. Optional: the v0.2.8 latent slice issue

```diff
-        q8 = fused_gr_read_multi_slice(s, ct, xn_scratch + (size_t) c0 * D, stream, c0 == 0 ? stamp_buf : nullptr, stamp_i0);
+        // GR_FORK: its scratch is one region (counters reset by each read's last blocks); the slices run in order
+        float* scr = fused_gr_fork_enabled() ? xn_scratch : xn_scratch + (size_t) c0 * D;
+        q8 = fused_gr_read_multi_slice(s, ct, scr, stream, c0 == 0 ? stamp_buf : nullptr, stamp_i0);
```

`fused_gr_fork_enabled()` is already declared in fused_gr.hpp. The alternative is a patch-guard line that refuses
GR_FORK when the window maximum is above 8.

### C. Not proposed: making the engine window-invariant

That would mean deciding the CPU / GPU device per (layer, expert) instead of per window, among other changes. It is
a much bigger change that touches speed, and nothing here needs it.

## 5. Test plan

1. Build only the twin with change A as a MEASUREMENT commit, on r22-port028-meas. Leave the serving binaries alone.
2. **Bitwise confirmation (about 5 min, the deciding test).**
   - Start a fork-on, speculation-off twin server with STRATA_FORCE_T1=1, STATE_HASH=1 and `--pcie-frac 0.35`.
   - Send arith-j3 sampled requests until one lands on the path, then one forced arith-j3 request.
   - Their STATE_HASH lines (gdn / ple / tail / kv) must be equal, and the FORCE 3 logits are then exactly what the
     sampler drew from.
   - Do the same with GR_FORK off.
   - Equal hashes in both builds confirm F1. If they differ with the fork but match without it, F2 is back on the
     table: go to step 4.
3. **Check (2) rerun.** r27t-hnospec-nov2 and -nofork (on 0.2.8: the same arms), 4,000 samples each, with the
   T = 1 reference. Also keep the old T = 3 reference from the same server as a second column, to document the gap.
   Expected: p >= 0.05 for both arms on the T = 1 reference; the fork's T = 3 column reproduces about 55 % against
   about 53 % drawn.
4. **Optional proof that the fork read is window-invariant.**
   - A small parity run with STRATA_GR_FORK=1 (gr_parity-style, random R / bo / inj, apply on and off, with and
     without inject).
   - Read token k alone (T = 1) and inside T = 2..8 at every position.
   - lo, rs, inject_out, mixed and R_out must match bit for bit (memcmp). Expected: 0 differences.
5. **Optional, to locate the engine's non-invariance:** repeat step 2 with T = 3 forcing and `--pcie-frac 0`. If the
   T = 1 and T = 3 hashes then agree, the per-window PCIe split is the whole source.
6. **Regression guard:** exact7 x2 at pin 2500 on the served form. No engine change, so 7/7 is expected. Add the
   v0.2.8 slice fix (B) only with a parity run at T = 12, or with the guard.

## 6. Confidence

- No code difference between the port and P021m in the fork's path: about 90 %. It was diffed and read line by line.
- Check (2)'s failure is the reference / sampler window-shape mismatch plus ordinary rounding non-invariance, with
  GR_FORK only moving where it lands: about 75 %. Step 2 settles it.
- A hidden fork-specific window dependence: about 10 %. Step 4 settles it.
