# Basalt's prompt path vs ours - code study and port (r23, Karl's item 2; written 11-04, nothing built or run)

Basalt 0.2.0 (f0bb833c, basalt-020/src) against our prompt path on branch r22-port0210 (v0.2.10 + 28 commits, fdd2fffa8;
the served P028x path is the same code at v0.2.8, gap 17: the pinned port is P028x bit for bit). The port is in the new
worktree `strata-r23basalt`, branch `r23-basalt-prompt`, 3 commits on r22-port0210, each behind its own switch, all off by
default. No build, no compile, no GPU run. The gate is in GATE-PLAN.md.

## 1. The answer in short

- **Most of the gap is chunk structure, not kernels we could copy.** Same lineage (Basalt forked Strata on 09-24), so the
  expert streaming, the fused/v2 expert kernels, the dense projections, the router and the staged walk are the same design
  on both sides. The differences that cost time are:
  1. **How a long prompt is cut.** We read 16,384-token chunks and a last chunk of the rest; Basalt reads up to 32,768
     tokens per chunk, in equal chunks, with a 16,384 first chunk for prompts above the cap. Basalt's fixtures land on our
     worst case: 16,676 = 16,384 + **292**, 66,617 = 4 x 16,384 + **1,081**. Such a rest (below our stream-all size of
     1,792) is a *staged* chunk: each layer's experts are copied only after its routing, and 292 tokens already route to
     ~510 of 512 experts per layer, so it costs about one more pass over the experts with almost no compute to hide it.
     Basalt reads 16K in 1 chunk and 64K in 3; we read 2 (one of them staged) and 5 (one staged).
  2. **Two lossy kernels** (not portable by our rule): the GDN prompt recurrence as a 16-token chunked delta rule on tensor
     cores with BF16 q/k (Basalt's own numbers: +5.0 / +5.6 / +6.2 % at 16.7K / 33K / 66K on a 5090), and int8-KV prompt
     attention as one FP16 MMA (+1.9 / +2.7 / +3.1 %).
  3. Smaller items: KV streaming of our 131K context beyond 32,768 resident cells (Basalt's fixture runs keep 66,661
     cells in VRAM), checkpoint saves at every 16,384, the fused hyper-connection up product.
- **Per stage, best estimate** (section 4; no per-stage profile exists for P028x or Basalt - the gate's first step measures it):

  | | 16K fixture (P028x 4.40 s vs Basalt 3.11 s, gap 1.29 s) | 64K fixture (15.29 s vs 12.24 s, gap 3.05 s) |
  |---|---|---|
  | staged rest chunk (292 / 1,081 tokens) | 0.5-0.7 s (40-55 %) | 0.35-0.6 s (12-20 %) |
  | chunk count beyond it (we 2 / 5, Basalt 1 / 3): fixed cost per stream-all chunk | 0.1-0.4 s (8-30 %) | 0.5-0.9 s (15-30 %) |
  | per-token: Basalt's lossy GDN + attention kernels | 0.15-0.25 s (12-20 %) | 0.7-1.1 s (23-36 %) |
  | KV streaming past 32K cells, checkpoints (5 vs 3), hc up product | 0.05-0.15 s | 0.15-0.5 s |
  | not explained | 0-0.3 s | 0-0.6 s |

- **Ported** (exact or rounding-level only; commits in section 6):
  - `STRATA_PF_AHEAD` (exact at =1) - Basalt 31aacda2: a staged chunk guesses the next layer's routing and copies its
    likely experts during the attention half.
  - `STRATA_PF_TAIL_SPLIT` (rounding-level) - after Basalt's equal chunks: the last chunk plus a staged rest of 256-1,791
    tokens become two near-equal stream-all chunks; the 16,384 checkpoint grid stays for everything before them.
  - `STRATA_PF_FIRST_CHUNK` (rounding-level) - Basalt e8f3b84b: with a chunk cap above 16,384 (a config arm), a long
    prompt reads 16,384 first and the rest in equal chunks, so the chat cache's checkpoints stay near their grid.
- **Expected** (GATE-PLAN.md section 7, estimates): the stack of the ported parts and the two Basalt-twin switches already
  in our tree (STRATA_HC_UPMIX, STRATA_CKPT_POOL) gives about **+7..+19 % at 16K** (a quarter to three fifths of the
  +32 %, in log ratio) and **+2..+9 % at 64K** (a tenth to two fifths of the +24 %), most of it from the tail split; with a
  raised chunk cap that fits our lend (+ PF_FIRST_CHUNK) instead of the tail split, **+13..+25 % / +5..+15 %**. On the
  9-workload screen only R4 (33,415 = 2 x 16,384 + 647) moves through the chunk plan; with HC_UPMIX the screen gains
  +0.5..+4 % of Basalt's +15 %. The rest of the gap is Basalt's two lossy kernels, the 32K chunks our buffers cannot
  hold, and what the profile has to find in our fixed cost per chunk.

## 2. What was read

- Basalt 0.2.0 source: src/prefill/ (run, stream, layer, gdn, qsa, routing, experts, expert_stream, expert_fused, ahead,
  combine, cpu_experts, layout, common, lifecycle, handoff), docs/precision/{index,features,gdn-split}.md, the engine logs
  of 11-02 / 11-03 (results/logs/man-*, serve-*.log), the commit log fb0944c7..f0bb833c (412 commits; the 41 prompt-path
  ones of results/r22/basalt-pr90/basalt-prompt-commits.txt, plus 0.2.0's: refactors only) and the commits before
  fb0944c7 that 10-21's notes-r2-codediff.md listed.
- Ours: strata-r22p0210/src/prefill/prefill.cpp (run_impl, carve, the staged and streamed walks, the CPU share),
  src/program/generate.cpp (the serve lend, the chunk choice, checkpoints), the P028x / P0210x-h configs and engine logs.
- Timing: gap 17's bp90 cold fixtures (results/r22/gap17/bp90, logs/engine-x28h.log: per-prompt totals), gap 17's screen
  (speed-table.md), Basalt's 11-02 / 11-03 runs (basalt-020/results: per-prompt totals, the --prefill 8192 / 32768 and
  --prefill-cpu-share tries), Basalt's commit messages (5090 + 5060 Ti measurements), basalt-ab/notes-r2-codediff.md.
  **Neither side has a per-stage prompt profile of these runs**: Basalt 0.2.0 has no prompt timing switch, and
  STRATA_PREFILL_TIMING was last run in round 15 (another pack and build). Section 4 is therefore a fit plus arithmetic.

**Licence.** Basalt is MIT, "Copyright (c) 2026 Jesús Gulfo" (basalt-020/src/LICENSE); its THIRD_PARTY_LICENSES lists
Strata (MIT, Niko1221 and contributors) and ggml / llama.cpp (MIT). Basalt's gdn_chunked.cu, its int8 prompt attention
and its FP4 GEMM adapt Apache-2.0 code (Infernix) - none of those is ported. Our three commits are ideas and control flow
re-implemented on our code, with the attribution in each commit message and in prefill.cpp beside each switch.

## 3. The gap that is left

After gap 17 (v0.2.10's GDN paths failed KL, nothing recovered), against Basalt 0.2.0 at its defaults on the 5080 alone:

| prompt | P028x | Basalt 0.2.0 | Basalt vs us | our chunks | Basalt's chunks |
|---|---|---|---|---|---|
| 1,370 (B-write) | 0.83 s | 0.7 s | +17 % | 1 staged (CPU share 0.4) | 1 MMQ (CPU share 0.6) |
| 2,678 (A-edit) | 0.98 s | 1.0 s | 0 % | 1 stream-all | 1 MMQ + share |
| 5,011 (R3) | 1.40 s | 1.3 s | +5..8 % | 1 stream-all | 1 MMQ + share |
| 16,676 (bp90 16K) | 4.37-4.45 s (3,783-3,827 tok/s) | 3.11 s (5,350-5,365) | +32 % (means) / +40 % | 16,384 + **292 staged** | 1 |
| 24,241 (R1) | 5.47 s | 4.49 s (client clock) | +23 % | 16,384 + 7,857 | 1 |
| 26,728 (W3) | 5.97 s | 4.8-5.0 s | +22 % | 16,384 + 10,344 | 1 |
| 33,416 (R4) | 7.78 s | 6.1-6.2 s | +26 % | 2 x 16,384 + **648 staged** | 16,384 + 17,032 |
| 54,070 (R2) | 11.97 s | 9.9 s | +21 % | 3 x 16,384 + 4,918 | 16,384 + 2 x 18,843 |
| 66,617 (bp90 64K) | 15.28-15.30 s (4,354-4,360) | 12.21-12.25 s (5,438-5,454) | +24 % | 4 x 16,384 + **1,081 staged** | 16,384 + 25,344 + 24,889 |

Rates are the engines' own (prompt_n / prompt_ms); our side is x28h (P028x without pictures: 5080 + 4060 Ti, 131,072
context, KV int8 with 32,768 cells resident, --prefill auto:16384, CPU share 0.4 up to 1,792 tokens); Basalt's is its
preset (66,661 context, KV int8 all in VRAM, auto chunk 32,768, CPU share 0.6 below 6,144 tokens). The 4060 Ti does not
help our prompts (11-03: x28h-solo read them 1 % faster), so the comparison is fair on that point.

Basalt's own chunk tries (11-02, one pass each): --prefill auto:8192 made its 16K 4,025 tok/s (-25 %: 3 chunks of 5,559,
all below its 6,144 stream-all size) and its 64K 4,870 (-10.5 %: 9 chunks); auto:32768 = its default. So Basalt itself
loses most of its 16K lead when it reads in small chunks.

## 4. Where the time goes (per stage, estimated)

**A two-term fit per engine** (scratch: work/r23/basalt-prompt/scratch/fit.py, the points above >= 5K tokens):

- Basalt: t = 26-190 ms per chunk + 0.175-0.182 ms per token (both fits within 1.4 % on its five points). Its chunk cost
  is small: a stream-all chunk's expert copies run behind its compute.
- Ours: the data cannot separate the terms well (our chunk count rises with the length). The physically split fit (a
  stream-all chunk, a staged rest, tokens) gives **~370 ms per stream-all chunk, ~700 ms per staged rest, 0.195 ms per
  token** (within 3.8 % on seven points). Other two-term fits: 574 ms/chunk + 0.183 ms/token, or 1,000 ms/chunk -
  340 ms + 0.157 ms/token. All agree on the shape: our fixed cost per chunk is several times Basalt's, a staged rest
  costs most, and our per-token cost is 5-12 % above Basalt's.

**The staged rest** (16K: 292 tokens, 64K: 1,081). From the routing statistics alone: 292 tokens x 10 experts spread
over 512 reach 1 - (1 - 10/512)^292 = 99.6 % of a layer's experts; ~28 per layer stay resident during a prompt (the loan
takes 3,231 of 4,585 slots), so ~480 are fetched per layer. The CPU share takes 40 % of them (the ones with the fewest
rows, at ~44 GB/s of expert bytes, 11-03 log), the link the other ~290 x 2.05 MB = ~0.6 GB a layer = ~10 ms at 57.8 GB/s,
x 48 layers = **~0.5 s**, plus a routing sync and host grouping per layer with the link idle (~1-3 ms a layer). The fit's
~0.7 s matches. Basalt never has such a chunk at these lengths.

**The chunk count.** Every stream-all chunk sends every non-resident expert once (~47 GB at 57.8 GB/s = ~0.8 s),
behind its compute. What stays exposed per chunk is the first layer's copies, the chunk end (a stream sync, the MTP draft
K/V of the chunk, a checkpoint save every 16,384 tokens: sync + ~118 MB of running state, STRATA_CKPT_POOL would skip its
zero-fill), and the PLE rows of the first chunk. Basalt pays the same kinds of costs, only fewer times (and smaller per
chunk in the fit). 16K: we pay one extra stream-all chunk only after a tail split (today the extra one is the staged rest);
64K: 4 stream-all chunks + the staged rest vs Basalt's 3.

**Per token.** Basalt's chunked GDN on tensor cores (lossy: BF16 q/k and a BF16 copy of the correction for one product;
2.9e-3 relative RMS against its previous FP32 kernel; KLD 0.0687 -> 0.0706 on its quality gate) and its one-MMA FP16
int8-KV attention (1.5e-3 of the output scale vs 1e-6 before) are worth +5..6 % and +2..3 % on a 5090 by Basalt's own
ABBA runs; on the 5080 (84 SMs; the GDN scan runs in waves) probably a little less. That accounts for most of the 5-12 %
per-token difference. The attention part grows with the context (the indexer scores every earlier block), which is why
our marginal cost per token rises faster past 32K (0.18 -> 0.21 ms vs Basalt's 0.175 -> 0.186).

**KV streaming** (ours only, a config choice: 131,072 context, 32,768 cells resident). A QSA layer of every chunk after
the first stages its K/V prefix [0, p0) from host memory on the compute stream (12 QSA layers, ~1.4 KB a cell and layer):
64K: 16K + 33K + 49K + 66K cells x 12 x 1.4 KB = ~2.8 GB over the same link as the expert stream, ~0.05-0.15 s.
16K: ~5-10 ms. Basalt's fixtures ran with every cell in VRAM.

**Not a difference:** the fused / v2 expert kernels (ported 10-21, bit-identical to ours since fdd2fffa8; v2 is in
P028x), the streamed walk and its issuer thread (identical code), the ring (ours 512 slots, Basalt 256 for fused chunks:
ours holds a whole layer), dense projections (FP16 dequant + cuBLAS; STRATA_DEQUANT_WIDE = Basalt's bae903f8, on in
P028x), the router (BF16 activations on both), the shared expert (FP16), the head (runs once per prompt), the PLE gather
(the same double-buffered SSD read; --ple-inflight 256 measured 0 % here on 10-21).

## 5. Stage by stage: Basalt's version, classification, what it needs on sm_89

Classification: **exact** = bit-identical outputs; **rounding-level** = the same math in another order or geometry
(acceptable only through our KL yardstick rule); **lossy** = lower precision, skipped work or an approximation (not
ported). The prompt path runs on the 5080 (CUDA0, sm_120) in every config we serve; the 4060 Ti (sm_89) only holds decode
helper experts and takes no part in a prompt (its experts are streamed from RAM like any other non-resident one).

| stage | Basalt 0.2.0 | ours (P028x) | class | sm_120-only? / sm_89 | ported |
|---|---|---|---|---|---|
| chunk cap | 32,768 for blobs > 1.5 MB (our IQ3_S pack: 2.66 MB), lend <= 90 % of the cache | --prefill auto:16384 (config) | rounding-level (chunk geometry) | host only | config arm (GATE-PLAN C) |
| chunk plan | equal chunks of at most the cap; prompts above it start with 16,384 (e8f3b84b) | 16,384 chunks, the rest last; STRATA_PREFILL_EQUAL (#693) evens out only rests >= the stream-all size and moves the 16,384 checkpoints (dropped in round 11) | rounding-level | host only | **STRATA_PF_TAIL_SPLIT**, **STRATA_PF_FIRST_CHUNK** |
| prompt buffers | hc rows inside the shared scratch region (ecf5157f); 256-slot fused ring; ~228 KB a token + ring | hc rows outside the region (~62 KB a token more); 512-slot ring; ~305 KB a token + ring: 3,231 slots for 16,384 vs Basalt's 4,068 for 32,768 | exact (placement) | - | not re-ported: = our STRATA_PF_HC_REGION, which failed exact7 3/7 with v2 in gap 17 (prompt logits 40/40 identical); gap 19 diagnoses it |
| stream-all size, CPU share | stream every expert from 6,144 tokens; below it the CPU pool takes a fixed 0.6 of the non-resident experts, fewest rows first | from 1,792 (STRATA_PREFILL_CPU_SHARE_MAX), share 0.4, same selection | rounding-level (CPU vs GPU rounding) | host + CPU | settings arm (GATE-PLAN optional): share 0.4-0.6 x max 3,072-6,144 |
| staged chunk copies | the next layer's router on this layer's FFN rows; experts with > 8 guessed rows copied ahead into their own slots during the combine and the next attention half (31aacda2) | copies after the routing sync only (8 in flight) | **exact** (where the slot exists) | host + one cuBLAS GEMM on CUDA0 | **STRATA_PF_AHEAD** |
| streamed walk, ring, issuer | issuer thread, fused batches of ring/3, deep ring 384 only for unfused chunks >= 16,384 (e9bea488) | the same code; ring 512 | - | - | nothing to port |
| GDN recurrence | 16-token chunked delta rule on TF32/BF16 tensor cores, BF16 q/k (1d1159aa, from Infernix) | token-by-token FP32 (gdn_rec_kh); STRATA_GDN_TC (failed KL, gap 17); STRATA_GDN_CHUNKED (FP32 WY chunks, within 1e-4, needs 128 SMs, =2 skips the check; never run here) | Basalt's: **lossy**; our GDN_CHUNKED=2: rounding-level | GDN_CHUNKED: cc 8.0+, the 5080 only | not ported; GDN_CHUNKED=2 is a pricing arm |
| QSA attention (int8 KV) | q and p rounded to FP16, V scale in the FP16 B operand, one FP16 MMA (f04e956a) | FP32-level split (default); STRATA_PROMPT_ATTN_IMMA (3 int8 MMAs, failed top-1 104/120 vs 108) | Basalt's: **lossy** | - | not ported |
| QSA indexer scores | 3xTF32 tensor cores | the same (qsa_select) | - | - | - |
| hc read: weights | down/up from the int8 copy dequantized to BF16 (the copy is always on) | BF16 tensors (STRATA_HC_REQ8 off) | Basalt's: **lossy** (and no faster: the GEMM still takes BF16) | - | not ported |
| hc read: up product + mix | one kernel from 33 tokens (10f338cc), "the same bits as the two steps" | two steps; STRATA_HC_UPMIX=1 is the same fusion, upstream: bitwise on CUDA sm_80+ from 33 tokens (5090) | exact if the 5080's cuBLAS sums k in the kernel's order (to verify) | the 5080 only | switch arm U (no code) |
| router, shared expert, dense projections | BF16 router input, FP16 shared expert, FP16 dequant + cuBLAS, 16-byte dequant stores | the same; DEQUANT_WIDE on | - | - | - |
| routed experts | fused int8 + v2 IQ3_XXS/IQ4_NL kernels, MMQ below 6,144 | the same (v2 ported, bit-identical to v1 since fdd2fffa8) | - | v2 needs cc 8.0+ and 99,856 B shared memory per block (5080 only in the prompt path) | done 10-21 |
| KV of a long prompt | elastic KV: all of the fixture's cells in VRAM, taken from the expert cache's tail (270 slots) | KV streaming past 32,768 cells: each later chunk's QSA layers stage the K/V prefix on the compute stream; STRATA_KV_PREFETCH=1 stages the next layer's on its own stream | Basalt's: exact for the K/V, moves expert placement (rounding-level for decode); KV_PREFETCH: exact by design | - | not ported (decode + memory feature); KV_PREFETCH arm |
| checkpoints | pooled buffers, GDN state copied device to device then to the host on a helper (f0f637c4, 426f552f) | a sync + a fresh ~118 MB image at every 16,384 tokens and the end; STRATA_CKPT_POOL(+_READY) reuses / pre-allocates the images | exact | host | switch arm K |
| a second card in the prompt | the peer tier reads later layers of long chunks (6f354bae ... 8ae0d95b); a slower peer takes only routed-only chunks up to 2,559 tokens (652b9515) | none (x28h-solo: the 4060 Ti adds nothing to prompts) | exact on the same card model; rounding-level across models | Basalt's peer code is sm_120-only (the build's #error); for the 4060 Ti it would need sm_89 prompt kernels (MMQ / fused) and a host-staged path | not ported (large; a later candidate for staged chunks: the 4060 Ti's 3,300 experts are 13 % of the link traffic there) |
| first token | sampled from the last prompt window (3d48edbc) | a separate step | (decode side) | - | not studied (it moves W1/W2's client-clock prompt rate, not the prompt path) |
| layer-major walk | none | STRATA_PREFILL_LAYER_MAJOR (0.2.7; pinned 0; never measured here): each expert once per super-chunk | rounding-level | - | not Basalt's; listed for later (it attacks the same per-chunk cost at 64K) |

## 6. The port (worktree strata-r23basalt, branch r23-basalt-prompt)

| commit | switch | class | what |
|---|---|---|---|
| 2bfc94694 | `STRATA_PF_AHEAD=1` (`=2`, `_MAX=N`) | =1 exact; =2 rounding-level through the CPU share | Basalt 31aacda2 on our staged walk. Each MoE half of a staged chunk runs the next layer's router on its own FFN rows (into the free logits, own ids/weights, a mapped host copy read after the grouping sync); at the combine the experts with > MAXT (8) guessed rows, not resident and page-locked, are copied most-rows-first into staging slots past STAGE_GRP, one set per layer parity; the next layer's stage_one takes them in place. =1 uses only slots the layout holds (a long prompt's tail inside its 512-slot stream-all layout: up to 112 per parity), so the loan is unchanged. =2 also gives a short prompt's staged layout Basalt's 32 + 2 x min(64, T/32) slots (stage_slots(), so bytes_needed agrees). The group gather's one wait (on its last staged copy) does not cover an ahead copy queued earlier: the walk waits on each ahead slot and the flush releases them with the group. No ahead copies for a QSA layer whose K/V streams from the host, a multi-GPU prompt path or KVA. Lines: one at init, one per prompt ("N experts copied ahead ..., M read in place"). |
| 358e5df3f | `STRATA_PF_TAIL_SPLIT=1` (`=N`) | rounding-level | A run that plans its own chunks and would end in a staged rest of 256 (or N) to 1,791 tokens reads the chunk before it and the rest as two chunks of ceil((C + rest)/2) rounded up to 256 and the remainder, both stream-all. Earlier chunks stay 16,384, so the periodic checkpoints before them stay; the one at the last grid point moves to the end. `chunk_len(at)` is now the one source of a chunk's length (loop, T, PLE gather and its prefetch, the DBG_NAN row). Off: min(C, n - at), today's chunks exactly. 16,676 -> 8,448 + 8,228; 66,617 -> 3 x 16,384 + 8,960 + 8,505; 33,417 -> 16,384 + 8,704 + 8,329. |
| 3383d1f8d | `STRATA_PF_FIRST_CHUNK=1` (`=N`) | rounding-level | For a chunk above 16,384 only (a raised --prefill auto:N): a longer prompt reads 16,384 first, then equal chunks of at most the chunk (rounded up to 256). 66,617 at 20,480: 16,384 + 3 x 16,896 + 16,441 -> checkpoints at 16,384 / 33,280 / 50,176 / end instead of 20,480 / 40,960 / 61,440. A no-op at the served 16,384. Takes precedence over the tail split. |

All three: one file (src/prefill/prefill.cpp, +292 / -13 lines), host code plus one extra cuBLAS GEMM and two existing kernels
(route, copy_i32) for PF_AHEAD; no new device code, nothing for sm_89. Each reads its variable once; unset or 0 runs
today's path (every new branch is behind ahead_n > 0, is_ahead(), tail_at >= 0 or first_len > 0).

**What the build must verify** (nothing was compiled):
1. It compiles in the CUDA build (CUDA 13.3, `-DCMAKE_CUDA_ARCHITECTURES=89;120`, -Wall -Wextra) with no new warning:
   the lambdas' captures (`chunk_len` by value into `ple_gather`, which runs on a std::async thread; `copy_ahead`,
   `is_ahead`, `gg_take` by reference), `m.guess_ids = m.guess_host = m.guess_host_dev = nullptr` (all int32_t*),
   `std::min<int>(m.ring_room_at, ring_cap())`, the `if (init; cond)` forms, the int64_t/int mixes in `stage_slots`.
2. With every switch unset the engine is P0210x-h bit for bit: exact7 7/7 and 40/40 byte-identical long40 logits.
3. PF_AHEAD=1 is bit-identical to off on prompts with a staged tail and prints "M read in place" with M > 0; with
   compute-sanitizer (racecheck/synccheck, one 16,676-token prompt, optional) no hazard on the ahead slots.
4. PF_TAIL_SPLIT / PF_FIRST_CHUNK print their plan lines with the chunk sizes above, and the engine's "N checkpoints" and
   STRATA_TRACE's "checkpoint at L" lines show the grid described.
5. PF_AHEAD=2: the startup lend line ("the prompt path borrows N slots") is unchanged for the auto chunk (a stream-all
   layout) and a short prompt's relayout borrows Basalt's extra slots (64-128 more at 1-2K tokens).
6. HIP is not built here; upstream's rules would need a HIP build of prefill.cpp before anything were posted (nothing is).

## 7. Not ported, and why

- Basalt's chunked GDN (BF16 q/k) and one-MMA FP16 attention: lossy. Our rounding-level counterparts are already in the
  tree: STRATA_GDN_CHUNKED=2 (FP32 chunked; unmeasured on 84 SMs, upstream expects it slower there - a pricing arm) and
  STRATA_PROMPT_ATTN_IMMA (failed top-1, backlog D3).
- The int8 hyper-connection copy in the prompt path: lossy, and not faster for the prompt (the GEMM still runs in BF16).
- 32,768-token chunks: our buffers hold ~16-22K tokens in the 90 % lend (estimate: (7.83 - 1.33) GiB / ~305 KB a token
  = ~21,900 tokens); 32K needs the lean layout (PF_HC_REGION, blocked on gap 19) and is then still at the lend's edge. The
  gate tries the largest chunk the scan fits (auto:24576) with PF_FIRST_CHUNK.
- The peer-tier prompt reads: a large port for a card that is slower than the 5080 and holds 13 % of the experts.
- Elastic KV: a memory / decode feature (it moves expert placement), not the prompt path; STRATA_KV_PREFETCH covers part
  of the cost it removes, exactly.
- Basalt's FP4-expert and batch-slot prompt commits (a2d9f07b, ebf6928b, 8a705207, 8ef87f76, 554995aa, ...): other packs / parallel serving.

## 8. Open questions for the gate

- Our fixed cost per stream-all chunk (fit: ~370 ms, Basalt's ~30-190 ms) is the largest unexplained term. Whether it is
  the chunk end (sync, MTP draft K/V, checkpoint), the first layer's copies, the PLE wait or the KV prefix staging can only
  be read from STRATA_PREFILL_TIMING=1 + STRATA_TRACE=1 on the two fixtures (GATE-PLAN step A1). If it is the checkpoint,
  STRATA_CKPT_POOL recovers it exactly; if it is the KV prefix, STRATA_KV_PREFETCH.
- Whether a split rest really costs a stream-all chunk's ~0.1-0.4 s and not more: the tail-split arm measures it directly.
- The chat-cache trade of the tail split: a follow-up that shares more than the last grid point but not the whole prompt
  reads from the grid point before it (16K: from 0). --prompt-cache-tail would add a checkpoint at the moved boundary.
