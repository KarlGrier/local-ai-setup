# Gate plan: the r23 exact decode items (11-04, written before any build or run)

Written by a helper; saved by Claude (the helper's .md write was refused).

- **Branch:** `r23-decode-exact` in worktree `strata-r23decode` = r22-port0210 (fdd2fffa8) + 2 commits, each behind its
  own switch, both off by default:
  - **L** (a52788161): `STRATA_REMOTE_LATE_LAUNCH=1` - the helper GPU's staging and launches run after the CPU pool's
    batch is published. Two cards only; nothing on one card.
  - **O** (c4c15d32c): `STRATA_POOL_ONE_BATCH=1` - a layer's gate/up rows and down rows go out as one pool batch.
- **Exactness:** both are scheduling-only (same calls, same bytes, same reductions) -> output must be bit-identical.
- **Measurement only:** nothing gets served or switched.
- **Baseline:** gap 17 found the port's baseline 2.4 % slower than P028x on Basalt's struct fixture, so every arm is
  compared with **the same r23 build with both switches off (B)**.
- **Arm configs** (in `results/r23/decode-timing/gate-configs/`, from `configs/P0210x-h.json`, exe
  `engine-r23decode/strata`; not in `configs/` - copy them if the gap driver expects that): r23-B / r23-L / r23-O / r23-LO
  (both cards); r23-Bs / r23-Os (the 5080 alone: no `--expert-cache-device1`, STRATA_ROUTE_TAIL_SKIP=0); r23-Bt /
  r23-LOt / r23-Bst / r23-Ost (the same + STRATA_DECODE_TIMING=1).

## 1. Build (in a gap with nothing else running; CPU only, 8080 down, ~15-20 min)

As `b17` in `work/r22/gap17.sh`, with tests ON:

```
cmake -G Ninja -S strata-r23decode -B strata-r23decode/build -DCMAKE_BUILD_TYPE=Release -DSTRATA_ENABLE_CUDA=ON -DSTRATA_BUILD_TESTS=ON "-DCMAKE_CUDA_ARCHITECTURES=89;120" -DCMAKE_CUDA_COMPILER=/usr/local/cuda-13.3/bin/nvcc -DSTRATA_GGML_DIR=<pinned llama.cpp>
cmake --build ... --target strata pool_tasks_test pool_test pool_stress numa_pool_test patch_guard_test -j 16
```

- **Install:** copy the binary to `engine-r23decode/strata`; write `SOURCE` (branch, HEAD, `v0.2.10..HEAD` = 30) and
  `SHA256`.
- **The build must confirm:** remote_experts `claim()` and `launch()` compile and `begin()` is just
  `claim() && launch()`; the local `LateLaunch` struct in `expert_source.cpp` compiles incl. its static `run` member;
  pool.hpp's aligned `ObExpert` / `ExitStamp` arrays compile; `generate.cpp` sees `drive.d.pool` and `copy_before` at the
  print sites; no new warnings under the tree's flags.
- **Not checkable here:** the HIP build compiles the same `pool.cpp`, `expert_source.cpp`, `remote_experts.cpp` (no HIP
  toolchain here; the edits use no new CUDA API). SYCL has its own copies, untouched.

## 2. Tests (CPU, ~10 min)

- **`pool_tasks_test`** - every part must pass, incl. the new ones: the publish hook (runs once, on the calling thread,
  rows bitwise the same); one batch per layer (`STRATA_POOL_ONE_BATCH`): bitwise equal to the two-phase reference for
  workers 1/3, host on/off, tasks 0/1/41/128/4096, then with sleeping workers (SPIN_US=0, 50 repeats), then with the
  switch read from the environment. Run with no arguments (synthetic Q4_0), then once per type pair of our pack:
  `pool_tasks_test GU DOWN BLOB` for IQ2_S/IQ4_NL, IQ2_S/Q2_0, IQ3_S/IQ4_NL, IQ3_S/Q2_0, IQ3_XXS/IQ4_NL, IQ3_XXS/Q2_0,
  IQ4_XS/IQ4_NL - one real blob per pair cut from the pack (covers the Q2_0 down path and the gate/up kernels that ship).
  A Q2_0 gate/up pack (the SwiGLU copy in `ob_gu_rows`) does not occur in our pack: covered by reading only.
- **Other suites:** `pool_test --selftest`, `numa_pool_test`, `pool_stress 20` twice (nothing set; then
  `STRATA_POOL_ONE_BATCH=1` - pool_stress only exercises run/run_split, a smoke test there).
- **Gap 17's serve tests** (servetests, patch_guard_test), unchanged.

## 3. GPU steps (pin 2500 for exact7; the screen harness of gaps 17/18)

### 3.1 exact7: 7/7 identical with the slots MATCHED in every row (~3.3 min each)

| label | config + ENVX | REF | proves |
|---|---|---|---|
| r23-B | r23-B.json | g17-p210a | the switches-off build = the port (and so P028x) bit for bit |
| r23-B2 | r23-B.json | r23-B | the base repeats itself |
| r23-L | r23-B.json, ENVX=STRATA_REMOTE_LATE_LAUNCH=1 | r23-B | item L (two cards: the CLI loads the helper, so the item's path runs) |
| r23-O | r23-B.json, ENVX=STRATA_POOL_ONE_BATCH=1 | r23-B | item O on two cards (decode and the prompt CPU share) |
| r23-LO | both | r23-B | both together |
| r23-Bs | r23-Bs.json | (its own base) | the solo base |
| r23-Os | r23-Bs.json, ENVX=STRATA_POOL_ONE_BATCH=1 | r23-Bs | item O on one card |

- Each row: `PIN_CACHE=2500 REF=<REF> ENVX="<ENVX>" bringup/lib/exact7.sh <label> <config>` (as gap 18's `e7`); covers the
  greedy and seed-11 sampled math / code items and p2000 / 32K / 112K.
- **Why exact7 carries the bitwise claim:** the exact7 CLI has no PcieAuto. In serve mode PcieAuto re-derives the PCIe
  share from the pool's measured speed (`generate.cpp`), so a faster pool (item O) can settle on a lower `pcie_frac` ->
  a placement change, rounding-level, between served arms that does not come from the item itself. Record each served
  arm's settled share (its "PCIe share:" lines).

### 3.2 Bit-identical logits: `pf_yardstick long40` (~9 min each)

r23-B and r23-LO, compared with `ndiff`: 0 of 40 first-token logit files differ between B and LO, and between B and gap
17's P0210x-h yardstick. Covers the prompt path (item O also reschedules the prompt CPU share) and the first decode window.

### 3.3 Timing arms: one screen pass each (~4 min each, 16 min in total)

r23-Bt and r23-LOt (both cards), r23-Bst and r23-Ost (solo), read with `t2_report.py`. If the mechanisms work:
- **L:** the per-layer host time drops by >= ~0.3 ms / window from Bt to LOt at a similar CPU-expert count per
  layer-window; "staging+launching" stays ~0.55 ms / window; "waiting for it" (the host waiting on the helper) rises by
  <= ~0.1 ms.
- **O:** Bt's / Bst's "gate/up phases" idle thread-ms / thread count + the host's quantization time = the measured upper
  bound for O; LOt's / Ost's "one-batch" idle and "waiting" show what remains.
- **H2:** the "CUDA1 rows copied by the host" line decides whether H2 is worth writing (>= 0.15 ms / window).

### 3.4 The 9-workload screen: 3 passes, a different order each pass (~4 min per arm-pass)

- Arms B, L, O, LO (two cards) + Bs, Os (one card). Order: pass 1 `B L O LO Bs Os`, pass 2 `Os Bs LO O L B`, pass 3
  `O B Os LO Bs L`. Harness `darm` as gaps 17/18 (warm-up, W1-W3, agent x2, research4 x4); each arm's engine environment
  checked first; the switch's start line must be present - `strata: the helper GPUs' staging and launches follow the CPU
  pool's publish (STRATA_REMOTE_LATE_LAUNCH=1)`, `strata cpu pool: a layer's gate/up and down rows in one batch, no
  barrier between them (STRATA_POOL_ONE_BATCH=1)` - and both absent in B and Bs.
- **No-loss (Karl 11-03, as g17_rules.py):** per workload, decode and prompt tok/s each: the arm's pass mean >= the base's
  x (1 - the larger of the two arms' pass-to-pass spreads for that workload); overall geomean decode and prompt >= the
  base's minus the noise.
- **GAIN:** the decode geomean above the base by more than max(noise, 1 %).

### 3.5 Basalt's bp90 fixtures, cold, 3 passes (~11 min per arm)

B and LO with `bprun`'s community-1 set (as gap 17 A6): conv / struct / prose decode, pp16k, pp64k. LO must not fall below
B by more than B's pass spread on any of them.

### 3.6 Distribution checks (1) and (2): not required

Neither item touches the draft chain (`mtp.cpp`, the sampler, the draft-length rules unchanged) and exact7's sampled items
are bitwise. If Karl wants them anyway: build a MEASUREMENT twin (`r23-decode-exact` + the 5 MEASUREMENT commits of
`r22-port0210-meas`) and run gap 17's B2 (`chk2arm`, arith-j3 T 0.6, 4,000 samples, speculation off) and B3 (`essarm`)
with LO's env - ~2.2 h, as gap 17 part b.

## 4. GPU time

| step | minutes |
|---|---|
| exact7 (7 runs) | ~23 |
| pf_yardstick (2 runs) | ~18 |
| timing arms (4) | ~16 |
| screen (18 arm-passes) | ~72 |
| bp90 (2 arms x 3 passes) | ~22 |
| **total GPU** | **~151 (~2.5 h)** |
| build + tests, with 8080 down | +~30 |

Two gaps: **(a)** build, tests, exact7, pf_yardstick, timing arms (~1.5 h); **(b)** the screen and bp90 (~1.6 h).

## 5. Expected gain per item (decode, the served two-card form unless marked)

| item | upper bound | likely | source |
|---|---|---|---|
| L | +2.5 % (0.55 ms of 22.34 ms / window) | +1.1-2.0 % (0.25-0.45 ms) | gap 18 B arm: 0.55 ms / window staging+launching; 10-21 trace: CPU long pole in 69 % of layers, the helper in 20 % (those lose ~2 us each) |
| O, one card | +3.5 % (~0.85 ms) | +0.8-1.5 % (0.19-0.38 ms) | the fixed part of P021's gate/up phase (21.6 us / layer) on the 79 % CPU-bound layers; to be confirmed by 3.3 |
| O, two cards | +3.4 % (~0.75 ms) | +0.6-1.2 % (0.13-0.27 ms) | the same, at 69 % |
| L + O, two cards | ~+6 % | +1.7-3.2 % | the sum (they barely interact) |

- **Prompt speed:** ~0 for both (L does not touch the prompt path; O reschedules the prompt CPU share, but its batches are
  large, so the barrier is a small share).
- **The screen's decode noise has been 2.6-5.6 % per arm** (gaps 17/18): a single item can come out "PASS, no measured
  gain" even when 3.3 shows its mechanism working. **Karl decides** whether a mechanism-level result + no loss is enough,
  or L+O must clear max(noise, 1 %).

## 6. Decision per item

- **EXACT:** every step-2 test passes; its exact7 rows and LO's 7/7 MATCHED; r23-B 7/7 vs g17-p210a and r23-B2 7/7 vs
  r23-B; pf_yardstick 0 of 40 differ.
- **PASS** = EXACT + no loss on the screen (per workload and geomean) + no loss on bp90 for LO.
- **GAIN** = PASS + the decode geomean above B by more than max(noise, 1 %).
- **Anything else = FAIL / NOT DECIDED** (e.g. a fatal-GPU or engine-restart line in an arm's log - gap 17's `fatalchk` -,
  a missing start line, a kernel-check failure, which stops the gap and leaves it open).

## 7. Overlap and what is not in this gate

- **Overlap with `strata-r23basalt`** (branch r23-basalt-prompt, `src/prefill/prefill.cpp` only): no shared files, but
  `STRATA_POOL_ONE_BATCH` also reschedules the prompt CPU share's `run_split_multi_native` call (`prefill.cpp` ~5023),
  whose batches PF_TAIL_SPLIT / PF_FIRST_CHUNK change -> a combined build needs its own exact7; its prompt items are
  rounding-level and keep their own KL gate.
- **Not in this gate:** H2 (decided by 3.3's copy counter), P1 (decided by the two-card timing pass, ANALYSIS section 7),
  G5a (needs a probe), G4 and G6 (rejected, ANALYSIS section 5).
