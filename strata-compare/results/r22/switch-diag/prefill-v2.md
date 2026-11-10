# STRATA_PREFILL_V2 after the v0.2.7 / v0.2.8 port: why the KL check fails (code study, 2026-10-30)

Read-only study: git read commands, grep, file reads, and numpy over the existing pf_yardstick logit files in
results/r22/gap8, gap12, gap13 and gap14. Nothing was built, run, installed or edited in any tree.

## Verdict

I found **no integration defect** in the ported v2 path. The v2 kernels receive the same experts, rows, tables,
buffers, strides, scales and stream order on 0.2.7 as on 0.2.1, and the v2 code is byte-identical in all three trees.
On 0.2.7, v2's own effect on the prompt logits is the same size as on the served build or smaller.

The KL FAIL comes from the way the check is set up:

- r27h is compared with gap 8's **0.2.1, one-GPU** reference.
- So r27h carries two rounding-level steps: the 0.2.1 → 0.2.7 build step, plus v2's own step.
- The bounds (mean ≤ 0.401, p90 ≤ 0.366, top-1 ≥ 34/40) describe the spread of **one** rounding change.
- With 40 prompts, two or three chaotic rows decide both the mean and the p90.

Each step passes the rule when it is judged on its own. Stacked, they fail.

**A clean fix exists, and it is better than "rounding-level":** v2 can be made **bit-identical** to the current
kernels. The commit names a single arithmetic difference, the order of one product per 32-value term, and changing it
is a four-line edit (section 4). With that change, v2 on and v2 off give the same bytes, so the KL check shows exactly
the v2-off result (r27h-nov2: mean 0.086, PASS). The only open question is how much of v2's speed survives.

Side finding: distribution check (2) fails only in the arms with **GR_FORK** on, whether v2 is on or off. v2 is not
what fails check (2).

---

## 1. The patch in both trees (task 1)

| | served build | v0.2.7 port | v0.2.8 port |
|---|---|---|---|
| worktree | strata-r22p021m | strata-r22p027 | strata-r22p028 |
| commit | 785e45df | b7f25d8c | 91f7ef22 |

Comparing `git show` of the three commits (changed lines only):

- **moe_fused_iq.cu, moe_fused.cu, prefill.cpp, both headers, CMakeLists.txt, prefill_fused_iq_test.cpp:** identical
  +/- lines. Only the context differs:
  - the v2 section sits after 0.2.7's NT=256 / F16 / WS kernels and reopens the `!__HIPCC__` block;
  - `setup_v2` comes after `setup_nt`.
- **patch_guard.cpp / patch_guard_test.cpp:** the port carries P021m's final guard files. That adds the DRAFT_CUM
  guard and its two test cases, and keeps STRATA_DRAFT_CUM in the guard list. None of this touches v2.
- **md5 of the extracted code is equal in all three trees:**
  - the v2 kernel section: 021m moe_fused_iq.cu:728-1102, 027 and 028 :1193-1567 (`5c0f97b1…`);
  - the v2 host section (`v2_env`, `v2_occ`, `v2_counters`, `launch_v2`, `native_v2_*`): 021m :1785…, 027 :2316…,
    028 :2331… (`5c119b27…`);
  - `setup_v2`.
- **`experts_native(const Batch&)`:** 021m moe_fused_iq.cu:1917 vs 027 :2451. The only code difference is upstream's
  opt-in WideBatch early return at 027 :2538-2545 (`if (d.occ_nt > 0 || d.ws)`). It is inactive in every config here,
  because none sets STRATA_PF_FUSED_NT, _F16 or _WS. The v2 block itself is unchanged (021m :2014-2047, 027 :2556-2589).
- **Call site in prefill.cpp:** 021m :3654-3690 vs 027 :4282-4338. Differences:
  - upstream's opt-in `STRATA_PF_BATCH` / WideBatch plumbing (`per_launch` stays kMaxBatch when unset);
  - `cudaStreamWaitEvent(m.cs, m.copied[...])` (021m :3682) became `wait_copied(k - 1, ...)` (027 :4324). With
    STRATA_PREFILL_COPY_EVENT_EVERY unset, `wait_copied` is literally the same `cudaStreamWaitEvent(m.cs, m.copied[slot])`
    (027 :3608-3612; switch defaults at :3516-3523).
- **Scratch sizing:** `moe_bufs()` and `group_bytes()` + kV2CounterBytes are identical (021m prefill.cpp:1285 / 027
  :1473; moe_fused.cu:700-705 in both).

## 2. Upstream v0.2.1 → v0.2.7 (→ v0.2.8) in everything v2 depends on (task 2)

`git log v0.2.1..v0.2.7 -- src/prefill include/strata/prefill src/core/expert_cache*` lists 62 commits. What matters
for v2:

| Area | Upstream change | Effect on what v2 receives |
|---|---|---|
| moe_fused.cu: group(), tables(), tiles_at, group_bytes, act_bytes, quantize_act | **no change** (empty diff) | none |
| moe_fused.hpp: Batch, kMaxBatch, kTileRows | adds WideBatch / kBatchRoom (opt-in STRATA_PF_BATCH > 128) | none; Batch is unchanged |
| moe_fused_iq.hpp: NativeGeom, experts_native | adds `native_wide()` and the WideBatch overload | none unless NT/F16/WS is on |
| moe_fused_iq.cu (bdcc34df, 10c8cc62, c47c6994) | native_kernel templated on NT; opt-in NT=256, F16 mma, warp-specialized, Q2N; DevInfo gets occ_nt / ws / q2n | none on the default path; tables, H layout and the 32-value term (027 :791-792) match 021m :663-664 |
| copy events (a11f8b0a, f217b23b, #4005) | opt-in sparse copied events and wait dedupe | defaults unchanged (see section 1) |
| layer-major prefill (#3976) | default ON for a two-card CUDA *layer split*; STRATA_PREFILL_LAYER_MAJOR=0 and STRATA_DEFAULTS=026 pin it off | pinned off; it never calls `experts_native` (027 prefill.cpp:4336 is the only call) |
| KVA | ships off | none |
| expert_cache.cpp | Windows NVML free-VRAM query, NIBBLE seal | slot layout unchanged |
| ring staging | `stage_dev[i] = ring_base + i*MAXBLOB()` (021m :1668, 027 :1893) | unchanged |
| CPU share of prompt experts | `cpu_maybe = ... && !stream_all` (021m :3716, 027 :4365) | the share never runs on a chunk that takes the fused / v2 kernels (`fused_nat` requires `stream_all`, 027 :4241); STRATA_PREFILL_CPU_SHARE=0.4 cannot change v2's input, and the yardstick forces it to 0 anyway (quant_quality FIXED_ENV) |
| helper caches on the 4060 Ti (`--expert-cache-device1 3300`) | feed the prompt path only with STRATA_PREFILL_HELPER_SOURCE=1 (generate.cpp:9324-9336) | not set; the prompt walk streams the same experts through the 5080's ring |
| IQ3_XXS / IQ4_NL block layout | static_asserts on `sizeof(block_iq3_xxs)` / `block_iq4_nl` hold (v2 builds and its unit test passes) | none |
| v0.2.8 (9a398bd5) | GB10 / sm_121 tile choice in `pick_ww` | v2 does not use `pick_ww` |

No upstream change between v0.2.1 and v0.2.8 alters the tables, buffers, rows, weights or stream order that the v2
kernels get on our two-GPU configuration.

## 3. Findings, ranked by likelihood (task 3)

### F1 (most likely, about 85 %): no defect; two rounding-level steps judged as if they were one

Evidence, all from the existing logit files. Per-prompt KL is computed as in `kernel_rule2.py`: long40, full
vocabulary, KL(reference ‖ run).

**a) v2's own step is the same size on 0.2.7 as on the served build.** Each pair below differs only in v2.

| Pair (base → with v2) | top-1 | KL mean | median | p90 | rows > 1 |
|---|---|---|---|---|---|
| 0.2.1, one GPU, fork on: gap8 ref → v2 | 36/40 | 0.181 | 0.0118 | 0.359 | 2 |
| 0.2.1: ref → v2d (down only) | 36/40 | 0.402 | 0.0103 | 0.567 | 4 |
| 0.2.1: ref → v2g (gate/up only) | 33/40 | 0.385 | 0.0194 | 0.577 | 4 |
| 0.2.7, two GPUs, fork on: r27h-nov2 → r27h | 34/40 | 0.378 | 0.0078 | 0.359 | 3 |
| 0.2.7, two GPUs, fork off: r27h-noboth → r27h-nofork | 37/40 | 0.117 | 0.0086 | 0.211 | 2 |

The medians are no larger on 0.2.7. A real integration error would raise the median, because almost every prompt
would be hit: wrong rows, experts, scales or strides, or skipped work items. Here only a few chaotic tail rows move.

**b) Judged against its own build, v2 passes Karl's rule.** The bounds are gap 8's: top-1 ≥ 34, mean ≤ 0.4014,
p90 ≤ 0.3660, rows > 1 ≤ 4.
- v2 only on 0.2.7 (nofork vs noboth): 37 / 0.117 / 0.211 / 2 → **PASS**.
- v2's step with fork on (r27h vs nov2): 34 / 0.378 / 0.3585 / 3 → **PASS**.
- The build step alone (nov2 vs gap8 ref): 35 / 0.086 / 0.193 / 0 → PASS.
- Stacked (r27h vs gap8 ref): 33 / 0.585 / 0.890 / 3 → FAIL.

**c) The served build's own v2 fails today's rule too.** Under the p90 rule adopted after gap 8:
- gap 8's v2d run gives 0.402 / p90 0.567 → FAIL;
- gap 8's v2g run gives top-1 33 / p90 0.577 → FAIL;
- only the combined v2 run passed, at p90 0.3588 against a bound of 0.366.

v2 on 0.2.1 passed by a small margin, not by a wide one.

**d) The served build's v2 was never KL-tested in the port's form.** Gaps 7 and 8 ran v2 on the 5080 alone
(`CUDA_VISIBLE_DEVICES` = one card, no `--expert-cache-device1`). Every port run (gap 12-15) uses both cards with
`--expert-cache-device1 3300`. The served P021m config (configs/r21n-candpm.json) is also two-GPU with V2=1, but no
yardstick run exists for it. "Passed on the served build" is therefore a one-GPU, one-step result.

**e) The worst row is not corruption.** At tf-long40k-32768 (KL 10.22, 0.26 of the 0.585 mean):
- r27h puts p = 0.975 on token 52426 "coverage";
- the reference has entropy 7.7 nats and 0.17 on `<|im_end|>`;
- the source text reads `…lcov_branch_coverage=1 … '--branch-` and its **true next token is "coverage"**.

So r27h makes the correct copy prediction where the reference was confused. On the 36 cut prompts with a known next
token:

| Run | NLL of the true next token |
|---|---|
| r27h | 4.118 |
| gap 8 ref | 4.127 |
| rounding references and v2 runs | 3.90 to 4.38 |

**f) The other big row is a known chaotic prompt.** ldrsyn20k-7680 (KL 8.97) flips under every perturbation: unfused
2.46, cpushare 1.86, v2 3.13, 0.2.7 without either switch 4.15. The cpushare reference itself has a 9.76 confident flip
on tf-long28k-21504.

**g) The runs are deterministic.** gap 13 r27h and gap 14 r27h are byte-identical on 40 of 40 rows, and exact7 repeats
7/7. A race on v2's atomic counters or ring would show up as differences between runs.

### F2 (side finding, high confidence): check (2) follows GR_FORK, not v2

Speculation-off arms against their own probabilities (gap 13, gap 14):

| Arm | GR_FORK | V2 | p |
|---|---|---|---|
| r27t-hnospec (both on) | on | on | 0.006 |
| nov2 | on | off | 0.002 |
| nofork | off | on | 0.512 |
| noboth | off | off | 0.515 |

Dropping v2 does not fix check (2); GR_FORK's 0.2.7 port is the thing to look at there. The port moved the fork branch
ahead of 0.2.7's GR_V3 code in `fused_gr_read_multi`. That is a separate diagnosis.

### Ruled out (checked in code, not the cause)

- **Counter placement and scratch size.** `v2_counters()` (021m :1837, 027 :2368) puts two ints at the 16-aligned end
  of the tile list. `group_bytes()` reserves +64 for them (moe_fused.cu:704-705). `moe_bufs()` sizes `m.GU` from
  `group_bytes(T*K)` the same way in both trees.
- **Counter races.** Every `experts_native` call of a layer is issued on `m.cs` in order, and the zeroing memset sits on
  the same stream (027 :2564-2565). There is a single call site.
- **Copy and wait ordering.** Default `wait_copied` is unchanged (section 1).
- **Experts, rows and blobs per batch.** The same loop in both trees: streamed blobs come from `stage_dev`, resident
  ones from `cache->device_slot(host_res)`. The batch cut is unchanged at kMaxBatch with STRATA_PF_BATCH unset.
- **Weight geometry.** `NativeGeom` comes from the same `lay.fmt`, and `per16()` is false for IQ3_XXS and IQ4_NL.
- **The v2 setup per device.** `v2_occ()` sets the function attribute per device under `g_mu`; both cards meet
  99,856 bytes.
- **CPU share, helper caches, layer-major, KVA:** none reaches v2 (section 2).

### Latent hazards (not causes; worth a line in the port notes)

1. **WideBatch bypass.** With STRATA_PF_FUSED_NT=256, _F16 or _WS, `experts_native` returns before the v2 block (027
   :2538-2545). The start line (prefill.cpp:1426-1450) would still claim v2 takes 17 + 39 layers. `native_v2_takes()`
   or the start line should report v2 as off when `native_wide()`.
2. **Counter sharing.** v2's two counters live in the shared grouping scratch. If a later upstream release issues
   fused batches of one layer on two streams, the counters would race. That is not the case on 0.2.7 or 0.2.8.
3. **Layer-major prefill.** If it is ever enabled on a layer split (0.2.7's default there), v2 never runs on that path,
   so v2's prompt gain would silently disappear.

## 4. The fix (task 4)

### Option A (recommended): make v2 bit-identical to the current kernels

The commit message and the kernel comments (027 moe_fused_iq.cu:1230-1242) name **one** arithmetic difference.
Everything else is already the same:

- the int32 dots (same `mma32` from C = MAGIC);
- `d_w` (exact either way: half × (2s+1) × 0.25);
- `d_x`;
- the K order (32-value sub-blocks in sequence, one FP32 accumulator);
- SwiGLU: `gt / (1.0f + __expf(-gt)) * up` at 021m :694 vs :1057, and 027 :829 vs :1522;
- H's max (order-free), `__float2int_rn(h * 127/max)` and `max/127`;
- the down store.

The one difference is the term of each sub-block:

```
current (027 :791-792, 021m :663-664):  p = d_w * d_x;            acc = fma(p, D - MAGIC, acc)   // fma(round(d_w*d_x), dot, acc)
v2      (027 :1498-1501, 021m :1033-1036): acc = fma(fma(D, d_w, -MAGIC*d_w), d_x, acc)            // fma(round(dot*d_w), d_x, acc)
```

The diff below is the same in 027 and 028 (lines 1469, 1481, 1498-1501). In 021m the matching lines are 1004, 1016 and
1033-1036.

```diff
-                float dw[2][2], nm[2][2];
+                float dw[2][2];
 ...
                         dw[i][hh] = d;
-                        nm[i][hh] = -MAGICF * d;
 ...
-                            // D = 1.5 * 2^23 + dot (rows g, g + 8 x columns 2t, 2t + 1)
-                            ac[0] = __fmaf_rn(__fmaf_rn(__int_as_float(d[0]), dw[i][0], nm[i][0]), dx.x, ac[0]);
-                            ac[1] = __fmaf_rn(__fmaf_rn(__int_as_float(d[1]), dw[i][0], nm[i][0]), dx.y, ac[1]);
-                            ac[2] = __fmaf_rn(__fmaf_rn(__int_as_float(d[2]), dw[i][1], nm[i][1]), dx.x, ac[2]);
-                            ac[3] = __fmaf_rn(__fmaf_rn(__int_as_float(d[3]), dw[i][1], nm[i][1]), dx.y, ac[3]);
+                            // D = 1.5 * 2^23 + dot (rows g, g + 8 x columns 2t, 2t + 1).  native_kernel's term bit for
+                            // bit: acc = fma(round(d_w * d_x), dot, acc), dot = D - 1.5 * 2^23 (exact)
+                            ac[0] = __fmaf_rn(__fmul_rn(dw[i][0], dx.x), __fsub_rn(__int_as_float(d[0]), MAGICF), ac[0]);
+                            ac[1] = __fmaf_rn(__fmul_rn(dw[i][0], dx.y), __fsub_rn(__int_as_float(d[1]), MAGICF), ac[1]);
+                            ac[2] = __fmaf_rn(__fmul_rn(dw[i][1], dx.x), __fsub_rn(__int_as_float(d[2]), MAGICF), ac[2]);
+                            ac[3] = __fmaf_rn(__fmul_rn(dw[i][1], dx.y), __fsub_rn(__int_as_float(d[3]), MAGICF), ac[3]);
```

Notes on the diff:

- Rows and columns line up with the old kernel's `q`: `d[0]` / `d[1]` are row g, `d[2]` / `d[3]` are row g + 8, and
  `.x` / `.y` are columns 2t and 2t + 1. The old kernel's `wa0 * dx` is one rounded multiply, and `D - MAGIC` is exact
  for |dot| < 2^22.
- The explicit `_rn` intrinsics stop the compiler from contracting anything differently.
- Also update the comment at :1230-1236 ("the one place the results differ" no longer applies) and the commit text.

**Cost:** 3 FP32 operations per output per 32 values instead of 2, which is exactly what Basalt removed. v2's other
gains are on the memory side and stay: raw cp.async rows, decode into the mma fragments, a warp per 32 rows × 128
routed rows, the atomic item queue, and the L2 prefetch. How much speed is left has to be measured. As a reference,
gap 14 shows v2 worth about 4.5-5 % of long-prompt TTFT (r27h vs noboth). GR_FORK's code is only in verify.cpp, mtp.cpp
and fused_gr.cu, not in src/prefill, so it touches at most the prompt's tail windows. That is also how it moves the
yardstick's last-position logits.

| Workload | r27h (s) | noboth (s) |
|---|---|---|
| W3 26.7K | 6.05 / 6.04 | 6.34 / 6.33 |
| R1 20K | 5.55 / 5.54 | 5.80 / 5.81 |
| R2 54K | 12.08 / 12.08 | 12.67 / 12.69 |
| R4 33K | 7.84 / 7.85 | 8.22 / 8.21 |

The cleanest delivery is to make this the only v2 term. A keep-Basalt's-order sub-switch, such as STRATA_PREFILL_V2_FAST=1
for A/B, is optional.

### Option B (no code change): change how the switch is judged (Karl's call)

- Judge a prompt-arithmetic switch against **its own build with the switch off**: r27h vs r27h-nov2 already passes
  (section 3, b).
- Pool long40 + long80b (120 prompts), as gap 9 did for IMMA, so that two chaotic rows cannot decide mean and p90.
- Calibrate the reference spread on the same build and GPU form.

This keeps a rounding-level v2, and the next rounding-level switch will hit the same stacking problem.

## 5. Test plan

1. **Unit, tighter.** In prefill_fused_iq_test part 3 (tests/cuda/prefill_fused_iq_test.cpp:485-620, run with `--v2`),
   require `h1.moved == 0`, `h1.bitwise`, and `memcmp(r1.y, r0.y, db) == 0` for modes 1, 2 and 3. The `HDiff.bitwise`
   field already exists (:568-588). Keep parts 1-2's timing to price the change: v2-exact vs v2 vs current kernels at
   2048 / 3584 / 8192 tokens.
2. **Engine exactness, the deciding gate.** exact7 on the rebuilt port: v2-exact vs r27h-nov2 (or r28h with only
   GR_FORK off) at matched slots, pin 2500. It must be **7/7 identical**, the gate STRATA_DEQUANT_WIDE passed in gap 8.
   Run it twice for the repeat gate.
3. **KL check.** Yes, it shows the fix, trivially:
   - pf_yardstick long40 with V2=1 must give logit files **byte-identical** to the V2=0 arm (40/40, `cmp`);
   - the kernel_rule2 verdict vs gap 8's reference then equals the V2=0 arm's (fork on: 0.086 PASS; fork off: 0.132
     PASS).
   - If even one row differs, the kernels are not exact; part 3 should already have caught it.
4. **Check (2).** Not needed for v2-exact, which is byte-identical on the prompt path and absent on decode. It stays
   needed for GR_FORK, which is what fails it (F2).
5. **Speed.** The usual screen (P021m test form vs port), v2-exact vs V2=0, 2 passes in turned order, reading prompt
   TTFT on W3 / R1 / R2 / R4. This is the number to report to Karl.
6. **Optional, only if Option B is chosen instead:**
   - pf_yardstick long40 + long80b on r27h vs r27h-nov2;
   - one long40 run of the served P021m in its two-GPU form (r21n-candpm with V2=1 and with V2=0), to close the gap
     in F1 d.

## 6. Confidence

- **No integration defect; the FAIL is stacking, a cross-build reference and chaotic rows: about 85 %.** The code
  path is byte-identical. v2's pairwise step is unchanged or smaller, the runs are deterministic, the worst row is a
  correct prediction, and quality on the true next token is unchanged. What keeps this short of 95 %: I did not run
  anything. A defect that only touches a few long-prompt rows, and whose size happens to match v2's normal rounding
  spread, cannot be excluded from the files alone. Test 2 above settles it either way.
- **Option A makes v2 bit-identical to the current kernels: about 90 %.** The term is the only arithmetic difference
  documented, and reading both kernels confirms it. The residual risk is an unnoticed difference elsewhere, such as
  an accumulator start value or a compiler contraction. Part 3, tightened, would show it at once.
- **The speed cost of Option A:** unknown. Expect a part of v2's 4.5-5 % long-prompt gain to remain; measure it.

## Appendix: how the numbers were made

The per-prompt KL is `sum p_ref (log p_ref − log p_run)` over the full vocabulary, the same as kernel_rule2.py.
Rule bounds come from gap 8's references: unfused 35 / 0.162 / p90 0.366 / 3, cpushare 35 / 0.365 / 0.215 / 3.
Files used:

- results/r22/gap8/pfy/{ref,unfused,cpushare,v2,v2d,v2g}
- results/r22/gap12/pfy/r27a (byte-identical to gap14 r27h-noboth and to gap15 r28h)
- results/r22/gap13/pfy/r27h
- results/r22/gap14/pfy/{r27h,r27h-nov2,r27h-nofork,r27h-noboth}

The true next tokens come from bringup/out/r20a/prompts with LONG40's cuts (pf_yardstick.py). The token text comes
from bringup/out/r20a/pack/tokenizer/vocab.json.
