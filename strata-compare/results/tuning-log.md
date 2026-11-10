# Strata tuning log (C0 → C*)

Every experiment = one change against the C0 baseline, measured with `scripts/screen.sh` (fresh server, cold n-gram
page cache, identical request sequence: warm-up · 1K ×3 · 32K ×1 · 5 greedy correctness prompts; extra scenarios where
the change targets them). "Same tokens" = the 5 correctness outputs are byte-identical to the C0 screen's.
Noise floor from repeated C0 screens is stated below; gains inside it are "no gain".

C0 = setup.py defaults (expert cache auto, prefill 2048, spec 4 [= 3 drafts], spec-min-p 0.5, int8 KV, KV streaming
32768 cells, 131,072 context, MTP on) **+ `--vram-reserve-mib 1000`** (the defaults do not start here: see REPORT).

## v0.1.6 screens (reference T-c0a)

| config | 1K decode tok/s (3 prompts) | 32K decode tok/s | 32K TTFT s (PP tok/s) | correctness decode tok/s (5) | draft acceptance | tokens/round | same tokens as T-c0a (first divergence) |
|---|---|---|---|---|---|---|---|
| T-c0a | 46.9 [41.5–55.9] | 52.8 | 37.8 (866) | 55.1 [41.7–63.4] | 0.772 | 2.40 | 5/5 (= = = = =) |
| T-c0b | 46.4 [45.1–51.9] | 50.5 | 37.6 (871) | 48.1 [42.3–60.8] | 0.765 | 2.39 | 1/5 (= 41 81 108 65) |
| T-pcie0 | 92.7 [75.6–108.3] | 87.7 | 37.8 (866) | 78.4 [74.4–97.2] | 0.784 | 2.49 | 2/5 (= 41 = 38 133) |
| T-pcie02 | 66.6 [59.7–71.4] | 58.9 | 37.9 (864) | 58.3 [51.7–67.5] | 0.776 | 2.40 | 3/5 (= 41 = = 133) |
| T-w15 | 48.9 [47.4–57.0] | 54.3 | 37.8 (867) | 52.7 [42.4–63.4] | 0.780 | 2.49 | 1/5 (71 41 = 48 161) |
| T-mmap | 47.6 [46.3–55.0] | 51.8 | 37.4 (876) | 50.0 [40.8–61.1] | 0.780 | 2.49 | 1/5 (71 41 = 48 161) |
| T-p0w15 | 95.2 [88.7–109.7] | 88.5 | 37.8 (866) | 80.3 [79.4–99.8] | 0.787 | 2.49 | 1/5 (= 41 81 48 104) |
| T-p0pf4096 | 87.1 [86.9–91.2] | 86.7 | 31.9 (1028) | 79.0 [70.0–95.7] | 0.773 | 2.37 | 1/5 (40 41 = 2 81) |
| T-p0thp | 88.2 [88.1–107.0] | 85.9 | 37.9 (864) | 80.1 [73.8–98.4] | 0.790 | 2.52 | 3/5 (= 41 = = 104) |
| T-p0deta | 76.4 [74.7–77.7] | 76.0 | 37.9 (865) | 69.6 [58.4–79.0] | 0.772 | 2.38 | 1/5 (35 41 = 48 81) |
| T-p0detb | 73.6 [73.3–76.8] | 74.9 | 37.9 (866) | 69.1 [57.6–77.7] | 0.749 | 2.33 | 2/5 (35 41 = = 81) |

## v0.1.11 screens (reference N-n0)

| config | 1K decode tok/s (3 prompts) | 32K decode tok/s | 32K TTFT s (PP tok/s) | correctness decode tok/s (5) | draft acceptance | tokens/round | same tokens as N-n0 (first divergence) |
|---|---|---|---|---|---|---|---|
| N-n0 | 43.8 [43.2–55.5] | 45.9 | 37.8 (867) | 49.2 [34.3–65.5] | 0.747 | 2.34 | 5/5 (= = = = =) |
| N-n1 | 86.2 [82.5–108.7] | 85.7 | 31.8 (1030) | 78.6 [72.8–95.7] | 0.789 | 2.52 | 1/5 (40 68 = 48 36) |
| N-n2 | 88.2 [87.7–88.3] | 89.9 | 22.7 (1445) | 83.4 [74.4–98.4] | 0.745 | 2.14 | 2/5 (= 68 = 48 36) |
| N-n3 | 93.3 [91.7–115.1] | 89.7 | 22.7 (1444) | 85.7 [77.9–102.3] | 0.783 | 2.52 | 1/5 (= 42 130 3 36) |
| N-n3x | 92.4 [90.8–93.1] | 92.9 | 22.7 (1446) | 82.4 [77.7–102.9] | 0.743 | 2.18 | 1/5 (40 42 = 108 36) |
| N-n3sd0 | 95.0 [92.4–100.2] | 91.6 | 22.7 (1447) | 85.1 [78.8–104.8] | 0.775 | 2.43 | 2/5 (= 41 = 95 36) |
| N-n3kv0 | 89.9 [84.2–96.9] | 83.0 | 23.1 (1420) | 83.0 [75.2–96.6] | 0.752 | 2.32 | 3/5 (= 43 = = 36) |
| N-n3q4 | 92.0 [90.8–110.0] | 87.7 | 22.9 (1433) | 83.9 [76.8–103.2] | 0.765 | 2.47 | 0/5 (40 42 224 2 36) |
| N-n3stash | 92.2 [91.6–102.0] | 90.7 | 22.5 (1454) | 80.2 [75.3–101.8] | 0.760 | 2.33 | 2/5 (= 43 = 3 36) |


## Decisions (one change at a time; noise floor: two identical C0 screens differ by ~1–5 % on 1K decode medians and
<1 % on 32K prompt speed)

| # | engine | change | result vs its base | same tokens? | kept? | why |
|---|---|---|---|---|---|---|
| 1 | 0.1.6 | C0 repeat (c0b vs c0a) | 1K 46.4 vs 46.9, 32K PP 871 vs 866 | **no, 1/5** (first diff at 41–108) | — | defines the noise and shows Strata is not reproducible run to run (adaptive expert swaps; GPU vs CPU rounding) |
| 2 | 0.1.6 | `--pcie-frac 0` | 1K ×1.98 (92.7), 32K decode ×1.66 (87.7), PP = | 2/5 (41–133: same range as #1) | ✔ | GPU was the bottleneck (35.8 of 48.6 ms/window); PCIe experts were on its critical path |
| 3 | 0.1.6 | `--pcie-frac 0.2` | 66.6 / 58.9 | 3/5 | ✘ | monotone in the share → 0 |
| 4 | 0.1.6 | `--pool-workers 15` (no pcie change) | 48.9 / 54.3 | 1/5 | ✘ | noise while the GPU bounds |
| 5 | 0.1.6 | `--ple-io mmap` (cold) | 47.6 / 51.8; 1K TTFT +0.4 s | 1/5 | ✘ | Linux mmap path does no prefetch; cold rows fault serially |
| 6 | 0.1.6 | #2 + `--pool-workers 15` | 95.2 / 88.5 | 1/5 | (✔ on 0.1.11) | +1–3 %: noise edge |
| 7 | 0.1.6 | #2 + `--prefill 4096` | PP 866 → 1,028 (+19 %); decode = | 1/5 | ✔ | prompt path streams each missed expert once per chunk; 2× chunk halves the traffic per token |
| 8 | 0.1.6 | #2 + THP arena (patch, `STRATA_ARENA_THP=1`) | 88.2 / 85.9 | 3/5 | ✘ | no gain → patch dropped |
| 9 | 0.1.6 | #2 + `--adapt-swaps 0`, twice | 76.4 / 76.0 and 73.6 / 74.9 | **4/5 between the two** | ✘ | reproducible but −18 %: a reproducibility option, not a default |
| 10 | 0.1.6 | `--spec`, `--spec-min-p` | — | — | not run | cancelled for the v0.1.11 switch |
| 11 | 0.1.11 | N0 = defaults | 43.8 / 45.9 / PP 867 | (base) | — | same as C0 within noise; starts without the VRAM workaround |
| 12 | 0.1.11 | N1 = pcie 0 + prefill 4096 | 86.2 / 85.7 / 1,030 | 1/5 | ✔ | re-confirms #2 + #7 on 0.1.11 |
| 13 | 0.1.11 | N2 = N1 + patch 0001 (parallel n-gram reads) | 88.2 / 89.9 / **1,445** (+40 % PP) | 2/5 | ✔ | serial `pread` per n-gram row was the prompt-path limiter on Linux |
| 14 | 0.1.11 | N3 = N2 + `--pool-workers 15` | 93.3 / 89.7 / 1,444 | 1/5 | ✔ | +2–5 %, fewer SMT-sibling collisions |
| 15 | 0.1.11 | N3 + `--suffix-draft 0` (prompt lookup off) | 95.0 / 91.6 / 1,447; code edit 117.6/124.9 vs 116.5/124.2 | 2/5 | default kept (on) | no measurable effect either way here |
| 16 | 0.1.11 | N3 + `--kv-resident 0` (KV streaming off) | 89.9 / 83.0 / 1,420; 3,832 vs 4,502 VRAM experts | 3/5 | streaming kept | −4 / −7 % |
| 17 | 0.1.11 | N3 + `--kv q4_0` | 92.0 / 87.7 / 1,433; 4,603 experts | 0/5 | ✘ (8-bit kept, as asked) | no gain at ≤ 32K |
| 18 | 0.1.11 | N3 + patch 0002 `--side-stash 4096` | 92.2 / 90.7 / 1,454; side-request chat turn 7 TTFT **4.75 s vs 26.8 s** | 2/5 | ✔ | Open WebUI's title/tag requests no longer evict the chat |

**Token changes, where and why:** every change that alters which experts run on the GPU vs the CPU (the expert
cache's adaptive swaps, the PCIe share, the prefill chunk borrowing cache slots) changes floating-point order, so
greedy outputs drift at near-ties (examples: "We need to answer" vs "We need to respond" at token 3;
"Need maybe concise" vs "Need maybe ensure" at token 36). C0 drifts against itself the same way (#1). Accuracy check
(teacher-forced perplexity on 2 × 1,536 fixed tokens through the decode path): tuned − default = **+0.0006 ± 0.0006**
and **+0.0008 ± 0.0014** nats/token → no loss. The quality checks on C\* are in REPORT §8.

## Round 2 (2026-09-27 14:16 →): C\* → C\*2

Method: `work/r2/screen3.sh` = the round-1 screen, but **sampled** (no request sends sampling fields, so the config's
0.6/0.95/20/0.05 applies, as in Open WebUI): warm-up · 1K ×3 · 32K · the 5 correctness prompts (sampled now) · plus
`lr8k` (long-reasoning math prompt, 8,192-token cap) for speculation changes and `speed120` for prompt-path changes.
Fresh server, cold model page cache each time; one change against C\* (configs/R2-*.json). Mechanism checks with
`strata generate --stats` (`work/r2/prof.sh`, tables from `work/r2/prof_table.py`). "agg decode" = tokens ÷ decode time
over the four 1K+32K requests (steadier than the median of three sampled prompts).

**Noise (two C\* screens, R2-basea/b):** prompt reading 32K 22.84/22.82 s, 120K 88.9/88.8 s (**±0.1 %**); agg decode
83.1/81.9 (±1.5 %); 8K reasoning 96.0/93.7 (±2.4 %); a single 32K decode 80.8/86.6 (±7 %, sampling).

| config | 1K decode tok/s (3 prompts) | agg decode 1K+32K (engine) | 32K decode | 32K TTFT s (PP tok/s) | correctness decode (5, sampled) | acceptance | tok/round | 8K reasoning tok/s (acc) | 120K TTFT s (PP) | peak GPU MiB / min MemAvail / peak RSS |
|---|---|---|---|---|---|---|---|---|---|---|
| R2-basea | 83.1 [78.8–92.4] | 83.1 | 80.8 | 22.84 (1435) | 75.5 [73.8–90.4] | 0.728 | 2.38 | 96.0 (0.716) | 88.9 (1383) | 15482 / 36.5 GB / 50.5 GB |
| R2-baseb | 81.1 [77.0–84.9] | 81.9 | 86.6 | 22.82 (1436) | 75.8 [69.0–97.8] | 0.731 | 2.27 | 93.7 (0.699) | 88.8 (1385) | 15482 / 36.4 GB / 50.6 GB |
| R2-spec5 | 88.6 [76.4–109.1] | 86.3 | 79.6 | 22.88 (1432) | 82.6 [74.4–96.5] | 0.733 | 2.66 | 96.8 (0.682) | – | 15502 / 36.7 GB / 50.4 GB |
| R2-smp03 | 79.0 [75.8–82.0] | 78.2 | 77.4 | 22.85 (1434) | 72.9 [65.3–93.7] | 0.594 | 2.37 | 95.7 (0.656) | – | 15482 / 36.8 GB / 50.3 GB |
| R2-smp07 | 81.6 [79.8–84.7] | 82.2 | 84.3 | 22.85 (1434) | 81.5 [75.4–93.0] | 0.835 | 2.03 | 95.1 (0.818) | – | 15482 / 36.7 GB / 50.3 GB |
| R2-io64 | 86.2 [77.7–108.1] | 86.2 | 80.3 | 22.57 (1452) | 75.5 [72.9–88.3] | 0.773 | 2.48 | – | 87.8 (1400) | 15480 / 36.4 GB / 50.5 GB |
| R2-pcie005 | 77.8 [76.0–89.7] | 79.8 | 78.5 | 22.82 (1436) | 78.2 [67.7–96.1] | 0.707 | 2.22 | – | – | 15480 / 36.8 GB / 50.2 GB |

Mechanism profiles (1K prompt, 512 sampled tokens, `generate --stats`):

| config | decode tok/s | tokens/window | acceptance | ms/window: GPU wait / CPU pool / MTP | CPU experts/layer (distinct) | RAM MB streamed per token | PCIe MB/token (tier swaps) | VRAM hit rate |
|---|---|---|---|---|---|---|---|---|
| Cstar | 99.6 | 2.45 | 0.840 | 10.8 / 10.5 / 1.1 | 7.44 | 296 | 20 | 0.674 |
| R2-pcie005 | 95.7 | 2.32 | 0.789 | 11.0 / 9.9 / 1.1 | 6.92 | 290 | 21 | 0.692 |
| R2-pcie01 | 81.8 | 2.12 | 0.749 | 13.4 / 9.2 / 1.1 | 6.26 | 288 | 22 | 0.689 |

Speculation profiles (math reasoning prompt, 1,024 sampled tokens, `generate --stats`; RAM MB/token = expert weights the CPU pool streams per generated token):

| config | decode tok/s | tokens/window | acceptance | ms/window: GPU wait / CPU pool / MTP | CPU experts/layer (distinct) | RAM MB streamed per token | PCIe MB/token (tier swaps) | VRAM hit rate |
|---|---|---|---|---|---|---|---|---|
| Cstar | 111.7 | 2.69 | 0.777 | 12.0 / 8.7 / 1.2 | 6.01 | 217 | 18 | 0.777 |
| R2-spec3 | 110.0 | 2.26 | 0.846 | 10.8 / 6.9 / 0.9 | 4.81 | 207 | 19 | 0.782 |
| R2-spec5 | 111.7 | 2.93 | 0.744 | 12.7 / 9.7 / 1.5 | 6.80 | 225 | 17 | 0.770 |
| R2-smp03 | 107.4 | 2.82 | 0.685 | 12.7 / 9.8 / 1.4 | 6.84 | 236 | 17 | 0.779 |
| R2-smp07 | 111.4 | 2.38 | 0.877 | 11.0 / 7.3 / 1.1 | 5.00 | 204 | 19 | 0.776 |

Expert-cache profiles (1K prompt, 512 sampled tokens):

| config | decode tok/s | tokens/window | acceptance | ms/window: GPU wait / CPU pool / MTP | CPU experts/layer (distinct) | RAM MB streamed per token | PCIe MB/token (tier swaps) | VRAM hit rate |
|---|---|---|---|---|---|---|---|---|
| Cstar | 99.6 | 2.45 | 0.840 | 10.8 / 10.5 / 1.1 | 7.44 | 296 | 20 | 0.674 |
| R2-res800 | 97.4 | 2.35 | 0.813 | 10.6 / 10.1 / 1.1 | 7.18 | 298 | 20 | 0.679 |
| R2-adapt8 | 97.7 | 2.47 | 0.820 | 10.7 / 11.2 / 1.1 | 8.02 | 317 | 10 | 0.655 |
| R2-adapt2 | 98.2 | 2.42 | 0.792 | 10.9 / 10.3 / 1.1 | 7.21 | 290 | 32 | 0.691 |

**Long-reasoning A/B, spec 5 vs C\* (8,192-token cap, sampled; `work/r2/lr.sh` + the screens' lr8k):** C\* math
96.0/93.7/97.1/97.7 (mean 96.1), code 80.2/84.5 (82.3); spec5 math 96.8/97.9/96.4/98.6 (97.4), code 78.6/81.2 (79.9); all
requests 91.5 vs 91.6 tok/s → no difference.

**Combined candidate R2-final = C\* + `--prefill 8192` + `STRATA_PLE_IO_THREADS=64 --ple-inflight 128` + `--vram-reserve-mib 800`:**

| config | 1K decode tok/s (3 prompts) | agg decode 1K+32K (engine) | 32K decode | 32K TTFT s (PP tok/s) | correctness decode (5, sampled) | acceptance | tok/round | 8K reasoning tok/s (acc) | 120K TTFT s (PP) | peak GPU MiB / min MemAvail / peak RSS |
|---|---|---|---|---|---|---|---|---|---|---|
| R2-basea | 83.1 [78.8–92.4] | 83.1 | 80.8 | 22.84 (1435) | 75.5 [73.8–90.4] | 0.728 | 2.38 | 96.0 (0.716) | 88.9 (1383) | 15482 / 36.5 GB / 50.5 GB |
| R2-baseb | 81.1 [77.0–84.9] | 81.9 | 86.6 | 22.82 (1436) | 75.8 [69.0–97.8] | 0.731 | 2.27 | 93.7 (0.699) | 88.8 (1385) | 15482 / 36.4 GB / 50.6 GB |
| R2-io64 | 86.2 [77.7–108.1] | 86.2 | 80.3 | 22.57 (1452) | 75.5 [72.9–88.3] | 0.773 | 2.48 | – | 87.8 (1400) | 15480 / 36.4 GB / 50.5 GB |
| R2-pf8192 | 89.1 [79.8–90.9] | 86.3 | 88.1 | 19.76 (1658) | 77.0 [73.3–93.9] | 0.748 | 2.47 | – | 76.8 (1600) | 15480 / 36.4 GB / 50.6 GB |
| R2-pf12288 | 82.5 [79.7–97.2] | 83.9 | 80.2 | 21.35 (1535) | 74.7 [69.7–90.5] | 0.737 | 2.36 | – | 80.8 (1521) | 15482 / 36.5 GB / 50.5 GB |
| R2-mmapwarm | 81.1 [78.4–86.9] | 81.2 | 80.6 | 22.83 (1436) | 76.6 [66.6–95.3] | 0.729 | 2.29 | – | 87.4 (1406) | 15480 / 36.6 GB / 76.8 GB |
| R2-w8x | 82.0 [76.4–85.4] | 80.3 | 79.6 | 22.82 (1436) | 71.8 [61.0–87.6] | 0.719 | 2.25 | – | – | 15480 / 36.8 GB / 50.2 GB |
| R2-adapt8 | 90.6 [77.5–100.6] | 85.2 | 77.8 | 22.80 (1437) | 74.0 [65.3–83.9] | 0.762 | 2.51 | – | – | 15480 / 36.8 GB / 50.2 GB |
| R2-res800 | 79.0 [77.6–83.8] | 79.4 | 78.7 | 22.83 (1435) | 77.1 [75.0–95.5] | 0.715 | 2.13 | – | – | 15380 / 36.8 GB / 50.2 GB |
| R2-spec5b | 79.8 [78.5–83.9] | 80.3 | 80.6 | 22.78 (1438) | 76.5 [68.9–101.2] | 0.689 | 2.28 | 97.9 (0.692) | – | 15502 / 36.7 GB / 50.4 GB |
| R2-spec6 | 81.9 [76.8–94.1] | 82.6 | 81.4 | 22.79 (1438) | 79.8 [72.6–96.7] | 0.675 | 2.55 | 96.4 (0.634) | – | 15526 / 36.7 GB / 50.4 GB |
| R2-final | 82.0 [77.5–83.5] | 82.0 | 87.2 | 19.39 (1690) | 75.3 [73.3–94.8] | 0.758 | 2.26 | 96.3 (0.716) | 75.8 (1622) | 15382 / 36.3 GB / 50.7 GB |

**Accuracy (teacher-forced perplexity, round-1 method, 2 × 1,536 fixed tokens):** C\*2 − C\* = +0.0001 ± 0.0006 (math) and
+0.0021 ± 0.0017 (corpus) nats/token; C\* against its own round-1 run of the same flags: −0.0013 ± 0.0006 / −0.0021 ± 0.0013
→ within the run-to-run drift. **C\*2 kept.**

### Round-2 decisions (base = C\*; noise: prompt ±0.1 %, agg decode ±1.5 %, 8K reasoning ±2.4 %)

| # | change | result vs C\* | kept? | why |
|---|---|---|---|---|
| 19 | `--spec 5` | agg +4.6 % / −2 % (2 screens); reasoning A/B 91.6 vs 91.5 tok/s (6 vs 6 requests); profile 111.7 vs 111.7 | ✘ | flat optimum: 2.93 vs 2.69 tok/window but 26.2 vs 24.1 ms/window; +20 MiB VRAM |
| 20 | `--spec 6` | agg +0.1 %, reasoning 96.4 (acc 0.634) | ✘ | no gain, +44 MiB VRAM |
| 21 | `--spec 3` (profile only) | 110.0 vs 111.7 tok/s, 207 vs 217 MB/token | ✘ | fewer tokens per window |
| 22 | `--spec-min-p 0.3` | acc 0.594, agg −5 %, 236 MB/token | ✘ | more drafts, same tokens/window |
| 23 | `--spec-min-p 0.7` | agg −0.4 %, reasoning 95.1; 204 MB/token, 2.38 tok/window | ✘ | noise |
| 24 | `--pcie-frac 0.05 / 0.1` | agg −3 %; window 24.2 / 25.9 vs 24.6 ms | ✘ | GPU wait grows as fast as the pool shrinks |
| 25 | `STRATA_PLE_IO_THREADS=64 --ple-inflight 128` | 32K TTFT −1.2 %, 120K −1.2 %; SSD p50 164 → 106 µs | ✔ | 12× the prompt noise; no memory cost |
| 26 | `--prefill 8192` | 32K −13.4 %, 120K −13.6 %; short prompts +0.08–0.1 s | ✔ | half the PCIe expert traffic per prompt token; borrows 2,997 slots, no extra VRAM |
| 27 | `--prefill 12288` | 32K −6.5 %, 120K −9.1 % (worse than 8192) | ✘ | only 2,296 slots left to borrow |
| 28 | `--ple-io mmap` + whole n-gram shard in page cache | 32K =, 120K −1.6 %, RSS 77 GB | ✘ | upper bound of a RAM-resident table; not worth 29 GB |
| 29 | 8 pool workers 4+4 across CCDs (taskset) | agg −2.7 %, prompt = | ✘ | same bandwidth, no gain |
| 30 | `--adapt-every 8` | agg +3.3 % screen; profile hit 0.655, 317 MB/token, 97.7 vs 99.6 | ✘ | screen = noise; mechanism slightly worse |
| 31 | `--adapt-every 2` (profile only) | hit 0.691, 290 MB/token, 32 MB/token swaps, 98.2 vs 99.6 | ✘ | noise |
| 32 | `--vram-reserve-mib 800` | −52 slots; hit 0.679 vs 0.674; agg in noise; peak VRAM −100 MiB | ✔ (constraint) | keeps ≥300 MiB free with Chrome (C\*: ~304 → C\*2 ~404) |
| 33 | usage-profile cache warm-up | — | not built | routing trace is empty on the speculative path (engine patch needed); tier re-ranks every 4 windows anyway |
| 34 | **C\*2 = #25 + #26 + #32** | 32K −15.1 %, 120K −14.7 %, chat turn −0.6 s, decode =, reasoning =, NLL = | ✔ | configs/Cstar2.json |

## Round 3 (2026-09-27 23:21 → 2026-09-28): engine changes, C\*2 → C\*3

Method: screens as in round 2 (`work/r3/screen.sh`, sampled via the config, cold page cache, fresh server; + `speed120`,
`lr8k`), decode mechanism by nsys node-level traces and by A/B on one binary with `strata generate --stats` (greedy in the
windows — upstream bug — so identical windows run to run: ±0.1 %), accuracy by teacher-forced NLL (deterministic per
build; long-context texts added), chat-cache behaviour by `work/r3/chatsoak.py` (chat-page-shaped requests).
Base: v0.1.12 + 0001/0002 = R3-base (= C\*2 within noise: 32K 19.16 vs 19.15 s, 120K 74.72 vs 74.64 s).

| # | change | result | kept? | why |
|---|---|---|---|---|
| 35 | v0.1.11 → v0.1.12 (pool race fix + watchdog) | prompt/decode = | ✔ | fixes a hang seen upstream on big-VRAM cards |
| 36 | batched layer-1 PLE in the prompt path (patch 0003) | 32K 19.16 → 17.86 s, 120K 74.72 → 69.73 s | ✔ | ~10 launches + 65 MB of weight reads per token → 2 GEMMs + 7 kernels; post-ops bit-identical |
| 37 | next-chunk n-gram prefetch (patch 0004) | 32K → 17.51 s, 120K → 68.31 s (−2 % more) | ✔ | the chunk's SSD gather overlaps the previous chunk's layers |
| 38 | CPU expert rows only over PCIe (patch 0005) | mapped copy 6.3 → 3.4 µs/layer | ✔ | with #39: decode +2.5 % (A/B, identical windows) |
| 39 | multi-token BF16 MMVF for router/indexer (patch 0006) | bit-identical; weight read once per window | ✔ | see #38; first version spilled accumulators (fixed) |
| 40 | hyper-connection kernels v2/v3 (bit-identical) | GR read +1–2 µs (down +14 %, up +7 %, norm −37 %) | ✘ | register pressure; biggest GPU item left (73 µs/layer, floor ~29) |
| 41 | `--spec-split` (overlap across two token groups) | T=2 windows +30 %, T=4 = ; RAM traffic +5 % | ✘ | GPU does dense + GR work twice |
| 42 | `--chat-cache 6` (patch 0007) replacing `--side-stash` | back to a 40K chat after a 64K paste 22.9 → 0.53 s; 64K chat 38.0 → 0.44 s | ✔ | parks conversations (checkpoints + host KV + indexer rows) in RAM |
| 43 | web app: chat list, file text kept (patch 0008) | QuickJS test 15/15 | ✔ | the page had one chat |
| 44 | **C\*3 = #35–39 + #42–43** | 32K −8.7 %, 120K −8.4 %, decode ~+2 %, switching ~0.5 s, TF within spread, soak 67/0 errors | ✔ | configs/Cstar3.json |

## Round 4 (2026-09-28): C\*3 → C\*4 (Strata v0.1.15)

Method: `work/r4/screen.sh` (1K×3, 32K, 64K, 120K + 768 decoded each, long reasoning math+code 8K, correctness ×5; sampled
via the config; fresh server, cold page cache), two alternating pairs C\*3/R4; exact decode by `generate --stats` profiles
(greedy windows); accuracy by teacher-forced NLL incl. a new 64K text, plus a llama.cpp reference (`work/r4/llama_tf.cpp`).

| # | change | result | kept? | why |
|---|---|---|---|---|
| 45 | Strata v0.1.12 → v0.1.15 + r3 patches 0001/0002/0005/0006/0007/0008 (R4) | prompt 1K −18 %, 32K/64K/120K −10 %; decode = (89.0 vs 88.6 tok/s all long requests; profiles 114.9 vs 112.0); TF short +0.0010/−0.0024 | ✔ | upstream's MMQ prompt path + next-layer expert streaming |
| 46 | r3 patches 0003 (batched PLE) / 0004 (next-chunk n-gram prefetch) | upstream v0.1.13 does both | dropped | prefer upstream |
| 47 | `--pool-workers 15` | upstream v0.1.14 counts physical cores: 15 workers | dropped | prefer upstream |
| 48 | `--prefill 8192` → `auto` | auto picks 8,192 here (2,405 slots lent) | ✔ auto | prefer upstream |
| 49 | patch 0001 off (STRATA_PLE_IO_THREADS=0 = upstream reader) | 32K 21.71 vs 15.73 s, 1K 1.6–1.8 vs 1.13 s | 0001 kept | one synchronous pread per row is still the limiter |
| 50 | `CUDA_MODULE_LOADING` EAGER (v0.1.15 default) → LAZY | VRAM free after load 321 → 568 MiB, after a request 220 → ~450 | ✔ LAZY | EAGER loads cuBLAS after the cache is sized (below the 300 MiB floor) |
| 51 | `--pcie-mode kernel` (default) vs `dma` | 114.9 vs 114.0/113.0 tok/s; 93.4 vs 93.5 at 32K | default kept | no measurable cost with pcie-frac 0 |
| 52 | GR kernels v4 (bit-identical, no smem staging) | down 24.2 → 33.0 µs, engine GPU wait +0.4 ms | ✘ | activation loads from L2 on the critical path |
| 53 | GR kernels v5 (down split over K, 164 blocks; norm in registers) | GR read −19–21 % (cold L2); decode +2.3 % (2 pairs); TF within spread | not in C\*4 | no sampled screen / soak (stall); configs/R4-gr.json |
| 54 | `--spec-split` with v5 | −8.5 % at 1K (2 runs), +3 % at 32K (1 run, more tok/window) | ✘ | still GPU-bound |
| 55 | **C\*4 = #45–51** | see REPORT "Round 4" | ✔ | configs/Cstar4.json |

## Round 5 (2026-09-28/29): C\*4 → C\*5 (Strata v0.1.24)

Method as round 4 (`work/r5/screen.sh` = round-4 screen + the chat-switch test; alternating fresh-server screens; exact
greedy `generate --stats` profiles; teacher-forced NLL incl. clipped NLL vs llama.cpp on the same IQ3_S file). The 5080
now carries only Strata (the desktop moved to the new 4060 Ti) → 4,560 expert slots instead of 4,337.

| # | change | result | kept? | why |
|---|---|---|---|---|
| 56 | v0.1.15 → v0.1.20 + C\*4 patches | prompts/decode = C\*4; TF bit-identical | ✔ (base) | upstream sampler-order and penalty fixes |
| 57 | `--calibrate` (v0.1.19) → `--pcie-frac 0.2` | beats the product default 0.55, not our 0 (89.5 vs 91.1/89.3 tok/s, same ms/window) | ✘ | only if it beats ours |
| 58 | EAGER (upstream default) re-checked on v0.1.20 | 321 MiB free after load, 208 after 32K | ✘ (LAZY kept) | unchanged in 0.1.24 |
| 59 | v0.1.21 layer split 5080 + 4060 Ti | does not start ("no room": 1.35 GiB / 2.50 GiB (0.1.22) left, 0 experts on CUDA1; predicted 38–39 ms/window vs 24) | ✘ | 8 GB second card |
| 60 | v0.1.21/0.1.22 helper cache (4060 Ti, 3,300 experts) | hit rate 75.7 → 86.4 %, but decode −4–5 %, prompts +22–25 % | ✘ | x4 link, low-ranked experts, 8 GiB pin limit |
| 61 | v0.1.22 (tensor-core prompt attention, thread-pool n-gram reads) | 32K 15.7 → 10.4 s, 120K 61.9 → 42.7 s; decode =; TF fine | ✔ | our 0001 dropped (upstream does it; STRATA_IO_THREADS=64) |
| 62 | v0.1.23 (#109 batched verify window) | exact decode +3.4 % (GPU wait 11.2 → 10.5 ms); bit-identical to our 0002/0003 on 6/7 texts | ✔ | our 0002/0003 dropped (upstream does both) |
| 63 | v0.1.24 (QSA selection on tensor cores) | 32K −3 %, 64K −8 %, 120K 42.6 → 36.7 s (−14 %); needles 72/72; long-text TF within the last-bit spread (vs llama.cpp mean −0.005) | ✔ (base) | |
| 64 | GR v5 on v0.1.24 (patch 0009) | −5 % time per verify window (sampled), +4 % exact; TF fine (mean −0.034 vs plain); needles 72/72 | ✔ | passed screens, accuracy, needles, soak |
| 65 | chat cache round trip (park/resume/edit), 0.1.20 / 0.1.22 / 0.1.24 | 0 changed tokens, NLL identical, drafter identical | ✔ | nothing to fix |
| 66 | Web search switch (SearXNG, server-side tool loop) | kernel/Python/news questions answered with sources; guard holds | ✔ | patches 0005/0006 |
| 67 | Stop during a prompt read (patch 0007) | idle 11.0 → 1.0–3.0 s after Stop | ✔ | server watches the socket |
| 68 | warm-up prompt at start (run-strata.sh) | 120K prompt with 32 MiB free: abort → completes | ✔ | first long prompt allocates GPU memory |
| 69 | two tabs (patch 0008) | chat list kept across tabs | ✔ | round-4 fix confirmed and applied |
| 70 | **C\*5 = #63 base + 8 serve/web patches + #64** | see REPORT "Round 5" | ✔ | configs/Cstar5.json |

## Round 6 (2026-09-29): C\*5 → C\*6 (experimental engine work)

Method: Phase A feasibility with a measurement build (NVTX/nsys, routing trace v2, microbenchmarks, trace-driven
replays; oracle and model estimates labelled as such), Phase B only the sure things, Phase C = 4 alternating fresh-server
A/B pairs (round-5 screen, your settings), web-replay chat, TF, needles, quality, failure tests, round trip, sampler
test, browser test, 2-h soak, rollback. Every experimental load under a memory guard (MemAvailable ≥ 20 GiB, 5080 ≥ 300
MiB free, from before the load).

| # | change | result | kept? | why |
|---|---|---|---|---|
| 71 | CPU-cache warming of the next layer's experts (microbench) | −36 % (T1) … −11 % (T4) of the pool's DRAM time; oracle 8.3 % of a window; causal 4–5 % (model) | ✘ | below the large-track bar |
| 72 | next-layer PCIe staging to VRAM (oracle / causal, model) | 13.6 % / 10.4–10.6 % (pre-MoE router, K=10); (a+b) oracle 14.7 % | ✘ (Round 7) | ceiling < 15 %, model-only (DMA contention unmeasured) |
| 73 | per-layer expert-cache budgets by time saved per byte (replay) | +1.1 / +1.4 / −0.6 % held-out | ✘ | noise-level |
| 74 | selective helper use (by layer / window size) | 4-token windows 23.38–23.83 vs 23.50 ms | ✘ | noise |
| 75 | n-gram rows read beside layer 0 (thread + GPU flag) | T4 −0.6 %, T1 +1.3 % | ✘ | the wait moved to the GPU |
| 76 | **n-gram rows of the next window's first token prefetched at commit** (patch 0012) | staging 0.61 → 0.28 ms/window; windows −1.0 … −3.7 %; bit-identical | ✔ | exact, beats noise |
| 77 | **helper GPU (4060 Ti, 3,300 experts) with the whole arena pinned on Linux** (patch 0011) | windows −2 … −3.5 % vs the 5080 alone; 32K prompt 10.88 vs 12.56 s with upstream's 8 GiB cap | ✔ | round 5's helper loss was the cap |
| 78 | `--dump-routing` accepted rows only (patch 0010) | 14.9 % double counts removed; verified against the engine's counters | ✔ | exact trace |
| 79 | **C\*6 = C\*5 + #76–78 + the helper** (A/B, 4 pairs) | decode all long requests 89.9 → 93.6 tok/s (+4.1 %), ms/token −3.9 %, reasoning +2.6/+4.1 %, prompts =, TF within spread, needles 72/72, round trip exact | pending | soak stopped at 43 min on your request (133 requests, 0 errors); not promoted yet |
