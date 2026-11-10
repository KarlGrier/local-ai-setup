# Shapes audit: our 29 patches (v0.2.11..r23-port0211) against v0.2.13's compiled geometry

Desk audit, 2026-11-09. Read-only: git show / git diff / git grep only. Nothing was built, compiled or run.
Line numbers are in `r23-port0211` unless a tag is named. Each claim carries a mark:
**[R]** read in the code; **[I]** inferred (arithmetic done by hand, or a hunk's apply judged from the context lines
without running `git apply`).

Scratch copies of the files read are in this folder (`*.r23.*`, `*.v0213.*`, `p18/p23/p24/p28.diff`).

## The shapes, as v0.2.13 defines them [R]

| field | flash_next | q4_mid | q4_big | q4_deep |
|---|---|---|---|---|
| n_embd | 2560 | 3072 | 4096 | 2560 |
| n_layers (QSA / GDN) | 48 (12/36) | 48 (12/36) | 60 (15/45) | 64 (16/48) |
| n_head / n_head_kv (G) | 24/2 (12) | 32/2 (16) | 32/2 (16) | 24/2 (12) |
| ssm_v_heads (conv ch, value dim) | 48 (10240, 6144) | 64 (12288, 8192) | 64 (12288, 8192) | 48 |
| hc / hc_lr (hc width) | 4/320 (10240) | 4/384 (12288) | 4/512 (16384) | 4/320 |
| n_expert / top-k / n_ff | 512/10/640 | 256/8/1024 | 512/10/1024 | 512/10/640 |
| n_vocab | 248320 | 248320 | 248320 | 248320 |

geometry_checks.hpp pins state 128, k-heads 16, d_conv 4, head_dim 256, n_rot 64, qsa_interval 4, hc 4, indexer 4x128,
idx_block 4, and bounds the rest (n_embd % 256 in 1024..4096; n_ff % 64 in 256..1100; hc_lr % 64 with 32 <= hc_lr/8 <= 64;
G <= 16; top-k 1..16). q4_deep differs from Flash-Next only in the layer count, and none of our code pins the layer
count, so q4_deep is fine everywhere below. [R]

Upstream's pattern (4041af8e6, b273c8006, da7b1d022) [R]: a file-level `constexpr int X = kCompiledGeometry.<field>`
(or `kMoeEmbd` / `kMoeFF` / `kMoeGuRows` from moe_fused.hpp), plain literals replaced by named strides (`H_ROW_BYTES`,
`GU_ROWS_N`, `D_ROWS_N`), and a `static_assert` only for a rule the tiles need (`GU_ROWS_N % WR == 0`, ...), worded
with the field it constrains.

## Findings

Severity: **BUILD** = a compile error at that shape; **WRONG** = runs, wrong numbers; **OOB** = out-of-bounds writes;
**GUARD** = a startup guard turns the patch off; **ok** = fine.

| # | commit (n) | file:line | field(s) | q4_mid | q4_big | q4_deep | moves in v0.2.13? |
|---|---|---|---|---|---|---|---|
| F1 | eaaebbee0 (18) | src/kernels/cuda/fused_gr.cu:2823-2826 | n_embd, hc, hc_lr | **BUILD** | **BUILD** | ok | no (applies by offset) |
| F2 | eaaebbee0 (18), 0c684edba (19) | include/strata/kernels/fused_gr.hpp:80-81; fused_gr.cu:2828-2829 | n_embd, hc, hc_lr | ok now; **BUILD**/**OOB** once F1 is generalised | same | ok | no |
| F3 | eaaebbee0 (18) | fused_gr.cu:2978-3061 (gr_up_fork_kernel), 2881, 2948 | hc_lr, n_embd | ok | ok | ok | no |
| F4 | 35ce9a54e (20) | fused_gr.cu:3342; src/core/patch_guard.cpp:196-203 | n_embd, hc, hc_lr | ok (guard cannot see F1) | same | ok | no |
| F5 | 1c915d7d5 (23) | include/strata/prefill/moe_fused_iq.hpp:63; src/prefill/moe_fused_iq.cu:1322; patch_guard.cpp:225 | n_embd, n_ff | **BUILD** (CUDA) | **BUILD** (CUDA) | ok | yes: line 80 rewritten |
| F6 | 1c915d7d5 (23) | moe_fused_iq.cu:1309 (+ grids 2642, 2656) | n_ff, n_embd | **WRONG** if F5 is relaxed | **WRONG** | ok | same pattern fixed upstream |
| F7 | 1c915d7d5 (23) | moe_fused_iq.cu:1544 | n_ff | **WRONG** if F5 is relaxed | **WRONG** | ok | same pattern fixed upstream |
| F8 | 1c915d7d5 (23) | moe_fused_iq.cu:1561 | n_embd | **WRONG** if F5 is relaxed | **WRONG** | ok | same pattern fixed upstream |
| F9 | 35ce9a54e (20), 1c915d7d5 (23) | src/core/patch_guard_test.cpp:84, 85, 88 (94) | n_head/n_head_kv, hc_lr, n_embd (n_ff) | test FAIL (84, 88) | test FAIL (84) | ok | no (our file) |
| F10 | 35ce9a54e (20) | patch_guard.cpp:175 | qsa_interval | ok | ok | ok | no |
| F11 | b53f68d00 (1), used by 4036f229f (2) | src/program/generate.cpp:15196-15198 | head_dim | ok | ok | ok | no (our block) |
| F12 | 08cf582ea (24) | src/kernels/cuda/sampler.cu:1686-1693; patch_guard.cpp:163-171 | n_vocab | ok | ok | ok | no (file unchanged) |
| R1 | eaaebbee0 (18) | fused_gr.cu:36-39 (upstream's N, HC, D, LR) | n_embd, hc, hc_lr | ok after rebase | ok after rebase | ok | yes: 4041af8e6 |
| R2 | 1c915d7d5 (23) | moe_fused_iq.cu:80 (upstream's GU_ROWS_K, D_ROWS_K) | n_embd, n_ff | ok after rebase | ok after rebase | ok | yes: b273c8006 |
| R3 | 1c915d7d5 (23), d797db9f6 (28) | tests/cuda/prefill_fused_iq_test.cpp:55 (upstream's N, FF, K) | n_embd, n_ff, top-k | ok after rebase | ok after rebase | ok | yes: test line 44 at v0.2.13 |
| R4 | 35ce9a54e (20) | src/kernels/cuda/qsa_prompt_attn.cu:2382 (reads upstream's HD, G) | head_dim, n_head/n_head_kv | ok after rebase | ok after rebase | ok | yes: G at line 32 |

### F1 - the fork read's down tiling is written for 324 rows and 10240 columns

```cpp
constexpr int NR = LR + HC;     // the down projection's rows: w_down's 320, then w_inject's 4
constexpr int DG = 4, DS = 20, DW = 9, DR = 9, DT = 4;
constexpr int DTH = DW * 32, DRB = DW * DR, DCS = D / DS, DSPC = DS / HC, DSTEPS = DCS / 256, DNF = DCS / 4;
static_assert(DRB * DG == NR && DCS % 256 == 0 && DS % HC == 0 && DNF <= DTH, "down geometry");
```
- [R] The block is in `namespace fk` at file scope, with no `#if` around it, so the assert is evaluated in every build
  of fused_gr.cu, CUDA and HIP, **whether or not STRATA_GR_FORK is set**.
- [I] q4_mid: NR = 388 != 4 x 81 = 324, and DCS = 12288 / 20 = 614 (614 % 256 = 102): the assert fires, so fused_gr.cu
  and the engine fail to build. q4_big: NR = 516, DCS = 16384 / 20 = 819: it fires. q4_deep: 324 rows, DCS 512: it
  passes. (q4_lite also fires: NR 260, DCS 409.)
- [R] Everything else in the down kernel already reads the file constants: `bo_prev + col0 - c * N` (2881),
  `rsqrtf(sq / (float) N + eps)` (2948), `w_down + rb * D`. The inject-row mask `ok = rb < LR || has_inj` (2888, 2934,
  2953) assumes that every row below DG x DRB is a real row.
- Moves: [R] v0.2.13 changes fused_gr.cu (constants at 34-44, several other kernels). It does not change the context
  of our insertions: the end of `gr_up_pf_dispatch` (v0.2.13:2815-2822), the q8 branch's `return q8; }` before the
  STRATA_GR_V3 line (2865-2867), and `fused_gr_quantize_q8_0` / `fused_gr_supported` (3083-3089). [I] The hunks
  should apply with a shift of about +20 lines.
- Fix (upstream style, [I] not compiled). Derive the slice count from the hidden size, round the row groups up, and
  mask the padding rows:
  ```cpp
  constexpr int NR = LR + HC;                                // 324 for Flash-Next
  constexpr int DCS = 512, DS = D / DCS, DT = 4, DW = 9, DR = 9;   // 20 slices of 512 columns for Flash-Next
  constexpr int DTH = DW * 32, DRB = DW * DR, DG = (NR + DRB - 1) / DRB;   // 4 row groups (exactly 324 rows) for Flash-Next
  constexpr int DSPC = DS / HC, DSTEPS = DCS / 256, DNF = DCS / 4;
  static_assert(N % DCS == 0 && DS % HC == 0 && DNF <= DTH && DG <= 64,
                "the fork read: n_embd must be whole 512-column slices (a slice inside one stream), at most 64 row groups (the scratch's counters)");
  // rows DG*DRB > NR are padding: rb < LR || (has_inj && rb < NR) at 2888 / 2934, and `if (rb >= NR || (rb >= LR && !has_inj)) continue;` at 2953
  ```
  With this, Flash-Next keeps DS 20 / DG 4 and so the same blocks, order and bits [I]. q4_mid gets DS 24 / DG 5
  (405 rows, 17 padding); q4_big gets DS 32 / DG 7 (567 rows, 51 padding) [I]. geometry_checks allows n_embd values
  that are multiples of 256 but not of 512 (2304, 2816, ...). The assert would then break a shape that upstream
  accepts. If that matters, gate the fork instead of asserting:
  `constexpr bool kForkBuilt = N % 512 == 0;`, `if constexpr (kForkBuilt)` around `fk::launch_fork`, and
  `fused_gr_fork_enabled()` false otherwise (see F4).
  - Minimal alternative, Flash-Next shapes only: `constexpr bool kForkBuilt = N == 2560 && HC == 4 && LR == 320;`. Put
    the fk block behind it (templates and `if constexpr`), so other shapes compile with the fork off.

### F2 - the fork scratch size is a hand-derived Flash-Next number

```cpp
/// ... (26,304 floats, rounded up) ...
constexpr int64_t kGrForkScratchFloats = 26368;                       // fused_gr.hpp:80
constexpr int64_t kGrForkScratchMin = 2 * kGrForkScratchFloats;       // :81
constexpr int SC_CTR = 0, SC_SSP = 64, SC_PART = SC_SSP + DG * DS * DT, SC_FLOATS = SC_PART + DS * DT * NR;   // fused_gr.cu:2828
static_assert(SC_FLOATS <= kGrForkScratchFloats, "fork scratch");                                          // :2829
```
- [I] 64 + 4*20*4 + 20*4*324 = 26,304, rounded up to 26,368 (103 x 256). Once F1 is generalised: q4_mid needs 37,792
  and q4_big needs 67,008, so the assert fires (BUILD). If someone deletes the assert instead, the two token groups'
  regions overlap and the second group writes past `grfk_` (OOB, NaN windows like the v0.1.39 bug that patch 19 fixed).
  q4_deep: 26,304, fine.
- [R] The callers follow the constant: verify.cpp:1087 (`grfk_ = take(kGrForkScratchMin)`), 1626
  (`grfk_ + grp * kGrForkScratchFloats`), 2603 / 2620 (head reads), and mtp.cpp:441 (`max(T*HC*N, kGrForkScratchMin)`).
  Nothing else to change there.
- Moves: [R] fused_gr.hpp is unchanged between v0.2.11 and v0.2.13. Its only include is window_limits.hpp, so the fix
  must add `#include "strata/core/geometry.hpp"`.
- Fix: compute it in the header from the compiled geometry, with the same tiling numbers F1 uses (moved there so that
  both sides share them). Round up to 256 so that Flash-Next keeps 26,368 and its offsets:
  ```cpp
  namespace gr_fork {   // the fork read's down tiling (fused_gr.cu fk::), from the compiled geometry
  inline constexpr int64_t kSliceCols = 512, kTokens = 4, kRowsPerGroup = 81;
  inline constexpr int64_t kRows = strata::core::kCompiledGeometry.hc_lr + strata::core::kCompiledGeometry.hc;
  inline constexpr int64_t kSlices = strata::core::kCompiledGeometry.hc * strata::core::kCompiledGeometry.n_embd / kSliceCols;
  inline constexpr int64_t kGroups = (kRows + kRowsPerGroup - 1) / kRowsPerGroup;
  }
  constexpr int64_t kGrForkScratchFloats =
      (64 + gr_fork::kGroups * gr_fork::kSlices * gr_fork::kTokens + gr_fork::kSlices * gr_fork::kTokens * gr_fork::kRows + 255) / 256 * 256;   // 26,368 for Flash-Next
  ```
  Keep the static_assert at fused_gr.cu:2829. With the derived constant it holds at every shape.

### F3 - the fork read's up kernel: fine, given geometry_checks' lane rule

```cpp
__shared__ __align__(16) float4 lo4[TT][2][LR / 8];                                   // 2978
wb[q] = lane < LR / 8 - 32 ? __ldg(w4 + 32 + lane) : make_uint4(0, 0, 0, 0);          // 2997
gr_up_fork_kernel<8><<<UPM_BLOCKS, THREADS, 0, st>>>(m);                               // 3061 (UPM_BLOCKS = N / 16)
```
- [R] The kernel is written for any hc_lr with 32 <= hc_lr/8 <= 64, which geometry_checks enforces ("fused_gr lane
  rule"). [I] Its shared memory at TT 8 is 18 KB at hc_lr 512 and 12 KB at 384. UPM_ROWS = HC x UPM_COLS / WARPS = 8,
  and RW 4 or 2 divides it. The grid is N / 16 blocks (upstream's UPM_BLOCKS, derived at v0.2.13). OK at every shape.
  No change.

### F4 - the gr_fork guard compares with the compiled geometry, which upstream already enforces

```cpp
void fused_gr_fork_geometry(int& n, int& hc, int& lr) { n = N; hc = HC; lr = LR; }      // fused_gr.cu:3342
if (m.n_embd != gr_n || m.hc != gr_hc || m.hc_lr != gr_lr) ...                           // patch_guard.cpp:198
```
- [R] At v0.2.13, N / HC / LR are kCompiledGeometry's (fused_gr.cu v0.2.13:34-37, and the static_assert at 44). The
  guard therefore checks "model == compiled shape", which upstream's load check already refuses on mismatch (geometry.hpp
  header: "a model file of another shape is refused at load"; [I] not traced to the call). It cannot tell whether the
  fork kernel supports the compiled shape. For q4_mid / q4_big that question is answered by the build failure (F1); once
  F1 is gated, the guard must ask.
- Fix: export `bool fused_gr_fork_built()` (the F1 `kForkBuilt`) beside `fused_gr_fork_geometry` and fail the guard when it is false:
  "the fork read is not built for the compiled geometry (n_embd N, low rank LR)". Turn STRATA_GR_FORK off as now.

### F5 - the v2 prompt expert kernels assert K = 2560 / 640

```cpp
constexpr int kV2Embd = 2560, kV2FF = 640;                                                 // moe_fused_iq.hpp:63
static_assert(GU_ROWS_K == kV2Embd && D_ROWS_K == kV2FF, "moe_fused_iq.hpp: kV2Embd / kV2FF");   // moe_fused_iq.cu:1322
if (m.n_embd != F::kV2Embd || m.n_ff != F::kV2FF) return "... compiled for ...";        // patch_guard.cpp:225
```
- [R] At v0.2.13, `GU_ROWS_K = kMoeEmbd, D_ROWS_K = kMoeFF` (v0.2.13:79, b273c8006). [I] At q4_mid (3072 / 1024) and
  q4_big (4096 / 1024) the assert fires and moe_fused_iq.cu fails to build. [R] The assert is inside the v2 section's
  `#if !defined(__HIPCC__)`, so this is CUDA builds only. q4_deep is fine. If the file did compile, the guard would
  refuse v2 for any model that is not 2560 / 640 (GUARD).
- [R] `kV2SharedBytes = 99856` does not depend on the shape: 2 x V2_ACT (128 x 144 + 2048) + 2 x 256 x 112 + 512 +
  1024 + 16. No change.
- Moves: [R] b273c8006 rewrote moe_fused_iq.cu:80, the line our `V2<GU>::K` reads, so V2::K, NC and ACT_LD follow the
  geometry after the rebase. Keep upstream's line 79-83 (with `GU_ROWS_N`, `D_ROWS_N` and `H_ROW_BYTES`).
- Fix: `constexpr int kV2Embd = kMoeEmbd, kV2FF = kMoeFF;   // the compiled geometry's (2560 / 640 for Flash-Next)`.
  [R] moe_fused_iq.hpp includes moe_fused.hpp, which defines kMoeEmbd / kMoeFF at v0.2.13:29-31. **Only together with
  F6-F8.** With F5 alone, the assert passes, the guard passes, and F6-F8 silently produce wrong prompt outputs.

### F6 - v2's work items per tile pair: literal 1280 / 2560

```cpp
static constexpr int NFB = (GU ? 1280 : 2560) / V2_WR;  // items per routed-row pair of tiles      // moe_fused_iq.cu:1309
```
- [I] At q4_mid with F5 relaxed: gate/up NFB = 5 instead of 2048/256 = 8. Features 640..1023 are never computed, so
  their H bytes keep whatever the buffer held. Down NFB = 10 instead of 12, so outputs 2560..3071 of every row are never
  written. Grids (2642, 2656: `tiles * V2<..>::NFB`) shrink with it, so nothing is written out of bounds: WRONG.
  q4_big: 5 instead of 8 and 10 instead of 16: WRONG. q4_deep: fine.
- [R] Upstream fixed the same expression in native_kernel, native_ws_kernel and native_w11_kernel (b273c8006).
- Fix:
  ```cpp
  static constexpr int NFB = (GU ? GU_ROWS_N : D_ROWS_N) / V2_WR;   // 5 / 10 for Flash-Next
  static_assert(GU_ROWS_N % V2_WR == 0 && D_ROWS_N % V2_WR == 0 && D_ROWS_K % 128 == 0,
                "v2: 2 n_ff and n_embd whole 256-row items, n_ff whole 128-value chunks (IQ4_NL down)");
  ```
  [I] q4_mid / q4_big / q4_deep (and q4_lite) all pass. The n_ff % 128 rule is stricter than geometry_checks'
  n_ff % 64. To keep shapes such as n_ff 576 building, put the rule in a `constexpr bool kV2Shape` and return it
  from `native_v2_built()`, so the guard and `v2_occ()` keep the current kernels there.

### F7 - v2's H store stride: literal 10 x AB

```cpp
uint8_t* o = out + (size_t) (row0 + r) * (10 * AB) + (blk >> 1) * AB;                    // moe_fused_iq.cu:1544
```
- [I] 10 = n_ff / 64 (AB = 80: 800 B per H row for Flash-Next). At n_ff 1024 the row is 1280 B: the down kernel reads
  ACT_LD = K / 64 x AB = 1280 B, and the buffer is `act_bytes(n, n_ff)`. Rows written 800 B apart then overlap, which
  is WRONG but stays in bounds. Applies to q4_mid and q4_big; q4_deep is fine.
- [R] Upstream replaced the same literal in its three kernels with `H_ROW_BYTES = D_ROWS_K / 64 * AB` (b273c8006).
- Fix: `(size_t) (row0 + r) * H_ROW_BYTES`.

### F8 - v2's down store stride: literal 2560

```cpp
dm[(size_t) (row0 + r) * 2560 + V2_WR * fb + 32 * warp + 16 * i + 8 * (q >> 1) + g] = acc[i][n][q];   // moe_fused_iq.cu:1561
```
- [I] The row stride of `dm [n][n_embd]`. q4_mid / q4_big: rows written 2560 floats apart in a 3072 / 4096-wide
  buffer, which is WRONG but in bounds. q4_deep: fine.
- [R] Upstream: `* kMoeEmbd` in all of its down epilogues (b273c8006).
- Fix: `(size_t) (row0 + r) * kMoeEmbd`.
- Moves for F5-F8 [R]: the v2 section's anchors exist at v0.2.13: `#endif  // !__HIPCC__` at 1210, `bool ws = false;`
  in DevInfo at 1704, `setup_nt` at 1757, `pick_ww` at 2009, `gfx12_iq2s_default` at 2035. **The experts_native hunk
  must be redone by hand** [I]. Its context is upstream's `g_gu` / `g_d` lines, which b273c8006 changed from
  `1280 / weight_rows(ww)` and `2560 / ...` to `GU_ROWS_N / ...` and `D_ROWS_N / ...` (v0.2.13:2214-2215). The v2
  dispatch itself is shape-free once F6 is in. [R] Upstream's new STRATA_PF_DM16 (FP16 down rows) exists only in the HIP
  branch of experts_native (v0.2.13:2148), so v2's FP32 down store on CUDA is not affected.

### F9 - patch_guard_test's synthetic mismatches assume the compiled shape is Flash-Next

```cpp
{"16 query heads per KV head", [](ModelFacts& m) { m.head_count = 32; }, "STRATA_QSA_SPLIT_ATTN"},   // :84
{"low rank 256", [](ModelFacts& m) { m.hc_lr = 256; }, "STRATA_GR_FORK"},                           // :85
{"n_embd 3072", [](ModelFacts& m) { m.n_embd = 3072; }, "STRATA_GR_FORK"},                           // :88
{"expert n_ff 768", [](ModelFacts& m) { m.n_ff = 768; }, "STRATA_PREFILL_V2"},                       // :94 (patch 23)
```
- [I] q4_mid: the compiled G is 16 and the compiled n_embd is 3072, so cases 84 and 88 match the compiled shape. Their
  guard passes and the test FAILs. q4_big: G 16, so case 84 FAILs. q4_deep: all pass. (q4_lite: hc_lr 256, so case 85
  FAILs.) Test only. The real-header part needs a model file of the compiled shape (q4geo_synth).
- Fix: offsets from the compiled shape that give today's Flash-Next values:
  `m.head_count = m.head_count_kv * (G.n_head / G.n_head_kv + 4)` (32 for Flash-Next), `m.hc_lr = G.hc_lr - 64`
  (256), `m.n_embd = G.n_embd + 512` (3072, still a multiple of 256 so router_q8k stays on), `m.n_ff = G.n_ff + 128`
  (768), with `const auto& G = strata::core::kCompiledGeometry;` and the case labels formatted from those values.

### F10 - the side_mixer guard's literal 4

```cpp
if (!m.gdn || !m.qsa || m.full_attention_interval != 4)                                   // patch_guard.cpp:175
```
- [R] geometry_checks pins qsa_interval = 4, so this is fine at every shape. For the record: `!= strata::core::kCompiledGeometry.qsa_interval`.

### F11 - the side stash / chat cache: q4_0 KV bytes per head as 144

```cpp
if (st.kv_q4) {                            // q4_0 (v0.1.8): 144 B per cell and head, K and V
    out.emplace_back((uint8_t*) st.host.k_q4, cells * 144);                               // generate.cpp:15197-15198
```
- [I] 144 = 256 / 32 x 18, which is head_dim's q4_0 row. geometry_checks pins head_dim = 256, so this is fine at every
  shape. The int8 lines beside it already read `stash_qs.head_dim` [R]. `stash_arrays` also serves `park` / `unpark`
  (patch 2) [R].
- Fix: `cells * strata::kernels::kv_q4_bytes_per_head((int) stash_qs.head_dim)` (kv_q4.hpp:33, at both tags [R]).

### F12 - exact speculative sampling exits above a 262,144-token vocabulary

```cpp
const int n_blocks = (n_vocab + kSplitBlockSpan - 1) / kSplitBlockSpan;
if (n_blocks <= kSplitMaxBlocks && n_tokens <= kSplitMaxRows && !stream_capturing(stream)) scratch = ...;
if (scratch == nullptr) { fprintf(... "the split sampler cannot run here" ...); std::exit(1); }   // sampler.cu:1686-1693
```
- [R] kSplitMaxBlocks 64 x kSplitBlockSpan 4096 = 262,144. Upstream's `sample_tokens` falls back to its one-block
  kernel in that case; ours ends the process. All four shapes keep 248,320, so this is fine. A larger vocabulary would
  exit at the first exact window, and the spec_exact guard (patch_guard.cpp:163-171) does not check for it.
- Fix: in the spec_exact guard, `if (m.n_vocab > K::sample_split_max_vocab()) return "vocabulary N above the split
  sampler's 262,144"`. Export the bound from sampler.cu as a function, because its constants live in an anonymous
  namespace there.
- Moves: [R] sampler.cu, sampler.hpp, mtp.cpp and mtp.hpp are unchanged between v0.2.11 and v0.2.13.

### R1-R4 - our code that reads a Flash-Next constant upstream defines (now derived in v0.2.13)

- R1 [R]: the fork (F1, F3) uses fused_gr.cu's `N`, `HC`, `D`, `LR`, `UPM_COLS`, `UPM_BLOCKS` and `THREADS`. In
  r23-port0211 these are `2560`, `4` and `320` (lines 36-39). At v0.2.13 they come from kCompiledGeometry
  (4041af8e6). On rebase, take upstream's lines. Nothing of ours to change beyond F1 / F2.
- R2 [R]: v2 (F5-F8) uses `GU_ROWS_K` / `D_ROWS_K` (moe_fused_iq.cu:80, `2560, 640`). At v0.2.13 they are
  kMoeEmbd / kMoeFF. Take upstream's line.
- R3 [R]: our v2 test parts (patch 23 `reference_part` v2 block, `v2_part`, the timing v2 block; patch 28's bitwise
  checks) use the test's `N`, `FF`, `K` (prefill_fused_iq_test.cpp:55, `2560, 640, 10`). At v0.2.13 these are
  `fused::kMoeEmbd`, `kMoeFF` and `n_expert_used` (v0.2.13:44). The H check's 80-byte blocks are AB, which does not
  depend on the shape. With upstream's line, the test follows the geometry.
- R4 [R]: `qsa_split_attn_geometry` (patch 20, qsa_prompt_attn.cu:2382) returns the file's `HD` / `G`. At v0.2.13,
  `G = n_head / n_head_kv` from kCompiledGeometry (v0.2.13:32), so the qsa_split_attn guard compares with the compiled
  G (16 at q4_mid / q4_big). Fine. The only v0.2.13 change in that file is at lines 29-34; our insertion near 2379 [I]
  applies.

## Patches checked and found shape-free

| n | commit | why shape-free |
|---|---|---|
| 1 | b53f68d00 | side stash: sizes from `g` (n_qsa_layers, n_head_kv, head_dim, idx_key_dim) and `qsa_real_shapes()`; only the 144 of F11 (head_dim, pinned) [R] |
| 2 | 4036f229f | chat cache: reuses the stash's arrays; 512 / 256 / 4096 are token-count thresholds, 16384 MiB a RAM budget [R] |
| 3 | 053339b81 | keeps the root checkpoint on park: no sizes [R] |
| 4 | 0043e3b7f | web search (Python, server and web app): no model sizes [R] |
| 5 | 1ff135304 | web search date / host allow-list [R] |
| 6 | 180690340 | Q8_K doorbell: rows of `N / 256` blocks of 292 B from `g.n_embd` (n_embd % 256 pinned); guard `n_tok * k > 256` can't fire: n_tok <= kVerifyMaxT <= 16 and top-k <= 16 (geometry_checks) [R]; xk rows are their own buffer, so v0.2.13's larger kNativeActBytes doesn't matter [R]; elementwise.cu/.hpp unchanged between the tags [R] |
| 7 | 25e1a6969 | Q8_K rounding (nearest_int) [R] |
| 8 | 136c43cce | bsums of the stored int8 values [R] |
| 9 | 27c803d13 | NaN rounding [R] |
| 10 | 9d64da88a | nextn: tensor-name suffixes; iq_pack reads n_expert from the router rows and the layer count from the tensors minus nextn [R]; native_dense.cpp `eligible()` unchanged in v0.2.13 [R] |
| 11 | e0163360c | model_check.py: template strings vs the tokenizer [R] |
| 12 | 882b3a539 | chat cache dropped with the non-finite guard: counts only [R] |
| 13 | 6323ab04b | reasoning parser (Python) [R] |
| 14 | 22fd730bd | Tavily fallback (Python) [R] |
| 15 | 0748d2176 | Exa/Tavily chain (Python) [R] |
| 16 | a7a45b11d | owner tag / chat_drop: strings [R] |
| 17 | b52a40948 | keep=1 / tcap / tend: the `</think>` id comes from the tokenizer (`self.tok.encode(THINK_END)`); the 151668 in test_server.py is a synthetic id [R] |
| 19 | 0c684edba | grfk_ region sized by kGrForkScratchMin: follows F2 automatically [R] |
| 21 | e4d4e7ddc | drops the hc BF16 check from the gr_fork guard [R] |
| 22 | 9a98d8488 | drops the mmvq_il guard [R] |
| 24 | 08cf582ea | exact sampling: vocab sizes passed at run time (n_vocab_, nv); kEssMaxList 64 = the top-k list width; only F12 (vocab bound) [R] |
| 25 | 45be9b24c | cost gate: draft-step table by probability bin; no model sizes [R] |
| 26 | 5f7a72c94 | cost gate past its table: same [R] |
| 27 | 478de574a | draft_cum: loops over `g.n_layers` x `g.n_expert` from the run-time geometry; its table is the drafter's, guarded by arch (see open questions) [R] |
| 28 | d797db9f6 | v2's term order: arithmetic only, no sizes; it lives inside the kernel F6-F8 fix [R] |
| 29 | 5f5aebcc2 | done reset per round (Python); iq_pack nextn without files [R] |

Patch 18 (eaaebbee0), patch 20 (35ce9a54e) and patch 23 (1c915d7d5) carry the findings above. Their other parts
(xor_scatter.cuh, the mtp.cpp / verify.cpp scratch callers, the prefill.cpp start line counting `layers`, group_bytes'
+64 counter bytes, and the patch_guard.cpp facts reader) are shape-free [R].

## Port notes found on the way (not shape questions)

- CMake [R]: v0.2.13 splits CMakeLists.txt. Our edits move as follows:
  - patch 20: `src/core/patch_guard.cpp` goes into the strata_engine source list at `cmake/strata_gpu_engine.cmake:289`,
    and `patch_guard_test` goes beside `native_grouped_parity` at `cmake/strata_gpu_engine.cmake:1048`.
  - patch 23: `prefill_fused_v2_test` goes after `prefill_fused_iq_test_ws` at `cmake/backends/cuda.cmake:285`.
  - patches 26 / 27: `cost_gate_test` and `draft_cum_test` go beside `window_rule_test` and its neighbours at
    `cmake/backends/cpu.cmake:54-92`.
- prefill_fused_iq_test.cpp [R]: v0.2.13 gives `reference_part(p, s, T, E, ZERO)` parameters and calls it with E 16
  / 32 and ZERO -1 (lines 739-743, for Q5_0 pairs or `--edge`). Our v2 block inside reference_part (r23:460, 472) still
  passes cuts `{0, 1, 20, E}` (20 > E = 16) and reads `slot2[ZERO * K + k]` without upstream's `ZERO >= 0` test. With
  `--edge` on an IQ3_XXS / IQ4_NL pair it would index out of range. Use `std::min(20, E - 1)` and `ZERO >= 0` as
  upstream does.
- [R] verify.cpp (patch 6, 18, 19) contexts exist at v0.2.13: `h_ymiss_` mapped at 976, the `lo_ ... xn_` line at
  1073, the group read at 1611, the doorbell at 2265, the head reads at 2560 / 2582 / 2599, and `progress_at` at 3492.
  expert_source.cpp `if (any_cpu) {` at 5191 and `jb.nact[jb.nt]` at 5320. mtp.cpp `xn_` at 435.

## Open questions

1. [I] The generalised fork tiling (F1 / F2) is a desk design. Flash-Next keeps DS 20 / DG 4, so by construction it
   keeps the same blocks and summation order. At q4_mid / q4_big, neither the bits against upstream's read nor the speed
   (24 x 5 and 32 x 7 blocks of 288 threads instead of 20 x 4) has been tested. Choose between "generalise" and
   "Flash-Next only, off elsewhere" before the port.
2. Not traced: whether v0.2.13's load check (`geometry_unsupported`) runs before our `run_patch_guards` in
   generate.cpp. If it does, the n_embd / hc / hc_lr parts of the gr_fork and prefill_v2 guards are redundant at every
   shape, and what the guards still need is the "built for this shape" test of F4 / F6.
3. Tuning, not geometry: DRAFT_CUM's acceptance table and its pack-factor range (1.1-3.5 MB of RAM experts per slot),
   and the cost gate's table, were measured on the Flash-Next drafter and blobs. At q4_big, blobs are about 2.6x larger
   (3 x 1024 x 4096 vs 3 x 640 x 2560 weights: about 5.2 MB against 2.05 MB), so the factor saturates at 1.5 [I]. That is valid behaviour, but how
   well it is tuned is unknown. The draft_cum guard only checks the architecture.
4. Not settled: whether `ModelGeometry.n_vocab` is enforced against the model at load. If it is, F12 could be a
   `static_assert(kCompiledGeometry.n_vocab <= 262144)` instead of a guard.
5. Outside this audit [I]: the fk block and xor_scatter.cuh (inline PTX `selp.f32`) have no `#if` for HIP. If HIP
   builds compile fused_gr.cu with it, they may already fail regardless of shape. That was not checked; it does not
   affect the NVIDIA build here.
