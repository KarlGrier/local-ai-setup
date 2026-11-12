# Profile pack: Qwen3.8-Flash-Next (IQ3_S GSQ-RCO) on the daily Strata build (P028x + U + ADAPT_FETCH=2), one desktop PC

Generated 2026-11-11 by `profile_pack.py` 1.1 (2026-11-11) from measurement files that already existed (nothing was run for this pack). Every number carries a source tag `[S<n>]`; Appendix A resolves each tag to a file and line (paths are relative to the project repository; `notes/` = the project's notes folder, `../` = a sibling project folder).

**What this is.** How a 512-expert MoE model runs on one desktop PC with 24 GB of VRAM over two GPUs and 96 GB of RAM: Qwen3.8-Flash-Next (published as a preview of the Qwen4 architecture) as the ISTA-DASLab GSQ-RCO IQ3_S GGUF, on the Strata engine (upstream v0.2.8) plus the owner's patch series (build label **P028x**) on the **fetch build** (upstream's STRATA_ADAPT_FETCH, run beside the helper GPU) with STRATA_HC_UPMIX=1 (U) and STRATA_ADAPT_FETCH=2: **the daily build**, served locally on 127.0.0.1 since 2026-11-09 20:06. All routed experts sit in pinned RAM (46.8 GiB); the main GPU caches 18.7 % of them and a helper GPU another 13.4 %. Because routing is skewed, and because the fetch build keeps often-routed experts that it had to read over PCIe in the main GPU's cache, those two caches serve about 85 % of the routed expert work during decode (the 11-10 screen, section 5). Everything served is lossless by the owner's rule: no switch that changes outputs beyond rounding, and outputs should repeat run to run (an open question on this build: section 3 and section 9). **Sources:** every speed, placement, memory and timing figure in sections 4-8 was measured on the daily in its test form (the served config without the picture reader) on 2026-11-09 to 11-11: the v0.2.13 port's baseline gate, whose B arm is the daily (11-10 18:34-19:14); the switch gap (11-10 morning); the decode confirmation gap (11-10 21:42-21:53, with the decode-timing switch on); the ADAPT_FETCH gap's =2 arm and the adoption check (11-09); and the served log since the switch. Figures of other builds appear only in quoted comparison lines and in the already-tried list, each labelled with its build. This file is the test run of a generator that will write the same pack for Qwen4 on its release day; section 10 lists what today's files only approximate.

## At a glance

|  |  | src |
|---|---|---|
| model | Qwen3.8-Flash-Next GSQ-RCO: 48 layers (36 linear-attention + 12 full-attention), 512 routed experts (10 per token) + a shared expert; 176.9 B parameters stored (120.8 B routed experts, 51.2 B per-layer embedding table), about 6.7 B active per token; routed experts at 3.33 bits/weight (46.84 GiB) | [S1] |
| prompt speed, tok/s (median of passes) | short: B-write 1,652.4; short: A-edit 2,711.7; short: R3-extract5k 3,728.9; 16K: pp16k 3,963.2; 64K: pp64k 4,567.7 | [S32-S42] |
| decode speed, tok/s (median of passes) | short context: W1-think 168.9; short context: W2-code 177.1; short context: conv 156.1; short context: prose 144.8; short context: struct 230.4; near 16K (approx.): R1-verify20k 163.7; near 16K (approx.): W3-research 182.8; near 64K (approx.): R2-report54k 162.8 | [S43-S60] |
| routed experts served from (decode) | main GPU cache 67.4 %, helper GPU cache 17.2 %, PCIe 6.0 %, CPU 9.4 % (screen B, the daily (v0.2.13 gate, 11-10 18:34-18:51; 3 passes, one warm-up request each), 36 requests) | [S129-S131] |
| MTP drafting | 72.9 % of MTP drafts accepted, 3.65 tokens per verify window (screen B, the daily (v0.2.13 gate, 11-10 18:34-18:51; 3 passes, one warm-up request each)); per-position acceptance: not logged (section 6) | [S129-S131] |
| memory over 15 measured runs (guard lines) | MemAvailable never below 29.8 GiB; main GPU free VRAM never below 437 MiB; server + engine RSS up to 54.3 GiB; system swap in use (pages swapped before the runs) up to 1.19 GiB; helper GPU free VRAM never below 1287 MiB | [S163-S177] |
| swap | 104 MiB of swap growth inside 15 measured runs (1-s samples) | [S178-S192] |
| decode window (verify step) | 21.71 ms for 3.52 tokens; slowest part: GPU-reach wait (dense layers + the GPU's own MoE branch, host-measured) 9.10 ms (42 %); next: CPU pool (missed experts) inside the host's per-layer work 8.62 ms (40 %) | [S162] |

Approximations (see section 10): 12 measurements here stand in for ones release day takes directly.

## 1. Hardware and software

|  |  |
|---|---|
| main gpu | NVIDIA RTX 5080 16 GB, PCIe Gen5 x16 (runs the model; no display attached) [S3] |
| helper gpu | NVIDIA RTX 4060 Ti 8 GB on a chipset PCIe Gen4 x4 link (a second expert cache only) [S3] |
| cpu | AMD Ryzen 9 9950X3D, 16 cores / 32 threads, AVX-512 [S3] |
| ram | 96 GB DDR5-6000 (about 77 GB/s measured); the desktop display runs on the CPU's integrated graphics [S3] |
| storage | Samsung 9100 PRO 2 TB NVMe (Gen5 x4), holds the model files [S3] |
| cpu (this machine, /proc/cpuinfo) | AMD Ryzen 9 9950X3D 16-Core Processor |
| RAM visible to the OS (/proc/meminfo) | 92.0 GiB |
| OS kernel | Linux 7.0.0-42-generic |
| CUDA toolkit (the config's library folders) | cuda-13.3 [S4] |

## 2. The model

Read from the GGUF header with the tree's tools/gguf_reader.py [S1]: 2 shard(s), 1,224 tensors; no weights were read.

| header key | value |
|---|---|
| general.name | Qwen3.8-Flash-Next GSQ-RCO |
| general.description | A Preview of the Qwen4 Architecture |
| general.size_label | 512x56B |
| general.quantized_by | ISTA DASLab |
| general.repo_url | https://huggingface.co/ISTA-DASLab/Qwen3.8-Flash-Next-GSQ-RCO-GGUF |
| general.architecture | qwen4exp |
| general.file_type | 26 |
| vocabulary (tokenizer.ggml.tokens) | 248,320 |
| tokenizer.ggml.model | gpt2 |
| tokenizer.ggml.pre | qwen35 |
| attention.compress_ratios | [48 values; distinct: 0, 4] |
| attention.head_count | 24 |
| attention.head_count_kv | 2 |
| attention.indexer.head_count | 4 |
| attention.indexer.key_length | 128 |
| attention.indexer.top_k | 2048 |
| attention.key_length | 256 |
| attention.layer_norm_rms_epsilon | 1e-06 |
| attention.value_length | 256 |
| block_count | 48 |
| context_length | 262144 |
| embedding_length | 2560 |
| embedding_length_per_layer_input | 160 |
| expert_count | 512 |
| expert_feed_forward_length | 640 |
| expert_shared_feed_forward_length | 640 |
| expert_used_count | 10 |
| full_attention_interval | 4 |
| hyper_connection.count | 4 |
| hyper_connection.low_rank | 320 |
| ple.conv_kernel | 4 |
| ple.eos_token_id | 248044 |
| ple.head_offsets | [16 values] |
| ple.head_vocab_sizes | [16 values] |
| ple.heads_per_ngram | 8 |
| ple.image_token_id | 248056 |
| ple.layer_multipliers | 23703573157769, 20109073645365, 8052911324071 |
| ple.layers | 1 |
| ple.ngram_size | 3 |
| rope.dimension_count | 64 |
| rope.dimension_sections | 11, 11, 10, 0 |
| rope.freq_base | 1e+07 |
| ssm.conv_kernel | 4 |
| ssm.group_count | 16 |
| ssm.inner_size | 6144 |
| ssm.state_size | 128 |
| ssm.time_step_rank | 48 |

Layers seen in the tensor table: 48; with linear-attention (SSM / GDN) tensors: 36; with full-attention q/k tensors: 12. Sampling suggested by the header: temp 1, top_p 0.95, top_k 20 [S1].

**Parameters and quantization by tensor role** (computed from the tensor table; GiB = the tensors' bytes) [S1]

| role | parameters | GiB | bits/weight | tensors | types (tensor count) |
|---|---|---|---|---|---|
| routed experts | 120.80 B | 46.84 | 3.33 | 144 | IQ2_S x40, IQ4_NL x39, IQ3_XXS x34, IQ3_S x20, Q2_0 x9, IQ4_XS x2 |
| per-layer embedding table (lookup) | 51.20 B | 26.82 | 4.50 | 1 | IQ4_NL x1 |
| attention (+ indexer) | 2.13 B | 1.46 | 5.89 | 192 | Q6_K x73, F32 x48, BF16 x24, Q5_K x19, Q4_K x14, IQ4_XS x14 |
| hyper-connections | 0.64 B | 1.20 | 16.02 | 387 | BF16 x290, F32 x97 |
| output head | 0.64 B | 0.49 | 6.56 | 1 | Q6_K x1 |
| linear-attention (SSM / GDN) | 0.58 B | 0.44 | 6.49 | 252 | F32 x144, BF16 x72, Q6_K x29, Q5_K x4, Q4_K x3 |
| token embedding | 0.64 B | 0.31 | 4.25 | 1 | IQ4_XS x1 |
| shared expert | 0.24 B | 0.14 | 4.94 | 192 | BF16 x48, IQ4_NL x47, Q4_K x30, IQ4_XS x28, Q6_K x26, Q5_K x12, Q8_0 x1 |
| router | 0.06 B | 0.12 | 16.00 | 48 | BF16 x48 |
| per-layer embedding (PLE) weights | 0.03 B | 0.06 | 16.01 | 6 | F32 x3, BF16 x2, F16 x1 |
| **total** | **176.94 B** | **77.86** | 3.78 | 1224 |  |

Active per token: about **6.67 B** parameters = everything but the routed experts and the two lookup tables (4.31 B) + 10 of 512 routed experts per layer (2.36 B); the token embedding and the per-layer embedding table are looked up one row per token. [S1]

Routed-expert quant mix per projection (the quant varies by layer): [S1]

| projection | types |
|---|---|
| gate | IQ2_S in 20 layers, IQ3_XXS in 17 layers, IQ3_S in 10 layers, IQ4_XS in 1 layer |
| up | IQ2_S in 20 layers, IQ3_XXS in 17 layers, IQ3_S in 10 layers, IQ4_XS in 1 layer |
| down | IQ4_NL in 39 layers, Q2_0 in 9 layers |

Shards [S1]:

| shard | file size | tensor bytes | tensors |
|---|---|---|---|
| Qwen3.8-Flash-Next-GSQ-RCO-IQ3_S-00001-of-00002.gguf | 54.82 GB | 51.04 GiB | 1223 |
| Qwen3.8-Flash-Next-GSQ-RCO-IQ3_S-00002-of-00002.gguf | 28.80 GB | 26.82 GiB | 1 |

## 3. Engine build and configuration

|  |  |
|---|---|
| build label | the daily = P028x on the fetch build: upstream Strata v0.2.8 + the owner's patch series (P028x, served since 2026-10-30) + upstream's STRATA_ADAPT_FETCH commit and the owner's patch that runs it beside the helper GPU; served since 2026-11-09 20:06 with STRATA_HC_UPMIX=1 (since 11-09 11:39) and STRATA_ADAPT_FETCH=2. What the fetch patch does: when the main GPU has to read a missed expert from RAM over PCIe and that expert is routed clearly more often than the least-used expert in that layer of the main GPU's cache, the engine keeps the copy in that cache slot instead of dropping it after the window. |
| engine source | v0.2.8 + 31 commits (branch r23-adaptfetch f381bfdf55098dba601fab70e0d6c756a1da586f), tree 2260660993d533e03e71353191197d1697531082 [S5] |
| engine binary sha256 | `153ce47d3ef03e5c189dc8725d6f9165eecbb8868f3c088c2eada8460d739706` [S6] (re-hashed for this pack: matches) |
| engine's self-reported version | 0.1.54 [S7] |
| main GPU (engine log) | NVIDIA GeForce RTX 5080, compute capability 12.0 [S8] |

- The patch series carries, among others: exact speculative sampling (STRATA_SPEC_EXACT), the cost-aware draft gate and cumulative draft length, the fork hyper-connection read (STRATA_GR_FORK), Basalt-derived v2 prompt-expert kernels made bit-identical to the stock path (STRATA_PREFILL_V2), the router's Q8_K doorbell rows (STRATA_ROUTER_Q8K), a chat cache that parks conversations in RAM, and upstream 0.2.7's new defaults pinned off [S9].
- The fetch build (`v0.2.8 + 31` in SOURCE) is P028x's 28 commits plus three: upstream's STRATA_ADAPT_FETCH commit (24c6c2f68, from v0.2.12, which turns the switch off when a helper GPU is present); the owner's patch f381bfdf5 that runs it beside the helper (the PCIe share's pick list leaves out experts the helper holds, admissions go to the main GPU's cache only, per-request admission counters and an optional read-back check in serve mode) [S10] [S11]; and one commit to the Python server only (an HTTP 400 for a request that names a model which is not loaded), not in the engine binary [S12].
- With the switch unset the fetch build is bitwise P028x: exact7 7/7 at matched slots, 0 of 40 long-prompt first-token logit files differ [S13]. With =2 the GPU computes a different set of experts than P028x would, which changes outputs at rounding level [S14]; a served-mode sampled-distribution test (D2 1.83 against a noise bound of 11.35) and a read-back of the 91,345 slots admitted in a check run (0 differ) passed [S15]. exact7 runs without adaptation, where the switch does not act [S16]; it gave 7/7 with =2 set as well [S17].
- Exactness on the daily's own switches, 11-10: exact7 7/7 between the adoption check's run of the daily form (=2 + U) and the v0.2.13 port's run with the same switches, at matched slots [S18].
- **Repeatability (open).** In the served form, seeded requests repeated token for token over two fresh starts in the 11-10 morning test (8 of 8; STRATA_DEBUG=1) [S19], but not in the evening test, which ran with STRATA_DECODE_TIMING=1 as well: first differences at tokens 2-163, short prompts included, and the same on the fetch-off fallback [S20]. The owner's rule is that outputs repeat run to run; the desk check (the timing switch first, then timing-dependent expert placement: adaptive swaps, the live PCIe share, fetch admissions) has not run yet [S21]. exact7 (no adaptation, a fixed slot count) repeats.
- The engine reports `engine 0.1.54` as its session version even though the tree is v0.2.8 + 31; the SOURCE file names the branch commit.
- The served config file keeps the name P028x.json, and its own comment line still describes the build before the fetch patch [S9]; its `exe` names the fetch build [S22].

**Engine arguments** (the served config [S23]; paths replaced by what they hold):

| argument | value | what it does | line in [S23] |
|---|---|---|---|
| `--pack` | `the engine's native pack built from the GGUF (dense weights, expert blobs, tokenizer)` | dense weights and expert blobs in the engine's own layout | l. 4 |
| `--native` | `the model's GGUF, shard 1 of 2` | read the GGUF's tensors natively (no conversion) | l. 6 |
| `--ple-gguf` | `the model's GGUF, shard 2 of 2 (the per-layer embedding table)` | per-layer embedding table, rows read directly from the SSD | l. 8 |
| `--expert-profile` | `the expert routing-frequency profile shipped in the Strata tree` | order in which the GPU expert cache is filled at start | l. 10 |
| `--expert-cache` | `auto` | main-GPU expert cache sized to the free VRAM minus the reserve (4,585 slots here) | l. 12 |
| `--prefill` | `auto:16384` | prompt read in chunks of up to 16,384 tokens | l. 14 |
| `--spec` | `7` | up to 7 MTP drafts per verify window (window up to 8 tokens) | l. 16 |
| `--spec-min-p` | `0.5` | a draft is kept while its draft probability >= 0.5 (the cost gate and cumulative rule decide on top) | l. 18 |
| `--mtp` | `the MTP draft-layer pack (one draft layer + a reduced-vocabulary draft head)` | multi-token-prediction draft layer | l. 20 |
| `--max-context` | `131072` | context limit (the model's header allows 262,144) | l. 22 |
| `--kv` | `int8` | int8 KV cache | l. 24 |
| `--kv-resident` | `32768` | 32,768 of the 131,072 KV cells per attention layer stay in VRAM; the rest stream from pinned RAM | l. 26 |
| `--ple-inflight` | `128` | per-layer-embedding rows read ahead | l. 28 |
| `--vram-reserve-mib` | `713` | VRAM kept free on the main GPU when the cache is sized | l. 30 |
| `--chat-cache` | `16` | up to 16 parked conversations (prompt state) for follow-up requests | l. 32 |
| `--chat-cache-mib` | `12288` | RAM budget for parked conversations | l. 34 |
| `--expert-cache-device1` | `3300` | the helper GPU holds 3,300 experts (static; filled at start) | l. 36 |
| `--conversation-cache-mib` | `0` | upstream 0.2.3's automatic conversation cache off (it parks synchronously) | l. 38 |
| `--vision` |  | picture input on; the picture reader runs on the CPU in its own process | l. 40 |

**Environment switches** (29 keys) [S23]:

| switch | value | what it does / why | line in [S23] |
|---|---|---|---|
| `STRATA_IO_THREADS` | `64` | file-reading threads for the expert arena and the PLE rows | l. 60 |
| `CUDA_MODULE_LOADING` | `LAZY` | CUDA lazy module loading (less VRAM at start) | l. 61 |
| `CUDA_VISIBLE_DEVICES` | `<2 GPUs by UUID; UUIDs removed>` | GPU 0 = the RTX 5080 (main), GPU 1 = the RTX 4060 Ti (helper) | l. 62 |
| `STRATA_SPEC_EXACT` | `1` | exact speculative sampling: sampled requests draft from the draft model's own q and verify by accept / residual / bonus (patch series) | l. 63 |
| `STRATA_GR_V3` | `1` | hyper-connection read split over two kernels (upstream; rounding level) | l. 64 |
| `STRATA_PF_FUSED` | `1` | prompt experts on the fused int8 kernels | l. 65 |
| `STRATA_SIDE_MIXER` | `2` | the mixer's input-only work on graph branches (exact; owner's upstream PR) | l. 66 |
| `STRATA_ROUTER_Q8K` | `1` | the router's doorbell kernel also writes the CPU pool's Q8_K activation rows (patch series) | l. 67 |
| `STRATA_GR_FORK` | `1` | fork hyper-connection read (patch series) | l. 68 |
| `STRATA_QSA_SPLIT_ATTN` | `1` | decode attention split across blocks on the int8 mma path (rounding level) | l. 69 |
| `STRATA_MMVQ_IL` | `1` | interleaved quantized mat-vec kernels for the dense layers | l. 70 |
| `STRATA_ADAPT_LAG` | `2` | the adaptive expert tier's swaps are used once two windows old | l. 71 |
| `STRATA_DISJOINT_ADAPT` | `1` | the main cache never promotes an expert the helper already holds | l. 72 |
| `STRATA_COST_GATE` | `the cost-gate table fitted on this PC` | cost-aware draft length: prices draft steps 1-3 from this PC's measured row costs (patch series) | l. 73 |
| `STRATA_PREFILL_CPU_SHARE` | `0.4` | prompt chunks below the MAX send 40 % of the expert work to the CPU | l. 74 |
| `STRATA_MMVQ_IL_ROWS` | `23:2:0,1,2,1,1;23:3:0,4,4,4,4;23:4:0,2,2,4,4;12:2:0,1,1,1...` | per-layer row table for the interleaved mat-vec kernels (tuned on this PC) | l. 75 |
| `STRATA_PREFILL_CPU_SHARE_MAX` | `1792` | the CPU share applies only to prompt chunks under 1,792 tokens | l. 76 |
| `STRATA_DRAFT_CUM` | `1` | cumulative draft length: drafting continues while the product of the drafts' acceptance estimates stays above an adaptive threshold (adapted from Basalt; patch series) | l. 77 |
| `STRATA_PREFILL_V2` | `1` | v2 prompt-expert kernels (adapted from Basalt; bit-identical to the stock path in this build) | l. 78 |
| `STRATA_DEQUANT_WIDE` | `1` | wide dequantization of the prompt's dense weights (bit-exact) | l. 79 |
| `STRATA_DEFAULTS` | `026` | pins the 0.2.6 per-card defaults (0.2.7's new ones off) | l. 80 |
| `STRATA_ROUTE_PRIOR` | `0` | 0 = off: routing bias toward cached experts (adds KL) | l. 81 |
| `STRATA_PROMPT_ATTN_IMMA` | `0` | 0 = off: int8 tensor-core prompt attention (failed the owner's top-1 check) | l. 82 |
| `STRATA_PREFILL_LAYER_MAJOR` | `0` | 0 = off: layer-major prompt reading (0.2.7 default for layer splits) | l. 83 |
| `STRATA_PLE_AUTO_RAM` | `0` | 0 = off: keep the PLE table on the SSD (direct reads) instead of RAM | l. 84 |
| `STRATA_ROUTE_TAIL_SKIP` | `0` | 0 = off: upstream's lossy skip of low-ranked missed experts | l. 85 |
| `STRATA_ADAPT_ASYNC` | `0` | 0 = off: the asynchronous adaptive tier (not repeatable run to run) | l. 86 |
| `STRATA_HC_UPMIX` | `1` | hyper-connection up projection fused with its mix in one kernel, prompt path (upstream opt-in; exact here) | l. 87 |
| `STRATA_ADAPT_FETCH` | `2` | 2 = a missed expert that the main GPU read over PCIe is copied into the main cache when it is routed at least 1 and 0.5 more than the layer's least-used resident expert; in a layer where that ran, the adaptive tier's own swaps skip the experts the share can fetch (upstream v0.2.12 opt-in + the owner's helper-aware patch) | l. 88 |

`STRATA_MMVQ_IL_ROWS` in full: `23:2:0,1,2,1,1;23:3:0,4,4,4,4;23:4:0,2,2,4,4;12:2:0,1,1,1,1;12:3:0,0,0,2,2;12:4:0,2,2,1,1;13:2:0,1,1,1,1;13:3:0,1,2,2,1;13:4:0,1,2,2,2;14:2:0,0,0,1,4;14:3:0,2,2,4,4;14:4:0,2,2,1,2` [S24]

**Sampling (served):** temperature 1.0, top_p 0.95, top_k 20, min_p 0.05 [S25]. Every client path and every measurement arm uses these, except the decode fixtures' own temperatures (section 4). The GGUF header suggests the same temperature / top-p / top-k [S26]

**Measured form.** The speed, placement and memory runs used the served config without the picture reader (`--vision` and its CPU process off); args, env and engine are otherwise identical (the gate's and the switch gap's B, and the 11-09 F2 / S2, below). The decode-timing starts (the confirmation gap's B) add STRATA_DECODE_TIMING=1 and STRATA_DEBUG=1 (section 8).

- B (v0.2.13 gate) (the gate's B arm, the daily's test form: the served config minus the picture reader) vs the served config [S27]: args only in the served config: ['--vision']; args only in B (v0.2.13 gate): none; env differences (served, B (v0.2.13 gate)): none.
- B (switch gap) (the same) vs the served config [S28]: args only in the served config: ['--vision']; args only in B (switch gap): none; env differences (served, B (switch gap)): none.
- B (confirmation gap) (the same + the decode-timing switches (section 8)) vs the served config [S29]: args only in the served config: ['--vision']; args only in B (confirmation gap): none; env differences (served, B (confirmation gap)): STRATA_DEBUG None vs '1', STRATA_DECODE_TIMING None vs '1'.
- F2 (ADAPT_FETCH gap, 11-09) (the same form, a day earlier) vs the served config [S30]: args only in the served config: ['--vision']; args only in F2 (ADAPT_FETCH gap, 11-09): none; env differences (served, F2 (ADAPT_FETCH gap, 11-09)): none.
- S2 (adoption check, 11-09) (the same) vs the served config [S31]: args only in the served config: ['--vision']; args only in S2 (adoption check, 11-09): none; env differences (served, S2 (adoption check, 11-09)): none.

## 4. Speeds

Engine clock (the engine's own prompt and decode timers), cold prompts (nothing reused). **Fixtures** start a fresh engine for each test (Basalt's method): pp16k = a 16,676-token prompt + up to 32 tokens; pp64k = a 66,617-token prompt + 1 token; decode = three short-prompt texts with thinking off (conv 38 tokens at T 0.6 up to 1,200 tokens; struct 98 tokens at T 0.0 up to 8,192; prose 19 tokens at T 0.6 up to 1,200). **Screen** = 9 workloads in 3 groups, each pass on one fresh engine after one warm-up request, at the served sampling with thinking on: W1-think / W2-code / W3-research (short and long prompts, fixed 3,072 / 3,072 / 2,048 tokens), A-edit / B-write (agent tool-call turns), R1-verify20k / R2-report54k / R3-extract5k / R4-agent33k (research-style long prompts). 'Short prompt' = the screen's cold 1.4K-5K-token prompts; 'short-context decode' = W1 / W2 (110-125-token prompts) and the decode fixtures. All five sets are the daily in its test form; **B** and **B-screen** (the v0.2.13 gate's B arm, 3 passes) are the main ones, **B-screen-sw** (one pass) and **F2** / **F2-screen** (11-09) repeat the same form on other days.

**Headline speeds** (median over passes [min-max]; tok/s, engine clock):

| what | workload | tok/s | passes | set | src |
|---|---|---|---|---|---|
| prompt, short | B-write (1,370 tokens) | 1,652.4 [1,643.6-1,661.0] | 3 | B-screen | [S32-S34] |
| prompt, short | A-edit (2,677 tokens) | 2,711.7 [2,703.3-2,714.2] | 3 | B-screen | [S35-S37] |
| prompt, short | R3-extract5k (5,013 tokens) | 3,728.9 [3,676.3-3,746.4] | 3 | B-screen | [S38-S40] |
| prompt, 16K | pp16k (16,676 tokens) | 3,963.2 [3,931.1-3,995.6] | 3 | B | [S41] |
| prompt, 64K | pp64k (66,617 tokens) | 4,567.7 [4,566.3-4,567.8] | 3 | B | [S42] |
| decode, short context | W1-think (prompt 111, 3,072 tokens, T 1.0) | 168.9 [168.6-196.7] | 3 | B-screen | [S43-S45] |
| decode, short context | W2-code (prompt 124, 3,072 tokens, T 1.0) | 177.1 [169.5-180.0] | 3 | B-screen | [S46-S48] |
| decode, short context | conv (prompt 38, 1,056 tokens, T 0.6) | 156.1 [152.0-156.7] | 3 | B | [S49] |
| decode, short context | prose (prompt 19, 1,200 tokens, T 0.6) | 144.8 [141.2-150.1] | 3 | B | [S50] |
| decode, short context | struct (prompt 98, 7,230 tokens, T 0.0) | 230.4 [230.4-239.2] | 3 | B | [S51] |
| decode near 16K (APPROXIMATE) | R1-verify20k (prompt 24,240, 3,614 tokens) | 163.7 [163.3-165.3] | 3 | B-screen | [S52-S54] |
| decode near 16K (APPROXIMATE) | W3-research (prompt 26,729, 2,048 tokens) | 182.8 [177.7-185.8] | 3 | B-screen | [S55-S57] |
| decode at 16K (too few tokens to count) | pp16k: 26 tokens after the prompt | 104.6 | 3 | B | [S41] |
| decode near 64K (APPROXIMATE) | R2-report54k (prompt 54,070, 2,852 tokens) | 162.8 [153.9-163.1] | 3 | B-screen | [S58-S60] |

**Every workload in the inputs** (median [min-max] over passes; acceptance = drafts accepted / drafts offered, MTP and prompt-lookup drafts together):

| set | workload | prompt tokens | prompt tok/s | generated | decode tok/s | draft acceptance | temperature | passes | src |
|---|---|---|---|---|---|---|---|---|---|
| B | prose | 19 | 153.0 [152.4-153.8] | 1,200 | 144.8 [141.2-150.1] | 53.8 % | 0.6 | 3 | [S50] |
| B | conv | 38 | 117.5 [98.8-117.7] | 1,056 | 156.1 [152.0-156.7] | 64.0 % | 0.6 | 3 | [S49] |
| B | struct | 98 | 238.4 [231.4-242.8] | 7,230 | 230.4 [230.4-239.2] | 95.9 % | 0.0 | 3 | [S51] |
| B | pp16k | 16,676 | 3,963.2 [3,931.1-3,995.6] | 26 | 104.6 [100.2-105.9] | 75.0 % | 1.0 | 3 | [S41] |
| B | pp64k | 66,617 | 4,567.7 [4,566.3-4,567.8] | 1 | - | - | 1.0 | 3 | [S42] |
| B-screen | W1-think | 111 | 301.1 [299.7-312.8] | 3,072 | 168.9 [168.6-196.7] | 69.0 % | 1.0 | 3 | [S43-S45] |
| B-screen | W2-code | 124 | 411.3 [405.5-420.5] | 3,072 | 177.1 [169.5-180.0] | 70.6 % | 1.0 | 3 | [S46-S48] |
| B-screen | B-write | 1,370 | 1,652.4 [1,643.6-1,661.0] | 2,042 | 173.9 [171.8-180.2] | 71.4 % | 1.0 | 3 | [S32-S34] |
| B-screen | A-edit | 2,677 | 2,711.7 [2,703.3-2,714.2] | 316 | 174.5 [168.4-190.2] | 80.4 % | 1.0 | 3 | [S35-S37] |
| B-screen | R3-extract5k | 5,013 | 3,728.9 [3,676.3-3,746.4] | 1,264 | 193.8 [182.7-194.9] | 79.3 % | 1.0 | 3 | [S38-S40] |
| B-screen | R1-verify20k | 24,240 | 4,525.7 [4,525.5-4,530.0] | 3,614 | 163.7 [163.3-165.3] | 76.7 % | 1.0 | 3 | [S52-S54] |
| B-screen | W3-research | 26,729 | 4,648.1 [4,641.4-4,648.5] | 2,048 | 182.8 [177.7-185.8] | 80.1 % | 1.0 | 3 | [S55-S57] |
| B-screen | R4-agent33k | 33,417 | 4,452.0 [4,449.3-4,452.3] | 287 | 154.8 [151.5-156.3] | 71.6 % | 1.0 | 3 | [S61-S63] |
| B-screen | R2-report54k | 54,070 | 4,712.0 [4,711.6-4,714.5] | 2,852 | 162.8 [153.9-163.1] | 72.0 % | 1.0 | 3 | [S58-S60] |
| B-screen-sw | W1-think | 112 | 304.4 [304.4-304.4] | 3,072 | 198.4 [198.4-198.4] | 72.6 % | 1.0 | 1 | [S64] |
| B-screen-sw | W2-code | 123 | 411.9 [411.9-411.9] | 3,072 | 171.2 [171.2-171.2] | 65.9 % | 1.0 | 1 | [S65] |
| B-screen-sw | B-write | 1,371 | 1,685.5 [1,685.5-1,685.5] | 2,316 | 172.8 [172.8-172.8] | 70.8 % | 1.0 | 1 | [S66] |
| B-screen-sw | A-edit | 2,676 | 2,731.4 [2,731.4-2,731.4] | 363 | 166.8 [166.8-166.8] | 77.5 % | 1.0 | 1 | [S67] |
| B-screen-sw | R3-extract5k | 5,010 | 3,738.8 [3,738.8-3,738.8] | 1,209 | 196.9 [196.9-196.9] | 80.0 % | 1.0 | 1 | [S68] |
| B-screen-sw | R1-verify20k | 24,240 | 4,531.3 [4,531.3-4,531.3] | 3,530 | 160.8 [160.8-160.8] | 74.1 % | 1.0 | 1 | [S69] |
| B-screen-sw | W3-research | 26,728 | 4,644.6 [4,644.6-4,644.6] | 2,048 | 175.3 [175.3-175.3] | 76.9 % | 1.0 | 1 | [S70] |
| B-screen-sw | R4-agent33k | 33,417 | 4,462.1 [4,462.1-4,462.1] | 435 | 146.5 [146.5-146.5] | 66.4 % | 1.0 | 1 | [S71] |
| B-screen-sw | R2-report54k | 54,071 | 4,717.2 [4,717.2-4,717.2] | 2,718 | 152.2 [152.2-152.2] | 67.6 % | 1.0 | 1 | [S72] |
| F2 | prose | 19 | 155.1 [149.8-157.2] | 1,180 | 142.8 [142.0-145.6] | 51.9 % | 0.6 | 4 | [S73-S76] |
| F2 | conv | 38 | 116.2 [101.3-118.8] | 1,094 | 156.2 [154.6-171.6] | 64.6 % | 0.6 | 4 | [S77-S80] |
| F2 | struct | 98 | 243.4 [241.2-246.2] | 7,230 | 237.4 [234.4-240.9] | 96.3 % | 0.0 | 4 | [S81-S84] |
| F2 | pp16k | 16,676 | 3,975.6 [3,975.6-3,975.6] | 32 | 121.0 [121.0-121.0] | 73.1 % | 1.0 | 1 | [S85] |
| F2 | pp64k | 66,617 | 4,564.8 [4,564.8-4,564.8] | 1 | - | - | 1.0 | 1 | [S86] |
| F2-screen | W1-think | 111 | 306.4 [300.1-319.2] | 3,072 | 178.5 [173.6-199.1] | 71.8 % | 1.0 | 3 | [S87-S89] |
| F2-screen | W2-code | 125 | 415.4 [405.8-418.6] | 3,072 | 174.3 [172.3-174.8] | 69.2 % | 1.0 | 3 | [S90-S92] |
| F2-screen | B-write | 1,369 | 1,666.5 [1,663.8-1,674.2] | 2,438 | 167.8 [164.8-206.4] | 70.3 % | 1.0 | 3 | [S93-S95] |
| F2-screen | A-edit | 2,676 | 2,715.5 [2,713.7-2,721.3] | 343 | 184.1 [172.9-187.2] | 84.0 % | 1.0 | 3 | [S96-S98] |
| F2-screen | R3-extract5k | 5,012 | 3,667.5 [3,656.7-3,735.7] | 1,193 | 199.6 [182.0-201.6] | 82.5 % | 1.0 | 3 | [S99-S101] |
| F2-screen | R1-verify20k | 24,238 | 4,534.5 [4,531.5-4,538.0] | 3,647 | 168.4 [164.2-168.9] | 77.5 % | 1.0 | 3 | [S102-S104] |
| F2-screen | W3-research | 26,728 | 4,653.1 [4,637.9-4,655.2] | 2,048 | 181.8 [181.0-188.9] | 77.7 % | 1.0 | 3 | [S105-S107] |
| F2-screen | R4-agent33k | 33,417 | 4,460.3 [4,459.2-4,460.6] | 281 | 151.8 [150.4-153.7] | 69.5 % | 1.0 | 3 | [S108-S110] |
| F2-screen | R2-report54k | 54,070 | 4,712.7 [4,710.0-4,714.2] | 3,304 | 158.6 [156.5-169.4] | 70.5 % | 1.0 | 3 | [S111-S113] |

Sets: **B** = the daily: pp16k / pp64k / decode, 3 cold passes each, in the v0.2.13 gate (11-10 18:55-19:14; its bp90 rows 'M'); **B-screen** = the daily: the 9-workload screen, 3 passes, in the v0.2.13 gate (11-10 18:34-18:51); **B-screen-sw** = the daily: the same screen, one pass, in the switch gap (11-10 11:41); **F2** = the daily's form on 11-09: decode 3 passes in the ADAPT_FETCH gap (17:54-18:03) + 1 pass of pp16k / pp64k / decode in the adoption check (20:02-20:05); **F2-screen** = the daily's form on 11-09: the screen, 3 passes, in the ADAPT_FETCH gap (its arm F2, 18:13-18:34).

- Two workloads (W1-think, R1-verify20k) are two engine requests each: the server ends the thinking pass at its room limit and continues the answer in a second request that reuses the first's state (it reads 19 new tokens) [S114]. The numbers above count the whole reply, and the server adds the continuation's ~90 ms prompt read to the prompt time, so R1-verify20k's prompt rate reads ~1.6 % low (pass 1: 4,525.7 tok/s for the reply vs 4,601.4 for its first engine request) [S115] [S52]; W1-think's 111-token prompt rate means nothing for the same reason.
- The engine's prompt time of a screen request also holds the chat cache's save of the previous conversation, logged just before it: 3-10 ms before most workloads, 50 ms before R2-report54k (R1's 24K conversation, 578 MiB) and 106 ms before R3-extract5k (R2's 54K conversation, 1,238 MiB) in pass 1 [S116] [S117]. R3-extract5k's 5,012-token prompt therefore reads 3,728.9 tok/s, about 4,048 without the save. The gate's own per-workload prompt numbers subtract it [S118]; the save's time by size is in section 9 (Serving).
- The struct fixture (T 0.0, repetitive structured text) accepts ~96 % of drafts, so its 230-239 tok/s is the upper end; W1 / W2 at T 1.0 with thinking are the realistic short-context decode.
- Noise, as the spread of the daily's 3 passes in the gate: screen decode geomean 3.3 % (passes 170.8 / 176.4 / 170.8 tok/s) [S119], screen prompt geomean noise 1.1 % (the larger of the gate's two arms) [S120]; fixtures conv 3.0 %, struct 3.8 %, prose 6.1 %, pp16k 1.6 %, pp64k 0.0 % [S121]. The other runs of the same form agree within that: the switch gap's one screen pass (11-10 morning) decoded 170.4 tok/s [S122], the ADAPT_FETCH gap's three (11-09) 174.8 [S123].
- **How =2 came to be served** (11-09, against the P028x engine before the fetch patch, with U). The gap's frozen rule made =1 (screen decode +10.2 %) its proposal and failed =2 on one per-workload prompt check, R4-agent33k -0.1 % against a 0.1 % noise [S124] [S125]. The owner adopted =2 as a recorded exception for this decision only, with the rule unchanged: the loss is on the prompt path, which ADAPT_FETCH does not touch; =2 had the higher decode (+12.7 %); both quality checks passed [S126].

- v0.2.13 gate, screen decode geomean of 3 passes (client clock): B = the daily, P = the v0.2.13 port (not served): "speed screen decode: P -1.69 % vs B (B 172.7, P 169.8; noise 3.3 %) -> BORDERLINE" [S127]
- Same gate, screen prompt geomean (client clock minus the chat-cache save): "speed screen prompt: P -0.35 % vs B (B 2,194.6, P 2,186.9; noise 1.1 %) -> PASS" [S120]
- Same gate, the fixtures as Basalt's table reports them: mean (min-max, spread) of 3 cold passes; the blend is Basalt's token-weighted decode: "| the daily (P028x test form, the fetch build) | 154.9 (152.0-156.7, 3.0 %) | 233.3 (230.4-239.2, 3.8 %) | 145.4 (141.2-150.1, 6.1 %) | 206.1 (204.1-209.1, 2.4 %) +10.3 % | 3,963.3 (3,931.1-3,995.6, 1.6 %) -18.7 % | 4,567.3 (4,566.3-4,567.8, 0.0 %) -7.9 % | 3,927.3 (3,895.5-3,959.3, 1.6 %) | 4,550.0 (4,548.9-4,550.7, 0.0 %) |" [S121]
- Same fixtures against Basalt PR #90's published row (Basalt on an RTX 5080 on PCIe 4.0 x16, 9950X3D, 64 GB): "- the daily (P028x test form, the fetch build), cold: 16K prompt -18.7 %, 64K prompt -7.9 %, decode blend +10.3 % - PROMPT MORE THAN 15 % BEHIND" [S128]
- Switch gap (11-10 morning), one screen pass: B = the daily, P = the v0.2.13 port: "INFO screen speed (one pass each, no noise estimate): decode geomean P 166.1 vs B 170.4 tok/s (-2.5 %), prompt geomean P 2,203.1 vs B 2,205.1 tok/s (-0.1 %; the 11-07 amendment's client clock minus the save)" [S122]

## 5. Where the routed experts are served (decode)

Per request the engine logs: `decode expert cache hit rate: X% (H hits / L lookups); O more read by the GPU over PCIe or from another GPU (p% of all R routed)` and, with a helper GPU, `CUDA1: N expert entries`. Counted per routed (token column x layer x expert) entry: **main GPU cache** = H; **helper GPU cache** = N; **PCIe share** (the main GPU reads the expert from pinned RAM over PCIe) = O - N; **CPU** (the CPU pool computes it) = L - H. The four add up to R. The parser is adapted from the project's earlier placement study.

| log | subset | requests | routed entries | main GPU cache | helper GPU cache | PCIe share | CPU | src |
|---|---|---|---|---|---|---|---|---|
| screen B, the daily (v0.2.13 gate, 11-10 18:34-18:51; 3 passes, one warm-up request each) | all requests | 36 | 34,647,360 | 67.4 % | 17.2 % | 6.0 % | 9.4 % | [S129-S131] |
| screen B, the daily (v0.2.13 gate, 11-10 18:34-18:51; 3 passes, one warm-up request each) | requests with >= 200,000 routed entries | 31 | 33,777,600 | 67.5 % | 17.2 % | 6.0 % | 9.3 % | [S129-S131] |
| decode fixtures B, the daily (same gate, conv / struct / prose x3) | all requests | 9 | 15,422,400 | 72.2 % | 13.1 % | 5.9 % | 8.7 % | [S132-S134] |
| seeded requests B, the daily (confirmation gap starts B1 / B4 / B5, 11-10 21:42-21:53; STRATA_DECODE_TIMING=1) | all requests | 24 | 15,461,760 | 66.8 % | 17.4 % | 6.5 % | 9.3 % | [S135-S137] |
| seeded requests B, the daily (confirmation gap starts B1 / B4 / B5, 11-10 21:42-21:53; STRATA_DECODE_TIMING=1) | requests with >= 200,000 routed entries | 22 | 15,114,240 | 66.9 % | 17.3 % | 6.5 % | 9.3 % | [S135-S137] |
| screen B, the daily, one pass (switch gap, 11-10 11:41) | all requests | 12 | 11,824,320 | 67.6 % | 17.5 % | 5.8 % | 9.2 % | [S138] |
| screen B, the daily, one pass (switch gap, 11-10 11:41) | requests with >= 200,000 routed entries | 12 | 11,824,320 | 67.6 % | 17.5 % | 5.8 % | 9.2 % | [S138] |
| screen F2, the daily's form on 11-09 (ADAPT_FETCH gap, 3 passes, one warm-up request each) | all requests | 36 | 35,634,240 | 67.3 % | 17.3 % | 6.0 % | 9.4 % | [S139-S141] |
| screen F2, the daily's form on 11-09 (ADAPT_FETCH gap, 3 passes, one warm-up request each) | requests with >= 200,000 routed entries | 32 | 34,998,240 | 67.4 % | 17.2 % | 6.0 % | 9.3 % | [S139-S141] |
| decode fixtures F2, the daily's form on 11-09 (same gap) | all requests | 9 | 15,436,800 | 72.1 % | 13.1 % | 5.7 % | 9.0 % | [S142-S144] |
| served log on the daily, 11-09 20:06 - 11-11 08:03 (10 engine starts) | all requests | 54 | 222,623,520 | 69.2 % | 16.9 % | 5.3 % | 8.5 % | [S145] |
| served log on the daily, 11-09 20:06 - 11-11 08:03 (10 engine starts) | requests with >= 200,000 routed entries | 21 | 222,164,640 | 69.2 % | 16.9 % | 5.3 % | 8.5 % | [S145] |

Slots: the main GPU holds 4,585 experts (8.75 GiB) [S146] and the helper 3,300 (6.21 GiB) [S147], of 24,576 routed experts (48 layers x 512) [S1]: 18.7 % + 13.4 % = 32.1 % of the experts serve the shares above; the rest live in pinned RAM. The main cache is filled from a routing-frequency profile; an adaptive tier swaps experts in while decoding.

- PCIe share setting: the engine re-prices it while serving (`PCIe share: ... -> pcie_frac X`), 8 times in served log on the daily, 11-09 20:06 - 11-11 08:03 (10 engine starts): 0.40 x3, 0.45 x5 [S149].
- No `route tail skip` line in served log on the daily, 11-09 20:06 - 11-11 08:03 (10 engine starts): the lossy tail skip never acted [S145].

- Decode only. The prompt pass works differently: it borrows 3,231 of the main GPU's cache slots for its chunks [S150] (section 7), and chunks under 1,792 tokens send 40 % of the expert work to the CPU.
- What the fetch patch does on the daily: with STRATA_ADAPT_FETCH=2 a missed expert that the main GPU read over PCIe is kept in the main cache when it is routed clearly more often than the layer's least-used resident expert [S151]: about 82 admissions per verify window on the 11-10 screen (1,290,347 in 15,644 windows over the 3 passes' `fetch:` lines) [S152-S154], 84 on the decode fixtures and 86 on the seeded requests, while the adaptive tier's own swaps run at about 0.6 per window (=2 keeps them out of the layers where admissions ran) [S155]. Against the same screen on the P028x engine before the fetch patch (11-09, the same args with U), the main cache's share of routed entries rose from 62.6 to 67.3 % and the CPU's fell from 14.4 to 9.4 %; the helper's (17.3 %) and the PCIe share (about 6 %) stayed [S156] [S157].
- Admissions land only in the main (RTX 5080) cache. The helper's experts are static (filled at start), and the owner's patch makes the PCIe share's pick list leave out experts the helper holds; without that, the picks would go to the helper and never be fetched [S158] [S159].
- The served log since the switch is mostly long generations: its 21 requests with >= 200,000 routed entries hold 99.8 % of its routed entries and 351,419 of its 352,113 generated tokens, so it leans to long-context decode; read the screen as the main figure.

- The ADAPT_FETCH gap's own count, screen F2 (the daily's form, 11-09; cross-check of the F2 row): "F2 B3: 36 requests, admissions per window 82.875 (1,331,726 in 16,069 windows, 36 fetch lines); placement main 67.3 % / helper 17.3 % / PCIe 6.0 % / CPU 9.4 % of 35,634,240 routed; decode 172.6 tok/s (engine)" [S156]
- The same gap's screen on the P028x engine before the fetch patch (same args, 11-09; the 'before' of the patch): "P B3: 36 requests, admissions per window - (no fetch line); placement main 62.6 % / helper 17.3 % / PCIe 5.7 % / CPU 14.4 % of 37,412,160 routed; decode 157.8 tok/s (engine)" [S157]
- The same gap's decode fixtures on the P028x engine before the fetch patch: "P B2: 9 requests, admissions per window - (no fetch line); placement main 69.9 % / helper 13.1 % / PCIe 6.1 % / CPU 10.9 % of 15,169,920 routed; decode 198.4 tok/s (engine)" [S160]

## 6. MTP speculative drafting

Drafting: one MTP draft layer (837 MiB of VRAM) with a 40,525-token draft head, `--spec 7` (verify windows of up to 8 tokens), `--spec-min-p 0.5`, the cost gate pricing draft steps 1-3 and the cumulative draft-length rule past them; exact speculative sampling. The engine also drafts from earlier repeats in the context (prompt lookup, `--suffix-draft`, default 3); those drafts are logged apart and subtracted below.

| log | requests | verify windows | all drafts accepted | MTP drafts accepted | prompt-lookup drafts accepted | drafts per MTP window | tokens per window | src |
|---|---|---|---|---|---|---|---|---|
| screen B, the daily (v0.2.13 gate, 11-10 18:34-18:51; 3 passes, one warm-up request each) | 36 | 15,644 | 41,470 / 56,538 = 73.3 % | 38,749 / 53,125 = 72.9 % | 2,721 / 3,413 in 657 windows | 3.56 | 3.65 | [S129-S131] |
| decode fixtures B, the daily (same gate, conv / struct / prose x3) | 9 | 5,941 | 22,515 / 26,189 = 86.0 % | 21,128 / 24,644 = 85.7 % | 1,387 / 1,545 in 271 windows | 4.36 | 4.79 | [S132-S134] |
| seeded requests B, the daily (confirmation gap starts B1 / B4 / B5, 11-10 21:42-21:53; STRATA_DECODE_TIMING=1) | 24 | 7,320 | 18,526 / 24,892 = 74.4 % | 17,969 / 24,124 = 74.5 % | 557 / 768 in 174 windows | 3.40 | 3.53 | [S135-S137] |
| screen B, the daily, one pass (switch gap, 11-10 11:41) | 12 | 5,327 | 13,817 / 19,307 = 71.6 % | 13,098 / 18,367 = 71.3 % | 719 / 940 in 207 windows | 3.60 | 3.59 | [S138] |
| screen F2, the daily's form on 11-09 (ADAPT_FETCH gap, 3 passes, one warm-up request each) | 36 | 16,069 | 42,746 / 58,169 = 73.5 % | 40,418 / 55,279 = 73.1 % | 2,328 / 2,890 in 580 windows | 3.59 | 3.66 | [S139-S141] |
| decode fixtures F2, the daily's form on 11-09 (same gap) | 9 | 5,920 | 22,595 / 26,240 = 86.1 % | 21,266 / 24,732 = 86.0 % | 1,329 / 1,508 in 274 windows | 4.40 | 4.82 | [S142-S144] |
| served log on the daily, 11-09 20:06 - 11-11 08:03 (10 engine starts) | 54 | 131,142 | 221,079 / 332,657 = 66.5 % | 212,489 / 321,871 = 66.0 % | 8,590 / 10,786 in 2,314 windows | 2.52 | 2.69 | [S145] |

Tokens per window = (drafts accepted + windows) / windows: each verify window commits its accepted drafts plus one token of its own. MTP = all drafts minus the prompt-lookup (`suffix drafts`) lines.

**Acceptance per draft position: not in these logs.** The Qwen engine prints it only with `STRATA_SPEC_DEPTH=1` (serve mode, positions 1-5, accepted / tested), and no existing run had it on. What exists: the per-request totals above and the decode-timing pass's mean window width (section 8).

- The cumulative rule's threshold adapts per request between 0.371 and its floor 0.265 [S161]; the 'drafts per MTP window' column shows where it settles for each kind of text: greedy and low-temperature fixtures ~4.4, the screen and the seeded requests at T 1.0 with thinking ~3.4-3.6.
- The served log is mostly long research-style generations; its acceptance is lower than the screen's and not comparable with it.

- Decode-timing pass on the daily (section 8): mean verify-window width T and tokens per window (tok/w): "24 requests, 7320 windows: 21.71 ms/window = GPU-reach 9.10 + host 9.48 (plan 0.75, CPU 8.62) + draft 2.33 + tail 0.77; T 4.40, 3.52 tok/w" [S162]

## 7. Memory: RAM, VRAM and swap

**At engine start** (one start of the measured form [S152]):

| what | value | line in [S152] |
|---|---|---|
| engine memory guard: limit / available at start | 92.0, 87.2 | l. 2 |
| helper GPU free before its expert arena | 7.56 | l. 3 |
| PCIe probe and the start-up PCIe share | 57.8, 0.55 | l. 4 |
| dense weights from the native pack (MiB) | 1466 | l. 6 |
| native projection matrices (count, MiB) | 300, 2018.88 | l. 7 |
| expert routing profile: ranked (layer, expert) pairs | 24,576 | l. 10 |
| KV cache: cells per attention layer in VRAM / total, K/V in pinned RAM (GiB) | 32,768, 131,072, 1.55 | l. 11 |
| per-layer-embedding table rows (read from the second shard) | 320,001,536 | l. 12 |
| MTP draft layer in VRAM (MiB: total, experts, dense) | 837, 675, 111 | l. 13 |
| output head as loaded (bytes) | 521,472,000 | l. 14 |
| expert arena loaded into pinned RAM (GiB, GiB/s) | 46.84, 6.24 | l. 18 |
| CPU expert-pool workers | 15 | l. 21 |
| main GPU free / reserve when sizing the expert cache | 9.53, 713 | l. 28 |
| main GPU expert cache (slots, GiB) | 4585, 8.75 | l. 29 |
| helper GPU expert cache (experts, GiB) | 3300, 6.21 | l. 35 |
| prompt chunk | 16,384 | l. 40 |
| prompt path borrows main-cache slots (slots, GiB) | 3231, 6.13 | l. 41 |
| verify window (tokens) | 8 | l. 44 |
| MTP draft head vocabulary (tokens, MiB) | 40,525, 81.2 | l. 45 |
| main GPU free with everything loaded (MiB) | 524 | l. 50 |
| cumulative draft-length threshold (start, floor) | 0.371, 0.265 | l. 52 |
| cost gate table bins | 60 | l. 51 |

**Per run, from the server guard's summary line** (whole process tree; GPU free memory from nvidia-smi):

| run | s | min_MemAvailable | min_5080_free | max_tree_RSS | max_swap_used | min_4060Ti_free | guard | src |
|---|---|---|---|---|---|---|---|---|
| g1311101804-B1 | 199 | 32.7 GiB | 443 MiB | 54.3 GiB | 0.4 GiB | 1287 MiB | ok | [S163] |
| g1311101804-B2 | 197 | 32.7 GiB | 441 MiB | 54.3 GiB | 0.4 GiB | 1287 MiB | ok | [S164] |
| g1311101804-B3 | 207 | 32.7 GiB | 443 MiB | 54.3 GiB | 0.4 GiB | 1287 MiB | ok | [S165] |
| g1311101804-bpM-decode-1 | 94 | 35.8 GiB | 441 MiB | 51.1 GiB | 0.4 GiB | 1287 MiB | ok | [S166] |
| g1311101804-bpM-decode-2 | 93 | 35.8 GiB | 441 MiB | 51.1 GiB | 0.4 GiB | 1287 MiB | ok | [S167] |
| g1311101804-bpM-decode-3 | 92 | 35.8 GiB | 443 MiB | 51.1 GiB | 0.4 GiB | 1287 MiB | ok | [S168] |
| g1311101804-bpM-pp16k-1 | 51 | 35.6 GiB | 473 MiB | 51.2 GiB | 0.4 GiB | 1287 MiB | ok | [S169] |
| g1311101804-bpM-pp16k-2 | 51 | 35.8 GiB | 473 MiB | 51.2 GiB | 0.4 GiB | 1287 MiB | ok | [S170] |
| g1311101804-bpM-pp16k-3 | 51 | 35.7 GiB | 465 MiB | 51.2 GiB | 0.4 GiB | 1287 MiB | ok | [S171] |
| g1311101804-bpM-pp64k-1 | 61 | 35.3 GiB | 501 MiB | 51.5 GiB | 0.4 GiB | 1287 MiB | ok | [S172] |
| g1311101804-bpM-pp64k-2 | 61 | 35.4 GiB | 501 MiB | 51.5 GiB | 0.4 GiB | 1287 MiB | ok | [S173] |
| g1311101804-bpM-pp64k-3 | 61 | 35.4 GiB | 501 MiB | 51.5 GiB | 0.4 GiB | 1287 MiB | ok | [S174] |
| c1311102142-B1 | 122 | 29.8 GiB | 437 MiB | 52.6 GiB | 1.19 GiB | 1287 MiB | ok | [S175] |
| c1311102142-B4 | 123 | 31.1 GiB | 437 MiB | 52.6 GiB | 1.19 GiB | 1287 MiB | ok | [S176] |
| c1311102142-B5 | 124 | 30.5 GiB | 437 MiB | 52.6 GiB | 1.19 GiB | 1287 MiB | ok | [S177] |

**Swap during each run** (1-second system samples from the run's monitor; MiB of swap in use: first -> max -> last):

| run | samples | min MemAvailable GiB | max engine RSS GiB | swap used MiB | swap growth | src |
|---|---|---|---|---|---|---|
| monitor-g1311101804-B1 | 201 | 32.7 | 54.1 | 405 -> 405 -> 405 | 0 MiB in 0 steps | [S178] |
| monitor-g1311101804-B2 | 200 | 32.7 | 54.1 | 405 -> 405 -> 405 | 0 MiB in 0 steps | [S179] |
| monitor-g1311101804-B3 | 209 | 32.7 | 54.1 | 405 -> 405 -> 405 | 0 MiB in 0 steps | [S180] |
| monitor-g1311101804-bpM-decode-1 | 96 | 35.8 | 50.8 | 405 -> 405 -> 405 | 0 MiB in 0 steps | [S181] |
| monitor-g1311101804-bpM-decode-2 | 95 | 35.8 | 50.8 | 405 -> 405 -> 405 | 0 MiB in 0 steps | [S182] |
| monitor-g1311101804-bpM-decode-3 | 94 | 35.8 | 50.8 | 405 -> 405 -> 405 | 0 MiB in 0 steps | [S183] |
| monitor-g1311101804-bpM-pp16k-1 | 53 | 35.6 | 51.0 | 405 -> 405 -> 405 | 0 MiB in 0 steps | [S184] |
| monitor-g1311101804-bpM-pp16k-2 | 53 | 35.8 | 51.0 | 405 -> 405 -> 405 | 0 MiB in 0 steps | [S185] |
| monitor-g1311101804-bpM-pp16k-3 | 53 | 35.8 | 51.0 | 405 -> 405 -> 405 | 0 MiB in 0 steps | [S186] |
| monitor-g1311101804-bpM-pp64k-1 | 63 | 35.4 | 51.3 | 405 -> 405 -> 405 | 0 MiB in 0 steps | [S187] |
| monitor-g1311101804-bpM-pp64k-2 | 63 | 35.5 | 51.3 | 405 -> 405 -> 405 | 0 MiB in 0 steps | [S188] |
| monitor-g1311101804-bpM-pp64k-3 | 63 | 35.5 | 51.3 | 405 -> 405 -> 405 | 0 MiB in 0 steps | [S189] |
| monitor-c1311102142-B1 | 124 | 29.8 | 52.4 | 1109 -> 1213 -> 1213 | 104 MiB in 3 steps | [S190] |
| monitor-c1311102142-B4 | 125 | 31.1 | 52.4 | 1213 -> 1213 -> 1213 | 0 MiB in 0 steps | [S191] |
| monitor-c1311102142-B5 | 126 | 30.5 | 52.4 | 1213 -> 1213 -> 1196 | 0 MiB in 0 steps | [S192] |

- RAM available with no engine loaded (the v0.2.13 gate's open, 11-10 18:05): "=== 2026-11-10 18:05:35 8080 down: engines left: none MemAvailable 86 GB; deadline 20:15 (130 min)" [S193]
- Restart of the served engine after the gate (11-10 19:19): "2026-11-10 19:19:27 port_gap4: WARNING: 86 MB swapped out while P028x started" [S194]
- Restart of the served engine after the switch gap (11-10 11:47): "2026-11-10 11:47:41 port_gap4: no swap-out while P028x started" [S195]
- Restart of the served engine after the confirmation gap (11-10 22:09): "2026-11-10 22:09:22 port_gap4: no swap-out while P028x started" [S196]

- The engine warned 10 times in the served log on the daily, 11-09 20:06 - 11-11 08:03 (10 engine starts) that the main GPU had under 512 MiB free at a request's start (lowest 504 MiB) [S197]: the cache is sized to leave only the configured reserve.

- The owner's guard stops a run if the main GPU's free memory falls under 300 MiB or MemAvailable under 12 GiB [S198] [S199]; every run above ended `ok`.
- Swap: about 0.4 GiB of other programs' pages were swapped out before the gate's runs and none moved inside them. The confirmation gap's first start (B1) pushed 104 MiB more out in three 1-second steps while the engine loaded (seconds 10-12 of the run, 1,109 -> 1,213 MiB); no further swap-out followed in it or in the two later starts (B5 ended 17 MiB lower) [S200]. The owner's swap rule fails a run on the engine's own swap or on sustained swap traffic inside it, and logs a run's first one-off push-out of other programs' idle pages rather than failing it [S201]; the monitors record system swap only, not the engine's own. One restart of the served engine (after the gate) pushed 86 MB out (quoted above).
- The served config adds the CPU picture reader (about 1 GB of RAM in its own process), not in these runs [S202].
- VRAM use is flat by design: the main GPU's expert cache takes all but the reserve at start, so its free memory is the reserve's remainder (about 435-500 MiB) whatever the context; the KV cells past 32,768 per attention layer live in 1.55 GiB of pinned RAM allocated at start, so a 64K prompt costs prompt time and a little RSS (51.5 vs 51.2 GiB for 16K), not VRAM. The screen runs' RSS (54.3 GiB) includes the conversations parked by the chat cache. The fetch patch adds about 260 bytes of VRAM, carved after the cache is sized, so the main cache keeps its 4,585 slots [S203].

## 8. Where a decode window's time goes (the slowest step)

24 requests, 7,320 windows [S162]; window width 4.40 columns, 3.52 tokens per window = 6.17 ms per token (162 tok/s inside the windows).

| part of a window | ms | share |
|---|---|---|
| GPU-reach wait (dense layers + the GPU's own MoE branch, host-measured) | 9.10 | 41.9 % |
| CPU pool (missed experts) inside the host's per-layer work | 8.62 | 39.7 % |
| host plan + other per-layer host work | 0.86 | 4.0 % |
| MTP drafting between windows | 2.33 | 10.7 % |
| tail (head, sampling, launch) | 0.77 | 3.5 % |
| **window** | **21.71** | 100 % |

**Slowest step: GPU-reach wait (dense layers + the GPU's own MoE branch, host-measured), 9.10 of 21.71 ms (42 %)** [S162].
Per layer-window: GPU-reach 189.6 us, CPU 179.7 us, plan 15.65 us; distinct CPU experts 3.90, PCIe experts 1.92, VRAM hit entries 29.4 [S204].
Helper GPU: 46.6 launches per window; the host spends 0.579 ms per window staging and launching them and 0.723 ms waiting for them [S205].

The timing pass ran [S29] = the served form with the timing switches STRATA_DEBUG, STRATA_DECODE_TIMING and without nothing (and the picture reader off).

- **Measured on the daily, 11-10 21:42-21:53:** the confirmation gap's three B starts (B1, B4, B5), each a fresh engine with STRATA_DECODE_TIMING=1 and STRATA_DEBUG=1, running 6 seeded requests at the served sampling (think-s1 1,536 tokens with thinking; code-s1 512; W3-s1 2,048 after a 26.7K prompt; R1-s1 up to 4,096 after 24.2K; R4-s1 / R4-s2 tool calls after 33.4K) = 8 engine runs per start [S206] [S207]. The split pools all 24 runs, window-weighted; none is left out (these starts had no warm-up request). It was read from the three engine logs by a desk script that keeps the 11-05 timing report's parsing (scratch-1111/timing_report.py). There is no GPU stage table: these starts ran without STRATA_VERIFY_PROFILE.
- Reading it: a window is a serial chain per layer. The GPU runs the dense part of a layer (GDN mixer, hyper-connection reads, router) while the CPU pool idles; then the CPU pool computes the layer's missed experts while the GPU mostly waits [S208] (the 11-05 analysis, on the P028x engine before the fetch patch; the structure is the same). In that 11-05 profile the GPU's serial part was 98-99 % busy with 1.5-3 us of launch gaps per layer, so only kernel work shortens it [S209].
- On the daily the GPU-reach wait (9.10 ms) is the largest part and the CPU pool (8.62 ms) second. The 11-05 pass on the engine before the fetch patch, without U, had them the other way round (CPU 9.67, GPU-reach 9.60 of 23.17 ms, 4.91 CPU experts per layer-window against 3.90 here; quoted below), but it ran a different request mix (the 9-workload screen with the GPU profile on), so read that comparison loosely.
- Per engine request (the report's last lines): the window grows with its width and context, think-s1's first pass (137-token prompt, 2.89 tokens per window) 17.39 ms and R1-s1's continuation at 27K (4.88 tokens per window) 27.78 ms, i.e. 6.0 and 5.7 ms per token. The CPU part moves most (5.61 -> 12.76 ms, with 2.36 -> 6.20 CPU experts per layer-window), the GPU-reach wait less (8.28 -> 10.24 ms) [S210].
- Per start: 21.07-22.55 ms per window; the slowest start (B5, GPU-reach 9.70 against 8.81-8.82 ms in the other two) is the one whose live PCIe share settled at 0.45 instead of 0.40 [S211] [S212]: one start, so a hint, not a finding.

- For comparison only: the 11-05 timing pass on the P028x engine before the fetch patch, without U (one 9-workload screen pass with the GPU profile on, which runs ~2 % slow): "11 requests, 5208 windows: 23.17 ms/window = GPU-reach 9.60 + host 10.41 (plan 0.64, CPU 9.67) + draft 2.35 + tail 0.77; T 4.55, 3.64 tok/w" [S213]
- The live PCIe share each confirmation start settled at (B = the daily; P, PX, FP, FX = other builds): "(info) the settled PCIe share per start: B1 0.40, P2 0.40, P3 0.40, B4 0.40, B5 0.45, P6 0.45, FX1 0.45, FP2 0.45, FX3 0.45, FP4 0.45, PX7 0.40, P8 0.40, PX9 0.40" [S212]

## 9. Already tried on this model

One line per idea: status, the measured result, and where it was measured. ADOPTED = in the served config; REJECTED = measured and dropped; PARKED = measured or built, waiting; NOT MEASURED / DESK ONLY = estimate or reading only; INFO = a measured fact. 'The daily' = the build of this pack; 'P028x' = the same v0.2.8 port before the fetch patch, on which most 'vs P028x' lines ran; older lines name their round or release. Many upstream switches since v0.2.9 exist only on the port branches (v0.2.10-v0.2.13), not on the daily's v0.2.8 base; their lines say so. (List: work/qwen4-kit/profile-pack/already-tried-daily-1111.txt.)

### Prompt path (reading the prompt)

| status | idea | measured result | src |
|---|---|---|---|
| **ADOPTED** | STRATA_HC_UPMIX=1 (U: hyper-connection up projection + mix in one kernel; upstream opt-in) | exact on P028x (exact7 7/7, long40 0 of 40 logit files differ); pp16k 3,975.7 vs 3,849.4 tok/s (+3.3 %, noise 0.1 %), pp64k 4,566.7 vs 4,370.4 (+4.5 %, noise 0.5 %); screen and decode no loss; served since 11-09 | [S214-S216] |
| **PARKED** | STRATA_PF_TAIL_SPLIT=1 (T, Basalt prompt-path port) | rounding-level; pp16k +6.1 %, pp64k +2.6 % vs P028x; but it drops the 16,384-token mid-prompt checkpoint, so a prompt that shares 16,500 tokens with a parked one is read again in full (16,527 tokens in 3,950 ms vs 143 in 381 ms); needs the newer port base; 11-10: parked until after Qwen4 day one, then to be judged by its net effect per research-agent run (its faster cold reads against the re-reads of edited prompts that share a long prefix), not per request | [S217-S220] |
| **REJECTED** | STRATA_PF_AHEAD=1 (A, Basalt prompt-path port) | exact; +0.2 % pp16k / +0.6 % pp64k vs P028x, within noise | [S221] |
| **PARKED** | C = A,T,U + checkpoint pool (K, KP) + first-chunk rule at chunk 22,528 | rounding-level; pp16k +15.9 %, pp64k +8.9 % vs P028x, but decode -3.2 / -2.7 / -4.1 % (conv / struct / prose) vs B and the checkpoint pool switches the chat cache off; retry without K; 11-10: parked until after Qwen4 day one | [S222] [S223] [S220] |
| **REJECTED** | K = STRATA_CKPT_POOL, KP (checkpoint pool) | pp16k +1.2 % (noise 1.6 %), pp64k +0.1 %; KP +0.8 / -0.1 %: no gain | [S224] |
| **REJECTED** | GDN prompt paths STRATA_GDN_TC / STRATA_GDN_CONVL2 (upstream v0.2.9-0.2.10 defaults; pinned off) | failed the 40-prompt KL band on the port (stack: KL mean 0.575, p90 1.10, 5 rows above 1; TC alone fails too); stock v0.2.10 fails the same way; a decode-path check later put every prompt path in one scatter, so the question was closed; prompt speed never priced (KL failed first); v0.2.13 turns both on at every Linux CUDA start whatever STRATA_DEFAULTS says, so the v0.2.13 port pins both =0 explicitly | [S225-S229] |
| **ADOPTED** | prompt chunk --prefill auto:16384 (vs 8K chunks) | TTFT 32K -2.9 %, 120K -3.7 % (round 10); decode after the prompt -1.5 / -2.3 % at 32K / 120K (the chunk borrows cache slots) | [S230] |
| **REJECTED** | prompt chunk auto:32768 (the engine picks 22,272 tokens, borrows 4,086 slots) | 33.5K-token prompt -7.6 % TTFT, others within 1 % (round 11); later calibration: decode +0.5 %, TTFT 32K +1.3 %, 120K -1.4 %, so 16K stayed | [S231] [S232] |
| **ADOPTED** | equal-size prompt chunks (upstream #693) | rounding-level; up to -12.4 % TTFT where a prompt's tail is just over 1,024 tokens, never slower | [S233] |
| **ADOPTED** | STRATA_PREFILL_CPU_SHARE 0.4 with STRATA_PREFILL_CPU_SHARE_MAX 1792 | 0.4 cuts prompt time 15-21 % up to ~1,500 tokens and costs from ~2,000 (+6 % at 2,000, +27 % at 3,000), hence the 1,792 cap; on P028x share 0 is pp16k -2.9 %, pp64k -1.0 % | [S234] [S235] |
| **ADOPTED** | STRATA_PF_FUSED=1 (fused int8 prompt experts) | TTFT -3.3 to -3.7 % (round 10); off on P028x: pp16k -6.1 %, pp64k -6.5 % | [S236] [S235] |
| **ADOPTED** | STRATA_PREFILL_V2=1 (v2 prompt-expert kernels from Basalt) + STRATA_DEQUANT_WIDE=1 + draft rule (the 10-22 bundle) | decode +1.6 %; TTFT -4.3 / -8.9 / -6.0 / -6.0 % at 1K / 4K / 32K / 120K; on the v0.2.8 port v2 is bit-identical to the stock path | [S237-S239] |
| **ADOPTED** | STRATA_DEQUANT_WIDE=1 alone | output identical; TTFT -6.7 / -4.4 / -1.5 / -1.5 % at 1K / 4K / 32K / 120K | [S240] |
| **REJECTED** | STRATA_PROMPT_ATTN_IMMA=1 (int8 tensor-core prompt attention; upstream default since 0.2.7, pinned off) | TTFT -2.7 % at 32K / 120K; lowest KL of the variants but changed top-1 picks: 104 of 120 kept vs a floor of 108 | [S241] [S242] |
| **REJECTED** | --ple-inflight 256 (vs 128) | TTFT -0.7 / -0.4 / 0.0 / 0.0 %: no gain | [S243] |
| **REJECTED** | STRATA_PLE_AUTO_RAM / --ple-io ram (per-layer embedding table in RAM) | on paper: 28.8 GB table + 64.7 GB engine = 93.5 of 96.4 GB, above the lock limit; rows stay on the SSD (direct reads) | [S244] |
| **REJECTED** | GDN chunked prefill / FlashQLA-style recurrence (round 8) | the recurrence is only 7.6 % of prompt GPU time; dropped | [S245] |
| **REJECTED** | PF_HC_REGION=1 with PREFILL_V2 (v0.2.10, gap 17) | not exact: exact7 3/7; one quick screen decode +0.34 %, prompt +0.26 % (noise 5.6 / 0.6 %) | [S246] |
| **NOT MEASURED** | STRATA_QSA_FUSE_NR (v0.2.10 default on CUDA: the prompt path's QSA rms-norm + rope in one pass) | claimed same bits, but a rounding fix followed and its parity test was HIP-only; pinned 0 in the v0.2.10-v0.2.13 ports, never priced (the daily's v0.2.8 base predates it) | [S247] [S248] |
| **INFO** | the daily's prompt and decode speed against Basalt's published RTX 5080 row (Basalt PR #90: the 5080 on PCIe 4.0 x16, 9950X3D, 64 GB; Basalt's own prompts and method, cold, 3 passes, 11-10) | prefill 16K 3,963.3 vs 4,876.9 tok/s (-18.7 %), 64K 4,567.3 vs 4,961.0 (-7.9 %); decode blend 206.1 vs 186.8 (+10.3 %) | [S249] [S121] [S128] |

### Decode: speculative drafting

| status | idea | measured result | src |
|---|---|---|---|
| **ADOPTED** | --spec 7 + STRATA_DRAFT_CUM=1 (cumulative draft length) vs --spec 4 | W1-W3 +3.2 % (ahead in 4 of 4 passes), tool-call turns +1.3 %, research call +0.3 % | [S250] |
| **INFO** | draft length A/B (gap 7, W1-W3 engine tok/s) | spec 4: 148.6; spec 7: 151.4 (+1.9 %); spec 7 + DRAFT_CUM: 158.9 (+6.9 %); the same without the cost gate: 160.5 (+8.0 %, one screen) | [S251] |
| **INFO** | why DRAFT_CUM exists | greedy structured text at spec 7: the earlier patch series drafted 3.00 per window vs stock 5.91 and Basalt 5.74 | [S252] |
| **REJECTED** | other draft depths on spec 4 (round 9) | spec 5 / min-p 0.5 +0.2 %; spec 6 / 0.6 -3.4 %; spec 8 + split -3.6 % | [S253] |
| **ADOPTED** | --spec-min-p 0.5 | 0.4 gave +0.5 % on one screen and -3.1 % in the rehearsal; with the cost gate on, min-p no longer sets the window | [S254] |
| **ADOPTED** | STRATA_COST_GATE (cost-aware draft length fitted on this PC) | round 14 on vs off: decode +3.4 %, agent-workload screen +2.8 %; round 19: +4.2 % decode on two cards, -2.0 % after 120K prompts | [S255] [S256] |
| **ADOPTED** | STRATA_SPEC_EXACT=1 (exact speculative sampling) vs upstream STRATA_SPEC_PROB | exact sampling +3.5 % decode, acceptance +8.5 % (round 14); upstream's SPEC_PROB is biased at a T 0.6 near-tie ('=' 59.6-62.2 % vs 52.3 % with speculation off; ours 54.5 %) because --spec-min-p gates on the drawn token's q | [S257-S259] |
| **REJECTED** | upstream SPEC_PROB + STRATA_SPEC_PROB_GATE=top on v0.2.7 | near-tie 51.0 vs 51.9 % (pass) but a second distribution check at p 0.047; decode geomean 0.897 of the then-served build vs 0.925 for upstream paths without it | [S260] |
| **NOT MEASURED** | STRATA_SPEC_COST (upstream's cost-aware draft window) | backlog item, never run | [S261] |
| **ADOPTED** | prompt-lookup drafts --suffix-draft 3 (served default); longer variants rejected | spec 8 with suffix 3 / 8 / 16: decode +0.9 / -0.8 / +0.7 %; the 8x3 variant -0.9 % on the agent-workload screen | [S262] [S263] |
| **REJECTED** | lookup windows up to 12 tokens (v0.2.10 --lookup-max-t) | decode +0.96 % (noise 5.6 %), but outputs depend on the window and the distribution checks fail | [S264] |
| **REJECTED** | Basalt's tuned MTP draft layer on this engine | W1 / W2 / W3 at spec 7: 182.9 / 152.2 / 152.5 vs 175.1 / 153.8 / 152.3 tok/s: a wash | [S265] |
| **NOT MEASURED** | DFlash / DFlash2 drafters | skipped: not exact, slower than MTP upstream (PR closed), CLI-only at the time | [S266] |
| **REJECTED** | tree drafting, drafter adapter, next-layer warming, L3 hot set (round 12) | next-layer warming exact but -6.5 % served (its reads compete for the DRAM the CPU pool needs); tree drafting -10 %; drafter adapter ~0.4 %; L3 hot set 0.9 % | [S267] |

### Decode: where experts are served

| status | idea | measured result | src |
|---|---|---|---|
| **ADOPTED** | helper GPU (RTX 4060 Ti, 3,300-expert static cache) | screen decode 154.8 vs 134.5 tok/s with the helper off (+15.1 %, 0.98 ms per token); fixture blend 199.9 vs 180.2 (+10.9 %); prompts ~1 % faster without it | [S268] [S269] |
| **ADOPTED** | helper slot count 3300 | agent-workload screen: 3300 = 138.9 tok/s; 2400 -3.9 %; 1500 -7.3 %; 3500 +0.8 % (noise); 3475 later +2.2 % decode but slower rounds, so 3300 stayed | [S270-S272] |
| **REJECTED** | helper variants: helper cap, upstream --remote-expert-opt, upstream peer tier | cap -6 to -13 %; --remote-expert-opt -17.9 %; --peer-device 1 -14.7 % decode and TTFT +4-7 % | [S273] |
| **ADOPTED** | --pcie-frac auto (PCIe share of missed experts, no longer forced to 0) | research calls + tool-call turns +3.1 %, W1-W3 +2.6 % (ahead 6 of 6), KL and decode-side checks pass; the engine re-prices the share while serving (0.40-0.45 most of the time) | [S274] [S275] |
| **REJECTED** | STRATA_ROUTE_TAIL_SKIP (upstream's skip of low-ranked missed experts; pinned 0) | lossy; on the 5080 alone it reads 131.0 vs 114.9 tok/s (skip on vs off); with a helper GPU it never acts | [S276] [S277] |
| **REJECTED** | --vram-reserve-mib 512 (vs 713, more cache slots) | 4,694 vs 4,586 slots; decode screen -5.0 %, full screen -1.9 %; main GPU free fell to 269-295 MiB, under the 300 MiB floor | [S278] |
| **ADOPTED** | STRATA_ADAPT_LAG=2 + STRATA_DISJOINT_ADAPT=1 (upstream versions of the owner's helper-aware tier) | outputs identical to the owner's own versions (4 of 4), speed equal (decode -1.1 %, agent-workload screen -0.5 %); a helper-aware tier itself was worth +5.3 % on the agent-workload screen | [S279] [S280] |
| **REJECTED** | adaptive-tier tuning: decay 0.8 / 0.9, more swaps, --adapt-swaps 0 | decay +0.4 / +0.7 % (noise); swaps 48 +1.7 % did not repeat; no adaptation -18 % | [S281-S283] |
| **NOT MEASURED** | STRATA_ADAPT_ASYNC / --adapt-async (asynchronous adaptive tier; pinned 0) | the v0.2.7 repeat gate passed 7 of 7 with it; a desk reading says it would not engage on two cards; speed never run | [S284] [S285] |
| **ADOPTED** | STRATA_ADAPT_FETCH=2 beside the helper cache (upstream v0.2.12 admits PCIe-fetched misses into the main cache but is off with a helper GPU; the owner's patch adds a helper-aware pick list) | gap vs P028x + U, 3 passes each: screen decode +12.7 % (noise 3.4 %), conv / struct / prose +9.9 / +5.6 / +4.9 %, screen prompt +0.18 %; main cache's share of routed entries 62.6 -> 67.3 %, CPU 14.4 -> 9.4 % (screen); unset = P028x bitwise (exact7 7/7, long40 0/40); sampled-distribution test and read-back of 91,345 admitted slots pass; =1 +10.2 % (the frozen rule's proposal), =2 vs =1 +2.3 % (noise 3.4 %); by the rule =2 failed one per-workload prompt check (R4-agent33k -0.1 %, noise 0.1 %) and was adopted as a recorded owner exception; adoption check exact7 7/7, pp16k / pp64k level; served since 11-09 20:06; the desk estimate had been about +3 % | [S13] [S124] [S286] [S287] [S156] [S157] [S288-S290] |
| **REJECTED** | STRATA_ADAPT_FETCH=1 (=2 served instead; =1 admits the PCIe-fetched misses but leaves the adaptive tier's own swaps on in every layer) | gap vs P028x + U: screen decode geomean 170.9 vs 155.1 tok/s (+10.2 %), the frozen rule's proposal; sampled test D2 7.31 vs bound 11.35 (the slot read-back ran on =2 only); =2 then +2.3 % over it (noise 3.4 %) and was served; =1 kept as the ready fallback | [S291] [S287] [S292] |
| **DESK ONLY** | STRATA_ADAPT_FETCH beside upstream's self-deciding asynchronous adaptive tier | code reading (v0.2.12, fetch code unchanged in v0.2.13): a one-GPU serve session can switch itself to the async tier mid-session while fetch admissions stay on, the combination upstream's --adapt-async off-condition exists to prevent; not reproduced; the daily's two-card setup never self-switches (a one-GPU Qwen4 config could) | [S293] |
| **NOT MEASURED** | STRATA_PCIE_START (v0.2.10 default: the PCIe share's start value from the CPU pool's size instead of 0.55) | changes which experts the CPU computes in the first windows (upstream kept the old start on HIP because it flips near-tie tokens there); pinned 'old' in the ports, never priced; on the daily the live share settles at 0.40-0.45 during the first request | [S294] [S295] [S212] |
| **INFO** | STRATA_PCIE_SHARE_MAX=0.60 / STRATA_PCIE_K_RULE=0 (v0.2.11 switches) | identities under STRATA_DEFAULTS=026 (the 0.60 ceiling, the K rule off); pinned for clarity, nothing to price | [S296] |
| **NOT MEASURED** | STRATA_ARENA_RAM_FALLBACK (v0.2.10) and STRATA_ARENA_FILE_CACHE (v0.2.13, #5327): what the expert arena does when RAM is short at start | normal starts unchanged; the fallbacks switch silently to the file source plus a RAM copy of the hottest experts (v0.2.10) or load anyway while evicting the file cache (v0.2.13), which can push MemAvailable under the owner's 12 GiB floor or into swap; pinned 0 (keeps the slower file read); no speed effect on a normal start | [S297-S299] |
| **NOT MEASURED** | STRATA_MTP_KEEP=1 / STRATA_SPILL_OFF=1 (v0.2.10 short-of-VRAM paths: drop the MTP layer at start, loan cache slots, priced spill, the head in host memory) | never fire here (an empty 5080 and an explicit --vram-reserve-mib); pinned so they stay off | [S300] |
| **REJECTED** | alternative expert profiles | learned profile (#477) -4.2 % on the agent-workload screen (helper overloaded); make_profile +1.0 / -0.8 % (noise) | [S301] |
| **NOT MEASURED** | STRATA_ROUTE_PRIOR (routing bias toward cached experts) | lossy by design (changes which experts run); upstream 0.2.7 would turn it on for the 4060 Ti; pinned 0 | [S302] |

### Decode: kernels and the window's host work

| status | idea | measured result | src |
|---|---|---|---|
| **ADOPTED** | STRATA_GR_FORK=1 (fork hyper-connection read) | fork off on 0.2.7 / 0.2.8 costs +3.5-3.9 % step time; vs upstream's multi-token read: -6.1 % on the agent-workload screen, +6.0 % per round | [S303] [S304] |
| **ADOPTED** | the v0.2.8 port with GR_FORK and PREFILL_V2 back (P028x vs the earlier P021m) | screen decode +1.03 %, prompt -0.03 %; fixtures 16K -1.9 %, 64K -1.0 % (accepted); exact7 7/7 | [S305] |
| **ADOPTED** | STRATA_ROUTER_Q8K / STRATA_QSA_SPLIT_ATTN / STRATA_MMVQ_IL / STRATA_SIDE_MIXER=2 (round 14) | +1.4 % / +3.0 % / +2.0 % (agent-workload screen) / +2.5 % (decode) | [S306] [S307] |
| **ADOPTED** | STRATA_MMVQ_IL_ROWS (per-layer table tuned on this PC) | re-derived table +0.2 % decode, -1.8 % ms per round | [S308] |
| **ADOPTED** | STRATA_GR_V3=1; the staged hyper-connection read (HC_SPLIT) rejected | v3 +2.7 % vs the older read; the staged read is bitwise identical and -1.4 % | [S309] [S310] |
| **PARKED** | STRATA_GR_V3_PF=133 (v0.2.10) | identity 7/7, decode +2.06 % (noise 5.6 %) | [S311] |
| **REJECTED** | STRATA_POOL_ONE_BATCH=1 (one CPU-pool batch per layer) | exact; screen decode -0.33 %, prompt +0.23 %; one-card timing 25.61 vs 25.65 ms per window | [S312] [S313] |
| **REJECTED** | STRATA_REMOTE_LATE_LAUNCH=1 (helper launches after the CPU pool starts), alone and with ONE_BATCH | exact; decode -1.03 % alone; both together +0.88 % decode but a 64K-prompt loss; two-card timing 22.15 vs 22.01 ms per window | [S314-S316] |
| **REJECTED** | DF_PDL / IQ_GATHER / GRAPH_PRIO / FUSE_WAIT=2 (gap 18) | exact7 7/7 each; decode +0.15 / +0.80 / -0.06 / -0.87 %, all four +0.20 % (noise 2.6-3.9 %) | [S317] |
| **REJECTED** | DF_PLE (gap 7) | decode -2.2 % and the main GPU's free VRAM fell to 25 MiB | [S318] |
| **DESK ONLY** | GPU-side MoE planning (G4), one-graph draft chain (G6) | bounds ~0.15 ms (0.6 %) and 0.1-0.17 ms per window: not written | [S319] |
| **NOT MEASURED** | PCIe groups beside the VRAM hits (P1), L2 prefetch of the next layer (G5a), helper rows written in place (H2) | P1: 0.98 ms per window of GPU overhang, 0.44 ms of PCIe groups (two-card pass); G5a needs a probe; H2's copy measured 0.108 ms per window, under the 0.15 ms bar | [S320-S322] |
| **REJECTED** | transparent huge pages for the expert arena (#650) | +0.01 %; makes CPU-pool time bimodal run to run | [S323] [S324] |
| **REJECTED** | IQ_GATHER / IQ_PREFETCH / n-gram prefetch | no gain | [S325] [S326] |
| **NOT MEASURED** | STRATA_GR_R2 (v0.2.9 default 2: exact-T 5-8-token kernels for upstream's v3 hyper-connection read) | bit-identical to v3 by upstream's tests; acts only where GR_FORK is off, which the v0.2.13 port does at every shape but Flash-Next's (so a new Qwen4 shape runs upstream's read); pinned 0 to reproduce v0.2.8's dispatch, never priced | [S327] [S328] [S299] |
| **DESK ONLY** | GR_FORK (the fork hyper-connection read) at other model shapes | its tiling and scratch are written for Flash-Next's n_embd 2560 / 4 streams / low rank 320 (a build break at other shapes); decided: compiled out at other shapes on day one, the guard refuses it with a reason and upstream's read runs; generalise once the Qwen4 shape is known, only if its gain warrants | [S329] [S330] [S299] |
| **INFO** | PREFILL_V2 (the v2 prompt-expert kernels) generalised to the compiled geometry on the v0.2.13 port | done as upstream did its own kernels; v2 covers IQ3_XXS gate/up and IQ4_NL down experts only (17 and 39 of 48 layers in this file); the port builds, passes upstream's geometry parity programs (bar upstream's shape-unaware gguf_geometry_test) and loads and answers at three synthetic Qwen4 shapes (q4_mid / q4_big / q4_deep; 4-layer files, random weights) | [S331-S333] |
| **INFO** | STRATA_NO_IQ4XS512=1 + STRATA_DISPATCH_STATS=0 (turn off v0.2.13's IQ4_XS CPU rows in 512-bit lanes and its dispatch counters) on the v0.2.13 port | seeded, at matched work: +0.11 % vs the port (2 v 2, noise 1.25 %): no pin; the 512-bit IQ4_XS rows act on 1 of 48 layers in this file; a UD / IQ4_XS Qwen4 file, or one with Q5_0 experts (STRATA_NO_Q50_512), would send far more CPU experts through these paths, so both are on the Qwen4 day-one list | [S334-S337] |
| **NOT MEASURED** | vpdpwssd in v0.2.13's AVX-512 i-quant CPU rows (6368dc68a: madd + add fused into one instruction; no switch) | used in every CPU expert call that serves 2 or more of a window's tokens, on 47 of 48 layers; the leading code suspect for the port's +0.1-0.3 % per-window cost at matched work (desk fit, unattributed); testing needs a one-line revert build | [S338] [S339] |
| **NOT MEASURED** | STRATA_HC_Q8 (v0.2.13: Q8_0 hyper-connection projections, on by default on CUDA when the GGUF carries them as Q8_0) | stays off here: this IQ3_S file stores all 192 HC projections in BF16; a UD file would turn it on (rounding-level), so pin 0 in any such config until gated | [S340] |
| **NOT MEASURED** | STRATA_HC_REQ8 (Strata's opt-in int8 copy of the hyper-connection matrices for decode; Basalt always reads such a copy) | off in every config: prompt and decode would read different HC values, so not lossless by the owner's rule; Basalt's figures put the BF16 read at about +0.31 ms per token over its int8 copy | [S341] [S342] |
| **NOT MEASURED** | STRATA_SMALL_UNR / STRATA_IL_PAD (v0.2.10 kernel defaults: bf16 router and GDN a/b constant-trip loads; IQ4_XS 5-column interleaved mat-vec run as 6 columns) | bit-identical by upstream's hashes; SMALL_UNR is 0 under 026 anyway, IL_PAD pinned 0 because IQ4_XS (type 23) rows are in our tuned STRATA_MMVQ_IL_ROWS; neither priced | [S343] [S344] |

### Serving, caches, batching

| status | idea | measured result | src |
|---|---|---|---|
| **ADOPTED** | the owner's chat cache (--chat-cache 16, 12 GiB of RAM) | same return times as the alternative (0.36-0.75 s), switching 0.06-0.18 s faster, exact; parking a 54K conversation takes 100-139 ms | [S345] [S346] |
| **REJECTED** | upstream 0.2.3's automatic conversation cache (--conversation-cache-mib 0) | screen prompt -6.8 %, decode -0.2 %; it parks synchronously (40-47 ms on short turns, 126 ms before an agent turn) | [S347] [S348] |
| **REJECTED** | --batch 4 / --batch-mtp (several requests at once) | 4 agent turns at once: 59.8 tok/s one at a time vs 58.4 / 61.1 batched; one request with batch slots allocated -12 % (138 -> 122); the main cache falls from 4,585 to 2,781 slots | [S349] [S350] |
| **REJECTED** | two requests in one verify window (round 12) | pairs finish 20 % later (the slots decode without drafts) | [S351] |
| **ADOPTED** | picture reader on the CPU (not the 4060 Ti) | the GPU reader on the helper costs 1-2 % decode; the CPU reader costs ~2 cache slots | [S352] [S353] |
| **DESK ONLY** | reuse the chat cache's save buffers (the 1,238 MiB save of a 54K conversation runs at two levels, 102-113 or 123-137 ms; theory: the allocator's mmap threshold on the ~28 MB K/V buffers) | not supported: the engine's page faults per start do not follow the save level (two starts 4 faults apart with opposite levels); not built; the cause of the two levels is open | [S354-S356] |
| **INFO** | the chat cache's save (park) on the daily, timed inside the next request's prompt time (11-10 gate, 3 passes) | 3 ms at 132 MiB, 5 ms at 152 MiB, 10 ms at 186 MiB, 49-50 ms at 578 MiB, 53-55 ms at 614 MiB, 106-128 ms at 1,238 MiB (a 54K conversation; two levels); the screen's per-workload prompt numbers include it | [S357] [S358] |
| **INFO** | run-to-run repeatability of seeded requests on the daily's served form (the owner's rule: outputs repeat run to run) | 11-10 morning (STRATA_DEBUG=1, no STRATA_DECODE_TIMING): 8 of 8 seeded requests token-identical over two fresh starts (and on the v0.2.13 port); 11-10 evening, with STRATA_DECODE_TIMING=1: the same build did not repeat (first difference at token 2-163, short anchors included), nor did the fetch-off fallback (both runs STRATA_DEBUG=1); open, desk first (the timing switch, then timing-dependent expert placement: adaptive swaps, the live PCIe share, fetch admissions); exact7 (no adaptation, fixed slots) repeats | [S19] [S20] [S359] [S360] |
| **NOT MEASURED** | STRATA_STREAM_WRITE_TIMEOUT_S=0 / STRATA_BLOCKING_CONSOLE=1 (v0.2.11 server) and STRATA_PENALTY_PROMPT=1 (v0.2.10 sampler) | behaviour pins, not speed: the old stream-write and console behaviour (open), and the penalty window over prompt + answer (only with penalties, which the served sampling does not set) | [S361] [S362] |

### Quantization

| status | idea | measured result | src |
|---|---|---|---|
| **ADOPTED** | IQ3_S GSQ-RCO (ISTA-DASLab, the served GGUF) | vs a Q8_0 reference over 4,995 positions: top-1 87.43 %, KL 0.144 | [S363] |
| **REJECTED** | NVFP4 (GPTQ pack) and FP4-Local | decode ~100 vs 143 tok/s; TTFT at 32K 9.3 vs 7.7 s; top-1 vs Q8_0 91.7 / 91.2 %; task suite level with IQ3_S (94.3 vs 94.5 at medium effort) | [S364] |
| **REJECTED** | Unsloth UD-Q4_K_XL (kept as the KL reference) | best measured fidelity (top-1 92.37 %, KL 0.059; long-text NLL -0.35 nats vs IQ3_S) but decode 68.7 vs 138.8 tok/s (-51 %, round 16) | [S365-S367] |
| **REJECTED** | Unsloth v3.1 UD-IQ3_XXS, and its experts spliced into the IQ3_S file | KL vs UD-Q4_K_XL: served 0.717, UD-IQ3_XXS 0.734, splice 0.889 (worse); decode +1.95 % / +3.01 %, no loss; not adopted | [S368] [S369] |
| **REJECTED** | splice of IQ3_S experts with UD-Q4_K_XL's other tensors | long-text -0.053 nats, only 15 % of the Q4 file's -0.350 | [S370] |
| **REJECTED** | higher-precision side paths (BF16 token embedding, BF16x2 prompt math, RoPE table) | BF16 embedding worse on long texts (+0.08 / +0.10 nats); BF16x2 TTFT 120K +10 %; RoPE table no change; none adopted | [S371] |

### Engines, ports and settings

| status | idea | measured result | src |
|---|---|---|---|
| **REJECTED** | Basalt 0.2.0 (another engine) at its defaults vs P028x | fixture blend +9.5 % (217.2 vs 198.4), 16K prompt +32.3 %, 64K +24.1 %, screen decode +2.8 % (within spread), prompt +15.3 %; not lossless (int8 hyper-connection copy, two-stage head always on) | [S372] |
| **REJECTED** | Basalt made lossless + the helper GPU (estimate) | exact head -3.0 % (156.7 vs 161.5); estimate +13.0 % (+6.2..+17.6 %) over P028x; no local Basalt branch | [S373] [S374] |
| **REJECTED** | Basalt's two-stage Q6_K head | 2.2 % of verify rows have a wrong top-20 where its per-window cap binds; gain +0.7 % (noise) | [S375] |
| **INFO** | Basalt 0.2.0's own lossless flag tries (its engine on the 5080 alone, one pass each against its defaults' 3-pass spread) | --spec 7 / 10 / 6: blend +2.2 / +2.1 / -0.5 % (spread 2.9 %); --kv fp16 -2.6 %; prompt chunks 8K / 32K: 16K -24.8 % / +0.1 %; CPU prompt share 0.4 / 0.8 within 0.2 %; best = its defaults | [S376] |
| **INFO** | value of the patch series over stock Strata (v0.2.1, 10-21) | decode +9.8 %, prompt +8 % | [S377] |
| **REJECTED** | the v0.2.10 port (gap 17) | screen decode -0.87 %; fixtures struct -2.4 %, blend -2.5 %: no gain | [S378] |
| **PARKED** | the v0.2.11 port (base for the Qwen4 port; not served) | exact7 7/7 vs P028x; screen decode +1.34 %, prompt +0.55 %; failed per-workload no-loss on R3 prompt -1.4 % (the chat-cache park inside the timer); passed the 11-09 confirmation gap (R3 with the chat cache off +0.20 %); superseded as the Qwen4 base by the v0.2.13 port (below), which carries its 29 commits | [S379-S382] |
| **PARKED** | the v0.2.13 port (v0.2.13 + the patch series, the ADAPT_FETCH patch included; the Qwen4 day-one base; not served) | BASELINE PASS 11-10 against the daily: exact7 7/7 = P028x bit for bit; screen decode -1.69 % (noise 3.26 %), prompt -0.35 % (noise 1.1 %); Basalt fixtures blend -0.7 %, 16K +0.5 %, 64K -0.4 %; the per-workload flags (R1 -1.7 %, R4 -4.3 %) traced to draft-acceptance sampling; the seeded confirmation at matched work -0.44 % (noise 5.95 %); switch checks: parity / unit tests, 8 of 8 seeded served outputs identical to the daily, sampled test D2 1.33 vs bound 11.35, read-back of 91,375 admitted slots 0 differ | [S383-S388] |
| **INFO** | upstream v0.2.7 paths without the patch series vs the then-served build | decode -7.5 %, prompt -5 % | [S389] |
| **ADOPTED** | STRATA_DEFAULTS=026 (0.2.7's new per-card defaults pinned off: GR_UP_WIDE, MMVQ_IL_89, English draft vocabulary, ...) | the new defaults were never measured one by one | [S390] |
| **ADOPTED** | reasoning effort "medium" by default | task suite: medium 94.5, xhigh 90.7, low 91.4; medium takes about a third of xhigh's time | [S391] |
| **NOT MEASURED** | KV formats other than int8; --kv-resident sizes | no A/B of KV formats on this engine; --kv-resident 16384 was +1.2 % (within spread) in one round | [S392] |
| **INFO** | RAM at 6200 vs 6000 MT/s | 6200 MT/s was unstable (memtest errors); all numbers since 10-10 are at 6000 MT/s (76.6 GB/s); no clean speed pair | [S393] |
| **NOT MEASURED** | Infernix (another engine's ideas: frame pools, prefix cache tiers, BF16-activation arithmetic) | not reviewed; desk check: its per-size frame pools would add no experts here | [S394] [S395] |
| **NOT MEASURED** | Strata's own tuner (strata tune auto) | planned, never run | [S396] |

Totals: ADOPTED 27, DESK ONLY 4, INFO 12, NOT MEASURED 18, PARKED 5, REJECTED 38.

## 10. What these files only approximate (measure on release day)

1. **Decode speed at 16K context** - no decode of >= 256 tokens after a ~16,384-token prompt in the inputs; the pack shows the nearest: R1-verify20k at 24,240, W3-research at 26,729.
2. **Decode speed at 64K context** - no decode of >= 256 tokens after a ~65,536-token prompt in the inputs; the pack shows the nearest: R2-report54k at 54,070.
3. **MTP acceptance per draft position** - no log has STRATA_SPEC_DEPTH=1 lines; only per-request totals exist.
4. **The engine's own swap (VmSwap) per run** - the monitors record system swap only; the owner's swap rule is about the engine's VmSwap.
5. **Short-prompt reading speed on fixed fixtures** - today's short-prompt figures are screen workloads (1.4K-5K-token prompts with chat formatting and tool schemas, one request per pass, the chat cache's save inside the prompt time); add pp1k / pp4k cold fixtures, 3 passes.
6. **Prompt speed at 128K** - nothing above a 66,617-token prompt on the served form; the exactness run's 112K prompt used a pinned smaller cache.
7. **Expert placement on the new model** - on day one only the screen and the fixtures exist (no served traffic); report the screen figure and say so.
8. **Helper GPU memory over time** - only the guard's minimum free (one value per run); the helper's own use is flat by design but not sampled.
9. **Per-position MTP acceptance at the served sampling** - take it on the screen at T 1.0 with thinking on (STRATA_SPEC_DEPTH=1), not on the decode fixtures (T 0.6 / 0.0).
10. **GPU stage table on the served build** - today's split on the daily has no GPU stage table (STRATA_VERIFY_PROFILE off); the last stage table is from 11-05 on the engine before the fetch patch; take one profiled screen pass.
11. **Seeded repeatability in the served form** - seeded requests did not repeat over fresh starts in the 11-10 evening test (with STRATA_DECODE_TIMING=1) and did in the morning one; run the same seeds 3 times on fresh starts, timing switch off.
12. **The 512-bit CPU-row switches on the new file** - STRATA_NO_IQ4XS512=1 and STRATA_NO_Q50_512=1 against the default (release-day list item 24); on this IQ3_S file the IQ4_XS path acts on one layer only.

## Appendix A. Sources

- **S1** `models/ISTA-GSQ-RCO/IQ3_S/Qwen3.8-Flash-Next-GSQ-RCO-IQ3_S-00001-of-00002.gguf` - GGUF header (metadata + tensor table; weights not read)
- **S2** `models/ISTA-GSQ-RCO/IQ3_S/Qwen3.8-Flash-Next-GSQ-RCO-IQ3_S-00002-of-00002.gguf` - GGUF header (metadata + tensor table; weights not read)
- **S3** `notes/pc-hardware.md:8-12,20`
- **S4** `configs/P028x.json:46` - config
- **S5** `engine-r23afetch/SOURCE:1` - engine SOURCE
- **S6** `engine-r23afetch/SHA256:1` - engine SHA256
- **S7** `results/r23/port-0213/gate/englog/B1.englog:38`
- **S8** `results/r23/port-0213/gate/englog/B1.englog:15`
- **S9** `configs/P028x.json:58` - cited in the text
- **S10** `results/r23/ADAPTFETCH-DESK-1109.md:12-14` - cited in the text
- **S11** `results/r23/ADAPTFETCH-DESK-1109.md:37-58` - cited in the text
- **S12** `strata-r22p028x/serve/server.py:7341` - cited in the text
- **S13** `results/r23/adaptfetch/gap/decision.txt:3` - cited in the text; already-tried source
- **S14** `results/r23/ADAPTFETCH-DESK-1109.md:53-57` - cited in the text
- **S15** `results/r23/adaptfetch/gap/decision.txt:14-16` - cited in the text
- **S16** `results/r23/ADAPTFETCH-DESK-1109.md:102-103` - cited in the text
- **S17** `results/r23/afetch-adopt/summary.txt:55` - cited in the text
- **S18** `results/r23/port-0213/gate/decision.txt:31` - cited in the text
- **S19** `results/r23/port-0213/switch-gap/decision.txt:10` - cited in the text; already-tried source
- **S20** `results/r23/port-0213/confirm/decision.txt:4` - cited in the text; already-tried source
- **S21** `results/r23/port-0213/REPRO-PLAN-1111.md:19-34` - cited in the text
- **S22** `configs/P028x.json:2` - cited in the text
- **S23** `configs/P028x.json` - served config
- **S24** `configs/P028x.json:75`
- **S25** `configs/P028x.json:51`
- **S26** `notes/sampling-settings-everywhere.md:11` - cited in the text
- **S27** `results/r23/port-0213/gate/configs/B.json` - B (v0.2.13 gate) config
- **S28** `results/r23/port-0213/switch-gap/configs/B.json` - B (switch gap) config
- **S29** `results/r23/port-0213/confirm/configs/B.json` - B (confirmation gap) config; timing config
- **S30** `results/r23/adaptfetch/gap/configs/F2.json` - F2 (ADAPT_FETCH gap, 11-09) config
- **S31** `results/r23/afetch-adopt/S2.json` - S2 (adoption check, 11-09) config
- **S32** `results/r23/port-0213/gate/speed/B1a.jsonl:2` - prompt speed; speed record
- **S33** `results/r23/port-0213/gate/speed/B2a.jsonl:2` - prompt speed; speed record
- **S34** `results/r23/port-0213/gate/speed/B3a.jsonl:2` - prompt speed; speed record
- **S35** `results/r23/port-0213/gate/speed/B1a.jsonl:1` - prompt speed; speed record
- **S36** `results/r23/port-0213/gate/speed/B2a.jsonl:1` - prompt speed; speed record
- **S37** `results/r23/port-0213/gate/speed/B3a.jsonl:1` - prompt speed; speed record
- **S38** `results/r23/port-0213/gate/speed/B1r.jsonl:3` - prompt speed; speed record
- **S39** `results/r23/port-0213/gate/speed/B2r.jsonl:3` - prompt speed; speed record
- **S40** `results/r23/port-0213/gate/speed/B3r.jsonl:3` - prompt speed; speed record
- **S41** `results/r23/port-0213/gate/bp90/cold-M.jsonl:4,9,14` - prompt speed; decode after the prompt fixture; speed record
- **S42** `results/r23/port-0213/gate/bp90/cold-M.jsonl:5,10,15` - prompt speed; speed record
- **S43** `results/r23/port-0213/gate/speed/B1n.jsonl:1` - decode speed; speed record
- **S44** `results/r23/port-0213/gate/speed/B2n.jsonl:1` - decode speed; speed record
- **S45** `results/r23/port-0213/gate/speed/B3n.jsonl:1` - decode speed; speed record
- **S46** `results/r23/port-0213/gate/speed/B1n.jsonl:2` - decode speed; speed record
- **S47** `results/r23/port-0213/gate/speed/B2n.jsonl:2` - decode speed; speed record
- **S48** `results/r23/port-0213/gate/speed/B3n.jsonl:2` - decode speed; speed record
- **S49** `results/r23/port-0213/gate/bp90/cold-M.jsonl:1,6,11` - decode speed; speed record
- **S50** `results/r23/port-0213/gate/bp90/cold-M.jsonl:3,8,13` - decode speed; speed record
- **S51** `results/r23/port-0213/gate/bp90/cold-M.jsonl:2,7,12` - decode speed; speed record
- **S52** `results/r23/port-0213/gate/speed/B1r.jsonl:1` - decode speed; speed record; cited in the text
- **S53** `results/r23/port-0213/gate/speed/B2r.jsonl:1` - decode speed; speed record
- **S54** `results/r23/port-0213/gate/speed/B3r.jsonl:1` - decode speed; speed record
- **S55** `results/r23/port-0213/gate/speed/B1n.jsonl:3` - decode speed; speed record
- **S56** `results/r23/port-0213/gate/speed/B2n.jsonl:3` - decode speed; speed record
- **S57** `results/r23/port-0213/gate/speed/B3n.jsonl:3` - decode speed; speed record
- **S58** `results/r23/port-0213/gate/speed/B1r.jsonl:2` - decode speed; speed record
- **S59** `results/r23/port-0213/gate/speed/B2r.jsonl:2` - decode speed; speed record
- **S60** `results/r23/port-0213/gate/speed/B3r.jsonl:2` - decode speed; speed record
- **S61** `results/r23/port-0213/gate/speed/B1r.jsonl:4` - speed record
- **S62** `results/r23/port-0213/gate/speed/B2r.jsonl:4` - speed record
- **S63** `results/r23/port-0213/gate/speed/B3r.jsonl:4` - speed record
- **S64** `results/r23/port-0213/switch-gap/speed/B1n.jsonl:1` - speed record
- **S65** `results/r23/port-0213/switch-gap/speed/B1n.jsonl:2` - speed record
- **S66** `results/r23/port-0213/switch-gap/speed/B1a.jsonl:2` - speed record
- **S67** `results/r23/port-0213/switch-gap/speed/B1a.jsonl:1` - speed record
- **S68** `results/r23/port-0213/switch-gap/speed/B1r.jsonl:3` - speed record
- **S69** `results/r23/port-0213/switch-gap/speed/B1r.jsonl:1` - speed record
- **S70** `results/r23/port-0213/switch-gap/speed/B1n.jsonl:3` - speed record
- **S71** `results/r23/port-0213/switch-gap/speed/B1r.jsonl:4` - speed record
- **S72** `results/r23/port-0213/switch-gap/speed/B1r.jsonl:2` - speed record
- **S73** `results/r23/adaptfetch/gap/bp90/F2-decode-1.jsonl:3` - speed record
- **S74** `results/r23/adaptfetch/gap/bp90/F2-decode-2.jsonl:3` - speed record
- **S75** `results/r23/adaptfetch/gap/bp90/F2-decode-3.jsonl:3` - speed record
- **S76** `results/r23/afetch-adopt/bp90/S2-decode-1.jsonl:3` - speed record
- **S77** `results/r23/adaptfetch/gap/bp90/F2-decode-1.jsonl:1` - speed record
- **S78** `results/r23/adaptfetch/gap/bp90/F2-decode-2.jsonl:1` - speed record
- **S79** `results/r23/adaptfetch/gap/bp90/F2-decode-3.jsonl:1` - speed record
- **S80** `results/r23/afetch-adopt/bp90/S2-decode-1.jsonl:1` - speed record
- **S81** `results/r23/adaptfetch/gap/bp90/F2-decode-1.jsonl:2` - speed record
- **S82** `results/r23/adaptfetch/gap/bp90/F2-decode-2.jsonl:2` - speed record
- **S83** `results/r23/adaptfetch/gap/bp90/F2-decode-3.jsonl:2` - speed record
- **S84** `results/r23/afetch-adopt/bp90/S2-decode-1.jsonl:2` - speed record
- **S85** `results/r23/afetch-adopt/bp90/S2-pp16k-1.jsonl:1` - speed record
- **S86** `results/r23/afetch-adopt/bp90/S2-pp64k-1.jsonl:1` - speed record
- **S87** `results/r23/adaptfetch/gap/speed/F21n.jsonl:1` - speed record
- **S88** `results/r23/adaptfetch/gap/speed/F22n.jsonl:1` - speed record
- **S89** `results/r23/adaptfetch/gap/speed/F23n.jsonl:1` - speed record
- **S90** `results/r23/adaptfetch/gap/speed/F21n.jsonl:2` - speed record
- **S91** `results/r23/adaptfetch/gap/speed/F22n.jsonl:2` - speed record
- **S92** `results/r23/adaptfetch/gap/speed/F23n.jsonl:2` - speed record
- **S93** `results/r23/adaptfetch/gap/speed/F21a.jsonl:2` - speed record
- **S94** `results/r23/adaptfetch/gap/speed/F22a.jsonl:2` - speed record
- **S95** `results/r23/adaptfetch/gap/speed/F23a.jsonl:2` - speed record
- **S96** `results/r23/adaptfetch/gap/speed/F21a.jsonl:1` - speed record
- **S97** `results/r23/adaptfetch/gap/speed/F22a.jsonl:1` - speed record
- **S98** `results/r23/adaptfetch/gap/speed/F23a.jsonl:1` - speed record
- **S99** `results/r23/adaptfetch/gap/speed/F21r.jsonl:3` - speed record
- **S100** `results/r23/adaptfetch/gap/speed/F22r.jsonl:3` - speed record
- **S101** `results/r23/adaptfetch/gap/speed/F23r.jsonl:3` - speed record
- **S102** `results/r23/adaptfetch/gap/speed/F21r.jsonl:1` - speed record
- **S103** `results/r23/adaptfetch/gap/speed/F22r.jsonl:1` - speed record
- **S104** `results/r23/adaptfetch/gap/speed/F23r.jsonl:1` - speed record
- **S105** `results/r23/adaptfetch/gap/speed/F21n.jsonl:3` - speed record
- **S106** `results/r23/adaptfetch/gap/speed/F22n.jsonl:3` - speed record
- **S107** `results/r23/adaptfetch/gap/speed/F23n.jsonl:3` - speed record
- **S108** `results/r23/adaptfetch/gap/speed/F21r.jsonl:4` - speed record
- **S109** `results/r23/adaptfetch/gap/speed/F22r.jsonl:4` - speed record
- **S110** `results/r23/adaptfetch/gap/speed/F23r.jsonl:4` - speed record
- **S111** `results/r23/adaptfetch/gap/speed/F21r.jsonl:2` - speed record
- **S112** `results/r23/adaptfetch/gap/speed/F22r.jsonl:2` - speed record
- **S113** `results/r23/adaptfetch/gap/speed/F23r.jsonl:2` - speed record
- **S114** `results/r23/port-0213/gate/speed/B1n.englog:3-10` - cited in the text
- **S115** `results/r23/port-0213/gate/speed/B1r.englog:2-9` - cited in the text
- **S116** `results/r23/port-0213/gate/speed/B1r.englog:16-17` - cited in the text
- **S117** `results/r23/port-0213/gate/speed/B1r.englog:24-25` - cited in the text
- **S118** `results/r23/port-0213/gate/decision.txt:6` - cited in the text
- **S119** `results/r23/port-0213/gate/decision.txt:4` - cited in the text
- **S120** `results/r23/port-0213/gate/decision.txt:8` - cited in the text; Same gate, screen prompt geomean (client clock minus the chat-cache save)
- **S121** `results/r23/port-0213/gate/bp90/report.md:13` - cited in the text; Same gate, the fixtures as Basalt's table reports them: mean (min-max, spread) of 3 cold passes; the blend is Basalt's token-weighted decode; already-tried source
- **S122** `results/r23/port-0213/switch-gap/decision.txt:33` - cited in the text; Switch gap (11-10 morning), one screen pass: B = the daily, P = the v0.2.13 port
- **S123** `results/r23/adaptfetch/gap/decision.txt:13` - cited in the text
- **S124** `results/r23/adaptfetch/gap/decision.txt:4-5` - cited in the text; already-tried source
- **S125** `results/r23/adaptfetch/gap/decision.txt:12-13` - cited in the text
- **S126** `results/r23/adaptfetch/OWNER-EXCEPTION-1109.md:28-35` - cited in the text
- **S127** `results/r23/port-0213/gate/decision.txt:7` - v0.2.13 gate, screen decode geomean of 3 passes (client clock): B = the daily, P = the v0.2.13 port (not served)
- **S128** `results/r23/port-0213/gate/bp90/report.md:31` - Same fixtures against Basalt PR #90's published row (Basalt on an RTX 5080 on PCIe 4.0 x16, 9950X3D, 64 GB); already-tried source
- **S129** `results/r23/port-0213/gate/englog/B1.englog:1-162` - screen B, the daily (v0.2.13 gate, 11-10 18:34-18:51; 3 passes, one warm-up request each) (per-request lines in this range)
- **S130** `results/r23/port-0213/gate/englog/B2.englog:1-160` - screen B, the daily (v0.2.13 gate, 11-10 18:34-18:51; 3 passes, one warm-up request each) (per-request lines in this range)
- **S131** `results/r23/port-0213/gate/englog/B3.englog:1-162` - screen B, the daily (v0.2.13 gate, 11-10 18:34-18:51; 3 passes, one warm-up request each) (per-request lines in this range)
- **S132** `results/r23/port-0213/gate/englog/bpM-decode-1.englog:1-90` - decode fixtures B, the daily (same gate, conv / struct / prose x3) (per-request lines in this range)
- **S133** `results/r23/port-0213/gate/englog/bpM-decode-2.englog:1-91` - decode fixtures B, the daily (same gate, conv / struct / prose x3) (per-request lines in this range)
- **S134** `results/r23/port-0213/gate/englog/bpM-decode-3.englog:1-92` - decode fixtures B, the daily (same gate, conv / struct / prose x3) (per-request lines in this range)
- **S135** `results/r23/port-0213/confirm/englog/B1.englog:1-137` - seeded requests B, the daily (confirmation gap starts B1 / B4 / B5, 11-10 21:42-21:53; STRATA_DECODE_TIMING=1) (per-request lines in this range)
- **S136** `results/r23/port-0213/confirm/englog/B4.englog:1-135` - seeded requests B, the daily (confirmation gap starts B1 / B4 / B5, 11-10 21:42-21:53; STRATA_DECODE_TIMING=1) (per-request lines in this range)
- **S137** `results/r23/port-0213/confirm/englog/B5.englog:1-134` - seeded requests B, the daily (confirmation gap starts B1 / B4 / B5, 11-10 21:42-21:53; STRATA_DECODE_TIMING=1) (per-request lines in this range)
- **S138** `results/r23/port-0213/switch-gap/englog/scrB1.englog:1-160` - screen B, the daily, one pass (switch gap, 11-10 11:41) (per-request lines in this range)
- **S139** `results/r23/adaptfetch/gap/englog/scr-F21.englog:1-161` - screen F2, the daily's form on 11-09 (ADAPT_FETCH gap, 3 passes, one warm-up request each) (per-request lines in this range)
- **S140** `results/r23/adaptfetch/gap/englog/scr-F22.englog:1-159` - screen F2, the daily's form on 11-09 (ADAPT_FETCH gap, 3 passes, one warm-up request each) (per-request lines in this range)
- **S141** `results/r23/adaptfetch/gap/englog/scr-F23.englog:1-160` - screen F2, the daily's form on 11-09 (ADAPT_FETCH gap, 3 passes, one warm-up request each) (per-request lines in this range)
- **S142** `results/r23/adaptfetch/gap/englog/bp-F2-decode-1.englog:1-92` - decode fixtures F2, the daily's form on 11-09 (same gap) (per-request lines in this range)
- **S143** `results/r23/adaptfetch/gap/englog/bp-F2-decode-2.englog:1-92` - decode fixtures F2, the daily's form on 11-09 (same gap) (per-request lines in this range)
- **S144** `results/r23/adaptfetch/gap/englog/bp-F2-decode-3.englog:1-91` - decode fixtures F2, the daily's form on 11-09 (same gap) (per-request lines in this range)
- **S145** `logs/engine-P028x.log:238213-239335` - served log on the daily, 11-09 20:06 - 11-11 08:03 (10 engine starts) (per-request lines in this range)
- **S146** `results/r23/port-0213/gate/englog/B1.englog:29`
- **S147** `results/r23/port-0213/gate/englog/B1.englog:35`
- **S148** `results/r23/port-0213/gate/englog/B1.englog:29,35`
- **S149** `logs/engine-P028x.log:238308,238516-238518,238757,238920-238922` - PCIe share re-pricing lines
- **S150** `results/r23/port-0213/gate/englog/B1.englog:41` - cited in the text
- **S151** `results/r23/port-0213/gate/englog/B1.englog:47` - cited in the text
- **S152** `results/r23/port-0213/gate/englog/B1.englog` - cited in the text; engine start lines of one start of the measured form
- **S153** `results/r23/port-0213/gate/englog/B2.englog` - cited in the text
- **S154** `results/r23/port-0213/gate/englog/B3.englog` - cited in the text
- **S155** `work/qwen4-kit/profile-pack/scratch-1111/report-confirmB.txt:6` - cited in the text
- **S156** `results/r23/adaptfetch/gap/fetchstats.txt:5` - cited in the text; The ADAPT_FETCH gap's own count, screen F2 (the daily's form, 11-09; cross-check of the F2 row); already-tried source
- **S157** `results/r23/adaptfetch/gap/fetchstats.txt:9` - cited in the text; The same gap's screen on the P028x engine before the fetch patch (same args, 11-09; the 'before' of the patch); already-tried source
- **S158** `results/r23/ADAPTFETCH-DESK-1109.md:21-30` - cited in the text
- **S159** `results/r23/ADAPTFETCH-DESK-1109.md:53-55` - cited in the text
- **S160** `results/r23/adaptfetch/gap/fetchstats.txt:8` - The same gap's decode fixtures on the P028x engine before the fetch patch
- **S161** `results/r23/port-0213/gate/englog/B1.englog:52` - cited in the text
- **S162** `work/qwen4-kit/profile-pack/scratch-1111/report-confirmB.txt:1` - Decode-timing pass on the daily (section 8): mean verify-window width T and tokens per window (tok/w); decode timing: window split
- **S163** `bringup/out/logs/server_g1311101804-B1_20261110T183437.log:259` - server guard summary line
- **S164** `bringup/out/logs/server_g1311101804-B2_20261110T184457.log:257` - server guard summary line
- **S165** `bringup/out/logs/server_g1311101804-B3_20261110T184820.log:266` - server guard summary line
- **S166** `bringup/out/logs/server_g1311101804-bpM-decode-1_20261110T185533.log:168` - server guard summary line
- **S167** `bringup/out/logs/server_g1311101804-bpM-decode-2_20261110T190650.log:167` - server guard summary line
- **S168** `bringup/out/logs/server_g1311101804-bpM-decode-3_20261110T191034.log:167` - server guard summary line
- **S169** `bringup/out/logs/server_g1311101804-bpM-pp16k-1_20261110T185713.log:122` - server guard summary line
- **S170** `bringup/out/logs/server_g1311101804-bpM-pp16k-2_20261110T190829.log:121` - server guard summary line
- **S171** `bringup/out/logs/server_g1311101804-bpM-pp16k-3_20261110T191213.log:121` - server guard summary line
- **S172** `bringup/out/logs/server_g1311101804-bpM-pp64k-1_20261110T185810.log:125` - server guard summary line
- **S173** `bringup/out/logs/server_g1311101804-bpM-pp64k-2_20261110T190926.log:125` - server guard summary line
- **S174** `bringup/out/logs/server_g1311101804-bpM-pp64k-3_20261110T191311.log:125` - server guard summary line
- **S175** `bringup/out/logs/server_c1311102142-B1_20261110T214251.log:209` - server guard summary line
- **S176** `bringup/out/logs/server_c1311102142-B4_20261110T214909.log:211` - server guard summary line
- **S177** `bringup/out/logs/server_c1311102142-B5_20261110T215119.log:210` - server guard summary line
- **S178** `bringup/out/logs/monitor-g1311101804-B1.sys.csv:2-202` - 1-s monitor samples
- **S179** `bringup/out/logs/monitor-g1311101804-B2.sys.csv:2-201` - 1-s monitor samples
- **S180** `bringup/out/logs/monitor-g1311101804-B3.sys.csv:2-210` - 1-s monitor samples
- **S181** `bringup/out/logs/monitor-g1311101804-bpM-decode-1.sys.csv:2-97` - 1-s monitor samples
- **S182** `bringup/out/logs/monitor-g1311101804-bpM-decode-2.sys.csv:2-96` - 1-s monitor samples
- **S183** `bringup/out/logs/monitor-g1311101804-bpM-decode-3.sys.csv:2-95` - 1-s monitor samples
- **S184** `bringup/out/logs/monitor-g1311101804-bpM-pp16k-1.sys.csv:2-54` - 1-s monitor samples
- **S185** `bringup/out/logs/monitor-g1311101804-bpM-pp16k-2.sys.csv:2-54` - 1-s monitor samples
- **S186** `bringup/out/logs/monitor-g1311101804-bpM-pp16k-3.sys.csv:2-54` - 1-s monitor samples
- **S187** `bringup/out/logs/monitor-g1311101804-bpM-pp64k-1.sys.csv:2-64` - 1-s monitor samples
- **S188** `bringup/out/logs/monitor-g1311101804-bpM-pp64k-2.sys.csv:2-64` - 1-s monitor samples
- **S189** `bringup/out/logs/monitor-g1311101804-bpM-pp64k-3.sys.csv:2-64` - 1-s monitor samples
- **S190** `bringup/out/logs/monitor-c1311102142-B1.sys.csv:2-125` - 1-s monitor samples
- **S191** `bringup/out/logs/monitor-c1311102142-B4.sys.csv:2-126` - 1-s monitor samples
- **S192** `bringup/out/logs/monitor-c1311102142-B5.sys.csv:2-127` - 1-s monitor samples
- **S193** `results/r23/port-0213/gate/summary.txt:21` - RAM available with no engine loaded (the v0.2.13 gate's open, 11-10 18:05)
- **S194** `results/r23/port-0213/gate/summary.txt:462` - Restart of the served engine after the gate (11-10 19:19)
- **S195** `results/r23/port-0213/switch-gap/summary.txt:257` - Restart of the served engine after the switch gap (11-10 11:47)
- **S196** `results/r23/port-0213/confirm/summary.txt:234` - Restart of the served engine after the confirmation gap (11-10 22:09)
- **S197** `logs/engine-P028x.log:238276,238391,238484,238652,238743,238894,239039,239132,239223,239314` - low-VRAM warnings
- **S198** `bringup/lib/guard.py:7-8` - cited in the text
- **S199** `notes/memavailable-floor.md:8` - cited in the text
- **S200** `bringup/out/logs/monitor-c1311102142-B1.sys.csv:11-13` - cited in the text
- **S201** `notes/kernel-oops-pinned-memory.md:51` - cited in the text
- **S202** `notes/memavailable-floor.md:29-30` - cited in the text
- **S203** `results/r23/ADAPTFETCH-DESK-1109.md:58` - cited in the text
- **S204** `work/qwen4-kit/profile-pack/scratch-1111/report-confirmB.txt:2`
- **S205** `work/qwen4-kit/profile-pack/scratch-1111/report-confirmB.txt:3`
- **S206** `results/r23/port-0213/confirm/decision.txt:1` - cited in the text
- **S207** `results/r23/port-0213/confirm/summary.txt:8` - cited in the text
- **S208** `results/r23/decode-timing/ANALYSIS.md:11-14` - cited in the text
- **S209** `results/r23/decode-timing/ANALYSIS.md:15-17` - cited in the text
- **S210** `work/qwen4-kit/profile-pack/scratch-1111/report-confirmB.txt:12-19` - cited in the text
- **S211** `work/qwen4-kit/profile-pack/scratch-1111/report-confirmB.txt:7-10` - cited in the text
- **S212** `results/r23/port-0213/confirm/decision.txt:33` - cited in the text; The live PCIe share each confirmation start settled at (B = the daily; P, PX, FP, FX = other builds); already-tried source
- **S213** `results/r23/decode-timing/t2/report-T2dv.txt:1` - For comparison only: the 11-05 timing pass on the P028x engine before the fetch patch, without U (one 9-workload screen pass with the GPU profile on, which runs ~2 % slow)
- **S214** `results/r23/basalt-prompt/gap-speed/decision.txt:4` - already-tried source
- **S215** `results/r23/basalt-prompt/gap-speed/decision.txt:9` - already-tried source
- **S216** `results/r23/u-adopt/result.txt:1` - already-tried source
- **S217** `results/r23/basalt-prompt/gap-speed/decision.txt:6` - already-tried source
- **S218** `results/r23/basalt-prompt/gap-speed/decision.txt:11` - already-tried source
- **S219** `results/BACKLOG-1027.md:239-241` - already-tried source
- **S220** `results/BACKLOG-1027.md:316` - already-tried source
- **S221** `results/r23/basalt-prompt/gap-speed/decision.txt:5` - already-tried source
- **S222** `results/r23/basalt-prompt/gap-speed/decision.txt:8` - already-tried source
- **S223** `results/BACKLOG-1027.md:220-228` - already-tried source
- **S224** `results/r23/basalt-prompt/gap-b/decision-b.txt:5-6` - already-tried source
- **S225** `results/r22/gap17/decision.txt:16-21` - already-tried source
- **S226** `results/r22/gap19/decision.txt:11-13` - already-tried source
- **S227** `results/r23/decpath/decision.txt:18-24` - already-tried source
- **S228** `results/r23/decpath/decision.txt:70` - already-tried source
- **S229** `results/r23/port-0213/NOTES-0213.md:91-96` - already-tried source
- **S230** `NOTES.md:3014-3016` - already-tried source
- **S231** `NOTES.md:4177-4178` - already-tried source
- **S232** `NOTES.md:5285` - already-tried source
- **S233** `NOTES.md:4190-4191` - already-tried source
- **S234** `notes/strata-sampler-share-findings.md:22-24` - already-tried source
- **S235** `results/r23/decpath/decision.txt:68-69` - already-tried source
- **S236** `NOTES.md:3019-3025` - already-tried source
- **S237** `results/r22/gap8/dec-K.md:3` - already-tried source
- **S238** `results/r22/gap8/ttft-K.md:3-6` - already-tried source
- **S239** `results/r22/gap16/gates.txt:10-12` - already-tried source
- **S240** `results/r22/gap7/ttft-flags.md:3-6` - already-tried source
- **S241** `results/r22/gap7/ttft-flags.md:9-12` - already-tried source
- **S242** `results/r22/gap9/imma.txt:10` - already-tried source
- **S243** `results/r22/gap7/ttft-flags.md:15-18` - already-tried source
- **S244** `results/PORT-V027-PLAN.md:30-35` - already-tried source
- **S245** `NOTES.md:1606-1618` - already-tried source
- **S246** `results/r22/gap17/decision.txt:54-56` - already-tried source
- **S247** `results/r22/port-0210-review.md:264` - already-tried source
- **S248** `results/r22/port-0210-review.md:352` - already-tried source
- **S249** `results/r23/port-0213/gate/bp90/report.md:5` - already-tried source
- **S250** `results/r22/gap8/cvsa-verdict.txt:7` - already-tried source
- **S251** `NOTES.md:8072` - already-tried source
- **S252** `../basalt-ab/PLAN.md:134-135` - already-tried source
- **S253** `NOTES.md:2388-2392` - already-tried source
- **S254** `NOTES.md:5286` - already-tried source
- **S255** `NOTES.md:5248-5251` - already-tried source
- **S256** `notes/strata-sampler-share-findings.md:25` - already-tried source
- **S257** `NOTES.md:5211` - already-tried source
- **S258** `notes/strata-sampler-share-findings.md:13-16` - already-tried source
- **S259** `notes/strata-sampler-share-findings.md:35` - already-tried source
- **S260** `results/r22/port-027.md:100-110` - already-tried source
- **S261** `results/BACKLOG-1027.md:77` - already-tried source
- **S262** `NOTES.md:3230-3234` - already-tried source
- **S263** `NOTES.md:3299-3301` - already-tried source
- **S264** `results/r22/gap17/decision.txt:42-51` - already-tried source
- **S265** `../basalt-ab/PLAN.md:109-111` - already-tried source
- **S266** `notes/basalt-ab-results.md:30` - already-tried source
- **S267** `results/round12-summary.md:9-12` - already-tried source
- **S268** `../basalt-020/results/followup-decision.md:9-10` - already-tried source
- **S269** `../basalt-020/results/followup-decision.md:17` - already-tried source
- **S270** `NOTES.md:4107-4114` - already-tried source
- **S271** `NOTES.md:4158` - already-tried source
- **S272** `NOTES.md:5282` - already-tried source
- **S273** `NOTES.md:4158-4160` - already-tried source
- **S274** `notes/pcie-frac-later-test.md:16-20` - already-tried source
- **S275** `results/r22/gap9/pcie-speed.txt:3` - already-tried source
- **S276** `NOTES.md:6135` - already-tried source
- **S277** `notes/tail-skip-off-single-gpu.md:14-20` - already-tried source
- **S278** `NOTES.md:7761-7768` - already-tried source
- **S279** `NOTES.md:5208` - already-tried source
- **S280** `NOTES.md:5229-5230` - already-tried source
- **S281** `NOTES.md:3185-3187` - already-tried source
- **S282** `NOTES.md:98` - already-tried source
- **S283** `NOTES.md:5746` - already-tried source
- **S284** `results/r22/port-027.md:96` - already-tried source
- **S285** `results/r22/switch-diag/decode-loss.md:150` - already-tried source
- **S286** `results/r23/adaptfetch/gap/decision.txt:12-18` - already-tried source
- **S287** `results/r23/adaptfetch/gap/decision.txt:25` - already-tried source
- **S288** `results/r23/adaptfetch/OWNER-EXCEPTION-1109.md:26-35` - already-tried source
- **S289** `results/r23/afetch-adopt/result.txt:1` - already-tried source
- **S290** `results/r23/ADAPTFETCH-DESK-1109.md:88-93` - already-tried source
- **S291** `results/r23/adaptfetch/gap/decision.txt:4-8` - already-tried source
- **S292** `results/BACKLOG-1027.md:306` - already-tried source
- **S293** `results/r23/ISSUE-DRAFT-adaptfetch-async-1109.md:3-36` - already-tried source
- **S294** `results/r22/port-0210-review.md:267` - already-tried source
- **S295** `results/r23/port-0213/gate/decision.txt:37-42` - already-tried source
- **S296** `results/r23/port-0211/PORT.md:52-55` - already-tried source
- **S297** `results/r22/port-0210-review.md:268` - already-tried source
- **S298** `results/r23/port-0213/NOTES-0213.md:120-129` - already-tried source
- **S299** `results/r23/port-0213/NOTES-0213.md:133-136` - already-tried source
- **S300** `results/r22/port-0210-review.md:270-271` - already-tried source
- **S301** `NOTES.md:3172-3176` - already-tried source
- **S302** `results/PORT-V027-PLAN.md:28` - already-tried source
- **S303** `results/r22/switch-diag/decode-loss.md:16-21` - already-tried source
- **S304** `NOTES.md:5231` - already-tried source
- **S305** `results/r22/gap16/decision.txt:2-11` - already-tried source
- **S306** `NOTES.md:5209` - already-tried source
- **S307** `NOTES.md:5212-5214` - already-tried source
- **S308** `NOTES.md:5296-5298` - already-tried source
- **S309** `NOTES.md:2275` - already-tried source
- **S310** `NOTES.md:2303-2308` - already-tried source
- **S311** `results/r22/gap17/decision.txt:52-56` - already-tried source
- **S312** `results/r23/decode-timing/screen-rerun/decision-b-final.txt:13-15` - already-tried source
- **S313** `results/r23/decode-timing/gap-a/decision.txt:16-17` - already-tried source
- **S314** `results/r23/decode-timing/screen-rerun/decision-b-final.txt:10-12` - already-tried source
- **S315** `results/r23/decode-timing/screen-rerun/decision-b-final.txt:16-28` - already-tried source
- **S316** `results/r23/decode-timing/gap-a/decision.txt:14-15` - already-tried source
- **S317** `results/r22/gap18/decision.txt:2-7` - already-tried source
- **S318** `results/r22/gap7/dec-PL.md:3` - already-tried source
- **S319** `results/r23/decode-timing/ANALYSIS.md:22-24` - already-tried source
- **S320** `results/r23/decode-timing/t2/report-T2dv.txt:4-5` - already-tried source
- **S321** `results/r23/decode-timing/ANALYSIS.md:160` - already-tried source
- **S322** `results/r23/decode-timing/gap-a/timing/report-Bt.txt:4` - already-tried source
- **S323** `NOTES.md:3963` - already-tried source
- **S324** `NOTES.md:6100` - already-tried source
- **S325** `NOTES.md:3961-3962` - already-tried source
- **S326** `NOTES.md:5215` - already-tried source
- **S327** `results/r22/port-0210-review.md:193-194` - already-tried source
- **S328** `results/r22/port-0210-review.md:263` - already-tried source
- **S329** `results/r23/port-0213/NOTES-0213.md:48-53` - already-tried source
- **S330** `results/r23/port-0213/NOTES-0213.md:70-77` - already-tried source
- **S331** `results/r23/port-0213/NOTES-0213.md:63-69` - already-tried source
- **S332** `results/r23/port-0213/NOTES-0213.md:306-325` - already-tried source
- **S333** `results/r23/port-0213/gate/englog/B1.englog:27` - already-tried source
- **S334** `results/r23/port-0213/confirm/decision.txt:5` - already-tried source
- **S335** `results/r23/port-0213/HUNT-1110.txt:156-163` - already-tried source
- **S336** `results/r23/port-0213/HUNT-1110.txt:244-251` - already-tried source
- **S337** `results/qwen4-kit/dayone-dryrun/RELEASE-DAY-ONLY.md:158-164` - already-tried source
- **S338** `results/r23/port-0213/HUNT-1110.txt:148-155` - already-tried source
- **S339** `results/r23/port-0213/HUNT-1110.txt:118-133` - already-tried source
- **S340** `results/r23/port-0213/NOTES-0213.md:97-102` - already-tried source
- **S341** `../basalt-020/REPORT.md:66-72` - already-tried source
- **S342** `../basalt-020/results/followup-decision.md:15` - already-tried source
- **S343** `results/r22/port-0210-review.md:262` - already-tried source
- **S344** `results/r22/port-0210-review.md:265` - already-tried source
- **S345** `NOTES.md:1444` - already-tried source
- **S346** `results/r23/port-0211/PORT.md:202-215` - already-tried source
- **S347** `results/r22/gap16/decision.txt:2-3` - already-tried source
- **S348** `results/r22/switch-diag/decode-loss.md:157-161` - already-tried source
- **S349** `NOTES.md:8047-8054` - already-tried source
- **S350** `results/r22/conc/tables.md:5-14` - already-tried source
- **S351** `results/round12-summary.md:13` - already-tried source
- **S352** `../basalt-ab/PLAN.md:120-121` - already-tried source
- **S353** `HANDOFF.md:127-131` - already-tried source
- **S354** `results/r23/port-0211/PORT.md:308-317` - already-tried source
- **S355** `results/r23/port-0211/HUNT-1107.md:55-56` - already-tried source
- **S356** `NOTES.md:9697` - already-tried source
- **S357** `results/r23/port-0213/gate/decision.txt:10-18` - already-tried source
- **S358** `NOTES.md:9695` - already-tried source
- **S359** `results/r23/port-0213/REPRO-PLAN-1111.md:5-17` - already-tried source
- **S360** `results/r23/port-0213/REPRO-PLAN-1111.md:27-34` - already-tried source
- **S361** `results/r23/port-0211/PORT.md:101-106` - already-tried source
- **S362** `results/r22/port-0210-review.md:272` - already-tried source
- **S363** `results/r21/yq/compare2.md:32` - already-tried source
- **S364** `notes/strata-v0144-nvfp4-pack.md:21-27` - already-tried source
- **S365** `results/r21/yq/compare2.md:26` - already-tried source
- **S366** `NOTES.md:4562-4564` - already-tried source
- **S367** `NOTES.md:6031-6034` - already-tried source
- **S368** `results/r23/ud31/decision.txt:24-25` - already-tried source
- **S369** `results/r23/ud31/decision.txt:45-46` - already-tried source
- **S370** `NOTES.md:4605-4608` - already-tried source
- **S371** `NOTES.md:4232-4235` - already-tried source
- **S372** `../basalt-020/REPORT.md:20-23` - already-tried source
- **S373** `../basalt-020/results/followup-decision.md:14` - already-tried source
- **S374** `../basalt-020/results/followup-decision.md:18` - already-tried source
- **S375** `../basalt-ab/PLAN.md:113-116` - already-tried source
- **S376** `../basalt-020/REPORT.md:31-44` - already-tried source
- **S377** `notes/basalt-ab-results.md:22-23` - already-tried source
- **S378** `results/r22/gap17/decision.txt:1-10` - already-tried source
- **S379** `results/r23/port-0211/gap/decision.txt:1-4` - already-tried source
- **S380** `results/r23/port-0211/confirm/decision.txt:3` - already-tried source
- **S381** `results/r23/port-0211/confirm/decision.txt:38` - already-tried source
- **S382** `results/r23/port-0213/NOTES-0213.md:160-162` - already-tried source
- **S383** `results/r23/port-0213/gate/decision.txt:3-10` - already-tried source
- **S384** `results/r23/port-0213/gate/decision.txt:19-24` - already-tried source
- **S385** `results/r23/port-0213/gate/BASELINE-VERDICT-1110.txt:6-16` - already-tried source
- **S386** `results/r23/port-0213/HUNT-1110.txt:16-28` - already-tried source
- **S387** `results/r23/port-0213/switch-gap/decision.txt:1-19` - already-tried source
- **S388** `results/r23/port-0213/confirm/decision.txt:3` - already-tried source
- **S389** `results/r22/port-027.md:100-112` - already-tried source
- **S390** `results/PORT-V027-PLAN.md:22-28` - already-tried source
- **S391** `notes/reasoning-effort-local.md:15-19` - already-tried source
- **S392** `NOTES.md:5284` - already-tried source
- **S393** `notes/kernel-oops-pinned-memory.md:11-15` - already-tried source
- **S394** `results/BACKLOG-1027.md:127-152` - already-tried source
- **S395** `NOTES.md:9605` - already-tried source
- **S396** `HANDOFF.md:97-108` - already-tried source

## Appendix B. How this pack was made

- Generator `profile_pack.py` 1.1 (2026-11-11); inputs `work/qwen4-kit/profile-pack/inputs-daily-1111.json`; GGUF header read with the tree's tools/gguf_reader.py.
- Read-only: configs, engine SOURCE / SHA256, GGUF headers, JSONL speed records, engine logs, server guard lines, 1-second monitor CSVs, the decode-timing report, the project's notes. Nothing on the GPU.
- Privacy scrub before writing: no username, home path, hostname, IP other than 127.0.0.1, UUID, email, API key or token, or the owner's other tools; the generator refuses to write otherwise.

