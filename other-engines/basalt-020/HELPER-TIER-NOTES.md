# Basalt 0.2.0: adding the RTX 4060 Ti (sm_89) as an expert tier - plan notes (11-02)

Read-only survey of `basalt-020/src` at v0.2.0 (f0bb833c). Nothing was built, run, changed or downloaded. Paths below
are relative to `basalt-020/src/`. Hardware facts come from a read-only nvidia-smi query: 5080 = sm_120, 16,303 MiB,
Gen5 x16, 960 GB/s. 4060 Ti = sm_89, 8,188 MiB, Gen4 x4 (the card supports x8), 288 GB/s. Run facts come from
`results/logs/man-probe-1-dec/engine.log`.

## 0. Bottom line

- Basalt already has a peer-card expert tier (`--gpu 0,1`). It assumes no P2P (everything goes through pinned or
  mapped host memory) and already has rules for a slower peer. **The only blockers are the architecture checks and
  the missing sm_89 device code.**
- For the IQ3_S pack and this pair of cards, the tier card runs only expert math: one persistent decode kernel and,
  optionally, MMQ for short prompts. The GDN split, the head split, the prompt split and the FP4 path all stay off.
- **Minimum change set:** sm_89 code for one TU (`iq_kernels.cu`), plus `elementwise.cu` for the fallback path.
  About 6 guard sites for sm_90-only instructions. Relax the card checks. Add a per-device code check. Add a
  cross-device bitwise test. Overall size: **medium**. Upstream will not take it (CONTRIBUTING.md:7 says Blackwell
  only), so it stays a local patch that has to be carried to every new release.
- **Lossless:** decode is very likely bitwise-equal to the 5080 once compiled (integer dot products, IEEE ops, no
  dependence on SM count). Two things still need a test: `__expf` (MUFU.EX2) and FMA contraction across
  architectures. The prompt share (MMQ) is **not** placement-invariant (stream-k depends on the SM count), so
  phase 1 runs decode only, with `--peer-prefill-rows 0`.
- **Room on the 4060 Ti:** about 3,500-3,700 slots (real average 2.05 MB per expert), which is 14-15 % of the 24,576
  experts. Basalt's own price model gives decode **+8-9 %** (217 -> ~235 tok/s), before link costs. Prompts of
  16K/64K are **unchanged**.

## 1. Where Basalt refuses non-sm_120 cards

| Stage | File:line | What happens / the message |
|---|---|---|
| CMake default | CMakeLists.txt:3-4 | `CMAKE_CUDA_ARCHITECTURES 120` (CACHE FORCE when unset) |
| CMake check | CMakeLists.txt:40-46 | any arch whose base is not 120 -> `FATAL_ERROR "CMAKE_CUDA_ARCHITECTURES is '89;120': basalt builds for compute capability 12.0 only"` |
| CMake, FP4 lib | CMakeLists.txt:1308-1309 | `fp4` target pinned to `120a-real` (block-scaled FP4 MMA) |
| MMQ device code | src/prefill/mmq/mmq_common.cuh:28-30 | `#error "the MMQ kernels are built for compute capability 12.0 only"` for `__CUDA_ARCH__ < 1200` |
| Card enumeration | src/program/gpu_select.cpp:66-111 | NVML lists the cards and reads the compute capability (`nvmlDeviceGetCudaComputeCapability`, :77/:96) |
| Support rule | gpu_select.cpp:136 | `gpu_supported`: cc 12.0, or unknown |
| `--gpu 0,1` | gpu_select.cpp:148-151, 207-210 | error `gpu: GPU 1 (RTX 4060 Ti) is sm_89, not sm_120` |
| `--gpu auto` | gpu_select.cpp:158-163 | note `gpu auto: GPU 1 (RTX 4060 Ti) skipped, not sm_120` |
| unset | gpu_select.cpp:181-195 | GPU 0 alone. The 4060 Ti is not even named in the "unused" warning |
| Callers | cli/gpu.cpp:28-33 (engine, via configure.cpp:14); bench_main.cpp:736; probe_main.cpp:250; serve/server.py:113 (calls the engine's `--gpu-plan`) | all share the same rule |
| Main-card code check | src/program/generate/sources.cpp:26-49 + core/device.cu:110-117 | `poison_kernel` probe, **device 0 only**: "this engine has no code for ... rebuild it for this card". The comment at device.cu:111 assumes every .cu file is built for one arch |
| basalt-device tool | core/device.cu:151-155 | "device ... reports compute capability 8.9; basalt needs an NVIDIA GPU of compute capability 12.0" |
| Per-kernel runtime gates (main card) | hc_fused.cu:1205 (`major == 12`); pdl.hpp:95 (>= 9, falls back to a plain launch); iq_kernels.cu:2564/2588, native_mmvq.cu:1489, moe_fused.cu:369, moe_fused_iq.cu:889 (>= 8); sampler.cu:1580/1623, qsa_select.cu:1135 (>= 9, cluster) | sm_89 already passes the >= 8 gates |

## 2. The build

- **Today:** one architecture, `120`, which CMake expands to sm_120 SASS plus compute_120 PTX. PTX only JIT-compiles
  forward, so the 4060 Ti cannot use any of it. CUDA 13.3 is required (CMakeLists.txt:47) and supports sm_89. There
  are no arch-specific compile definitions. `--use_fast_math` is set per file (CMakeLists.txt:262-280, the native_*
  and head kernels) and on the `mmq` library (:1300); `iq_kernels.cu` is **not** fast-math.
- **Libraries:** no CUTLASS. cuBLAS is used only for the prompt path's dense GEMMs (prefill/gemm.cu, cublasGemmEx
  BF16/FP32) and for the vision encoder, both on the main card. cuBLAS ships sm_89 code, so nothing is needed there.
- **Recommended fat build: per-TU, not global.**
  - Leave `CMAKE_CUDA_ARCHITECTURES=120`.
  - Add `--generate-code=arch=compute_89,code=sm_89` only to the TUs the tier runs, through
    `set_source_files_properties(... COMPILE_OPTIONS ...)`, or by moving them into a small target with
    `CUDA_ARCHITECTURES "89-real;120"`:
    - `src/kernels/cuda/iq_kernels.cu`, which includes gu2.cuh, dec_gdn_rec.cu (device part), dec_moe.cuh and
      pk_moe.cuh (iq_kernels.cu:2642, 2892-2896);
    - `src/kernels/cuda/elementwise.cu` (`scatter_rows_f32`, fallback path only);
    - phase 2 only: the `mmq` library.
  - Leave `fp4` at `120a-real`.
  - A global `89;120` would instead mean guarding about 12 main-card TUs that use TMA, clusters or griddepcontrol
    (hc_fused, dense_tc, mid_chain, qsa_mid, attn_chain, dec_gdn_rec, verify_kernels, sampler, qsa_select,
    gdn_chunked ...) for no gain.
- **sm_120 code must stay byte-identical.** Every guard is a no-op for `__CUDA_ARCH__ >= 900`. Check with
  `cuobjdump -sass` that the before/after sm_120 output matches, so Basalt-alone numerics do not move.
- **Binary assumptions to fix:** `device_code_error()` probes one kernel on device 0 only (device.cu:110-117).
  Mixed per-TU archs need a per-tier-device probe on the kernels the tier launches (for example
  `cudaFuncGetAttributes(dm_peer_kernel...)` with the tier card current). Without it, a missing image shows up late
  as `cudaErrorNoKernelImageForDevice`, or `dec_moe_peer_blocks()` silently returns 0 (dec_moe.cuh:2410-2419).

## 3. Kernels

### 3a. Device code that needs sm_90+ or sm_120

| Feature | Where | Guarded / fallback |
|---|---|---|
| Block-scaled FP4 MMA `mma.sync...kind::mxf4nvf4.block_scale.scale_vec::4X.m16n8k64...e2m1...ue4m3`, `cvt.rn.satfinite.e2m1x2.f32`, `__nv_fp8` | prefill/fp4/moe_fp4.cu:51, :156 | none (120a only). NVFP4 packs' prompt experts only. Not used by IQ3_S (`fp4_every_layer`, layout.cpp:172-184) |
| TMA tensor maps, `cp.async.bulk(.tensor)`, `mbarrier...expect_tx`, `fence.proxy.async` | hc_fused.cu:162-230 (+ runtime gate :1205); dec_moe.cuh:1854-1977 (`dm_vram_tma_kernel`); mid_chain.cu, attn_chain_kernel.cuh:67-117, verify_kernels.cu:575 | hc: plain hc read fallback; dense_tc.cu / qsa_mid.cu / attn_chain:119 have `>= 900` guards. **dec_moe.cuh TMA is unguarded and sits in the tier's TU** |
| Clusters / DSMEM (`__cluster_dims__`, `barrier.cluster`, `mapa`, `cg::cluster_group`) | dec_gdn_rec.cu:205, 317, 340, 355; sampler.cu:184-334; qsa_select.cu:740-1002 | sampler / qsa_select: `>= 900` guards with fallbacks. **dec_gdn_rec.cu is unguarded and is included in iq_kernels.cu** |
| PDL `griddepcontrol` | pdl.hpp:66-77 (guarded); gu2.cuh:346, 369 (unguarded, tier TU); dec_gdn_rec.cu:203 (unguarded); mmq_common.cuh:78-84 via `cudaGridDependencySynchronize` in quantize.cu:25 (unguarded) | host side: `launch_pdl` checks cc >= 9 (pdl.hpp:81-106), but `launch_dependent` (gu2.cuh:393-405) sets the programmatic attribute unconditionally |
| wgmma (sm_90a), tcgen05 (sm_100a), setmaxnreg | none in the tree | - |
| `__CUDA_ARCH__ >= 1000/1200` | only the MMQ `#error` (mmq_common.cuh:28) | the MMQ code itself is Ampere-class |

Generic code that compiles for sm_89 as-is: int8 `mma.sync m16n8k32/k16 s8` (iq_kernels.cu:1520-1890 with a dp4a
`#elif`; native_mmvq; moe_fused*; mmq/mma.cuh), f16/bf16/tf32 mma, `ldmatrix` (sm_75+), `cp.async` (sm_80+), dp4a,
`prmt`/`funnelshift`, cooperative launch, `%globaltimer`, `__grid_constant__`.

### 3b. What the tier would run (IQ3_S pack, 4060 Ti as tier)

Routing and top-k always run on the 5080: `dm_route_kernel` splits entries by the residency tables `res0`/`res1`
(dec_moe.hpp:1-10). The tier does no routing.

| Path | Kernels on the tier card | Status for sm_89 |
|---|---|---|
| Decode, device-planned tail (default, on for our formats) | `dm_peer_kernel<Q2,false>` (dec_moe.cuh:1594; gate/up via `gu2::pair`, down via `dm_down_item`, SwiGLU `dm_swiglu_q8`:1010-1020, L2 warm-up `dm_warm`:1364); `dm_table_put_kernel`, `dm_zero_words_kernel` (:2436-2445) | the code compiles as-is, but the TU needs guards on: gu2.cuh:346/369; the dec_gdn_rec.cu include (iq_kernels.cu:2892-2894); the `MIX=true` branch (dec_moe.cuh:1637-1706) and its instantiations (:2405-2407); the TMA kernel (:1854-1977) |
| Decode fallback (pool-thread path, `PeerExperts::launch`, peer_experts.cpp:223-291) | `quantize_q8_1_kernel` (iq_kernels.cu:2161/2731); `native_expert_grouped` chain: `native_gu2_kernel`, `swiglu_q8_1_entries_pdl_kernel`, `native_down_multi_kernel<TD,true>` (iq_kernels.cu:2838-2888); `scatter_rows_f32` (elementwise.cu) | same guards, plus `launch_dependent` making a plain launch when cc < 9 |
| Prompt share, routed-only chunks <= 2,559 tokens (slower peer; layout.hpp:69, peer.cpp:152-185, prefill/peer_experts.cpp:105-186) | `mmq::gather_native` copy kernels (moe_mmq.cu:25-60), `quantize_mmq_q8_1` (mmq/quantize.cu), `mul_mat_q<IQ2_S/IQ3_XXS/IQ3_S/IQ4_XS/IQ4_NL/Q2_0>` + `mul_mat_q_stream_k_fixup` (mmq.cuh:799-870), `swiglu_kernel` and `iota_kernel` (moe_mmq.cu:94, 114) | remove `#error` (mmq_common.cuh:28), guard the PDL calls (:78-84). Tile configs are the Ampere ones, and the shared memory per block is 99 KB on both cards. **Rounding issue: see 5b** |

These do **not** run on the tier for this pair or pack:
- GDN mixer split: 288/(960+288) = 0.23 is under the 1/4 floor (gdn_split.cpp:44-49).
- Head split: the Q6_K head is excluded (head_split.cpp:26), and the two-stage split needs a Q8_0 head (:51).
- Prompt split (whole layers on the tier): NVFP4 only (generate/prompt_split.cpp:32-35).
- FP4 experts: NVFP4 only.
- The PCIe "staged share": needs no peer and one blob size (expert_resources.cpp:203-205). It is already off for
  our mixed pack.

## 4. The existing peer tier (`--gpu 0,1`)

- **Roles:** the first card is main; later cards are expert tiers, up to 3 (gpu_select.cpp:221-228; cli/gpu.cpp:43-61;
  configure.cpp:14). The process sees the chosen cards in `CUDA_DEVICE_ORDER=PCI_BUS_ID`, main first
  (gpu_select.cpp:290-299). The tier must be device >= 1 (peer_experts.cpp:140).
- **What lives where:**
  - Main card: dense weights, KV, MTP, its own adaptive cache, the verify graph (peer_experts.hpp:3-13).
  - Peer card:
    - expert slots in 512 MiB VMM segments (peer_experts.cpp:181);
    - small staging and scratch;
    - DEC_MOE extras: blob-address table, layouts, scratch, an int8 router copy for the L2 warm-up (~63 MB)
      (expert_resources.cpp:117-141);
    - optional: about 200 MiB of prompt-share buffers, and GDN or head rows when the peer is faster.
- **Placement:**
  - The ranking comes from the profile (`data/profiles/qwen4exp-48x512.prof`). The main card takes the top slots.
  - A slower peer (`mem_gbps < 0.9 x main`, model.cpp:177-180, which the 4060 Ti is) takes the next ranked pairs
    that fit. Its budget is free VRAM - (`--peer-reserve-mib` 600 + split bytes + prompt bytes)
    (resident_plan.cpp:76-91; peer_experts.cpp:107-128).
  - An equal or faster peer gets 45 % of the hot pairs instead.
  - Several tiers are dealt out by bandwidth (`spread_experts`, gpu_select.cpp:230-256).
  - Slot size = blob rounded up to 256 B, sized per layer (peer_experts.cpp:130-134).
- **Movement:**
  - `adapt`: each round swaps the most-routed CPU experts into the peer's least-used slots, per layer
    (routed >= 2, gain >= 1.5; peer_experts.cpp:312-385). The copies run H2D on the peer's refill stream.
  - Cap per round: `--peer-adapt-swaps`, which defaults to `--adapt-swaps` = 96 (options.hpp:98, 213; help.cpp:169-172).
  - Promote: a hot expert moves peer -> main through `cudaMemcpyPeerAsync`, which is host-staged without P2P, and
    the peer slot takes the expert the main card gave up (peer_experts.cpp:395-421; serve/tiers.cpp:134-140).
- **`--peer-exclusive`:** the peer's experts have no RAM copy, and evictions DMA back to free RAM places
  (peer_experts.cpp:351-371). The prompt path then fetches them from the peer through host staging
  (stream.cpp:73-77). Auto chooses it only when it keeps experts off the SSD, which we do not need (96 GB RAM).
- **Decode data flow, per layer and window** (dec_moe.hpp:1-10, 140-170):
  1. The 5080's route kernel writes the ring header and the q8_1 rows into mapped pinned host memory and rings a
     doorbell.
  2. The peer's persistent cooperative kernel polls the doorbell over PCIe, computes, and writes fp32 rows
     (10 KiB per entry) plus a done word into mapped host memory.
  3. The 5080 combines.
  The peer uses the **5080's q8_1 bytes**, so its inputs are identical.
- **Assumptions:**
  - Same architecture: explicit. "SAME kernels as the primary's hit path ... bit-identical rows" (peer_experts.hpp:11-12;
    docs/configuration/gpus.md), a single-arch build, and a code check on device 0 only.
  - P2P: **not assumed**. There is no `cudaDeviceEnablePeerAccess` anywhere; peer copies go through the host; decode
    uses zero-copy host memory.
  - Bandwidth: memory bandwidth is priced (slow-peer rules, split pricing). **Link width and latency are not priced
    for decode**: multi_gpu_plan.cpp:11-75 uses memory bandwidth and VRAM only, and the link probes are only for the
    prompt split (prompt_split.cpp:36-56).
- **Verdict for a 4060 Ti on Gen4 x4 through the chipset:** the design supports it (slow-peer path, no P2P, host
  rings work over any link). The costs are latency (about two chipset round trips per layer when the peer has
  entries) and slow refills (see 6c).

## 5. Work estimate

### 5a. Changes

| # | Change | Size |
|---|---|---|
| 1 | CMake: per-TU sm_89 SASS for iq_kernels.cu + elementwise.cu (phase 2: the mmq lib); keep the arch check for the global list | small |
| 2 | sm_89 guards in the tier TU: gu2.cuh:346/369, dec_gdn_rec.cu include, dm_peer_kernel MIX branch and instantiations, dm_vram_tma_kernel. Trap stubs for < 900; sm_120 SASS diff must be empty | medium (mechanical, careful) |
| 3 | `launch_dependent` (gu2.cuh:393): plain launch on cc < 9 | small |
| 4 | Card rules: an sm_89 card is allowed **only as an expert tier**, never main (gpu_select.cpp:136-215, cli/gpu.cpp:43-56); `auto` includes it as a tier; new messages; docs | small |
| 5 | Per-tier-device code probe at start (device.cu:110-117 pattern), with a clear refusal | small |
| 6 | Force off for an sm_89 tier: GDN split, head split, prompt split, MIX (all already off by bandwidth or pack, so make it explicit); phase 1 defaults `--peer-prefill-rows 0` | small |
| 7 | Cross-device bitwise test (extend tests/kernels/dec_moe_parity.cpp "window"/"peer math": compare against native_expert_grouped **on the 5080**, not on the peer) + an exhaustive `ex2.approx.ftz.f32` check | medium |
| 8 | Phase 2 (prompt share): mmq `#error`/PDL guards; make stream-k independent of the card (pin `nsm` to the main card's count in mmq_host.cu:38, or force the tiled path); rounding check | medium |
| 9 | Link-aware tuning: cap `--peer-adapt-swaps`; maybe use `peer_cap` (hard-coded 0, record_layer.cpp:355) if the peer lands last | small-medium |
| 10 | Carry the patch to every Basalt release (upstream refuses: CONTRIBUTING.md:7) | ongoing |

Phase 1 (decode only) = items 1-7 and 9: roughly **medium**. Phase 2 adds item 8.

### 5b. Risks: would an sm_89 kernel round differently?

- **Integer math is exact:** dp4a, int8 MMA.
- **IEEE-safe:** `iq_kernels.cu` is built without fast-math (div.rn, `__fmul_rn`).
- **Independent of the SM count:** the decode peer kernel does each row's dot inside one warp in a fixed lane order.
  The number of blocks (34 SMs vs 84) only changes who does the work.
- **`__expf` -> `ex2.approx.ftz` (MUFU) in SwiGLU** (dec_moe.cuh:1017; iq_kernels.cu:1899, 2183; gu2.cuh:387): a
  hardware approximation. Equality across architectures is not documented. **Test all 2^32 inputs on both cards.**
- **FMA contraction:** gu2.cuh:5-10 relies on the compiler contracting `s += apply` into an FMA. The same source
  compiled for compute_89 vs compute_120 normally contracts the same way, but this is not guaranteed. The bitwise
  cross-card test covers it.
- **MMQ (phase 2), stream-k:** `block_nums = nsm` when tile efficiency is < 90 % (mmq.cuh:843-846). K is then split
  at boundaries that depend on `gridDim` (mmq.cuh:496-500), so float partial sums are added in an order that depends
  on the card. The split also depends on which experts share a group, so **the 5080's prompt rows already depend on
  placement** (pre-existing). `-use_fast_math` on mmq adds approximate division and MUFU `__expf`
  (moe_mmq.cu:102/111).
- **Not a tier issue:** Basalt's CPU tier already rounds differently from its GPU tier (engine log: "it rounds
  differently from the CPU"). Moving experts CPU -> 4060 Ti changes the text at rounding level, like any cache-size
  change. **The lossless claim to prove is: 4060 Ti rows == 5080 rows for the same expert and the same input.** With
  that, Basalt + helper == Basalt with a bigger 5080 cache.
- **Other risks:**
  - Link contention: refills (H2D) against the doorbell polls.
  - The peer landing last on some layers (link latency is unpriced).
  - VRAM on the 4060 Ti: P028x uses it, so the two cannot run together.
  - Upstream drift.

### 5c. Test plan (each GPU step in a gap with 8080 down: P028x uses both cards; hold tmp/gpu-test.lock)

- **T0 (no GPU):**
  - Build A (stock) and B (patched).
  - `cuobjdump -sass` of every sm_120 cubin, A vs B: must be identical.
  - `cuobjdump --list-elf`: sm_89 images present for the tier TUs.
  - Phase 2: also diff the mmq library.
- **T1, kernels, bitwise:**
  - Run the existing parity tests on each card (dec_moe_parity "peer math"/"window", native_grouped_parity,
    quantize_act_parity, dm_table_put_parity).
  - New cross-card test: same random and real inputs, all 6 format pairs used by the pack, 1..80 entries, group
    shapes 1..16. 4060 Ti `dm_peer_kernel` rows vs 5080 `native_expert_grouped` / VRAM rows, compared with memcmp.
  - Exhaustive `ex2.approx.ftz.f32`, all 2^32 inputs, both cards (seconds).
  - Phase 2: MMQ products with the main card's `nsm` on both cards.
- **T2, in situ:** an optional shadow mode that also computes each peer entry on the 5080 for N windows and counts
  bitwise mismatches (medium; strongest evidence).
- **T3, quality:**
  - `basalt-bench --quality` (PPL/KLD vs Q8_0) tier on/off.
  - Our yardstick as for a cache-size change ("rounding-level"): mean, p90, KL>1, top-1, NLL within the
    references' spread.
- **T4, speed:**
  - Community fixtures x3 (decode blend, 16K, 64K), 4060 Ti on/off, same settings, `--wait-stats` on.
  - The 9-workload screen.
  - A `--peer-adapt-swaps` sweep (4/8/16).
  - The usual guards: MemAvailable floor, VRAM floors, kernel log, swap.

## 6. Net speed estimate method

### 6a. How much the 4060 Ti can hold

Real blob sizes (n_embd 2560, n_ff 640; formats from the engine log):

| Layers | Formats | MB per expert |
|---|---|---|
| 5 | IQ2_S/Q2_0 | 1.51 |
| 15 | IQ2_S/IQ4_NL | 1.97 |
| 3 | IQ3_XXS/Q2_0 | 1.72 |
| 14 | IQ3_XXS/IQ4_NL | 2.18 |
| 1 | IQ3_S/Q2_0 | 1.87 |
| 9 | IQ3_S/IQ4_NL | 2.33 |
| 1 | IQ4_XS/IQ4_NL | 2.66 (the log's "largest blob") |

The mean is **2.046 MB**, matching the log's 46.8 GiB / 24,576. The "~1.96 MB" figure is the IQ2_S/IQ4_NL size only.

Free on the 4060 Ti at start is about 7.8-7.9 GiB. From that come the 600 MiB reserve, ~63 MB of router codes, small
buffers, and +200 MiB of prompt buffers unless `--peer-prefill-rows 0`. That leaves about 7.0-7.3 GiB, or **about
3,500-3,700 slots**: 14-15 % of the experts (P028x holds ~3,300). Both cards together hold ~8,300-8,500 = 34-35 %, up
from 19.5 % (4,790).

### 6b. Basalt's own price

multi_gpu_plan.cpp:11-17, 74-75:
`ms/window = 11.9/bw_main*1000 + 18.1*(1 - (slots/24576)^(1/6))`

| Setup | Hit share (model) | ms/window | Decode rate |
|---|---|---|---|
| 5080 alone (4,790 slots) | 76.1 % (our measured 73.7-79.0 %: the curve fits) | 12.40 + 4.32 = 16.71 | 217 |
| + 3,300 slots | 83.1 % | 15.46 | 217 x 1.081 = ~235 |
| + 3,600 slots | 83.6 % | 15.36 | 217 x 1.088 = ~236 |

The helper serves ~7-7.5 % of routed reads, which cuts the CPU tier's reads by ~30 % (23.9 % -> ~16.5 %). This
model charges nothing for the link or for the peer's own compute, so treat it as the upper side.

### 6c. Link vs RAM

- **Decode never moves weights over the x4 link.** The peer reads its experts from its own 288 GB/s VRAM. Only
  q8_1 rows (~2.9 KB per token) go in, and 10 KiB fp32 rows per entry come out.
- **Bandwidth is not the limit.** At ~35-46 peer entries per token (7-7.5 % of the 498-609 lookups per token in our
  logs), that is ~0.4 MiB per token, about 100 MB/s, roughly 1.5 % of x4 Gen4 (7.9 GB/s raw, ~6.5 achieved).
  Per layer and window it is ~3-4 entries = ~35 KiB = ~5-6 us.
- **Latency is the cost:** about two chipset round trips (~2-4 us) per layer in which the peer has entries. Against
  that, the CPU tail it removes is ~28 us per layer per window (model). The peer chain is about 5 + 3 + ~25 us of
  compute, under the remaining CPU tail of ~62 us, so it is normally off the critical path.
- **The RAM tier, by comparison,** reads ~2.05 MB of DDR5-6000 per missed distinct expert per window.
- **Refills are the weak spot.** One swap = 2.05 MB / ~6.5 GB/s = ~0.32 ms over x4, against ~0.035 ms over the
  5080's x16 Gen5 (57.8 GB/s probed). The default 96 swaps per round, with a round every window, would need ~30 ms of
  link time per round, more than a ~17 ms window. **Cap `--peer-adapt-swaps` (try 4-8).** The tier then adapts
  slowly, closer to the profile placement the model assumes.
- **Prompts:**
  - Long prompts (streamed chunks of 6,144+ tokens; 32K chunks at 16K/64K) never use a slower peer, and the prompt
    split is NVFP4-only. Expect **16K ~5,350 and 64K ~5,440, unchanged.**
  - Only prompts under 2,560 tokens could gain, and only in phase 2.
  - A start or WAKE refill of ~7.3 GB over x4 takes ~1.1 s.

### 6d. Carrying over P028x's measured helper value

1. Measure P028x with the helper on and off: `Δ_P = 1/r_off - 1/r_on` (ms per token). Also take its helper read
   share `h_P` and lookups per token `L_P` from its tier counters.
2. Per-read value: `s = Δ_P / (h_P * L_P)`.
3. For Basalt, get `h_B` from 6b (7.0-7.5 %), or use `h_P` adjusted for the slot counts. Take `L_B` from the engine
   log's lookups and generated tokens.
4. Set `k` = Basalt's CPU cost per miss / Strata's. Use 1 first, then refine from each engine's pool timings.
5. `Δ_B = min(s * k * h_B * L_B, w_B)`. Here `w_B` is Basalt's `--wait-stats` wait on the CPU pool per token with the
   5080 alone; it caps the gain.
6. `r_B+ = 1 / (1/217 - Δ_B)`.
7. **Carry over the ms saved per token, not the percentage.** The faster engine gets a larger percentage from the
   same saving.

Illustration only (the off value is hypothetical): if P028x went 185 -> 198.4 tok/s, then Δ_P = 0.365 ms per token,
and with equal h, L and k, Basalt goes 1/(4.608 - 0.365 ms) = ~236 tok/s (+8.6 %). Cross-check the result against
6b and the link adjustment in 6c.
