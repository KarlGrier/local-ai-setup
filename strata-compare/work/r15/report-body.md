### Before the first test

* **48-hour monitor stopped** (logs/r14/uptime-c14/): 02:59 → 07:29, 19 samples, health ok 19/19, idle 19/19, **no requests
  of yours** (the 3 counted are the rollback test's), engine RSS 51,813 MiB flat, MemAvailable 35.4–36.1 GiB, swap 0,
  5080 506 MiB / 4060 Ti 1,231 MiB free throughout.
* **Base = v0.1.40.2** (e8ca9afd, tree af123e17; 242 commits after v0.1.40.1). **The release alone with your flags computes
  what v0.1.40.1 computed: exact7 7/7 identical to v0.1.40.1's stock**, repeats itself 7/7, server tests OK.

### The port (the runbook's ledger pass) — 34 → 27 commits

| row(s) | outcome on v0.1.40.2 |
|---|---|
| 1, 5, 8, 33 | conflicts resolved by hand. **Row 8 (our exact sampling) sits beside upstream's new STRATA_SPEC_PROB** (probabilistic draft acceptance, opt-in): both paths kept, ours wins when both are set (upstream's q buffer is not allocated then); sampler.cu = upstream's file + our two pure-addition blocks |
| 9 (side mixer) | **re-ported onto upstream's new opt-in mixer branches (STRATA_DF_BRANCH, PR #904)**: our branches run v0.1.40.2's own steps with a stream parameter (#1188's K8V4 host copy, the copy-kernel q/gate split, the fused norm + RoPE); DF_BRANCH is off while ours is on; switch off = v0.1.40.2's launch order |
| 16–20, 34 (B.3) | **not ported: upstream's F4 (ffac97f7) is the same fork code** (Eddoursul 738e166 + b67a291), on by default, with the same function names and the same switch name STRATA_MMVQ_IL; it covers IQ4_XS / Q4_K / Q5_K / Q6_K at 2–4 tokens — every dense format of IQ3_S, and --spec 4 never makes a window of 5. Ours added 5–8 columns and IQ3_S / Q8_0 types. The B.3 guard goes with it (it would have set STRATA_MMVQ_IL=0 = F4 off) |
| 28 (#583) | dropped: upstream carries #954's backstop and the fused-layout fix |
| 30 | EMPTY: upstream ccfdc2eb is the same change |
| the rest | applied unchanged |

**Gates of the 27-commit series on IQ3_S (runbook r15, clean clone): patched with every switch off = the release 7/7;
`strata patch guards: 5 checked, 0 off`; server tests OK; every switch gate PASS** — B.2 TF −0.0008 / −0.0006, exact
sampling chi-square ALL PASS, side mixer pair identical, A.2 pair identical, B.1 TF +0.0008 / −0.0026 (bound 0.005),
cost gate chi-square ALL PASS (Round 14's values to the digit).

### Files (inspector on 16 MB of each shard's header first)

| file | routed experts | bpw (experts) | vs IQ3_S per expert read | n-gram table | the rest | verdict |
|---|---|---|---|---|---|---|
| IQ3_S (served) | 46.84 GiB | 3.3 | 1.00× | 26.82 GiB (IQ4_NL) | 4.20 GiB | RUNS |
| **unsloth UD-Q5_K_XL** (stands for IQ3_XXS at 300B, target 89 GiB) | **91.61 GiB** | 6.5 | 1.96× | 50.66 GiB (Q8_0) | 5.13 GiB | RUNS with -DSTRATA_Q6K_EXPERTS=ON (+K-quant prompt kernels) — **but does not load** (below) |
| **unsloth Q8_0** (stands for IQ3_S at 300B, target 113 GiB) | **119.53 GiB** | 8.5 | 2.55× | 50.66 GiB (Q8_0) | 5.09 GiB | RUNS |
| also checked | UD-Q6_K_XL 101.75, bartowski Q6_K ≈ 101, bartowski Q5_K_L ≈ 85.5, bartowski Q8_0 = unsloth's; ggml-org Q8_0 needs upstream (Q4_0 n-gram table) | | | | | |

Downloads: 291 GB (UD-Q5_K_XL's shards 2 and 3 are Q8_0's LFS blobs → hard links) in 42 min, 10 / 10 SHA-256 OK.
**UD-Q5_K_XL does not load:** its shard 1 (metadata only) is 10,946,618 bytes, 6 bytes short of the 32-byte-aligned data
section Strata's GGUF reader computes ("data section starts past EOF"); Q8_0's shard 1 is aligned and loads. Your order:
no build option applies → **2. the splice: its 144 routed-expert tensors + every other tensor from IQ3_S**
(work/r15/splice.py, 122.6 GiB, written in 118 s) — so on this file the n-gram table and dense weights are IQ3_S's.

### Step 1 — fit plans at your 6 GB margin (bringup/placements.py; results/r15/step1-plan.md)

Placements v0.1.40.2 allows for a file whose experts do not fit in RAM: **A** both GPUs, the helper cache +
`--mmap-experts`; **B** the 5080 + `--resident-budget-gib` (a budget is still refused beside a helper cache); **C** a layer
split over both cards + the budget (#642 / #848; **the engine takes a split only with `--serve`**); **D** the 5080 +
`--peer-device 1` (the 4060 Ti as an adaptive expert tier) + the budget — **not refused, new to this PC**; **E**
`--resident-experts` (setup's low-RAM mode). Predicted experts from the SSD at the floor (budget 72 GiB, desktop and
services assumed 10 GiB): UD-Q5_K_XL / its splice A 0.7 / 0.0, B 11.6 / 10.5, C 4.8 / 3.8, D 4.9 / 3.9, E 7.6 / 6.5 GiB;
Q8_0 A 28.7, B 39.5, C 32.8, D 32.9, E 35.5 GiB. 5080 slots: planner 1,588 (Q8_0, one GPU) vs 1,589 measured (+0.1 %),
2,355 (splice) vs 2,333 (−0.9 %); the 4060 Ti (no desktop on it) has 7.51 GiB free, not the planner's 7.25.

### Step 2 — the runbook on each stand-in (5080 + 64 GiB budget, 2 GiB chat cache, your 6 GB floor)

| | Q8_0 | UD-Q5 splice |
|---|---|---|
| clone / inspect / pack / build | 27 + 4 commits clean; RUNS; pack 1.4 GB (compat-BF16); 3 min | 27 + 4 clean; RUNS (-DSTRATA_Q6K_EXPERTS=ON + K-quant); pack 1.5 GB; 3 min |
| stock: all 7 outputs / repeats itself | yes / **3 of 7** → not repeatable | yes / **4 of 7** → not repeatable |
| patched, every switch off | 3/7 = stock; **repeat gate PASS**; guards 5 checked, 0 off | 5/7 = stock; **repeat gate PASS**; 5 / 0 |
| switch gates (TF bound 0.005 nats, chi-square) | **ALL PASS**: TF noise −0.0009 / +0.0003; B.2 −0.0009 / +0.0032; exact sampling, cost gate chi-square; side mixer 0.0000 / +0.0005; A.2 +0.0004 / +0.0001; B.1 −0.0005 / +0.0028 | **ALL PASS**: 0 / 0; −0.0003 / −0.0033; chi-square ×2; 0.0000 / −0.0001; +0.0005 / −0.0004; +0.0001 / −0.0018 |
| served decode screen (your settings) | 10.2 tok/s, 230 ms/round, 2.36 tokens/round, acceptance 0.681, TTFT 32K 83 s | 27.4 tok/s, 87 ms/round, 2.39, 0.675, 27.7 s |
| calibration (30-min bound) | reserve 713: +1.8 % (keep 813); KV 16K: −0.9 % decode, TTFT 32K −13.8 % (keep; step 5) | reserve 713: **+10.4 %** (one sample; step 5); KV 16K +0.3 %; chunk 32K +4.9 % decode, TTFT +6.4 % (keep 16K) |
| runbook stage time | 3 h 15 min (two invocations) | 2 h 6 min |

### Step 3 — every placement (probes; full sets on the best, on B, on the runner-up within 10 %)

Your rules: warm first; two consecutive probes whose decode agrees within 3 % (the output's first difference is reported,
not gating — with the adaptive tier live, two greedy probes of an unchanged build split at tokens 97–279). CLI probes
for A, B, D, E; the layer split (C) only through the server, so the top placements were probed again through the
server too (the served numbers sit 19–48 % above the CLI's: the server renders the prompt; only served numbers are
compared with each other).

| placement (64 GiB budget, buffered by the engine's rule) | Q8_0 CLI | Q8_0 served | splice CLI | splice served |
|---|---|---|---|---|
| A both GPUs, helper + page cache | 12.98 | **15.45** | 24.55 | – |
| B 5080 + budget | 10.82 | 11.10 | 30.95 | **45.95** |
| C split (Q8_0: K=47 forced, reserves 1,613 / 1,213 MiB) | – | 11.50 (32K read **783 s**) | – | 44.6 |
| D 5080 + peer tier + budget | 11.36 | – | 31.42 | 35.6 |
| E --resident-experts | **stopped by your floor**: the engine sized its copy at 76.9 GiB (Q8_0) / 77.4 GiB (splice) with 8 GiB headroom → MemAvailable 5.7–6.0 GiB | | | |

Q8_0's C did not start with the split the engine chose (auto put too much on the 4060 Ti: "verify: the device arena
(114 MiB) does not fit", 55 MiB free), nor at K=47 with the default reserve (the 5080 at 4 MiB), and the 300 MiB floor
stopped it at 1,213 MiB; it ran at 1,613.

### Step 4 — file-tier options (each alone, A B B A, CLI greedy 1,024 tokens, cold page cache; keep at >= +3 %)

| option | Q8_0 A (no budget) | Q8_0 B | splice B |
|---|---|---|---|
| **unbuffered reads forced** (`STRATA_UNBUFFERED_LOAD=1`; the 0.1.40.2 rule chose the file cache here) | – (not honoured without a budget) | **+47.7 %** | **+15.2 %** |
| buffered forced (`=0`, what the rule chose) | – | +0.8 % | −8.3 % |
| `STRATA_IO_PREFETCH=1` | **+4.2 %** (base arms' spread 4.5 %) | −8.7 % | +12.5 % (spread 39 %; not available with unbuffered reads) |
| #699 read-ahead | closed (not merged) on 10-06 → skipped (your condition); its idea is a v0.1.40 default | | |
| I/O threads (`STRATA_FETCH_THREADS` 8 → 16; `STRATA_IO_THREADS` = 64 in your config acts on unbuffered reads) | −8.7 % | −1.0 % | +0.9 % |
| budget 56 GiB (vs 64), buffered | – | +19.4 % | −16.1 % |
| budget 74 GiB, buffered | – | −19.3 % | **+21.5 %** |
| **budget 74 GiB with unbuffered reads** (the combination) | – | **+27.5 %** (19.85 tok/s) | **+33.2 %** (49.0) |
| budget 56 GiB with unbuffered reads | – | −16.5 % | −18.0 % |

**The file tier's buffered path is the slow part on this PC:** on Q8_0 B reading the experts outside RAM took 360–436 ms a
round through the page cache, 100–106 ms with direct reads (64 I/O threads, PCIe 5 SSD). With buffered reads a bigger copy
squeezes the page cache (at 74 GiB half the misses went to the drive), so the budget sizes only rank right once the
reads are unbuffered. **Re-probes at 74 GiB + unbuffered (served):** Q8_0 D 23.8, B 21.1 (32K read 18.4 s, was 72.8), C 21.1
(32K 228 s), A + prefetch 12.25; the splice C 57.95, B 52.25 (32K 11.2 s), D 51.0. Full sets: Q8_0 D + B, the splice C + B.
**74 GiB did not hold your floor over a full run:** Q8_0 D stopped at 129 s (74), 317 s (73), 722 s (72) as parked
conversations and prompt checkpoints filled RAM → 71 GiB for Q8_0, 72 for the splice (stepping down on a stop).

### Step 3 — full sets (served, your sampling; each at the largest budget that held your floor over a full run, unbuffered reads)

| | Q8_0 **D** (5080 + 4060 Ti peer tier, 71 GiB) | Q8_0 B (5080, 71 GiB) | splice **B** (5080, 72 GiB) | splice C (layer split, 72 GiB) |
|---|---|---|---|---|
| decode screen items tok/s (ms/round) | **18.1** (125) | 15.9 (142) | 40.1 (58.5) | **45.2** (51.6) |
| LDR screen tok/s (ms/round) | **14.0** (179) | 12.1 (203) | 33.3 (73.8) | **41.4** (60.0; re-run 10-08, the first run's answers were degenerate, below) |
| acceptance (decode / LDR) | 0.662 / 0.696 | 0.657 / 0.691 | 0.671 / 0.690 | 0.668 / 0.694 |
| expert lookups: 5080 / 4060 Ti / CPU | 42 / 28 / 30 % (decode); 36 / 25 / 40 % (LDR) | 54 / 0 / 46 %; 44 / 0 / 56 % | 63 / 0 / 38 %; 53 / 0 / 47 % | 68 / 0 / 33 % (decode) |
| drive per round (GiB, decode / LDR) | 0.41 / 0.69 | 0.53 / 0.88 | 0.09 / 0.15 | 0.06 / 0.13 |
| time to first token 8K / 32K / 64K / 120K (s) | 6.5 / 19.4 / 31.3 / 50.4 | 6.5 / 19.3 / 31.3 / 50.7 | **5.1 / 12.4 / 20.6 / 39.4** | 16.5 / 63.8 / 127.0 / 237.1 |
| decode right after them (tok/s) | 21–23 | 21–24 | 43–46 | 45–48 (120K: degenerate) |
| needle 120K | **6/6** | **6/6** | **6/6** | **0/6** in the full set; 6/6 in the re-run and in 8 fresh sessions |
| min MemAvailable / 5080 free / swap | 6.0 GiB / ≥ 406 MiB / flat | 6.7 / 406 / flat | **5.7** (one 0.2-s sample) / 408 / flat | 7.9 / 410 / flat |
| SSD max temperature, read in the session | 58 °C, 13.4 TB | 61 °C, 17.2 TB | 57 °C, 3.0 TB | 59 °C, 3.6 TB |
| failures | the 64K prompt hung once at 73 GiB (1 of 2 runs; the watchdog restarted the engine) | – | – | **broken output from a long prompt on** (below) |

**Where the decode time goes** (CLI --stats, greedy 1,024 tokens, warm): Q8_0 D 140 ms/round = GPU ~22 + CPU pool ~118
(the file tier's reading ~82 ms, 537 MB/round); Q8_0 B 127 = GPU ~20 + RAM experts ~38 + reading ~68 (446 MB); splice B
56 = GPU ~16 + RAM experts ~25 + reading ~14.5 (80 MB). Served windows: Q8_0 D 167 ms = the GPU's reach wait 8 + the
per-layer host 126 + draft 2; splice C 47 ms = reach wait 8 + host 27 + draft 3.

**Where the prompt read goes** (your addition for the 6-bit file; STRATA_PREFILL_TIMING, results/r15/s3-prompt-split-q5s-*.md):

| prompt | splice C: read | C's 5080 stage (critical path) | of it: expert uploads / dequant / expert GEMMs / attention+GDN+other / grouping + KV | C's 4060 Ti stage (overlapped) | link (hand-off copies) | drive during the read | splice B: read (uploads) | B: drive |
|---|---|---|---|---|---|---|---|---|
| 8K | 14.6 s | 13.8 | 54 % / 5 / 4 / 15 / 22 | 2.9 s busy | ≤ 0.1 s | 76 GB, 4.6 GB/s | 4.2 s (23 %) | 10 GB |
| 32K | 63.7 | 62.7 | 50 % / 19 / 12 / 12 / 7 | 13.5 | ≤ 0.3 | 329 GB, 5.1 GB/s | 12.2 (6 %) | 33 GB |
| 64K | 126.7 | 125.7 | 50 % / 18 / 12 / 13 / 7 | 26.1 | ≤ 0.6 | 683 GB, 5.4 GB/s | 20.3 (9 %) | 70 GB |
| 120K | 236.8 | 236.0 | 49 % / 16 / 10 / 14 / 10 | 48.3 | ≤ 1.4 | 1,275 GB, 5.4 GB/s | 38.7 (11 %) | 155 GB |

C's prompt chunk is **1,024 tokens**: the 8 GB 4060 Ti has room for 431 expert slots and a 16K chunk would borrow all of
them, so the engine sizes the chunk to what every stage can lend (its #448 warning). With 1,024-token chunks the 5080
re-reads every expert outside the RAM budget from the drive on every chunk — 1.28 TB for a 120K prompt — and waits on
those uploads half the time. The 4060 Ti stage (layer 47 + the head) is busy ~20 % of the read beside it; the link is < 1 %.

**C breaks on long prompts.** Both 120K requests answered with degenerate output (256 tokens of 255 characters, every draft
accepted, every expert lookup a VRAM hit: the router picks the same experts each token; stopped at 256 tokens) → needle
0/6. From then on, every request of that server with a prompt over ~2.5K tokens (more than one chunk) answered the same
way (10 of 12 LDR requests); prompts under ~200 tokens stayed normal, and the 8K–64K prompts before it were fine. So
that session's LDR figure was invalid (its decode-screen figure and prompt times stand); C's LDR screen and needle were
run again on 10-08 (41.4 tok/s, 6/6). **Not reproduced in 8 fresh sessions** (results/r15/c120diag.md): ours fresh, ours
without STRATA_QSA_SPLIT_ATTN, ours as configured, stock fresh, ours and stock in the full set's order with and without
the timing switches, and the full set's exact config and order (its 120K speed prompt included) — all normal, needle
6/6. Intermittent, cause unknown; nothing ties it to our patches, but stock never ran in the failing session's
conditions either. The saved C config caps the context at 64K as a precaution.

### Step 5 — settings on the best placement (each alone, A B B A, keep at >= +3 %; 2 hours at most per file)

**Q8_0, placement D (CLI, your sampling, seed 11, 1,024 tokens, cold page cache; 22:50–23:41 + a re-check of the two keeps inside the noise and of them together, 01:46–02:03: 68 min)**

| setting | base → option tok/s | change | base arms' spread | kept |
|---|---|---|---|---|
| draft length 3 (vs 4) | 18.06 → 18.59 | +2.9 % | 1.2 % | no |
| draft floor 0.7 (cost gate off) | 19.00 → 19.16 | +0.8 % | 1.1 % | no |
| --pcie-frac 0.2 | 19.59 → 19.94 | +1.8 % | 7.2 % | no |
| CPU pool workers 12 | 18.88 → 17.91 | −5.1 % | 1.8 % | no |
| VRAM reserve 713 MiB (expert cache vs reserve) | 19.38 → 20.07 (one arm) | – | – | **no: the second arm crossed the 5080's 300 MiB floor (guard stop)** |
| resident KV 16K (vs 32K) | 19.30 → 19.49 | +1.0 % | 7.5 % | no |
| **max context 64K** (vs 131K) | 18.80 → 19.99; re-check 18.24 → 19.92 | **+6.3 %; +9.2 %** | 9.1 %; 3.9 % | **yes** (twice; it gives up prompts over 64K) |
| adaptive swaps 48 (vs 96) | 18.55 → 19.29; re-check 18.64 → 18.95 | +4.0 %; +1.7 % | 6.7 %; 7.5 % | no (did not repeat) |
| swaps 48 + 64K together | 18.55 → 19.23 | +3.7 % | 7.2 % | (less than 64K alone) |
| adaptive swaps 192 | 19.61 → 19.45 | −0.8 % | 11.3 % | no |

**The ~6-bit splice, placement C (served: each arm a fresh server, a warm-up + 2 requests of the math prompt at your
sampling, 1,024 tokens; the split/chunk arms also read the 32K prompt; 23:42–01:45, all 13 settings inside the 2 hours)**

| setting | base → option tok/s | change | base arms' spread | 32K read base → option | kept |
|---|---|---|---|---|---|
| split point 46 (vs auto = 47) | 50.72 → 52.69 | +3.9 % | 0.1 % | 63.6 → 63.4 s (−0.3 %) | no (your rule: it does not cut the read) |
| split point 44 | 53.09 → 52.62 | −0.9 % | 2.6 % | 63.5 → 62.9 s (−0.9 %) | no |
| prompt chunk 2,048 (auto = 1,024 here) | – | – | – | the engine shrank it back to 1,024 (the 4060 Ti's 431 slots) | no (no effect; one arm) |
| prompt chunk 512 | 51.68 → 52.20 | +1.0 % | 1.6 % | 63.5 → 93.9 s (**+47.8 %**) | no |
| draft length 3 | 51.33 → 50.98 | −0.7 % | 2.8 % | | no |
| draft floor 0.7 (cost gate off) | 51.58 → 51.54 | −0.1 % | 2.5 % | | no |
| VRAM reserve 713 MiB | 51.61 → 52.52 | +1.8 % | 4.9 % | (chunk became 1,280; read not timed) | no |
| resident KV 16K | 51.28 → 52.56 | +2.5 % | 2.8 % | | no |
| max context 64K | 53.41 → 54.33 | +1.7 % | 2.7 % | (chunk became 1,280; read not timed) | no (set anyway for correctness, below) |
| **adaptive swaps 48** | 51.34 → **58.79** | **+14.5 %** | 2.8 % | | **yes** |
| --pcie-frac 0.2 | 50.77 → 52.57 | +3.5 % | 0.7 % | | yes |
| CPU pool workers 12 | 51.85 → 52.14 | +0.5 % | 0.2 % | | no |
| adaptive swaps 192 | 51.76 → 49.96 | −3.5 % | 3.8 % | | no |

Saved: **configs/r15-q5s-C.json** (C, 72 GiB, unbuffered, swaps 48, --pcie-frac 0.2, **max context 64K for correctness**: the
120K failure above) and **configs/r15-q5s-B.json** (B as measured in step 3; budget 71 GiB, the largest that keeps 6 GiB
strictly; swaps 48 not measured on B, so not set). The kept settings were measured each alone; their combination was not.

Saved for Q8_0: **configs/r15-q8.json** (D, 71 GiB, unbuffered, 64K context) and configs/r15-q8-131k.json (the same at 131K,
as measured in step 3).

**C's saved config on the full screens** (your request; configs/r15-q5s-C.json, single runs, 08:12): decode screen **50.7**
tok/s (was 45.2: +12 %), LDR **43.1** (was 41.4: +4 %) — most of step 5's +14.5 % (measured on the short math prompt)
carries to the decode screen, little to research answers. (The earlier runs had the timing switches on: a small overhead.)

### Step 6 — every expert in RAM: an ESTIMATE, not a measurement (results/r15/s6-estimate.md)

From each full set's CLI split: the SSD part of the round replaced by the same bytes read at the CPU pool's own measured
RAM rate (70–74 GB/s), everything else as measured; the served figure scaled by the same factor. Real numbers would sit
somewhat lower (the RAM bandwidth is shared with the reads the pool already does).

| placement | measured round → estimated (ms) | CLI tok/s → estimated | served (all requests) → **estimated** | RAM it would need |
|---|---|---|---|---|
| Q8_0 D | 143.5 → 66.5 | 18.9 → 40.9 | 14.8 → **~32** | ~123 GiB |
| Q8_0 B | 126.9 → 64.7 | 19.5 → 38.3 | 12.9 → **~25** | ~130 GiB |
| splice B | 56.2 → 42.8 | 48.7 → 64.0 | 34.7 → **~46** | ~101 GiB |

### Step 7 — quality (teacher-forced NLL, 9 texts, nats per token, lower is better; results/r15/s7-quality.md; 85 min)

| | IQ3_S (served today) | UD-Q4_K_XL | splice: UD-Q5_K_XL experts + IQ3_S's other tensors | Q8_0 |
|---|---|---|---|---|
| short (math, corpus), mean | 0.3387 | 0.3421 | 0.3401 | 0.3405 |
| long 16K–112K (clipped at 5), mean of 7 | 2.046 | 1.837 | 1.872 | **1.779** |
| shift vs IQ3_S on the long texts (± text-level se) | – | −0.209 ± 0.080 | −0.174 ± 0.068 | **−0.267 ± 0.084** |

On short texts the four files are within 0.004 nats. On long documents every bigger file reads the forced continuation
better than IQ3_S; Q8_0 most. The splice keeps IQ3_S's attention, shared experts and n-gram table, so it is not a whole
6-bit file and lands behind UD-Q4_K_XL; one text (long40k) is worse than IQ3_S for UD-Q4 and the splice.

### Step 8 — the catch-up on IQ3_S (your config, the 20 GB floor)

**Every default changed since v0.1.40.1** (results/r15/v0402-defaults.md): no existing engine default changed; 35 new
switches, of which on by default here: upstream's F4 (STRATA_MMVQ_IL — the same code and switch as our B.3, so B.3 was
not ported), the AVX2 Q8_K quantizer (#851), the IQ3_S AVX2 decode, STRATA_STAGER_SLEEP, STRATA_PIN_GUARD,
STRATA_PREFILL_STREAM_AHEAD, the layer-split probe and pipeline async (unused here), the unbuffered-read rule (budgets
only), #789's prefill overlap and #1252's draft policy (no switches). Server changes that reach your Open WebUI → 8080
path: #1182 (a Stop / closed tab during a long prompt read cancels it), #1059 (a refused request answers at once, not after
300 s), #1317 (a hung engine start times out), the restart fixes (ec7f6a02, #351), #1031 (/settings without "defaults" no
longer clears every shared setting). /metrics stays JSON for our monitor.

**Upstream's new drafting vs our exact sampling** (served, A B C C B A on the decode screen, then A B B A on LDR):
STRATA_SPEC_PROB alone 137.5 vs ours 141.3 (−2.7 %: acceptance +10.5 % but 11.9 % fewer tokens per round); under our
cost gate 141.8 (+0.3 %) and on LDR 138.3 vs 139.2 (−0.6 %) → **ours kept**; C\*15 = C\*14's flags.

**C\*15 vs C\*14** (A B B A, fresh guarded servers): **LDR 142.9 → 138.9 (−2.8 %), decode 144.7 → 140.3 (−3.1 %), full
145.6 → 142.2 (−2.3 %)**; the verify round costs 2.8–3.5 % more; acceptance and tokens per round equal; outputs identical
(exact7 7/7 = C\*14's hashes).

**Where the 3 % went** (your request: 1 hour, settings and defaults only, each changed default back on C\*15 alone, decode
screen against interleaved C\*14 arms; results/r15/s8-find3.md): C\*14 145.1, plain C\*15 141.8; cost gate off 137.1
(the gate still helps), STAGER_SLEEP=0 141.1, PIN_GUARD=0 140.9, PREFILL_STREAM_AHEAD=0 141.0, NO_Q8K_AVX2=1 141.4,
MMVQ_IL=0 139.2 (F4 gives ~1.8 %, about what B.3 gave). **None restores the speed: the slowdown is unexplained by any
setting.** What is left has no switch: #1252's draft-policy re-measurement, #789's prefill overlap, the IQ3_S AVX2 decode
and the rest of the 242 commits. STRATA_SPEC_PROB was already at its old value (off).

**Newer releases** (found late, item 19 below): v0.1.40.3 (Windows / Intel / HIP setup, web #1392, a guard on the drafter's
router for 512 experts / k = 10), v0.1.40.4 (a Pascal decode regression, #1469) and **v0.1.41** (151 commits after
v0.1.40.2). v0.1.41's last commit makes upstream's new pinned stage buffers (STRATA_STAGE_PIN, added after v0.1.40.3)
opt-in because its release gate found IQ3_S decode corrupted after a 4,096-token prompt ("a stage buffer recycled before
its asynchronous copy finished"). That switch is not in v0.1.40.2, so it is not placement C's failure, but it is the
same class of symptom — possibly related, not shown. C\*15 stays on this round's base, v0.1.40.2.

### What the runbook, the planner and I got wrong

**Runbook / tools**
1. The inspector carried v0.1.39's expert-format list (it called UD-Q5_K_XL unsupported; v0.1.40.2 runs it with
   `-DSTRATA_Q6K_EXPERTS=ON`). Fixed: it reads is_iq() and the build options from the tree.
2. Nothing checked a shard's header against the engine's own reader: UD-Q5_K_XL's metadata-only shard 1 is 6 bytes short
   of the aligned data section, so the engine refuses the file ("data section starts past EOF") while gguf-py reads it.
   Fixed: the inspector flags such a shard. The stand-in became a splice (UD-Q5 experts + IQ3_S's other tensors).
3. The runbook computes PIN_CACHE at its start, so a run started at "clone" pins differently from one started at
   "stock" (exact7's x-32k / x-112k hashes differ for that reason alone).
4. Calibration on a file that reads experts from the SSD is one noisy sample per setting (the splice's reserve 713 MiB:
   +10.4 % once, +1.8 % in step 5's A B B A).

**The fit planner / the placements**
5. The planner assumed 10 GiB for the desktop and services where 2–5 GiB are used, so its budget at your margin was 72
   where the full runs held 71–72, and I started step 3 at 64 GiB: **neither the planner's default nor my starting
   budget used your 6 GiB margin** (your note).
6. It did not know that a full run needs more RAM than a probe: the chat cache's parked conversations and prompt
   checkpoints took ~3 GiB more over an hour (74 GiB passed the probes and failed every full run; 71–72 held).
7. Placement E (`--resident-experts`) sizes its own RAM copy with 8 GiB headroom (76.9 / 77.4 GiB), below your floor on
   both files; there is no flag to size it, so it cannot run under a 6 GiB margin.
8. Placement C runs only under --serve; on Q8_0 its auto split did not start (the arena did not fit the 4060 Ti) and the
   forced split needed 1,613 MiB reserve. On the 8 GB 4060 Ti a split caps the prompt chunk at 1,024 tokens (the engine's
   #448 warning): prompt reads 5–6x slower than B, 1.28 TB from the drive for one 120K prompt.
9. v0.1.40.2's unbuffered-read rule chose the page cache on this PC; forced direct reads were +15 % (splice) and +48 %
   (Q8_0), and only with them did the budget sizes rank right (buffered: a bigger copy squeezed the page cache).
10. Probes are noisy where experts come from the SSD (CLI probes 19–48 % under served ones; two greedy probes of the same
    build split at tokens 97–279), so the repeat gate needed up to four probes and every comparison stayed served-vs-served.

**Correctness**
11. Placement C answered degenerately after a 120K prompt inside its full set and for every later multi-chunk prompt of
    that server; not reproduced in 8 fresh sessions (ours and stock, the full set's exact config and order). Intermittent,
    cause unknown; the saved C config caps the context at 64K as a precaution.
12. Q8_0's placement D hung once reading a 64K prompt (73 GiB run; "no progress for 60 s … layer 33"); not seen again.

**My slips**
13. My splice wrote 123 GiB while Q8_0's first stock runs page-locked their copy: three swap-rule stops (re-run after).
14. I re-queued full sets while the previous server was still shutting down: they refused the busy port and two step-5
    runs ran out of memory; cleaned up, the full-set script now waits for the port.
15. The 120K diagnostic failed to start twice (a relative path; then stock has no --chat-cache) before it ran.
16. Steps 3 and 4 ended without the promoted build on 8080 (the queue ran them back to back); phase ends now follow
    steps 5 and 7.
17. I briefly read the diagnostic as "STRATA_QSA_SPLIT_ATTN breaks C"; the positive control (ours as configured, fresh)
    passed, so that reading was withdrawn.
18. The acceptance suite started from the queue before your 3 % search; my first stop missed its llama.cpp server, so the
    search's first run refused the busy port and was re-run.
19. **Three upstream releases came out during the round and I did not report them until 09:30 on 10-08:** v0.1.40.3
    (10-07 13:02), v0.1.40.4 (10-08 03:42), v0.1.41 (10-08 07:42). The watcher logged them and wrote its flag files;
    none of my waiters checked those files.

