# Profile pack: Qwen3.8-Flash-Next (IQ3_S GSQ-RCO) on a patched Strata build, one desktop PC - generator test run

Generated 2026-11-10 by `profile_pack.py` 1 (2026-11-09) from measurement files that already existed (nothing was run for this pack). Every number carries a source tag `[S<n>]`; Appendix A resolves each tag to a file and line (paths are relative to the project repository; `notes/` = the project's notes folder, `../` = a sibling project folder).

**What this is.** How a 512-expert MoE model runs on one desktop PC with 24 GB of VRAM over two GPUs and 96 GB of RAM: Qwen3.8-Flash-Next (published as a preview of the Qwen4 architecture) as the ISTA-DASLab GSQ-RCO IQ3_S GGUF, on the Strata engine (upstream v0.2.8) plus the owner's patch series (build label **P028x**), since 2026-11-09 20:06 on the **fetch build**, which adds upstream's STRATA_ADAPT_FETCH and runs it beside the helper GPU; served locally on 127.0.0.1. All routed experts sit in pinned RAM (46.8 GiB); the main GPU caches 18.7 % of them and a helper GPU another 13.4 %. Because routing is skewed, and because the fetch build keeps often-routed experts that it had to read over PCIe in the main GPU's cache, those caches serve about 85 % of the routed expert work during decode on the 11-09 screen (80 % on the same screen before the fetch patch; section 5). Everything is lossless by the owner's rule: no switch that changes outputs beyond rounding is served. **Older measurements:** where the current build was not measured, the pack keeps figures from the P028x engine before the fetch patch (2026-11-09 or earlier) and says so where they appear: the per-window time split of section 8 (measured 11-05; it is also the source of the 'decode window' row in the table below, so that row describes the P028x engine before the fetch patch), the ten-day served-log figures, the 3-pass pp16k / pp64k fixtures (the current build has one pass of each) and the reference sets P, P-screen and PU. This file is the test run of a generator that will write the same pack for Qwen4 on its release day; section 10 lists what today's files only approximate.

## At a glance

|  |  | src |
|---|---|---|
| model | Qwen3.8-Flash-Next GSQ-RCO: 48 layers (36 linear-attention + 12 full-attention), 512 routed experts (10 per token) + a shared expert; 176.9 B parameters stored (120.8 B routed experts, 51.2 B per-layer embedding table), about 6.7 B active per token; routed experts at 3.33 bits/weight (46.84 GiB) | [S1] |
| prompt speed, tok/s (median of passes) | short: B-write 1,666.5; short: A-edit 2,715.5; short: R3-extract5k 3,667.5; 16K: pp16k 3,975.6; 64K: pp64k 4,564.8 | [S27-S37] |
| decode speed, tok/s (median of passes) | short context: W1-think 178.5; short context: W2-code 174.3; short context: conv 156.2; short context: prose 142.8; short context: struct 237.4; near 16K (approx.): R1-verify20k 168.4; near 16K (approx.): W3-research 181.8; near 64K (approx.): R2-report54k 158.6 | [S38-S64] |
| routed experts served from (decode) | main GPU cache 67.3 %, helper GPU cache 17.3 %, PCIe 6.0 %, CPU 9.4 % (screen F2, current build (ADAPT_FETCH gap, 3 passes, one warm-up request each), 36 requests) | [S123-S125] |
| MTP drafting | 73.1 % of MTP drafts accepted, 3.66 tokens per verify window (screen F2, current build (ADAPT_FETCH gap, 3 passes, one warm-up request each)); per-position acceptance: not logged (section 6) | [S123-S125] |
| memory over 9 measured runs (guard lines) | MemAvailable never below 33.1 GiB; main GPU free VRAM never below 439 MiB; server + engine RSS up to 54.3 GiB; system swap in use (pages swapped before the runs) up to 4.3 GiB; helper GPU free VRAM never below 1287 MiB | [S159-S167] |
| swap | 0 MiB of swap growth inside 9 measured runs (1-s samples) | [S168-S176] |
| decode window (verify step) | 23.17 ms for 3.64 tokens; slowest part: CPU pool (missed experts) inside the host's per-layer work 9.67 ms (42 %); the GPU-reach wait 9.60 ms is close behind | [S157] |

Approximations (see section 10): 11 measurements here stand in for ones release day takes directly.

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
| build label | P028x on the fetch build = upstream Strata v0.2.8 + the owner's patch series (P028x, served since 2026-10-30; STRATA_HC_UPMIX=1 since 2026-11-09 11:39) + upstream's STRATA_ADAPT_FETCH commit and the owner's patch that runs it beside the helper GPU, served since 2026-11-09 20:06 with STRATA_ADAPT_FETCH=2. What the fetch patch does: when the main GPU has to read a missed expert from RAM over PCIe and that expert is routed clearly more often than the least-used expert in that layer of the main GPU's cache, the engine keeps the copy in that cache slot instead of dropping it after the window. |
| engine source | v0.2.8 + 31 commits (branch r23-adaptfetch f381bfdf55098dba601fab70e0d6c756a1da586f), tree 2260660993d533e03e71353191197d1697531082 [S5] |
| engine binary sha256 | `153ce47d3ef03e5c189dc8725d6f9165eecbb8868f3c088c2eada8460d739706` [S6] (re-hashed for this pack: matches) |
| engine's self-reported version | 0.1.54 [S7] |
| main GPU (engine log) | NVIDIA GeForce RTX 5080, compute capability 12.0 [S8] |

- The patch series carries, among others: exact speculative sampling (STRATA_SPEC_EXACT), the cost-aware draft gate and cumulative draft length, the fork hyper-connection read (STRATA_GR_FORK), Basalt-derived v2 prompt-expert kernels made bit-identical to the stock path (STRATA_PREFILL_V2), the router's Q8_K doorbell rows (STRATA_ROUTER_Q8K), a chat cache that parks conversations in RAM, and upstream 0.2.7's new defaults pinned off [S9].
- The fetch build (`v0.2.8 + 31` in SOURCE) is P028x's 28 commits plus three: upstream's STRATA_ADAPT_FETCH commit (24c6c2f68, from v0.2.12, which turns the switch off when a helper GPU is present); the owner's patch f381bfdf5 that runs it beside the helper (the PCIe share's pick list leaves out experts the helper holds, admissions go to the main GPU's cache only, per-request admission counters and an optional read-back check in serve mode) [S10] [S11]; and one commit to the Python server only (an HTTP 400 for a request that names a model which is not loaded), not in the engine binary [S12].
- With the switch unset the fetch build is bitwise P028x: exact7 7/7 at matched slots, 0 of 40 long-prompt first-token logit files differ [S13]. With =2 the GPU computes a different set of experts than P028x would, which changes outputs at rounding level [S14]; a served-mode sampled-distribution test (D2 1.83 against a noise bound of 11.35) and a read-back of the 91,345 slots admitted in a check run (0 differ) passed [S15]. exact7 runs without adaptation, where the switch does not act [S16]; it gave 7/7 with =2 set as well [S17].
- The engine reports `engine 0.1.54` as its session version even though the tree is v0.2.8 + 31; the SOURCE file names the branch commit.
- The served config file keeps the name P028x.json, and its own comment line still describes the build before the fetch patch [S9]; its `exe` names the fetch build [S18].

**Engine arguments** (the served config [S19]; paths replaced by what they hold):

| argument | value | what it does | line in [S19] |
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

**Environment switches** (29 keys) [S19]:

| switch | value | what it does / why | line in [S19] |
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

`STRATA_MMVQ_IL_ROWS` in full: `23:2:0,1,2,1,1;23:3:0,4,4,4,4;23:4:0,2,2,4,4;12:2:0,1,1,1,1;12:3:0,0,0,2,2;12:4:0,2,2,1,1;13:2:0,1,1,1,1;13:3:0,1,2,2,1;13:4:0,1,2,2,2;14:2:0,0,0,1,4;14:3:0,2,2,4,4;14:4:0,2,2,1,2` [S20]

**Sampling (served):** temperature 1.0, top_p 0.95, top_k 20, min_p 0.05 [S21]. Every client path and every measurement arm uses these, except the decode fixtures' own temperatures (section 4). The GGUF header suggests the same temperature / top-p / top-k [S22]

**Measured form.** The speed and memory runs used the served config without the picture reader (`--vision` and its CPU process off); args, env and engine are otherwise identical (F2 and S2 below). The reference sets P, P-screen and PU ran the same args on the P028x engine before the fetch patch (engine sha f4c4f654fb24, the build served until 11-09 20:06) without STRATA_ADAPT_FETCH [S23].

- F2 (gap arm) (the ADAPT_FETCH gap's arm for the current build: the served config minus the picture reader) vs the served config [S24]: args only in the served config: ['--vision']; args only in F2 (gap arm): none; env differences (served, F2 (gap arm)): none.
- S2 (adoption check) (the adoption check's config: the same) vs the served config [S25]: args only in the served config: ['--vision']; args only in S2 (adoption check): none; env differences (served, S2 (adoption check)): none.
- P (gap reference) (the gap's reference arm: the same args on the P028x engine before the fetch patch (engine-r22p028x); this list compares args and env only, not the engine) vs the served config [S26]: args only in the served config: ['--vision']; args only in P (gap reference): none; env differences (served, P (gap reference)): STRATA_ADAPT_FETCH '2' vs None.

## 4. Speeds

Engine clock (the engine's own prompt and decode timers), cold prompts (nothing reused). **Fixtures** start a fresh engine for each test: pp16k = a 16,676-token prompt + up to 32 tokens; pp64k = a 66,617-token prompt + 1 token; decode = three short-prompt texts (conv 38 tokens at T 0.6 up to 1,200 tokens; struct 98 tokens at T 0.0 up to 8,192; prose 19 tokens at T 0.6 up to 1,200). **Screen** = 9 workloads in 3 groups, each pass on one fresh engine after one warm-up request, at the served sampling with thinking on: W1-think / W2-code / W3-research (short and long prompts, fixed 3,072 / 3,072 / 2,048 tokens), A-edit / B-write (agent tool-call turns), R1-verify20k / R2-report54k / R3-extract5k / R4-agent33k (research-style long prompts). 'Short prompt' = the screen's cold 1.4K-5K-token prompts; 'short-context decode' = W1 / W2 (110-125-token prompts) and the decode fixtures. Set **F2** joins two runs of the same config: the ADAPT_FETCH gap's three decode passes and the adoption check's single pp16k / pp64k / decode pass.

**Headline speeds** (median over passes [min-max]; tok/s, engine clock):

| what | workload | tok/s | passes | set | src |
|---|---|---|---|---|---|
| prompt, short | B-write (1,369 tokens) | 1,666.5 [1,663.8-1,674.2] | 3 | F2-screen | [S27-S29] |
| prompt, short | A-edit (2,676 tokens) | 2,715.5 [2,713.7-2,721.3] | 3 | F2-screen | [S30-S32] |
| prompt, short | R3-extract5k (5,012 tokens) | 3,667.5 [3,656.7-3,735.7] | 3 | F2-screen | [S33-S35] |
| prompt, 16K | pp16k (16,676 tokens) | 3,975.6 [3,975.6-3,975.6] | 1 | F2 | [S36] |
| prompt, 64K | pp64k (66,617 tokens) | 4,564.8 [4,564.8-4,564.8] | 1 | F2 | [S37] |
| decode, short context | W1-think (prompt 111, 3,072 tokens, T 1.0) | 178.5 [173.6-199.1] | 3 | F2-screen | [S38-S40] |
| decode, short context | W2-code (prompt 125, 3,072 tokens, T 1.0) | 174.3 [172.3-174.8] | 3 | F2-screen | [S41-S43] |
| decode, short context | conv (prompt 38, 1,094 tokens, T 0.6) | 156.2 [154.6-171.6] | 4 | F2 | [S44-S47] |
| decode, short context | prose (prompt 19, 1,180 tokens, T 0.6) | 142.8 [142.0-145.6] | 4 | F2 | [S48-S51] |
| decode, short context | struct (prompt 98, 7,230 tokens, T 0.0) | 237.4 [234.4-240.9] | 4 | F2 | [S52-S55] |
| decode near 16K (APPROXIMATE) | R1-verify20k (prompt 24,238, 3,647 tokens) | 168.4 [164.2-168.9] | 3 | F2-screen | [S56-S58] |
| decode near 16K (APPROXIMATE) | W3-research (prompt 26,728, 2,048 tokens) | 181.8 [181.0-188.9] | 3 | F2-screen | [S59-S61] |
| decode at 16K (too few tokens to count) | pp16k: 32 tokens after the prompt | 121.0 | 1 | F2 | [S36] |
| decode near 64K (APPROXIMATE) | R2-report54k (prompt 54,070, 3,304 tokens) | 158.6 [156.5-169.4] | 3 | F2-screen | [S62-S64] |

**Every workload in the inputs** (median [min-max] over passes; acceptance = drafts accepted / drafts offered, MTP and prompt-lookup drafts together):

| set | workload | prompt tokens | prompt tok/s | generated | decode tok/s | draft acceptance | temperature | passes | src |
|---|---|---|---|---|---|---|---|---|---|
| F2 | prose | 19 | 155.1 [149.8-157.2] | 1,180 | 142.8 [142.0-145.6] | 51.9 % | 0.6 | 4 | [S48-S51] |
| F2 | conv | 38 | 116.2 [101.3-118.8] | 1,094 | 156.2 [154.6-171.6] | 64.6 % | 0.6 | 4 | [S44-S47] |
| F2 | struct | 98 | 243.4 [241.2-246.2] | 7,230 | 237.4 [234.4-240.9] | 96.3 % | 0.0 | 4 | [S52-S55] |
| F2 | pp16k | 16,676 | 3,975.6 [3,975.6-3,975.6] | 32 | 121.0 [121.0-121.0] | 73.1 % | 1.0 | 1 | [S36] |
| F2 | pp64k | 66,617 | 4,564.8 [4,564.8-4,564.8] | 1 | - | - | 1.0 | 1 | [S37] |
| F2-screen | W1-think | 111 | 306.4 [300.1-319.2] | 3,072 | 178.5 [173.6-199.1] | 71.8 % | 1.0 | 3 | [S38-S40] |
| F2-screen | W2-code | 125 | 415.4 [405.8-418.6] | 3,072 | 174.3 [172.3-174.8] | 69.2 % | 1.0 | 3 | [S41-S43] |
| F2-screen | B-write | 1,369 | 1,666.5 [1,663.8-1,674.2] | 2,438 | 167.8 [164.8-206.4] | 70.3 % | 1.0 | 3 | [S27-S29] |
| F2-screen | A-edit | 2,676 | 2,715.5 [2,713.7-2,721.3] | 343 | 184.1 [172.9-187.2] | 84.0 % | 1.0 | 3 | [S30-S32] |
| F2-screen | R3-extract5k | 5,012 | 3,667.5 [3,656.7-3,735.7] | 1,193 | 199.6 [182.0-201.6] | 82.5 % | 1.0 | 3 | [S33-S35] |
| F2-screen | R1-verify20k | 24,238 | 4,534.5 [4,531.5-4,538.0] | 3,647 | 168.4 [164.2-168.9] | 77.5 % | 1.0 | 3 | [S56-S58] |
| F2-screen | W3-research | 26,728 | 4,653.1 [4,637.9-4,655.2] | 2,048 | 181.8 [181.0-188.9] | 77.7 % | 1.0 | 3 | [S59-S61] |
| F2-screen | R4-agent33k | 33,417 | 4,460.3 [4,459.2-4,460.6] | 281 | 151.8 [150.4-153.7] | 69.5 % | 1.0 | 3 | [S65-S67] |
| F2-screen | R2-report54k | 54,070 | 4,712.7 [4,710.0-4,714.2] | 3,304 | 158.6 [156.5-169.4] | 70.5 % | 1.0 | 3 | [S62-S64] |
| P | prose | 19 | 134.9 [134.0-136.6] | 1,113 | 136.0 [133.1-138.4] | 54.4 % | 0.6 | 3 | [S68-S70] |
| P | conv | 38 | 112.8 [111.5-113.1] | 1,006 | 146.0 [143.7-149.0] | 62.4 % | 0.6 | 3 | [S71-S73] |
| P | struct | 98 | 241.0 [239.0-242.5] | 7,230 | 225.8 [225.7-226.4] | 96.5 % | 0.0 | 3 | [S74-S76] |
| P-screen | W1-think | 110 | 296.3 [292.6-300.6] | 3,072 | 174.3 [171.8-189.0] | 72.6 % | 1.0 | 3 | [S77-S79] |
| P-screen | W2-code | 124 | 410.1 [409.6-428.9] | 3,072 | 153.9 [148.8-155.0] | 64.3 % | 1.0 | 3 | [S80-S82] |
| P-screen | B-write | 1,371 | 1,674.2 [1,628.5-1,684.5] | 2,149 | 158.9 [155.4-165.1] | 71.7 % | 1.0 | 3 | [S83-S85] |
| P-screen | A-edit | 2,679 | 2,723.0 [2,719.5-2,724.2] | 356 | 134.8 [132.4-143.1] | 80.0 % | 1.0 | 3 | [S86-S88] |
| P-screen | R3-extract5k | 5,010 | 3,663.2 [3,648.7-3,717.4] | 1,080 | 182.3 [172.0-184.9] | 82.0 % | 1.0 | 3 | [S89-S91] |
| P-screen | R1-verify20k | 24,239 | 4,527.8 [4,526.1-4,535.9] | 3,805 | 154.8 [153.3-155.2] | 77.4 % | 1.0 | 3 | [S92-S94] |
| P-screen | W3-research | 26,728 | 4,648.1 [4,640.9-4,656.1] | 2,048 | 161.5 [159.3-163.3] | 76.8 % | 1.0 | 3 | [S95-S97] |
| P-screen | R4-agent33k | 33,416 | 4,464.8 [4,462.6-4,466.7] | 260 | 130.9 [125.3-133.4] | 71.3 % | 1.0 | 3 | [S98-S100] |
| P-screen | R2-report54k | 54,071 | 4,713.5 [4,711.5-4,715.7] | 3,399 | 150.8 [147.0-152.8] | 70.7 % | 1.0 | 3 | [S101-S103] |
| PU | pp16k | 16,676 | 3,976.4 [3,972.9-3,977.9] | 31 | 99.6 [84.3-104.4] | 58.1 % | 1.0 | 3 | [S104-S106] |
| PU | pp64k | 66,617 | 4,565.3 [4,564.8-4,570.0] | 1 | - | - | 1.0 | 3 | [S107-S109] |

Sets: **F2** = the current build (fetch build + STRATA_ADAPT_FETCH=2, no picture reader): decode 3 passes in the ADAPT_FETCH gap (11-09 17:54-18:03) + 1 pass of pp16k / pp64k / decode in the adoption check (11-09 20:02-20:05); **F2-screen** = 9-workload screen on the current build, 3 passes, 11-09 18:13-18:34 (the gap's arm F2); **P** = reference: the same form on the P028x engine before the fetch patch (P028x + STRATA_HC_UPMIX=1), decode 3 passes, same gap, 11-09 17:51-18:05; **P-screen** = reference: the same screen on the P028x engine before the fetch patch, 3 passes, same gap, 11-09 18:05-18:37; **PU** = reference: pp16k / pp64k, 3 passes, on the P028x engine before the fetch patch with STRATA_HC_UPMIX=1, 11-09 08:13-08:43.

- Two workloads (W1-think, R1-verify20k) are two engine requests each: the server ends the thinking pass at its room limit and continues the answer in a second request that reuses the first's state (the second reads only 19 new tokens) [S110]. The numbers above count the whole reply, and the server adds the continuation's ~80 ms prompt read to the prompt time, so R1-verify20k's prompt rate reads ~1.5 % low (pass 1: 4,534.5 tok/s for the reply vs 4,601.8 for its first engine request) [S111] [S56]; W1-think's 111-token prompt rate means nothing for the same reason.
- The struct fixture (T 0.0, repetitive structured text) accepts ~96 % of drafts, so its ~237 tok/s is the upper end; W1 / W2 at T 1.0 with thinking are the realistic short-context decode.
- Noise, as the spread of the 3 passes per arm in the ADAPT_FETCH gap: screen decode geomean 3.4 %, conv 11.0 %, struct 2.3 %, prose 4.0 % [S112]; pp16k / pp64k 0.1 / 0.5 % over 3 passes on the P028x engine before the fetch patch [S113]. The current build's pp16k / pp64k ran one pass each, level with that engine's 3-pass medians [S114].
- **How =2 came to be served.** The gap's frozen rule made =1 (F1: screen decode +10.2 %, prompt +0.11 %) its proposal and failed =2 on one per-workload prompt check, R4-agent33k -0.1 % against a 0.1 % noise [S115] [S116]. The owner adopted =2 as a recorded exception for this decision only, with the rule unchanged: the loss is on the prompt path, which ADAPT_FETCH does not touch; =2 had the higher decode (+12.7 %); both quality checks passed [S117]. The adoption check on the served config: exact7 7/7 with the switch unset and set, pp16k / pp64k level with the P028x engine before the fetch patch, decode +3.8 to +7.1 % over the gap's P in one pass [S118].

- ADAPT_FETCH gap, F2 (=2, the current build) vs P (the P028x engine before the fetch patch), 3 passes each: "speed vs P: FAIL (screen) - decode targets (GAIN_FORM screen): conv: 160.8 vs 146.2 tok/s (+9.9 %; noise 11.0 %; 3/3 passes) [no-loss check]; struct: 238.6 vs 226.0 tok/s (+5.6 %; noise 2.3 %; 3/3 passes) above +max(noise, 1 %) [no-loss check]; prose: 142.5 vs 135.8 tok/s (+4.9 %; noise 4.0 %; 3/3 passes) above +max(noise, 1 %) [no-loss check]; screen decode geomean: 174.8 vs 155.1 tok/s (+12.7 %; noise 3.4 %; 3/3 passes) above +max(noise, 1 %) [the primary target]; B2 check PASS: conv +9.9 % (noise 6.9 %); struct +5.6 % (noise 2.3 %); prose +4.9 % (noise 6.3 %); B3 FAIL: screen prompt geomean +0.18 % vs P (B3_PROMPT_FORM tol1: within -1 %; client clock minus the save; (info) the strict form: not below), decode geomean +12.69 %; per-workload no-loss [11-07 amendment: prompt = engine prompt ms minus the chat-cache save] FAILS: R4-agent33k prompt -0.1 % (noise 0.1 %); (info) client clock minus the save: no workload slower beyond its noise; (info) outside-engine time: no workload of F2 worse than P in every pass; chat-cache save [11-07 amendment]: F2 +1.4 % vs P (save index = each save / the stored median of its level, geometric mean per pass then over passes; 3 / 3 passes; noise 3.7 %) -> PASS; (info) with noise = half the range: GAIN" [S112]
- Same gap, =2 vs =1: "INFO F2 vs F1 (the =2 part's own effect): no gain: conv: 160.8 vs 153.8 tok/s (+4.6 %; noise 11.0 %; 3/3 passes) [no-loss check]; struct: 238.6 vs 236.3 tok/s (+1.0 %; noise 3.5 %; 3/3 passes) [no-loss check]; prose: 142.5 vs 144.0 tok/s (-1.0 %; noise 3.6 %; 3/3 passes) [no-loss check]; screen decode geomean: 174.8 vs 170.9 tok/s (+2.3 %; noise 3.4 %; 3/3 passes) [the primary target]" [S119]
- Adoption check on the served config (11-09 20:02-20:05), pp16k; in these quoted lines 'this morning's PU' = set PU, 'this morning's P' = the same engine without U (not set P), 'the U adoption's check' = one pass on the same engine with U at 11:35: "pp16k: S2 3,975.6 tok/s; vs this morning's PU 3,976.4 (-0.0 %); vs this morning's P 3,849.8 (+3.3 %); vs the U adoption's check 3,929.5 (+1.2 %)" [S120]
- Adoption check, pp64k: "pp64k: S2 4,564.8 tok/s; vs this morning's PU 4,565.3 (-0.0 %); vs this morning's P 4,365.6 (+4.6 %); vs the U adoption's check 4,566.1 (-0.0 %)" [S121]
- Adoption check, decode ('gap P' = set P, 'gap F2' = the gap's three F2 passes): "decode tok/s (1 pass, sampled, noise 4-7 %): conv 156.2 (gap P 146.0, +7.0 %) (gap F2 156.1, +0.1 %); struct 234.4 (gap P 225.8, +3.8 %) (gap F2 239.4, -2.1 %); prose 145.6 (gap P 136.0, +7.1 %) (gap F2 142.2, +2.4 %); geomean vs gap P +5.9 %, vs gap F2 +0.1 %" [S122]

## 5. Where the routed experts are served (decode)

Per request the engine logs: `decode expert cache hit rate: X% (H hits / L lookups); O more read by the GPU over PCIe or from another GPU (p% of all R routed)` and, with a helper GPU, `CUDA1: N expert entries`. Counted per routed (token column x layer x expert) entry: **main GPU cache** = H; **helper GPU cache** = N; **PCIe share** (the main GPU reads the expert from pinned RAM over PCIe) = O - N; **CPU** (the CPU pool computes it) = L - H. The four add up to R. The parser is adapted from the project's earlier placement study.

| log | subset | requests | routed entries | main GPU cache | helper GPU cache | PCIe share | CPU | src |
|---|---|---|---|---|---|---|---|---|
| screen F2, current build (ADAPT_FETCH gap, 3 passes, one warm-up request each) | all requests | 36 | 35,634,240 | 67.3 % | 17.3 % | 6.0 % | 9.4 % | [S123-S125] |
| screen F2, current build (ADAPT_FETCH gap, 3 passes, one warm-up request each) | requests with >= 200,000 routed entries | 32 | 34,998,240 | 67.4 % | 17.2 % | 6.0 % | 9.3 % | [S123-S125] |
| decode fixtures F2, current build (conv / struct / prose x3) | all requests | 9 | 15,436,800 | 72.1 % | 13.1 % | 5.7 % | 9.0 % | [S126-S128] |
| served log on the current build, 11-09 20:06 - 11-10 (4 engine starts) | all requests | 23 | 103,199,520 | 72.3 % | 15.0 % | 5.1 % | 7.6 % | [S129] |
| served log on the current build, 11-09 20:06 - 11-10 (4 engine starts) | requests with >= 200,000 routed entries | 8 | 102,863,520 | 72.3 % | 15.0 % | 5.1 % | 7.5 % | [S129] |
| screen P, the P028x engine before the fetch patch (same gap, 3 passes, one warm-up request each) | all requests | 36 | 37,412,160 | 62.6 % | 17.3 % | 5.7 % | 14.4 % | [S130-S132] |
| screen P, the P028x engine before the fetch patch (same gap, 3 passes, one warm-up request each) | requests with >= 200,000 routed entries | 33 | 36,912,480 | 62.8 % | 17.3 % | 5.7 % | 14.2 % | [S130-S132] |
| decode fixtures P, the P028x engine before the fetch patch (same gap) | all requests | 9 | 15,169,920 | 69.9 % | 13.1 % | 6.1 % | 10.9 % | [S133-S135] |
| served log 10-30 16:55 - 11-09 11:39, the P028x engine before the fetch patch (103 engine starts) | all requests | 32,797 | 42,408,661,440 | 62.8 % | 17.4 % | 6.0 % | 13.8 % | [S136] |
| served log 10-30 16:55 - 11-09 11:39, the P028x engine before the fetch patch (103 engine starts) | requests with >= 200,000 routed entries | 26,568 | 41,540,459,520 | 62.9 % | 17.4 % | 6.0 % | 13.7 % | [S136] |
| decode-timing pass T2dv (11-05, the P028x engine before the fetch patch, without U) | all requests | 12 | 11,638,560 | 62.6 % | 17.3 % | 5.7 % | 14.4 % | [S137] |

Slots: the main GPU holds 4,585 experts (8.75 GiB) [S138] and the helper 3,300 (6.21 GiB) [S139], of 24,576 routed experts (48 layers x 512) [S1]: 18.7 % + 13.4 % = 32.1 % of the experts serve the shares above; the rest live in pinned RAM. The main cache is filled from a routing-frequency profile; an adaptive tier swaps experts in while decoding.

- PCIe share setting: the engine re-prices it while serving (`PCIe share: ... -> pcie_frac X`), 4 times in served log on the current build, 11-09 20:06 - 11-10 (4 engine starts): 0.40 x1, 0.45 x3 [S141].
- No `route tail skip` line in served log on the current build, 11-09 20:06 - 11-10 (4 engine starts): the lossy tail skip never acted [S129].
- PCIe share setting: the engine re-prices it while serving (`PCIe share: ... -> pcie_frac X`), 121 times in served log 10-30 16:55 - 11-09 11:39, the P028x engine before the fetch patch (103 engine starts): 0.35 x1, 0.40 x86, 0.45 x28, 0.50 x5, 0.55 x1 [S142].
- No `route tail skip` line in served log 10-30 16:55 - 11-09 11:39, the P028x engine before the fetch patch (103 engine starts): the lossy tail skip never acted [S136].

- Decode only. The prompt pass works differently: it borrows 3,231 of the main GPU's cache slots for its chunks (section 7), and chunks under 1,792 tokens send 40 % of the expert work to the CPU.
- What the fetch patch changes: with STRATA_ADAPT_FETCH=2 a missed expert that the main GPU read over PCIe is kept in the main cache when it is routed clearly more often than the layer's least-used resident expert [S143], about 83 admissions per verify window on the screen. Against the same screen on the P028x engine before the fetch patch, the main cache's share of routed entries rose from 62.6 to 67.3 % and the CPU's fell from 14.4 to 9.4 %; the helper's (17.3 %) and the PCIe share (about 6 %) stayed [S144] [S145].
- Admissions land only in the main (RTX 5080) cache. The helper's experts are static (filled at start), and the owner's patch makes the PCIe share's pick list leave out experts the helper holds; without that, the picks would go to the helper and never be fetched [S146] [S147].
- The served log on the current build is short (the 11-09 evening and the 11-10 morning), and four long generations (71,579, 27,946, 32,768 and 15,110 tokens) carry most of its routed entries [S148-S151]; read the screen as the main figure.
- On the P028x engine before the fetch patch (ten days of served traffic, 10-30 to 11-09): about 63 % of routed entries hit the main GPU's cache, 17 % the helper's, 6 % came over PCIe and 14 % were computed by the CPU, and the adaptive tier ran at its cap of 24 swaps per window in every request [S152].

- The gap's own count, screen F2 (cross-check of the first row): "F2 B3: 36 requests, admissions per window 82.875 (1,331,726 in 16,069 windows, 36 fetch lines); placement main 67.3 % / helper 17.3 % / PCIe 6.0 % / CPU 9.4 % of 35,634,240 routed; decode 172.6 tok/s (engine)" [S144]
- The gap's own count, decode fixtures F2: "F2 B2: 9 requests, admissions per window 82.988 (491,287 in 5,920 windows, 9 fetch lines); placement main 72.1 % / helper 13.1 % / PCIe 5.7 % / CPU 9.0 % of 15,436,800 routed; decode 209.6 tok/s (engine)" [S153]
- The gap's own count, screen P (the P028x engine before the fetch patch): "P B3: 36 requests, admissions per window - (no fetch line); placement main 62.6 % / helper 17.3 % / PCIe 5.7 % / CPU 14.4 % of 37,412,160 routed; decode 157.8 tok/s (engine)" [S145]
- The gap's own count, decode fixtures P (the P028x engine before the fetch patch): "P B2: 9 requests, admissions per window - (no fetch line); placement main 69.9 % / helper 13.1 % / PCIe 6.1 % / CPU 10.9 % of 15,169,920 routed; decode 198.4 tok/s (engine)" [S154]
- The earlier desk study's figure from the ten-day served log (the P028x engine before the fetch patch; cross-check): "| Served P028x, 32,797 requests | 62.8 % | 17.4 % | 6.0 % | 13.8 % |" [S155]

## 6. MTP speculative drafting

Drafting: one MTP draft layer (837 MiB of VRAM) with a 40,525-token draft head, `--spec 7` (verify windows of up to 8 tokens), `--spec-min-p 0.5`, the cost gate pricing draft steps 1-3 and the cumulative draft-length rule past them; exact speculative sampling. The engine also drafts from earlier repeats in the context (prompt lookup, `--suffix-draft`, default 3); those drafts are logged apart and subtracted below.

| log | requests | verify windows | all drafts accepted | MTP drafts accepted | prompt-lookup drafts accepted | drafts per MTP window | tokens per window | src |
|---|---|---|---|---|---|---|---|---|
| screen F2, current build (ADAPT_FETCH gap, 3 passes, one warm-up request each) | 36 | 16,069 | 42,746 / 58,169 = 73.5 % | 40,418 / 55,279 = 73.1 % | 2,328 / 2,890 in 580 windows | 3.59 | 3.66 | [S123-S125] |
| decode fixtures F2, current build (conv / struct / prose x3) | 9 | 5,920 | 22,595 / 26,240 = 86.1 % | 21,266 / 24,732 = 86.0 % | 1,329 / 1,508 in 274 windows | 4.40 | 4.82 | [S126-S128] |
| served log on the current build, 11-09 20:06 - 11-10 (4 engine starts) | 23 | 56,091 | 99,619 / 158,908 = 62.7 % | 93,913 / 151,909 = 61.8 % | 5,706 / 6,999 in 1,482 windows | 2.80 | 2.78 | [S129] |
| screen P, the P028x engine before the fetch patch (same gap, 3 passes, one warm-up request each) | 36 | 17,112 | 43,978 / 60,830 = 72.3 % | 41,811 / 58,038 = 72.0 % | 2,167 / 2,792 in 626 windows | 3.54 | 3.57 | [S130-S132] |
| decode fixtures P, the P028x engine before the fetch patch (same gap) | 9 | 5,828 | 22,311 / 25,776 = 86.6 % | 20,571 / 23,848 = 86.3 % | 1,740 / 1,928 in 345 windows | 4.36 | 4.83 | [S133-S135] |
| served log 10-30 16:55 - 11-09 11:39, the P028x engine before the fetch patch (103 engine starts) | 32,797 | 19,727,477 | 51,414,392 / 68,623,901 = 74.9 % | 43,916,482 / 59,956,438 = 73.2 % | 7,497,910 / 8,667,463 in 1,584,839 windows | 3.33 | 3.61 | [S136] |
| decode-timing pass T2dv (11-05, the P028x engine before the fetch patch, without U) | 12 | 5,326 | 14,045 / 18,921 = 74.2 % | 13,254 / 17,875 = 74.1 % | 791 / 1,046 in 234 windows | 3.53 | 3.64 | [S137] |

Tokens per window = (drafts accepted + windows) / windows: each verify window commits its accepted drafts plus one token of its own. MTP = all drafts minus the prompt-lookup (`suffix drafts`) lines.

**Acceptance per draft position: not in these logs.** The Qwen engine prints it only with `STRATA_SPEC_DEPTH=1` (serve mode, positions 1-5, accepted / tested), and no existing run had it on. What exists: the per-request totals above and the decode-timing pass's mean window width (section 8).

- The cumulative rule's threshold adapts per request between 0.371 and its floor 0.265 [S156]: greedy structured text drafts ~6 per window, sampled thinking text ~2-3.
- The served slice on the current build is mostly four long generations [S148-S151], so its acceptance is not comparable with the screen's.

- Decode-timing pass (11-05, the P028x engine before the fetch patch): mean verify-window width T and tokens per window (tok/w): "11 requests, 5208 windows: 23.17 ms/window = GPU-reach 9.60 + host 10.41 (plan 0.64, CPU 9.67) + draft 2.35 + tail 0.77; T 4.55, 3.64 tok/w" [S157]

## 7. Memory: RAM, VRAM and swap

**At engine start** (one start of the measured form [S158]):

| what | value | line in [S158] |
|---|---|---|
| engine memory guard: limit / available at start | 92.0, 87.7 | l. 2 |
| helper GPU free before its expert arena | 7.56 | l. 3 |
| PCIe probe and the start-up PCIe share | 57.8, 0.55 | l. 4 |
| dense weights from the native pack (MiB) | 1466 | l. 6 |
| native projection matrices (count, MiB) | 300, 2018.88 | l. 7 |
| expert routing profile: ranked (layer, expert) pairs | 24,576 | l. 10 |
| KV cache: cells per attention layer in VRAM / total, K/V in pinned RAM (GiB) | 32,768, 131,072, 1.55 | l. 11 |
| per-layer-embedding table rows (read from the second shard) | 320,001,536 | l. 12 |
| MTP draft layer in VRAM (MiB: total, experts, dense) | 837, 675, 111 | l. 13 |
| output head as loaded (bytes) | 521,472,000 | l. 14 |
| expert arena loaded into pinned RAM (GiB, GiB/s) | 46.84, 6.22 | l. 18 |
| CPU expert-pool workers | 15 | l. 21 |
| main GPU free / reserve when sizing the expert cache | 9.53, 713 | l. 28 |
| main GPU expert cache (slots, GiB) | 4585, 8.75 | l. 29 |
| helper GPU expert cache (experts, GiB) | 3300, 6.21 | l. 35 |
| prompt chunk | 16,384 | l. 40 |
| prompt path borrows main-cache slots (slots, GiB) | 3231, 6.13 | l. 41 |
| verify window (tokens) | 8 | l. 44 |
| MTP draft head vocabulary (tokens, MiB) | 40,525, 81.2 | l. 45 |
| main GPU free with everything loaded (MiB) | 522 | l. 50 |
| cumulative draft-length threshold (start, floor) | 0.371, 0.265 | l. 52 |
| cost gate table bins | 60 | l. 51 |

**Per run, from the server guard's summary line** (whole process tree; GPU free memory from nvidia-smi):

| run | s | min_MemAvailable | min_5080_free | max_tree_RSS | max_swap_used | min_4060Ti_free | guard | src |
|---|---|---|---|---|---|---|---|---|
| r23af11091734-bpF2-1 | 92 | 36.3 GiB | 439 MiB | 51.1 GiB | 4.3 GiB | 1287 MiB | ok | [S159] |
| r23af11091734-bpF2-2 | 92 | 36.3 GiB | 441 MiB | 51.1 GiB | 4.3 GiB | 1287 MiB | ok | [S160] |
| r23af11091734-bpF2-3 | 93 | 36.4 GiB | 441 MiB | 51.1 GiB | 4.3 GiB | 1287 MiB | ok | [S161] |
| r23af11091734-scrF21 | 193 | 33.2 GiB | 441 MiB | 54.3 GiB | 4.3 GiB | 1287 MiB | ok | [S162] |
| r23af11091734-scrF22 | 209 | 33.1 GiB | 441 MiB | 54.3 GiB | 4.3 GiB | 1287 MiB | ok | [S163] |
| r23af11091734-scrF23 | 209 | 33.2 GiB | 441 MiB | 54.3 GiB | 4.29 GiB | 1287 MiB | ok | [S164] |
| r23aa11091954-S2-decode | 92 | 36.3 GiB | 439 MiB | 51.1 GiB | 4.29 GiB | 1287 MiB | ok | [S165] |
| r23aa11091954-S2-pp16k | 51 | 36.2 GiB | 473 MiB | 51.2 GiB | 4.29 GiB | 1287 MiB | ok | [S166] |
| r23aa11091954-S2-pp64k | 61 | 35.9 GiB | 499 MiB | 51.5 GiB | 4.29 GiB | 1287 MiB | ok | [S167] |

**Swap during each run** (1-second system samples from the run's monitor; MiB of swap in use: first -> max -> last):

| run | samples | min MemAvailable GiB | max engine RSS GiB | swap used MiB | swap growth | src |
|---|---|---|---|---|---|---|
| monitor-r23af11091734-bpF2-1 | 95 | 36.3 | 50.8 | 4399 -> 4399 -> 4399 | 0 MiB in 0 steps | [S168] |
| monitor-r23af11091734-bpF2-2 | 94 | 36.3 | 50.8 | 4399 -> 4399 -> 4399 | 0 MiB in 0 steps | [S169] |
| monitor-r23af11091734-bpF2-3 | 95 | 36.4 | 50.8 | 4399 -> 4399 -> 4399 | 0 MiB in 0 steps | [S170] |
| monitor-r23af11091734-scrF21 | 195 | 33.2 | 54.1 | 4398 -> 4398 -> 4398 | 0 MiB in 0 steps | [S171] |
| monitor-r23af11091734-scrF22 | 211 | 33.1 | 54.1 | 4398 -> 4398 -> 4398 | 0 MiB in 0 steps | [S172] |
| monitor-r23af11091734-scrF23 | 212 | 33.3 | 54.1 | 4397 -> 4397 -> 4397 | 0 MiB in 0 steps | [S173] |
| monitor-r23aa11091954-S2-decode | 95 | 36.3 | 50.8 | 4394 -> 4394 -> 4394 | 0 MiB in 0 steps | [S174] |
| monitor-r23aa11091954-S2-pp16k | 53 | 36.2 | 51.0 | 4395 -> 4395 -> 4394 | 0 MiB in 0 steps | [S175] |
| monitor-r23aa11091954-S2-pp64k | 63 | 35.9 | 51.3 | 4394 -> 4394 -> 4394 | 0 MiB in 0 steps | [S176] |

- RAM available with no engine loaded (before the adoption check): "=== 2026-11-09 19:55:14 8080 down: engines left: none MemAvailable 88 GB" [S177]
- The 40-long-prompt exactness run on the fetch build with the switch unset (one engine, its own cache setting; read it for RAM and swap): "pfy F0L40: 2026-11-09T17:49:06 pfyaf-F0L40 exit=0 514s min_MemAvailable=39.0GiB@312s min_5080_free=7355MiB@506s max_tree_RSS=48.7GiB max_swap_used=4.30GiB min_4060Ti_free=1179MiB ok" [S178]
- Restart of the served engine after the gap (still the P028x engine before the fetch patch): "2026-11-09 19:03:10 port_gap4: no swap-out while P028x started" [S179]
- Restart of the served engine on the current build after the adoption check: "2026-11-09 20:06:08 port_gap4: no swap-out while P028x started" [S180]

- The engine warned 4 times in the served log on the current build, 11-09 20:06 - 11-10 (4 engine starts) that the main GPU had under 512 MiB free at a request's start (lowest 504 MiB) [S181]: the cache is sized to leave only the configured reserve.
- The engine warned 103 times in the served log 10-30 16:55 - 11-09 11:39, the P028x engine before the fetch patch (103 engine starts) that the main GPU had under 512 MiB free at a request's start (lowest 455 MiB) [S182]: the cache is sized to leave only the configured reserve.

- The owner's guard stops a run if the main GPU's free memory falls under 300 MiB or MemAvailable under 12 GiB [S183] [S184]; every run above ended `ok`.
- Swap in use stayed flat inside every measured run: about 4.3 GiB of other programs' pages were swapped out before the runs began and none moved during them, and the served engine restarted with no swap-out after the gap and after the adoption check (quoted above). The owner's swap rule fails a run on the engine's own swap or on sustained swap traffic inside it, not on pages swapped before it [S185].
- The served config adds the CPU picture reader (about 1 GB of RAM in its own process), not in these runs [S186].
- VRAM use is flat by design: the main GPU's expert cache takes all but the reserve at start, so its free memory is the reserve's remainder (about 440-500 MiB) whatever the context; the KV cells past 32,768 per attention layer live in 1.55 GiB of pinned RAM allocated at start, so a 64K prompt costs prompt time and a little RSS (51.5 vs 51.2 GiB for 16K), not VRAM. The fetch patch adds about 260 bytes of VRAM, carved after the cache is sized, so the main cache keeps its 4,585 slots [S187].

## 8. Where a decode window's time goes (the slowest step)

11 requests, 5,208 windows [S157]; window width 4.55 columns, 3.64 tokens per window = 6.37 ms per token (157 tok/s inside the windows).

| part of a window | ms | share |
|---|---|---|
| GPU-reach wait (dense layers + the GPU's own MoE branch, host-measured) | 9.60 | 41.4 % |
| CPU pool (missed experts) inside the host's per-layer work | 9.67 | 41.7 % |
| host plan + other per-layer host work | 0.74 | 3.2 % |
| MTP drafting between windows | 2.35 | 10.1 % |
| tail (head, sampling, launch) | 0.77 | 3.3 % |
| **window** | **23.17** | 100 % |

**Slowest step: CPU pool (missed experts) inside the host's per-layer work, 9.67 of 23.17 ms (42 %)** [S157].
Per layer-window: GPU-reach 199.9 us, CPU 201.6 us, plan 13.33 us; distinct CPU experts 4.91, PCIe experts 2.37, VRAM hit entries 28.5 [S188].
Helper GPU: 46.6 launches per window; the host spends 0.541 ms per window staging and launching them and 0.658 ms waiting for them [S189].
GPU stage table (profiled windows): serial stages 8.61 ms per window, MoE branch with the inline shared expert 11.44 (of it waiting for the CPU rows 0.54, VRAM hits 2.51, PCIe groups 0.44), head 0.66 [S190].

Largest GPU stages (ms per window):

| ms/window | layer kind | stage | line in [S191] |
|---|---|---|---|
| 5.08 | GDN layers | waitB | l. 6 |
| 1.85 | GDN layers | VRAM hits | l. 7 |
| 1.52 | QSA layers | waitB | l. 8 |
| 1.46 | GDN layers | q8+qkv/q-idx gemv | l. 9 |
| 0.85 | GDN layers | out-proj | l. 10 |
| 0.77 | GDN layers | shared+quant | l. 11 |
| 0.67 | QSA layers | VRAM hits | l. 12 |
| 0.66 | GDN layers | head | l. 13 |
| 0.58 | GDN layers | hc1 down | l. 14 |
| 0.55 | GDN layers | hc0 down | l. 15 |
| 0.53 | GDN layers | router+plan+bell | l. 16 |
| 0.42 | GDN layers | waitCPU | l. 17 |
| 0.42 | GDN layers | copy+combine | l. 18 |
| 0.41 | GDN layers | hc1 up | l. 19 |

The timing pass ran [S192] = the served form with the timing switches STRATA_DECODE_TIMING, STRATA_VERIFY_PROFILE and without STRATA_ADAPT_FETCH, STRATA_HC_UPMIX (and the picture reader off).

- **Everything in this section was measured on 11-05 on the P028x engine before the fetch patch, without U.** The fetch patch acts on exactly this split: on the 11-09 screen it cut the CPU's share of routed entries from 14.4 to 9.4 % (section 5), so on the current build the CPU pool takes a smaller part of each window than shown here; whether it is still the slowest step was not measured.
- Method: one 9-workload screen pass with STRATA_DECODE_TIMING=1 (the host's split per window) and STRATA_VERIFY_PROFILE=1 (the GPU stage table); the profile changes the graph (shared expert inline, fused waits off), so its rates run ~2 % low [S193]. The first request (warm-up) is left out; means are window-weighted.
- Reading it: a window is a serial chain per layer. The GPU runs the dense part of a layer (GDN mixer, hyper-connection reads, router) while the CPU pool idles; then the CPU pool computes the layer's missed experts while the GPU mostly waits (`waitB` in the stage table) [S194]. The GPU's serial part is 98-99 % busy with 1.5-3 us of launch gaps per layer, so only kernel work shortens it [S195].
- The CPU pool (9.67 ms) and the GPU-reach wait (9.60 ms) are nearly equal; per layer-window the CPU pool is the long pole in 69 % of layer-windows on two cards (an older build's trace, 10-21) [S196]. Fewer CPU-computed experts (a bigger or smarter GPU cache) is the lever; a faster GPU kernel helps only the other half. The fetch patch is such a lever (section 5).

- Timing pass (11-05, the P028x engine before the fetch patch), W1-think (client decode speed under the profiler): "T2dvn W1-think r0: prompt 108 ttft 0.29 s, 3072 tokens, 163.97 tok/s, length" [S197]
- Timing pass, R2-report54k: "T2dvr R2-report54k r0: prompt 54070 ttft 12.014 s, 3462 tokens, 155.02 tok/s, stop" [S198]
- Cross-check: the two-card base arm of the 11-05 decode-timing gate (the P028x engine before the fetch patch; host split only, no GPU profile): "timing Bt (INFO): 12 requests, 4958 windows: 22.01 ms/window = GPU-reach 8.88 + host 10.05 (plan 0.64, CPU 9.31) + draft 2.30 + tail 0.75; T 4.44, 3.54 tok/w |   per layer: GPU-reach 185.0 us, CPU 194.0 us, plan 13.35 us; CPU experts 4.62, PCIe 2.19, VRAM hits 28.2 per layer-window" [S199]

## 9. Already tried on this model

One line per idea: status, the measured result, and where it was measured. ADOPTED = in the served config; REJECTED = measured and dropped; PARKED = measured or built, waiting; NOT MEASURED / DESK ONLY = estimate or reading only. (List: work/qwen4-kit/profile-pack/already-tried-flashnext.txt.)

### Prompt path (reading the prompt)

| status | idea | measured result | src |
|---|---|---|---|
| **ADOPTED** | STRATA_HC_UPMIX=1 (U: hyper-connection up projection + mix in one kernel; upstream opt-in) | exact on P028x (exact7 7/7, long40 0 of 40 logit files differ); pp16k 3,975.7 vs 3,849.4 tok/s (+3.3 %, noise 0.1 %), pp64k 4,566.7 vs 4,370.4 (+4.5 %, noise 0.5 %); screen and decode no loss; served since 11-09 | [S200] [S113] [S201] |
| **PARKED** | STRATA_PF_TAIL_SPLIT=1 (T, Basalt prompt-path port) | rounding-level; pp16k +6.1 %, pp64k +2.6 % vs P028x; but it drops the 16,384-token mid-prompt checkpoint, so a prompt that shares 16,500 tokens with a parked one is read again in full (16,527 tokens in 3,950 ms vs 143 in 381 ms); needs the newer port base | [S202] [S203] |
| **REJECTED** | STRATA_PF_AHEAD=1 (A, Basalt prompt-path port) | exact; +0.2 % pp16k / +0.6 % pp64k vs P028x, within noise | [S204] |
| **PARKED** | C = A,T,U + checkpoint pool (K, KP) + first-chunk rule at chunk 22,528 | rounding-level; pp16k +15.9 %, pp64k +8.9 % vs P028x, but decode -3.2 / -2.7 / -4.1 % (conv / struct / prose) vs B and the checkpoint pool switches the chat cache off; retry without K | [S205] [S206] |
| **REJECTED** | K = STRATA_CKPT_POOL, KP (checkpoint pool) | pp16k +1.2 % (noise 1.6 %), pp64k +0.1 %; KP +0.8 / -0.1 %: no gain | [S207] |
| **REJECTED** | GDN prompt paths STRATA_GDN_TC / STRATA_GDN_CONVL2 (upstream v0.2.9-0.2.10 defaults; pinned off) | failed the 40-prompt KL band on the port (stack: KL mean 0.575, p90 1.10, 5 rows above 1; TC alone fails too); stock v0.2.10 fails the same way; a decode-path check later put every prompt path in one scatter, so the question was closed; prompt speed never priced (KL failed first) | [S208-S211] |
| **ADOPTED** | prompt chunk --prefill auto:16384 (vs 8K chunks) | TTFT 32K -2.9 %, 120K -3.7 % (round 10); decode after the prompt -1.5 / -2.3 % at 32K / 120K (the chunk borrows cache slots) | [S212] |
| **REJECTED** | prompt chunk auto:32768 (the engine picks 22,272 tokens, borrows 4,086 slots) | 33.5K-token prompt -7.6 % TTFT, others within 1 % (round 11); later calibration: decode +0.5 %, TTFT 32K +1.3 %, 120K -1.4 %, so 16K stayed | [S213] [S214] |
| **ADOPTED** | equal-size prompt chunks (upstream #693) | rounding-level; up to -12.4 % TTFT where a prompt's tail is just over 1,024 tokens, never slower | [S215] |
| **ADOPTED** | STRATA_PREFILL_CPU_SHARE 0.4 with STRATA_PREFILL_CPU_SHARE_MAX 1792 | 0.4 cuts prompt time 15-21 % up to ~1,500 tokens and costs from ~2,000 (+6 % at 2,000, +27 % at 3,000), hence the 1,792 cap; on P028x share 0 is pp16k -2.9 %, pp64k -1.0 % | [S216] [S217] |
| **ADOPTED** | STRATA_PF_FUSED=1 (fused int8 prompt experts) | TTFT -3.3 to -3.7 % (round 10); off on P028x: pp16k -6.1 %, pp64k -6.5 % | [S218] [S217] |
| **ADOPTED** | STRATA_PREFILL_V2=1 (v2 prompt-expert kernels from Basalt) + STRATA_DEQUANT_WIDE=1 + draft rule (the 10-22 bundle) | decode +1.6 %; TTFT -4.3 / -8.9 / -6.0 / -6.0 % at 1K / 4K / 32K / 120K; on the v0.2.8 port v2 is bit-identical to the stock path | [S219-S221] |
| **ADOPTED** | STRATA_DEQUANT_WIDE=1 alone | output identical; TTFT -6.7 / -4.4 / -1.5 / -1.5 % at 1K / 4K / 32K / 120K | [S222] |
| **REJECTED** | STRATA_PROMPT_ATTN_IMMA=1 (int8 tensor-core prompt attention; upstream default since 0.2.7, pinned off) | TTFT -2.7 % at 32K / 120K; lowest KL of the variants but changed top-1 picks: 104 of 120 kept vs a floor of 108 | [S223] [S224] |
| **REJECTED** | --ple-inflight 256 (vs 128) | TTFT -0.7 / -0.4 / 0.0 / 0.0 %: no gain | [S225] |
| **REJECTED** | STRATA_PLE_AUTO_RAM / --ple-io ram (per-layer embedding table in RAM) | on paper: 28.8 GB table + 64.7 GB engine = 93.5 of 96.4 GB, above the lock limit; rows stay on the SSD (direct reads) | [S226] |
| **REJECTED** | GDN chunked prefill / FlashQLA-style recurrence (round 8) | the recurrence is only 7.6 % of prompt GPU time; dropped | [S227] |

### Decode: speculative drafting

| status | idea | measured result | src |
|---|---|---|---|
| **ADOPTED** | --spec 7 + STRATA_DRAFT_CUM=1 (cumulative draft length) vs --spec 4 | W1-W3 +3.2 % (ahead in 4 of 4 passes), tool-call turns +1.3 %, research call +0.3 % | [S228] |
| **INFO** | draft length A/B (gap 7, W1-W3 engine tok/s) | spec 4: 148.6; spec 7: 151.4 (+1.9 %); spec 7 + DRAFT_CUM: 158.9 (+6.9 %); the same without the cost gate: 160.5 (+8.0 %, one screen) | [S229] |
| **INFO** | why DRAFT_CUM exists | greedy structured text at spec 7: the earlier patch series drafted 3.00 per window vs stock 5.91 and Basalt 5.74 | [S230] |
| **REJECTED** | other draft depths on spec 4 (round 9) | spec 5 / min-p 0.5 +0.2 %; spec 6 / 0.6 -3.4 %; spec 8 + split -3.6 % | [S231] |
| **ADOPTED** | --spec-min-p 0.5 | 0.4 gave +0.5 % on one screen and -3.1 % in the rehearsal; with the cost gate on, min-p no longer sets the window | [S232] |
| **ADOPTED** | STRATA_COST_GATE (cost-aware draft length fitted on this PC) | round 14 on vs off: decode +3.4 %, agent-workload screen +2.8 %; round 19: +4.2 % decode on two cards, -2.0 % after 120K prompts | [S233] [S234] |
| **ADOPTED** | STRATA_SPEC_EXACT=1 (exact speculative sampling) vs upstream STRATA_SPEC_PROB | exact sampling +3.5 % decode, acceptance +8.5 % (round 14); upstream's SPEC_PROB is biased at a T 0.6 near-tie ('=' 59.6-62.2 % vs 52.3 % with speculation off; ours 54.5 %) because --spec-min-p gates on the drawn token's q | [S235-S237] |
| **REJECTED** | upstream SPEC_PROB + STRATA_SPEC_PROB_GATE=top on v0.2.7 | near-tie 51.0 vs 51.9 % (pass) but a second distribution check at p 0.047; decode geomean 0.897 of the then-served build vs 0.925 for upstream paths without it | [S238] |
| **NOT MEASURED** | STRATA_SPEC_COST (upstream's cost-aware draft window) | backlog item, never run | [S239] |
| **ADOPTED** | prompt-lookup drafts --suffix-draft 3 (served default); longer variants rejected | spec 8 with suffix 3 / 8 / 16: decode +0.9 / -0.8 / +0.7 %; the 8x3 variant -0.9 % on the agent-workload screen | [S240] [S241] |
| **REJECTED** | lookup windows up to 12 tokens (v0.2.10 --lookup-max-t) | decode +0.96 % (noise 5.6 %), but outputs depend on the window and the distribution checks fail | [S242] |
| **REJECTED** | Basalt's tuned MTP draft layer on this engine | W1 / W2 / W3 at spec 7: 182.9 / 152.2 / 152.5 vs 175.1 / 153.8 / 152.3 tok/s: a wash | [S243] |
| **NOT MEASURED** | DFlash / DFlash2 drafters | skipped: not exact, slower than MTP upstream (PR closed), CLI-only at the time | [S244] |
| **REJECTED** | tree drafting, drafter adapter, next-layer warming, L3 hot set (round 12) | next-layer warming exact but -6.5 % served (its reads compete for the DRAM the CPU pool needs); tree drafting -10 %; drafter adapter ~0.4 %; L3 hot set 0.9 % | [S245] |

### Decode: where experts are served

| status | idea | measured result | src |
|---|---|---|---|
| **ADOPTED** | helper GPU (RTX 4060 Ti, 3,300-expert static cache) | screen decode 154.8 vs 134.5 tok/s with the helper off (+15.1 %, 0.98 ms per token); fixture blend 199.9 vs 180.2 (+10.9 %); prompts ~1 % faster without it | [S246] [S247] |
| **ADOPTED** | helper slot count 3300 | agent-workload screen: 3300 = 138.9 tok/s; 2400 -3.9 %; 1500 -7.3 %; 3500 +0.8 % (noise); 3475 later +2.2 % decode but slower rounds, so 3300 stayed | [S248-S250] |
| **REJECTED** | helper variants: helper cap, upstream --remote-expert-opt, upstream peer tier | cap -6 to -13 %; --remote-expert-opt -17.9 %; --peer-device 1 -14.7 % decode and TTFT +4-7 % | [S251] |
| **ADOPTED** | --pcie-frac auto (PCIe share of missed experts, no longer forced to 0) | research calls + tool-call turns +3.1 %, W1-W3 +2.6 % (ahead 6 of 6), KL and decode-side checks pass; the engine re-prices the share while serving (0.40-0.45 most of the time) | [S252] [S253] |
| **REJECTED** | STRATA_ROUTE_TAIL_SKIP (upstream's skip of low-ranked missed experts; pinned 0) | lossy; on the 5080 alone it reads 131.0 vs 114.9 tok/s (skip on vs off); with a helper GPU it never acts | [S254] [S255] |
| **REJECTED** | --vram-reserve-mib 512 (vs 713, more cache slots) | 4,694 vs 4,586 slots; decode screen -5.0 %, full screen -1.9 %; main GPU free fell to 269-295 MiB, under the 300 MiB floor | [S256] |
| **ADOPTED** | STRATA_ADAPT_LAG=2 + STRATA_DISJOINT_ADAPT=1 (upstream versions of the owner's helper-aware tier) | outputs identical to the owner's own versions (4 of 4), speed equal (decode -1.1 %, agent-workload screen -0.5 %); a helper-aware tier itself was worth +5.3 % on the agent-workload screen | [S257] [S258] |
| **REJECTED** | adaptive-tier tuning: decay 0.8 / 0.9, more swaps, --adapt-swaps 0 | decay +0.4 / +0.7 % (noise); swaps 48 +1.7 % did not repeat; no adaptation -18 % | [S259-S261] |
| **NOT MEASURED** | STRATA_ADAPT_ASYNC / --adapt-async (asynchronous adaptive tier; pinned 0) | the v0.2.7 repeat gate passed 7 of 7 with it; a desk reading says it would not engage on two cards; speed never run | [S262] [S263] |
| **ADOPTED** | STRATA_ADAPT_FETCH=2 beside the helper cache (upstream v0.2.12 admits PCIe-fetched misses into the main cache but is off with a helper GPU; the owner's patch adds a helper-aware pick list) | gap vs P028x + U, 3 passes each: screen decode +12.7 % (noise 3.4 %), conv / struct / prose +9.9 / +5.6 / +4.9 %, screen prompt +0.18 %; main cache's share of routed entries 62.6 -> 67.3 %, CPU 14.4 -> 9.4 % (screen); unset = P028x bitwise (exact7 7/7, long40 0/40); sampled-distribution test and read-back of 91,345 admitted slots pass; =1 +10.2 % (the frozen rule's proposal), =2 vs =1 +2.3 % (noise 3.4 %); by the rule =2 failed one per-workload prompt check (R4-agent33k -0.1 %, noise 0.1 %) and was adopted as a recorded owner exception; adoption check exact7 7/7, pp16k / pp64k level; served since 11-09 20:06; the desk estimate had been about +3 % | [S13] [S115] [S264] [S119] [S144] [S145] [S265] [S118] [S266] |
| **REJECTED** | alternative expert profiles | learned profile (#477) -4.2 % on the agent-workload screen (helper overloaded); make_profile +1.0 / -0.8 % (noise) | [S267] |
| **NOT MEASURED** | STRATA_ROUTE_PRIOR (routing bias toward cached experts) | lossy by design (changes which experts run); upstream 0.2.7 would turn it on for the 4060 Ti; pinned 0 | [S268] |

### Decode: kernels and the window's host work

| status | idea | measured result | src |
|---|---|---|---|
| **ADOPTED** | STRATA_GR_FORK=1 (fork hyper-connection read) | fork off on 0.2.7 / 0.2.8 costs +3.5-3.9 % step time; vs upstream's multi-token read: -6.1 % on the agent-workload screen, +6.0 % per round | [S269] [S270] |
| **ADOPTED** | the v0.2.8 port with GR_FORK and PREFILL_V2 back (P028x vs the earlier P021m) | screen decode +1.03 %, prompt -0.03 %; fixtures 16K -1.9 %, 64K -1.0 % (accepted); exact7 7/7 | [S271] |
| **ADOPTED** | STRATA_ROUTER_Q8K / STRATA_QSA_SPLIT_ATTN / STRATA_MMVQ_IL / STRATA_SIDE_MIXER=2 (round 14) | +1.4 % / +3.0 % / +2.0 % (agent-workload screen) / +2.5 % (decode) | [S272] [S273] |
| **ADOPTED** | STRATA_MMVQ_IL_ROWS (per-layer table tuned on this PC) | re-derived table +0.2 % decode, -1.8 % ms per round | [S274] |
| **ADOPTED** | STRATA_GR_V3=1; the staged hyper-connection read (HC_SPLIT) rejected | v3 +2.7 % vs the older read; the staged read is bitwise identical and -1.4 % | [S275] [S276] |
| **PARKED** | STRATA_GR_V3_PF=133 (v0.2.10) | identity 7/7, decode +2.06 % (noise 5.6 %) | [S277] |
| **REJECTED** | STRATA_POOL_ONE_BATCH=1 (one CPU-pool batch per layer) | exact; screen decode -0.33 %, prompt +0.23 %; one-card timing 25.61 vs 25.65 ms per window | [S278] [S279] |
| **REJECTED** | STRATA_REMOTE_LATE_LAUNCH=1 (helper launches after the CPU pool starts), alone and with ONE_BATCH | exact; decode -1.03 % alone; both together +0.88 % decode but a 64K-prompt loss; two-card timing 22.15 vs 22.01 ms per window | [S280-S282] |
| **REJECTED** | DF_PDL / IQ_GATHER / GRAPH_PRIO / FUSE_WAIT=2 (gap 18) | exact7 7/7 each; decode +0.15 / +0.80 / -0.06 / -0.87 %, all four +0.20 % (noise 2.6-3.9 %) | [S283] |
| **REJECTED** | DF_PLE (gap 7) | decode -2.2 % and the main GPU's free VRAM fell to 25 MiB | [S284] |
| **DESK ONLY** | GPU-side MoE planning (G4), one-graph draft chain (G6) | bounds ~0.15 ms (0.6 %) and 0.1-0.17 ms per window: not written | [S285] |
| **NOT MEASURED** | PCIe groups beside the VRAM hits (P1), L2 prefetch of the next layer (G5a), helper rows written in place (H2) | P1: 0.98 ms per window of GPU overhang, 0.44 ms of PCIe groups (two-card pass); G5a needs a probe; H2's copy measured 0.108 ms per window, under the 0.15 ms bar | [S286-S288] |
| **REJECTED** | transparent huge pages for the expert arena (#650) | +0.01 %; makes CPU-pool time bimodal run to run | [S289] [S290] |
| **REJECTED** | IQ_GATHER / IQ_PREFETCH / n-gram prefetch | no gain | [S291] [S292] |

### Serving, caches, batching

| status | idea | measured result | src |
|---|---|---|---|
| **ADOPTED** | the owner's chat cache (--chat-cache 16, 12 GiB of RAM) | same return times as the alternative (0.36-0.75 s), switching 0.06-0.18 s faster, exact; parking a 54K conversation takes 100-139 ms | [S293] [S294] |
| **REJECTED** | upstream 0.2.3's automatic conversation cache (--conversation-cache-mib 0) | screen prompt -6.8 %, decode -0.2 %; it parks synchronously (40-47 ms on short turns, 126 ms before an agent turn) | [S295] [S296] |
| **REJECTED** | --batch 4 / --batch-mtp (several requests at once) | 4 agent turns at once: 59.8 tok/s one at a time vs 58.4 / 61.1 batched; one request with batch slots allocated -12 % (138 -> 122); the main cache falls from 4,585 to 2,781 slots | [S297] [S298] |
| **REJECTED** | two requests in one verify window (round 12) | pairs finish 20 % later (the slots decode without drafts) | [S299] |
| **ADOPTED** | picture reader on the CPU (not the 4060 Ti) | the GPU reader on the helper costs 1-2 % decode; the CPU reader costs ~2 cache slots | [S300] [S301] |

### Quantization

| status | idea | measured result | src |
|---|---|---|---|
| **ADOPTED** | IQ3_S GSQ-RCO (ISTA-DASLab, the served GGUF) | vs a Q8_0 reference over 4,995 positions: top-1 87.43 %, KL 0.144 | [S302] |
| **REJECTED** | NVFP4 (GPTQ pack) and FP4-Local | decode ~100 vs 143 tok/s; TTFT at 32K 9.3 vs 7.7 s; top-1 vs Q8_0 91.7 / 91.2 %; task suite level with IQ3_S (94.3 vs 94.5 at medium effort) | [S303] |
| **REJECTED** | Unsloth UD-Q4_K_XL (kept as the KL reference) | best measured fidelity (top-1 92.37 %, KL 0.059; long-text NLL -0.35 nats vs IQ3_S) but decode 68.7 vs 138.8 tok/s (-51 %, round 16) | [S304-S306] |
| **REJECTED** | Unsloth v3.1 UD-IQ3_XXS, and its experts spliced into the IQ3_S file | KL vs UD-Q4_K_XL: served 0.717, UD-IQ3_XXS 0.734, splice 0.889 (worse); decode +1.95 % / +3.01 %, no loss; not adopted | [S307] [S308] |
| **REJECTED** | splice of IQ3_S experts with UD-Q4_K_XL's other tensors | long-text -0.053 nats, only 15 % of the Q4 file's -0.350 | [S309] |
| **REJECTED** | higher-precision side paths (BF16 token embedding, BF16x2 prompt math, RoPE table) | BF16 embedding worse on long texts (+0.08 / +0.10 nats); BF16x2 TTFT 120K +10 %; RoPE table no change; none adopted | [S310] |

### Engines, ports and settings

| status | idea | measured result | src |
|---|---|---|---|
| **REJECTED** | Basalt 0.2.0 (another engine) at its defaults vs P028x | fixture blend +9.5 % (217.2 vs 198.4), 16K prompt +32.3 %, 64K +24.1 %, screen decode +2.8 % (within spread), prompt +15.3 %; not lossless (int8 hyper-connection copy, two-stage head always on) | [S311] |
| **REJECTED** | Basalt made lossless + the helper GPU (estimate) | exact head -3.0 % (156.7 vs 161.5); estimate +13.0 % (+6.2..+17.6 %) over P028x; no local Basalt branch | [S312] [S313] |
| **REJECTED** | Basalt's two-stage Q6_K head | 2.2 % of verify rows have a wrong top-20 where its per-window cap binds; gain +0.7 % (noise) | [S314] |
| **INFO** | value of the patch series over stock Strata (v0.2.1, 10-21) | decode +9.8 %, prompt +8 % | [S315] |
| **REJECTED** | the v0.2.10 port (gap 17) | screen decode -0.87 %; fixtures struct -2.4 %, blend -2.5 %: no gain | [S316] |
| **PARKED** | the v0.2.11 port (base for the Qwen4 port; not served) | exact7 7/7 vs P028x; screen decode +1.34 %, prompt +0.55 %; failed per-workload no-loss on R3 prompt -1.4 % (the chat-cache park inside the timer); passed the 11-09 confirmation gap (R3 with the chat cache off +0.20 %) | [S317-S319] |
| **INFO** | upstream v0.2.7 paths without the patch series vs the then-served build | decode -7.5 %, prompt -5 % | [S320] |
| **ADOPTED** | STRATA_DEFAULTS=026 (0.2.7's new per-card defaults pinned off: GR_UP_WIDE, MMVQ_IL_89, English draft vocabulary, ...) | the new defaults were never measured one by one | [S321] |
| **ADOPTED** | reasoning effort "medium" by default | task suite: medium 94.5, xhigh 90.7, low 91.4; medium takes about a third of xhigh's time | [S322] |
| **NOT MEASURED** | KV formats other than int8; --kv-resident sizes | no A/B of KV formats on this engine; --kv-resident 16384 was +1.2 % (within spread) in one round | [S323] |
| **INFO** | RAM at 6200 vs 6000 MT/s | 6200 MT/s was unstable (memtest errors); all numbers since 10-10 are at 6000 MT/s (76.6 GB/s); no clean speed pair | [S324] |
| **NOT MEASURED** | Infernix (another engine's ideas: frame pools, prefix cache tiers, BF16-activation arithmetic) | not reviewed; desk check: its per-size frame pools would add no experts here | [S325] [S326] |
| **NOT MEASURED** | Strata's own tuner (strata tune auto) | planned, never run | [S327] |

Totals: ADOPTED 27, DESK ONLY 1, INFO 5, NOT MEASURED 8, PARKED 4, REJECTED 36.

## 10. What these files only approximate (measure on release day)

1. **Decode speed at 16K context** - no decode of >= 256 tokens after a ~16,384-token prompt in the inputs; the pack shows the nearest: R1-verify20k at 24,238, W3-research at 26,728.
2. **Decode speed at 64K context** - no decode of >= 256 tokens after a ~65,536-token prompt in the inputs; the pack shows the nearest: R2-report54k at 54,070.
3. **MTP acceptance per draft position** - no log has STRATA_SPEC_DEPTH=1 lines; only per-request totals exist.
4. **The engine's own swap (VmSwap) per run** - the monitors record system swap only; the owner's swap rule is about the engine's VmSwap.
5. **Decode-timing split on the served form** - the timing pass lacks STRATA_ADAPT_FETCH, STRATA_HC_UPMIX.
6. **Short-prompt reading speed on fixed fixtures** - today's short-prompt figures are screen workloads (1.4K-5K-token prompts with chat formatting and tool schemas, one request per pass); add pp1k / pp4k cold fixtures, 3 passes.
7. **Prompt fixtures with 3 passes on the served build** - today's current-build pp16k / pp64k ran 1 pass (the adoption check); the 3-pass figures are from the P028x engine before the fetch patch; run 3 passes of every fixture.
8. **Prompt speed at 128K** - nothing above a 66,617-token prompt on the served form; the exactness run's 112K prompt used a pinned smaller cache.
9. **Expert placement on the new model** - today's main placement figure is the 9-workload screen; long served traffic exists only for the P028x engine before the fetch patch (the current build has one evening and one morning); on day one only the screen and fixtures exist, so report the screen figure and say so.
10. **Helper GPU memory over time** - only the guard's minimum free (one value per run); the helper's own use is flat by design but not sampled.
11. **Per-position MTP acceptance at the served sampling** - take it on the screen at T 1.0 with thinking on, not on the decode fixtures (T 0.6 / 0.0).

## Appendix A. Sources

- **S1** `models/ISTA-GSQ-RCO/IQ3_S/Qwen3.8-Flash-Next-GSQ-RCO-IQ3_S-00001-of-00002.gguf` - GGUF header (metadata + tensor table; weights not read)
- **S2** `models/ISTA-GSQ-RCO/IQ3_S/Qwen3.8-Flash-Next-GSQ-RCO-IQ3_S-00002-of-00002.gguf` - GGUF header (metadata + tensor table; weights not read)
- **S3** `notes/pc-hardware.md:8-12,20`
- **S4** `configs/P028x.json:46` - config
- **S5** `engine-r23afetch/SOURCE:1` - engine SOURCE
- **S6** `engine-r23afetch/SHA256:1` - engine SHA256
- **S7** `results/r23/afetch-adopt/englog/r23aa11091954-S2-decode.englog:38`
- **S8** `results/r23/afetch-adopt/englog/r23aa11091954-S2-decode.englog:15`
- **S9** `configs/P028x.json:58` - cited in the text
- **S10** `results/r23/ADAPTFETCH-DESK-1109.md:12-14` - cited in the text
- **S11** `results/r23/ADAPTFETCH-DESK-1109.md:37-58` - cited in the text
- **S12** `strata-r22p028x/serve/server.py:7341` - cited in the text
- **S13** `results/r23/adaptfetch/gap/decision.txt:3` - cited in the text; already-tried source
- **S14** `results/r23/ADAPTFETCH-DESK-1109.md:53-57` - cited in the text
- **S15** `results/r23/adaptfetch/gap/decision.txt:14-16` - cited in the text
- **S16** `results/r23/ADAPTFETCH-DESK-1109.md:102-103` - cited in the text
- **S17** `results/r23/afetch-adopt/summary.txt:55` - cited in the text
- **S18** `configs/P028x.json:2` - cited in the text
- **S19** `configs/P028x.json` - served config
- **S20** `configs/P028x.json:75`
- **S21** `configs/P028x.json:51`
- **S22** `notes/sampling-settings-everywhere.md:11` - cited in the text
- **S23** `results/r23/adaptfetch/gap/decision.txt:1` - cited in the text
- **S24** `results/r23/adaptfetch/gap/configs/F2.json` - F2 (gap arm) config
- **S25** `results/r23/afetch-adopt/S2.json` - S2 (adoption check) config
- **S26** `results/r23/adaptfetch/gap/configs/P.json` - P (gap reference) config
- **S27** `results/r23/adaptfetch/gap/speed/F21a.jsonl:2` - prompt speed; speed record
- **S28** `results/r23/adaptfetch/gap/speed/F22a.jsonl:2` - prompt speed; speed record
- **S29** `results/r23/adaptfetch/gap/speed/F23a.jsonl:2` - prompt speed; speed record
- **S30** `results/r23/adaptfetch/gap/speed/F21a.jsonl:1` - prompt speed; speed record
- **S31** `results/r23/adaptfetch/gap/speed/F22a.jsonl:1` - prompt speed; speed record
- **S32** `results/r23/adaptfetch/gap/speed/F23a.jsonl:1` - prompt speed; speed record
- **S33** `results/r23/adaptfetch/gap/speed/F21r.jsonl:3` - prompt speed; speed record
- **S34** `results/r23/adaptfetch/gap/speed/F22r.jsonl:3` - prompt speed; speed record
- **S35** `results/r23/adaptfetch/gap/speed/F23r.jsonl:3` - prompt speed; speed record
- **S36** `results/r23/afetch-adopt/bp90/S2-pp16k-1.jsonl:1` - prompt speed; decode after the prompt fixture; speed record
- **S37** `results/r23/afetch-adopt/bp90/S2-pp64k-1.jsonl:1` - prompt speed; speed record
- **S38** `results/r23/adaptfetch/gap/speed/F21n.jsonl:1` - decode speed; speed record
- **S39** `results/r23/adaptfetch/gap/speed/F22n.jsonl:1` - decode speed; speed record
- **S40** `results/r23/adaptfetch/gap/speed/F23n.jsonl:1` - decode speed; speed record
- **S41** `results/r23/adaptfetch/gap/speed/F21n.jsonl:2` - decode speed; speed record
- **S42** `results/r23/adaptfetch/gap/speed/F22n.jsonl:2` - decode speed; speed record
- **S43** `results/r23/adaptfetch/gap/speed/F23n.jsonl:2` - decode speed; speed record
- **S44** `results/r23/adaptfetch/gap/bp90/F2-decode-1.jsonl:1` - decode speed; speed record
- **S45** `results/r23/adaptfetch/gap/bp90/F2-decode-2.jsonl:1` - decode speed; speed record
- **S46** `results/r23/adaptfetch/gap/bp90/F2-decode-3.jsonl:1` - decode speed; speed record
- **S47** `results/r23/afetch-adopt/bp90/S2-decode-1.jsonl:1` - decode speed; speed record
- **S48** `results/r23/adaptfetch/gap/bp90/F2-decode-1.jsonl:3` - decode speed; speed record
- **S49** `results/r23/adaptfetch/gap/bp90/F2-decode-2.jsonl:3` - decode speed; speed record
- **S50** `results/r23/adaptfetch/gap/bp90/F2-decode-3.jsonl:3` - decode speed; speed record
- **S51** `results/r23/afetch-adopt/bp90/S2-decode-1.jsonl:3` - decode speed; speed record
- **S52** `results/r23/adaptfetch/gap/bp90/F2-decode-1.jsonl:2` - decode speed; speed record
- **S53** `results/r23/adaptfetch/gap/bp90/F2-decode-2.jsonl:2` - decode speed; speed record
- **S54** `results/r23/adaptfetch/gap/bp90/F2-decode-3.jsonl:2` - decode speed; speed record
- **S55** `results/r23/afetch-adopt/bp90/S2-decode-1.jsonl:2` - decode speed; speed record
- **S56** `results/r23/adaptfetch/gap/speed/F21r.jsonl:1` - decode speed; speed record; cited in the text
- **S57** `results/r23/adaptfetch/gap/speed/F22r.jsonl:1` - decode speed; speed record
- **S58** `results/r23/adaptfetch/gap/speed/F23r.jsonl:1` - decode speed; speed record
- **S59** `results/r23/adaptfetch/gap/speed/F21n.jsonl:3` - decode speed; speed record
- **S60** `results/r23/adaptfetch/gap/speed/F22n.jsonl:3` - decode speed; speed record
- **S61** `results/r23/adaptfetch/gap/speed/F23n.jsonl:3` - decode speed; speed record
- **S62** `results/r23/adaptfetch/gap/speed/F21r.jsonl:2` - decode speed; speed record
- **S63** `results/r23/adaptfetch/gap/speed/F22r.jsonl:2` - decode speed; speed record
- **S64** `results/r23/adaptfetch/gap/speed/F23r.jsonl:2` - decode speed; speed record
- **S65** `results/r23/adaptfetch/gap/speed/F21r.jsonl:4` - speed record
- **S66** `results/r23/adaptfetch/gap/speed/F22r.jsonl:4` - speed record
- **S67** `results/r23/adaptfetch/gap/speed/F23r.jsonl:4` - speed record
- **S68** `results/r23/adaptfetch/gap/bp90/P-decode-1.jsonl:3` - speed record
- **S69** `results/r23/adaptfetch/gap/bp90/P-decode-2.jsonl:3` - speed record
- **S70** `results/r23/adaptfetch/gap/bp90/P-decode-3.jsonl:3` - speed record
- **S71** `results/r23/adaptfetch/gap/bp90/P-decode-1.jsonl:1` - speed record
- **S72** `results/r23/adaptfetch/gap/bp90/P-decode-2.jsonl:1` - speed record
- **S73** `results/r23/adaptfetch/gap/bp90/P-decode-3.jsonl:1` - speed record
- **S74** `results/r23/adaptfetch/gap/bp90/P-decode-1.jsonl:2` - speed record
- **S75** `results/r23/adaptfetch/gap/bp90/P-decode-2.jsonl:2` - speed record
- **S76** `results/r23/adaptfetch/gap/bp90/P-decode-3.jsonl:2` - speed record
- **S77** `results/r23/adaptfetch/gap/speed/P1n.jsonl:1` - speed record
- **S78** `results/r23/adaptfetch/gap/speed/P2n.jsonl:1` - speed record
- **S79** `results/r23/adaptfetch/gap/speed/P3n.jsonl:1` - speed record
- **S80** `results/r23/adaptfetch/gap/speed/P1n.jsonl:2` - speed record
- **S81** `results/r23/adaptfetch/gap/speed/P2n.jsonl:2` - speed record
- **S82** `results/r23/adaptfetch/gap/speed/P3n.jsonl:2` - speed record
- **S83** `results/r23/adaptfetch/gap/speed/P1a.jsonl:2` - speed record
- **S84** `results/r23/adaptfetch/gap/speed/P2a.jsonl:2` - speed record
- **S85** `results/r23/adaptfetch/gap/speed/P3a.jsonl:2` - speed record
- **S86** `results/r23/adaptfetch/gap/speed/P1a.jsonl:1` - speed record
- **S87** `results/r23/adaptfetch/gap/speed/P2a.jsonl:1` - speed record
- **S88** `results/r23/adaptfetch/gap/speed/P3a.jsonl:1` - speed record
- **S89** `results/r23/adaptfetch/gap/speed/P1r.jsonl:3` - speed record
- **S90** `results/r23/adaptfetch/gap/speed/P2r.jsonl:3` - speed record
- **S91** `results/r23/adaptfetch/gap/speed/P3r.jsonl:3` - speed record
- **S92** `results/r23/adaptfetch/gap/speed/P1r.jsonl:1` - speed record
- **S93** `results/r23/adaptfetch/gap/speed/P2r.jsonl:1` - speed record
- **S94** `results/r23/adaptfetch/gap/speed/P3r.jsonl:1` - speed record
- **S95** `results/r23/adaptfetch/gap/speed/P1n.jsonl:3` - speed record
- **S96** `results/r23/adaptfetch/gap/speed/P2n.jsonl:3` - speed record
- **S97** `results/r23/adaptfetch/gap/speed/P3n.jsonl:3` - speed record
- **S98** `results/r23/adaptfetch/gap/speed/P1r.jsonl:4` - speed record
- **S99** `results/r23/adaptfetch/gap/speed/P2r.jsonl:4` - speed record
- **S100** `results/r23/adaptfetch/gap/speed/P3r.jsonl:4` - speed record
- **S101** `results/r23/adaptfetch/gap/speed/P1r.jsonl:2` - speed record
- **S102** `results/r23/adaptfetch/gap/speed/P2r.jsonl:2` - speed record
- **S103** `results/r23/adaptfetch/gap/speed/P3r.jsonl:2` - speed record
- **S104** `results/r23/basalt-prompt/gap-speed/bp90/PU-pp16k-1.jsonl:1` - speed record
- **S105** `results/r23/basalt-prompt/gap-speed/bp90/PU-pp16k-2.jsonl:1` - speed record
- **S106** `results/r23/basalt-prompt/gap-speed/bp90/PU-pp16k-3.jsonl:1` - speed record
- **S107** `results/r23/basalt-prompt/gap-speed/bp90/PU-pp64k-1.jsonl:1` - speed record
- **S108** `results/r23/basalt-prompt/gap-speed/bp90/PU-pp64k-2.jsonl:1` - speed record
- **S109** `results/r23/basalt-prompt/gap-speed/bp90/PU-pp64k-3.jsonl:1` - speed record
- **S110** `results/r23/adaptfetch/gap/speed/F21n.englog:3-10` - cited in the text
- **S111** `results/r23/adaptfetch/gap/speed/F21r.englog:2-9` - cited in the text
- **S112** `results/r23/adaptfetch/gap/decision.txt:13` - cited in the text; ADAPT_FETCH gap, F2 (=2, the current build) vs P (the P028x engine before the fetch patch), 3 passes each
- **S113** `results/r23/basalt-prompt/gap-speed/decision.txt:9` - cited in the text; already-tried source
- **S114** `results/r23/afetch-adopt/summary.txt:74-75` - cited in the text
- **S115** `results/r23/adaptfetch/gap/decision.txt:4-5` - cited in the text; already-tried source
- **S116** `results/r23/adaptfetch/gap/decision.txt:12-13` - cited in the text
- **S117** `results/r23/adaptfetch/OWNER-EXCEPTION-1109.md:28-35` - cited in the text
- **S118** `results/r23/afetch-adopt/result.txt:1` - cited in the text; already-tried source
- **S119** `results/r23/adaptfetch/gap/decision.txt:25` - Same gap, =2 vs =1; already-tried source
- **S120** `results/r23/afetch-adopt/summary.txt:74` - Adoption check on the served config (11-09 20:02-20:05), pp16k; in these quoted lines 'this morning's PU' = set PU, 'this morning's P' = the same engine without U (not set P), 'the U adoption's check' = one pass on the same engine with U at 11:35
- **S121** `results/r23/afetch-adopt/summary.txt:75` - Adoption check, pp64k
- **S122** `results/r23/afetch-adopt/summary.txt:76` - Adoption check, decode ('gap P' = set P, 'gap F2' = the gap's three F2 passes)
- **S123** `results/r23/adaptfetch/gap/englog/scr-F21.englog:1-161` - screen F2, current build (ADAPT_FETCH gap, 3 passes, one warm-up request each) (per-request lines in this range)
- **S124** `results/r23/adaptfetch/gap/englog/scr-F22.englog:1-159` - screen F2, current build (ADAPT_FETCH gap, 3 passes, one warm-up request each) (per-request lines in this range)
- **S125** `results/r23/adaptfetch/gap/englog/scr-F23.englog:1-160` - screen F2, current build (ADAPT_FETCH gap, 3 passes, one warm-up request each) (per-request lines in this range)
- **S126** `results/r23/adaptfetch/gap/englog/bp-F2-decode-1.englog:1-92` - decode fixtures F2, current build (conv / struct / prose x3) (per-request lines in this range)
- **S127** `results/r23/adaptfetch/gap/englog/bp-F2-decode-2.englog:1-92` - decode fixtures F2, current build (conv / struct / prose x3) (per-request lines in this range)
- **S128** `results/r23/adaptfetch/gap/englog/bp-F2-decode-3.englog:1-91` - decode fixtures F2, current build (conv / struct / prose x3) (per-request lines in this range)
- **S129** `logs/engine-P028x.log:238213-238673` - served log on the current build, 11-09 20:06 - 11-10 (4 engine starts) (per-request lines in this range)
- **S130** `results/r23/adaptfetch/gap/englog/scr-P1.englog:1-148` - screen P, the P028x engine before the fetch patch (same gap, 3 passes, one warm-up request each) (per-request lines in this range)
- **S131** `results/r23/adaptfetch/gap/englog/scr-P2.englog:1-147` - screen P, the P028x engine before the fetch patch (same gap, 3 passes, one warm-up request each) (per-request lines in this range)
- **S132** `results/r23/adaptfetch/gap/englog/scr-P3.englog:1-147` - screen P, the P028x engine before the fetch patch (same gap, 3 passes, one warm-up request each) (per-request lines in this range)
- **S133** `results/r23/adaptfetch/gap/englog/bp-P-decode-1.englog:1-88` - decode fixtures P, the P028x engine before the fetch patch (same gap) (per-request lines in this range)
- **S134** `results/r23/adaptfetch/gap/englog/bp-P-decode-2.englog:1-88` - decode fixtures P, the P028x engine before the fetch patch (same gap) (per-request lines in this range)
- **S135** `results/r23/adaptfetch/gap/englog/bp-P-decode-3.englog:1-88` - decode fixtures P, the P028x engine before the fetch patch (same gap) (per-request lines in this range)
- **S136** `logs/engine-P028x.log:1-237843` - served log 10-30 16:55 - 11-09 11:39, the P028x engine before the fetch patch (103 engine starts) (per-request lines in this range)
- **S137** `results/r23/decode-timing/t2/engine-T2dv.log:1-172` - decode-timing pass T2dv (11-05, the P028x engine before the fetch patch, without U) (per-request lines in this range)
- **S138** `results/r23/afetch-adopt/englog/r23aa11091954-S2-decode.englog:29`
- **S139** `results/r23/afetch-adopt/englog/r23aa11091954-S2-decode.englog:35`
- **S140** `results/r23/afetch-adopt/englog/r23aa11091954-S2-decode.englog:29,35`
- **S141** `logs/engine-P028x.log:238308,238516-238518` - PCIe share re-pricing lines
- **S142** `logs/engine-P028x.log:80-81,4270,13046,14709,15716,16056,16066,22498,24045,27209,28937,28952,29633,33662,34466,35658,36820,38919,38942,40253,41316,43484,44487,45189,46834,49219,49705,51496,51516,52476,57147,57722,61375,62748,66027,67841,70247,70250,74648,75823,75843,76781,79518,81294,86250-86251,89442,90959,90962,93630,93650,94780,98342,103095,104560-104561,107214,108991,109457,112197,113784,114290,116204,116207,121575,121578,125855,126793,131632,136073-136075,139752,143754,147642,148453-148455,152123,153539,159050,159053,162454,162457,166449-166450,166457,170164,171397,183917,185616,187134,187438,188324,188785,188890,192144-192145,193281,193972,193975-193976,196800,196814,201163,201876-201878,204097,206469,206497,208530,208550,210148,224672,224675,232971,234030,236018,237115` - PCIe share re-pricing lines
- **S143** `results/r23/afetch-adopt/englog/r23aa11091954-S2-decode.englog:47` - cited in the text
- **S144** `results/r23/adaptfetch/gap/fetchstats.txt:5` - cited in the text; The gap's own count, screen F2 (cross-check of the first row); already-tried source
- **S145** `results/r23/adaptfetch/gap/fetchstats.txt:9` - cited in the text; The gap's own count, screen P (the P028x engine before the fetch patch); already-tried source
- **S146** `results/r23/ADAPTFETCH-DESK-1109.md:21-30` - cited in the text
- **S147** `results/r23/ADAPTFETCH-DESK-1109.md:53-55` - cited in the text
- **S148** `logs/engine-P028x.log:238315` - cited in the text
- **S149** `logs/engine-P028x.log:238519` - cited in the text
- **S150** `logs/engine-P028x.log:238527` - cited in the text
- **S151** `logs/engine-P028x.log:238576` - cited in the text
- **S152** `results/r23/ADAPTFETCH-DESK-1109.md:84` - cited in the text
- **S153** `results/r23/adaptfetch/gap/fetchstats.txt:4` - The gap's own count, decode fixtures F2
- **S154** `results/r23/adaptfetch/gap/fetchstats.txt:8` - The gap's own count, decode fixtures P (the P028x engine before the fetch patch)
- **S155** `results/r23/ADAPTFETCH-DESK-1109.md:78` - The earlier desk study's figure from the ten-day served log (the P028x engine before the fetch patch; cross-check)
- **S156** `results/r23/afetch-adopt/englog/r23aa11091954-S2-decode.englog:52` - cited in the text
- **S157** `results/r23/decode-timing/t2/report-T2dv.txt:1` - Decode-timing pass (11-05, the P028x engine before the fetch patch): mean verify-window width T and tokens per window (tok/w); decode timing: window split
- **S158** `results/r23/afetch-adopt/englog/r23aa11091954-S2-decode.englog` - engine start lines of one start of the measured form
- **S159** `bringup/out/logs/server_r23af11091734-bpF2-1_20261109T175410.log:166` - server guard summary line
- **S160** `bringup/out/logs/server_r23af11091734-bpF2-2_20261109T175547.log:166` - server guard summary line
- **S161** `bringup/out/logs/server_r23af11091734-bpF2-3_20261109T180221.log:166` - server guard summary line
- **S162** `bringup/out/logs/server_r23af11091734-scrF21_20261109T181300.log:251` - server guard summary line
- **S163** `bringup/out/logs/server_r23af11091734-scrF22_20261109T181619.log:268` - server guard summary line
- **S164** `bringup/out/logs/server_r23af11091734-scrF23_20261109T183038.log:268` - server guard summary line
- **S165** `bringup/out/logs/server_r23aa11091954-S2-decode_20261109T200357.log:165` - server guard summary line
- **S166** `bringup/out/logs/server_r23aa11091954-S2-pp16k_20261109T200154.log:121` - server guard summary line
- **S167** `bringup/out/logs/server_r23aa11091954-S2-pp64k_20261109T200250.log:124` - server guard summary line
- **S168** `bringup/out/logs/monitor-r23af11091734-bpF2-1.sys.csv:2-96` - 1-s monitor samples
- **S169** `bringup/out/logs/monitor-r23af11091734-bpF2-2.sys.csv:2-95` - 1-s monitor samples
- **S170** `bringup/out/logs/monitor-r23af11091734-bpF2-3.sys.csv:2-96` - 1-s monitor samples
- **S171** `bringup/out/logs/monitor-r23af11091734-scrF21.sys.csv:2-196` - 1-s monitor samples
- **S172** `bringup/out/logs/monitor-r23af11091734-scrF22.sys.csv:2-212` - 1-s monitor samples
- **S173** `bringup/out/logs/monitor-r23af11091734-scrF23.sys.csv:2-213` - 1-s monitor samples
- **S174** `bringup/out/logs/monitor-r23aa11091954-S2-decode.sys.csv:2-96` - 1-s monitor samples
- **S175** `bringup/out/logs/monitor-r23aa11091954-S2-pp16k.sys.csv:2-54` - 1-s monitor samples
- **S176** `bringup/out/logs/monitor-r23aa11091954-S2-pp64k.sys.csv:2-64` - 1-s monitor samples
- **S177** `results/r23/afetch-adopt/summary.txt:10` - RAM available with no engine loaded (before the adoption check)
- **S178** `results/r23/adaptfetch/gap/summary.txt:54` - The 40-long-prompt exactness run on the fetch build with the switch unset (one engine, its own cache setting; read it for RAM and swap)
- **S179** `results/r23/adaptfetch/gap/summary.txt:398` - Restart of the served engine after the gap (still the P028x engine before the fetch patch)
- **S180** `results/r23/afetch-adopt/summary.txt:81` - Restart of the served engine on the current build after the adoption check
- **S181** `logs/engine-P028x.log:238276,238391,238484,238652` - low-VRAM warnings
- **S182** `logs/engine-P028x.log:68,4258,13034,14685,15723,16034,22486,24054,27195,28925,29609,33669,34452,35646,36827,38909,40241,41302,43470,44494,45175,46820,49207,49691,51484,52464,57133,57708,61363,62736,66013,67829,70049,70138,70225,74634,75809,76767,79525,81284,86238,89430,90947,93618,94766,98328,103083,104360,104449,104536,107200,108977,109433,112183,113772,114268,116008,116095,116182,121553,125843,126769,131608,136049,139728,143730,147632,148429,152111,153515,159028,162343,162432,166425,170152,171373,183893,185592,187112,187414,188300,188763,188866,192152,193267,193950,196786,201151,201852,204069,206457,208518,210126,224660,232959,234043,236006,237124,237471,237558,237645,237730,237824` - low-VRAM warnings
- **S183** `bringup/lib/guard.py:7-8` - cited in the text
- **S184** `notes/memavailable-floor.md:8` - cited in the text
- **S185** `notes/kernel-oops-pinned-memory.md:51` - cited in the text
- **S186** `notes/memavailable-floor.md:29-30` - cited in the text
- **S187** `results/r23/ADAPTFETCH-DESK-1109.md:58` - cited in the text
- **S188** `results/r23/decode-timing/t2/report-T2dv.txt:2`
- **S189** `results/r23/decode-timing/t2/report-T2dv.txt:3`
- **S190** `results/r23/decode-timing/t2/report-T2dv.txt:4`
- **S191** `results/r23/decode-timing/t2/report-T2dv.txt:6-19` - GPU stage table
- **S192** `results/r23/decode-timing/x28h-t2dv.json` - timing config
- **S193** `results/r23/decode-timing/ANALYSIS.md:174-176` - cited in the text
- **S194** `results/r23/decode-timing/ANALYSIS.md:11-14` - cited in the text
- **S195** `results/r23/decode-timing/ANALYSIS.md:15-17` - cited in the text
- **S196** `results/r23/decode-timing/ANALYSIS.md:89-90` - cited in the text
- **S197** `results/r23/decode-timing/t2/summary.txt:4` - Timing pass (11-05, the P028x engine before the fetch patch), W1-think (client decode speed under the profiler)
- **S198** `results/r23/decode-timing/t2/summary.txt:10` - Timing pass, R2-report54k
- **S199** `results/r23/decode-timing/gap-a/decision.txt:14` - Cross-check: the two-card base arm of the 11-05 decode-timing gate (the P028x engine before the fetch patch; host split only, no GPU profile)
- **S200** `results/r23/basalt-prompt/gap-speed/decision.txt:4` - already-tried source
- **S201** `results/r23/u-adopt/result.txt:1` - already-tried source
- **S202** `results/r23/basalt-prompt/gap-speed/decision.txt:6` - already-tried source
- **S203** `results/r23/basalt-prompt/gap-speed/decision.txt:11` - already-tried source
- **S204** `results/r23/basalt-prompt/gap-speed/decision.txt:5` - already-tried source
- **S205** `results/r23/basalt-prompt/gap-speed/decision.txt:8` - already-tried source
- **S206** `results/BACKLOG-1027.md:220-228` - already-tried source
- **S207** `results/r23/basalt-prompt/gap-b/decision-b.txt:5-6` - already-tried source
- **S208** `results/r22/gap17/decision.txt:16-21` - already-tried source
- **S209** `results/r22/gap19/decision.txt:11-13` - already-tried source
- **S210** `results/r23/decpath/decision.txt:18-24` - already-tried source
- **S211** `results/r23/decpath/decision.txt:70` - already-tried source
- **S212** `NOTES.md:3014-3016` - already-tried source
- **S213** `NOTES.md:4177-4178` - already-tried source
- **S214** `NOTES.md:5285` - already-tried source
- **S215** `NOTES.md:4190-4191` - already-tried source
- **S216** `notes/strata-sampler-share-findings.md:22-24` - already-tried source
- **S217** `results/r23/decpath/decision.txt:68-69` - already-tried source
- **S218** `NOTES.md:3019-3025` - already-tried source
- **S219** `results/r22/gap8/dec-K.md:3` - already-tried source
- **S220** `results/r22/gap8/ttft-K.md:3-6` - already-tried source
- **S221** `results/r22/gap16/gates.txt:10-12` - already-tried source
- **S222** `results/r22/gap7/ttft-flags.md:3-6` - already-tried source
- **S223** `results/r22/gap7/ttft-flags.md:9-12` - already-tried source
- **S224** `results/r22/gap9/imma.txt:10` - already-tried source
- **S225** `results/r22/gap7/ttft-flags.md:15-18` - already-tried source
- **S226** `results/PORT-V027-PLAN.md:30-35` - already-tried source
- **S227** `NOTES.md:1606-1618` - already-tried source
- **S228** `results/r22/gap8/cvsa-verdict.txt:7` - already-tried source
- **S229** `NOTES.md:8072` - already-tried source
- **S230** `../basalt-ab/PLAN.md:134-135` - already-tried source
- **S231** `NOTES.md:2388-2392` - already-tried source
- **S232** `NOTES.md:5286` - already-tried source
- **S233** `NOTES.md:5248-5251` - already-tried source
- **S234** `notes/strata-sampler-share-findings.md:25` - already-tried source
- **S235** `NOTES.md:5211` - already-tried source
- **S236** `notes/strata-sampler-share-findings.md:13-16` - already-tried source
- **S237** `notes/strata-sampler-share-findings.md:35` - already-tried source
- **S238** `results/r22/port-027.md:100-110` - already-tried source
- **S239** `results/BACKLOG-1027.md:77` - already-tried source
- **S240** `NOTES.md:3230-3234` - already-tried source
- **S241** `NOTES.md:3299-3301` - already-tried source
- **S242** `results/r22/gap17/decision.txt:42-51` - already-tried source
- **S243** `../basalt-ab/PLAN.md:109-111` - already-tried source
- **S244** `notes/basalt-ab-results.md:30` - already-tried source
- **S245** `results/round12-summary.md:9-12` - already-tried source
- **S246** `../basalt-020/results/followup-decision.md:9-10` - already-tried source
- **S247** `../basalt-020/results/followup-decision.md:17` - already-tried source
- **S248** `NOTES.md:4107-4114` - already-tried source
- **S249** `NOTES.md:4158` - already-tried source
- **S250** `NOTES.md:5282` - already-tried source
- **S251** `NOTES.md:4158-4160` - already-tried source
- **S252** `notes/pcie-frac-later-test.md:16-20` - already-tried source
- **S253** `results/r22/gap9/pcie-speed.txt:3` - already-tried source
- **S254** `NOTES.md:6135` - already-tried source
- **S255** `notes/tail-skip-off-single-gpu.md:14-20` - already-tried source
- **S256** `NOTES.md:7761-7768` - already-tried source
- **S257** `NOTES.md:5208` - already-tried source
- **S258** `NOTES.md:5229-5230` - already-tried source
- **S259** `NOTES.md:3185-3187` - already-tried source
- **S260** `NOTES.md:98` - already-tried source
- **S261** `NOTES.md:5746` - already-tried source
- **S262** `results/r22/port-027.md:96` - already-tried source
- **S263** `results/r22/switch-diag/decode-loss.md:150` - already-tried source
- **S264** `results/r23/adaptfetch/gap/decision.txt:12-18` - already-tried source
- **S265** `results/r23/adaptfetch/OWNER-EXCEPTION-1109.md:26-35` - already-tried source
- **S266** `results/r23/ADAPTFETCH-DESK-1109.md:88-93` - already-tried source
- **S267** `NOTES.md:3172-3176` - already-tried source
- **S268** `results/PORT-V027-PLAN.md:28` - already-tried source
- **S269** `results/r22/switch-diag/decode-loss.md:16-21` - already-tried source
- **S270** `NOTES.md:5231` - already-tried source
- **S271** `results/r22/gap16/decision.txt:2-11` - already-tried source
- **S272** `NOTES.md:5209` - already-tried source
- **S273** `NOTES.md:5212-5214` - already-tried source
- **S274** `NOTES.md:5296-5298` - already-tried source
- **S275** `NOTES.md:2275` - already-tried source
- **S276** `NOTES.md:2303-2308` - already-tried source
- **S277** `results/r22/gap17/decision.txt:52-56` - already-tried source
- **S278** `results/r23/decode-timing/screen-rerun/decision-b-final.txt:13-15` - already-tried source
- **S279** `results/r23/decode-timing/gap-a/decision.txt:16-17` - already-tried source
- **S280** `results/r23/decode-timing/screen-rerun/decision-b-final.txt:10-12` - already-tried source
- **S281** `results/r23/decode-timing/screen-rerun/decision-b-final.txt:16-28` - already-tried source
- **S282** `results/r23/decode-timing/gap-a/decision.txt:14-15` - already-tried source
- **S283** `results/r22/gap18/decision.txt:2-7` - already-tried source
- **S284** `results/r22/gap7/dec-PL.md:3` - already-tried source
- **S285** `results/r23/decode-timing/ANALYSIS.md:22-24` - already-tried source
- **S286** `results/r23/decode-timing/t2/report-T2dv.txt:4-5` - already-tried source
- **S287** `results/r23/decode-timing/ANALYSIS.md:160` - already-tried source
- **S288** `results/r23/decode-timing/gap-a/timing/report-Bt.txt:4` - already-tried source
- **S289** `NOTES.md:3963` - already-tried source
- **S290** `NOTES.md:6100` - already-tried source
- **S291** `NOTES.md:3961-3962` - already-tried source
- **S292** `NOTES.md:5215` - already-tried source
- **S293** `NOTES.md:1444` - already-tried source
- **S294** `results/r23/port-0211/PORT.md:202-215` - already-tried source
- **S295** `results/r22/gap16/decision.txt:2-3` - already-tried source
- **S296** `results/r22/switch-diag/decode-loss.md:157-161` - already-tried source
- **S297** `NOTES.md:8047-8054` - already-tried source
- **S298** `results/r22/conc/tables.md:5-14` - already-tried source
- **S299** `results/round12-summary.md:13` - already-tried source
- **S300** `../basalt-ab/PLAN.md:120-121` - already-tried source
- **S301** `HANDOFF.md:127-131` - already-tried source
- **S302** `results/r21/yq/compare2.md:32` - already-tried source
- **S303** `notes/strata-v0144-nvfp4-pack.md:21-27` - already-tried source
- **S304** `results/r21/yq/compare2.md:26` - already-tried source
- **S305** `NOTES.md:4562-4564` - already-tried source
- **S306** `NOTES.md:6031-6034` - already-tried source
- **S307** `results/r23/ud31/decision.txt:24-25` - already-tried source
- **S308** `results/r23/ud31/decision.txt:45-46` - already-tried source
- **S309** `NOTES.md:4605-4608` - already-tried source
- **S310** `NOTES.md:4232-4235` - already-tried source
- **S311** `../basalt-020/REPORT.md:20-23` - already-tried source
- **S312** `../basalt-020/results/followup-decision.md:14` - already-tried source
- **S313** `../basalt-020/results/followup-decision.md:18` - already-tried source
- **S314** `../basalt-ab/PLAN.md:113-116` - already-tried source
- **S315** `notes/basalt-ab-results.md:22-23` - already-tried source
- **S316** `results/r22/gap17/decision.txt:1-10` - already-tried source
- **S317** `results/r23/port-0211/gap/decision.txt:1-4` - already-tried source
- **S318** `results/r23/port-0211/confirm/decision.txt:3` - already-tried source
- **S319** `results/r23/port-0211/confirm/decision.txt:38` - already-tried source
- **S320** `results/r22/port-027.md:100-112` - already-tried source
- **S321** `results/PORT-V027-PLAN.md:22-28` - already-tried source
- **S322** `notes/reasoning-effort-local.md:15-19` - already-tried source
- **S323** `NOTES.md:5284` - already-tried source
- **S324** `notes/kernel-oops-pinned-memory.md:11-15` - already-tried source
- **S325** `results/BACKLOG-1027.md:127-152` - already-tried source
- **S326** `NOTES.md:9605` - already-tried source
- **S327** `HANDOFF.md:97-108` - already-tried source

## Appendix B. How this pack was made

- Generator `profile_pack.py` 1 (2026-11-09); inputs `work/qwen4-kit/profile-pack/inputs-flashnext.json`; GGUF header read with the tree's tools/gguf_reader.py.
- Read-only: configs, engine SOURCE / SHA256, GGUF headers, JSONL speed records, engine logs, server guard lines, 1-second monitor CSVs, the decode-timing report, the project's notes. Nothing on the GPU.
- Privacy scrub before writing: no username, home path, hostname, IP other than 127.0.0.1, UUID, email, API key or token, or the owner's other tools; the generator refuses to write otherwise.

