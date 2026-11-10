# Qwen4 day-one kit (a): every hard-coded Qwen3.8 Flash-Next shape in our Qwen engine

2026-11-04. A read-only study. Nothing was built, run, installed or changed. No GPU was used.

- **Base read:** worktree `strata-r22p0210`, branch `r22-port0210`, HEAD `fdd2fffa8` = upstream v0.2.10 + our 28 commits.
  Every `file:line` below is relative to that worktree.
- **Model file:** the header of the served file
  `models/ISTA-GSQ-RCO/IQ3_S/Qwen3.8-Flash-Next-GSQ-RCO-IQ3_S-0000{1,2}-of-00002.gguf`, read with a small header-only
  parser (`work/qwen4-kit/scratch-a/ghdr.py`; dumps in `hdr1.txt` and `hdr2.txt`). No tensor data was read.
- **Scope:** the qwen4exp engine path that we serve: `src/core`, `src/kernels`, `src/prefill`, `src/program`,
  `src/ngram`, `src/spec`, `include/`, plus the pack and MTP tools and the server's token ids. Off our path, and only
  noted in section 3.13: `src/split` (the all-cards engine), `src/qwen35` (Qwen3.6), `src/dsv41` (DeepSeek), DFlash2,
  Metal and SYCL.

**Classes used in the "reading it from the file" column:**

| class | meaning |
|---|---|
| **K** | one line or a few: read a key, drop a pin, or use a runtime field the code already has |
| **P** | plumbing: a file-local `constexpr` becomes the runtime geometry across one file. Mechanical, no new math, but buffers become runtime-sized. Tens to ~200 lines. |
| **T** | a template parameter per shape: the constant sizes shared memory, unrolls or tiles. Each supported shape is one more instantiation plus a dispatch, and the tile divisibility has to hold for the new value. |
| **R** | kernel rework: the tiling is built on this exact factorization, or the value must stay under a fixed capacity. A new value needs a new tile plan and new parity tests. |
| **D** | data: regenerate a file or table. No code. |

A **Qwen4-only build** (edit the constants and rebuild) is much cheaper than a binary that runs both models. Where it
matters, the table says which one the size is for.

---

## 1. Bottom line

1. **There is one geometry struct, and a load gate in front of it.** The defaults are in `include/strata/core/geometry.hpp`
   (lines 24-60), and `kCompiledGeometry` is "the shape the kernels are compiled for". `read_geometry`
   (`include/strata/artifact/gguf_reader.hpp:677`) reads about 20 keys from the GGUF. `geometry_unsupported`
   (`:805-845`) then **refuses any file whose shape differs from the compiled one**. At load, only the expert count, the
   experts per token (at most 64) and the vocabulary are free.
2. **The architecture string comes first.** `gguf_reader.hpp:681` refuses anything but `general.architecture =
   qwen4exp`, by name, before it reads any shape key. The served file says `qwen4exp`, described as "A Preview of the
   Qwen4 Architecture". vLLM calls its MTP `qwen4_exp` (`include/strata/core/mtp.hpp:3`). If Qwen4's GGUF arrives as
   `qwen4`, `qwen4moe` or anything else, this is the first stop, whatever the shapes are.
3. **Behind the gate the widths are compile-time constants in about 40 files.** Thirteen kernel sites `static_assert`
   against `kCompiledGeometry`, and `ple.cu` asserts the same numbers as literals (all listed in 3.3). A Qwen4-only rebuild therefore fails to compile there instead of
   mis-running. **The rest have no assert:**
   - the prompt path: `src/prefill/prefill.cpp:213-214`, `src/prefill/kernels.cu:24-25`, `src/prefill/gdn_chunk.cu:28`,
     and the `src/prefill/moe_*` expert kernels;
   - `wmma_gemm.cu`'s hyper-connection GEMM, the n-gram header, the nibble layout and `native_flash_attn.cu`.

   Some of these have runtime checks that refuse a wrong shape. Others would mis-run quietly.
4. **The worst silent item is the n-gram hash.** Its constants are written into the code (`src/kernels/ngram.cpp:46-65`)
   and are never compared with the file's `ple.layer_multipliers`, `ple.head_vocab_sizes` and `ple.head_offsets`. A
   Qwen4 with other hash constants would load and run on wrong rows of the n-gram table, with plausible-looking output.
   Upstream's split engine already reads them from the file (`src/split/src/model.cpp:1333-1362`).
5. **Our 28 commits add pins in two places, and both are guarded.** One is the GR fork tiling (`fused_gr.cu:2823-2829`,
   which factors 320 + 4 = 9 x 9 x 4). The other is the v2 prompt expert kernels (`moe_fused_iq.hpp:63`,
   `moe_fused_iq.cu:1292-1561`, built for 2560 / 640). Our patch guards (`src/core/patch_guard.cpp:172-245`) switch both
   off on another shape, so they fall back to upstream's path instead of breaking. Section 4 has the full list.
6. **What breaks first** (section 5):
   - **Expert count:** nothing at load. Above 512 the prompt path breaks first: `NE = 512` arrays and loops in
     `prefill.cpp`. The tools break too: `mtp_rt.py` NE, `make_profile.py`, and the profile file.
   - **Experts per token:** `prefill.cpp:1739` refuses the batched prompt path at start (`K = 10`). The helper-card tier
     sizes its buffers for top-10 (`remote_experts.cpp:22`).
   - **Layer count:** only the load pin, then three or four one-liners and the profile tooling. This is the cheapest change.
   - **Widths:** the load pin, then everything in 3.3-3.7. This is the expensive class.
   - **Karl's guess, read through UPGRADE-ESTIMATE section 8, is a width change.** It keeps 48 x 512 and top-10 with
     9.4-11.8M parameters per expert, against 4.92M today.

---

## 2. The served file against the compiled shape

GGUF header values (`hdr1.txt`). "Pinned" means `geometry_unsupported` refuses a file whose value differs.

| quantity | file value | GGUF key | compiled default (`geometry.hpp`) | read at load? | pinned at load? |
|---|---|---|---|---|---|
| architecture | `qwen4exp` | `general.architecture` | `ModelFamily::Qwen4Exp` (:59) | yes | **refused by name** if not qwen4exp (`gguf_reader.hpp:681`) |
| layers | 48 | `qwen4exp.block_count` | `n_layers = 48` (:25) | yes (required) | **yes** (:812) |
| hidden width | 2560 | `embedding_length` | `n_embd = 2560` (:24) | yes (required) | **yes** |
| full-attention interval | 4 | `full_attention_interval` | `qsa_interval = 4` (:26) | yes | **yes** |
| layer split, twice over | `[0,0,0,4,...]` x 48 | `attention.compress_ratios` | `idx_block = 4` (:45) | yes, checked against the interval (:768-801) | **yes** (the pooling block) |
| GDN state / head width | 128 | `ssm.state_size` | 128 (:31) | yes | **yes** |
| GDN k heads | 16 | `ssm.group_count` | 16 (:32) | yes | **yes** |
| GDN v heads | 48 | `ssm.time_step_rank` | 48 (:33) | yes | **yes** |
| GDN conv kernel | 4 | `ssm.conv_kernel` | 4 (:34) | yes | **yes** |
| GDN value dim | 6144 | `ssm.inner_size` | 6144 (:36) | yes, must be 128 x 48 (:756) | **yes** |
| GDN conv channels | 10240 | derived: 2 x 128 x 16 + 6144 | 10240 (:35) | derived | via its parts |
| attention q heads | 24 | `attention.head_count` | 24 (:39) | yes (required) | **yes** |
| attention kv heads | 2 | `attention.head_count_kv` | 2 (:40) | yes (required) | **yes** |
| head dim (k = v) | 256 / 256 | `attention.key_length` / `value_length` | 256 (:41) | yes; k must equal v (:736) | **yes** |
| rotary dims | 64 | `rope.dimension_count` | 64 (:42) | yes | **yes** |
| rope sections | [11, 11, 10, 0] | `rope.dimension_sections` | none (logic in `mrope.hpp:49-52`) | **no** | n/a (logic assumes it) |
| rope base | 1e7 | `rope.freq_base` | `qsa_freq_base() = 1e7` (`qsa.hpp:125`) | **no** (CLI `--rope-freq-base` only) | no |
| trained context | 262144 | `context_length` | `orig_ctx = 262144` (`rope_scaling.hpp:71`) | **no** | no |
| RMS eps | 1e-6 | `attention.layer_norm_rms_epsilon` | 1e-6 (:28) | yes | **yes** (:837) |
| indexer heads | 4 | `attention.indexer.head_count` | 4 (:43) | yes | **yes** |
| indexer key dim | 128 | `attention.indexer.key_length` | 128 (:44) | yes | **yes** |
| indexer top-k | 2048 | `attention.indexer.top_k` | 2048 (:46) | yes | **yes** |
| hyper-connection streams | 4 | `hyper_connection.count` | `hc = 4` (:49) | yes | **yes** |
| hyper-connection low rank | 320 | `hyper_connection.low_rank` | `hc_lr = 320` (:50) | yes | **yes** |
| routed experts | 512 | `expert_count` | 512 (:53) | yes (required) | **no (free)** |
| experts per token | 10 | `expert_used_count` | 10 (:54) | yes (required) | **no**, but at most 64 (:760) |
| expert FFN width | 640 | `expert_feed_forward_length` | `n_ff = 640` (:55) | yes | **yes** |
| shared expert width | 640 | `expert_shared_feed_forward_length` | 640 (:58) | yes; **must equal n_ff** (:739) | via n_ff |
| shared experts | 1 per layer | none (tensor `ffn_*_shexp`) | implied | n/a | n/a |
| vocab | 248320 | length of `tokenizer.ggml.tokens` | 248320 (:27) | yes | **no (free)** |
| in-file MTP layers | 0 (no `nextn` key) | `nextn_predict_layers` | `n_mtp_layers = 0` (:60) | **no** for qwen4exp (qwen35moe only, `family_layout.hpp:64`) | `block_count` pin |
| n-gram: ngram size | 3 | `ple.ngram_size` | `NGRAM_SIZE = 3` (`ngram.hpp:33`) | read by the patch guard only | no, silent |
| n-gram: heads per ngram | 8 | `ple.heads_per_ngram` | 8 (`ngram.hpp:34`) | patch guard only | no, silent |
| n-gram: row width | 160 | `embedding_length_per_layer_input` | `PLE_HEAD_DIM = 160` (`ngram.hpp:32`) | patch guard only; the table's ne0 is checked (`ngram.cpp:326`) | ne0 only |
| n-gram: conv kernel | 4 | `ple.conv_kernel` | 4 (`ngram.hpp:36`) | **no** | no |
| n-gram: hash constants | 3 multipliers, 16 vocab sizes, 16 offsets | `ple.layer_multipliers`, `ple.head_vocab_sizes`, `ple.head_offsets` | `ngram.cpp:51-59` | **no** | **no, silent** |
| n-gram: table rows | 320,001,536 | tensor `per_layer_token_embd.weight` [160, 320001536] | `PLE_TABLE_ROWS` (`ngram.hpp:46`) | rows taken from the tensor | n/a |
| n-gram: layers | [1] | `ple.layers` | `blk.1.*` and `layer == 1` | **no** | no |
| n-gram: EOS id | 248044 | `ple.eos_token_id` | `PLE_EOS_TOKEN_ID` (`ngram.hpp:37`) | **no** | no |
| image token id | 248056 | `ple.image_token_id` | `kImagePad` (`generate.cpp:13513`) | **no** | no |
| EOS ids | eos 248046, bos/pad 248044 | `tokenizer.ggml.eos_token_id` etc. | `{248044, 248046}` (`generate.cpp:899`) | **no** | no |

For scale: the file holds **176.9B parameters**:
- routed experts 120.8B (4.915M each, 48 x 512);
- n-gram table 51.2B;
- dense 4.95B, of which embedding + head are 1.27B;
- **active per token about 7.3B**, counting embedding and head (`params.py`).

---

## 3. Every hard-coded site, by area

### 3.1 Load gate and architecture

| value | file:line | GGUF key | reading it from the file takes |
|---|---|---|---|
| arch must be `qwen4exp` | `include/strata/artifact/gguf_reader.hpp:681`; prefix `"qwen4exp."` :682 and :834, :839 | `general.architecture` | **K**, ~10 lines: map a new name onto `ModelFamily::Qwen4Exp` in `model_family.hpp:21-25` and use the family's prefix. Only valid if the tensors and keys are otherwise qwen4exp-shaped. |
| family runs only Qwen4Exp | `include/strata/artifact/model_family.hpp:54` | same | **K** |
| shape pins (the 19 keys in section 2) | `gguf_reader.hpp:805-845`; the same list a second time in `include/strata/core/family_layout.hpp:99-131` (`compiled_geometry_mismatch`, called at `src/program/generate.cpp:4696`) | section 2 | **K** to drop a pin, but only after the kernels behind it take the new value (3.2-3.10) |
| `expert_used_count <= 64` | `gguf_reader.hpp:760` | `expert_used_count` | K. It is the router's limit. |
| shared width == routed width | `gguf_reader.hpp:739` | `expert_shared_feed_forward_length` | **P**: the decode shared expert takes n_ff at run time (`shared_expert.hpp:70`). The prompt path sizes it `T * 640` (`prefill.cpp:2016`). |
| default experts per token 10 when the key is absent | `family_layout.hpp:51` | `expert_used_count` | K |
| layer count a multiple of the interval; layer kind by `layer % 4 == 3` only | `family_layout.hpp:92`; `geometry.hpp:75` | `full_attention_interval`; llama.cpp also writes `attention.recurrent_layers` (seen in upstream #4449), which is not read | **P** if Qwen4 lists an irregular pattern: `is_qsa_layer` and `n_qsa_layers()` become a per-layer table |
| server side: the arch gates for defaults and names | `serve/server.py:4057`, `:9346-9383`, `:9906` | arch | K |
| pack tool: nextn key by name | `tools/iq_pack.py:445` (`"qwen4exp.nextn_predict_layers"`) | `nextn_predict_layers` | K |

### 3.2 Layer count (48) and layer pattern (36 GDN + 12 attention, every 4th)

The host code takes `g.n_layers` almost everywhere: the session, the per-layer graphs, verify, prefill loops and the
expert cache. The remaining pins:

| value | file:line | GGUF key | takes |
|---|---|---|---|
| load pin 48 | `gguf_reader.hpp:812` | `block_count` | K |
| routing trace accepts layers 0..47 only (the expert profile is built from it) | `src/program/generate.cpp:1414`, `:1438` | `block_count` | K (2 lines) |
| profile tool: 48 x 512 | `tools/make_profile.py:33` (`N_LAYER, N_EXPERT = 48, 512`; `--n-expert` exists, no layer flag) | `block_count`, `expert_count` | K, then **D** (a new `data/expert-profile.bin`; the engine reader takes both counts, `src/core/expert_cache.cpp:163`) |
| KVA declines unless 48 layers and 512 experts | `src/prefill/prefill.cpp:3226-3233` | same | K. KVA ships off; `STRATA_KVA_ANY_MODEL=1` overrides. |
| planner defaults 48 / 12 / 48 v heads / 10240 | `include/strata/plan/plan.hpp:24-25`, `:52-54` | several | K (the `strata plan` tool only) |
| 4-card AMD split "13,26,39" | `strata_control/amd_four_card.py:25` | `block_count` | K (not our hardware) |
| in-file MTP block: `block_count` 49 is refused | `gguf_reader.hpp:812` (no `nextn` subtraction for qwen4exp; our #619 port covers only `tools/iq_pack.py:439-446` and `src/core/native_dense.cpp`) | `nextn_predict_layers` | **P**: read nextn as the qwen35moe path does (`family_layout.hpp:64`) and load the block as the drafter. Upstream #4449 is open on exactly this. |

### 3.3 Hidden width n_embd = 2560, hyper-connections (hc = 4, hc_lr = 320, hc_dim = 10240)

Sites marked **(A)** `static_assert` against `kCompiledGeometry`, so a Qwen4-only rebuild cannot silently keep the old
value there. The other sites have no assert.

| value | file:line | takes |
|---|---|---|
| N 2560, HC 4, D 10240, LR 320 (A) | `src/kernels/cuda/fused_gr.cu:36-46` (+ `Q32_BLOCKS = N/32` :652, `H_TILE = 1280` :1159, `GS_SL = 2048` :1902, `Q8_KC = 640` (16 chunks, 4 a stream) :1983-1985, eps 1e-6 :3477, :3984). This is the hyper-connection read/write on every layer. | **T/R**: 4,072 lines of kernels tiled on N/32, N/2 and D/640 |
| our GR fork: NR = LR + HC = 324 = DW 9 x DR 9 x DG 4, DS = 20 slices of 512 | `fused_gr.cu:2823-2829` (ours, f16db7c72) | **R**. It only works for this factorization. The `gr_fork` guard turns it off on another shape. |
| N 2560, H 4, HISTORY 9 (A) | `src/kernels/cuda/native_ple_postops.cu:36-37` | T |
| `NG_N_EMBD == 2560 && NG_HC_DIM == 10240`, a literal assert | `src/kernels/cuda/ple.cu:239` | T |
| H 2560, FF 640 (A) | `src/kernels/cuda/s2_expert_grouped.cu:40-42` | T |
| CPU expert path H 2560, FF 640, NE 512 (A for H and FF) | `include/strata/kernels/cpu/expert.hpp:36-40` (MAXC 80, ROW_GU, ROW_D, arrays `q[H]`, `ff[FF]`, `ff[MAXT][FF]` :69-161); `src/kernels/cpu/pool.cpp:1221` (`thread_local gbuf[MAXT][FF]`); `src/kernels/cpu/expert_layout.cpp:487` (`native_fmt(gt, dt, H, FF)`); refusal in `src/core/expert_source.cpp:4727-4730` | Qwen4-only build: K (change the constants). Both models in one binary: **P/T** (arrays to max size or heap). This is the CPU tier from RAM, which takes most expert misses (~78 % in UPGRADE-ESTIMATE 8.3). |
| helper-card tier: H, FF, `CAP = kWindowMaxT * 10` | `src/core/remote_experts.cpp:20-22`; `src/core/peer_experts.cpp:29-30`, `:169`; `src/core/remote_expert_opt.cu:14` | P. These are the `--expert-cache-device1` experts that UPGRADE-ESTIMATE section 9 places. |
| native activation buffers: 4096 B (2560 as Q8_K = 2,920 B) and 1024 B (640 as Q8_0 = 680 B) | `include/strata/kernels/cpu/native_expert.hpp:17`, `:19` | **R** (capacity): **n_embd <= 3584** at Q8_K; **n_ff <= 960** at Q8_0, <= 768 at Q8_K. Above that, raise the constants (K) and re-check the pool's buffers. |
| shared-memory x of 4096 halves | `src/kernels/cuda/s2_gemv_fast.cu:41` | capacity: n_in <= 4096 |
| prompt path: N 2560, HC 4, D, LR 320, K 10, NE 512, C 10240, ZV 6144, HV 48; runtime refusal of other N/HC/LR/K at :1739 and of non-2560 x 640 experts at :1746 | `src/prefill/prefill.cpp:212-214` (90 code lines carry literal widths, e.g. :1396, :1465-1514, :2001-2037, :2556-2584, :4260-4268, :5036-5831, :7015-7063) | **P**, about 200 lines in one 7,797-line file |
| prompt kernels: N, HC, D, LR, S 128, HK 16, HV 48, C 10240; `24 * 256` and `24 * 512` in split_q / gate_attn :2470-2477; the blob layout `1280 * 640`, `2560 * 160` :2260-2285 | `src/prefill/kernels.cu:24-25` | **T/P** (3,410 lines) |
| hyper-connection down GEMM: `HX_N = 320`, `HX_K = 10240` | `src/prefill/wmma_gemm.cu:584`; tuning keys `N == 320 && K == 10240` in `src/prefill/gemm.cu:917-928`, and `K == 2560` / `N == 6144` / `12288` at :901-903 | T, plus re-tuning |
| nibble expert layout kNEmbd 2560, kNFf 640, kRows 1280, kItems 80, kSuper 10 | `include/strata/core/expert_nibble.hpp:62-66` | T (`STRATA_EXPERT_NIBBLE`, off in P028x) |
| decode expert fast paths: `ED_XB = 80`, `ED_HB = 20`, `S26_XMAX = 80`, `S26_HMAX = 20`; gated at run time on `L.n_embd == 2560` / `L.n_ff == 640` | `src/kernels/cuda/iq_kernels.cu:2464-2465`, `:3622`, `:3724`; gates :4100, :4276, :4590, :6291, :6324, :6348, :6475-6476 | Generic kernels run instead, slower. The speed paths need **T** per shape. |
| dense GEMV row-class thresholds 2048 / 4096 / 8192 / 12288 (the qkv, gate, q shapes) and the persistent grid 640 | `src/kernels/cuda/native_mmvq.cu:3857`, `:3912`, `:2522` | D: re-tune `STRATA_MMVQ_IL_ROWS` (P028x sets it per type x columns) |
| router-shaped fast read for `n_in == 2560` | `src/kernels/cuda/native_bf16.cu:72`, `:142`; `src/kernels/cuda/verify_kernels.cu:112` | falls back; T for speed |
| BF16 key gather scratch `kTok * 2560` | `src/program/generate.cpp:2994` | K |

**The asserted kernel sites** (13 against `kCompiledGeometry`, plus `ple.cu` against literals):
- `native_gdn.cu:39`, `fused_gdn.cu:14`, `verify_kernels.cu:33` (S only);
- `s2_expert_grouped.cu:42`;
- `qsa_decode_attn.cu:25`, `qsa_prompt_attn.cu:33`, `qsa_pattn.cu:58`;
- `native_qsa_score.cu:33`, `native_qsa_indexer.cu:37`, `qsa_select.cu:23`;
- `native_ple_postops.cu:37`, `fused_gr.cu:46`;
- `include/strata/kernels/cpu/expert.hpp:39`;
- `ple.cu:239` (asserts literals, not the struct).

**Unasserted kernel constants:**
- `native_gdn_preprocess.cu:35` (S 128);
- `native_flash_attn.cu:55` (`kv = head / 12`, 256-wide rows, :62-166);
- `gdn_chunk.cu:28`;
- `prefill/kernels.cu:24-25`;
- every `src/prefill/moe_*` file (3.4).

### 3.4 Expert FFN width n_ff = 640 (gate + up = 1280 rows), shared expert

| value | file:line | takes |
|---|---|---|
| `n_ff` load pin; shared == routed | `gguf_reader.hpp:739` and `:831` | K once the kernels take it |
| prompt expert kernels, blob layout `1280*640 / 2560*160`, WROWS 256, NFB = 1280/256 and 2560/256, CODE_LD 640/160 | `src/prefill/moe_fused.cu:51-54`, `:235`, `:404-423` | **T** per (N, FF) |
| v2 prompt kernels (ours): `kV2Embd 2560, kV2FF 640, kV2SharedBytes 99856`; NFB = (GU ? 1280 : 2560) / 256; output rows `(10 * AB)`; `dm[... * 2560]` | `include/strata/prefill/moe_fused_iq.hpp:63-64`; `src/prefill/moe_fused_iq.cu:1292-1561` (ours, 65837e059 / fdd2fffa8). Upstream's own forms are at :576, :916, :1681 (NFB) and :838, :1166, :1879 (`10 * AB`). | **R** for v2. The `prefill_v2` guard turns it off on another shape. Upstream's fused kernels: T. |
| MMQ blob: `O_D_CODES = 1280 * 640`...; `n_ff = 640, ne0 = 1024 (pad512)` | `src/prefill/moe_mmq.cu:114-123`, `:158` | T |
| weight-stationary prompt kernels: `GU_ROWS 1280, GU_K 2560, PIECES = 1280/128`; `DN_ROWS 2560, DN_K 640, NSTEP = 640/128, PIECES = 2560/128` | `src/prefill/moe_ws_gu_iq3.cu:28`, `moe_ws_gu_iq2.cu:34`, `moe_ws_down.cu:21`, `:36` | T, with tile divisibility |
| F16 prompt expert path: `GU_NFB = 640/64, D_NFB = 2560/128, GU_ACT_LD, H_LD`; stages `2560/64`, `640/64` | `src/prefill/moe_f16_common.cuh:49-51`; `src/prefill/moe_f16_kq.cu:44` | T |
| IQ4_NL down at K = 640 (= 2.5 x 256) has its own path: "no WK=256 path for this K" | `src/kernels/cuda/iq_kernels.cu:7059`, `:4590`, `:6476` | A Qwen4 n_ff that is a multiple of 256 (1024, 1280) picks other down kernels. Speed changes, nothing breaks. |
| pack and MTP tools: `H, FF, NE = 2560, 640, 512` | `tools/mtp_rt.py:27-28`, `tools/pack_layer.py:40-51` (the Q2_0 pack; not ours) | K (read them from the GGUF; `tools/iq_pack.py:447` already reads n_expert) |

### 3.5 Expert count 512 and experts per token 10

The decode path takes both at run time:
- `router_top10.cu` takes `n_expert` and `k`;
- verify (`src/core/verify.cpp:950`, `:1358-1360`) and the MTP drafter read `g.n_expert` and `ss.k`;
- the expert cache sizes slots from blob bytes.

The pins:

| value | file:line | effect on another count | takes |
|---|---|---|---|
| prompt path `K = 10`, `NE = 512` | `src/prefill/prefill.cpp:213`; refusal `ss.k != K` at :1739 | **other K: the batched prompt path refuses at start.** NE > 512: `kGrpEv = NE/16 + 2` events (:853) and `kHostBounds` (:902) are fixed sizes for 512 (out of range above that); the layer-major loops `e < NE` (:6788-6898) fail with "routed id out of range", and `host_res[l * NE + e]` assumes a stride of 512. | **P**: K and NE become runtime (about 140 lines use K, most of them `T * K` buffer sizes) |
| prompt combine unrolled for 10 | `src/prefill/kernels.cu:2342-2345` (`float4 v[10]; ww[10]; k < 10; t * 10`) | wrong for K != 10 | T (K as a template parameter) |
| helper tier `CAP = kWindowMaxT * 10` | `src/core/remote_experts.cpp:22`, `src/core/peer_experts.cpp:30` | K > 10 overflows the helper buffers | K |
| resident plan asserts `kVerifyMaxT * 10 <= 256` | `src/kernels/cuda/verify_kernels.cu:1404-1405` | K > 10 may break the "one thread per entry" rule | K, then check |
| native router `<NE, K>`, used at 512 / 10 only (`route`, `route_multi`); route-prior and route-resident only at 512 / 10 | `src/kernels/cuda/native_router.cu:49-309`; `src/core/layer.cpp:420`, `:446`; `src/core/verify.cpp:2219`, `:2251`, `:2253`; `src/core/mtp.cpp:1293-1303`; `src/kernels/cuda/route_prior.cu:33-34` | falls back to the generic router (the route-prior path is pinned off in P028x anyway) | T: one instantiation per (NE, K), NE a multiple of 32, K <= 32 |
| AMD wave router `n_expert <= 64 * 8` | `src/kernels/cuda/router_top10.cu:197` | HIP only | not ours |
| CPU-side default NE | `include/strata/kernels/cpu/expert.hpp:38`; `include/strata/core/expert_source.hpp:513`; `include/strata/kernels/cpu/expert_layout.hpp:20` | defaults, overwritten from the pack | K |
| pack tool | `tools/iq_pack.py:202` (`N_EXPERT = 512`; the real count is read at :447) | fine | none |
| MTP runtime pack `NE = 512` | `tools/mtp_rt.py:27` | **wrong experts.bin for another count** | K |
| profile | `tools/make_profile.py:33` (`--n-expert` flag exists) and `data/expert-profile.bin` | must be rebuilt | D |
| app constants | `strata_control/drafting.py:233` (`MAX_SLOTS = 24576` = 48 x 512), `:238` (`SLOT_MIB = 1.95`) | app sizing only | K |

### 3.6 GDN (state 128, 16 k heads, 48 v heads, conv 4, 10240 channels, 6144 value dim)

| value | file:line | takes |
|---|---|---|
| S = 128 (A) | `src/kernels/cuda/fused_gdn.cu:13`, `native_gdn.cu:38`, `verify_kernels.cu:32`; unasserted: `native_gdn_preprocess.cu:35`, `src/prefill/gdn_tc.cuh:321-332` (`GCH * S / 4 / 256`) | **T** (square 128 x 128 state, a warp per column) |
| S 128, HK 16, HV 48, C 10240 in the prompt path | `src/prefill/kernels.cu:25`, `src/prefill/gdn_chunk.cu:28`, `src/prefill/prefill.cpp:214` | P/T |
| head map `idx[h] = h % h_k` (not h / (h_v / h_k)) | `include/strata/kernels/gdn.hpp:7-11`, and the kernels | A model change, not a shape. A Qwen4 with grouped heads would need **R**. |
| decode GDN otherwise takes `g` (channels, value dim, heads) | `src/core/layer.cpp:245` | free |

### 3.7 Full attention ("QSA": 24 q / 2 kv heads, head dim 256, n_rot 64, indexer 4 / 128 / block 4 / top-k 2048)

| value | file:line | takes |
|---|---|---|
| HD 256, G = 24/2 = 12 (A) | `src/kernels/cuda/qsa_decode_attn.cu:23-25`, `qsa_prompt_attn.cu:31-33`, `qsa_pattn.cu:56-59` | **T** (shared-memory tiles by HD and G) |
| `kv = head / 12`, 256-wide rows, unasserted | `src/kernels/cuda/native_flash_attn.cu:55`, `:62-166` | T |
| our B.2 split attention reports its compiled HD / G to the guard | `src/core/patch_guard.cpp:188-195` | guarded |
| prompt path literals: `rms_rope_rows(m.Qf, 24 * 512, 512, m.q, 6144, ..., T, 24, 256, ...)`; indexer `512, 128, ..., 4, 128` | `src/prefill/prefill.cpp:4260-4268`; `src/prefill/kernels.cu:2470-2477` | P |
| indexer D 128, R 4, ROT 64 (A) | `src/kernels/cuda/native_qsa_indexer.cu:36-37` | T |
| indexer score D 128, HEADS 4, R 4 (A); refuses `idx_top_k != 2048` at run time | `src/kernels/cuda/native_qsa_score.cu:32-33`, `:197` | T |
| selection IDX_DIM 128, IDX_HEADS 4, R 4 (A); chunking `SP_CH = 2048` | `src/kernels/cuda/qsa_select.cu:22-23`, `:2448` | T |
| `qsa_real_shapes()` = 24 / 2 / 256 / 64 / 4 / 128 / 4 / 2048, page 4 | `include/strata/kernels/qsa.hpp:109-118`. `core::qsa_shapes(g)` (`include/strata/core/layout.hpp:29-40`) overrides everything but the page size. **Direct users that keep idx_block = 4:** `src/core/conversation_snapshot.cpp:26`, `:40`, `:318`, `:411`; `src/core/conversation_state.cpp:69`, `:124`, `:421`, `:452`; our side stash `src/program/generate.cpp:14795-14797`, `:14833` | K: use `qsa_shapes(g)` in each (about 10 lines) |
| KV page = 4 cells = one indexer block | `qsa.hpp:115` | tied to idx_block |

### 3.8 Rope, context, eps

| value | file:line | GGUF key | takes |
|---|---|---|---|
| freq base 1e7 | `include/strata/kernels/qsa.hpp:125`; `include/strata/kernels/rope_scaling.hpp:68` | `rope.freq_base` (in the file, not read) | **K** (the q36 path already reads it: `src/qwen35/q36_engine.cu:978`) |
| trained context 262144 (the YaRN default) | `rope_scaling.hpp:71`; `generate.cpp:640`, `:1091` | `context_length` (not read) | K |
| rotary 64 in the prompt rope: `powf(base, -2.0f / 64.0f)`, `kernel_args(64)` | `src/prefill/kernels.cu:3362-3363`, `:3387` | `rope.dimension_count` | K. Decode reads `n_rot` (`native_rope.cu:205`). |
| rope table 32 pairs a row | `include/strata/kernels/mrope.hpp:57-59` | `rope.dimension_count` | K (with `STRATA_ROPE_TABLE=1` only) |
| M-RoPE sections 11 / 11 / 10 / 0 as `pair % 3` | `mrope.hpp:49-52` | `rope.dimension_sections` (not read) | P. Pictures only; text has t = h = w. |
| RMS eps 1e-6 | `src/core/layer.cpp:54`, `src/core/verify.cpp:111`, `src/core/mtp.cpp:71`, `src/prefill/prefill.cpp:212`, `include/strata/kernels/ngram.hpp:42`, `include/strata/kernels/qsa.hpp:120`, `fused_gr.cu:3477`, `:3984` | `attention.layer_norm_rms_epsilon` (read and pinned) | K (about 8 sites) |

### 3.9 Vocabulary and special tokens

The head and the embedding take their tensors' shapes, so `n_vocab` is free. The special ids are literals:

| value | file:line | GGUF key | takes |
|---|---|---|---|
| EOS ids {248044, 248046} | `src/program/generate.cpp:899`; `serve/server.py:952` | `tokenizer.ggml.eos_token_id` (248046), `padding_token_id` / `bos_token_id` (248044) | K (`--eos-ids` overrides) |
| turn token 248045 (`<|im_start|>`) | `serve/server.py:2440` | in `tokenizer.ggml.tokens` | K |
| tool-call ids 248058 / 248066 / 248070 | `serve/frontend.py:269` | tokens list | K |
| image pad 248056 | `src/program/generate.cpp:13513` | `ple.image_token_id` | K |
| PLE EOS 248044 | `include/strata/kernels/ngram.hpp:37` | `ple.eos_token_id` | K |
| MTP draft vocabulary, a 40K-token subset of this tokenizer | `include/strata/core/mtp.hpp:73-74` (`rt/draft_vocab.bin`, `data/draft_vocab_en.bin`); our spec_exact guard checks max id < n_vocab (`patch_guard.cpp:163-171`) | none | D (`tools/draft_vocab.py`), if the tokenizer changes |

If Qwen4 keeps Qwen3.5+'s tokenizer (`tokenizer.ggml.pre = qwen35`, 248320 tokens), none of these move.

### 3.10 The n-gram (PLE) table

| value | file:line | GGUF key | takes |
|---|---|---|---|
| **hash constants**: multipliers [23703573157769, 20109073645365, 8052911324071]; 16 head vocab sizes (20000003 ...); 16 offsets | `src/kernels/ngram.cpp:46-65`; used at `src/program/generate.cpp:5271` | `ple.layer_multipliers`, `ple.head_vocab_sizes`, `ple.head_offsets` | **K-P, ~20-30 lines. Silent today**: nothing compares them with the file. Upstream's split engine reads them (`src/split/src/model.cpp:1333-1362`). At minimum, refuse a mismatch at load. |
| NGRAM_SIZE 3, HEADS_PER_NGRAM 8, PLE_N_HEADS 16, PLE_CONV_KERNEL 4, NG_HIST 9 | `include/strata/kernels/ngram.hpp:33-40`; `PleConsts` arrays sized by them (:91-95); verify's history `HS = NG_HIST * NG_HC_DIM` (`src/core/verify.cpp:955`, `:1365`) | `ple.ngram_size`, `ple.heads_per_ngram`, `ple.conv_kernel` | P (array sizes become a maximum) |
| row width 160 = n_embd / 16, so 16 rows are exactly n_embd; NG_N_EMBD 2560; NG_HC 4 | `ngram.hpp:31-32`, `:38-39`; row bytes per format `:47-53`; gather into `out2560` (:182-222) | `embedding_length_per_layer_input` | T (ties to n_embd) |
| table rows 320,001,536 | `ngram.hpp:46` (comment-level; the reader takes `shape[1]`, `ngram.cpp:356`) | tensor shape | free |
| the PLE runs on layer 1 only | `src/program/generate.cpp:5222-5227`; `src/core/layer.cpp:1495` (`layer == 1`); `src/core/native_dense.cpp:159`, `:177`, `:241`, `:260` | `ple.layers` = [1] | K for another single layer. **P** if Qwen4 lists several. |
| PLE key/value projections [2560, 10240] / [2560, 2560], conv [4, 10240] | `include/strata/kernels/ple.hpp:44-60`; `native_ple_postops.hpp:9-15` | tensor shapes | via n_embd / hc |

**Not tied to the vocab:** the hash takes token ids mod about 20M primes, so a larger vocabulary does not change the
table. The EOS and image ids feed the hash, though.

### 3.11 The MTP head (one layer)

| value | file:line | takes |
|---|---|---|
| the source: repo `Qwen/Qwen3.8-Flash-Next` at `PINNED_REVISION de4b8e4d...`, SHA256 of 31 `mtp.*` tensors | `tools/mtp_fetch.py:40-51`, `:58-` (SHA256 table) | D: a new repo, revision and hash table. Or read an in-file nextn block (3.2). |
| pack layout `gate_up_proj [512, 1280, 2560]`, `down_proj [512, 2560, 640]` | `tools/mtp_pack.py:10-11`; writes arch `qwen4exp-mtp` (:144) | K |
| runtime pack `H, FF, NE = 2560, 640, 512`, `BLOB = 3 * (H * FF * 18 // 64)` | `tools/mtp_rt.py:27-28` | K |
| drafter structure: fc_embedding / fc_hidden, hyper-connection mixer, attention with indexer, 512 experts top-10 + shared, head = main head rows over the draft vocab | `include/strata/core/mtp.hpp:3-19`; `src/core/mtp.cpp` (it takes `g` for widths: :421, :1060, :1186) | free beyond the shared kernels' pins. Its slots `kMpSlots = 24` (`mtp.cpp:895`) and window 32768 (`mtp.hpp:49`) are not shapes. |
| tables measured on this drafter: cost gate `configs/r12-cost-gate.txt`; DRAFT_CUM's acceptance table (the guard requires arch `qwen4exp`, `patch_guard.cpp:209-216`) | | D: re-measure on Qwen4's drafter |

### 3.12 Tables, pools, scratch and graphs sized for the shape

| item | where | shape-bound? |
|---|---|---|
| expert profile (48 x 512 ranked pairs) | `data/expert-profile.bin`, `tools/make_profile.py:33` | **D** |
| expert slots (VRAM, helpers, RAM tier) | runtime, from blob bytes (`src/core/expert_cache.cpp`, `remote_experts.cpp`) | free. Fewer, larger slots. |
| per-layer decode graphs (`pre` / `post` per layer) | `src/core/session.cpp` (by `g.n_layers`) | free |
| verify windows T <= 8, MTP K_MAX 8, `kFusedGrMaxT 8`, `kAttnRowsMax 8` | `window_limits.hpp:15-21`, `spec/controller.hpp:23`, `fused_gr.hpp:70`, `qsa_decode_attn.hpp:36` | not model shapes |
| graph reserve 6 MiB a window graph, 48 MiB burst (measured on Flash-Next) | `include/strata/program/stage_reserve.hpp:42-43` | D: re-check at larger widths |
| decode / verify scratch arenas | runtime from `g` (`verify.cpp:950-956`, `:1358-1366`), except the PLE history (compile-time `NG_*`) | mostly free |
| prompt arenas | compile-time N / K / 640 / 1280 / 12288 (`prefill.cpp:1396`, `:1620-1648`, `:2001-2046`, `:2556-2584`, `:2830`) | P (with 3.3) |
| prompt chunk tables `{32768 ... 256}`, `kKeepRingChunk 6144`, `kWinHipAutoChunkCap 6144` | `generate.cpp:9368`, `:10309`, `:10718`; `prefill.cpp:2869`; `host_limits.hpp:19` | sizes, not shapes. Re-tune. |
| MMVQ row tuning (`STRATA_MMVQ_IL_ROWS` in P028x) and gemm tuning keys | `native_mmvq.cu:3647-3912`; `prefill/gemm.cu:901-928` | D |
| PLE row cache 1M rows, 256 in flight | `ngram.hpp:152-153` | free (bytes scale with the row width) |

### 3.13 Off our path (noted for completeness)

- **`src/split` (sFNX, the all-cards engine):**
  - All shapes are `constexpr`, chosen at build time with `make FNX_MODEL=fnx|27b` (`src/split/src/model.hpp:21-41`).
  - Flash-Next: N 2560 / 48 layers / 512 x top-10 / FF 640 / NKVH 2. Qwen3.8-27B dense: N 5120 / 64 layers / NKVH 4.
  - It reads the PLE hash constants and ids from the file (`model.cpp:1333-1362`).
- **DFlash2 drafter:** refuses unless `NH 32 / NKV 8 / HD 128 / rank 256 / N 2560` (`src/core/dflash2.cpp:172`).
  We use the MTP.
- **`src/qwen35` (Qwen3.6 path):**
  - A second engine with its own pins: router `NE = 256, K = 8` (`q36_kernels.cuh:314`), HD 256 and S 128
    (`q36_engine.cu:304`, `:344`, `:678`, `:749`).
  - It takes most other shapes from the file.
  - If Qwen4 dropped the hyper-connections and the indexer, this path (plain residual, dense attention) would be the
    nearer base.

---

## 4. What our 28 commits hard-code on top of upstream

| commit | where | pin | guard |
|---|---|---|---|
| f16db7c72, c7cf663d6 (GR fork) | `src/kernels/cuda/fused_gr.cu:2823-2829` (+ `include/strata/kernels/fused_gr.hpp`) | NR = LR + HC = 324 = 9 x 9 x 4, DS = 20 slices of 512 (D / 20), DSTEPS = 2 | `gr_fork`: off unless n_embd / hc / hc_lr equal the compiled ones (`patch_guard.cpp:196-203`) |
| 65837e059, fdd2fffa8 (STRATA_PREFILL_V2) | `include/strata/prefill/moe_fused_iq.hpp:63-64`; `src/prefill/moe_fused_iq.cu:1292-1561` | K = 2560 gate/up, 640 down, IQ3_XXS / IQ4_NL blocks, 99,856 B smem, `NFB = (GU ? 1280 : 2560) / 256`, row stride 2560 | `prefill_v2`: off unless 2560 / 640 + types + an sm_80+ card (`patch_guard.cpp:221-244`) |
| c1a2077bb .. dafa1a765 (ROUTER_Q8K) | `src/kernels/cuda/elementwise.cu:395-` | n_embd % 256 == 0 (generic otherwise) | `router_q8k` (`patch_guard.cpp:181-186`) |
| B.2 split attention (in v0.2.10 as `STRATA_QSA_SPLIT_ATTN`) | reports HD / G through `qsa_split_attn_geometry` | HD 256, G 12 | `qsa_split_attn` (`patch_guard.cpp:187-195`) |
| side mixer (`STRATA_SIDE_MIXER=2`) | | GDN x 3 + QSA, interval 4 | `side_mixer` (`patch_guard.cpp:172-180`) |
| 5765aa2bc (side stash) | `src/program/generate.cpp:14794-14833` | takes `idx_block` (4) and the page size from `qsa_real_shapes()`, not from `g` | **none**: switch to `core::qsa_shapes(g)` (K) |
| eddc0c583, 0fe78a39b (cost gate); 0df5f4c45 (DRAFT_CUM) | `configs/r12-cost-gate.txt` (data); `include/strata/spec/draft_cum.hpp` | tables measured on Flash-Next's drafter | `draft_cum`: off for an arch other than `qwen4exp` (`patch_guard.cpp:209-217`). The cost gate has no guard (it is data). |
| d8aa76f3d (SPEC_EXACT) | `src/kernels/cuda/sampler.cu`, `include/strata/core/spec_exact.hpp` | draft-vocab ids < n_vocab | `spec_exact` (`patch_guard.cpp:163-171`) |
| 785b1a1f7 (#619, partial) | `tools/iq_pack.py:439-446`; `src/core/native_dense.cpp` | the key name `qwen4exp.nextn_predict_layers` | none needed |
| 3ab636d54, 8a0cedc81, b92a2add3 (the guards themselves) | `src/core/patch_guard.cpp` | reads `<arch>.*` keys by the file's own prefix (:72-98) | n/a |

The serve and web-search commits hard-code no shapes.

**Net:** our layer is safe on a new shape. Every pinned patch turns itself off, except the side stash's `idx_block`.
What is left is upstream's pins.

---

## 5. Against Karl's Qwen4 guess: what breaks first

**The guess:**
- QWEN4-DAY1-PLAN: 240-300B total, 12-13B active, the same Qwen-style design.
- UPGRADE-ESTIMATE section 8.1 makes it concrete as 48 x 512 experts, top-10, an MTP drafter, dense 7-8.5B and
  9.4-11.8M parameters per expert (Flash-Next: 4.92M).
- 3 x n_embd x n_ff = 9.4-11.8M gives, for example:

| n_embd x n_ff | per expert | first capacity pin it hits |
|---|---|---|
| 2560 x 1280 | 9.83M | n_ff > 960: `kNativeHBytes` (`native_expert.hpp:19`); every 640 pin in 3.4 |
| 3072 x 1024 | 9.44M | every 2560 pin in 3.3. The PLE row becomes 192 if it stays n_embd / 16. hc_lr probably moves, and with it the GR fork (324 = 9 x 9 x 4 no longer factors). |
| 3072 x 1280 | 11.80M | both of the above |
| 4096 x 768 / 960 | 9.44 / 11.80M | n_embd > 3584: `kNativeActBytes` (`native_expert.hpp:17`); `MAX_SHARED_HALVES` 4096 is reached exactly |

Dense 7-8.5B against Flash-Next's 4.95B points at a larger n_embd, more layers, or both. A larger n_ff alone leaves the
dense part where it is. These are illustrations, not predictions.

**In the order the engine meets them:**

1. **Architecture name.** If it is not `qwen4exp`, `gguf_reader.hpp:681` refuses before any shape is read. The same
   happens to the pack tool's nextn key (`iq_pack.py:445`) and to the server's family tables. The fix is K (~10 lines),
   if everything else matches.
2. **Expert count.** It is not pinned at load. Below 512 it runs today: the 256-expert Coder is the precedent. Above 512:
   - **the prompt path breaks first:** the `prefill.cpp:213` `NE = 512` arrays (:853, :902), the layer-major loops
     (:6788-6898) and the `host_res` stride;
   - the native router and route-prior paths quietly fall back;
   - then the tools: `mtp_rt.py:27` writes a 512-expert drafter pack; `make_profile.py` needs `--n-expert`, and the
     profile must be rebuilt.
   - **Size:** P, ~40 lines in `prefill.cpp`, plus K edits in the tools and D for the profile.
3. **Experts per token.** It is not pinned at load (up to 64). **The prompt path refuses at start**
   (`prefill.cpp:1739`, `ss.k != K = 10`). The helper tier's `CAP = kWindowMaxT * 10` (`remote_experts.cpp:22`,
   `peer_experts.cpp:30`) is too small for K > 10. The prompt combine is unrolled for 10 (`kernels.cu:2342`).
   - **Size:** P, about 140 lines that use K in `prefill.cpp`, one template for the combine, and K edits for CAP and the
     resident-plan asserts. About a day.
4. **Layer count.** Pinned at load (`gguf_reader.hpp:812`, `family_layout.hpp:99-131`). Behind the pin the host code is
   n_layers-generic. Then:
   - the routing trace caps at 48 (`generate.cpp:1414`, `:1438`), which leaves the profile incomplete;
   - `make_profile.py:33`;
   - the KVA gate (off anyway);
   - the count must stay a multiple of 4 under the fixed 3:1 pattern. An irregular pattern needs P (3.1).
   - **Size:** K, ~10 lines plus the profile. **The cheapest of the four.**
5. **Widths** (n_embd, n_ff, hc_lr, heads, head dim, GDN heads). Pinned at load, and behind the pin about 40 files fix
   them at compile time:
   - **Qwen4-only build** (new `kCompiledGeometry` + every unasserted constant in 3.3-3.7, tilings re-checked, parity
     tests re-run): the 13 asserted sites fail to compile and show where to start. The unasserted ones must be found by
     list (this file). Rough size: several days of edits plus a full exactness / KL gate.
   - **One binary for both** (templates per shape and dispatch in `fused_gr.cu`, the QSA kernels, the GDN kernels and
     the prompt expert kernels; runtime plumbing in `prefill.cpp`, `prefill/kernels.cu` and the CPU tier): weeks.
   - **Order inside the class:**
     - n_ff alone hits the prompt expert kernels (3.4) and `kNativeHBytes`;
     - n_embd hits everything in 3.3, the PLE row width, `kNativeActBytes` above 3584, and our GR fork and v2 (both
       guarded off);
     - attention heads or head dim hit the QSA templates (3.7);
     - GDN heads hit only the prompt kernels (3.6); decode GDN takes them at run time.
6. **Whatever the shapes, the silent items need a check on day one:**
   - the PLE hash constants (`ngram.cpp:46-65`) against `ple.*`;
   - `ple.layers`, `ple.eos_token_id`, `ple.image_token_id`;
   - `rope.freq_base` and `context_length`, which are not read;
   - the EOS ids;
   - `idx[h] = h % h_k` in GDN, and the shared expert width equal to n_ff.

**What UPGRADE-ESTIMATE section 9 needs:**
- The L-c helper placement it studies runs through the helper tier, which is compiled for 2560 / 640 / top-10
  (`remote_experts.cpp:20-22`).
- Its slot math works from blob bytes, which is runtime, so the 4.05 MB experts are fine.
- Its ranking needs a profile built for Qwen4's layer and expert counts (`make_profile.py:33`).
- The bandwidth-weighted deal it proposes touches no shape. That is r22p028x's `generate.cpp:7596-7628`; in this base it is the deal at `generate.cpp:8383-8416`.
- **So section 9 holds for a Qwen4 that keeps the widths. If the widths change, the helper tier is part of the width
  work above.**

---

## Files

All under `work/qwen4-kit/scratch-a/`:

| file | contents |
|---|---|
| `ghdr.py` | header-only GGUF reader |
| `hdr1.txt`, `hdr2.txt` | metadata and tensor shapes of both shards |
| `params.py` | parameter counts by group |
| `lit_code.txt`, `lit_code_byfile.txt` | the 281 code lines (46 files, comments excluded) that carry a literal width or token id |
| `src_consts.txt`, `inc_consts.txt`, `ours_lits.txt` | grep dumps |
